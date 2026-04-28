# Brieflow Speed Benchmarking

## Getting Started

```bash
# Clone both speed branches
git clone -b speed https://github.com/cheeseman-lab/brieflow-analysis brieflow-speed
cd brieflow-speed
git submodule update --init --recursive  # checks out brieflow/speed branch

# Set up environment
conda create -n brieflow_speed -c conda-forge python=3.11 uv pip -y
eval "$(conda shell.bash hook)" && conda activate brieflow_speed
cd brieflow && uv pip install -e ".[dev]" && cd ..

# Run the well-tier validation (next step)
cd analysis/
bash autoresearch/run_well_overnight.sh 2>&1 | tee autoresearch/well_run2.log
```

Results appear in `analysis/autoresearch/well_results.tsv`. See **What's Next** below for what to do after.

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
- **Scope (by design)**: the benchmark is preprocess-only. The tile/well/full configs
  intentionally contain just `all:` and `preprocess:` sections, so flow.sh stops after
  preprocess with `MissingRuleException: No rule to produce all_sbs` — this is expected;
  the subsequent-module errors are ignored. The winner time is the 150-job preprocess DAG
  wall time. Expanding scope to SBS/phenotype is not on the roadmap for this branch.

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
- All attempts failed, cause unknown. Previous write-ups blamed tmux socket cleanup, but
  this has never been reproduced and tmux has historically been reliable for these
  sessions. Treat the prior failures as undiagnosed and re-run fresh.
- **No valid well results recorded yet**

### Phase 6: First fully verified clean runs (2026-04-28)
The success-gating exposed that the historical "3.4 min winner" was logging partial
failures as wins. After fixing two configuration brittleness sources, we have the first
honest baselines:

| Config | Wall (gated) | held | queued | compute | parallelism | failures |
|---|---|---|---|---|---|---|
| `winner_4x_lat30`            (arrays)    | **6.10 min** | 29%  | 0.6%  | 70% | 19.7× | 0 |
| `winner_4x_lat30_noarrays`   (no arrays) | **11.18 min**| 0%   | 18%   | 82% | 11.2× | 0 |

**What changed from the historical "3.4 min winner":**
- `latency_wait`: 5 → **30** (NFS attribute-cache propagation under load can exceed 10s,
  causing MissingOutputException + snakemake's failure-cleanup to delete files that DID
  land. lat=5 and lat=10 reproduced this; lat=30 cleared it on this cluster.)
- `MEM_MARGIN_TILE`: 1.5× → **4.0×** (the 1.5× margin gave convert_sbs a 451 MB cap;
  under load actual peak RSS exceeded that and slurmstepd OOM-killed jobs. 4× lifted
  the cap to 1120 MB and OOMs went to zero.)

**MissingOutputException is real data loss, not just bookkeeping noise.** When NFS
visibility lags, snakemake's mini-snakemake declares the output missing, the parent
declares the rule failed, and snakemake's failure-cleanup actively deletes the (just-
landed) output file. Cross-ref evidence: per-rule slurm logs show "Storing output in
storage" + parent-dir listings include the file at the moment the exception fires.

**At tile scale**, array batching is NOT the cause of MissingOutputException. Tested both
with and without arrays at lat=30: both clean. Arrays win 1.8× by absorbing cluster-slot
contention into a small held-time tax instead of a large queued-time tax.

### Phase 7: Array-batching wildcard-collision bug at well scale (2026-04-28)
Above conclusion held only at tile scale (~150 jobs). At well scale (~4,300 jobs), arrays
fail catastrophically due to a `snakemake-executor-plugin-slurm` 2.6.0 defect:

- The plugin packs N distinct-wildcard rule invocations into a single slurm array task.
- Slurm's `--comment` field (which the plugin uses to encode wildcards) is ONE string
  per submission. The plugin emits the warning twice per batch:
  > `Array job submission does not allow for multiple different wildcard combinations
  > in the comment string. Only the first one will be used.`
