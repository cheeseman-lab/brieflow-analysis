# results.tsv reliability note

**Pre-2026-04-28 rows in `results.tsv` are unreliable for any conclusion about wall time
or parameter ranking.**

Why: prior to commit `77f8daa` (2026-04-28), `cmd_run_one_trial` recorded any run with
`wall_time > 60s` as a successful trial. There was no success-gating. As a result:

- Runs that hit `MissingOutputException` (NFS attribute-cache propagation > `latency_wait`)
  recorded the wall time at which snakemake bailed out, not the wall time of a complete
  preprocess. Snakemake's failure-cleanup actively deletes "incomplete" output files
  that DID land but weren't visible to its `stat()` check in time, so partial-failure
  trials are also data-loss events that left output trees inconsistent.
- Runs that hit OOM kills on `convert_sbs` (`mem_mb=451` cap from the 1.5× margin) also
  bailed early but recorded the partial wall time.
- Plugin-reporting bugs (sacct COMPLETED, output on disk, but parent flagged as FAILED)
  also caused early termination + partial timing.

Concretely, the historical "winner" `slurm_arr_j400_al20_lat5_mem` recorded a
**3.4–3.9 min** wall-time distribution. Under the success-gated harness on the same
config the same run takes **~6.10 min** (sacct envelope) when it actually completes.
The historical numbers were **~1.8× underestimates**, and the parameter rankings derived
from them (e.g., "lat=5 is the sweet spot", "al=15 might be a sweet spot") cannot be
trusted as comparisons because each row independently underestimated by an unknown amount
depending on the failure pattern in that specific run.

What's still usable from pre-2026-04-28 data:
- **Per-job RSS measurements in `harness/results/calibration_*.json`** — these are
  per-job sacct readings, not run-level wall times, and so are unaffected by the
  tracking bug. The 4× margin in `mem_recommendations.json` is built on these.
- **Per-job efficiency reports** in `logs/efficiency_*.log/` — same reason.
- The fact that **arrays beat no-arrays** by ~2× is robust because both modes were
  similarly affected by the tracking bug; the relative comparison is preserved even
  when absolute wall times are wrong. (Confirmed 2026-04-28: 6.10 min arrays vs
  11.18 min no-arrays under the gated harness.)

What's NOT usable:
- Any specific wall-time number from rows tagged before `winner_4x_lat30`.
- Any claim that a particular `latency_wait`, `array_limit`, or `max_status_checks`
  value beats another by a few tenths of a minute. These differences are within the
  underestimate band of the broken tracking.
- The notes column claiming things like "best params so far at 3.4 min" — those notes
  reflected the broken metric.

Going forward, only rows tagged from `winner_4x_lat30` onward (recorded with the
preprocess-completion gate) are reliable.
