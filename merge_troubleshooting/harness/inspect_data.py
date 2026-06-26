"""Quick schema + density inspection of all pulled datasets (read-only, light)."""
import sys
import pandas as pd
import numpy as np
import datasets as D


def show(name):
    print(f"\n===== {name} : {D.REGISTRY[name]['optics']} =====")
    ds = D.load(name)
    for key in ("phenotype_info", "sbs_info"):
        df = ds[key]
        per_tile = df.groupby("tile").size()
        print(f"  {key}: {len(df):,} cells, {df.tile.nunique()} tiles, "
              f"~{int(per_tile.median())} cells/tile | cols={list(df.columns)}")
        if "area" in df.columns:
            print(f"      area px^2 median={df['area'].median():.0f}")
    for key in ("ph_meta", "sbs_meta"):
        m = ds.get(key)
        if m is None:
            print(f"  {key}: ABSENT")
            continue
        cols = list(m.columns)
        px = D.pixel_size(m)
        print(f"  {key}: {m.tile.nunique() if 'tile' in m.columns else '?'} tiles | "
              f"pixel_size={px} | cols={cols}")
    pdet = D.predicted_det(ds)
    print(f"  predicted det (pixel-size cross-check): {pdet}")
    # owen_20x existing alignment
    fa = D.raw_path(name, "fast_alignment")
    if fa.exists():
        a = pd.read_parquet(fa)
        print(f"  fast_alignment: {len(a)} rows, cols={list(a.columns)}")
        if "determinant" in a.columns and "score" in a.columns:
            good = a[a.score > 0.1]
            print(f"      score>0.1: {len(good)} rows, det median={good.determinant.median():.5f} "
                  f"(p10-p90 {good.determinant.quantile(.1):.5f}-{good.determinant.quantile(.9):.5f})")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(D.REGISTRY)):
        try:
            show(n)
        except Exception as e:
            print(f"  ERROR on {n}: {type(e).__name__}: {e}")