- All N mini-snakemakes (each on a different compute node) read the comment, see the
  FIRST member's wildcards, and treat that tile as part of their own work.
- Each mini-snakemake successfully writes its own assigned tile (the `.0` python step
  records `COMPLETED 0:0` in sacct), then verifies the comment-encoded tile (which a
  sibling task produced). NFS hasn't propagated the sibling's write → `MissingOutputException`.
- Snakemake's failure-cleanup runs and **deletes the sibling's actual output**. The
  sibling task ran cleanly but its output is gone. Cascade.

Concrete trace (well_winner_4x_lat30_runtime1d, 2026-04-28 15:13–15:20):
- Task `7561311_1` produced T-57_C-3 cleanly (sacct COMPLETED, log shows `1 of 1 steps
  (100%) done`, `Storing output in storage`).
- Task `7561311_20` (assigned T-226_C-2, host c13b3) read the same comment-string
  wildcards and tried to verify T-57_C-3. Hit MissingOutputException at 30s.
- `7561311_20.log` line: `Removing output files of failed job convert_sbs since they might
  be corrupted: brieflow_output_well/preprocess/images/sbs/P-1_W-A1_T-57_C-3__image.tiff`
- T-57_C-3 deleted from disk despite task _1 having produced it correctly.

20 such cross-contaminations in a single batch caused the cascade that killed the well
run at 134/4328 steps.

**Implication**: arrays cannot be used at well or full scale on this plugin version. The
robust well config requires `use_arrays=false` until the upstream bug is fixed. We trade
away the plugin's headline 1.8× speedup for correctness.

### Phase 5: sacct pending-time decomposition (tool built 2026-04-23)
- New subcommand: `python harness/harness.py diagnose [--csv PATH]`
- Joins the efficiency CSV (already has `JobID → RuleName`) with a post-hoc `sacct` pull
  for `Submit/Eligible/Start/End`. Decomposes per parent array task:
  - `held    = Eligible - Submit`  — scheduler-held (deps, `MaxSubmitJobs`, rate limit)
  - `queued  = Start - Eligible`   — no free slot at the requested resources
  - `compute = End - Start`        — actual run time (includes mini-snakemake wrapper)
- Writes `harness/results/diagnose_<uuid>.json` + prints a ranked per-rule table.
- **First datapoint (tile-scale winner config, 7.55 min wall)**: compute dominates
  entirely (166 min job-sec vs 13 min held+queued). `held` is a flat ~6s/job across all
  rules — likely the plugin's own `latency_wait`+status-check overhead, not rate limiting.
  `queued` is ~0s everywhere except the tail rules waiting on dependency chains.
- **Implication**: at tile scale the cluster scheduler is NOT the bottleneck. Whether the
  same holds at well scale is the question the admin conversation should answer.

### Harness bugs found and fixed (2026-04-23)
- **Runtime-as-knob bug**: `apply_mem_recommendations` was pushing a derived
  `runtime_recommended` (computed from observed elapsed × 2) into the slurm profile as a
  per-rule `runtime:`. This tightened the slurm kill-ceiling and caused TIMEOUTs on
  `calculate_ic_sbs` / `calculate_ic_phenotype` under any cluster slowdown. Runtime is a
  ceiling, not an optimization target — never tune it. Fixed: removed the `runtime`
  assignment, the `runtime_rec` computation, the `RUNTIME_MARGIN` constant, the dead
  `runtime_recommended: 30` write in the well path, and stripped stale values from
  `mem_recommendations.json`.
- **Success-tracking bug (still open)**: `cmd_run_one_trial` records any wall time > 60s
  to `results.tsv` without checking snakemake's exit code or output files. Failed and
  partially-completed runs get logged as valid trials. Every historical row in
  `results.tsv` is suspect on this basis — some of the fast outliers (2.4, 2.8, 2.9 min)
  may be partial failures, not real speedups. Fix: gate recording on exit==0 AND a
  spot-check of expected outputs on disk.

