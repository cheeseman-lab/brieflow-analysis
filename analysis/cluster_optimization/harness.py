#!/usr/bin/env python3
"""Minimal cluster-optimization harness for brieflow.

This is the **slimmed** post-baker harness (2026-05-14). The speed-search /
SEARCH_TRIALS / autoresearch machinery has been retired — that work was
exploratory tile-tier tuning for the speed-branch arc and is no longer
load-bearing. What remains is the minimum viable surface for ad-hoc dev
work on this analysis dir:

  run_tile     — launch a tile-tier dev cycle via the plugin runloop
  run_well     — launch a well-tier validation cycle via the plugin runloop
  aggregate_efficiency  — refresh `mem_recommendations.json` from observed RSS

All runtime logic (mem-rec injection, OOM auto-recover, push notifications,
phase orchestration, config validation) lives in the brieflow-ops plugin
under `/lab/barcheese01/mdiberna/brieflow-ops/`. This harness does NOT
duplicate that. The two launchers are thin wrappers around
`brieflow_runloop.py` configured for the tile/well dataset tiers; everything
substantive happens in the plugin.

`aggregate_efficiency` is the one piece of canonical sizing logic that still
lives here — the canonical writer of `mem_recommendations.json`. HARDENING
TODO #25 will migrate it into the plugin so per-screen analysis dirs can
become pure data + tier-launcher only. Until then it stays here, callable
the same way operators have been calling it.

Usage:
    python harness.py run_tile [--tag X] [--notes "..."]
    python harness.py run_well [--tag X] [--notes "..."]
    python harness.py aggregate_efficiency
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CLUSTER_OPT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = CLUSTER_OPT_DIR.parent
RESULTS_DIR = CLUSTER_OPT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

TILE_CONFIG = "config/config_tile.yml"
WELL_CONFIG = "config/config_well.yml"

PLUGIN_RUNLOOP = "/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_runloop.py"

# ---------------------------------------------------------------------------
# Sizing constants used by aggregate_efficiency
# ---------------------------------------------------------------------------

# Multiplier on observed worst-case peak RSS when computing the recommended
# cap. Smaller than per-trial margins because input is already the worst
# observation across many runs.
AGGREGATE_OVERHEAD = 1.5

# Flag rules whose peak landed at >=95% of the cap they ran under as
# OOM-clipped (likely lower-bound observation, not a true peak).
PEAK_AT_CAP_THRESHOLD = 0.95

MANUAL_OVERRIDE_MARKERS = (
    "manual_override",
    "manual_from_sacct",
    "manual_post_oom",
)

# Per-rule scaling-tier classification. Used by aggregate_efficiency to
# annotate output entries; `tier` is `tile` (rule scales per-tile) or `well`
# (rule scales per-well or per-well-per-cycle). Keep up to date when new
# rules are added to brieflow's preprocess/sbs/phenotype phases. Aggregate-
# and cluster-phase rules are not listed here yet — they came online in v34
# and will be added when next observed; until then aggregate_efficiency
# silently skips them (preserving any manual_override entries).
RULE_MEMORY_PROFILE: dict[str, dict] = {
    # preprocess
    "convert_sbs":                  {"scales_with": "tile"},
    "convert_phenotype":            {"scales_with": "tile"},
    "extract_metadata_sbs":         {"scales_with": "tile"},
    "extract_metadata_phenotype":   {"scales_with": "tile"},
    "calculate_ic_sbs":             {"scales_with": "well"},
    "calculate_ic_phenotype":       {"scales_with": "well"},
    "combine_metadata_sbs":         {"scales_with": "well"},
    "combine_metadata_phenotype":   {"scales_with": "well"},
    # sbs per-tile
    "align_sbs":                    {"scales_with": "tile"},
    "log_filter":                   {"scales_with": "tile"},
    "compute_standard_deviation":   {"scales_with": "tile"},
    "find_peaks":                   {"scales_with": "tile"},
    "max_filter":                   {"scales_with": "tile"},
    "apply_ic_field_sbs":           {"scales_with": "tile"},
    "segment_sbs":                  {"scales_with": "tile"},
    "extract_bases":                {"scales_with": "tile"},
    "call_reads":                   {"scales_with": "tile"},
    "call_cells":                   {"scales_with": "tile"},
    "extract_sbs_info":             {"scales_with": "tile"},
    # sbs aggregation
    "combine_reads":                {"scales_with": "well"},
    "combine_cells":                {"scales_with": "well"},
    "combine_sbs_info":             {"scales_with": "well"},
    # phenotype per-tile
    "apply_ic_field_phenotype":     {"scales_with": "tile"},
    "align_phenotype":              {"scales_with": "tile"},
    "segment_phenotype":            {"scales_with": "tile"},
    "identify_cytoplasm":           {"scales_with": "tile"},
    "extract_phenotype_info":       {"scales_with": "tile"},
    # phenotype aggregation
    "combine_phenotype_info":       {"scales_with": "well"},
}


def _is_manual_override(entry: dict) -> bool:
    src = (entry or {}).get("obs_source") or ""
    return any(m in src for m in MANUAL_OVERRIDE_MARKERS)


# ---------------------------------------------------------------------------
# Tier launchers — thin wrappers over the plugin runloop
# ---------------------------------------------------------------------------

def _runloop_invoke(
    *,
    config_path: str,
    tag: str,
    notes: str | None,
    phases: str = "preprocess,sbs,phenotype",
    extra_runloop_args: list[str] | None = None,
):
    """Shell out to brieflow_runloop.py with the given config and tag."""
    cmd = [
        sys.executable,
        PLUGIN_RUNLOOP,
        "--analysis-dir", str(ANALYSIS_DIR),
        "--phases", phases,
        "--config", config_path,
        "--backend", "slurm",
        "--jobs", "400",
        "--latency-wait", "60",
        "--max-attempts", "20",
        "--tag", tag,
    ]
    if notes:
        cmd.extend(["--notes", notes])
    if extra_runloop_args:
        cmd.extend(extra_runloop_args)
    print(f"[harness] launching: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ANALYSIS_DIR).returncode


def cmd_run_tile(args):
    """Launch a tile-tier dev cycle on this analysis dir.

    Tile config (`config/config_tile.yml`) is the smallest tier — fast
    iteration for testing config changes, env updates, or pipeline-code
    changes before committing to a longer well-tier validation.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = args.tag or f"tile_{ts}"
    return _runloop_invoke(
        config_path=TILE_CONFIG,
        tag=tag,
        notes=args.notes,
        phases=args.phases,
    )


