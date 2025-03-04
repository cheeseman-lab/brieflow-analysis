#!/bin/bash

# Generate a rulegraph of the Snakefile
snakemake \
    --snakefile "../brieflow/workflow/Snakefile" \
    --configfile "config/config.yml" \
    --rulegraph | dot -Gdpi=100 -Tpng -o "../images/brieflow_rulegraph.png"
