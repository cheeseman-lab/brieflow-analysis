# Brieflow Plugin Feedback

Things the brieflow plugin (`brieflow-ops`) should know about or consider implementing,
based on issues encountered on this branch (`brieflow-speed`).

## Config schema source of truth

`brieflow/tests/small_test_analysis/config/config.yml` in the brieflow submodule defines
the canonical schema for the brieflow version pinned in your repo. It is NOT safe to
copy configs from sibling production screens — they may carry deprecated keys.

**2026-04-28 example**: copying baker's config (which has `foci_channel: 2`) into the
speed-branch repo failed because the speed-branch's `phenotype.smk` requires
`foci_channel_index: 2`. Several other key renames and additions:
- baker's `cyto_model: cyto3` → speed-branch's `cellpose_model: cyto3` (phenotype only)
- baker had separate `nuclei_/cell_flow_threshold` and `_cellprob_threshold`; speed-branch
  consolidated these to single `flow_threshold` and `cellprob_threshold` for phenotype
- speed-branch added `manual_channel_mapping`, `dapi_cycle_index`, `barcode_type`,
  `heatmap_shape`, `heatmap_plate`, `window` (sbs); these don't exist in baker's config

**Suggestion**: `/brieflow-migrate` should reference `tests/small_test_analysis` in the
brieflow submodule as the schema diff target, not just the brieflow-analysis template.
The test-analysis tracks the submodule code exactly, so its config is always in sync
with what the rules require.

## Don't edit configs while a pipeline is running

Snakemake's mini-snakemake processes re-parse the snakefile (and config) on every job
spawn. Editing `config/config.yml` while a run is in flight will KeyError every job
spawned after the edit — even if the edit is "correct" but incomplete (e.g., adds new
sections that reference keys not yet filled in).

**2026-04-28 example**: a well-tier preprocess run was at 19% (~38 minutes in) when
sbs/phenotype sections were added to the active config to "make Andy's reference
complete." The next job submission re-parsed the snakefile, hit `KeyError:
'manual_channel_mapping'` (a key the running rule didn't need but the snakefile module
does), and the run cascaded into 38 errors before it could be killed. The previous
~38 minutes of cluster compute were lost.

**Suggestion**: detect when an active snakemake process exists for the workflow's profile
(e.g., presence of `.snakemake/locks/`) and warn or block config edits via the plugin's
config commands. At minimum, document this as a sharp edge in `/brieflow-run` output.

## Memory calibration

See `CLAUDE.md` → "Memory Calibration (Known Gap)" for the full problem description.
Summary: the current `calibrate_well` in `harness/harness.py` samples peak RSS from a
single run under one cluster condition. This is fine for rules whose memory is
~constant per job, but underestimates **peak RSS for rules whose memory scales with
input cardinality** (e.g., `calculate_ic_sbs` and `calculate_ic_phenotype` scale with
N_tiles per cycle/round).

**2026-04-28 observations**:
| Rule | Apr 5 calibration | Well-scale observed peak |
|---|---|---|
| `calculate_ic_sbs` | 945 MB | **15.7 GB** (per cycle) |
| `calculate_ic_phenotype` | 2.5 GB | **210 GB** (~1300 tiles × 70 MB raw + working set) |

Iterating up on memory caps based on OOM events (the workaround we used) consumed
6 attempts × cluster compute before landing on values that didn't OOM.

**Suggestions**:

1. **Replace single-sample calibration with an efficiency-CSV aggregator.** Every
   brieflow run produces `logs/efficiency_*/efficiency_report_*.csv` containing per-job
   `MaxRSS_MB`. Walk all such CSVs, take worst-case observed peak per rule, apply a
   small overhead (1.5×), write to `mem_recommendations.json`. Self-correcting: every
   successful run feeds forward worst-case observations. Trivial to implement; the
   data already exists.

2. **Optional: per-rule scoring formula** for forward-prediction on new screens.
   `mem_mb = k_rule × total_input_size_MB + b_rule`, with constants learned from
   observations. Generalizes to new screens with different tile counts WITHOUT
   recalibration. Falls back to the `mem_recommendations.json` defaults if the formula
   isn't computable for a given rule.

3. **Plugin command idea**: `/brieflow-tune-memory` that runs the aggregator over the
   user's `logs/` and updates their `mem_recommendations.json` (or whatever the
   equivalent file is called in production analysis repos). Documented as a
   post-successful-run hygiene step.