### Diagnostic rule (learned the hard way)
When snakemake reports `WorkflowError: At least one job did not complete successfully`,
**do not hypothesize causes from the parent's summary.** Open the actual log files for
the run before forming any theory:

1. **Snakemake master log** — the parent's output prints
   `Complete log(s): .snakemake/log/<timestamp>.snakemake.log`. Read the section around
   the reported error jobids.
2. **Per-rule slurm log** — under `slurm/slurm_output/rule/rule_<NAME>/`. Match by
   **output filename** (`grep -l "<expected-output>"`), NEVER by mtime — mtime grabs
   whichever task wrote last, often unrelated, and leads to invented explanations.
3. **`sacct` for the run window** — confirm whether any slurm job actually hit
   FAILED / TIMEOUT / OUT_OF_MEMORY.
4. **`ls` the expected outputs** — do the files exist at expected size?

The 2.6.0 plugin has parent↔worker reporting bugs where every slurm task returns exit 0
and every output file is on disk, yet the parent still marks DAG jobids as failed. The
only way to tell "real failure" from "plugin bookkeeping bug" is to read the actual
per-job logs. Hypothesizing from error text leads to wrong conclusions — concretely,
on 2026-04-23 I invoked a made-up "nd2 read contention" story (since removed from
CLAUDE.md) when every output was actually on disk.

---

## What's Next

1. ~~**Fix the harness success-tracking bug**~~ — DONE 2026-04-28 (preprocess-completion
   marker gate added; runtime-as-knob removed; mem margin bumped to 4×).
2. **Re-run well trials A/B/C with the robust config** (lat=30, mem 4×, arrays on, al=20)
   — single snakemake process on cheeserind
3. **Run `diagnose` on a clean well-tier trial** — the tool is built (Phase 5). At tile
   scale it showed compute-bound, no scheduler pressure. The well-scale decomposition is
   the datapoint that makes the admin conversation concrete.
4. **Well autoresearch** — if runs are ~30-40 min, do 10-15 trials overnight using the
   same agent loop as tile. Launch a Claude Code session in `analysis/`, load
   `autoresearch/program.md` as context, and let it run autonomously:
   ```bash
   cd analysis/
   # In Claude Code: read autoresearch/program.md and run the well autoresearch loop
   # using cmd_run_well_trial instead of run_one_trial
   ```

---

## Repo Structure

```
brieflow-speed/
├── analysis/
│   ├── flow.sh                     ← unified pipeline runner
│   ├── harness/harness.py          ← benchmark harness
│   ├── config/config_tile.yml      ← tile tier (~150 jobs)
│   ├── config/config_well.yml      ← well tier (~4,300 jobs)
│   ├── autoresearch/               ← trial configs, results, agent program
│   └── slurm/config.yaml           ← SLURM resources per rule
└── brieflow/                       ← pipeline code (speed branch)
```

**Run from cheeserind** — enough RAM to manage the well-scale DAG from the login node.

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

1. **Job submission rate limits and per-user caps** — we observe "Job rate limit reached"
   messages during submission but don't know the actual ceiling. We want to:
   - Know the per-user submission rate cap and `MaxSubmitJobs` limit
   - Understand whether array submissions count against these limits differently from
     individual submissions
   - Use this to calibrate `--slurm-array-limit` and `--jobs` optimally for this cluster
   Can you share the current limits, and is there headroom to raise them for benchmarking?
   (We will measure actual pending-vs-running time via sacct instrumentation on our side;
   the ask here is the configured cap, not the observed impact.)

2. **Array job submission overhead** — our data shows ~2× speedup from `sbatch --array`
   vs individual submissions at tile scale (~150 jobs). We want to understand:
   - At what job count does array submission stop helping (scheduler crossover point)?
   - What is the per-array-job vs per-individual-job scheduling latency on this cluster?
   This helps us set `--slurm-array-limit` correctly across tile/well/full scales.
