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
**Launch from cheeserind login node** for all tiers (tile, well, full). cheeserind has
enough RAM to manage even well-scale (~4300-job) DAGs directly; no interactive Slurm
node is needed just for DAG management. cheesegrater (the older/weaker head node) has
been reported to OOM on large DAGs, but that is not the current working setup — do not
suggest it.

## Dataset Tiers
| Tier | Config | Jobs | Use |
|------|--------|------|-----|
| tile | `config/config_tile.yml` | ~150 (preprocess) | Fast iteration, harness calibration + search |
| well | `config/config_well.yml` | ~4300 (preprocess) | Well-scaling rule calibration |
| full | `config/config.yml` | ~26K | Production benchmark |

Tile and well output to isolated dirs (`brieflow_output_tile/`, `brieflow_output_well/`).

**Benchmark scope (by design)**: all three configs only contain `all:` and `preprocess:`
sections. This is intentional — the speed benchmarks on this branch are preprocess-only.
`flow.sh preprocess sbs phenotype` will raise `MissingRuleException: No rule to produce
all_sbs` after preprocess finishes; that error is expected and ignored. Do not treat it
as a bug and do not add `sbs:`/`phenotype:` sections unless the scope explicitly changes.

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

### Phase 1 — Speed search (~hours, runs overnight):
```bash
cd analysis/

# Step 1: Calibrate tile rules — MaxRSS/elapsed per rule (~15-30 min)
python harness/harness.py calibrate

# Step 2: Run all SEARCH_TRIALS, measure wall time per config (~8-12 hr)
python harness/harness.py search

# Step 3: See ranked results
python harness/harness.py report
```

### Phase 2 — Memory + scale (run after Phase 1):
```bash
# Step 4: Calibrate well-scaling rules on well tier (~1-2 hr)
python harness/harness.py calibrate_well

# Step 5: Compute DAG memory overhead
python harness/harness.py dag_overhead

# Step 6: Generate memory recommendations
python harness/harness.py mem_report

# Step 7: Run well tier with best Phase 1 config
python harness/harness.py scale_test
```

Results saved to `harness/results/`:
- `calibration_tile.json` — per-rule MaxRSS/elapsed on tile tier
- `trials.jsonl` — one line per search trial with wall time + params
- `calibration_well.json` — per-rule MaxRSS/elapsed on well tier
- `dag_overhead.json` — estimated DAG memory overhead per 1000 jobs
- `mem_recommendations.json` — final mem_mb per rule with breakdown
- `scale_test_well.json` — tile vs well wall time comparison

### Search trials (defined in SEARCH_TRIALS list in harness.py)
13 trials covering:
- Local backend (all cores)
- Slurm without array jobs (jobs: 200, 400, 600)
- Slurm with array jobs (jobs × array_limit × cpus_per_task variants)

search resumes automatically if interrupted (skips completed trials).

### Key findings so far (from Apr 4 efficiency report)
| Rule | MaxRSS | Requested | Waste |
|------|--------|-----------|-------|
| convert_sbs | 265 MB | 2130 MB | 88% |
| convert_phenotype | 687 MB | 3069 MB | 78% |
| calculate_ic_sbs | 945 MB | 59033 MB | 98% |
| extract_metadata_* | ~180 MB | ~2000 MB | 91% |

## Known Issues
- **DAG memory overhead — compute nodes**: Each array job task runs a mini-snakemake (`.batch` step) that uses ~270 MB at well scale (vs ~130 MB at tile scale, 150-job DAG). This overhead is NOT accounted for in tile-calibrated `mem_mb_recommended` values. When applying tile mem_recs to well runs, add `dag_overhead_mb` (183 MB from `mem_recommendations.json`) to `obs_rss_mb` before applying the margin: `corrected = round((obs_rss_mb + 183) * MEM_MARGIN_TILE)`. Example: convert_sbs needs ~675 MB at well scale, not 451 MB.
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

## Diagnosing Failures: Read the Log File for That Run, Don't Hypothesize
When snakemake reports `Error in rule X` / `WorkflowError: At least one job did not complete
successfully`, **do not theorize about causes from the parent's summary alone.** Open the
actual log files for the actual run:

1. **The snakemake master log** — cited in the parent's own output as
   `Complete log(s): .snakemake/log/<timestamp>.snakemake.log`. Open that file and read
   the section around the reported error jobids.
2. **The per-rule slurm log for each failing jobid** — under `slurm/slurm_output/rule/rule_<NAME>/`.
   Match by **output filename** (e.g. `grep -l "P-1_W-A1_T-4__image"` over the rule's log
   dir), not by mtime — mtime pulls whichever array task wrote last, which is often an
   unrelated one, and invites invented reconciliation narratives.
3. **`sacct` for the run window** — `sacct -u $USER --starttime=<run-start>` to confirm
   whether any slurm job actually hit a FAILED / TIMEOUT / OUT_OF_MEMORY state.
4. **`ls` the expected outputs** — do the files exist at the expected size on disk?

The `snakemake-executor-plugin-slurm` 2.6.0 has parent↔worker reporting bugs where every
slurm task returns exit 0 and every output file is on disk, yet the parent still marks
DAG jobids as failed. The only way to tell "real failure" from "plugin bookkeeping bug"
is to read the actual per-job logs. Hypothesizing from the parent's error text leads to
wrong conclusions.

## Harness Invariants
- **Never treat `runtime` as an optimization knob.** It is a slurm kill-ceiling, not a speed
  lever; tightening it only causes TIMEOUTs. The harness only sets `mem_mb` from mem
  recommendations. The single authoritative runtime is `default-resources: runtime: 400` in
  `slurm/config.yaml`.
- **Success gate (added 2026-04-28)**: `cmd_run_one_trial` and `cmd_run_well_trial` require
  the snakemake-emitted `Finished jobid: 0 (Rule: all_preprocess)` marker in the flow.sh
  aggregate log before writing to `results.tsv` / `well_results.tsv`. Pre-gate code only
  checked `wall_time > 60s`, which let partial-failure runs record a wall time as if they
  had completed. All such pre-gate rows were deleted on 2026-04-29 — only success-gated
  rows remain. The marker pattern is `Finished jobid: 0 (Rule: all_<MODULE>)` — snakemake
  emits one per top-level rule. If scope expands beyond preprocess, the same gate logic
  works by checking for `all_sbs`, `all_phenotype`, etc.
- **MEM_MARGIN_TILE = 4.0** (bumped from 1.5 on 2026-04-28). The 1.5× margin gave
  convert_sbs a 451 MB ceiling; under cluster load actual peak RSS exceeded that and
  slurmstepd OOM-killed jobs. 4× lifts it to 1120 MB and eliminates OOMs.

## Memory Calibration (Known Gap)
The `calibrate_well` command samples peak RSS from a single sample run under one cluster
condition. For most rules this is fine. For `calculate_ic_sbs` and `calculate_ic_phenotype`
it severely underestimates real full-scale peaks because those rules' memory scales
linearly with the **number of tiles per cycle/round**, not per job:

- `calculate_ic_sbs`: input ≈ N_tiles × tile_size for one cycle. Peak ≈ input + working
  set. Tile config (~10 tiles): peak < 1 GB. Well config (~333 tiles): peak ~15 GB observed.
- `calculate_ic_phenotype`: input ≈ N_tiles × phenotype_tile_size for one round.
  Tile config: peak ~2.5 GB. Well config (~1300 tiles, 70 MB each = 93 GB raw input):
  peak ~210 GB observed.

The original calibration values (945 MB / 2.5 GB) reflected tile-only sampling, and a
4× margin couldn't absorb the well-scale 5–80× growth. **Iterating up on memory caps
based on OOM events is wasteful** — it consumed 6 attempts × cluster compute on
2026-04-28 before we had stable values.

**Current stopgap** (2026-04-29):
- `harness/results/mem_recommendations.json` — observed peak × 1.5 overhead, aggregated
  across all efficiency CSVs in `logs/`. Self-correcting: each successful run feeds
  forward worst-case observations.
