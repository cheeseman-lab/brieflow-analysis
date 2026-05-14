# brieflow-speed — Claude Instructions

## What This Repo Is
Speed-optimization branch of brieflow OPS pipeline. Two `speed` branches:
- This repo (`brieflow-analysis` fork): `analysis/` scripts, configs, the
  slim cluster-optimization launcher
- `brieflow/` submodule: pipeline code (polars I/O, vectorization, dep bumps)

Working directory for all commands: `analysis/`

The heavy runtime + recovery logic (runloop, recover.py, push notifications,
phase orchestration, config validation) lives in the **brieflow-ops plugin**
at `/lab/barcheese01/mdiberna/brieflow-ops/`. This repo provides the per-
screen data + a thin tier launcher.

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
node is needed just for DAG management. Caveat: external memory pressure on the login
node CAN OOM-kill the snakemake driver mid-run (caught 2026-05-13 baker v33 — lost
~5 hr of progress until manually relaunched). HARDENING_TODO #24 in the plugin
tracks the driver-watchdog fix.

cheesegrater (the older/weaker head node) has been reported to OOM on large DAGs;
do not suggest it.

## Dataset Tiers
| Tier | Config | Jobs | Use |
|------|--------|------|-----|
| tile | `config/config_tile.yml` | ~150 (preprocess) | Fast iteration, dev cycles |
| well | `config/config_well.yml` | ~4300 (preprocess) | Single-well validation |
| full | `config/config.yml` | ~26K | Production screen run (e.g. baker = 1 plate × 6 wells) |

Tile and well output to isolated dirs (`brieflow_output_tile/`, `brieflow_output_well/`).

## Running the Pipeline

**Production runs** go through the plugin's runloop directly (autonomous OOM
recovery, push notifications, mem-rec injection):

```bash
python /lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_runloop.py \
  --analysis-dir /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis \
  --phases preprocess,sbs,phenotype \
  --config config/config.yml \
  --backend slurm --jobs 400 --latency-wait 60 \
  --max-attempts 99 \
  --tag <descriptive_tag>
```

Or via the `/brieflow-run` Claude Code slash command if the plugin is installed.

**Dev cycles** (tile/well-tier) use the slim harness in `analysis/cluster_optimization/`:

```bash
python cluster_optimization/harness.py run_tile [--tag X] [--notes "..."]
python cluster_optimization/harness.py run_well [--tag X] [--notes "..."]
python cluster_optimization/harness.py aggregate_efficiency
```

These are thin wrappers that invoke the same plugin runloop with the appropriate
tier config. See `analysis/cluster_optimization/README.md` for details.

**Direct flow.sh** (lower level, no auto-recovery):

```bash
bash flow.sh preprocess --backend slurm --profile --configfile config/config_tile.yml
bash flow.sh preprocess sbs phenotype --backend slurm --profile --configfile config/config_tile.yml

# Monitor
squeue -u $USER | head -20
tail -f logs/preprocess-*.log
```

## Per-Screen Sizing Data

`analysis/cluster_optimization/results/`:
- `mem_recommendations.json` — canonical per-rule mem caps. Refreshed after
  successful runs by `aggregate_efficiency`. Manual override entries
  (`obs_source` containing `manual_override`) are preserved across refreshes
  so post-OOM bumps don't get clobbered.
- `baker_observations_raw_2026-05-14.csv` — 66,207 per-job RSS observations
  from the full baker session (April 28 → May 14). Bootstrap dataset for
  fitting per-rule scaling formulas (HARDENING_TODO #23 in the plugin).
- `baker_scaling_summary_2026-05-14.csv` — per-rule summary (peak / p99 /
  p95 / median / suggested_cap).

## Known Issues
- **Array wrap-target collision (well/full scale, BLOCKING)**: `snakemake-executor-plugin-slurm`
  2.6.0/2.6.1/main builds each `--array=N-M` chunk's `--wrap=` from `jobs[start_index-1]`
  only, so all sibling tasks share one `--target-jobs` and verify the wrong file. At well
  scale this cascades into snakemake's failure-cleanup deleting siblings' real outputs.
  Andy retested 2026-05-14 — still broken upstream. Must use `use_arrays=false` at
  well/full scale.
- **disk_mb auto-calculation**: Snakemake sets `disk_mb` = 2× input file size. For
  well-level nd2s (84 GB each × 4 channels = 685 GB requested). Not enforced on our
  cluster but worth overriding.
- **Login-node driver SIGKILL**: external memory pressure on cheeserind can OOM-kill
  the snakemake driver mid-run (exit 137). Snakemake's `--rerun-triggers mtime` resume
  recovers cleanly when relaunched. HARDENING_TODO #24 (plugin) tracks the watchdog fix
  for unattended runs.

## snakemake-executor-plugin-slurm 2.6.0 Notes
See `slurm/further_2.6.0.md` for full docs.
- `--slurm-array-jobs=all` — enable array submission (DO NOT USE at well/full scale)
- `--slurm-array-limit=10` — keep low if testing arrays
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

## Resume Workflow

When a long run dies after most jobs have completed (e.g. OOM in the long-pole tail
at 99% of preprocess), don't restart from scratch. Snakemake's incremental scheduler
will skip jobs whose outputs already exist on disk:

1. **Fix the underlying issue** (bump mem cap, fix config, etc.).
2. **Don't wipe the output directory.** The plugin's runloop preserves outputs by default.
3. **Snakemake re-detects the DAG state** via `--rerun-triggers mtime` (already in the
   plugin's flow.sh invocation) and submits only the still-needed jobs.
4. **Wall time recorded for the resume is for the resume only**, not the cumulative time
   across attempts. Note this when interpreting results.

**Caveat**: only resume when you're confident existing outputs are correct. If a previous
failure mode could have corrupted partial outputs (truncated writes, etc.), wipe and restart.

## slurm/config.yaml runtime
Always express `runtime` as a string with units (e.g. `runtime: "1d"`, `runtime: "12h"`),
not a bare int. Bare ints take an unintended path through snakemake's resource handling
that yielded a 7-min slurm Timelimit when we set `runtime: 400`. The string form goes
through `parse_human_friendly` and produces the expected timelimit. Verify once via
`sacct -j <id> --format=Timelimit` after any change. Do not tune runtime — it is a kill
ceiling, not a knob.

## Checking Efficiency After a Run
```bash
# Efficiency report (if --profile was used — runloop sets this by default)
ls logs/efficiency_*/

# sacct summary
sacct -u $USER --starttime=2026-04-04T15:00 \
  --format=JobID%25,Elapsed,MaxRSS,ReqMem,NCPUS,TotalCPU,State --parsable2

# Refresh mem_recommendations.json from all observations
python cluster_optimization/harness.py aggregate_efficiency
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
