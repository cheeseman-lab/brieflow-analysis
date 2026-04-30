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

# Run a well-tier trial (default reads autoresearch/next_trial.json)
cd analysis/
python harness/harness.py run_well_trial 2>&1 | tee logs/run_well_$(date +%Y%m%d_%H%M%S).log

# Or pass an explicit trial JSON
python harness/harness.py run_well_trial --trial-json autoresearch/well_arrays_failure_test.json
```

Results appear in `analysis/autoresearch/well_results.tsv`. The harness's success gate
(`Finished jobid: 0 (Rule: all_preprocess)` in the flow.sh log) is what proves a run
completed cleanly; trials that fail the gate exit non-zero without recording. See
**What's Next** and **Handoff Notes** below for current state.

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

### Phase 2: Autoresearch — agent-driven tile search (data discarded 2026-04-29)
- Autonomous agent loop ran 30+ trials searching `array_limit`, `latency_wait`,
  `use_mem_recommendations`. Recorded data was DELETED after we found the harness's
  pre-gate success-tracking was logging partial-failure runs as if they had completed.
  Wall times in the historical rows underestimated by ~1.8× and parameter rankings
  were not trustworthy. Only post-gate rows from 2026-04-28 onward remain in
  `results.tsv` (see Phase 6).
- The qualitative finding that **arrays-on beats arrays-off ~2×** survived the cleanup
  because both modes were similarly affected by the tracking bug, so the relative
  comparison was preserved. Confirmed under the gated harness: 6.10 min arrays vs
  11.18 min no-arrays.

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
With the success gate in place, two clean tile-tier baselines were established:

| Config | Wall (gated) | held | queued | compute | parallelism | failures |
|---|---|---|---|---|---|---|
| `winner_4x_lat30`            (arrays)    | **6.10 min** | 29%  | 0.6%  | 70% | 19.7× | 0 |
| `winner_4x_lat30_noarrays`   (no arrays) | **11.18 min**| 0%   | 18%   | 82% | 11.2× | 0 |

**Two configuration brittleness sources had to be fixed before either could complete:**
- `latency_wait`: pre-gate trials had used 5 (an unreliable value chosen during the
  unreliable autoresearch). Bumped to **30** because NFS attribute-cache propagation
  under cluster load can exceed 10s, causing MissingOutputException → snakemake's
  failure-cleanup → deletion of files that DID land. lat=5 and lat=10 reproduced this;
  lat=30 cleared it on this cluster.
- `MEM_MARGIN_TILE`: was 1.5× (giving convert_sbs a 451 MB cap), bumped to **4.0×**.
  Under load the actual peak RSS exceeded 451 MB and slurmstepd OOM-killed jobs.
  4× lifts the cap to 1120 MB and eliminates OOMs at tile scale.

**MissingOutputException is real data loss, not just bookkeeping noise.** When NFS
visibility lags, snakemake's mini-snakemake declares the output missing, the parent
declares the rule failed, and snakemake's failure-cleanup actively deletes the (just-
landed) output file. Cross-ref evidence: per-rule slurm logs show "Storing output in
storage" + parent-dir listings include the file at the moment the exception fires.

**At tile scale**, array batching is NOT the cause of MissingOutputException. Tested both
with and without arrays at lat=30: both clean. Arrays win 1.8× by absorbing cluster-slot
contention into a small held-time tax instead of a large queued-time tax.

### Phase 7: Array-batching wildcard-collision bug at well scale (2026-04-28, mechanism revised 2026-04-29)
Above conclusion held only at tile scale (~150 jobs). At well scale (~4,300 jobs), arrays
fail catastrophically due to a `snakemake-executor-plugin-slurm` 2.6.0 defect.

**Source-level diagnosis (2026-04-29 re-investigation, verified by `--verbose` trace):**

The bug is in how the plugin builds its `sbatch --wrap` command for array submissions
(`snakemake_executor_plugin_slurm/__init__.py:884–917`):

```python
exec_job = self.format_job_exec(jobs[start_index - 1])   # only the FIRST job in the chunk
sub_array_execs = {str(i): array_execs[i]
                   for i in range(start_index + 1, end_index + 1)}  # remaining N-1 jobs
