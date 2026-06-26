"""Does raising the match threshold (2->3->4->5 px) help merge rate, or just add
false matches? Measured on the honest pooled-region setup, with local_refinement ON.

For each threshold we report, over SBS cells in a tile (pooled PH from all overlapping
PH tiles, mapped + refined):
  matched%   : nearest PH within threshold
  MNN%       : of matched, fraction that are MUTUAL nearest neighbours (SBS<->PH both
               pick each other) -> trustworthy
  ambig%     : of matched, fraction with a 2nd PH ALSO within threshold -> likely wrong
  d_new      : how many NEW matches vs threshold=2, and what fraction of those are MNN
Context: median nearest-neighbour spacing within each modality (false-match danger zone).
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
DET=(0.065,0.080); SCORE=0.1; OVERLAP_UM=1300

def pooled(sbs_tile):
    sc=sbs_info[sbs_info.tile==sbs_tile]; Y=sc[["i","j"]].values.astype(float)
    cl=find_closest_tiles(sb, ph_meta, sbs_tile, verbose=False)
    near=cl[cl["distance"]<=OVERLAP_UM]["tile"].astype(int).tolist()
    P=[]
    for pt in near:
        pc=ph_info[ph_info.tile==pt];
        if len(pc)<10: continue
        ptr=find_triangles(pc[["i","j"]].assign(well="A1",tile=pt))
        st=find_triangles(sc[["i","j"]].assign(well="A1",tile=sbs_tile))
        R,t,score=evaluate_match(ptr,st)
        if R is None or not (DET[0]<=np.linalg.det(R)<=DET[1] and score>SCORE): continue
        X=pc[["i","j"]].values.astype(float)
        P.append(refine_local_warp(X,Y,build_linear_model(R,t).predict(X),2.0))
    return Y, (np.vstack(P) if P else None)

def nn_spacing(A):
    d=cdist(A,A,"euclidean"); np.fill_diagonal(d,np.inf); return np.median(d.min(1))

for st in [280,140,168]:
    Y,P=pooled(st)
    if P is None: print(f"SBS {st}: no PH"); continue
    DM=cdist(Y,P,"euclidean")          # SBS x PH distances
    order=np.argsort(DM,axis=1)
    d1=DM[np.arange(len(Y)),order[:,0]]; j1=order[:,0]
    d2=DM[np.arange(len(Y)),order[:,1]] if P.shape[0]>1 else np.full(len(Y),np.inf)
    # mutual NN: for each SBS i matched to PH j1[i], is i the nearest SBS to j1[i]?
    sbs_nearest_to_ph=DM.argmin(axis=0)   # for each PH, nearest SBS
    print(f"\nSBS {st}: {len(Y)} SBS cells, {len(P)} pooled PH | "
          f"NN spacing SBS={nn_spacing(Y):.1f}px PH={nn_spacing(P):.1f}px")
    base=None
    print(f"  {'thr':>3} {'matched%':>9} {'MNN%':>6} {'ambig%':>7} {'newVs2':>7} {'new_MNN%':>9}")
    base_set=None
    for thr in [2,3,4,5]:
        m=d1<thr
        mnn=m & (sbs_nearest_to_ph[j1]==np.arange(len(Y)))
        ambig=m & (d2<thr)
        cur=set(np.where(m)[0])
        if thr==2: base_set=cur; newn=0; new_mnn=np.nan
        else:
            new=cur-base_set; newn=len(new)
            new_idx=np.array(sorted(new)) if new else np.array([],dtype=int)
            new_mnn=100*mnn[new_idx].mean() if len(new_idx) else np.nan
        print(f"  {thr:>3} {100*m.mean():>8.1f} {100*mnn.sum()/max(m.sum(),1):>6.1f} "
              f"{100*ambig.sum()/max(m.sum(),1):>6.1f} {newn:>7d} "
              f"{new_mnn if not np.isnan(new_mnn) else 0:>8.1f}")
