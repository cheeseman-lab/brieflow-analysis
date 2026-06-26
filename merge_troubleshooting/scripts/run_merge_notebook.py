"""Drive the 5_merge.py notebook's FAST-mode flow on Vaishnavi's flat data.

Reproduces, cell-for-cell, the notebook's lib calls (plot_combined_tile_grid ->
find_closest_tiles -> hash_cell_locations -> initial_alignment ->
plot_alignment_quality -> fast_merge_example/plot_merge_example) and dumps every
QC figure + a structured log, so we can SEE the "weird" plots and catalog issues.
"""
import sys, warnings, traceback
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
D = "/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"
OUT = "/run/user/5573/claude-5573/-lab-ops-analysis-ssd-test-matteo-brieflow-speed/88da5ac2-2c45-4fdd-9615-84f2f5f8c28e/scratchpad/merge_qc"
import os; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, WF)

from lib.merge.merge_utils import (
    plot_combined_tile_grid, align_metadata, find_closest_tiles, plot_merge_example,
)
from lib.merge.hash import hash_cell_locations, initial_alignment
from lib.merge.eval_alignment import plot_alignment_quality

def save(name):
    plt.gcf().savefig(f"{OUT}/{name}", dpi=110, bbox_inches="tight"); plt.close("all")

# ---- load her FLAT data (notebook expects nested paths; ISSUE #1) ----
ph_info = pd.read_parquet(f"{D}/P-1_W-A1__phenotype_info.parquet")
sbs_info = pd.read_parquet(f"{D}/P-1_W-A1__sbs_info.parquet")
ph_meta = pd.read_parquet(f"{D}/preprocess_metadata_phenotype/P-1_W-A1__combined_metadata.parquet")
sbs_meta = pd.read_parquet(f"{D}/preprocess_metadata_sbs/P-1_W-A1__combined_metadata.parquet")

# notebook: dedup pheno metadata; sbs filter cycle==SBS_METADATA_CYCLE(=1)
ph_meta = ph_meta.drop_duplicates(subset=["plate","well","tile"])
sbs_meta = sbs_meta[sbs_meta["cycle"] == 1].drop_duplicates(subset=["plate","well","tile"])

PH_DIM = (3200, 3200); SBS_DIM = (1480, 1480)   # her config dims
print(f"PH tiles {ph_meta.tile.nunique()}  SBS tiles {sbs_meta.tile.nunique()}")
print(f"PH cells {len(ph_info):,}  SBS cells {len(sbs_info):,}")

# ---- CELL: combined tile grid (raw) -> her 'weird' grid (point 1) ----
fig = plot_combined_tile_grid(ph_meta, sbs_meta, ph_image_dims=PH_DIM, sbs_image_dims=SBS_DIM)
save("01_tile_grid_raw.png")
# diagnostics for point 1: coordinate-origin offset between scopes
ph_cx, ph_cy = ph_meta.x_pos.mean(), ph_meta.y_pos.mean()
sb_cx, sb_cy = sbs_meta.x_pos.mean(), sbs_meta.y_pos.mean()
print(f"\n[point1] PH center=({ph_cx:.0f},{ph_cy:.0f})  SBS center=({sb_cx:.0f},{sb_cy:.0f})  "
      f"offset=({sb_cx-ph_cx:.0f},{sb_cy-ph_cy:.0f}) um")

# ---- CELL: METADATA_ALIGN center-align (shows the offset is cosmetic) ----
sbs_al, ph_al, tinfo = align_metadata(sbs_meta, ph_meta, flip_x=False, flip_y=False, rotate_90=False)
fig = plot_combined_tile_grid(ph_al, sbs_al, ph_image_dims=PH_DIM, sbs_image_dims=SBS_DIM)
save("02_tile_grid_centeraligned.png")

# ---- CELL: DET_RANGE from optics. Fitted transform maps PH->SBS coords, so its
# linear scale = pheno_px/sbs_px and determinant = (pheno_px/sbs_px)^2 (NOT the
# inverse). Getting this direction wrong is exactly Vaishnavi's point-3 confusion.
MxB = sbs_meta.pixel_size_x.iloc[0] / ph_meta.pixel_size_x.iloc[0]  # magnification*binning factor
det_exp = 1.0 / (MxB**2)                                            # notebook formula: 1/(M*B)^2
DET_RANGE = [0.9*det_exp, 1.1*det_exp]
SCORE = 0.1
print(f"\n[point3] M*B (pheno_px/sbs_px ratio)={MxB:.4f}  expected det=1/(M*B)^2={det_exp:.5f}  "
      f"DET_RANGE={[round(x,5) for x in DET_RANGE]}")
