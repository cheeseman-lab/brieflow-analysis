# cluster_optimization/

This directory holds **per-screen sizing data + minimal tier launchers** for
this analysis dir. As of the post-baker trim (2026-05-14), the bulk of the
runtime + recovery + monitoring logic moved into the brieflow-ops plugin at
`/lab/barcheese01/mdiberna/brieflow-ops/`. What remains here is screen-
specific data and a thin wrapper for ad-hoc dev cycles.

## Contents

- **`harness.py`** (~350 lines) — minimal launcher with three commands:
  - `python harness.py run_tile [--tag X] [--notes "..."]` — tile-tier dev
    cycle via the plugin runloop (uses `config/config_tile.yml`)
  - `python harness.py run_well [--tag X] [--notes "..."]` — well-tier
    validation cycle (uses `config/config_well.yml`)
  - `python harness.py aggregate_efficiency` — refresh
    `mem_recommendations.json` from observed RSS in `logs/efficiency_*/`
- **`results/mem_recommendations.json`** — canonical per-rule memory caps,
  read by the plugin's runloop at every launch. Gets refreshed by
  `aggregate_efficiency` after successful runs (manual_override entries
  preserved).
- **`results/baker_observations_raw_2026-05-14.csv`** — 66,207 per-job
  RSS observations across the full baker session (April 28 → May 14, 52
  efficiency reports). Bootstrap dataset for fitting per-rule scaling
  formulas (HARDENING_TODO #23).
- **`results/baker_scaling_summary_2026-05-14.csv`** — per-rule summary
  (peak / p99 / p95 / median / suggested_cap) for the 40 rules observed.

## What's NOT here (and where it went)

The pre-2026-05-14 harness had ~1,300 lines covering tile-tier speed
search, autoresearch trial management, calibration, sacct decomposition,
and per-rule mem-cap injection. All of that was speed-branch tuning
infrastructure for the baker arc. It was retired in the post-success trim:

- **Runtime + recovery** (mem-rec injection, OOM auto-bump, push
  notifications, phase orchestration, config validation) → plugin
  (`brieflow-ops/scripts/brieflow_runloop.py`, `brieflow_recover.py`,
  `brieflow_run.py`).
- **Tile-tier speed search** (`SEARCH_TRIALS`, `calibrate`, `search`,
  `report`) → archived in commit history; no longer relevant once
  baker's optimal config was identified.
- **Autoresearch trial machinery** (`run_one_trial`, `next_trial.json`,
  `well_results.tsv`, `autoresearch_winner_*` dirs) → same.
- **Array-bug diagnostics** (`cross_ref_failure.py`, `array_wrap_trace_*`)
  → resolved upstream by `use_arrays=false` policy; deleted.

## Where production runs go

For real screen runs (production, not dev), use the plugin directly:

```
python /lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_runloop.py \
  --analysis-dir /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis \
  --phases preprocess,sbs,phenotype \
  --config config/config.yml \
  --backend slurm --jobs 400 --latency-wait 60 \
  --max-attempts 99 \
  --tag baker_<descriptive>
```

Or invoke via `/brieflow-run` if the plugin is installed as a Claude Code
plugin in your environment.

## Future migration

HARDENING_TODO #25 (in the plugin repo) tracks moving `aggregate_efficiency`
itself into the plugin. After that lands, this directory can shrink further
to just `results/` (pure data) — the harness disappears entirely and per-
screen analysis dirs become "config + data only", with all logic owned by
the plugin.
