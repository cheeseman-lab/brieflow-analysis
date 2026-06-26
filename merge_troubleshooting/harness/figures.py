"""Per-(dataset, config) figures for the report, reusing notebook-5 lib functions where
clean (plot_alignment_quality, plot_combined_tile_grid) and a self-contained cell-overlay
for the matching view (plot_merge_example calls plt.show()).
"""
import json
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist

import datasets as D
import run_config as RC
import metric as M
import cache as C
import figure_audit as A

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.hash import evaluate_match  # noqa: E402
from lib.merge.eval_alignment import plot_alignment_quality  # noqa: E402
from lib.merge.merge_utils import (  # noqa: E402
    plot_combined_tile_grid, plot_merge_example, align_metadata, find_closest_tiles,
)

FIGDIR = D.MT_DIR / "figures" / "harness"
ANCHOR_DIR = D.MT_DIR / "cache" / "anchors"
JUMP = 2.0


def _spacing(Y):
    if len(Y) < 5:
        return 12.0
    d = cdist(Y, Y); np.fill_diagonal(d, np.inf)
    return float(np.median(d.min(1)))


def _overlay(ax, X, Y, R, t, refine, wk, thr, title, win=110):
    """Tight zoomed overlay (a `win`-px window at the overlap centre) so individual cells are
    legible even on dense screens; green=SBS, red=mapped PH, grey lines = matches <2px."""
    P = M.map_ph_to_sbs(X, Y, R, t, local_refinement=refine, warp_kwargs={**wk, "_threshold": thr})
    ci, cj = float(P[:, 0].mean()), float(P[:, 1].mean())
    ys = (np.abs(Y[:, 0] - ci) < win) & (np.abs(Y[:, 1] - cj) < win)
    ps = (np.abs(P[:, 0] - ci) < win) & (np.abs(P[:, 1] - cj) < win)
    Yw, Pw = Y[ys], P[ps]
    ax.scatter(Yw[:, 1], Yw[:, 0], s=80, facecolors="none", edgecolors="#2ca02c", linewidths=1.2,
               label=f"SBS ({len(Yw)})")
    ax.scatter(Pw[:, 1], Pw[:, 0], s=22, c="#d62728", label=f"PH->SBS ({len(Pw)})")
    nm = 0
    if len(Yw) and len(Pw):
        d = cdist(Yw, Pw); j = d.argmin(1); dm = d.min(1)
        for k in range(len(Yw)):
            if dm[k] < JUMP:
                nm += 1
                ax.plot([Yw[k, 1], Pw[j[k], 1]], [Yw[k, 0], Pw[j[k], 0]], "-", c="#555", lw=0.6)
    ax.set_xlim(cj - win, cj + win); ax.set_ylim(ci + win, ci - win)
    ax.set_title(f"{title}\n{nm}/{len(Yw)} matched <{JUMP:.0f}px in {2*win}px window "
                 f"({100*nm/max(len(Yw),1):.0f}%)", fontsize=9)
    ax.set_aspect("equal"); ax.legend(loc="upper right", fontsize=7)
    return len(Yw), nm


def matching_figure(name, cfg, ctx=None, n_pairs=3):
    """Baseline (affine) vs candidate config overlay on a few eval pairs."""
    ctx = ctx or RC.load_context(name)
    wk = RC.build_warp_kwargs(cfg); thr = cfg.get("threshold", 4); refine = cfg.get("local_refinement")
    pairs = [p for p in ctx["pairs"] if ctx["ref"].get(p)][:n_pairs]
    fig, axes = plt.subplots(len(pairs), 2, figsize=(12, 5.2 * len(pairs)))
    axes = np.atleast_2d(axes)
    nv, nmatch = [], []
    for r, (ph, site) in enumerate(pairs):
        R, t = ctx["ref"][(ph, site)]
        X, Y = ctx["ph_cells"][ph], ctx["sbs_cells"][site]
        _overlay(axes[r][0], X, Y, R, t, None, {}, 4, f"PH{ph}->SBS{site}  affine only")
        n, m = _overlay(axes[r][1], X, Y, R, t, refine, wk, thr,
                        f"PH{ph}->SBS{site}  tuned (deg3 poly, thr4)")
        nv.append(n); nmatch.append(m)
    fig.suptitle(f"{name}: matching at eval pairs (affine vs tuned config)", fontsize=13)
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    out = FIGDIR / f"{name}__matching.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight"); plt.close(fig)
    m = dict(n_in_view=float(np.mean(nv)) if nv else 0,
             matched_frac=float(sum(nmatch) / max(sum(nv), 1)))
    return out, A.evaluate("matching", m)


