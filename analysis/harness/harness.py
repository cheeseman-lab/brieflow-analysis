#!/usr/bin/env python3
"""
Speed optimization harness for brieflow.

Phases:
  calibrate       — tile tier, generous resources. Measures MaxRSS + elapsed
                    for per-tile rules. Also measures DAG overhead via a
                    lightweight constant rule run on both tier sizes.
  calibrate_well  — well tier for rules that scale with tile count
                    (calculate_ic, combine_*). Requires calibrate first.
  dag_overhead    — estimate pure snakemake DAG memory by comparing a
                    constant rule (extract_metadata) on tile vs well tier.
  mem_report      — print recommended mem_mb per rule with breakdown:
                    rule_memory vs dag_overhead vs safety_margin.
  search          — grid search over cpus_per_task, --jobs, --slurm-array-limit
                    using calibrated memory values. Tile tier only.
  report          — ranked comparison of search trials.

Usage:
    python harness.py calibrate
    python harness.py calibrate_well
    python harness.py dag_overhead
    python harness.py mem_report
    python harness.py search
    python harness.py report
"""

import argparse
import csv
import json
import os
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

RESULTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Rule memory profile
# ---------------------------------------------------------------------------
# scales_with: "tile"  — memory is roughly constant per job regardless of
#                        how many tiles are in the workflow
# scales_with: "well"  — memory grows with tile count (aggregation rules);
#                        must calibrate on well tier
# dag_sensitive: True  — this rule's observed MaxRSS includes significant
#                        snakemake DAG overhead; apply dag_overhead correction
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

# Rules used as the "constant rule" anchor for DAG overhead measurement.
# extract_metadata runs once per well regardless of tile count — same work,
# different DAG sizes.
DAG_ANCHOR_RULES = ["extract_metadata_sbs", "extract_metadata_phenotype"]

# Memory safety margins
MEM_MARGIN_TILE = 1.5   # for per-tile rules
MEM_MARGIN_WELL = 1.5   # for well-scaling rules
DAG_MARGIN = 1.2        # extra buffer on top of estimated DAG overhead
RUNTIME_MARGIN = 2.0


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def load_base_profile() -> dict:
    with open(BASE_PROFILE) as f:
        return yaml.safe_load(f)


def write_trial_profile(trial_dir: Path, profile: dict) -> Path:
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
        set_res[rule]["runtime"] = data["runtime_recommended"]
    profile["set-resources"] = set_res
    return profile


def apply_search_params(profile: dict, cpus_per_task: int) -> dict:
    """Apply cpus_per_task to all tile-scaling rules."""
    profile = profile.copy()
    set_res = dict(profile.get("set-resources", {}))
    for rule, meta in RULE_MEMORY_PROFILE.items():
        if meta["scales_with"] == "tile":
            if rule not in set_res:
                set_res[rule] = {}
            set_res[rule]["cpus_per_task"] = cpus_per_task
    profile["set-resources"] = set_res
    return profile


# ---------------------------------------------------------------------------
# Run helper
# ---------------------------------------------------------------------------

def run_flow(modules: list[str], config: str, profile_dir: Path,
             trial_name: str, extra_flags: list[str] | None = None) -> tuple[Path, float]:
    """Run flow.sh --profile and return (log_path, wall_time_seconds)."""
    log_dir = ANALYSIS_DIR / "logs"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    cmd = [
        "bash", "flow.sh",
        *modules,
        "--backend", "slurm",
        "--profile",
        "--configfile", config,
        "--slurm-profile", str(profile_dir),
    ]
    if extra_flags:
        cmd.extend(extra_flags)

    print(f"\n[harness] Running: {' '.join(cmd)}")
    start = time.time()
    subprocess.run(cmd, cwd=ANALYSIS_DIR)
    elapsed = time.time() - start

    logs = sorted(log_dir.glob(f"*{ts[:13]}*.log"), key=lambda p: p.stat().st_mtime)
    log_path = logs[-1] if logs else Path("/dev/null")
    return log_path, elapsed


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

    # Flatten lists to means
    for r in rules.values():
        r["mean_cpu_eff"] = sum(r["cpu_eff"]) / len(r["cpu_eff"]) if r["cpu_eff"] else 0
        r["mean_mem_eff"] = sum(r["mem_eff"]) / len(r["mem_eff"]) if r["mem_eff"] else 0
        del r["cpu_eff"], r["mem_eff"]

    return rules


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_calibrate(args):
    """Calibrate tile-scaling rules."""
    print("[harness] === CALIBRATION (tile tier) ===")
    profile = load_base_profile()
    trial_dir = RESULTS_DIR / "calibration_tile"
    trial_dir.mkdir(exist_ok=True)
    profile_dir = write_trial_profile(trial_dir, profile)

    log_path, wall_time = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=TILE_CONFIG,
        profile_dir=profile_dir,
        trial_name="calibration_tile",
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


