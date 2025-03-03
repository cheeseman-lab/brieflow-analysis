#!/bin/bash

# Run the merge process rules
snakemake --use-conda --cores all \
    --snakefile "../brieflow/workflow/Snakefile" \
    --configfile "config/config.yml" \
    --rerun-triggers mtime \
    --until all_aggregate
