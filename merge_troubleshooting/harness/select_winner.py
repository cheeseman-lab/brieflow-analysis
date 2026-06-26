"""Pick the generalized winning config across datasets.

Rule: maximize the WORST-CASE ratio of a config's dataset_score to that dataset's own
optimum (so a config must work everywhere, protecting the owen_40x canary from being
averaged away). Tie-break by weighted mean score (vaishnavi+pdac share optics -> 0.5 each
so the optics-distinct Owen sets are not outvoted). Reports the per-dataset generalization
tax. Writes results/winner.json.
"""
import json
import sys

import numpy as np
import pandas as pd

import datasets as D

RESULTS = D.MT_DIR / "results"
WEIGHTS = {"vaishnavi": 0.5, "pdac": 0.5, "owen_40x": 1.0, "owen_20x": 1.0}


def load_all():
    frames = []
    for name in D.REGISTRY:
        p = RESULTS / f"{name}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        raise SystemExit("no results yet")
    return pd.concat(frames, ignore_index=True)


def main():
    df = load_all()
    piv = df.pivot_table(index="config_id", columns="dataset", values="dataset_score")
    piv = piv.dropna()                      # configs scored on every dataset
    if piv.empty:
        raise SystemExit("no config scored on all datasets yet")
    optimum = piv.max(axis=0)
    ratio = piv / optimum
    worst_ratio = ratio.min(axis=1)
    w = np.array([WEIGHTS.get(c, 1.0) for c in piv.columns])
    wmean = (piv.values * w).sum(axis=1) / w.sum()
    rank = pd.DataFrame({"worst_ratio": worst_ratio, "wmean": wmean}, index=piv.index)
    rank = rank.sort_values(["worst_ratio", "wmean"], ascending=False)

    win_id = rank.index[0]
    win_row = df[df.config_id == win_id].iloc[0]
    cfg = {k[4:]: win_row[k] for k in df.columns if k.startswith("cfg_") and pd.notna(win_row[k])}

    per_ds = []
    for ds in piv.columns:
        per_ds.append(dict(dataset=ds, score=round(float(piv.loc[win_id, ds]), 4),
                           optimum=round(float(optimum[ds]), 4),
                           tax=round(float(optimum[ds] - piv.loc[win_id, ds]), 4)))

    out = dict(winner_config_id=win_id, winner_config=cfg,
               per_dataset=per_ds,
               worst_ratio=round(float(worst_ratio[win_id]), 4),
               n_configs=int(len(piv)), datasets=list(piv.columns))
    (RESULTS / "winner.json").write_text(json.dumps(out, indent=2, default=str))

    print(json.dumps(out, indent=2, default=str))
    print("\nTop 6 configs by worst-case ratio:")
    show = rank.head(6).join(piv).round(4)
    print(show.to_string())
    return out


if __name__ == "__main__":
    main()
