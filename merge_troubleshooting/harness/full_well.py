"""Run the (winner) config end-to-end on a dataset's full well and report final rates.

vaishnavi/pdac: hash (cached) -> multistep_alignment seeded by anchors (winner alignment
levers) -> per-pair merge (winner threshold/warp) -> distance dedup.
owen_40x/owen_20x: reuse the existing fast_alignment (can't re-derive) -> same merge+dedup.

Distance-only dedup priors (mock data lacks the gene/fov feature columns the real pipeline
tie-breakers use; those only split same-distance ties, not the matched count).
"""
import json
import sys
import time

import numpy as np
import pandas as pd

import datasets as D
import cache as C
import run_config as RC

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.merge_utils import align_metadata  # noqa: E402
from lib.merge.hash import multistep_alignment  # noqa: E402
from lib.merge.fast_merge import merge_triangle_hash  # noqa: E402
from lib.merge.deduplicate_merge import deduplicate_cells  # noqa: E402

RESULTS = D.MT_DIR / "results"
ANCHOR_DIR = D.MT_DIR / "cache" / "anchors"


def _alignment(name, cfg, ph_h, sbs_h, ds):
    """Return a DataFrame of per-pair (tile, site, rotation, translation, determinant, score)."""
    if D.REGISTRY[name].get("use_existing_alignment"):
        fa = pd.read_parquet(D.raw_path(name, "fast_alignment"))
        fa["rotation"] = [np.array([a, b]) for a, b in zip(fa.rotation_1, fa.rotation_2)]
        det_med = float(fa[fa.score > 0.3].determinant.median())
        band = (det_med * 0.85, det_med * 1.15)
        return fa[(fa.score > 0.1) & (fa.determinant.between(*band))].copy(), band
    # vaishnavi/pdac: re-derive via multistep seeded by anchors
    a = json.loads((ANCHOR_DIR / f"{name}.json").read_text())
    det_range = a["det_range"]
    ph_meta = ds["ph_meta"].drop_duplicates("tile").copy()
    sbs_meta = ds["sbs_meta"].drop_duplicates("tile").copy()
    if "cycle" in sbs_meta.columns and D.REGISTRY[name].get("sbs_cycle") is not None:
        sbs_meta = sbs_meta[sbs_meta.cycle == D.REGISTRY[name]["sbs_cycle"]]
    for m in (ph_meta, sbs_meta):
        for c in ("x_pos", "y_pos"):
            m[c] = m[c].astype(float)
    ph_a, sb_a, _ = align_metadata(ph_meta, sbs_meta, x_col="x_pos", y_col="y_pos")
    ph_xy = ph_a.set_index("tile")[["x_pos", "y_pos"]].rename(columns={"x_pos": "x", "y_pos": "y"})
    sb_xy = sb_a.set_index("tile")[["x_pos", "y_pos"]].rename(columns={"x_pos": "x", "y_pos": "y"})
    well = multistep_alignment(
        ph_h, sbs_h,  # ph_h has 'tile', sbs_h has 'site' (renamed in run())
        ph_xy, sb_xy, det_range=tuple(det_range), score=0.1,
        initial_sites=a["initial_sites"], n_jobs=8,
        evaluate_kwargs=RC.build_eval_kwargs(cfg) or None,
    )
    well = well[(well.determinant.between(*det_range)) & (well.score > 0.1)].copy()
    return well, det_range


def run(name, cfg):
    t0 = time.time()
    ds = D.load(name)
    ph_info, sbs_info = ds["phenotype_info"], ds["sbs_info"]
    ph_h = C.hashed(name, "phenotype")
    sbs_h = C.hashed(name, "sbs").rename(columns={"tile": "site"})
    align, band = _alignment(name, cfg, ph_h, sbs_h, ds)
    print(f"[{name}] {len(align)} aligned pairs ({time.time()-t0:.0f}s)", flush=True)

    wk = RC.build_warp_kwargs(cfg); thr = cfg.get("threshold", 4); refine = cfg.get("local_refinement")
    merged = []
    for _, row in align.iterrows():
        p = ph_info[ph_info.tile == row["tile"]]
        s = sbs_info[sbs_info.tile == row["site"]]
        if len(p) < 3 or len(s) < 3:
            continue
        merged.append(merge_triangle_hash(p, s, row, threshold=thr,
                                          local_refinement=refine, warp_kwargs=wk or None))
    merged = pd.concat(merged, ignore_index=True)
    dedup, _ = deduplicate_cells(merged.assign(mapped_single_gene=False),
                                 mapped_single_gene=False, return_stats=True, approach="fast",
                                 sbs_dedup_prior={"distance": True},
                                 pheno_dedup_prior={"distance": True})
    msbs = dedup[["plate", "well", "site", "cell_1"]].drop_duplicates().shape[0]
    mph = dedup[["plate", "well", "tile", "cell_0"]].drop_duplicates().shape[0]
    summary = dict(
        dataset=name, config=cfg, det_band=[round(b, 5) for b in band],
        aligned_pairs=int(len(align)), raw_merged=int(len(merged)), deduped=int(len(dedup)),
        total_sbs=int(len(sbs_info)), total_ph=int(len(ph_info)),
        sbs_rate_pct=round(100 * msbs / len(sbs_info), 2),
        ph_rate_pct=round(100 * mph / len(ph_info), 2),
        median_dist_px=round(float(dedup.distance.median()), 3),
        frac_under_2px=round(100 * (dedup.distance < 2).mean(), 2),
        seconds=round(time.time() - t0, 0),
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"full_{name}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return summary


if __name__ == "__main__":
    name = sys.argv[1]
    cfg = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"threshold": 4, "local_refinement": "polynomial"}
    run(name, cfg)
