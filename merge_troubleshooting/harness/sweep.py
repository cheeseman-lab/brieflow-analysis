"""Run the config grid over one or more datasets; append rows to results/{name}.parquet.

Loads each dataset's eval context ONCE (the big cached hash) and reuses it across all
configs (each config is per-pair cheap). Resumable: skips config_ids already recorded.
"""
import sys
import time

import pandas as pd

import datasets as D
import grid
import run_config as RC

RESULTS = D.MT_DIR / "results"


def sweep(name):
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{name}.parquet"
    done = set()
    rows = []
    if out.exists():
        prev = pd.read_parquet(out)
        rows = prev.to_dict("records")
        done = set(prev.config_id)
    cfgs = [c for c in grid.expand() if RC.config_id(c) not in done]
    print(f"[{name}] {len(cfgs)} new configs ({len(done)} already done)", flush=True)
    if not cfgs:
        return
    t = time.time()
    ctx = RC.load_context(name)
    print(f"[{name}] context loaded ({len(ctx['pairs'])} eval pairs) in {time.time()-t:.0f}s", flush=True)
    for i, cfg in enumerate(cfgs):
        try:
            rows.append(RC.run(name, cfg, ctx))
        except Exception as e:
            print(f"  cfg {RC.config_id(cfg)} FAILED: {type(e).__name__}: {e}", flush=True)
        if (i + 1) % 10 == 0:
            pd.DataFrame(rows).to_parquet(out)
            print(f"  {i+1}/{len(cfgs)} configs", flush=True)
    pd.DataFrame(rows).to_parquet(out)
    print(f"[{name}] done -> {out} ({len(rows)} rows total)", flush=True)


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(D.REGISTRY)):
        sweep(n)