print(f"         brieflow default det_range=(1.125,1.186) -> would reject ALL (off by ~16x)")

# ---- CELL: auto initial sites (find_closest_tiles) ----
sbs_tiles = sorted(sbs_meta.tile.unique())
INITIAL_SBS_TILES = sbs_tiles[:: max(1, len(sbs_tiles)//11)][:11]
candidate_pairs = []
for st in INITIAL_SBS_TILES:
    closest = find_closest_tiles(sbs_meta, ph_meta, st, verbose=False)
    candidate_pairs.append([int(closest.iloc[0]["tile"]), int(st)])
print(f"\nInitial candidate pairs (ph,sbs): {candidate_pairs}")

# ---- CELL: hash + initial_alignment (subset to candidate tiles for speed) ----
cand_ph = {p for p,_ in candidate_pairs}; cand_sbs = {s for _,s in candidate_pairs}
ph_sub = ph_info[ph_info.tile.isin(cand_ph)].copy()
sbs_sub = sbs_info[sbs_info.tile.isin(cand_sbs)].copy()
ph_hash = hash_cell_locations(ph_sub)
sbs_hash = hash_cell_locations(sbs_sub).rename(columns={"tile":"site"})
ia = initial_alignment(ph_hash, sbs_hash, initial_sites=candidate_pairs)
ia = ia.dropna(subset=["determinant"])
print("\n=== initial_alignment_df ===")
print(ia[["tile","site","score","determinant"]].to_string(index=False))

# ---- CELL: plot_alignment_quality (det gating scatter) ----
try:
    plot_alignment_quality(ia, det_range=DET_RANGE, score=SCORE, xlim=(0,0.1), ylim=(0,1))
    save("03_alignment_quality.png")
except Exception as e:
    print(f"plot_alignment_quality ERR: {e}")

# ---- CELL: validation (>=5 pairs) ----
d0,d1 = DET_RANGE
valid = ia.query("@d0 <= determinant <= @d1 & score > @SCORE")
print(f"\n[validation] {len(valid)}/{len(ia)} pairs pass DET_RANGE+SCORE (need >=5)")

# ---- CELL: fast_merge_example for BEST and WORST pair (her screenshots) ----
THRESHOLD = 2
ia_sorted = ia.sort_values("score")
def merge_example(row, tag):
    Xn = len(ph_sub[ph_sub.tile==row.tile]); Yn = len(sbs_sub[sbs_sub.tile==row.site])
    try:
        plot_merge_example(ph_sub, sbs_sub, row, threshold=THRESHOLD); save(f"04_merge_{tag}.png")
    except Exception as e:
        print(f"  plot err {tag}: {e}")
    # recompute match count to quantify per-tile merge rate
    from lib.merge.fast_merge import build_linear_model
    from scipy.spatial.distance import cdist
    X = ph_sub[ph_sub.tile==row.tile][["i","j"]].values
    Y = sbs_sub[sbs_sub.tile==row.site][["i","j"]].values
    m = build_linear_model(row.rotation, row.translation); Yp = m.predict(X)
    dmin = np.sqrt(cdist(Y, Yp, metric="sqeuclidean").min(axis=1))
    nmatch = (dmin < THRESHOLD).sum()
    print(f"  [{tag}] ph_tile={row.tile} sbs_site={row.site} score={row.score:.2f} "
          f"det={row.determinant:.5f} | PH={Xn} SBS={Yn} matched={nmatch} "
          f"({100*nmatch/max(Xn,1):.1f}% of PH cells, {100*nmatch/max(Yn,1):.1f}% of SBS)")

print("\n=== per-pair merge examples ===")
merge_example(ia_sorted.iloc[-1], "best")
merge_example(ia_sorted.iloc[0], "worst")
# median pair
merge_example(ia_sorted.iloc[len(ia_sorted)//2], "median")

print(f"\nFigures saved to {OUT}")
print("done")
