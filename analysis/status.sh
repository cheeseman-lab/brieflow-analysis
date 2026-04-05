#!/bin/bash
# Quick status check for a running pipeline
echo "=== SLURM JOBS ==="
squeue -u $USER -o "%.8i %.30j %.2t %.10M %.6D %R" | head -20
TOTAL=$(squeue -u $USER -h | wc -l)
RUNNING=$(squeue -u $USER -h -t R | wc -l)
PENDING=$(squeue -u $USER -h -t PD | wc -l)
echo "Total: $TOTAL | Running: $RUNNING | Pending: $PENDING"

echo ""
echo "=== PIPELINE PROGRESS ==="
LOG=$(ls -t logs/*.log 2>/dev/null | head -1)
if [[ -n "$LOG" ]]; then
    grep "steps.*done" "$LOG" | tail -1
    echo "Log: $LOG"
else
    echo "No log file found"
fi