def alignment_quality_figure(name, cfg, ctx=None):
    """Reuse notebook-5 plot_alignment_quality on the eval pairs under this config."""
    ctx = ctx or RC.load_context(name)
    ek = RC.build_eval_kwargs(cfg)
    rows = []
    for ph, site in ctx["pairs"]:
        if not ctx["ref"].get((ph, site)):
            continue
        R, t, sc = evaluate_match(ctx["ph_htile"][ph], ctx["sbs_hsite"][site], **ek) if ek \
            else (*ctx["ref"][(ph, site)], None)
        if R is None:
            continue
        det = float(np.linalg.det(R))
        # score under default if not recomputed
        if sc is None:
            _, _, sc = evaluate_match(ctx["ph_htile"][ph], ctx["sbs_hsite"][site])
        rows.append(dict(tile=ph, site=site, determinant=det, score=sc))
    dfa = pd.DataFrame(rows)
    dmin, dmax = dfa.determinant.min(), dfa.determinant.max()
    det_range = (dmin * 0.9, dmax * 1.1)
    res = plot_alignment_quality(dfa, det_range, 0.1, xlim=(dmin * 0.8, dmax * 1.2))
    fig = res[0] if isinstance(res, tuple) else res
    out = FIGDIR / f"{name}__alignment_quality.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight"); plt.close(fig)
    cv = float(dfa.determinant.std() / dfa.determinant.mean()) if len(dfa) else 1.0
    return out, A.evaluate("alignment_quality", dict(n_points=int(len(dfa)), det_cv=cv))


def tile_grid_figure(name):
    """Conventional notebook-5 combined PH/SBS tile grid (reuses plot_combined_tile_grid)."""
    ds = D.load(name)
    ph, sb = ds.get("ph_meta"), ds.get("sbs_meta")
    if ph is None or sb is None:
        return None
    ph = ph.drop_duplicates("tile").copy(); sb = sb.drop_duplicates("tile").copy()
    for m in (ph, sb):
        for c in ("x_pos", "y_pos"):
            m[c] = m[c].astype(float)
    res = plot_combined_tile_grid(ph, sb)
    fig = res[0] if isinstance(res, tuple) else (res if res is not None else plt.gcf())
    out = FIGDIR / f"{name}__tile_grid.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight"); plt.close(fig)
    # frame-overlap on raw stage coords (catches unrelated scopes like owen_40x)
    def _bb(d):
        return d.x_pos.min(), d.x_pos.max(), d.y_pos.min(), d.y_pos.max()
    px0, px1, py0, py1 = _bb(ph); sx0, sx1, sy0, sy1 = _bb(sb)
    ox = max(0, min(px1, sx1) - max(px0, sx0)); oy = max(0, min(py1, sy1) - max(py0, sy0))
    a_ph = (px1 - px0) * (py1 - py0); a_sb = (sx1 - sx0) * (sy1 - sy0)
    frame_overlap = (ox * oy) / max(min(a_ph, a_sb), 1e-9)
    return out, A.evaluate("tile_grid", dict(frame_overlap=float(frame_overlap)))


