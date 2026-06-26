"""Coverage ceiling WITHOUT an arbitrary distance cutoff (Matteo's idea).

After matching, the region where PH cells matched onto SBS = confirmed mutual coverage.
Inside that region both modalities are present + registered, so an unmatched SBS cell
there is a GENUINE miss. We:
  1. match SBS<->pooled-PH at threshold
  2. take the convex hull (and bbox) of the matched SBS cells = confirmed-overlap region
  3. count SBS cells inside; how many are unmatched?  (this needs NO distance cutoff)
  4. sub-classify the unmatched-inside cells by nearest-PH distance, split at the cell
     spacing: < spacing  -> PH present, alignment/dedup miss
              >= spacing -> no PH    -> SEGMENTATION gap (the true ceiling)
"""
import sys, warnings; import numpy as np, pandas as pd
from scipy.spatial.distance import cdist
from scipy.spatial import ConvexHull
from matplotlib.path import Path
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
DET=(0.065,0.080); SCORE=0.1; OVERLAP_UM=1300; THR=4.0

def pooled(sbs_tile):
    sc=sbs_info[sbs_info.tile==sbs_tile]; Y=sc[["i","j"]].values.astype(float)
    cl=find_closest_tiles(sb, ph_meta, sbs_tile, verbose=False)
    near=cl[cl["distance"]<=OVERLAP_UM]["tile"].astype(int).tolist(); P=[]
    for pt in near:
        pc=ph_info[ph_info.tile==pt]
        if len(pc)<10: continue
        ptr=find_triangles(pc[["i","j"]].assign(well="A1",tile=pt))
        st=find_triangles(sc[["i","j"]].assign(well="A1",tile=sbs_tile))
        R,t,score=evaluate_match(ptr,st)
        if R is None or not (DET[0]<=np.linalg.det(R)<=DET[1] and score>SCORE): continue
        X=pc[["i","j"]].values.astype(float)
        P.append(refine_local_warp(X,Y,build_linear_model(R,t).predict(X),2.0))
    return Y,(np.vstack(P) if P else None)

def spacing(A):
    d=cdist(A,A,"euclidean"); np.fill_diagonal(d,np.inf); return np.median(d.min(1))

for st in [280,140,168]:
    Y,P=pooled(st)
    if P is None: continue
    d_sbs=cdist(Y,P,"euclidean").min(1); matched=d_sbs<THR
    sp=spacing(Y)
    mp=Y[matched]
    hull=ConvexHull(mp); hpath=Path(mp[hull.vertices])
    in_hull=hpath.contains_points(Y)
    # bbox of matched
    lo=mp.min(0); hi=mp.max(0); in_bbox=((Y>=lo)&(Y<=hi)).all(1)
    for region,mask in [("bbox",in_bbox),("hull",in_hull)]:
        nin=mask.sum(); mm=matched&mask; um=(~matched)&mask
        nun=um.sum()
        dd=d_sbs[um]
        seg_gap=(dd>=sp).sum()        # no PH within a cell spacing -> segmentation gap
        align_miss=(dd<sp).sum()      # PH present within spacing but beyond THR
        print(f"SBS {st} [{region}] spacing={sp:.1f}px: {nin} SBS in region | "
              f"matched {mm.sum()} ({100*mm.sum()/nin:.1f}%)  unmatched {nun} ({100*nun/nin:.1f}%)")
        print(f"        unmatched-in-region: seg-gap(no PH<{sp:.0f}px)={seg_gap} ({100*seg_gap/max(nun,1):.0f}%)  "
              f"align/dedup(PH present)={align_miss} ({100*align_miss/max(nun,1):.0f}%)")
    print()
