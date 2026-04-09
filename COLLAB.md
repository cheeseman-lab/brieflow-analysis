# Brieflow Speed Benchmarking — HPC Collaboration

## What We're Doing and Why

**brieflow** is an image analysis pipeline for optical pooled screens (OPS). A single screen
produces ~26,000 snakemake jobs: image conversion, segmentation, barcode calling, feature
extraction, etc. The pipeline runs on your HPC cluster using SLURM via
`snakemake-executor-plugin-slurm` (version 2.6.0).

We want to find the fastest snakemake + SLURM configuration for this pipeline. Right now we
over-provision memory, over-serialize on job concurrency, and haven't measured whether SLURM
array jobs actually help vs. individual job submission. The goal is to cut wall time on
production screens.

---

## The Test Dataset (Tile Tier)

To iterate quickly, we built a small representative subset:

| Tier | Data | Jobs | Wall time |
|------|------|------|-----------|
| **tile** | 10 tiles, 1 well (A1), 1 plate | ~150 jobs | ~5-20 min |
| **well** | All 333 tiles, 1 well (A1), 1 plate | ~5000 jobs | ~1-2 hr |
| **full** | All 6 wells, 1 plate | ~26K jobs | Hours |

All benchmarking runs against the **tile tier** for speed. Results from the well tier are used
separately to measure scaling behavior.

---

## What the Harness Measures

`analysis/harness/harness.py` runs 13 trials against the tile dataset, each varying one
or more axes of the snakemake/SLURM configuration:

| Axis | Values tested |
|------|---------------|
| **Backend** | local (all cores) vs. SLURM |
| **SLURM array jobs** | enabled vs. disabled |
| **`--jobs` (max concurrent SLURM jobs)** | 200, 400, 600 |
| **`--slurm-array-limit` (max tasks per array)** | 5, 10, 20 |
| **`cpus_per_task`** | 1, 2 |

Each trial runs the full preprocess → SBS → phenotype pipeline on 10 tiles, records
total wall time, and saves per-rule CPU/memory efficiency from SLURM's `sacct`.

**The key question:** for a ~150-job tile dataset (and by extension the ~26K-job
production screen), what combination minimizes total wall time?

---

## Full Trial List

```
local_all_cores          — local backend, all cores, no SLURM
slurm_noarr_j200_c1      — SLURM, no arrays, jobs=200, cpus=1
slurm_noarr_j400_c1      — SLURM, no arrays, jobs=400, cpus=1
slurm_noarr_j600_c1      — SLURM, no arrays, jobs=600, cpus=1
slurm_arr_j200_al5_c1    — SLURM, arrays, jobs=200, array_limit=5,  cpus=1
slurm_arr_j200_al10_c1   — SLURM, arrays, jobs=200, array_limit=10, cpus=1
slurm_arr_j400_al5_c1    — SLURM, arrays, jobs=400, array_limit=5,  cpus=1
slurm_arr_j400_al10_c1   — SLURM, arrays, jobs=400, array_limit=10, cpus=1
slurm_arr_j400_al20_c1   — SLURM, arrays, jobs=400, array_limit=20, cpus=1
slurm_arr_j600_al10_c1   — SLURM, arrays, jobs=600, array_limit=10, cpus=1
slurm_arr_j600_al20_c1   — SLURM, arrays, jobs=600, array_limit=20, cpus=1
slurm_arr_j400_al10_c2   — SLURM, arrays, jobs=400, array_limit=10, cpus=2
slurm_arr_j600_al10_c2   — SLURM, arrays, jobs=600, array_limit=10, cpus=2
```

---

## Setup

### Location
```
/lab/ops_analysis_ssd/test_matteo/brieflow-speed/
├── analysis/               ← working directory for all commands
│   ├── flow.sh             ← unified pipeline runner
│   ├── harness/harness.py  ← benchmark harness
│   ├── config/             ← configs for tile/well/full tiers
│   └── slurm/config.yaml   ← SLURM profile (resources per rule)
├── brieflow/               ← pipeline code (snakemake workflow)
└── CLAUDE.md               ← full session instructions
```

### Environment
**Must run from `cheesegrater`** — SLURM jobs hang when launched from `cheeserind`.

```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_speed
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis
```

### Run the harness
```bash
# Phase 1: full speed search (tile tier, ~8-12 hr overnight)
python harness/harness.py calibrate    # ~15-30 min: measure MaxRSS/timing per rule
python harness/harness.py search       # ~8-12 hr: 13 trials
python harness/harness.py report       # ranked results

# Phase 2: memory + scaling (after Phase 1)
python harness/harness.py calibrate_well   # ~1-2 hr: measure well-scaling rules
python harness/harness.py dag_overhead     # estimate DAG memory overhead
python harness/harness.py mem_report       # recommended mem_mb per rule
python harness/harness.py scale_test       # run well tier with best Phase 1 config
```

### Check results
```bash
# See ranked trial results
python harness/harness.py report

# Raw trial data
cat harness/results/trials.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    t = json.loads(line)
    print(f\"{t['tag']:<40} {t['wall_time_min']:>6.1f} min\")
"

# SLURM efficiency (CPU%, MaxRSS per rule)
ls logs/efficiency_*/
```

---

## Known Issues and Context

### Array limit deadlock (Critical)
`snakemake-executor-plugin-slurm` 2.6.0 introduced `run_jobs()` which groups jobs by
rule and waits until `len(same_rule_jobs) >= chunk_size` before submitting. Default
`chunk_size` = `--slurm-array-limit`. Snakemake sends jobs in batches of ~100; when
those split across 6+ rules, no single rule hits a high threshold → infinite wait →
empty squeue.

