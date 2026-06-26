"""Bidirectional, segmentation-fair merge metric (the 2px objective).

Within the phenotype bounding box, what fraction of SBS cells match a phenotype cell (and
vice versa) within a 2px "jump" — counting a cell as a MISS only when a partner actually
exists. "Partner exists" is judged by a FIXED reference alignment (independent of the
candidate config) so a bad candidate alignment is penalized (cells stay in the denominator)
rather than silently dropping out. Segmentation gaps (no partner under the reference) are
excluded from the denominator, so missing segmentation never counts as a merge error.

map_ph_to_sbs() reuses the exact pipeline geometry (build_linear_model + refine_local_warp).
"""
import sys

import numpy as np
from scipy.spatial.distance import cdist

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.fast_merge import build_linear_model, refine_local_warp  # noqa: E402

JUMP = 2.0          # correctness bar (px): a <2px match is unambiguously the same cell
K = 4               # k x k subcells for the uniformity (worst-subcell) term


def map_ph_to_sbs(X, Y, rotation, translation, local_refinement=None, warp_kwargs=None):
    """Predict phenotype cell coords X into SBS space (affine, + optional polynomial warp)."""
    Y_pred = build_linear_model(rotation, translation).predict(X)
    if local_refinement:
        # warp needs Y (target) to pick high-confidence correspondences; uses merge threshold
        thr = (warp_kwargs or {}).get("_threshold", 4.0)
        wk = {k: v for k, v in (warp_kwargs or {}).items() if not k.startswith("_")}
        Y_pred = refine_local_warp(X, Y, Y_pred, thr, **wk)
    return Y_pred


def score_pair(Y, cand_P, ref_P, jump=JUMP, k=K, min_cells=5):
    """Score one (SBS site, mapped-PH) pair.

    Y:      SBS cell coords (m,2)
    cand_P: phenotype cells mapped to SBS under the CANDIDATE config (n,2)
    ref_P:  phenotype cells mapped to SBS under the fixed REFERENCE alignment (n,2)
    Returns dict (or None if too few cells in the overlap).
    """
    if len(Y) < min_cells or len(ref_P) < min_cells:
        return None
    lo, hi = ref_P.min(0), ref_P.max(0)                  # phenotype bbox in SBS space
    inB_sbs = ((Y >= lo) & (Y <= hi)).all(1)
    inB_ph = ((ref_P >= lo) & (ref_P <= hi)).all(1)
    Yb = Y[inB_sbs]
    if len(Yb) < min_cells:
        return None

    # local cell spacing (px) among in-box SBS cells -> "a partner should be within this"
    dd = cdist(Yb, Yb); np.fill_diagonal(dd, np.inf)
    spacing = float(np.median(dd.min(1)))

    # candidate mutual-NN matches at the 2px jump
    d_ps = cdist(cand_P, Y)
    jc = d_ps.argmin(1)                                  # PH -> nearest SBS
    js = d_ps.argmin(0)                                  # SBS -> nearest PH
    ds = d_ps[js, np.arange(len(Y))]                     # SBS match dist
    dp = d_ps[np.arange(len(cand_P)), jc]                # PH match dist
    matched_sbs = (ds < jump) & (jc[js] == np.arange(len(Y)))
    matched_ph = (dp < jump) & (js[jc] == np.arange(len(cand_P)))

    # partner-present under the REFERENCE alignment (segmentation-fair denominator)
    sbs_ref_d = cdist(Y, ref_P).min(1)
    ph_ref_d = cdist(ref_P, Y).min(1)
    sbs_present = inB_sbs & (sbs_ref_d < spacing)
    ph_present = inB_ph & (ph_ref_d < spacing)

    match_sbs = float(matched_sbs[sbs_present].mean()) if sbs_present.sum() else np.nan
    match_ph = float(matched_ph[ph_present].mean()) if ph_present.sum() else np.nan

    # worst subcell (SBS side) for spatial uniformity
    worst = np.nan
    if sbs_present.sum() >= min_cells:
        gx = np.clip(((Y[:, 0] - lo[0]) / (hi[0] - lo[0] + 1e-9) * k).astype(int), 0, k - 1)
        gy = np.clip(((Y[:, 1] - lo[1]) / (hi[1] - lo[1] + 1e-9) * k).astype(int), 0, k - 1)
        cell_id = gx * k + gy
        fr = []
        for cid in range(k * k):
            sel = sbs_present & (cell_id == cid)
            if sel.sum() >= min_cells:
                fr.append(matched_sbs[sel].mean())
        worst = float(min(fr)) if fr else np.nan

    seg_gap = float(1 - sbs_present.sum() / max(inB_sbs.sum(), 1))
    med_dist = float(np.median(ds[matched_sbs])) if matched_sbs.sum() else np.nan
    return dict(
        match_sbs=match_sbs, match_ph=match_ph,
        tile_score=float(np.nanmean([match_sbs, match_ph])),
        worst_subcell=worst, seg_gap_frac=seg_gap,
        n_sbs_present=int(sbs_present.sum()), n_ph_present=int(ph_present.sum()),
        median_match_dist=med_dist, spacing_px=spacing,
    )


def aggregate(tile_results):
    """Tile-weighted dataset summary from a list of score_pair dicts (None dropped)."""
    rows = [r for r in tile_results if r]
    if not rows:
        return dict(dataset_score=np.nan, n_tiles=0)
    arr = lambda key: np.array([r[key] for r in rows], dtype=float)
    return dict(
        dataset_score=float(np.nanmean(arr("tile_score"))),
        match_sbs=float(np.nanmean(arr("match_sbs"))),
        match_ph=float(np.nanmean(arr("match_ph"))),
        worst_subcell=float(np.nanmean(arr("worst_subcell"))),
        seg_gap_frac=float(np.nanmean(arr("seg_gap_frac"))),
        median_match_dist=float(np.nanmedian(arr("median_match_dist"))),
        n_tiles=len(rows),
    )