def cmd_calibrate_well(args):
    """Calibrate well-scaling rules (calculate_ic, combine_*)."""
    print("[harness] === CALIBRATION (well tier) ===")
    profile = load_base_profile()
    trial_dir = RESULTS_DIR / "calibration_well"
    trial_dir.mkdir(exist_ok=True)
    profile_dir = write_trial_profile(trial_dir, profile)

    log_path, wall_time = run_flow(
        ["preprocess", "sbs", "phenotype"],
        config=WELL_CONFIG,
        profile_dir=profile_dir,
        trial_name="calibration_well",
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
    """
    Estimate DAG memory overhead by comparing a constant rule on tile vs well.

    extract_metadata_sbs runs once per well in both tiers — same actual work,
    but snakemake's internal DAG is larger on the well tier (more total jobs).
    The MaxRSS difference between tiers is attributable to DAG overhead scaling.

    tile_dag_overhead  = rule MaxRSS on tile tier  (small DAG,  ~150 jobs)
    well_dag_overhead  = rule MaxRSS on well tier  (large DAG, ~5000 jobs)

    For any dag_sensitive rule in production (25K jobs), the DAG overhead will
    be larger still. We report the per-1000-job scaling so you can extrapolate.
    """
    tile_path = RESULTS_DIR / "calibration_tile.json"
    well_path = RESULTS_DIR / "calibration_well.json"

    missing = [p for p in [tile_path, well_path] if not p.exists()]
    if missing:
        print(f"[harness] ERROR: Run calibrate and calibrate_well first. Missing: {missing}")
        sys.exit(1)

    with open(tile_path) as f:
        tile_data = json.load(f)["rules"]
    with open(well_path) as f:
        well_data = json.load(f)["rules"]

    print("\n[harness] === DAG OVERHEAD ESTIMATE ===")
    print("Using anchor rules (constant work, different DAG sizes):")
    print(f"  Tile tier:  ~150 total jobs")
    print(f"  Well tier:  ~5000 total jobs")
    print()

    overhead_estimates = {}
    for rule in DAG_ANCHOR_RULES:
        tile_rss = tile_data.get(rule, {}).get("max_rss_mb", 0)
        well_rss = well_data.get(rule, {}).get("max_rss_mb", 0)
        if tile_rss and well_rss:
            dag_delta = well_rss - tile_rss
            per_1k_jobs = dag_delta / (5000 - 150) * 1000
            overhead_estimates[rule] = {
                "tile_rss_mb": tile_rss,
                "well_rss_mb": well_rss,
                "dag_delta_mb": dag_delta,
                "per_1k_jobs_mb": per_1k_jobs,
            }
            print(f"  {rule}:")
            print(f"    tile RSS: {tile_rss:.0f} MB  |  well RSS: {well_rss:.0f} MB")
            print(f"    DAG delta: {dag_delta:.0f} MB  (~{per_1k_jobs:.1f} MB per 1000 jobs)")

    if overhead_estimates:
        # Use mean across anchor rules
        mean_per_1k = sum(e["per_1k_jobs_mb"] for e in overhead_estimates.values()) / len(overhead_estimates)
        mean_tile_base = sum(e["tile_rss_mb"] for e in overhead_estimates.values()) / len(overhead_estimates)

        result = {
            "tile_dag_overhead_mb": mean_tile_base,
            "per_1k_jobs_mb": mean_per_1k,
            "anchor_rules": overhead_estimates,
            # Projected overhead for full baker run (~26K jobs)
            "full_baker_dag_overhead_mb": mean_tile_base + mean_per_1k * 26,
        }

        out = RESULTS_DIR / "dag_overhead.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\n  Mean scaling: {mean_per_1k:.1f} MB per 1000 jobs")
        print(f"  Projected full baker DAG overhead: {result['full_baker_dag_overhead_mb']:.0f} MB")
        print(f"\n[harness] Saved to {out}")


