"""Build owen_40x anchors from its production fast_alignment (stage frames are unrelated and
it's too sparse to discover seeds blind, so we take the run's validated good pairs as the
operator-provided initial_sites). Seeds = top-10 distinct SBS sites; eval = held-out good
pairs on the OTHER sites (disjoint from seeds). det from the good-pair determinant.
"""
import json
import pandas as pd
import datasets as D

fa = pd.read_parquet(D.raw_path("owen_40x", "fast_alignment"))
det_med = float(fa[fa.score > 0.3].determinant.median())
band = (det_med * 0.85, det_med * 1.15)

# owen_40x only has ~12 alignable sites (of 16); can't have 10 seeds AND a held-out set.
# Use the strongest sites (score>0.5) as seeds, hold out the other alignable sites for eval.
seeds = fa[(fa.score > 0.5) & (fa.determinant.between(*band))] \
    .sort_values("score", ascending=False).drop_duplicates("site")
seed_sites = set(seeds.site.astype(int))
held = fa[(fa.score > 0.3) & (fa.determinant.between(*band))
          & (~fa.site.astype(int).isin(seed_sites))] \
    .sort_values("score", ascending=False).drop_duplicates("site")
good = fa[(fa.score > 0.4) & (fa.determinant.between(*band))]

det_center = float(good.determinant.median())
result = dict(
    dataset="owen_40x", det_center=det_center,
    det_range=[det_center * 0.92, det_center * 1.08],
    predicted_det=None, source="production fast_alignment (operator-provided seeds)",
    n_sbs_tiles=int(fa.site.nunique()), n_seed_sites=len(seed_sites), n_eval_sites=int(len(held)),
    initial_sites=seeds[["tile", "site"]].astype(int).values.tolist(),
    eval_sites=held[["tile", "site"]].astype(int).values.tolist(),
    anchors=seeds[["site", "tile", "determinant", "score"]].round(4)
        .rename(columns={"site": "sbs_tile", "tile": "ph_tile"}).to_dict("records"),
)
(D.MT_DIR / "cache" / "anchors").mkdir(parents=True, exist_ok=True)
(D.MT_DIR / "cache" / "anchors" / "owen_40x.json").write_text(json.dumps(result, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != "anchors"}, indent=2))