**Fix:** Keep `--slurm-array-limit` low (≤10 for this dataset). This is why we test
5, 10, 20 — to find the threshold where performance degrades.

### nd2 read contention
Baker data is well-organized: all 10 tiles in well A1 share 4 × 84GB nd2 files. If two
tiles land on the same node and both try to read the same nd2 file, one can fail silently.
Transient — pipeline resume recovers it. Root cause: NFS read contention on large files.

### SLURM memory over-provisioning
From our April 4 efficiency report on the tile run:

| Rule | MaxRSS | Requested | Waste |
|------|--------|-----------|-------|
| convert_sbs | 265 MB | 2130 MB | 88% |
| convert_phenotype | 687 MB | 3069 MB | 78% |
| calculate_ic_sbs | 945 MB | 59033 MB | 98% |
| extract_metadata_* | ~180 MB | ~2000 MB | 91% |

Memory is over-provisioned conservatively from initial estimates. The harness Phase 2
generates calibrated recommendations from actual MaxRSS.

### DAG memory overhead
Snakemake builds the full workflow DAG inside each SLURM jobstep, so memory usage scales
with total job count — not just rule complexity. A job in a 26K-job workflow uses more
memory than the same rule in a 150-job workflow. Phase 2 `dag_overhead` quantifies this.

### Plugin notes (2.6.0)
- `--slurm-pass-command-as-script` — **do not use**, breaks array jobs
- `slurm_extra --output` — **forbidden** in 2.6.0, use `--slurm-logdir` instead
- `--use-conda` — breaks libarchive on compute nodes; the conda env is pre-activated

---

## Questions for You

1. **Array job submission overhead** — on this scheduler, does array submission (`sbatch --array`)
   meaningfully reduce scheduler pressure vs. individual `sbatch` calls? At what job count does
   the crossover happen?

2. **Optimal `--jobs` for this cluster** — we're testing 200/400/600 but don't know the practical
   ceiling where more concurrent jobs stops helping (scheduler queue limits, fair share, etc.).

3. **Job start latency** — what's the typical time from `sbatch` to job start on `u20` partition
   for a 1-CPU, 2GB job? This directly affects whether local (`--cores all`) is competitive with
   SLURM for small job counts.

4. **nd2 contention** — is there a way to limit concurrent jobs per node (e.g., SLURM constraints
   or `--ntasks-per-node`) for rules that read the same source file? Or is this better handled
   at the snakemake level with `localrules`?

5. **Partition tuning** — would a dedicated partition for these benchmark runs give cleaner timing
   data by removing queue noise from other users?

---

## Results (tile tier, 150 jobs, April 5 2026)

```
#   Tag                              Backend   Arrays  Jobs  ArrLim  CPUs    Min
------------------------------------------------------------------------------------
1   local_all_cores                  local          -     -       -     -    4.1  ← fastest
2   slurm_arr_j400_al10_c1           slurm        yes   400      10     1    5.3
2   slurm_arr_j400_al20_c1           slurm        yes   400      20     1    5.3
2   slurm_arr_j600_al10_c1           slurm        yes   600      10     1    5.3
5   slurm_arr_j200_al5_c1            slurm        yes   200       5     1    6.0
5   slurm_arr_j200_al10_c1           slurm        yes   200      10     1    5.9
5   slurm_arr_j400_al5_c1            slurm        yes   400       5     1    5.9
8   slurm_arr_j400_al10_c2           slurm        yes   400      10     2    5.9
9   slurm_arr_j600_al20_c1           slurm        yes   600      20     1    6.2
10  slurm_arr_j600_al10_c2           slurm        yes   600      10     2    7.0
11  slurm_noarr_j200_c1              slurm         no   200       -     1   10.9
12  slurm_noarr_j400_c1              slurm         no   400       -     1   11.8
12  slurm_noarr_j600_c1              slurm         no   600       -     1   11.8
```

### Findings

**Local beats SLURM at tile scale.** For 150 jobs, running locally with all cores (4.1 min)
is ~30% faster than the best SLURM config (5.3 min). The SLURM overhead (job submission,
scheduling latency, array packaging) costs ~1.2 min at this job count.

**Array jobs are essential.** Non-array SLURM (10.9-11.8 min) is ~2× slower than array
SLURM (5.3-6.2 min). Individual `sbatch` calls at 150 jobs are significantly slower than
batching via `--array`.

**Sweet spot: `jobs=400-600, array_limit=10, cpus_per_task=1`.** Increasing jobs beyond 400
or array_limit beyond 10 doesn't improve performance at this scale.

**More CPUs per task hurts.** `cpus_per_task=2` trials (5.9-7.0 min) are consistently
slower than `cpus_per_task=1`. Likely cause: requesting 2 CPUs reduces node slot
availability, increasing queue wait time for these short-running jobs.

### Open questions for you

At **well scale (~5000 jobs)** and **production scale (~26K jobs)**, local is no longer an
option — the crossover point where SLURM becomes necessary is somewhere between 150 and
5000 jobs. What we don't yet know:

1. At what job count does SLURM with arrays match or beat local?
2. Does the array_limit sweet spot shift at higher job counts? (We expect yes — more
   jobs per rule means the deadlock threshold matters less, and higher limits may help.)
3. Is 5.3 min for 150 jobs scheduler-bound or I/O-bound? If jobs spend most of their
   queue wait time rather than running time, tuning the partition priority or requesting
   a reservation would help more than any snakemake parameter.
