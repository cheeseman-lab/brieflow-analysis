"""Evaluate ONE merge config on ONE dataset, scored by the seg-fair metric on held-out
contained pairs. Per-pair evaluation (no full-well multistep) keeps the sweep cheap; the
full-well merge is only run for the final winner (full_well.py).

A config is a flat dict; recognized keys:
  alignment levers : threshold_triangle, threshold_point, threshold_region,
                     ransac_residual_threshold, ransac_max_trials, ransac_min_samples, ransac_random_state
  merge/warp levers: threshold, local_refinement, warp_degree, warp_iterations, warp_min_correspondences
Absent keys -> brieflow defaults (backward compatible).
"""
import json
import sys

import numpy as np
import pandas as pd

import datasets as D
import cache as C
import metric as M

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.hash import evaluate_match  # noqa: E402

ANCHOR_DIR = D.MT_DIR / "cache" / "anchors"


def build_eval_kwargs(cfg):
    rk = {k: cfg.get("ransac_" + k) for k in ("residual_threshold", "max_trials", "min_samples")}
    rk = {k: v for k, v in rk.items() if v is not None}
    if cfg.get("ransac_random_state") is not None:
        rk["random_state"] = cfg["ransac_random_state"]
    ek = {k: cfg.get(k) for k in ("threshold_triangle", "threshold_point", "threshold_region")}
    ek = {k: v for k, v in ek.items() if v is not None}
    if rk:
        ek["ransac_kwargs"] = rk
    return ek


def build_warp_kwargs(cfg):
    wk = {
        "degree": cfg.get("warp_degree"),
        "iterations": cfg.get("warp_iterations"),
        "min_correspondences": cfg.get("warp_min_correspondences"),
    }
    return {k: v for k, v in wk.items() if v is not None}


def load_context(name):
    """Everything needed to score eval pairs for a dataset (built once, reused per config)."""
    ds = D.load(name)
    ph_info, sbs_info = ds["phenotype_info"], ds["sbs_info"]
    ph_h = C.hashed(name, "phenotype")
    sbs_h = C.hashed(name, "sbs").rename(columns={"tile": "site"})

    ref = {}                      # (ph,site) -> (R, t) reference transform
    pairs = []
    if D.REGISTRY[name].get("use_existing_alignment"):
        # Reuse an existing pipeline alignment for datasets we can't re-derive seeds for
        # (owen_40x is too sparse for per-tile triangle matching). Eval pairs = its
        # high-confidence pairs; det band derived from them.
        fa_path = D.raw_path(name, "fast_alignment")
        fa = pd.read_parquet(fa_path)
        det_med = float(fa[fa.score > 0.3].determinant.median())
        band = (det_med * 0.85, det_med * 1.15)
        fa = fa[(fa.score > 0.4) & (fa.determinant.between(*band))]
        fa = fa.sort_values("score", ascending=False).head(25)
        for _, r in fa.iterrows():
            R = np.array([r["rotation_1"], r["rotation_2"]])
            ref[(int(r["tile"]), int(r["site"]))] = (R, np.asarray(r["translation"]))
            pairs.append((int(r["tile"]), int(r["site"])))
    else:
        a = json.loads((ANCHOR_DIR / f"{name}.json").read_text())
        pairs = [tuple(p) for p in a["eval_sites"]]
        # reference transform per pair = default evaluate_match (fixed, config-independent)
        for ph, site in pairs:
            t0 = ph_h[ph_h.tile == ph]
            s0 = sbs_h[sbs_h.site == site]
            R, t, sc = evaluate_match(t0, s0)
            ref[(ph, site)] = None if R is None else (R, t)

    ph_cells = {ph: ph_info[ph_info.tile == ph][["i", "j"]].values.astype(float)
                for ph, _ in pairs}
    sbs_cells = {site: sbs_info[sbs_info.tile == site][["i", "j"]].values.astype(float)
                 for _, site in pairs}
    ph_htile = {ph: ph_h[ph_h.tile == ph] for ph, _ in pairs}
    sbs_hsite = {site: sbs_h[sbs_h.site == site] for _, site in pairs}
    return dict(name=name, pairs=pairs, ref=ref, ph_cells=ph_cells, sbs_cells=sbs_cells,
                ph_htile=ph_htile, sbs_hsite=sbs_hsite)


def run(name, cfg, ctx=None):
    ctx = ctx or load_context(name)
    ek = build_eval_kwargs(cfg)
    wk = build_warp_kwargs(cfg)
    thr = cfg.get("threshold", 4)
    refine = cfg.get("local_refinement")
    recompute_align = bool(ek)        # only recompute transforms if alignment levers set

    tile_results = []
    for ph, site in ctx["pairs"]:
        ref_t = ctx["ref"].get((ph, site))
        if ref_t is None:
            continue
        R0, t0 = ref_t
        X, Y = ctx["ph_cells"][ph], ctx["sbs_cells"][site]
        if len(X) < 5 or len(Y) < 5:
            continue
        if recompute_align:
            Rc, tc, _ = evaluate_match(ctx["ph_htile"][ph], ctx["sbs_hsite"][site], **ek)
            if Rc is None:
                tile_results.append(dict(match_sbs=0.0, match_ph=0.0, tile_score=0.0,
                                         worst_subcell=0.0, seg_gap_frac=np.nan,
                                         n_sbs_present=0, n_ph_present=0,
                                         median_match_dist=np.nan, spacing_px=np.nan))
                continue
        else:
            Rc, tc = R0, t0
        cand_P = M.map_ph_to_sbs(X, Y, Rc, tc, local_refinement=refine,
                                 warp_kwargs={**wk, "_threshold": thr})
        ref_P = M.map_ph_to_sbs(X, Y, R0, t0, local_refinement="polynomial",
                                warp_kwargs={"_threshold": 4.0})
        tile_results.append(M.score_pair(Y, cand_P, ref_P))

    summary = M.aggregate(tile_results)
    summary["dataset"] = name
    summary["config_id"] = config_id(cfg)
    summary.update({f"cfg_{k}": v for k, v in cfg.items()})
    return summary


def config_id(cfg):
    return "|".join(f"{k}={cfg[k]}" for k in sorted(cfg))


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "vaishnavi"
    # default config (all levers at brieflow defaults) + a refined variant
    for cfg in [{"threshold": 4}, {"threshold": 4, "local_refinement": "polynomial"}]:
        print(json.dumps(run(name, cfg), indent=2, default=str))