def cmd_run_well(args):
    """Launch a well-tier validation cycle on this analysis dir.

    Well config (`config/config_well.yml`) runs at single-well scale —
    longer than tile (~hours) but catches scaling issues that tile-tier
    misses. Use to validate before promoting to a full screen run.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = args.tag or f"well_{ts}"
    return _runloop_invoke(
        config_path=WELL_CONFIG,
        tag=tag,
        notes=args.notes,
        phases=args.phases,
    )


# ---------------------------------------------------------------------------
# aggregate_efficiency — canonical writer of mem_recommendations.json
# ---------------------------------------------------------------------------

def cmd_aggregate_efficiency(args):
    """Aggregate worst-case peak RSS per rule across all logs/efficiency_*/*.csv.

    Canonical writer of `mem_recommendations.json`. Each successful run drops
    a fresh efficiency CSV under `logs/efficiency_*/`; this command rolls
    them all up so memory recommendations self-correct as more data
    accumulates.

    PRESERVES manual override entries (entries whose `obs_source` contains
    one of `MANUAL_OVERRIDE_MARKERS`) — without preservation, aggregator
    runs would silently undo any post-OOM mem bumps that hadn't yet
    appeared in efficiency CSVs.

    HARDENING TODO #25 will migrate this function into the brieflow-ops
    plugin so per-screen analysis dirs can drop the harness scaffolding
    entirely. Until then the function lives here, called by operators or
    by the plugin's runloop after each phase success.
    """
    log_dir = ANALYSIS_DIR / "logs"
    csvs: list[Path] = []
    for d in log_dir.iterdir():
        if d.is_dir() and d.name.startswith("efficiency_"):
            csvs.extend(d.glob("*.csv"))
    if not csvs:
        print(f"[harness] ERROR: no efficiency CSVs under {log_dir}/efficiency_*/.")
        sys.exit(1)

    # Read existing recommendations to discover manual overrides to preserve.
    out = RESULTS_DIR / "mem_recommendations.json"
    existing: dict = {}
    if out.exists():
        try:
            with open(out) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    # Per-rule aggregate state.
    agg: dict = {}
    for csv_path in csvs:
        try:
            with open(csv_path) as f:
                for row in csv.DictReader(f):
                    rule = (row.get("RuleName") or "").split("_wildcards")[0].replace("rule_", "")
                    if not rule or rule not in RULE_MEMORY_PROFILE:
                        continue
                    try:
                        rss = float(row["MaxRSS_MB"]) if row.get("MaxRSS_MB") else 0.0
                        cap = float(row["RequestedMem_MB"]) if row.get("RequestedMem_MB") else 0.0
                    except ValueError:
                        continue
                    if rss <= 0:
                        continue
                    cur = agg.setdefault(rule, {"peak": 0.0, "cap_at_peak": 0.0, "n": 0})
                    cur["n"] += 1
                    if rss > cur["peak"]:
                        cur["peak"] = rss
                        cur["cap_at_peak"] = cap
        except OSError as e:
            print(f"[harness] WARN: skipping {csv_path}: {e}")

    if not agg and not existing:
        print("[harness] ERROR: no observations matched RULE_MEMORY_PROFILE rules "
              "and no existing mem_recommendations.json to preserve.")
        sys.exit(1)

    def ceil_to_100(x: float) -> int:
        return int(((x // 100) + 1) * 100)

    recommendations: dict = {}
    preserved: list = []

    # 1. Carry forward manual overrides verbatim.
    for rule, entry in existing.items():
        if _is_manual_override(entry):
            recommendations[rule] = entry
            preserved.append(rule)

    # 2. For each observed rule, build a fresh recommendation (unless it's a
    # preserved manual override).
    for rule, cur in sorted(agg.items()):
        if rule in recommendations:
            continue
        tier = RULE_MEMORY_PROFILE[rule]["scales_with"]
        rec = ceil_to_100(cur["peak"] * AGGREGATE_OVERHEAD)
        entry = {
            "tier": tier,
            "obs_peak_rss_mb": cur["peak"],
            "obs_cap_at_peak_mb": cur["cap_at_peak"],
            "obs_n": cur["n"],
            "obs_source": "efficiency_aggregated",
            "overhead": AGGREGATE_OVERHEAD,
            "mem_mb_recommended": rec,
        }
        if cur["cap_at_peak"] > 0 and cur["peak"] >= cur["cap_at_peak"] * PEAK_AT_CAP_THRESHOLD:
            entry["WARNING"] = "peak_was_at_cap_actual_peak_may_be_higher"
        recommendations[rule] = entry

    print(f"\n[harness] === AGGREGATE EFFICIENCY "
          f"({len(csvs)} CSVs, {sum(c['n'] for c in agg.values())} rule-observations, "
          f"{len(preserved)} manual-override preserved) ===")
    print(f"{'Rule':<32} {'Tier':>5} {'N':>5} {'PeakMB':>10} {'CapMB':>10} {'RecMB':>10}  Flag")
    print("-" * 88)
    for rule, v in sorted(recommendations.items(), key=lambda kv: (kv[1].get("tier", ""), kv[0])):
        flag = v.get("WARNING", "")
        if rule in preserved:
            flag = (flag + " manual_override").strip()
        print(f"{rule:<32} {v.get('tier', ''):>5} {v.get('obs_n', ''):>5} "
              f"{v.get('obs_peak_rss_mb', 0):>10.1f} {v.get('obs_cap_at_peak_mb', 0):>10.1f} "
              f"{v.get('mem_mb_recommended', 0):>10}  {flag}")

    with open(out, "w") as f:
        json.dump(recommendations, f, indent=2, sort_keys=True)
    print(f"\n[harness] Saved to {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Slim cluster-optimization harness — tier launchers + aggregate_efficiency."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_tile = sub.add_parser("run_tile", help="Launch a tile-tier dev cycle.")
    p_tile.add_argument("--tag", default=None)
    p_tile.add_argument("--notes", default=None)
    p_tile.add_argument(
        "--phases", default="preprocess,sbs,phenotype",
        help="Comma-separated phase chain (default: preprocess,sbs,phenotype)."
    )
    p_tile.set_defaults(func=cmd_run_tile)

    p_well = sub.add_parser("run_well", help="Launch a well-tier validation cycle.")
    p_well.add_argument("--tag", default=None)
    p_well.add_argument("--notes", default=None)
    p_well.add_argument(
        "--phases", default="preprocess,sbs,phenotype",
        help="Comma-separated phase chain (default: preprocess,sbs,phenotype)."
    )
    p_well.set_defaults(func=cmd_run_well)

    p_agg = sub.add_parser(
        "aggregate_efficiency",
        help="Refresh mem_recommendations.json from logs/efficiency_*/ CSVs."
    )
    p_agg.set_defaults(func=cmd_aggregate_efficiency)

    args = ap.parse_args()
    rc = args.func(args)
    sys.exit(int(rc or 0))


if __name__ == "__main__":
    main()