- `WELL_MEM_CONSERVATIVE` in `harness.py` — duplicates the well-scaling rule values from
  the JSON. Future cleanup is to drop the duplicate and have `use_well_mem` read the JSON.

**Real fix (TODO, not yet implemented)**:
1. Replace `calibrate_well` with an aggregator that walks `logs/efficiency_*.csv` and
   recomputes worst-case peak per rule on every call, instead of single-sample.
2. Build a per-rule scoring formula: `mem_mb = k_rule × total_input_size_MB + b_rule`,
   with constants learned from observations. Predicts memory for any new screen with
   different tile counts WITHOUT recalibration. Falls back to `mem_recommendations.json`
   if the formula isn't computable for a given rule.

The lesson from 2026-04-28: "iterate up on the cap until it stops OOMing" is a bad
workflow. Trust the observation data we already produce; don't re-derive memory empirically
under cluster pressure.

## Robust Configs (2026-04-28)
Tile-tier (verified clean, 150/150, success-gated, 0 OOM, 0 MissingOutputException):
```
backend=slurm  use_arrays=true  jobs=400  array_limit=20
latency_wait=30  cpus_per_task=1  use_mem_recommendations=true
```
Wall: ~6.10 min sacct envelope, ~7.0 min flow.sh (incl. expected SBS-module
MissingRuleException startup). `latency_wait=30` clears NFS attribute-cache
propagation; lower values caused MissingOutputException + failure-cleanup that
deleted already-landed outputs.

Well-tier (use this — `use_arrays=false`):
```
backend=slurm  use_arrays=false  jobs=400  latency_wait=30
cpus_per_task=1  use_tile_mem=true  use_well_mem=true
```
**Do NOT use `use_arrays=true` at well or full scale.** The slurm-executor-plugin 2.6.0
array mechanism has a wildcard-collision bug: it packs N distinct-wildcard tile jobs
into one array task with a single `--comment` string. Sibling array members each verify
the FIRST member's wildcards instead of their own, hit MissingOutputException, and
trigger snakemake's failure-cleanup that deletes other siblings' real outputs. At tile
scale (~150 jobs, small batches) this is invisible; at well scale (~4,300 jobs) it
cascades and kills the run. See COLLAB.md Phase 7 for the concrete trace.

## Resume Workflow (Recovering from Late-Stage Failures)

When a long run dies after most jobs have completed (e.g. an OOM in the long-pole tail
at 99.7% of preprocess), don't restart from scratch. Snakemake's incremental scheduler
will skip jobs whose outputs already exist on disk:

1. **Fix the underlying issue** (bump mem cap, fix config, etc.).
2. **Don't wipe the output directory.** `cmd_run_well_trial` clears `brieflow_output_well/`
   by default; pass `--resume` to skip that step:
   ```bash
   python harness/harness.py run_well_trial --resume
   ```
3. **Snakemake re-detects the DAG state** via `--rerun-triggers mtime` (already in the
   harness's flow.sh invocation) and submits only the still-needed jobs.
4. **Wall time recorded by the harness in this case is for the resume only**, not the
   cumulative time across attempts. Note this in `well_results.tsv` notes column when
   recording — single-run wall is misleading after a resume.

This is what made the 2026-04-29 well-tier success possible: the bulk of preprocess
(4317/4328 jobs) was completed in v2, then v6 finished the remaining 11 IC jobs in ~10 min
after `WELL_MEM_CONSERVATIVE` was bumped. Without `--resume`, we'd have re-run ~3 hours
of completed work.

**Caveat**: only use `--resume` when you're confident the existing outputs are correct.
If a previous failure mode could have corrupted partial outputs (e.g. a write that got
truncated), it's safer to wipe and restart.

## slurm/config.yaml runtime
Always express `runtime` as a string with units (e.g. `runtime: "1d"`, `runtime: "12h"`),
not a bare int. Bare ints take an unintended path through snakemake's resource
handling that yielded a 7-min slurm Timelimit when we set `runtime: 400`. The string
form goes through `parse_human_friendly` and produces the expected timelimit. Verify
once via `sacct -j <id> --format=Timelimit` after any change. Do not tune runtime —
it is a kill ceiling, not a knob.

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
