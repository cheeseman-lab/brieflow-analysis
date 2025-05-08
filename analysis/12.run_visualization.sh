#!/bin/bash

export BRIEFLOW_OUTPUT_PATH="/lab/cheeseman_ops/brieflow-screens/aconcagua-analysis/analysis/analysis_root"
export CONFIG_PATH="/lab/cheeseman_ops/brieflow-screens/aconcagua-analysis/analysis/config/config.yml"
export SCREEN_PATH="/lab/cheeseman_ops/brieflow-screens/aconcagua-analysis/analysis/screen.yaml"

# Start Streamlit server, force bind to 0.0.0.0
exec streamlit run ../brieflow/visualization/Experimental_Overview.py --server.address=0.0.0.0 "$@"