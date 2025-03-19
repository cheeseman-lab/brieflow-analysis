#!/bin/bash

# Log all output to a log file (stdout and stderr)
mkdir -p slurm/slurm_output/main
start_time_formatted=$(date +%Y%m%d_%H%M%S)
log_file="slurm/slurm_output/main/aggregate-${start_time_formatted}.log"
exec > >(tee -a "$log_file") 2>&1

echo "Started at: $(date)"

# Activate conda environment (adjust path as needed)
source ~/.bashrc
conda activate brieflow_agg_overhaul_env

# Run the aggregate rules
snakemake --executor slurm --use-conda \
    --workflow-profile "slurm/" \
    --snakefile "../brieflow/workflow/Snakefile" \
    --configfile "config/config.yml" \
    --latency-wait 60 \
    --rerun-triggers mtime \
    --keep-going \
    --until eval_aggregate

echo "Ended at: $(date)"