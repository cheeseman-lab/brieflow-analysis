"""Examine fast-mode merge alignment on Vaishnavi's troubleshooting data.

Goal: empirically read off, for overlapping SBS<->phenotype tile pairs:
  - the determinant of the fitted transform (tells us correct det_range / scale)
  - the rotation angle embedded in the 2x2 (tells us the inter-scope rotation)
  - the match score
Without guessing config. Pure diagnosis.
"""
import sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
D = "/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"
sys.path.insert(0, WF)

from lib.merge.hash import find_triangles, evaluate_match

ph_info = pd.read_parquet(f"{D}/P-1_W-A1__phenotype_info.parquet")
sbs_info = pd.read_parquet(f"{D}/P-1_W-A1__sbs_info.parquet")
ph_meta = pd.read_parquet(f"{D}/preprocess_metadata_phenotype/P-1_W-A1__combined_metadata.parquet")
sbs_meta = pd.read_parquet(f"{D}/preprocess_metadata_sbs/P-1_W-A1__combined_metadata.parquet")

# one row per tile (sbs has 13 cycles -> filter cycle 1)
sbs_meta1 = sbs_meta[sbs_meta["cycle"] == 1].drop_duplicates("tile")
ph_meta1 = ph_meta.drop_duplicates("tile")
print(f"SBS tiles: {sbs_meta1.tile.nunique()}  PH tiles: {ph_meta1.tile.nunique()}")
print(f"SBS cells: {len(sbs_info):,}  PH cells: {len(ph_info):,}")
print(f"SBS px size: {sbs_meta1.pixel_size_x.iloc[0]}  PH px size: {ph_meta1.pixel_size_x.iloc[0]}")
ratio = ph_meta1.pixel_size_x.iloc[0] / sbs_meta1.pixel_size_x.iloc[0]
print(f"PH->SBS expected linear scale = {ratio:.4f}, expected determinant = {ratio**2:.5f}")
print(f"default det_range=(1.125, 1.186) -> {'OK' if 1.125<=ratio**2<=1.186 else 'REJECTS ALL (scale mismatch)'}")

# stage-coord lookups
sbs_xy = sbs_meta1.set_index("tile")[["x_pos","y_pos"]]
ph_xy = ph_meta1.set_index("tile")[["x_pos","y_pos"]]

def closest_ph(sbs_tile):
    p = sbs_xy.loc[sbs_tile].values
    d = np.sqrt(((ph_xy.values - p)**2).sum(1))
    return int(ph_xy.index[d.argmin()]), float(d.min())

def angle_of(R):
    # R is 2x2 ~ scale*[[cos,-sin],[sin,cos]] (+possible reflection)
    det = np.linalg.det(R)
    refl = det < 0
    # remove scale
    s = np.sqrt(abs(det))
    Rn = R / s if s > 0 else R
    ang = np.degrees(np.arctan2(Rn[1,0], Rn[0,0]))
    return ang, refl

# probe several SBS tiles spread across the well
probe = sorted(sbs_xy.index)[:: max(1, sbs_xy.shape[0]//12)][:12]
print("\n=== per-pair fast-mode evaluate_match ===")
print(f"{'sbs':>4} {'ph':>4} {'stage_d':>8} {'score':>6} {'det':>9} {'angle°':>8} {'refl':>5}  matrix")
for st in probe:
    pt, sd = closest_ph(st)
    s_cells = sbs_info[sbs_info.tile == st]
    p_cells = ph_info[ph_info.tile == pt]
    if len(s_cells) < 5 or len(p_cells) < 5:
        print(f"{st:>4} {pt:>4}  too few cells"); continue
    try:
        s_tri = find_triangles(s_cells[["i","j"]].assign(well="A1", tile=st))
        p_tri = find_triangles(p_cells[["i","j"]].assign(well="A1", tile=pt))
        # evaluate_match(df_t=pheno, df_s=sbs) -> maps pheno->sbs (matches script direction)
        R, t, score = evaluate_match(p_tri, s_tri)
        if R is None:
            print(f"{st:>4} {pt:>4} {sd:>8.0f}  no-match (<5 triangles)")
            continue
        det = np.linalg.det(R)
        ang, refl = angle_of(R)
        print(f"{st:>4} {pt:>4} {sd:>8.0f} {score:>6.2f} {det:>9.5f} {ang:>8.2f} {str(refl):>5}  "
              f"[[{R[0,0]:+.3f} {R[0,1]:+.3f}][{R[1,0]:+.3f} {R[1,1]:+.3f}]]")
    except Exception as e:
        print(f"{st:>4} {pt:>4} {sd:>8.0f}  ERR {e}")
