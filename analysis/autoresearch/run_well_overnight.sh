#!/bin/bash
set -euo pipefail
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis
eval "$(conda shell.bash hook)" && conda activate brieflow_speed

echo "=== Well run A: baseline ==="
python harness/harness.py run_well_trial --trial-json autoresearch/well_trial_A.json

echo "=== Well run B: tile mem + al=20 ==="
python harness/harness.py run_well_trial --trial-json autoresearch/well_trial_B.json

echo "=== Well run C: full best ==="
python harness/harness.py run_well_trial --trial-json autoresearch/well_trial_C.json

echo "=== All done. Results: ==="
cat autoresearch/well_results.tsv | column -t -s $'\t'
