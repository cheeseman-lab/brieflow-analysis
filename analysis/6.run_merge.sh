#!/bin/bash

# Run the merge rules
snakemake --use-conda --cores all \
    --snakefile "../workflow/Snakefile" \
    --configfile "config/config.yml" \
    --rerun-triggers mtime \
    --until all_merge
