"""Honest region-level merge ceiling for an SBS tile.

Per-pair %PH is misleading: one SBS tile (1788um) overlaps ~3 PH tiles (1040um), so
pairing an SBS tile with ONE PH tile leaves SBS cells whose partner is in a neighbor PH
tile unmatched (not an alignment failure). And some cells have NO partner at all
(segmentation/coverage). This decomposes the unmatched.

For a target SBS tile:
  1. find ALL PH tiles overlapping it (nearest within a stage-distance cutoff)
  2. fit each (PH tile -> SBS tile) transform (hash + evaluate_match), keep passing ones
  3. map all those PH cells into the SBS tile frame and POOL them
  4. bucket SBS cells by nearest pooled-PH distance:
       <2px   = matched (alignment good)
       2-10px = partner present but misaligned  (refinement headroom)
       >10px  = NO partner present              (segmentation/coverage ceiling)
"""
import sys, warnings; import numpy as np, pandas as pd
from scipy.spatial.distance import cdist
warnings.filterwarnings("ignore")
WF="/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"; sys.path.insert(0,WF)
D="/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"
from lib.merge.hash import find_triangles, evaluate_match
from lib.merge.merge_utils import find_closest_tiles
from lib.merge.fast_merge import build_linear_model, refine_local_warp

ph_info=pd.read_parquet(f"{D}/P-1_W-A1__phenotype_info.parquet")
sbs_info=pd.read_parquet(f"{D}/P-1_W-A1__sbs_info.parquet")
sb=pd.read_parquet(f"{D}/preprocess_metadata_sbs/P-1_W-A1__combined_metadata.parquet"); sb=sb[sb.cycle==1].drop_duplicates("tile")
ph_meta=pd.read_parquet(f"{D}/preprocess_metadata_phenotype/P-1_W-A1__combined_metadata.parquet").drop_duplicates("tile")
DET=(0.065,0.080); SCORE=0.1; OVERLAP_UM=1300   # SBS_half(894)+PH_half(520) ~ 1414; use 1300 cutoff

def fit_pair(ph_tile, sbs_tile):
    pc=ph_info[ph_info.tile==ph_tile]; sc=sbs_info[sbs_info.tile==sbs_tile]
    if len(pc)<10 or len(sc)<10: return None
    pt=find_triangles(pc[["i","j"]].assign(well="A1",tile=ph_tile))
    st=find_triangles(sc[["i","j"]].assign(well="A1",tile=sbs_tile))
    R,t,score=evaluate_match(pt,st)
    if R is None: return None
    det=np.linalg.det(R)
    if not (DET[0]<=det<=DET[1] and score>SCORE): return None
    return R,t,score

def analyze(sbs_tile, refine=False):
    sc=sbs_info[sbs_info.tile==sbs_tile]; Y=sc[["i","j"]].values.astype(float)
    # overlapping PH tiles by stage distance
    cl=find_closest_tiles(sb, ph_meta, sbs_tile, verbose=False)
    near=cl[cl["distance"]<=OVERLAP_UM]["tile"].astype(int).tolist()
    pooled=[]; used=[]
    for pt in near:
        fit=fit_pair(pt, sbs_tile)
        if fit is None: continue
        R,t,score=fit; used.append((pt,round(score,2)))
        X=ph_info[ph_info.tile==pt][["i","j"]].values.astype(float)
        Yp=build_linear_model(R,t).predict(X)
        if refine: Yp=refine_local_warp(X,Y,Yp,2.0)
        pooled.append(Yp)
    if not pooled:
        print(f"SBS {sbs_tile}: no passing PH tiles"); return
    P=np.vstack(pooled)
    # nearest pooled-PH for each SBS cell
    dmin=np.sqrt(cdist(Y,P,"sqeuclidean").min(1))
    nS=len(Y)
    matched=(dmin<2).sum(); near10=((dmin>=2)&(dmin<10)).sum(); nopart=(dmin>=10).sum()
    has_partner=(dmin<10).sum()
    print(f"SBS {sbs_tile}: {nS} SBS cells | overlapping PH tiles used={used}")
    print(f"   matched <2px        : {matched:5d}  ({100*matched/nS:.1f}% of SBS)")
    print(f"   misaligned 2-10px   : {near10:5d}  ({100*near10/nS:.1f}%)  <- alignment headroom")
    print(f"   NO partner >10px    : {nopart:5d}  ({100*nopart/nS:.1f}%)  <- segmentation/coverage ceiling")
    print(f"   => match rate vs ACHIEVABLE ceiling (cells with a partner): "
          f"{100*matched/max(has_partner,1):.1f}%  (vs {100*matched/nS:.1f}% of all SBS)")
    return

for st in [280, 140, 168]:   # worst, median, best (by earlier per-pair %)
    print(f"\n{'='*70}")
    analyze(st, refine=False)
    print("   --- with local_refinement(polynomial) on each pair before pooling ---")
    analyze(st, refine=True)