def cmd_mem_report(args):
    """
    Print recommended mem_mb per rule with breakdown:
    rule_memory | dag_overhead | safety_margin | total_recommended

    For tile-scaling rules: rule_memory from tile calibration
    For well-scaling rules: rule_memory from well calibration
    For dag_sensitive rules: subtract estimated DAG overhead to isolate rule memory
    """
    tile_path = RESULTS_DIR / "calibration_tile.json"
    well_path = RESULTS_DIR / "calibration_well.json"
    dag_path = RESULTS_DIR / "dag_overhead.json"

    if not tile_path.exists():
        print("[harness] ERROR: Run calibrate first.")
        sys.exit(1)

    with open(tile_path) as f:
        tile_data = json.load(f)["rules"]

    well_data = {}
    if well_path.exists():
        with open(well_path) as f:
            well_data = json.load(f)["rules"]

    dag_overhead_mb = 0.0
    per_1k_mb = 0.0
    if dag_path.exists():
        with open(dag_path) as f:
            dag_info = json.load(f)
        dag_overhead_mb = dag_info["tile_dag_overhead_mb"]
        per_1k_mb = dag_info["per_1k_jobs_mb"]

    print(f"\n{'Rule':<35} {'Tier':>5} {'ObsRSS':>8} {'DAGoverhead':>12} {'RuleMem':>9} {'Margin':>7} {'Rec mem_mb':>11}")
    print("-" * 95)

    recommendations = {}
    for rule, meta in sorted(RULE_MEMORY_PROFILE.items()):
        tier = meta["scales_with"]
        dag_sens = meta["dag_sensitive"]
        source = tile_data if tier == "tile" else well_data

        if rule not in source:
            continue

        obs_rss = source[rule]["max_rss_mb"]
        dag_oh = dag_overhead_mb if dag_sens else 0.0
        rule_mem = max(obs_rss - dag_oh, obs_rss * 0.5)  # never subtract more than 50%
        margin = MEM_MARGIN_TILE if tier == "tile" else MEM_MARGIN_WELL
        rec = int(rule_mem * margin) + int(dag_oh * DAG_MARGIN) + 50

        elapsed_s = source[rule]["max_elapsed_s"]
        runtime_rec = max(5, int(elapsed_s / 60 * RUNTIME_MARGIN) + 2)

        recommendations[rule] = {
            "tier": tier,
            "obs_rss_mb": obs_rss,
            "dag_overhead_mb": dag_oh,
            "rule_mem_mb": rule_mem,
            "mem_mb_recommended": rec,
            "runtime_recommended": runtime_rec,
        }

        print(f"{rule:<35} {tier:>5} {obs_rss:>8.0f} {dag_oh:>12.0f} {rule_mem:>9.0f} {margin:>7.1f}x {rec:>11}")

    out = RESULTS_DIR / "mem_recommendations.json"
    with open(out, "w") as f:
        json.dump(recommendations, f, indent=2)
    print(f"\n[harness] Recommendations saved to {out}")

    if per_1k_mb:
        print(f"\nNote: DAG overhead ~{per_1k_mb:.1f} MB per 1000 jobs.")
        print(f"For full baker (~26K jobs), add ~{per_1k_mb*26:.0f} MB to dag_sensitive rules.")


