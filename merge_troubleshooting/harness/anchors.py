"""Per-dataset anchor selection + empirical det-range derivation.

Anchors = seed (phenotype_tile, sbs_tile) pairs with the phenotype tile FULLY contained in
the SBS tile, validated by triangle-hash det/score, spread across the well. They seed
multistep_alignment. det_range is derived EMPIRICALLY from the candidate determinants (no
pixel-size needed), so it works for every dataset's optics.

owen_20x has no metadata (no tile xy) -> anchors can't be selected; it instead reuses its
existing fast_alignment.parquet (handled in run_config, not here).
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

import datasets as D
import cache as C

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.merge_utils import align_metadata, find_closest_tiles  # noqa: E402
from lib.merge.hash import initial_alignment  # noqa: E402

ANCHOR_DIR = D.MT_DIR / "cache" / "anchors"
SCORE = 0.1
EPS = 0.08                 # det_range = center * (1 +/- EPS)
N_ANCHORS = 10
NEST_POOL = 50             # best-nested SBS tiles to hash/validate
SCORE_FLOOR = 0.5          # prefer strong seeds; relaxed if too few


def _tile_pitch(meta):
    """Median nearest-neighbor distance between tile centers (um) = effective tile pitch."""
    xy = meta[["x_pos", "y_pos"]].values.astype(float)
    d = cdist(xy, xy)
    np.fill_diagonal(d, np.inf)
    return float(np.median(d.min(axis=1)))


def select(name, verbose=True):
    spec = D.REGISTRY[name]
    if spec.get("no_metadata"):
        raise ValueError(f"{name} has no metadata; use its existing fast_alignment instead")

    ds = D.load(name)
    ph_meta, sbs_meta = ds["ph_meta"], ds["sbs_meta"]
    sbs_cycle = spec.get("sbs_cycle")
    if "cycle" in sbs_meta.columns and sbs_cycle is not None:
        sbs_meta = sbs_meta[sbs_meta.cycle == sbs_cycle]
    ph_meta = ph_meta.drop_duplicates("tile").copy()
    sbs_meta = sbs_meta.drop_duplicates("tile").copy()
    # some metadata (owen_40x) store coords as object/Decimal -> coerce for np math
    for m in (ph_meta, sbs_meta):
        for c in ("x_pos", "y_pos"):
            m[c] = m[c].astype(float)

    ph_a, sb_a, _ = align_metadata(ph_meta, sbs_meta, x_col="x_pos", y_col="y_pos")
    ph_pitch, sbs_pitch = _tile_pitch(ph_a), _tile_pitch(sb_a)
    half_diff = (sbs_pitch - ph_pitch) / 2.0   # nested if nearest-PH dist < half_diff

    # nearest + 2nd-nearest PH per SBS tile (best-match + ambiguity margin)
    sm = sb_a.set_index("tile")
    rows = []
    for t in sb_a.tile:
        c = find_closest_tiles(sb_a, ph_a, t, verbose=False)
        d1, d2 = c.iloc[0], c.iloc[1]
        rows.append(dict(sbs_tile=int(t), ph_tile=int(d1.tile),
                         nearest=float(d1.distance), margin=float(d2.distance - d1.distance),
                         x=float(sm.loc[t, "x_pos"]), y=float(sm.loc[t, "y_pos"])))
    cand = pd.DataFrame(rows)
    cand["contained"] = cand.nearest < max(half_diff, 0)
    pool = cand.nsmallest(NEST_POOL, "nearest").copy()

    # hash candidate tiles (cached) and run initial_alignment with NO det gating
    ph_h = C.hashed(name, "phenotype")
    sbs_h = C.hashed(name, "sbs").rename(columns={"tile": "site"})
    ph_h = ph_h[ph_h.tile.isin(set(pool.ph_tile))]
    sbs_h = sbs_h[sbs_h.site.isin(set(pool.sbs_tile))]
    ia = initial_alignment(ph_h, sbs_h, initial_sites=pool[["ph_tile", "sbs_tile"]].values.tolist())
    ia = ia.rename(columns={"tile": "ph_tile", "site": "sbs_tile"})[
        ["ph_tile", "sbs_tile", "determinant", "score"]]
    pool = pool.merge(ia, on=["ph_tile", "sbs_tile"], how="left")

    # empirical det center from score-passing, non-degenerate candidates
    good = pool[(pool.score > SCORE) & (pool.determinant.between(0.005, 0.5))]
    if len(good) < 3:
        raise ValueError(f"{name}: only {len(good)} score-passing candidates; cannot derive det")
    det_center = float(good.determinant.median())
    det_range = [det_center * (1 - EPS), det_center * (1 + EPS)]

    # validate against derived det_range, require contained, then spread by FPS
    pool["valid"] = (pool.determinant.between(*det_range)) & (pool.score > SCORE) & pool.contained
    valid = pool[pool.valid].copy()
    strong = valid[valid.score >= SCORE_FLOOR]
    use = strong if len(strong) >= min(N_ANCHORS, len(valid)) else valid
    use = use.reset_index(drop=True)

    n = min(N_ANCHORS, len(use))
    if n < 1:
        raise ValueError(f"{name}: no valid contained anchors (pool {len(pool)})")
    pts = use[["x", "y"]].values
    idx = [int(use.score.values.argmax())]
    while len(idx) < n:
        dmin = cdist(pts, pts[idx]).min(axis=1); dmin[idx] = -1
        idx.append(int(dmin.argmax()))
    chosen = use.iloc[idx].sort_values("sbs_tile")

    # held-out EVAL pairs: contained+validated tiles NOT used as anchor seeds, spread
    rest = use.drop(index=use.index[idx]).reset_index(drop=True)
    eval_rows = rest
    if len(rest) > 15:
        rp = rest[["x", "y"]].values
        eidx = [int(rest.score.values.argmax())]
        while len(eidx) < 15:
            dm = cdist(rp, rp[eidx]).min(axis=1); dm[eidx] = -1
            eidx.append(int(dm.argmax()))
        eval_rows = rest.iloc[eidx]
    eval_rows = eval_rows.sort_values("sbs_tile")

    result = dict(
        dataset=name, det_center=det_center, det_range=det_range,
        predicted_det=D.predicted_det(ds), eps=EPS,
        ph_pitch_um=ph_pitch, sbs_pitch_um=sbs_pitch, half_diff_um=half_diff,
        n_sbs_tiles=int(sb_a.tile.nunique()), n_contained=int(cand.contained.sum()),
        n_valid=int(len(valid)), n_anchors=int(n),
        initial_sites=chosen[["ph_tile", "sbs_tile"]].astype(int).values.tolist(),
        eval_sites=eval_rows[["ph_tile", "sbs_tile"]].astype(int).values.tolist(),
        anchors=chosen[["sbs_tile", "ph_tile", "nearest", "margin", "determinant", "score"]]
            .round(4).to_dict("records"),
    )
    ANCHOR_DIR.mkdir(parents=True, exist_ok=True)
    (ANCHOR_DIR / f"{name}.json").write_text(json.dumps(result, indent=2))
    if verbose:
        print(json.dumps({k: v for k, v in result.items() if k != "anchors"}, indent=2))
        print("anchors:")
        print(pd.DataFrame(result["anchors"]).to_string(index=False))
    return result


if __name__ == "__main__":
    for n in (sys.argv[1:] or ["vaishnavi"]):
        print(f"\n########## {n} ##########")
        try:
            select(n)
        except Exception as e:
            print(f"ERROR {n}: {type(e).__name__}: {e}")
