# Speed Branch Notes

## What This Branch Is
Speed optimization of brieflow pipeline across two `speed` branches (brieflow submodule + brieflow-analysis). Goal: faster I/O, vectorized operations, better slurm utilization — without changing scientific outputs.

## What Got Done (Pre-April 3)
- **`flow.sh`** — unified runner replacing 13 old shell scripts. Supports `--backend local|slurm`, `--dry-run`, `--sequential-plates`, `--profile`, `--config` override
- **`profile.sh`** / **`status.sh`** — monitoring tools
- **Polars I/O** — `workflow/lib/shared/io.py` swapped into all 19 script/lib files. Falls back to pandas on schema errors
- **Snakefile** — module `enabled:` flags, preprocess made conditional
- **Vectorization** — format_merge distance/min, hash.py KDTree + cached sqrt, uniprot explode, call_reads map
- **Aggregate** — PCA fit-once, cached matrix powers in TVN
- **Memory** — memmap stitching for >1GB canvases
- **Dep bumps** — snakemake 9.19, polars 1.39.3, many others (cellpose kept at 3.1.0)
- **Slurm config** — jobs: 600, segmentation cpus: 1
- **Baker config** — set up in `analysis/config/` with fixed archive paths and added missing config keys
- **Small test data** — full pipeline passes (2173/2173 steps, zero errors)

---

## snakemake-executor-plugin-slurm 2.6.0 Learnings

We upgraded from 1.4.0 → 2.6.0 for array jobs, efficiency reports, and better logging. Getting it working took significant debugging. Key findings:

### The Array Limit Deadlock (Critical)

**Problem:** 2.6.0 introduced `run_jobs()` which groups jobs by rule and waits until `len(same_rule_jobs) >= chunk_size` before submitting. Default `chunk_size` = `--slurm-array-limit` = 1000. Snakemake sends jobs in batches of ~100. When those 100 jobs are split across multiple rules (e.g. 17 convert_sbs + 27 convert_phenotype), no single rule hits the threshold → infinite wait → empty squeue.

**Fix:** Set `--slurm-array-limit` low enough that per-rule job count in a batch exceeds it. With 6 ready rules sharing 100-job batches (~15-20 jobs/rule), `--slurm-array-limit=10` works. **Do not use the default 1000 or even 100.**

```bash
--slurm-array-jobs=all --slurm-array-limit=10
```

### `--slurm-pass-command-as-script` Incompatible with Array Jobs

In 2.6.0, array jobs use zlib-compressed base64 payloads to pass commands — it has its own mechanism. Adding `--slurm-pass-command-as-script` causes malformed shell scripts on compute nodes:
```
slurm_script: 3: --slurm-jobstep-array-execs: not found
```
**Fix:** Remove `--slurm-pass-command-as-script` entirely. The plugin handles argument-length limits automatically (retries via stdin).

### `slurm_extra` with `--output` is Forbidden in 2.6.0

The plugin now manages all output/error file paths itself via `--slurm-logdir`. Setting `--output` in `slurm_extra` causes:
```
The --output-file option is not allowed in the 'slurm_extra' parameter
```
**Fix:** Remove `slurm_extra` from `slurm/config.yaml`. Use `--slurm-logdir` instead:
```bash
--slurm-logdir=slurm/slurm_output/rule
```

### `--use-conda` Breaks on Compute Nodes

Triggers broken libarchive on compute nodes:
```
Error while loading conda entry point: conda-libmamba-solver (libarchive.so.13)
```
**Fix:** Remove `--use-conda` entirely. The brieflow conda env is already activated before snakemake is called.

### Groups Cannot Be Array Jobs

Rules submitted with `--groups` are automatically excluded from array submission (logged as warning, reverted to individual). This affects `sbs` and `phenotype` modules in `flow.sh` which use tile groups. They still work — just not as arrays.

### New Features We're Using

| Flag | Purpose |
|------|---------|
| `--slurm-logdir=slurm/slurm_output/rule` | Per-rule log dirs (replaces `slurm_extra --output`) |
| `--slurm-array-jobs=all` | Enable array submission for all rules |
| `--slurm-array-limit=10` | Max tasks per array (keep low — see deadlock above) |
| `--slurm-keep-successful-logs` | Retain logs even for successful jobs (profile mode only) |
| `--slurm-efficiency-report` | CPU/mem efficiency CSV at end (profile mode only) |
| `--slurm-efficiency-report-path` | Where to write the efficiency report |

### Working `flow.sh` Slurm Command

```bash
snakemake --executor slurm \
  --workflow-profile slurm/ \
  --slurm-array-jobs=all \
  --slurm-array-limit=10 \
  --slurm-jobname-prefix=brieflow \
  --slurm-logdir=slurm/slurm_output/rule \
  --latency-wait 10 \
  --keep-going \
  --snakefile ../brieflow/workflow/Snakefile \
  --configfile config/config.yml \
  --rerun-triggers mtime \
  --until all_preprocess
```

---

## Current State (April 3, 2026)

Preprocess is running on cheesegrater — array jobs submitting correctly, ~16%+ done as of last check.

### What's Next
- [ ] Monitor baker preprocess completion
- [ ] Run remaining modules: `bash flow.sh sbs phenotype merge aggregate cluster --backend slurm`
- [ ] After speed run: checkout brieflow submodule to `main`, run same pipeline to `brieflow_output_baseline/`
- [ ] Compare timing + outputs between baseline and speed runs
- [ ] Parse results with `profile.sh` and `sacct`

---

## Key Config

- **Must run on cheesegrater** — slurm jobs hang when launched from cheeserind
- **Conda env:** `brieflow_speed` → `eval "$(conda shell.bash hook)" && conda activate brieflow_speed`
- **Baker raw data:** `/archive/cheeseman/ops_data/baker/`
- **Baker:** `sbs_data_organization: well`, `phenotype_data_organization: well`, 1 plate, 6 wells, ~26K preprocess jobs
- **Run preprocess:** `bash flow.sh preprocess --backend slurm`
- **Monitor:** `bash status.sh` or `tail -f logs/preprocess-*.log`

## Key Files
- `analysis/flow.sh` — unified pipeline runner
- `analysis/slurm/config.yaml` — slurm resources (jobs: 600)
- `analysis/config/config.yml` — baker config
- `brieflow/pyproject.toml` — dep versions (slurm plugin pinned to 2.6.0)
- `brieflow/workflow/lib/shared/io.py` — polars I/O helper
