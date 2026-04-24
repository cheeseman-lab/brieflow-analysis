#!/usr/bin/env python3
"""
Speed optimization harness for brieflow.

Phase 1 — Speed search (tile tier):
  calibrate   — tile tier, generous resources. Measures MaxRSS + elapsed per rule.
  search      — run SEARCH_TRIALS (local, slurm-noarray, slurm-array variants),
                measure total wall time. This is the primary output.
  report      — ranked comparison of search trials.

Phase 2 — Memory + scale (well tier, run after finding best config):
  calibrate_well  — well tier for rules that scale with tile count.
  dag_overhead    — estimate DAG memory overhead from anchor rules.
  mem_report      — recommended mem_mb per rule with breakdown.
  scale_test      — run well tier with the best Phase 1 config; measure scaling.

Usage:
    python harness.py calibrate
    python harness.py search
    python harness.py report

    python harness.py calibrate_well
    python harness.py dag_overhead
    python harness.py mem_report
    python harness.py scale_test
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ANALYSIS_DIR = Path(__file__).parent.parent
HARNESS_DIR = Path(__file__).parent
RESULTS_DIR = HARNESS_DIR / "results"
BASE_PROFILE = ANALYSIS_DIR / "slurm" / "config.yaml"
TILE_CONFIG = "config/config_tile.yml"
WELL_CONFIG = "config/config_well.yml"
TILE_OUTPUT_DIR = ANALYSIS_DIR / "brieflow_output_tile"
WELL_OUTPUT_DIR = ANALYSIS_DIR / "brieflow_output_well"

RESULTS_DIR.mkdir(exist_ok=True)

AUTORESEARCH_DIR = HARNESS_DIR.parent / "autoresearch"
AUTORESEARCH_RESULTS = AUTORESEARCH_DIR / "results.tsv"
AUTORESEARCH_TRIAL = AUTORESEARCH_DIR / "next_trial.json"
WELL_RESULTS = AUTORESEARCH_DIR / "well_results.tsv"
WELL_RESULTS_HEADER = (
    "tag\tbackend\tlatency_wait\tarray_limit\tuse_tile_mem\tuse_well_mem\twall_time_min\tnotes\n"
)

# ---------------------------------------------------------------------------
# Search trials
#
# Each trial is a dict with:
#   backend       "local" | "slurm"
#   tag           short label for results
#
# slurm-specific:
#   use_arrays    bool — whether to enable --slurm-array-jobs=all
#   jobs          int  — max concurrent slurm jobs (snakemake --jobs)
#   array_limit   int  — max tasks per array (--slurm-array-limit)
#   cpus_per_task int  — CPUs per slurm job
#
# local-specific:
#   cores         int | "all"
# ---------------------------------------------------------------------------
SEARCH_TRIALS = [
    # --- Local backend ---
    {"backend": "local", "cores": "all", "tag": "local_all_cores"},

    # --- Slurm, no array jobs ---
    {"backend": "slurm", "use_arrays": False, "jobs": 200, "cpus_per_task": 1, "tag": "slurm_noarr_j200_c1"},
    {"backend": "slurm", "use_arrays": False, "jobs": 400, "cpus_per_task": 1, "tag": "slurm_noarr_j400_c1"},
    {"backend": "slurm", "use_arrays": False, "jobs": 600, "cpus_per_task": 1, "tag": "slurm_noarr_j600_c1"},

    # --- Slurm, array jobs, vary jobs + array_limit ---
    {"backend": "slurm", "use_arrays": True, "jobs": 200, "array_limit":  5, "cpus_per_task": 1, "tag": "slurm_arr_j200_al5_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 200, "array_limit": 10, "cpus_per_task": 1, "tag": "slurm_arr_j200_al10_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 400, "array_limit":  5, "cpus_per_task": 1, "tag": "slurm_arr_j400_al5_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 400, "array_limit": 10, "cpus_per_task": 1, "tag": "slurm_arr_j400_al10_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 400, "array_limit": 20, "cpus_per_task": 1, "tag": "slurm_arr_j400_al20_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 600, "array_limit": 10, "cpus_per_task": 1, "tag": "slurm_arr_j600_al10_c1"},
    {"backend": "slurm", "use_arrays": True, "jobs": 600, "array_limit": 20, "cpus_per_task": 1, "tag": "slurm_arr_j600_al20_c1"},

    # --- Slurm, array jobs, vary cpus_per_task ---
    {"backend": "slurm", "use_arrays": True, "jobs": 400, "array_limit": 10, "cpus_per_task": 2, "tag": "slurm_arr_j400_al10_c2"},
    {"backend": "slurm", "use_arrays": True, "jobs": 600, "array_limit": 10, "cpus_per_task": 2, "tag": "slurm_arr_j600_al10_c2"},
]

# ---------------------------------------------------------------------------
# Rule memory profile
# ---------------------------------------------------------------------------
RULE_MEMORY_PROFILE: dict[str, dict] = {
    # preprocess
    "convert_sbs":                  {"scales_with": "tile", "dag_sensitive": False},
    "convert_phenotype":            {"scales_with": "tile", "dag_sensitive": False},
    "extract_metadata_sbs":         {"scales_with": "tile", "dag_sensitive": True},
    "extract_metadata_phenotype":   {"scales_with": "tile", "dag_sensitive": True},
    "calculate_ic_sbs":             {"scales_with": "well", "dag_sensitive": True},
    "calculate_ic_phenotype":       {"scales_with": "well", "dag_sensitive": True},
    "combine_metadata_sbs":         {"scales_with": "well", "dag_sensitive": True},
    "combine_metadata_phenotype":   {"scales_with": "well", "dag_sensitive": True},
    # sbs per-tile
    "align_sbs":                    {"scales_with": "tile", "dag_sensitive": False},
    "log_filter":                   {"scales_with": "tile", "dag_sensitive": False},
    "compute_standard_deviation":   {"scales_with": "tile", "dag_sensitive": False},
    "find_peaks":                   {"scales_with": "tile", "dag_sensitive": False},
    "max_filter":                   {"scales_with": "tile", "dag_sensitive": False},
    "apply_ic_field_sbs":           {"scales_with": "tile", "dag_sensitive": False},
    "segment_sbs":                  {"scales_with": "tile", "dag_sensitive": False},
    "extract_bases":                {"scales_with": "tile", "dag_sensitive": False},
    "call_reads":                   {"scales_with": "tile", "dag_sensitive": False},
    "call_cells":                   {"scales_with": "tile", "dag_sensitive": False},
    "extract_sbs_info":             {"scales_with": "tile", "dag_sensitive": False},
    # sbs aggregation
    "combine_reads":                {"scales_with": "well", "dag_sensitive": True},
    "combine_cells":                {"scales_with": "well", "dag_sensitive": True},
    "combine_sbs_info":             {"scales_with": "well", "dag_sensitive": True},
    # phenotype per-tile
    "apply_ic_field_phenotype":     {"scales_with": "tile", "dag_sensitive": False},
    "align_phenotype":              {"scales_with": "tile", "dag_sensitive": False},
    "segment_phenotype":            {"scales_with": "tile", "dag_sensitive": False},
    "identify_cytoplasm":           {"scales_with": "tile", "dag_sensitive": False},
    "extract_phenotype_info":       {"scales_with": "tile", "dag_sensitive": False},
    # phenotype aggregation
    "combine_phenotype_info":       {"scales_with": "well", "dag_sensitive": True},
}

# Conservative memory for well-scaling rules at full baker scale.
# Based on well-tier calibration × 4x margin (scales with tiles/well).
# Tile-scaling rules use mem_recommendations.json values instead.
WELL_MEM_CONSERVATIVE: dict[str, int] = {
    "calculate_ic_sbs":           4_000,
    "calculate_ic_phenotype":    10_000,
    "combine_metadata_sbs":       1_500,
    "combine_metadata_phenotype": 1_500,
}

DAG_ANCHOR_RULES = ["extract_metadata_sbs", "extract_metadata_phenotype"]

MEM_MARGIN_TILE = 1.5
MEM_MARGIN_WELL = 1.5
DAG_MARGIN = 1.2


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def load_base_profile() -> dict:
    with open(BASE_PROFILE) as f:
        return yaml.safe_load(f)


def write_slurm_profile(trial_dir: Path, trial: dict, mem_recs: dict | None = None) -> Path:
    """Build and write a slurm profile for a given trial."""
    profile = load_base_profile()
    profile["jobs"] = trial.get("jobs", 400)

    cpus = trial.get("cpus_per_task", 1)
    set_res = dict(profile.get("set-resources", {}))
    for rule, meta in RULE_MEMORY_PROFILE.items():
        if meta["scales_with"] == "tile":
            if rule not in set_res:
                set_res[rule] = {}
            set_res[rule]["cpus_per_task"] = cpus
    profile["set-resources"] = set_res

    if mem_recs:
        profile = apply_mem_recommendations(profile, mem_recs)

    profile_dir = trial_dir / "slurm_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    with open(profile_dir / "config.yaml", "w") as f:
        yaml.dump(profile, f, default_flow_style=False)
    return profile_dir


def apply_mem_recommendations(profile: dict, recommendations: dict) -> dict:
    """Set mem_mb and runtime in set-resources from recommendations dict."""
    profile = profile.copy()
    set_res = dict(profile.get("set-resources", {}))
    for rule, data in recommendations.items():
        if rule not in set_res:
            set_res[rule] = {}
        set_res[rule]["mem_mb"] = data["mem_mb_recommended"]
    profile["set-resources"] = set_res
    return profile


# ---------------------------------------------------------------------------
# Run helper
# ---------------------------------------------------------------------------

def unlock_snakemake(config: str) -> None:
    """Run snakemake --unlock to clear any stale locks before a trial."""
    result = subprocess.run(
        ["snakemake", "--unlock",
         "--snakefile", str(ANALYSIS_DIR / "../brieflow/workflow/Snakefile"),
         "--configfile", config],
        cwd=ANALYSIS_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[harness] Snakemake unlocked.")
    else:
        # Not a fatal error — lock may not have existed
        pass


def run_flow(modules: list[str], config: str, trial: dict,
             trial_dir: Path, mem_recs: dict | None = None) -> tuple[Path, float, int]:
    """Run flow.sh for a trial and return (log_path, wall_time_seconds, exit_code).

    Caller is responsible for gating results-recording on exit_code == 0 (plus, where
    appropriate, a data-on-disk spot-check). flow.sh exits non-zero when snakemake
    errors out at any module — this is the authoritative success signal.
    """
    log_dir = ANALYSIS_DIR / "logs"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backend = trial.get("backend", "slurm")

    cmd = ["bash", "flow.sh", *modules, "--backend", backend,
           "--profile", "--configfile", config]

    if backend == "slurm":
        profile_dir = write_slurm_profile(trial_dir, trial, mem_recs=mem_recs)
        cmd += ["--slurm-profile", str(profile_dir)]
        cmd += ["--slurm-array-limit", str(trial.get('array_limit', 10))]
        if not trial.get("use_arrays", True):
            cmd += ["--no-arrays"]
        if "latency_wait" in trial:
            cmd += ["--latency-wait", str(trial["latency_wait"])]
        if "max_status_checks" in trial:
            cmd += ["--max-status-checks", str(trial["max_status_checks"])]
    else:
        cores = str(trial.get("cores", "all"))
        cmd += ["--cores", cores]

    print(f"\n[harness] Running: {' '.join(cmd)}")
    start = time.time()
    proc = subprocess.run(cmd, cwd=ANALYSIS_DIR)
    elapsed = time.time() - start

    if elapsed < 10:
        print(f"[harness] WARNING: trial completed in {elapsed:.1f}s — likely failed or hit a lock.")

    logs = sorted(log_dir.glob(f"*{ts[:13]}*.log"), key=lambda p: p.stat().st_mtime)
    log_path = logs[-1] if logs else Path("/dev/null")
    return log_path, elapsed, proc.returncode


# ---------------------------------------------------------------------------
# Parse efficiency report
# ---------------------------------------------------------------------------

def find_latest_efficiency_report() -> Path | None:
    candidates = []
    for p in (ANALYSIS_DIR / "logs").iterdir():
        if p.is_dir() and p.name.startswith("efficiency_"):
            for csv_f in p.glob("*.csv"):
                candidates.append(csv_f)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_efficiency_report(path: Path) -> dict[str, dict]:
    """Parse efficiency CSV into {rule: {max_rss_mb, elapsed_s, cpu_eff, mem_eff, count}}."""
    rules: dict[str, dict] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            rule = row.get("RuleName", "")
            rule = rule.split("_wildcards")[0].replace("rule_", "")
            if not rule:
                continue
            rss = float(row["MaxRSS_MB"]) if row.get("MaxRSS_MB") else 0
            el = float(row["Elapsed_sec"]) if row.get("Elapsed_sec") else 0
            cpu = float(row["CPU Efficiency (%)"]) if row.get("CPU Efficiency (%)") else 0
            mem = float(row["Memory Usage (%)"]) if row.get("Memory Usage (%)") else 0

            if rule not in rules:
                rules[rule] = {"max_rss_mb": 0, "max_elapsed_s": 0, "cpu_eff": [], "mem_eff": [], "count": 0}
            rules[rule]["max_rss_mb"] = max(rules[rule]["max_rss_mb"], rss)
            rules[rule]["max_elapsed_s"] = max(rules[rule]["max_elapsed_s"], el)
            if cpu: rules[rule]["cpu_eff"].append(cpu)
            if mem: rules[rule]["mem_eff"].append(mem)
            rules[rule]["count"] += 1

    for r in rules.values():
        r["mean_cpu_eff"] = sum(r["cpu_eff"]) / len(r["cpu_eff"]) if r["cpu_eff"] else 0
        r["mean_mem_eff"] = sum(r["mem_eff"]) / len(r["mem_eff"]) if r["mem_eff"] else 0
        del r["cpu_eff"], r["mem_eff"]

    return rules


# ---------------------------------------------------------------------------
# Phase 1 commands
# ---------------------------------------------------------------------------

def cmd_calibrate(args):
    """Calibrate tile-scaling rules on the tile tier."""
    print("[harness] === CALIBRATION (tile tier) ===")
    unlock_snakemake(TILE_CONFIG)
    trial_dir = RESULTS_DIR / "calibration_tile"
    trial_dir.mkdir(exist_ok=True)

    calibration_trial = {
        "backend": "slurm", "use_arrays": True, "jobs": 400,
        "array_limit": 10, "cpus_per_task": 1,
    }
    log_path, wall_time, exit_code = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=TILE_CONFIG,
        trial=calibration_trial,
        trial_dir=trial_dir,
    )

    time.sleep(30)
    report_path = find_latest_efficiency_report()
    if not report_path:
        print("[harness] ERROR: No efficiency report found.")
        sys.exit(1)

    data = parse_efficiency_report(report_path)
    result = {"wall_time_s": wall_time, "tier": "tile", "rules": data}

    out = RESULTS_DIR / "calibration_tile.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    _print_calibration_table(data, "tile")
    print(f"\n[harness] Saved to {out}")


def cmd_search(args):
    """
    Run SEARCH_TRIALS and measure total wall time per trial.

    Tests local vs slurm, array vs non-array, and varying concurrency params.
    Does not require calibrate to have run first — uses base slurm profile as-is.
    If mem_recommendations.json exists, memory limits are applied as a bonus.
    Resumes automatically if trials.jsonl already has completed trials.
    """
    print(f"[harness] === SPEED SEARCH ({len(SEARCH_TRIALS)} trials) ===")

    rec_path = RESULTS_DIR / "mem_recommendations.json"
    mem_recs = {}
    if rec_path.exists():
        with open(rec_path) as f:
            mem_recs = json.load(f)
        print("[harness] Found mem_recommendations.json — will apply to slurm profiles.")

    trials_log = RESULTS_DIR / "trials.jsonl"
    done_tags: set[str] = set()
    if trials_log.exists():
        with open(trials_log) as f:
            for line in f:
                try:
                    done_tags.add(json.loads(line.strip())["tag"])
                except Exception:
                    pass
        if done_tags:
            print(f"[harness] Resuming — {len(done_tags)} trials already done: {sorted(done_tags)}")

    for i, trial in enumerate(SEARCH_TRIALS):
        tag = trial["tag"]
        if tag in done_tags:
            print(f"[harness] Skipping {tag} (already done)")
            continue

        print(f"\n[harness] === Trial {i+1}/{len(SEARCH_TRIALS)}: {tag} ===")
        _print_trial_params(trial)

        # Wipe tile outputs so snakemake reruns the full pipeline for this trial.
        if TILE_OUTPUT_DIR.exists():
            print(f"[harness] Deleting {TILE_OUTPUT_DIR} for clean run...")
            shutil.rmtree(TILE_OUTPUT_DIR)

        # Unlock any stale snakemake locks before starting.
        unlock_snakemake(TILE_CONFIG)

        trial_dir = RESULTS_DIR / f"trial_{tag}"
        trial_dir.mkdir(exist_ok=True)

        log_path, wall_time, exit_code = run_flow(
            ["preprocess", "sbs", "phenotype"],
            config=TILE_CONFIG,
            trial=trial,
            trial_dir=trial_dir,
            mem_recs=mem_recs if mem_recs else None,
        )

        # Sanity check: a real tile run takes >60 seconds. Flag suspiciously fast runs.
        if wall_time < 60:
            print(f"[harness] ERROR: {tag} finished in {wall_time:.1f}s — skipping, not recording.")
            continue

        time.sleep(15)
        report_path = find_latest_efficiency_report()
        rule_data = parse_efficiency_report(report_path) if report_path else {}

        result = {
            "tag": tag,
            "trial": trial,
            "wall_time_s": wall_time,
            "wall_time_min": round(wall_time / 60, 1),
            "rules": rule_data,
        }

        with open(trials_log, "a") as f:
            f.write(json.dumps(result) + "\n")

        print(f"[harness] {tag}: {wall_time/60:.1f} min")

    print(f"\n[harness] Search complete.")
    cmd_report(args)


def cmd_report(args):
    """Ranked comparison of search trials by wall time."""
    trials_log = RESULTS_DIR / "trials.jsonl"
    if not trials_log.exists():
        print("[harness] No trials found. Run search first.")
        sys.exit(1)

    trials = []
    with open(trials_log) as f:
        for line in f:
            try:
                trials.append(json.loads(line.strip()))
            except Exception:
                pass
    trials.sort(key=lambda t: t["wall_time_s"])

    print(f"\n{'#':<3} {'Tag':<38} {'Backend':<8} {'Arrays':>6} {'Jobs':>5} {'ArrLim':>7} {'CPUs':>5} {'Min':>7}")
    print("-" * 85)
    for rank, t in enumerate(trials, 1):
        p = t.get("trial", {})
        backend = p.get("backend", "?")
        arrays = "yes" if p.get("use_arrays") else ("no" if backend == "slurm" else "-")
        jobs = str(p.get("jobs", "-")) if backend == "slurm" else "-"
        arr_lim = str(p.get("array_limit", "-")) if backend == "slurm" and p.get("use_arrays") else "-"
        cpus = str(p.get("cpus_per_task", "-")) if backend == "slurm" else str(p.get("cores", "-"))
        print(f"{rank:<3} {t['tag']:<38} {backend:<8} {arrays:>6} {jobs:>5} {arr_lim:>7} {cpus:>5} {t['wall_time_min']:>7.1f}")

    best = trials[0]
    print(f"\nBest: {best['tag']} — {best['wall_time_min']} min")
    _print_trial_params(best.get("trial", {}))


# ---------------------------------------------------------------------------
# Autoresearch command
# ---------------------------------------------------------------------------

AUTORESEARCH_RESULTS_HEADER = (
    "tag\tbackend\tlatency_wait\tmax_status_checks\tuse_mem_recs"
    "\tuse_arrays\tjobs\tarray_limit\tcpus\twall_time_min\tnotes\n"
)


def cmd_run_one_trial(args):
    """
    Run a single trial defined in autoresearch/next_trial.json.
    Appends result to autoresearch/results.tsv.
    Called autonomously by the autoresearch agent in a loop.
    """
    trial_json = Path(getattr(args, "trial_json", None) or AUTORESEARCH_TRIAL)
    if not trial_json.exists():
        print(f"[harness] ERROR: {trial_json} not found.")
        sys.exit(1)

    with open(trial_json) as f:
        trial = json.load(f)

    tag = trial.get("tag", "unnamed")
    backend = trial.get("backend", "slurm")

    # Skip if already recorded.
    if AUTORESEARCH_RESULTS.exists():
        with open(AUTORESEARCH_RESULTS) as f:
            for line in f:
                if line.startswith(tag + "\t"):
                    print(f"[harness] {tag} already in results — skipping.")
                    return

    print(f"\n[harness] === autoresearch trial: {tag} ===")
    _print_trial_params(trial)

    # Load mem recommendations if trial requests them.
    mem_recs: dict = {}
    if trial.get("use_mem_recommendations"):
        rec_path = RESULTS_DIR / "mem_recommendations.json"
        if rec_path.exists():
            with open(rec_path) as f:
                mem_recs = json.load(f)
            print("[harness] Applying mem_recommendations.")
        else:
            print("[harness] WARNING: use_mem_recommendations=true but mem_recommendations.json not found.")

    # Clean slate.
    if TILE_OUTPUT_DIR.exists():
        print(f"[harness] Deleting {TILE_OUTPUT_DIR}...")
        shutil.rmtree(TILE_OUTPUT_DIR)
    unlock_snakemake(TILE_CONFIG)

    trial_dir = RESULTS_DIR / f"autoresearch_{tag}"
    trial_dir.mkdir(exist_ok=True)

    log_path, wall_time, exit_code = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=TILE_CONFIG,
        trial=trial,
        trial_dir=trial_dir,
        mem_recs=mem_recs or None,
    )

    if wall_time < 60:
        print(f"[harness] ERROR: {tag} finished in {wall_time:.1f}s — not recording (likely failed).")
        sys.exit(1)

    # Scope is preprocess-only. flow.sh exits non-zero after the expected
    # MissingRuleException on all_sbs — so exit code alone doesn't discriminate
    # success from failure. The authoritative signal is the snakemake-emitted
    # `Finished jobid: 0 (Rule: all_preprocess)` marker. If it is absent, the
    # preprocess module did NOT complete cleanly and we must not record the trial.
    preprocess_ok = False
    if log_path.exists():
        try:
            with open(log_path) as lf:
                for line in lf:
                    if "Finished jobid: 0 (Rule: all_preprocess)" in line:
                        preprocess_ok = True
                        break
        except OSError:
            pass
    if not preprocess_ok:
        print(f"[harness] ERROR: {tag} — preprocess did not complete cleanly "
              f"(no `Finished jobid: 0 (Rule: all_preprocess)` in {log_path}). Not recording.")
        sys.exit(1)

    # Build result row.
    lw = str(trial.get("latency_wait", 10)) if backend == "slurm" else "N/A"
    msc = str(trial.get("max_status_checks", "default")) if backend == "slurm" else "N/A"
    use_mem = str(trial.get("use_mem_recommendations", False))
    arrays = str(trial.get("use_arrays", True)) if backend == "slurm" else "N/A"
    jobs = str(trial.get("jobs", "-")) if backend == "slurm" else "N/A"
    arr_lim = str(trial.get("array_limit", "-")) if backend == "slurm" else "N/A"
    cpus = str(trial.get("cpus_per_task", 1)) if backend == "slurm" else str(trial.get("cores", "all"))
    notes = trial.get("notes", "")

    row = "\t".join([tag, backend, lw, msc, use_mem, arrays, jobs, arr_lim, cpus,
                     f"{wall_time/60:.1f}", notes]) + "\n"

    if not AUTORESEARCH_RESULTS.exists():
        AUTORESEARCH_RESULTS.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTORESEARCH_RESULTS, "w") as f:
            f.write(AUTORESEARCH_RESULTS_HEADER)

    with open(AUTORESEARCH_RESULTS, "a") as f:
        f.write(row)

    print(f"[harness] {tag}: {wall_time/60:.1f} min — recorded.")


def cmd_autoresearch_report(args):
    """Print ranked autoresearch results."""
    if not AUTORESEARCH_RESULTS.exists():
        print("[harness] No autoresearch results yet.")
        return

    import csv as _csv
    rows = []
    with open(AUTORESEARCH_RESULTS) as f:
        for row in _csv.DictReader(f, delimiter="\t"):
            try:
                row["_min"] = float(row["wall_time_min"])
                rows.append(row)
            except (ValueError, KeyError):
                pass

    rows.sort(key=lambda r: r["_min"])
    print(f"\n{'#':<3} {'Tag':<40} {'Backend':<7} {'LW':>4} {'MSC':>5} {'Mem':>5} {'Arr':>5} {'Jobs':>5} {'AL':>4} {'Min':>6}")
    print("-" * 90)
    for i, r in enumerate(rows, 1):
        print(f"{i:<3} {r['tag']:<40} {r['backend']:<7} {r['latency_wait']:>4} "
              f"{r['max_status_checks']:>5} {r['use_mem_recs']:>5} {r['use_arrays']:>5} "
              f"{r['jobs']:>5} {r['array_limit']:>4} {r['wall_time_min']:>6}")

    if rows:
        best = rows[0]
        print(f"\nBest: {best['tag']} — {best['wall_time_min']} min")


def cmd_run_well_trial(args):
    """
    Run a single well-tier trial defined in a JSON file.
    Schema same as run_one_trial plus two extra boolean fields:
      use_tile_mem: apply mem_recommendations for tile-scaling rules
      use_well_mem: apply WELL_MEM_CONSERVATIVE for well-scaling rules
    Appends to autoresearch/well_results.tsv.
    """
    trial_json = Path(getattr(args, "trial_json", None) or AUTORESEARCH_TRIAL)
    if not trial_json.exists():
        print(f"[harness] ERROR: {trial_json} not found.")
        sys.exit(1)

    with open(trial_json) as f:
        trial = json.load(f)

    tag = trial.get("tag", "unnamed")

    if WELL_RESULTS.exists():
        with open(WELL_RESULTS) as f:
            for line in f:
                if line.startswith(tag + "\t"):
                    print(f"[harness] {tag} already in well_results — skipping.")
                    return

    print(f"\n[harness] === well trial: {tag} ===")
    _print_trial_params(trial)

    # Build mem_recs from tile and/or well sources.
    mem_recs: dict = {}
    if trial.get("use_tile_mem"):
        rec_path = RESULTS_DIR / "mem_recommendations.json"
        if rec_path.exists():
            with open(rec_path) as f:
                all_recs = json.load(f)
            well_dag_overhead = next(
                v["dag_overhead_mb"] for v in all_recs.values()
                if v.get("tier") == "well" and v.get("dag_overhead_mb", 0) > 0
            )
            mem_recs = {}
            for r, v in all_recs.items():
                if RULE_MEMORY_PROFILE.get(r, {}).get("scales_with") == "tile":
                    corrected_mb = round((v["obs_rss_mb"] + well_dag_overhead) * MEM_MARGIN_TILE)
                    mem_recs[r] = {**v, "mem_mb_recommended": corrected_mb}
            print(f"[harness] Applying well-corrected tile mem_recs (dag_overhead={well_dag_overhead:.0f}MB): {list(mem_recs)}")
        else:
            print("[harness] WARNING: use_tile_mem=true but mem_recommendations.json not found.")

    if trial.get("use_well_mem"):
        for rule, mb in WELL_MEM_CONSERVATIVE.items():
            mem_recs[rule] = {"mem_mb_recommended": mb}
        print(f"[harness] Applying conservative well mem for: {list(WELL_MEM_CONSERVATIVE)}")

    # Wipe well output for a clean run.
    if WELL_OUTPUT_DIR.exists():
        print(f"[harness] Deleting {WELL_OUTPUT_DIR}...")
        shutil.rmtree(WELL_OUTPUT_DIR)
    unlock_snakemake(WELL_CONFIG)

    trial_dir = RESULTS_DIR / f"well_trial_{tag}"
    trial_dir.mkdir(exist_ok=True)

    log_path, wall_time, exit_code = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=WELL_CONFIG,
        trial=trial,
        trial_dir=trial_dir,
        mem_recs=mem_recs or None,
    )

    if wall_time < 120:
        print(f"[harness] ERROR: {tag} finished in {wall_time:.1f}s — not recording (likely failed).")
        sys.exit(1)

    backend = trial.get("backend", "slurm")
    lw = str(trial.get("latency_wait", 10)) if backend == "slurm" else "N/A"
    al = str(trial.get("array_limit", 10)) if backend == "slurm" else "N/A"
    row = "\t".join([
        tag, backend, lw, al,
        str(trial.get("use_tile_mem", False)),
        str(trial.get("use_well_mem", False)),
        f"{wall_time/60:.1f}",
        trial.get("notes", ""),
    ]) + "\n"

    if not WELL_RESULTS.exists():
        WELL_RESULTS.parent.mkdir(parents=True, exist_ok=True)
        with open(WELL_RESULTS, "w") as f:
            f.write(WELL_RESULTS_HEADER)
    with open(WELL_RESULTS, "a") as f:
        f.write(row)

    print(f"[harness] {tag}: {wall_time/60:.1f} min — recorded to {WELL_RESULTS}")


def cmd_well_report(args):
    """Print well-tier results sorted by wall time."""
    if not WELL_RESULTS.exists():
        print("[harness] No well results yet. Run run_well_trial first.")
        return

    import csv as _csv
    rows = []
    with open(WELL_RESULTS) as f:
        for row in _csv.DictReader(f, delimiter="\t"):
            try:
                row["_min"] = float(row["wall_time_min"])
                rows.append(row)
            except (ValueError, KeyError):
                pass

    rows.sort(key=lambda r: r["_min"])
    print(f"\n{'#':<3} {'Tag':<35} {'LW':>4} {'AL':>4} {'TileMem':>8} {'WellMem':>8} {'Min':>6}")
    print("-" * 75)
    for i, r in enumerate(rows, 1):
        print(f"{i:<3} {r['tag']:<35} {r['latency_wait']:>4} {r['array_limit']:>4} "
              f"{r['use_tile_mem']:>8} {r['use_well_mem']:>8} {r['wall_time_min']:>6}")

    if rows:
        print(f"\nBest: {rows[0]['tag']} — {rows[0]['wall_time_min']} min")


# ---------------------------------------------------------------------------
# Phase 2 commands
# ---------------------------------------------------------------------------

def cmd_calibrate_well(args):
    """Calibrate well-scaling rules (calculate_ic, combine_*) on the well tier."""
    print("[harness] === CALIBRATION (well tier) ===")
    unlock_snakemake(WELL_CONFIG)
    trial_dir = RESULTS_DIR / "calibration_well"
    trial_dir.mkdir(exist_ok=True)

    calibration_trial = {
        "backend": "slurm", "use_arrays": True, "jobs": 400,
        "array_limit": 10, "cpus_per_task": 1,
    }
    log_path, wall_time, exit_code = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=WELL_CONFIG,
        trial=calibration_trial,
        trial_dir=trial_dir,
    )

    time.sleep(30)
    report_path = find_latest_efficiency_report()
    if not report_path:
        print("[harness] ERROR: No efficiency report found.")
        sys.exit(1)

    data = parse_efficiency_report(report_path)
    result = {"wall_time_s": wall_time, "tier": "well", "rules": data}

    out = RESULTS_DIR / "calibration_well.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    _print_calibration_table(data, "well")
    print(f"\n[harness] Saved to {out}")


def cmd_dag_overhead(args):
    """Estimate DAG memory overhead from anchor rules (requires tile + well calibration)."""
    tile_path = RESULTS_DIR / "calibration_tile.json"
    well_path = RESULTS_DIR / "calibration_well.json"

    missing = [str(p) for p in [tile_path, well_path] if not p.exists()]
    if missing:
        print(f"[harness] ERROR: Run calibrate and calibrate_well first. Missing: {missing}")
        sys.exit(1)

    with open(tile_path) as f:
        tile_data = json.load(f)["rules"]
    with open(well_path) as f:
        well_data = json.load(f)["rules"]

    print("\n[harness] === DAG OVERHEAD ESTIMATE ===")
    print("Anchor rules (constant work, different DAG sizes):")
    print(f"  Tile tier: ~150 jobs | Well tier: ~5000 jobs")

    overhead_estimates = {}
    for rule in DAG_ANCHOR_RULES:
        tile_rss = tile_data.get(rule, {}).get("max_rss_mb", 0)
        well_rss = well_data.get(rule, {}).get("max_rss_mb", 0)
        if tile_rss and well_rss:
            dag_delta = well_rss - tile_rss
            per_1k_jobs = dag_delta / (5000 - 150) * 1000
            overhead_estimates[rule] = {
                "tile_rss_mb": tile_rss, "well_rss_mb": well_rss,
                "dag_delta_mb": dag_delta, "per_1k_jobs_mb": per_1k_jobs,
            }
            print(f"\n  {rule}:")
            print(f"    tile {tile_rss:.0f} MB → well {well_rss:.0f} MB  "
                  f"(delta {dag_delta:.0f} MB, ~{per_1k_jobs:.1f} MB/1K jobs)")

    if overhead_estimates:
        mean_per_1k = sum(e["per_1k_jobs_mb"] for e in overhead_estimates.values()) / len(overhead_estimates)
        mean_tile_base = sum(e["tile_rss_mb"] for e in overhead_estimates.values()) / len(overhead_estimates)
        result = {
            "tile_dag_overhead_mb": mean_tile_base,
            "per_1k_jobs_mb": mean_per_1k,
            "anchor_rules": overhead_estimates,
            "full_baker_dag_overhead_mb": mean_tile_base + mean_per_1k * 26,
        }
        out = RESULTS_DIR / "dag_overhead.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n  Mean: {mean_per_1k:.1f} MB/1K jobs")
        print(f"  Full baker (~26K jobs) DAG overhead: {result['full_baker_dag_overhead_mb']:.0f} MB")
        print(f"[harness] Saved to {out}")


def cmd_mem_report(args):
    """Print and save recommended mem_mb per rule (requires tile calibration; well optional)."""
    tile_path = RESULTS_DIR / "calibration_tile.json"
    if not tile_path.exists():
        print("[harness] ERROR: Run calibrate first.")
        sys.exit(1)

    with open(tile_path) as f:
        tile_data = json.load(f)["rules"]

    well_data: dict = {}
    dag_overhead_mb, per_1k_mb = 0.0, 0.0

    well_path = RESULTS_DIR / "calibration_well.json"
    if well_path.exists():
        with open(well_path) as f:
            well_data = json.load(f)["rules"]

    dag_path = RESULTS_DIR / "dag_overhead.json"
    if dag_path.exists():
        with open(dag_path) as f:
            dag_info = json.load(f)
        dag_overhead_mb = dag_info["tile_dag_overhead_mb"]
        per_1k_mb = dag_info["per_1k_jobs_mb"]

    print(f"\n{'Rule':<35} {'Tier':>5} {'ObsRSS':>8} {'DAGoh':>7} {'RuleMem':>9} {'Margin':>7} {'Rec MB':>8}")
    print("-" * 82)

    recommendations: dict = {}
    for rule, meta in sorted(RULE_MEMORY_PROFILE.items()):
        tier = meta["scales_with"]
        source = tile_data if tier == "tile" else well_data
        if rule not in source:
            continue

        obs_rss = source[rule]["max_rss_mb"]
        dag_oh = dag_overhead_mb if meta["dag_sensitive"] else 0.0
        rule_mem = max(obs_rss - dag_oh, obs_rss * 0.5)
        margin = MEM_MARGIN_TILE if tier == "tile" else MEM_MARGIN_WELL
        rec = int(rule_mem * margin) + int(dag_oh * DAG_MARGIN) + 50
        recommendations[rule] = {
            "tier": tier, "obs_rss_mb": obs_rss, "dag_overhead_mb": dag_oh,
            "rule_mem_mb": rule_mem, "mem_mb_recommended": rec,
        }
        print(f"{rule:<35} {tier:>5} {obs_rss:>8.0f} {dag_oh:>7.0f} {rule_mem:>9.0f} {margin:>7.1f}x {rec:>8}")

    out = RESULTS_DIR / "mem_recommendations.json"
    with open(out, "w") as f:
        json.dump(recommendations, f, indent=2)
    print(f"\n[harness] Saved to {out}")
    if per_1k_mb:
        print(f"DAG overhead: ~{per_1k_mb:.1f} MB/1K jobs → ~{per_1k_mb*26:.0f} MB at full baker scale")


def cmd_scale_test(args):
    """
    Run the well tier with the best config from Phase 1 search.
    Measures how wall time scales from tile (~150 jobs) to well (~5000 jobs).
    """
    trials_log = RESULTS_DIR / "trials.jsonl"
    if not trials_log.exists():
        print("[harness] ERROR: Run search first (Phase 1).")
        sys.exit(1)

    trials = []
    with open(trials_log) as f:
        for line in f:
            try:
                trials.append(json.loads(line.strip()))
            except Exception:
                pass

    best = min(trials, key=lambda t: t["wall_time_s"])
    best_trial = best["trial"]
    print(f"\n[harness] === SCALE TEST (well tier) ===")
    print(f"Using best config from Phase 1: {best['tag']} ({best['wall_time_min']} min on tile)")
    _print_trial_params(best_trial)

    trial_dir = RESULTS_DIR / "scale_test_well"
    trial_dir.mkdir(exist_ok=True)

    log_path, wall_time, exit_code = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=WELL_CONFIG,
        trial=best_trial,
        trial_dir=trial_dir,
    )

    result = {
        "tag": "scale_test_well",
        "based_on": best["tag"],
        "trial": best_trial,
        "wall_time_s": wall_time,
        "wall_time_min": round(wall_time / 60, 1),
    }
    out = RESULTS_DIR / "scale_test_well.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    tile_time = best["wall_time_min"]
    print(f"\n  Tile tier:  {tile_time:.1f} min  (~150 jobs)")
    print(f"  Well tier:  {wall_time/60:.1f} min  (~5000 jobs)")
    if tile_time > 0:
        print(f"  Scale factor: {(wall_time/60) / tile_time:.1f}x")
    print(f"[harness] Saved to {out}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_calibration_table(data: dict, tier: str):
    print(f"\n{'Rule':<35} {'MaxRSS MB':>10} {'CPU%':>7} {'Elapsed s':>10} {'N':>5}")
    print("-" * 70)
    for rule, d in sorted(data.items(), key=lambda x: -x[1]["max_rss_mb"]):
        print(f"{rule:<35} {d['max_rss_mb']:>10.0f} {d['mean_cpu_eff']:>7.1f}% "
              f"{d['max_elapsed_s']:>10.1f} {d['count']:>5}")


# ---------------------------------------------------------------------------
# Diagnose: sacct pending-time decomposition
# ---------------------------------------------------------------------------

def _parse_sacct_ts(s: str):
    """Parse sacct timestamp; return None for 'Unknown' / empty."""
    if not s or s in ("Unknown", "None"):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


def _load_efficiency_jobids(csv_path: Path) -> dict[str, str]:
    """Map slurm parent JobID (e.g. '7524699_2') → rule name from efficiency CSV.

    Efficiency CSV rows carry inner steps like '7524699_2.0' — the parent array
    task is everything before the trailing '.N'. sacct's scheduler-side fields
    (Submit/Eligible/Start) live on the parent, not the inner python step.
    """
    mapping: dict[str, str] = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            raw = row.get("JobID", "")
            rule = row.get("RuleName", "").split("_wildcards")[0].replace("rule_", "")
            if not raw or not rule:
                continue
            parent = raw.rsplit(".", 1)[0] if "." in raw.rsplit("_", 1)[-1] else raw
            mapping.setdefault(parent, rule)
    return mapping


def _pull_sacct(jobids: list[str]) -> list[dict]:
    """sacct -j <ids> → list of dicts with parent-array-task rows only."""
    if not jobids:
        return []
    rows: list[dict] = []
    # Chunk ids (sacct handles lots but stay safe with long command lines).
    for i in range(0, len(jobids), 500):
        chunk = jobids[i:i + 500]
        cmd = ["sacct", "--parsable2", "--noheader",
               "--format=JobID,Submit,Eligible,Start,End,State,ExitCode",
               "-j", ",".join(chunk)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) < 7:
                continue
            jid = parts[0]
            # Parent array task only — skip .batch, .extern, .0, etc.
            if "." in jid.rsplit("_", 1)[-1]:
                continue
            rows.append({
                "JobID":    jid,
                "Submit":   _parse_sacct_ts(parts[1]),
                "Eligible": _parse_sacct_ts(parts[2]),
                "Start":    _parse_sacct_ts(parts[3]),
                "End":      _parse_sacct_ts(parts[4]),
                "State":    parts[5],
                "ExitCode": parts[6],
            })
    return rows


def cmd_diagnose(args):
    """Decompose wall time into per-rule held/queued/compute via sacct.

    Intervals (sacct timestamps on the PARENT array task):
      held    = Eligible - Submit  (scheduler-held: deps, MaxSubmitJobs, rate limit)
      queued  = Start - Eligible   (no free slot at the requested resources)
      compute = End - Start        (actual run time incl. mini-snakemake overhead)

    Note: with the slurm plugin 2.6.0 array mechanism, each parent array task runs a
    mini-snakemake that processes multiple rule invocations serially. So `n` is the
    number of array tasks per rule, not tiles; `compute` is total array-task runtime
    (sum of the inner invocations plus mini-snakemake overhead), not per-tile time.
    For per-tile numbers see `calibration_tile.json`. Use this command to answer
    "where did wall time go between scheduler, queue, and compute?" at the whole-rule
    level, not to tune single-tile performance.
    """
    csv_path = Path(args.csv) if args.csv else find_latest_efficiency_report()
    if csv_path is None or not csv_path.exists():
        print("[harness] ERROR: no efficiency CSV found. Run with --csv PATH or run a trial first.")
        sys.exit(1)

    tag = args.tag or ""
    workflow_uuid = csv_path.stem.replace("efficiency_report_brieflow_", "")

    print(f"[harness] === diagnose" + (f": {tag}" if tag else "") + " ===")
    print(f"[harness] Source CSV:     {csv_path}")
    print(f"[harness] Workflow UUID:  {workflow_uuid}")

    jobid_to_rule = _load_efficiency_jobids(csv_path)
    if not jobid_to_rule:
        print("[harness] ERROR: efficiency CSV has no JobID/RuleName rows.")
        sys.exit(1)

    jobids = sorted(jobid_to_rule.keys())
    print(f"[harness] Querying sacct for {len(jobids)} parent array tasks...")
    sacct_rows = _pull_sacct(jobids)

    per_rule: dict[str, dict] = {}
    for r in sacct_rows:
        rule = jobid_to_rule.get(r["JobID"])
        if not rule:
            continue
        sub, el, st, en = r["Submit"], r["Eligible"], r["Start"], r["End"]
        if not (sub and el and st and en):
            continue
        held    = max(0.0, (el - sub).total_seconds())
        queued  = max(0.0, (st - el).total_seconds())
        compute = max(0.0, (en - st).total_seconds())
        d = per_rule.setdefault(rule, {
            "n": 0, "held": [], "queued": [], "compute": [],
            "states": {}, "earliest_submit": sub, "latest_end": en,
        })
        d["n"] += 1
        d["held"].append(held)
        d["queued"].append(queued)
        d["compute"].append(compute)
        d["states"][r["State"]] = d["states"].get(r["State"], 0) + 1
        if sub < d["earliest_submit"]:
            d["earliest_submit"] = sub
        if en > d["latest_end"]:
            d["latest_end"] = en

    if not per_rule:
        print("[harness] ERROR: no jobs with full Submit/Eligible/Start/End — nothing to decompose.")
        sys.exit(1)

    # Wall envelope (for % breakdowns).
    wall_start = min(d["earliest_submit"] for d in per_rule.values())
    wall_end   = max(d["latest_end"]      for d in per_rule.values())
    wall_s     = max(1.0, (wall_end - wall_start).total_seconds())

    # ----- Report header -----
    n_jobs_total = sum(d["n"] for d in per_rule.values())
    print()
    print("=" * 84)
    print(f"  Wall envelope: {wall_start.strftime('%H:%M:%S')} → "
          f"{wall_end.strftime('%H:%M:%S')}  "
          f"({wall_s/60:.2f} min, {int(wall_s)} s)")
    print(f"  Jobs analyzed: {n_jobs_total} parent array tasks across {len(per_rule)} rules")
    print("=" * 84)
    print("""