...
call_with_array += f' --wrap="{exec_job} --slurm-jobstep-array-execs={...payload...}"'
```

A single `--wrap=` is built from the chunk's first job and reused for every array task.
That wrap is a snakemake invocation carrying `--target-jobs '<rule>:<wildcards-of-first-job>'`.
Inside, the jobstep plugin sees `SLURM_ARRAY_TASK_ID`; for non-first tasks it decompresses
the right command from the payload and `Popen`s it (the actual work happens correctly,
producing the right tile's output). **But the surrounding inner snakemake spawned by the
wrap still has `--target-jobs=<first job>`. After Popen returns, that inner snakemake
verifies its own target on disk — the chunk's FIRST job's output, not whatever this task
actually produced.** If the first task's output isn't visible to this NFS client yet,
inner-1 raises `MissingOutputException`, and snakemake's failure-cleanup deletes the
target — i.e., wipes the *first* task's real output that some other compute node already
wrote. Cascade.

**Concrete `--verbose` trace (tile preprocess, 2026-04-29 23:48):**
The plugin debug-logs each chunk's wrap. Captured wraps (saved to
`analysis/harness/results/array_wrap_trace_evidence.txt`):

```
chunk 1-10 (convert_sbs)              wrap target=convert_sbs:plate=1,well=A1,tile=3,cycle=3
chunk 11-20 (convert_sbs)             wrap target=convert_sbs:plate=1,well=A1,tile=3,cycle=1
chunk 21-30 (convert_sbs)             wrap target=convert_sbs:plate=1,well=A1,tile=3,cycle=4
chunk 31-40 (convert_sbs)             wrap target=convert_sbs:plate=1,well=A1,tile=6,cycle=4
chunk 1-7  (convert_phenotype)        wrap target=convert_phenotype:plate=1,well=A1,tile=7
chunk 11-20 (extract_metadata_sbs)    wrap target=extract_metadata_sbs:...,cycle=3,channel=CY5_30p
...
```

Each `--array=N-M` carries a single `--target-jobs` for one tile. All M-N+1 sibling
tasks share that target. Confirmed across all rules submitted as arrays in the run.

**Concrete failure trace (well run, 2026-04-28 15:13–15:20):**
- Task `7561311_1` produced T-57_C-3 cleanly (sacct COMPLETED, `1 of 1 steps (100%) done`,
  `Storing output in storage`).
- Task `7561311_20` was assigned T-226_C-2 by the array_execs payload. It produced
  T-226_C-2 correctly via Popen. Then its surrounding inner snakemake (started with
  `--target-jobs=...,tile=57,cycle=3` per the chunk's wrap) verified T-57_C-3 instead of
  T-226_C-2. T-57_C-3 hadn't propagated yet on this NFS client.
- `7561311_20.log`: `Removing output files of failed job convert_sbs since they might
  be corrupted: brieflow_output_well/preprocess/images/sbs/P-1_W-A1_T-57_C-3__image.tiff`
- T-57_C-3 deleted from disk despite task `_1` having produced it correctly.

20 such cross-contaminations in a single batch caused the cascade that killed the well
run at 134/4328 steps.

**Why tile scale survives:** the same race exists. Inner-1 of every non-first task
verifies the chunk's first task's output. At tile scale (~150 jobs, fast rules, batches
of ≤10) the first task typically completes and its output propagates within
`latency_wait=30` of when sibling tasks finish, so verification incidentally passes. At
well scale (~4,300 jobs, slower rules, more variance) the first task is often still
running when siblings finish; verification fails; cleanup deletes; cascade. `latency_wait`
just buys the FS more propagation grace — it doesn't fix the underlying mistake.

**Note on prior diagnosis:** the original 2026-04-28 write-up attributed the cascade to
the `--comment` field. The plugin does emit a misleading warning to that effect:
> `Array job submission does not allow for multiple different wildcard combinations in
> the comment string. Only the first one will be used.`
…but `--comment` is purely a sacct/squeue label — snakemake never reads it back. The
real shared-state vector is `--target-jobs` inside the wrap, as shown above.

**Live capture at well scale (2026-04-30 07:44–08:55, 70 min run, killed in deadlock):**
A fresh `well_arrays_failure_test_20260430` trial reproduced everything above with
verbose plugin debug logging:
- 49 array submissions captured with full wrap content. Every chunk has exactly one
  `--target-jobs` regardless of array task count — same shape we observed at tile.
- 91 "Removing output files" cleanup events fired (the failure-cleanup that wipes
  siblings' real outputs).
- 353 "Error in rule" events — the failure pattern in action.
- Only 81/4328 steps marked done after 70 min, then snakemake deadlocked in
  "Ready jobs: 3481, Selected: 0" because every dependent had a "failed" upstream.
- Saved as `analysis/harness/results/array_wrap_trace_well_20260430.txt`.
- Recorded in `well_results.tsv` as `well_arrays_failure_test_20260430`.

**Upstream status (checked 2026-04-29):** wrap construction is identical in v2.6.0,
v2.6.1 (current release), and `main` HEAD. No PR fixes it. Adjacent open issue
[#447](https://github.com/snakemake/snakemake-executor-plugin-slurm/issues/447) reports
"Job arrays across different wildcards may not create output directories" with a related-
but-distinct symptom (output directories not created for templated paths) — same bug
family ("array path makes wildcard assumptions") but a different failure mode. We have
not filed an upstream issue for our exact symptom yet.

**Implication**: arrays cannot be used at well or full scale on this plugin version. The
robust well config requires `use_arrays=false` until the upstream bug is fixed. We trade
away the plugin's headline 1.8× speedup for correctness.

### Phase 8: Well-tier preprocess success + memory calibration learning (2026-04-29)

**Outcome**: First fully success-gated well-tier preprocess completion on the speed
branch. 4,328 jobs total, ~136 GB output. Cumulative wall ~3.5 hr across resume
iterations (most work in v2 to 99.7%, completed in v6 with mem caps that don't OOM).

**Key memory calibration finding**: `calibrate_well` (single-sample, run on Apr 5)
severely underestimated peak RSS for `calculate_ic_*` rules at full well scale because
those rules' memory scales linearly with N_tiles per cycle/round:

| Rule | Apr 5 calibration | 2026-04-28 well-scale observed |
|---|---|---|
| `calculate_ic_sbs` | 945 MB | **15.7 GB** (per cycle, ~333 tiles each) |
| `calculate_ic_phenotype` | 2.5 GB | **210 GB** (~1300 tiles × 70 MB raw + working set) |
| `convert_phenotype` | 686 MB | 839 MB |
| `convert_sbs` | 268 MB | 402 MB |
| `extract_metadata_*` | ~180 MB | ~317 MB |

The calculate_ic_phenotype gap is **80× the calibration value**. Iterating up on
caps based on OOM events consumed 6 attempts (10G → 16G → 32G → 128G → 500G) before
landing on baker's production value. With the actual data in hand, true peak is 210 GB
and a 1.5× overhead gives 315 GB — substantially under baker's 500 GB.

**Updated `mem_recommendations.json`** (2026-04-29, formalized 2026-04-30): switched
semantics from "calibration sample × margin" to "worst-case observed peak across all
efficiency CSVs × 1.5 overhead". This is the new stable defaults source. The aggregator
is now a first-class harness command (`python harness/harness.py aggregate_efficiency`,
added 2026-04-30) — walks every `logs/efficiency_*/*.csv`, takes worst peak per rule,
flags rules whose peak landed within 5% of the slurm cap (likely OOM-clipped). The
duplicated `WELL_MEM_CONSERVATIVE` table was deleted from `harness.py` on 2026-04-30;
both `use_tile_mem` and `use_well_mem` flags now read directly from the JSON, filtered
by tier.

**Lesson**: every run produces an efficiency CSV with per-job `MaxRSS_MB`. We were
generating this data from the start but not feeding it back into mem recommendations.
"Iterate up on the cap until it stops OOMing" was the bad workflow; "look at the data
we already have" was the missed opportunity.

### Phase 9: Source-level array-bug confirmation + first fresh well wall (2026-04-30)

Three things happened today, all flow from yesterday's open thread on the array bug.

**(A) Source-level confirmation of the array wrap-collision mechanism.** Original 04-28
narrative blamed `--comment`; turns out the actual shared-state vector is `--target-jobs`
inside the `--wrap=` string (built from `jobs[start_index-1]` only). Confirmed by reading
`snakemake_executor_plugin_slurm/__init__.py:884-916` and tracing the jobstep counterpart.
A subagent search confirmed: identical in v2.6.0, v2.6.1, current `main` HEAD; no fix
in flight; adjacent issue #447 is in the same bug family but a distinct symptom. Phase 7
above is the rewritten mechanism; the `--comment` story is preserved as a "prior
diagnosis" footnote.

**(B) Live capture of the bug at both scales.** `flow.sh` now permanently passes
`--verbose` so the plugin's `call with array:` debug line is preserved on every run.
- Tile capture (2026-04-29, 7-min run): 17 chunks across 4 rules, single `--target-jobs`
  per chunk every time. Saved to `harness/results/array_wrap_trace_evidence.txt`.
- Well capture (2026-04-30, killed at 70 min): 49 chunks captured, 91 cleanup events,
  353 rule-error events, 81/4328 steps before deadlock. Saved to
  `harness/results/array_wrap_trace_well_20260430.txt`.

**(C) First fresh end-to-end well-tier preprocess wall.** `well_noarrays_fresh_20260430_preprocess`:
**193 min** (preprocess only, modules=["preprocess"], use_arrays=false, latency_wait=30,
mem_recommendations.json). 4328/4328 steps, success-gate marker landed.

**Other findings from the day:**
- `latency_wait=30` is borderline at well scale even with `use_arrays=false`. The 193-min
  run got lucky on cross-node NFS visibility; an immediate retry with the same config
  hit 3 convert_sbs MissingOutputException events at exactly 30s (files were on disk —
  the visibility lag was the issue, not real data loss). CLAUDE.md "Robust Configs" now
  recommends `latency_wait=60` for well-tier no-array runs.
- `config_well.yml` carries real `sbs:` and `phenotype:` sections (added 2026-04-29 in
  commit `c370a0b`). The original "preprocess-only by design" CLAUDE.md claim was
  out of date. The harness was hardcoding `["preprocess", "sbs", "phenotype"]` modules
  and actually running them at well scale — discovered when the 193-min run cascaded
  into `phenotype_tile_group` rule failures after preprocess succeeded.
- **`phenotype_tile_group` has a real rule-code bug at well scale**: jobs fail in the .5
  sub-step with exit 1:0 in ~12s, MaxRSS ~629 MB on a 6 GB cap (so not OOM, not timeout).
  Real code error inside the python step. Needs separate triage; not infrastructure.
- Harness `cmd_run_well_trial` now reads `modules` from the trial JSON (defaults to the
  historical `["preprocess", "sbs", "phenotype"]` for back-compat). Both
  `next_trial.json` and `well_arrays_failure_test.json` now scope `modules: ["preprocess"]`
  so the broken phenotype phases don't pollute speed measurements.

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

Done since this doc was last refreshed (2026-04-29 / 2026-04-30):
- ~~**Fix the harness success-tracking bug**~~ — DONE 2026-04-28.
- ~~**Re-run well trials with the robust config**~~ — DONE 2026-04-29.
- ~~**Replace single-sample `calibrate_well` with efficiency-CSV aggregator**~~ — DONE
  2026-04-30 as `python harness/harness.py aggregate_efficiency`.
- ~~**Drop `WELL_MEM_CONSERVATIVE` from harness.py**~~ — DONE 2026-04-30.
- ~~**Confirm array-bug mechanism at source level + capture at well scale**~~ — DONE
  2026-04-30 (Phase 9).
- ~~**First fresh end-to-end well-preprocess wall time**~~ — DONE 2026-04-30, 193 min.

Open:
1. **File an upstream issue** for the array `--target-jobs` collision. We have all the
   evidence: source-line citation, tile + well verbose traces, well-scale failure trace
   with 91 cleanup events. Cross-link issue #447 as related-but-distinct. Until upstream
   merges a fix, `use_arrays=false` is the only correct setting at well/full scale.
2. **Triage the `phenotype_tile_group` rule-code bug.** Jobs fail in the .5 sub-step
   with exit 1:0 in ~12s, MaxRSS 629MB / 6GB cap (not OOM, not timeout — real Python
   error). Read the actual per-job slurm log under
   `slurm/slurm_output/rule/group_phenotype_tile_group_*` to see what's throwing.
   Unrelated to the array bug; blocks downstream module benchmarking.
3. **Re-run well no-array preprocess at `latency_wait=60`** to get an auto-recorded row
   in `well_results.tsv` (the current 193-min row is hand-recorded because the harness
   was killed mid-cascade). Bumping latency_wait should keep no-array runs robust under
   varying cluster load.
4. **Per-rule scoring formula for memory.** `mem_mb = k_rule × total_input_size_MB + b_rule`
   with constants learned from observations. Generalizes to new screens with different
   tile counts without recalibration. See CLAUDE.md "Memory Calibration" for design.
   Falls back to `mem_recommendations.json` if not computable.
5. **Run `diagnose` on a clean well-tier trial** — the tool is built (Phase 5). At tile
   scale it showed compute-bound, no scheduler pressure. The well-scale decomposition is
   the datapoint that makes the admin conversation concrete.
6. **Well autoresearch** — once latency_wait is settled and the phenotype bug is
   triaged, do 10-15 trials overnight using the same agent loop as tile. Launch a Claude
   Code session in `analysis/`, load `autoresearch/program.md` as context, and let it
   run autonomously:
   ```bash
   cd analysis/
   # In Claude Code: read autoresearch/program.md and run the well autoresearch loop
   # using cmd_run_well_trial instead of run_one_trial
   ```

---

## Handoff Notes (2026-04-30)

The repo is in a clean state for fresh investigation. Key artifacts:

**Evidence files** (under `analysis/harness/results/`):
- `array_wrap_trace_evidence.txt` — tile-tier verbose trace, 17 chunks, 4 rules
- `array_wrap_trace_well_20260430.txt` — well-tier verbose trace, 49 chunks, single
  `--target-jobs` per chunk regardless of array task count, plus deadlock summary
- `mem_recommendations.json` — current canonical memory caps, regenerable via
  `python harness/harness.py aggregate_efficiency`

**Logs** (under `analysis/logs/`):
- `run_well_arrays_failure_20260430_074405.log` — full verbose harness log of the
  array failure run (91 cleanup events, 353 rule errors)
- `run_well_noarrays_preprocess_*.log` — both the 193-min successful run and the
  immediate retry that hit the latency_wait=30 NFS race
- `preprocess-20260430_*.log` — flow.sh log files

**Results** (under `analysis/autoresearch/`):
- `well_results.tsv` — 4 rows, all with explicit caveats:
  - `well_resume_only_v6` — historical resume-only baseline (NOT a benchmark)
  - `well_noarrays_fresh_20260430_preprocess` — 193 min fresh wall (manual)
  - `well_noarrays_preprocess_20260430_FAILED` — NFS race retry (manual)
  - `well_arrays_failure_test_20260430` — array bug live (manual)
- `next_trial.json` and `well_arrays_failure_test.json` — both scope to
  `modules: ["preprocess"]`, both use the success-gated harness path

**Key code locations to dig into:**
- Array bug: `site-packages/snakemake_executor_plugin_slurm/__init__.py` lines
  884-916, especially line 889 (`exec_job = self.format_job_exec(jobs[start_index - 1])`)
- Jobstep counterpart: `site-packages/snakemake_executor_plugin_slurm_jobstep/__init__.py`
  lines 154-166 (the `_is_first_array_task` branch)
- Harness modules-arg: `analysis/harness/harness.py` `cmd_run_well_trial`, line ~672
- Aggregator: `analysis/harness/harness.py` `cmd_aggregate_efficiency`

**Things that look surprising but are intentional:**
- `flow.sh` always passes `--verbose` — keeps the plugin's array-debug log line on
  every run; tiny overhead, big diagnostic value.
- The 193-min row is hand-recorded — the harness's success gate worked correctly
  (preprocess marker landed) but flow.sh kept running into the broken sbs/phenotype
  phase, which we killed before the harness got back to writing the row.
- `well_results.tsv` has no `use_arrays` column — `array_limit=n/a` implies false,
  a number implies true. The notes column is the source of truth for each row.

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
