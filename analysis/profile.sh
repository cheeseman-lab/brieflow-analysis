#!/bin/bash
# =============================================================================
# profile.sh - Profile a brieflow pipeline run
# =============================================================================
#
# Wraps flow.sh and extracts per-rule timing + memory from snakemake logs.
#
# Usage:
#   bash profile.sh <flow.sh args...>
#
# Examples:
#   bash profile.sh all --dry-run           # just check what would run
#   bash profile.sh preprocess sbs          # profile preprocess + sbs
#   bash profile.sh all --backend slurm     # profile full slurm run
#
# Outputs:
#   logs/profile-<timestamp>.tsv            # per-rule timing summary
#   logs/profile-<timestamp>.log            # full run log
#
# For slurm runs, also run after completion:
#   bash profile.sh --sacct <jobid_range>   # extract slurm resource usage
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"

PROFILE_LOG="${LOG_DIR}/profile-${TIMESTAMP}.log"
PROFILE_TSV="${LOG_DIR}/profile-${TIMESTAMP}.tsv"

# Handle --sacct mode
if [[ "${1:-}" == "--sacct" ]]; then
    JOBID="${2:?Usage: profile.sh --sacct <jobid or jobid_range>}"
    echo "Extracting slurm resource usage for job(s): ${JOBID}"
    sacct -j "$JOBID" \
        --format=JobID%20,JobName%30,Elapsed,MaxRSS,ReqMem,NCPUS,State,Start,End \
        --parsable2 | column -t -s'|'
    exit 0
fi

echo "============================================================"
echo "  PROFILED RUN | $(date)"
echo "  Args: $*"
echo "  Log: ${PROFILE_LOG}"
echo "  Profile: ${PROFILE_TSV}"
echo "============================================================"

# Run flow.sh and capture full output
START_TIME=$(date +%s)
/usr/bin/time -v bash "${SCRIPT_DIR}/flow.sh" "$@" 2>&1 | tee "$PROFILE_LOG"
EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

echo ""
echo "============================================================"
echo "  Total wall time: $((TOTAL_DURATION / 3600))h $((TOTAL_DURATION % 3600 / 60))m $((TOTAL_DURATION % 60))s"
echo "============================================================"

# Parse snakemake log for per-rule timing
echo ""
echo "Extracting per-rule timing..."

python3 << 'PARSE_SCRIPT'
import re
import sys
from collections import defaultdict
from pathlib import Path

log_file = sys.argv[1] if len(sys.argv) > 1 else "PROFILE_LOG_PLACEHOLDER"
tsv_file = sys.argv[2] if len(sys.argv) > 2 else "PROFILE_TSV_PLACEHOLDER"

with open(log_file) as f:
    log_text = f.read()

# Parse "Finished jobid: X (Rule: name)" with timestamps
# Pattern: [timestamp]\nFinished jobid: N (Rule: name)
finished = re.findall(
    r'\[([^\]]+)\]\s*\nFinished jobid: \d+ \(Rule: (\w+)\)',
    log_text
)

# Parse rule start times: "[timestamp]\nlocalrule name:" or "[timestamp]\nrule name:"
starts = re.findall(
    r'\[([^\]]+)\]\s*\n(?:local)?rule (\w+):',
    log_text
)

# Build per-rule timing from start/finish pairs
from datetime import datetime

rule_times = defaultdict(list)

# Parse all timestamps
def parse_ts(ts_str):
    for fmt in ['%a %b %d %H:%M:%S %Y', '%Y-%m-%dT%H:%M:%S']:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None

# Match starts to finishes by rule name (approximate)
start_times = {}
for ts_str, rule_name in starts:
    ts = parse_ts(ts_str)
    if ts:
        if rule_name not in start_times:
            start_times[rule_name] = []
        start_times[rule_name].append(ts)

for ts_str, rule_name in finished:
    ts = parse_ts(ts_str)
    if ts and rule_name in start_times and start_times[rule_name]:
        start_ts = start_times[rule_name].pop(0)
        duration = (ts - start_ts).total_seconds()
        rule_times[rule_name].append(duration)

# Write summary
with open(tsv_file, 'w') as f:
    f.write("rule\tcount\ttotal_s\tmean_s\tmax_s\tmin_s\n")
    for rule_name in sorted(rule_times.keys(), key=lambda r: -sum(rule_times[r])):
        times = rule_times[rule_name]
        total = sum(times)
        mean = total / len(times)
        mx = max(times)
        mn = min(times)
        f.write(f"{rule_name}\t{len(times)}\t{total:.1f}\t{mean:.1f}\t{mx:.1f}\t{mn:.1f}\n")
        print(f"  {rule_name:40s}  {len(times):3d} runs  total={total:8.1f}s  mean={mean:6.1f}s  max={mx:6.1f}s")

print(f"\nProfile saved to: {tsv_file}")
PARSE_SCRIPT
"$PROFILE_LOG" "$PROFILE_TSV"

exit $EXIT_CODE
