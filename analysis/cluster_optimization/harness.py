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

`aggregate_efficiency` is preserved as a thin shellout to the plugin script
of the same name (operator muscle memory — `python harness.py
aggregate_efficiency` keeps working). HARDENING TODO #25 is the migration of
the canonical writer of `mem_recommendations.json` into the plugin; the
implementation now lives at
`<plugin>/scripts/brieflow_aggregate_efficiency.py`.

Usage:
    python harness.py run_tile [--tag X] [--notes "..."]
    python harness.py run_well [--tag X] [--notes "..."]
    python harness.py aggregate_efficiency
"""

from __future__ import annotations

import argparse
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
PLUGIN_AGG_EFF = "/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_aggregate_efficiency.py"

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
    """Refresh mem_recommendations.json from logs/efficiency_*/ CSVs.

    Thin shellout to the plugin's brieflow_aggregate_efficiency.py — the
    canonical implementation now lives in brieflow-ops (HARDENING TODO #25).
    Preserved here so `python harness.py aggregate_efficiency` keeps
    working for operator muscle memory.
    """
    cmd = [
        sys.executable, PLUGIN_AGG_EFF,
        "--analysis-dir", str(ANALYSIS_DIR),
    ]
    return subprocess.run(cmd, cwd=ANALYSIS_DIR).returncode


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