def cmd_search(args):
    """Grid search over cpus_per_task x jobs x slurm_array_limit (tile tier only)."""
    rec_path = RESULTS_DIR / "mem_recommendations.json"
    if not rec_path.exists():
        print("[harness] ERROR: Run mem_report first to generate memory recommendations.")
        sys.exit(1)

    with open(rec_path) as f:
        recommendations = json.load(f)

    base_profile = load_base_profile()
    calibrated_profile = apply_mem_recommendations(base_profile, recommendations)
    trials_log = RESULTS_DIR / "trials.jsonl"
    trial_num = 0

    for cpus in SEARCH_SPACE["cpus_per_task"]:
        for jobs in SEARCH_SPACE["jobs"]:
            for array_limit in SEARCH_SPACE["slurm_array_limit"]:
                trial_num += 1
                trial_name = f"trial_{trial_num:03d}_cpu{cpus}_jobs{jobs}_arr{array_limit}"
                print(f"\n[harness] === {trial_name} ===")

                profile = apply_search_params(calibrated_profile, cpus)
                profile["jobs"] = jobs

                trial_dir = RESULTS_DIR / trial_name
                trial_dir.mkdir(exist_ok=True)
                profile_dir = write_trial_profile(trial_dir, profile)

                log_path, wall_time = run_flow(
                    ["preprocess", "sbs", "phenotype"],
                    config=TILE_CONFIG,
                    profile_dir=profile_dir,
                    trial_name=trial_name,
                    extra_flags=[f"--slurm-array-limit={array_limit}"],
                )

                time.sleep(30)
                report_path = find_latest_efficiency_report()
                rule_data = parse_efficiency_report(report_path) if report_path else {}

                result = {
                    "trial": trial_name,
                    "params": {"cpus_per_task": cpus, "jobs": jobs, "slurm_array_limit": array_limit},
                    "wall_time_s": wall_time,
                    "wall_time_min": round(wall_time / 60, 1),
                    "rules": rule_data,
                }

                with open(trials_log, "a") as f:
                    f.write(json.dumps(result) + "\n")

                print(f"[harness] Wall time: {wall_time/60:.1f} min")

    print(f"\n[harness] Search complete. {trial_num} trials.")


def cmd_report(args):
    """Ranked comparison of search trials."""
    trials_log = RESULTS_DIR / "trials.jsonl"
    if not trials_log.exists():
        print("[harness] No trials found.")
        sys.exit(1)

    trials = []
    with open(trials_log) as f:
        for line in f:
            trials.append(json.loads(line.strip()))
    trials.sort(key=lambda t: t["wall_time_s"])

    print(f"\n{'Trial':<45} {'CPU/task':>8} {'Jobs':>6} {'Arr':>5} {'Wall min':>9}")
    print("-" * 80)
    for t in trials:
        p = t["params"]
        print(f"{t['trial']:<45} {p['cpus_per_task']:>8} {p['jobs']:>6} "
              f"{p['slurm_array_limit']:>5} {t['wall_time_min']:>9.1f}")

    best = trials[0]
    print(f"\nBest: {best['trial']} — {best['wall_time_min']} min")
    print(f"  cpus_per_task={best['params']['cpus_per_task']}, "
          f"jobs={best['params']['jobs']}, "
          f"slurm_array_limit={best['params']['slurm_array_limit']}")


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
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Brieflow speed harness")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("calibrate",      help="Tile tier: measure MaxRSS/elapsed for per-tile rules")
    sub.add_parser("calibrate_well", help="Well tier: measure MaxRSS for well-scaling rules")
    sub.add_parser("dag_overhead",   help="Estimate DAG memory overhead from anchor rules")
    sub.add_parser("mem_report",     help="Print recommended mem_mb with rule vs DAG breakdown")
    sub.add_parser("search",         help="Grid search over cpus_per_task, jobs, array_limit")
    sub.add_parser("report",         help="Ranked comparison of search trials")

    args = parser.parse_args()
    dispatch = {
        "calibrate":      cmd_calibrate,
        "calibrate_well": cmd_calibrate_well,
        "dag_overhead":   cmd_dag_overhead,
        "mem_report":     cmd_mem_report,
        "search":         cmd_search,
        "report":         cmd_report,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
