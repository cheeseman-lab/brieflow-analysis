# Brieflow Speed Autoresearch

## Goal
Find the fastest Snakemake configuration for the brieflow OPS pipeline.
Two targets: (1) local execution (all cores), (2) Slurm execution.
Metric: total wall time in minutes on the tile tier (~150 jobs). Lower is better.

## Context
- Working directory: `/lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis/`
- Environment: `eval "$(conda shell.bash hook)" && conda activate brieflow_speed`
- Pipeline runs preprocess + sbs + phenotype modules on the tile tier (~150 jobs, ~4-12 min)
- Results are recorded to `autoresearch/results.tsv`
- Existing baseline results are in `harness/results/trials.jsonl` — read these first

## Status
**Tile autoresearch: COMPLETE (30 trials).** Best tile config: `slurm_arr_j400_al20_lat5_mem`
at ~3.4 min. Results in `autoresearch/results.tsv`.

**Well autoresearch: NOT YET RUN.** Well runs are ~30-40 min each. Use this program
to run the well-tier autoresearch loop — adapt the schema below to include `use_tile_mem`
and `use_well_mem` fields (see `harness.py cmd_run_well_trial`).

## What We Know (from 30 tile trials)
- Local (all cores): **4.1 min** — fastest at tile scale, not usable at well/full scale
- Best Slurm: **~3.4 min** — `array_limit=20`, `latency_wait=5`, `use_mem_recommendations=True`
- Arrays essential: non-array SLURM is 2× slower (10.9–11.8 min)
- `cpus_per_task=2` does NOT help (I/O bound jobs)
- `jobs=400` optimal; 200 too few, 600 no benefit at tile scale

## The Experiment Loop

LOOP FOREVER — do NOT stop, do NOT ask for confirmation:

1. Read `autoresearch/results.tsv` and `harness/results/trials.jsonl` to understand current state
2. Choose the next most informative trial (see Search Strategy below)
3. Edit `autoresearch/next_trial.json` with the new trial parameters
4. Run: `cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis && python harness/harness.py run_one_trial`
5. Read the wall time from the output
6. Go to step 1

**NEVER STOP. NEVER ASK FOR CONFIRMATION. Run until manually interrupted.**

## next_trial.json Schema

```json
{
  "tag": "short_descriptive_tag",
  "notes": "why you chose this trial",
  "backend": "slurm",
  "use_arrays": true,
  "jobs": 400,
  "array_limit": 10,
  "cpus_per_task": 1,
  "latency_wait": 5,
  "max_status_checks": 2,
  "use_mem_recommendations": false
}
```

For local backend:
```json
{
  "tag": "local_mem_recs",
  "notes": "Local run with tight mem limits — does queue time change?",
  "backend": "local",
  "cores": "all",
  "use_mem_recommendations": true
}
```

**Note:** `latency_wait`, `max_status_checks`, `use_arrays`, `jobs`, `array_limit`, `cpus_per_task`
are ignored for local backend — do NOT include them for local trials.

## Search Strategy

### Priority 1 — Latency-wait (biggest untested lever for Slurm)
The SBS pipeline has ~10 sequential steps per tile. Each Slurm job completion triggers
a `latency_wait`-second pause before Snakemake checks outputs and submits the next job.
Current default: 10s → ~100s sequential overhead on critical path.
Hypothesis: reducing to 3-5s saves 50-70s (~1 min) on tile runs.

Values to try: 3, 5, 10 (baseline), 15
Combine with the best known Slurm config (arrays=true, j400, al10).

### Priority 2 — Mem recommendations
`harness/results/mem_recommendations.json` contains tight memory values (e.g. calculate_ic_sbs:
59,000 MB → 1,411 MB). Applying these may reduce queue wait time on a busy cluster.
Try: best latency_wait config × use_mem_recommendations=true vs false.

### Priority 3 — max_status_checks_per_second
Controls how often Snakemake polls Slurm for job status. Default is 10/s.
At tile scale (~150 jobs) this probably doesn't matter much, but worth a few trials.
Values to try: 1, 2, 5, 10 (default = omit field)

### Priority 4 — Array limit interactions
Best known: al=10. Try combinations with reduced latency_wait.
Values: 5, 10, 20 (already have some baseline data).

### Priority 5 — Local backend
Local already wins at 4.1 min. Test: does use_mem_recommendations change anything?
(Probably not — local doesn't go through Slurm queue — but verify.)

## What NOT to Try
- `cpus_per_task > 1`: already tested, no benefit (I/O-bound jobs)
- `jobs < 150 or > 400`: irrelevant at tile scale (only 150 jobs exist)
- `use_arrays=false`: already tested, 2x slower — not worth combining with other params
- `--scheduler=ilp`: not exposed in flow.sh, adds overhead at small scale

## Tag Naming Convention
`<backend>_<key_params>` — keep short and descriptive:
- `slurm_arr_j400_al10_lat5_nomem`
- `slurm_arr_j400_al10_lat3_mem`
- `slurm_arr_j400_al5_lat5_msc2`
- `local_mem`
- `local_nomem` (already done as `local_all_cores` — skip)

## Looking for Patterns
After ~15 trials, pause and analyze:
- Does latency_wait consistently predict wall time?
- Does mem_recommendations help or not?
- What is the gap between local and best Slurm? Is it closing?
- Are there interactions (e.g. low latency_wait + mem_recs = bigger speedup than either alone)?

The goal is not just to find the best tile config — it's to understand WHICH PARAMETERS DRIVE
SPEED so we can apply that understanding to well/full scale runs.

## Environment Notes
- Must run from `analysis/` directory (harness uses relative paths)
- Must run from cheeserind login node (has enough RAM for well-scale DAG)
- Check active processes before starting: `ps aux | grep snakemake | grep mdiberna | grep -v grep`
- If snakemake is running: `kill -9 <PID>` then unlock before starting
- Unlock command: `snakemake --unlock --snakefile ../brieflow/workflow/Snakefile --configfile config/config_tile.yml`
