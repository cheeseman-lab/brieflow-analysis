# brieflow-speed — Claude Instructions

## What This Repo Is
Speed optimization branch of brieflow OPS pipeline. Two `speed` branches:
- This repo (`brieflow-analysis` fork): `analysis/` scripts, configs, harness
- `brieflow/` submodule: pipeline code (polars I/O, vectorization, dep bumps)

Working directory for all commands: `analysis/`

## Environment
```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_speed
```
Always use this before running snakemake or flow.sh. Never use bare `conda activate`.

## CRITICAL: Process Management
**Always use `kill -9 <PID>` to stop snakemake — never pkill.**
Before any run, verify only one snakemake process is alive:
```bash
ps aux | grep snakemake | grep mdiberna | grep -v grep
```
Before restarting after a kill, always unlock:
```bash
snakemake --unlock --snakefile ../brieflow/workflow/Snakefile --configfile config/config.yml
```

## Must Run On
**cheesegrater only** — slurm jobs hang when launched from cheeserind.

## Dataset Tiers
| Tier | Config | Jobs | Use |
|------|--------|------|-----|
| tile | `config/config_tile.yml` | ~150 | Fast iteration, harness calibration + search |
| well | `config/config_well.yml` | ~5000 | Well-scaling rule calibration |
| full | `config/config.yml` | ~26K | Production benchmark |

Tile and well output to isolated dirs (`brieflow_output_tile/`, `brieflow_output_well/`).

## Running the Pipeline
```bash
# Standard run
bash flow.sh preprocess --backend slurm --profile --configfile config/config_tile.yml

# Full modules
bash flow.sh preprocess sbs phenotype --backend slurm --profile --configfile config/config_tile.yml

# Monitor
squeue -u $USER | head -20
tail -f logs/preprocess-*.log
```

## The Speed Harness
Located at `harness/harness.py`. Runs entirely on the tile tier.
Calibrates memory per rule from actual MaxRSS, then grid searches concurrency params.

### Full autonomous workflow:
```bash
cd analysis/

# Step 1: Measure per-tile rule memory + timing (~15-30 min)
python harness/harness.py calibrate

# Step 2: Measure well-scaling rules: calculate_ic, combine_* (~1-2 hr)
python harness/harness.py calibrate_well

# Step 3: Compute DAG memory overhead from anchor rules
python harness/harness.py dag_overhead

# Step 4: Print memory breakdown + generate recommendations
python harness/harness.py mem_report

# Step 5: Grid search overnight (27 trials: 3 cpus × 3 jobs × 3 array_limit)
python harness/harness.py search

# Step 6: See ranked results
python harness/harness.py report
```

Results saved to `harness/results/`:
- `calibration_tile.json` — per-rule MaxRSS/elapsed on tile tier
- `calibration_well.json` — per-rule MaxRSS/elapsed on well tier
- `dag_overhead.json` — estimated DAG memory overhead per 1000 jobs
- `mem_recommendations.json` — final mem_mb per rule with breakdown
- `trials.jsonl` — one line per search trial with wall time + params

### Search space (defined in harness.py)
```python
SEARCH_SPACE = {
    "cpus_per_task": [1, 2, 4],
    "jobs": [200, 400, 600],
    "slurm_array_limit": [5, 10, 20],
}
```

### Key findings so far (from Apr 4 efficiency report)
| Rule | MaxRSS | Requested | Waste |
|------|--------|-----------|-------|
| convert_sbs | 265 MB | 2130 MB | 88% |
| convert_phenotype | 687 MB | 3069 MB | 78% |
| calculate_ic_sbs | 945 MB | 59033 MB | 98% |
| extract_metadata_* | ~180 MB | ~2000 MB | 91% |

## Known Issues
- **nd2 read contention**: Two tiles sharing the same well-level nd2 file on the same node can fail silently. Transient — resume fixes it. Root cause: well-organized data means all tiles in A1 share the same 4x84GB nd2 files.
- **DAG memory overhead**: Snakemake's internal DAG uses RAM proportional to workflow size. Full baker (~26K jobs) adds significant overhead vs tile run (~150 jobs). The `dag_overhead` command quantifies this.
- **disk_mb auto-calculation**: Snakemake sets `disk_mb` = 2× input file size. For well-level nd2s (84 GB each × 4 channels = 685 GB requested). Not enforced on our cluster but worth overriding.
- **slurm-array-limit deadlock**: Must be ≤ per-rule job count per batch. With 6+ rules active, batches of 100 split ~15 jobs/rule. Keep `--slurm-array-limit=10`.

## snakemake-executor-plugin-slurm 2.6.0 Notes
See `slurm/further_2.6.0.md` for full docs.
- `--slurm-array-jobs=all` — enable array submission
- `--slurm-array-limit=10` — keep low (see deadlock above)
- `--slurm-logdir=slurm/slurm_output/rule` — per-rule log dirs
- `--slurm-pass-command-as-script` — **do not use**, breaks array jobs
- `slurm_extra --output` — **forbidden**, use `--slurm-logdir` instead
- `--use-conda` — **do not use**, breaks libarchive on compute nodes

## Checking Efficiency After a Run
```bash
# Efficiency report (if --profile was used)
ls logs/efficiency_*/

# sacct summary
sacct -u $USER --starttime=2026-04-04T15:00 \
  --format=JobID%25,Elapsed,MaxRSS,ReqMem,NCPUS,TotalCPU,State --parsable2
```

## flow.sh Flags
```
--backend local|slurm   Execution backend
--profile               Enable: keep successful logs + efficiency report
--configfile PATH       Override config file (default: config/config.yml)
--slurm-profile PATH    Override slurm profile dir (default: slurm/)
--slurm-array-limit N   Override array chunk size (default: 10)
--dry-run               Don't execute, just show what would run
--config key=val        Pass snakemake key=value config overrides
```
