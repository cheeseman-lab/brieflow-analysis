#!/bin/bash

# Log all output to a log file (stdout and stderr)
mkdir -p slurm/slurm_output/main
start_time_formatted=$(date +%Y%m%d_%H%M%S)
log_file="slurm/slurm_output/main/merge-${start_time_formatted}.log"
exec > >(tee -a "$log_file") 2>&1

# Start timing
start_time=$(date +%s)

# Activate conda environment (adjust path as needed)
source ~/.bashrc
conda activate brieflow_workflows

# Run the merge rules
snakemake --executor slurm --use-conda \
    --workflow-profile "slurm/" \
    --snakefile "../brieflow/workflow/Snakefile" \
    --configfile "config/config.yml" \
    --latency-wait 60 \
    --rerun-triggers mtime \
    --until all_merge

# End timing and calculate duration
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Total runtime: $((duration / 3600))h $(((duration % 3600) / 60))m $((duration % 60))s" >> slurm/slurm_output/main/merge-$SLURM_JOB_ID.out