Legend (all times are per parent array task; sums across all tasks in the run):
  held      = sacct Eligible - Submit  — scheduler held (deps, MaxSubmitJobs, rate-limit)
  queued    = sacct Start    - Eligible — waiting for a free slot
  compute   = sacct End      - Start    — actual run (incl. mini-snakemake wrapper)
  p50/p95   = percentiles of that bucket, per rule
  %h/%q/%c  = this rule's time split across the three buckets (sums to 100% per row)
""")
    print(f"{'Rule':<30} {'n':>4}  {'held p50/p95':>13}  {'queued p50/p95':>15}  "
          f"{'compute p50/p95':>16}  {'%h':>4} {'%q':>4} {'%c':>4}")
    print("-" * 98)

    summary = {}
    rows_sorted = sorted(per_rule.items(),
                         key=lambda kv: -(sum(kv[1]["held"]) + sum(kv[1]["queued"])))
    for rule, d in rows_sorted:
        h50, h95 = _pct(d["held"], 50),    _pct(d["held"], 95)
        q50, q95 = _pct(d["queued"], 50),  _pct(d["queued"], 95)
        c50, c95 = _pct(d["compute"], 50), _pct(d["compute"], 95)
        tot_h, tot_q, tot_c = sum(d["held"]), sum(d["queued"]), sum(d["compute"])
        total = max(1.0, tot_h + tot_q + tot_c)
        print(f"{rule:<30} {d['n']:>4}  "
              f"{h50:>5.0f}/{h95:<7.0f}  "
              f"{q50:>6.0f}/{q95:<8.0f}  "
              f"{c50:>7.0f}/{c95:<8.0f}  "
              f"{100*tot_h/total:>3.0f}% {100*tot_q/total:>3.0f}% {100*tot_c/total:>3.0f}%")
        summary[rule] = {
            "n": d["n"],
            "held_s":    {"p50": h50, "p95": h95, "sum": tot_h},
            "queued_s":  {"p50": q50, "p95": q95, "sum": tot_q},
            "compute_s": {"p50": c50, "p95": c95, "sum": tot_c},
            "states": d["states"],
        }

    # ----- Summary + verdict -----
    grand_h = sum(s["held_s"]["sum"]    for s in summary.values())
    grand_q = sum(s["queued_s"]["sum"]  for s in summary.values())
    grand_c = sum(s["compute_s"]["sum"] for s in summary.values())
    grand_total = max(1.0, grand_h + grand_q + grand_c)

    # Effective parallelism: how much the cluster actually overlapped work.
    # grand_c / wall_s > 1 means multiple compute-seconds happened per wall-second.
    eff_parallelism = grand_c / wall_s

    # Verdict heuristic (thresholds are rule-of-thumb, not strict).
    pct_h = 100 * grand_h / grand_total
    pct_q = 100 * grand_q / grand_total
    pct_c = 100 * grand_c / grand_total
    if pct_c >= 80:
        verdict = "COMPUTE-BOUND — scheduler is not the bottleneck at this scale"
    elif pct_q >= 40:
        verdict = "QUEUE-BOUND — waiting for slots dominates; likely capped by concurrent-slot limits"
    elif pct_h >= 40:
        verdict = "SCHEDULER-HELD — long Submit→Eligible gaps; check MaxSubmitJobs and rate-limit"
    else:
        verdict = "MIXED — no single bucket dominates"

    print()
    print("=" * 84)
    print("  Total job-seconds across all jobs (NOT wall time — these are summed):")
    print(f"    held:    {grand_h:>7.0f} s   ({grand_h/60:>5.1f} min)   {pct_h:>4.1f}%")
    print(f"    queued:  {grand_q:>7.0f} s   ({grand_q/60:>5.1f} min)   {pct_q:>4.1f}%")
    print(f"    compute: {grand_c:>7.0f} s   ({grand_c/60:>5.1f} min)   {pct_c:>4.1f}%")
    print()
    print(f"  Wall time:              {wall_s/60:>5.2f} min ({int(wall_s)} s)")
    print(f"  Effective parallelism:  {eff_parallelism:>5.2f}x  "
          f"(compute-sec / wall-sec — how much work overlapped)")
    print()
    print(f"  Verdict: {verdict}")
    print("=" * 84)

    # ----- JSON output -----
    out_name = f"diagnose_{tag}.json" if tag else f"diagnose_{workflow_uuid}.json"
    out = RESULTS_DIR / out_name
    with open(out, "w") as f:
        json.dump({
            "tag":             tag or None,
            "workflow_uuid":   workflow_uuid,
            "source_csv":      str(csv_path),
            "wall_start":      wall_start.isoformat(),
            "wall_end":        wall_end.isoformat(),
            "wall_s":          wall_s,
            "n_jobs_analyzed": n_jobs_total,
            "grand": {
                "held_s":    grand_h,
                "queued_s":  grand_q,
                "compute_s": grand_c,
                "pct_held":    pct_h,
                "pct_queued":  pct_q,
                "pct_compute": pct_c,
            },
            "effective_parallelism": eff_parallelism,
            "verdict":               verdict,
            "per_rule":              summary,
            "schema_version": 1,
            "_notes": (
                "All buckets are summed across parent array tasks. "
                "`compute_s` is total array-task runtime (multiple tiles per task), "
                "not per-tile time — see calibration_tile.json for per-tile. "
                "Intervals come from sacct: held=Eligible-Submit, queued=Start-Eligible, "
                "compute=End-Start."
            ),
        }, f, indent=2, default=str)
    print(f"\n[harness] JSON report: {out}")


def cmd_repeat_trial(args):
    """Run the same trial config N times sequentially on tile tier.

    Use case: verify tracking / gather a noise-band on a single config.
    Reads the trial params from the given JSON (default: autoresearch/next_trial.json),
    generates tags `<base_tag>_N1`, `_N2`, ..., and runs each via cmd_run_one_trial so
    results land in autoresearch/results.tsv with the normal success-gating.

    Safety: aborts if any snakemake process is alive (only one at a time).
    After each run, invokes diagnose on the efficiency CSV.
    """
    trial_json = Path(args.trial_json or AUTORESEARCH_TRIAL)
    if not trial_json.exists():
        print(f"[harness] ERROR: {trial_json} not found.")
        sys.exit(1)
    with open(trial_json) as f:
        base_trial = json.load(f)
    base_tag = args.base_tag or base_trial.get("tag", "repeat")
    n = args.n

    def _any_snakemake_alive() -> bool:
        r = subprocess.run(
            ["pgrep", "-u", os.environ.get("USER", ""), "-f", "snakemake"],
            capture_output=True, text=True,
        )
        return bool(r.stdout.strip())

    print(f"[harness] === repeat_trial: {n}× {base_tag} ===")
    for i in range(1, n + 1):
        tag = f"{base_tag}_N{i}"
        print(f"\n[harness] --- trial {i}/{n}: {tag} ---")

        if _any_snakemake_alive():
            print("[harness] ABORT: another snakemake process is alive. Only one at a time.")
            sys.exit(1)

        trial = {**base_trial, "tag": tag,
                 "notes": f"{base_trial.get('notes', '')} [repeat {i}/{n} of {base_tag}]"}
        with open(AUTORESEARCH_TRIAL, "w") as f:
            json.dump(trial, f, indent=2)

        # Call cmd_run_one_trial via args shim — preserves the success-gating path.
        class _A:  # minimal args carrier
            trial_json = str(AUTORESEARCH_TRIAL)
        try:
            cmd_run_one_trial(_A())
        except SystemExit as e:
            if e.code:
                print(f"[harness] trial {i}/{n} FAILED (exit {e.code}) — aborting repeat loop.")
                sys.exit(e.code)

        # Sanity: no lingering snakemake after the trial.
        if _any_snakemake_alive():
            print("[harness] ABORT: snakemake still alive after trial. Investigate before continuing.")
            sys.exit(1)

        # Diagnose: sacct decomposition for this trial's efficiency CSV.
        print(f"\n[harness] --- diagnose for {tag} ---")
        class _D:
            csv = None
        try:
            cmd_diagnose(_D())
        except SystemExit:
            print(f"[harness] diagnose failed for {tag} — continuing to next trial.")

    print(f"\n[harness] === repeat_trial complete: {n}/{n} ===")


def _print_trial_params(trial: dict):
    backend = trial.get("backend", "?")
    if backend == "slurm":
        arrays = "yes" if trial.get("use_arrays") else "no"
        print(f"  backend=slurm  arrays={arrays}  jobs={trial.get('jobs', '?')}  "
              f"array_limit={trial.get('array_limit', '-')}  cpus_per_task={trial.get('cpus_per_task', 1)}")
    else:
        print(f"  backend=local  cores={trial.get('cores', 'all')}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Brieflow speed harness")
    sub = parser.add_subparsers(dest="command")

    # Phase 1
    sub.add_parser("calibrate",  help="[Phase 1] Tile tier: measure MaxRSS/elapsed per rule")
    sub.add_parser("search",     help="[Phase 1] Run all SEARCH_TRIALS, measure wall time")
    sub.add_parser("report",     help="[Phase 1] Ranked comparison of search trials")

    # Phase 2
    sub.add_parser("calibrate_well", help="[Phase 2] Well tier: measure well-scaling rules")
    sub.add_parser("dag_overhead",   help="[Phase 2] Estimate DAG memory overhead")
    sub.add_parser("mem_report",     help="[Phase 2] Recommended mem_mb per rule")
    sub.add_parser("scale_test",     help="[Phase 2] Run well tier with best Phase 1 config")

    # Autoresearch
    ar = sub.add_parser("run_one_trial", help="[Autoresearch] Run next_trial.json, append to autoresearch/results.tsv")
    ar.add_argument("--trial-json", default=None, help="Path to trial JSON (default: autoresearch/next_trial.json)")
    sub.add_parser("ar_report", help="[Autoresearch] Ranked autoresearch results")

    # Well-tier validation
    wt = sub.add_parser("run_well_trial", help="[Well] Run a trial JSON on well tier, append to well_results.tsv")
    wt.add_argument("--trial-json", default=None, help="Path to trial JSON")
    sub.add_parser("well_report", help="[Well] Ranked well-tier results")

    # Diagnose
    dg = sub.add_parser("diagnose", help="[Diagnose] sacct decomposition: per-rule held/queued/compute")
    dg.add_argument("--csv", default=None, help="Efficiency CSV path (default: latest)")
    dg.add_argument("--tag", default=None, help="Trial tag; output goes to diagnose_<tag>.json (default: uses workflow UUID)")

    # Repeat trial (N sequential runs of the same config)
    rt = sub.add_parser("repeat_trial", help="[Verify] Run the same trial config N times sequentially")
    rt.add_argument("-n", type=int, default=5, help="Number of repeats (default: 5)")
    rt.add_argument("--trial-json", default=None, help="Base trial JSON (default: autoresearch/next_trial.json)")
    rt.add_argument("--base-tag", default=None, help="Base tag; iterations become <base>_N1.._Nn (default: use trial.tag)")

    args = parser.parse_args()
    dispatch = {
        "calibrate":      cmd_calibrate,
        "search":         cmd_search,
        "report":         cmd_report,
        "calibrate_well": cmd_calibrate_well,
        "dag_overhead":   cmd_dag_overhead,
        "mem_report":     cmd_mem_report,
        "scale_test":     cmd_scale_test,
        "run_one_trial":  cmd_run_one_trial,
        "ar_report":      cmd_autoresearch_report,
        "run_well_trial": cmd_run_well_trial,
        "well_report":    cmd_well_report,
        "diagnose":       cmd_diagnose,
        "repeat_trial":   cmd_repeat_trial,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
