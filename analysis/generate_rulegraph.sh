#!/bin/bash

# Generate a rulegraph of the Snakefile
snakemake \
    --snakefile "../brieflow/workflow/Snakefile" \
    --configfile "config/config.yml" \
    --until all_preprocessing all_sbs all_phenotype all_aggregate all_cluster \
    --rulegraph | dot -Gdpi=100 -Tpng -o "../images/brieflow_rulegraph.png"
