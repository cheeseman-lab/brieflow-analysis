"""Before/after the local_refinement augmentation on the POOLED region (all overlapping
PH tiles -> meaningful % of SBS cells). 2x2: threshold {2,4} x augmentation {off,on}.
Saves spatial images (matched / unmatched / recovered-by-augmentation).
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
DET=(0.065,0.080); SCORE=0.1; OVERLAP_UM=1300
TILES=[(280,"worst"),(140,"median"),(168,"best")]

def pooled(sbs_tile, refine):
    sc=sbs_info[sbs_info.tile==sbs_tile]; Y=sc[["i","j"]].values.astype(float)
    near=find_closest_tiles(sb,ph_meta,sbs_tile,verbose=False)
    near=near[near["distance"]<=OVERLAP_UM]["tile"].astype(int).tolist(); P=[]
    st=find_triangles(sc[["i","j"]].assign(well="A1",tile=sbs_tile))
    for pt in near:
        pc=ph_info[ph_info.tile==pt]
        if len(pc)<10: continue
        ptr=find_triangles(pc[["i","j"]].assign(well="A1",tile=pt))
        R,t,score=evaluate_match(ptr,st)
        if R is None or not (DET[0]<=np.linalg.det(R)<=DET[1] and score>SCORE): continue
        X=pc[["i","j"]].values.astype(float); Yp=build_linear_model(R,t).predict(X)
        if refine: Yp=refine_local_warp(X,Y,Yp,2.0)
        P.append(Yp)
    return Y,(np.vstack(P) if P else None)

rows=[]
for sbs_t,label in TILES:
    Y,_=pooled(sbs_t,False)
    _,P_off=pooled(sbs_t,False); _,P_on=pooled(sbs_t,True)
    d_off=cdist(Y,P_off,"euclidean").min(1); d_on=cdist(Y,P_on,"euclidean").min(1)
    nS=len(Y)
    for thr in (2,4):
        rows.append((label,sbs_t,thr,nS,int((d_off<thr).sum()),int((d_on<thr).sum())))
    # image at thr=4 (as requested) and thr=2 (where augmentation effect is largest)
    for thr in (2,4):
        moff=d_off<thr; mon=d_on<thr; rec=mon&~moff
        state=np.where(moff,"matched",np.where(rec,"recovered","unmatched"))
        fig,(axL,axR)=plt.subplots(1,2,figsize=(17,8.4),sharex=True,sharey=True)
        def draw(ax,states,title):
            for stt,c,s,a,mk in [("unmatched","#d62728",9,0.5,"o"),("matched","#2ca02c",9,0.5,"o"),
                                 ("recovered","#ff7f0e",36,0.95,"*")]:
                sel=states==stt
                if sel.sum(): ax.scatter(Y[sel,1],Y[sel,0],c=c,s=s,alpha=a,marker=mk,
                                         edgecolors="none",label=f"{stt} ({sel.sum()})")
            ax.set_title(title,fontsize=12); ax.invert_yaxis(); ax.set_aspect("equal")
            ax.legend(loc="upper right",markerscale=1.5,fontsize=9)
        draw(axL,np.where(moff,"matched","unmatched"),
             f"BEFORE (affine only)\nmatched {moff.sum()}/{nS} ({100*moff.mean():.1f}% of SBS)")
        draw(axR,state,
             f"AFTER (+ local_refinement)\nmatched {mon.sum()}/{nS} ({100*mon.mean():.1f}%)  +{rec.sum()} recovered")
        fig.suptitle(f"local_refinement before/after @ threshold={thr}px — SBS tile {sbs_t} ({label}), pooled overlap",fontsize=14)
        fig.tight_layout(rect=[0,0,1,0.94])
        p=f"{OUT}/ba_sbs{sbs_t}_{label}_thr{thr}.png"; fig.savefig(p,dpi=120,bbox_inches="tight"); plt.close(fig)
        print(f"saved {p}")

df=pd.DataFrame(rows,columns=["label","sbs","thr","nSBS","off","on"])
df["off%"]=100*df.off/df.nSBS; df["on%"]=100*df.on/df.nSBS; df["lift_pp"]=df["on%"]-df["off%"]
print("\n=== 2x2: pooled %SBS matched (threshold x augmentation) ===")
print(df.to_string(index=False,float_format=lambda x:f"{x:.1f}"))
print("\nNote: thr4-off vs thr2-on shows threshold and refinement are partial substitutes;")
print("refinement lets you keep a TIGHT threshold (more precise matches) at similar yield.")
