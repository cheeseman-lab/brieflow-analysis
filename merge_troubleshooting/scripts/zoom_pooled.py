"""Zoomed overlay using POOLED PH (all overlapping PH tiles, each affine+refined) — the
real well-level merge. Does the matching look good when done properly? Center + edge crops.
"""
import sys, warnings; import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
warnings.filterwarnings("ignore")
WF="/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"; sys.path.insert(0,WF)
D="/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"
OUT="/lab/ops_analysis_ssd/test_matteo/brieflow-speed/merge_troubleshooting/figures"
from lib.merge.hash import find_triangles, evaluate_match
from lib.merge.merge_utils import find_closest_tiles
from lib.merge.fast_merge import build_linear_model, refine_local_warp

ph_info=pd.read_parquet(f"{D}/P-1_W-A1__phenotype_info.parquet")
sbs_info=pd.read_parquet(f"{D}/P-1_W-A1__sbs_info.parquet")
sb=pd.read_parquet(f"{D}/preprocess_metadata_sbs/P-1_W-A1__combined_metadata.parquet"); sb=sb[sb.cycle==1].drop_duplicates("tile")
ph_meta=pd.read_parquet(f"{D}/preprocess_metadata_phenotype/P-1_W-A1__combined_metadata.parquet").drop_duplicates("tile")
DET=(0.065,0.080); SCORE=0.1; OVERLAP_UM=1300; WIN=180; THR=4.0

def pooled(sbs_tile, refine):
    sc=sbs_info[sbs_info.tile==sbs_tile]; Y=sc[["i","j"]].values.astype(float)
    near=find_closest_tiles(sb,ph_meta,sbs_tile,verbose=False)
    near=near[near["distance"]<=OVERLAP_UM]["tile"].astype(int).tolist(); P=[]; used=[]
    st=find_triangles(sc[["i","j"]].assign(well="A1",tile=sbs_tile))
    for pt in near:
        pc=ph_info[ph_info.tile==pt]
        if len(pc)<10: continue
        ptr=find_triangles(pc[["i","j"]].assign(well="A1",tile=pt))
        R,t,score=evaluate_match(ptr,st)
        if R is None or not (DET[0]<=np.linalg.det(R)<=DET[1] and score>SCORE): continue
        X=pc[["i","j"]].values.astype(float); Yp=build_linear_model(R,t).predict(X)
        if refine: Yp=refine_local_warp(X,Y,Yp,2.0)
        P.append(Yp); used.append(pt)
    return Y,(np.vstack(P) if P else None),used

for sbs_t,label in [(280,"tile280"),(168,"tile168")]:
    Y,Pr,used=pooled(sbs_t,True); _,Pa,_=pooled(sbs_t,False)
    print(f"SBS {sbs_t}: pooled PH from tiles {used}")
    rng=Y.max(0)-Y.min(0); ctr=Y.mean(0)
    crops={"center":ctr,"edge":(Y[:,0].min()+0.12*rng[0],Y[:,1].min()+0.12*rng[1])}
    fig,axes=plt.subplots(2,2,figsize=(15,15))
    for r,(cn,(pi,pj)) in enumerate(crops.items()):
        for c,(P,tag) in enumerate([(Pa,"pooled affine"),(Pr,"pooled affine+refine")]):
            ax=axes[r][c]
            ss=(np.abs(Y[:,0]-pi)<WIN)&(np.abs(Y[:,1]-pj)<WIN)
            sp=(np.abs(P[:,0]-pi)<WIN)&(np.abs(P[:,1]-pj)<WIN)
            Ys=Y[ss]; Ps=P[sp]
            ax.scatter(Ys[:,1],Ys[:,0],s=140,facecolors="none",edgecolors="#2ca02c",linewidths=1.6,label=f"SBS ({len(Ys)})")
            ax.scatter(Ps[:,1],Ps[:,0],s=20,c="#d62728",label=f"pooled PH→SBS ({len(Ps)})")
            nm=0
            if len(Ys) and len(Ps):
                d=cdist(Ys,Ps); j=d.argmin(1); dm=d.min(1)
                for k in range(len(Ys)):
                    if dm[k]<THR:
                        nm+=1; ax.plot([Ys[k,1],Ps[j[k],1]],[Ys[k,0],Ps[j[k],0]],"-",c="#555",lw=0.7)
            ax.set_title(f"SBS {sbs_t} {cn} — {tag}\n{nm}/{len(Ys)} SBS matched <{THR:.0f}px in crop")
            ax.invert_yaxis(); ax.set_aspect("equal"); ax.legend(loc="upper right",fontsize=8)
    plt.tight_layout()
    p=f"{OUT}/zoom_pooled_{label}.png"; fig.savefig(p,dpi=110,bbox_inches="tight"); plt.close(fig)
    print(f"saved {p}")