def pooled_merge_figure(name, cfg, ctx=None):
    """Full SBS tile merged from ALL overlapping phenotype tiles (what the well-level pipeline
    does) — replaces the misleading single-pair merge_example. Coverage ~1 when working."""
    ds = D.load(name)
    ph_info, sbs_info = ds["phenotype_info"], ds["sbs_info"]
    a = json.loads((ANCHOR_DIR / f"{name}.json").read_text())
    det_range = tuple(a["det_range"])
    sites = sorted({int(s) for _, s in a["initial_sites"]})
    wk = RC.build_warp_kwargs(cfg); thr = cfg.get("threshold", 4); refine = cfg.get("local_refinement")
    ek = RC.build_eval_kwargs(cfg)
    use_existing = D.REGISTRY[name].get("use_existing_alignment")

    if use_existing:
        fa = pd.read_parquet(D.raw_path(name, "fast_alignment"))
        fa["R"] = [np.array([x, y]) for x, y in zip(fa.rotation_1, fa.rotation_2)]

        def overlapping(site):
            sub = fa[(fa.site == site) & (fa.determinant.between(*det_range)) & (fa.score > 0.3)]
            return [(int(r.tile), r.R, np.asarray(r.translation)) for _, r in sub.iterrows()]
    else:
        ph_h = C.hashed(name, "phenotype")
        sbs_h = C.hashed(name, "sbs").rename(columns={"tile": "site"})
        ph_meta = ds["ph_meta"].drop_duplicates("tile").copy()
        sbs_meta = ds["sbs_meta"].drop_duplicates("tile").copy()
        if "cycle" in sbs_meta.columns and D.REGISTRY[name].get("sbs_cycle") is not None:
            sbs_meta = sbs_meta[sbs_meta.cycle == D.REGISTRY[name]["sbs_cycle"]]
        for m in (ph_meta, sbs_meta):
            for c in ("x_pos", "y_pos"):
                m[c] = m[c].astype(float)
        ph_a, sb_a, _ = align_metadata(ph_meta, sbs_meta, x_col="x_pos", y_col="y_pos")
        radius = a.get("sbs_pitch_um", 1600)

        def overlapping(site):
            c = find_closest_tiles(sb_a, ph_a, site, verbose=False)
            cand = c[c.distance < radius].tile.astype(int).tolist()
            out = []
            for pt in cand:
                t0 = ph_h[ph_h.tile == pt]; s0 = sbs_h[sbs_h.site == site]
                R, t, sc = evaluate_match(t0, s0, **ek)
                if R is not None and det_range[0] <= np.linalg.det(R) <= det_range[1] and sc > 0.1:
                    out.append((pt, R, t))
            return out

    # pick the anchor site with the most overlapping phenotype tiles
    best = max(sites, key=lambda s: len(overlapping(s)))
    triples = overlapping(best)
    Y = sbs_info[sbs_info.tile == best][["i", "j"]].values.astype(float)
    P = []
    for pt, R, t in triples:
        X = ph_info[ph_info.tile == pt][["i", "j"]].values.astype(float)
        if len(X) >= 5:
            P.append(M.map_ph_to_sbs(X, Y, R, t, local_refinement=refine,
                                     warp_kwargs={**wk, "_threshold": thr}))
    P = np.vstack(P) if P else np.empty((0, 2))

    spacing = _spacing(Y)
    nn = cdist(Y, P).min(1) if len(P) else np.full(len(Y), 1e9)
    covered = nn < spacing
    coverage = float(covered.mean())
    matched_frac = float((nn[covered] < JUMP).mean()) if covered.sum() else 0.0

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.scatter(Y[:, 1], Y[:, 0], s=9, facecolors="none", edgecolors="#2ca02c", linewidths=0.4,
               label=f"SBS ({len(Y)})")
    ax.scatter(P[:, 1], P[:, 0], s=3, c="#d62728",
               label=f"pooled PH->SBS ({len(P)}) from {len(triples)} tiles")
    ax.invert_yaxis(); ax.set_aspect("equal"); ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"{name} SBS {best}: pooled {len(triples)} PH tiles | "
                 f"coverage {coverage:.0%}, matched {matched_frac:.0%}", fontsize=11)
    out = FIGDIR / f"{name}__pooled_merge.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight"); plt.close(fig)
    m = dict(coverage=coverage, matched_frac=matched_frac, empty_frac=1 - coverage,
             n_ph_tiles=len(triples), site=best)
    return out, A.evaluate("pooled_merge", m)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "vaishnavi"
    cfg = {"threshold": 4, "local_refinement": "polynomial", "warp_degree": 3}
    ctx = RC.load_context(name)
    print(matching_figure(name, cfg, ctx))
    print(alignment_quality_figure(name, cfg, ctx))
    print(tile_grid_figure(name))
    print(pooled_merge_figure(name, cfg, ctx))
    print(merge_example_figure(name, ctx))
