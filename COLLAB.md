# Brieflow Speed Benchmarking

## What This Is

Speed optimization branch of the brieflow OPS pipeline. Two parallel `speed` branches:
- This repo (`brieflow-analysis` fork) — analysis scripts, configs, harness
- `brieflow/` submodule — pipeline code (Polars I/O, vectorization, dep bumps)

**Goal:** Find the fastest Snakemake + SLURM configuration for the brieflow pipeline.
A production screen generates ~26,000 Snakemake jobs. Right now we over-provision memory
and haven't optimized job concurrency. We want to cut wall time without changing outputs.

---

## What Got Done

### Pipeline code changes (brieflow submodule)
- **Polars I/O** — replaced pandas in 19 scripts; falls back gracefully on schema errors
- **Vectorization** — `format_merge`, `hash.py` (KDTree), `call_reads`, uniprot explode
- **Aggregate** — PCA fit-once, cached matrix powers in TVN
- **Memory** — memmap stitching for >1GB canvases
- **`flow.sh`** — unified runner replacing 13 old shell scripts
- **Dep bumps** — snakemake 9.19, polars 1.39.3, snakemake-executor-plugin-slurm 2.6.0

### Phase 1: Tile calibration + grid search (complete)
- Measured actual MaxRSS and elapsed time per rule on tile tier → `harness/results/calibration_tile.json`
- Ran 13 predefined configs (local, slurm-noarray, slurm-array variants)
- **Finding**: slurm-array backend wins; local is fastest at tile scale but doesn't scale

### Phase 2: Autoresearch — agent-driven tile search (complete, 30 trials)
- Autonomous agent loop: write `next_trial.json` → run tile tier → observe → repeat
- Searched: `array_limit`, `latency_wait`, `use_mem_recommendations`
- **Best config**: `slurm_arr_j400_al20_lat5_mem` — **~3.4 min** (vs 4.1 min local baseline)
- **Key levers**: `array_limit=20` and `use_mem_recommendations=True`
- Full results: `analysis/autoresearch/results.tsv`

### Phase 3: Memory calibration (complete)
- Measured well-scale DAG overhead: **183 MB** per compute-node mini-snakemake process
- Tile-calibrated values must be corrected for well scale: `round((obs_rss_mb + 183) * 1.5)`

| Rule | Observed RSS | Old Request | Recommended |
|------|-------------|-------------|-------------|
| convert_sbs | 268 MB | 2,130 MB | 676 MB |
| convert_phenotype | 686 MB | 3,069 MB | 1,305 MB |
| calculate_ic_sbs | 945 MB | 59,033 MB | 1,411 MB |
| extract_metadata_* | ~180 MB | ~2,000 MB | ~550 MB |

Full recommendations: `analysis/harness/results/mem_recommendations.json`

### Phase 4: Well-tier validation (incomplete)
- Designed 3 configs (A=baseline, B=tile mem, C=full best) — JSONs ready in `autoresearch/`
- Well runs are **~30-40 min** each (much shorter than expected at 4,328 jobs)
- All attempts failed due to tmux socket in `/tmp` being wiped by cluster cleanup
- **No valid well results recorded yet**

---

## What's Next

1. **Re-run well trials A/B/C** — clean single snakemake process, stable tmux socket
2. **Add sacct pending-time decomposition** — after each trial, decompose wall time into
   per-rule pending time (`Start - Eligible`) vs compute time. This becomes the signal
   for the well autoresearch and the admin conversation.
3. **Well autoresearch** — if runs are ~30-40 min, do 10-15 trials overnight using the
   same agent loop as tile. See `analysis/autoresearch/program.md`.

---

## Setup

```
/lab/ops_analysis_ssd/test_matteo/brieflow-speed/
├── analysis/
│   ├── flow.sh                     ← unified pipeline runner
│   ├── harness/harness.py          ← benchmark harness
│   ├── config/config_tile.yml      ← tile tier (~150 jobs)
│   ├── config/config_well.yml      ← well tier (~4,300 jobs)
│   ├── autoresearch/               ← trial configs, results, agent program
│   └── slurm/config.yaml           ← SLURM resources per rule
└── brieflow/                       ← pipeline code (speed branch)
```

**Run from cheeserind** — has enough RAM to manage the well-scale DAG directly from the login node.

```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_speed
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis
```

**Kill snakemake safely**: always `kill -9 <PID>`, never pkill. Unlock before restarting:
```bash
snakemake --unlock --snakefile ../brieflow/workflow/Snakefile --configfile config/config_well.yml
```

---

## snakemake-executor-plugin-slurm 2.6.0 Notes

### Array limit deadlock (critical)
2.6.0 groups jobs by rule and waits until `len(same_rule_jobs) >= chunk_size` before submitting.
With 6+ rules sharing 100-job batches (~15 jobs/rule), any `array_limit > 15` causes infinite wait.
**Fix:** keep `--slurm-array-limit=10` (or 20 with the right job count).

### Flags to avoid
- `--slurm-pass-command-as-script` — breaks array jobs in 2.6.0
- `slurm_extra --output` — forbidden; use `--slurm-logdir` instead
- `--use-conda` — breaks libarchive on compute nodes

See `analysis/slurm/further_2.6.0.md` for full plugin docs.

---

## Questions for the Admin

The bigger goal here is to build a brieflow config that auto-tunes for any cluster —
capturing all the relevant scheduling levers so anyone running brieflow gets optimal
performance without manual tuning. To do that, we need to understand the cluster's
actual limits and measure how much time is lost to each bottleneck.

1. **Job submission rate limits** — fast rules (`extract_metadata`, `convert_sbs`) spend
   the majority of their time pending rather than running. We observe repeated "Job rate
   limit reached" messages during submission. We want to:
   - Know the exact per-user submission rate cap and `MaxSubmitJobs` limit
   - Track pending time per job via `sacct` (`Start - Eligible`) to quantify how much
     wall time is lost to rate limiting vs actual compute
   - Use this to calibrate `--slurm-array-limit` and `--jobs` optimally for this cluster
   Can you share the current limits, and is there headroom to raise them for benchmarking?

2. **Array job submission overhead** — our data shows 2× speedup from `sbatch --array`
   vs individual submissions at tile scale (~150 jobs). We want to understand:
   - At what job count does array submission stop helping (scheduler crossover point)?
   - What is the per-array-job vs per-individual-job scheduling latency on this cluster?
   This helps us set `--slurm-array-limit` correctly across tile/well/full scales.

3. **tmux socket stability** — tmux sockets in `/tmp` are being wiped by cluster cleanup,
   killing overnight runs mid-job. What is the recommended approach for persistent
   login-node sessions? Can sockets in `/home` be used reliably?
