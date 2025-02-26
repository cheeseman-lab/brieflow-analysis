#!/bin/bash

# Run the SBS/phenotype rules
snakemake --use-conda --cores all \
    --snakefile "../workflow/Snakefile" \
    --configfile "config/config.yml" \
    --rerun-triggers mtime \
    --until all_sbs all_phenotype
