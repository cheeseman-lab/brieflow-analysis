#!/bin/bash
# =============================================================================
# prep_cellxstate.sh — Prepare OPS Data Standard submission directory
# =============================================================================
#
# Reshapes brieflow pipeline outputs into the CellxState/OPS submission
# directory structure:
#
#   {collection_root}/
#   ├── collection_metadata.yaml
#   └── {screen_name}/
#       ├── metadata/
#       │   ├── experimental_metadata.yaml
#       │   ├── perturbation_library.csv
#       │   └── feature_definitions.csv        (OPTIONAL)
#       ├── cell_data.parquet
#       ├── visualizations/
#       │   └── {visualization_id}/
#       │       ├── aggregated_data.h5ad
#       │       └── examples.zarr
#       └── {screen_name}.zarr
#
# Usage:
#   bash prep_cellxstate.sh
#
# Prerequisites:
#   - Pipeline must have completed (all_sbs, all_phenotype, all_merge, all_aggregate)
#   - analysis/screen.yaml must be filled in
#   - conda env with brieflow installed
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these for your screen
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Source paths (brieflow pipeline outputs)
SCREEN_YAML="${SCRIPT_DIR}/screen.yaml"
CONFIG_YAML="${SCRIPT_DIR}/config/screen.yml"  # brieflow pipeline config

# Read screen name from screen.yaml
SCREEN_NAME=$(python3 -c "
import yaml
with open('${SCREEN_YAML}') as f:
    cfg = yaml.safe_load(f)
print(cfg['experiment']['id'])
")

if [ -z "$SCREEN_NAME" ]; then
    echo "ERROR: experiment.id is empty in screen.yaml"
    exit 1
fi

# Pipeline output root (from brieflow config)
OUTPUT_ROOT=$(python3 -c "
import yaml
with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
print(cfg['all']['root_fp'])
")

# Submission output directory
SUBMISSION_DIR="${SCRIPT_DIR}/cellxstate_submission"

echo "=== OPS Data Standard Submission Prep ==="
echo "Screen:     ${SCREEN_NAME}"
echo "Output:     ${OUTPUT_ROOT}"
echo "Submission: ${SUBMISSION_DIR}"
echo ""

# ---------------------------------------------------------------------------
# Create submission directory structure
# ---------------------------------------------------------------------------
SCREEN_DIR="${SUBMISSION_DIR}/${SCREEN_NAME}"
mkdir -p "${SCREEN_DIR}/metadata"
mkdir -p "${SCREEN_DIR}/visualizations/default"

# ---------------------------------------------------------------------------
# 1. Collection metadata (from screen.yaml → collection_metadata.yaml)
# ---------------------------------------------------------------------------
echo "[1/7] Generating collection_metadata.yaml..."
python3 -c "
import yaml

with open('${SCREEN_YAML}') as f:
    screen = yaml.safe_load(f)

collection = {
    'collection': {
        'title': screen.get('collection', {}).get('title', ''),
        'publication_doi': screen.get('collection', {}).get('publication_doi'),
    }
}

with open('${SUBMISSION_DIR}/collection_metadata.yaml', 'w') as f:
    yaml.dump(collection, f, default_flow_style=False, sort_keys=False)
"
echo "  -> collection_metadata.yaml"

# ---------------------------------------------------------------------------
# 2. Experimental metadata (from screen.yaml → experimental_metadata.yaml)
#    Injects channel names from config + brieflow version
# ---------------------------------------------------------------------------
echo "[2/7] Generating experimental_metadata.yaml..."
python3 -c "
import yaml
from pathlib import Path

with open('${SCREEN_YAML}') as f:
    screen = yaml.safe_load(f)

# Read brieflow version from pyproject.toml
version = 'unknown'
pyproject = Path('${REPO_ROOT}/brieflow/pyproject.toml')
if pyproject.exists():
    for line in pyproject.read_text().splitlines():
        if line.strip().startswith('version'):
            version = line.split('=')[1].strip().strip('\"')
            break

# Read channel names from pipeline config
channel_names = []
try:
    with open('${CONFIG_YAML}') as f:
        cfg = yaml.safe_load(f)
    for ch in cfg.get('preprocess', {}).get('phenotype_channels_metadata', []):
        channel_names.append(ch.get('name', ''))
except Exception:
    pass

# Build spec-compliant experimental_metadata
meta = {
    'experiment': {
        'screen_title': screen.get('experiment', {}).get('screen_title', ''),
        'organism_ontology_term_id': screen.get('experiment', {}).get('organism_ontology_term_id', ''),
        'organism': screen.get('experiment', {}).get('organism', ''),
        'tissue_ontology_term_id': screen.get('experiment', {}).get('tissue_ontology_term_id', ''),
        'tissue': screen.get('experiment', {}).get('tissue', ''),
        'tissue_type': screen.get('experiment', {}).get('tissue_type', 'cell line'),
        'disease_ontology_term_id': screen.get('experiment', {}).get('disease_ontology_term_id', ''),
        'disease': screen.get('experiment', {}).get('disease', ''),
        'development_stage_ontology_term_id': screen.get('experiment', {}).get('development_stage_ontology_term_id', 'na'),
        'development_stage': screen.get('experiment', {}).get('development_stage', 'na'),
        'assay_ontology_term_id': screen.get('experiment', {}).get('assay_ontology_term_id', 'EFO:0022605'),
        'assay': screen.get('experiment', {}).get('assay', 'optical pooled screening'),
        'pseudobulk': screen.get('experiment', {}).get('pseudobulk', []),
    },
    'cellular': {
        'growth_conditions': screen.get('cellular', {}).get('growth_conditions', ''),
        'plate_type': screen.get('cellular', {}).get('plate_type', ''),
        'seeding': screen.get('cellular', {}).get('seeding', {}),
        'induction': screen.get('cellular', {}).get('induction', {}),
    },
    'library': screen.get('library', {}),
    'iss': {
        'cycles': screen.get('sbs', {}).get('cycles'),
        'objective': screen.get('sbs', {}).get('objective', ''),
        'chemistry': screen.get('sbs', {}).get('chemistry', ''),
        'channels': screen.get('sbs', {}).get('channels', []),
    },
    'phenotype': {
        'objective': screen.get('phenotype', {}).get('objective', ''),
        'exposure_time_ms': screen.get('phenotype', {}).get('exposure_time_ms', []),
        'channels': channel_names,
    },
    'microscope': screen.get('microscope', {}),
    'pipeline': {
        'github': 'cheeseman-lab/brieflow',
        'version': version,
    },
}

with open('${SCREEN_DIR}/metadata/experimental_metadata.yaml', 'w') as f:
    yaml.dump(meta, f, default_flow_style=False, sort_keys=False)
"
echo "  -> metadata/experimental_metadata.yaml"

# ---------------------------------------------------------------------------
# 3. Feature definitions (expand template with channel/compartment names)
# ---------------------------------------------------------------------------
echo "[3/7] Generating feature_definitions.csv..."
FEATURE_TEMPLATE="${REPO_ROOT}/brieflow/workflow/lib/external/feature_definitions.csv"
if [ -f "$FEATURE_TEMPLATE" ]; then
    python3 -c "
import csv
import yaml
from itertools import combinations
from pathlib import Path

# Read channel names from config
with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
channels = [ch['name'] for ch in cfg.get('preprocess', {}).get('phenotype_channels_metadata', [])]
compartments = ['nucleus', 'cell', 'cytoplasm']

# Read brieflow version
version = 'unknown'
pyproject = Path('${REPO_ROOT}/brieflow/pyproject.toml')
if pyproject.exists():
    for line in pyproject.read_text().splitlines():
        if line.strip().startswith('version'):
            version = line.split('=')[1].strip().strip('\"')
            break

# Read template
with open('${FEATURE_TEMPLATE}') as f:
    reader = csv.DictReader(f)
    templates = list(reader)

# Expand
rows = []
for t in templates:
    fid = t['feature_id']
    fname = t['feature_name']

    # Determine what placeholders are present
    has_compartment = '{compartment}' in fid
    has_channel = '{channel}' in fid
    has_two_channels = fid.count('{channel}') == 2

    comps = compartments if has_compartment else ['']

    for comp in comps:
        if has_two_channels:
            # Channel pair features (correlation, colocalization)
            for ch1, ch2 in combinations(channels, 2):
                row = dict(t)
                row['feature_id'] = fid.replace('{compartment}', comp).replace('{channel}', ch1, 1).replace('{channel}', ch2, 1)
                row['feature_name'] = fname.replace('{Compartment}', comp.capitalize()).replace('{Channel}', ch1, 1).replace('{Channel}', ch2, 1)
                row['version'] = version
                rows.append(row)
        elif has_channel:
            for ch in channels:
                row = dict(t)
                row['feature_id'] = fid.replace('{compartment}', comp).replace('{channel}', ch)
                row['feature_name'] = fname.replace('{Compartment}', comp.capitalize()).replace('{Channel}', ch)
                row['version'] = version
                rows.append(row)
        else:
            row = dict(t)
            row['feature_id'] = fid.replace('{compartment}', comp)
            row['feature_name'] = fname.replace('{Compartment}', comp.capitalize())
            row['version'] = version
            rows.append(row)

with open('${SCREEN_DIR}/metadata/feature_definitions.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['feature_id', 'feature_name', 'feature_type', 'unit', 'software', 'version'])
    writer.writeheader()
    writer.writerows(rows)

print(f'  -> metadata/feature_definitions.csv ({len(rows)} features)')
"
else
    echo "  SKIP: feature template not found at ${FEATURE_TEMPLATE}"
fi

# ---------------------------------------------------------------------------
# 4. Perturbation library
# ---------------------------------------------------------------------------
echo "[4/7] Copying perturbation_library.csv..."
# TODO: reshape brieflow gene library to spec format
# For now, look for existing file
PERT_LIB=$(find "${OUTPUT_ROOT}" -name "perturbation_library.csv" -o -name "gene_library.csv" 2>/dev/null | head -1)
if [ -n "$PERT_LIB" ]; then
    cp "$PERT_LIB" "${SCREEN_DIR}/metadata/perturbation_library.csv"
    echo "  -> metadata/perturbation_library.csv"
else
    echo "  SKIP: no perturbation library found (TODO: reshape from brieflow input)"
fi

# ---------------------------------------------------------------------------
# 5. Cell data (parquet)
# ---------------------------------------------------------------------------
echo "[5/7] Copying cell_data.parquet..."
# TODO: reshape brieflow merge output to spec column names
CELL_DATA=$(find "${OUTPUT_ROOT}/merge" -name "*.parquet" -path "*/combined*" 2>/dev/null | head -1)
if [ -n "$CELL_DATA" ]; then
    cp "$CELL_DATA" "${SCREEN_DIR}/cell_data.parquet"
    echo "  -> cell_data.parquet"
else
    echo "  SKIP: no merged cell data found"
fi

# ---------------------------------------------------------------------------
# 6. Zarr images (copy/link the plate zarr stores)
# ---------------------------------------------------------------------------
echo "[6/7] Copying zarr image stores..."
# Copy phenotype zarr stores (the primary image data)
for zarr_store in "${OUTPUT_ROOT}"/phenotype/*.zarr; do
    if [ -d "$zarr_store" ]; then
        store_name=$(basename "$zarr_store")
        echo "  Copying ${store_name}..."
        cp -r "$zarr_store" "${SCREEN_DIR}/${store_name}"
    fi
done
echo "  -> zarr stores copied"

# ---------------------------------------------------------------------------
# 7. Aggregated data + example images (placeholders)
# ---------------------------------------------------------------------------
echo "[7/7] Aggregated data and example images..."
AGG_DATA=$(find "${OUTPUT_ROOT}/aggregate" -name "*.h5ad" 2>/dev/null | head -1)
if [ -n "$AGG_DATA" ]; then
    cp "$AGG_DATA" "${SCREEN_DIR}/visualizations/default/aggregated_data.h5ad"
    echo "  -> visualizations/default/aggregated_data.h5ad"
else
    echo "  SKIP: no aggregated_data.h5ad found (TODO: reshape from brieflow aggregate output)"
fi
echo "  SKIP: examples.zarr (TODO: generate from montage/crop pipeline)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Submission directory ready ==="
echo ""
find "${SUBMISSION_DIR}" -type f | sort | sed "s|${SUBMISSION_DIR}/||"
echo ""
echo "Remaining TODOs:"
echo "  - [ ] Fill in all [REQUIRED] fields in screen.yaml"
echo "  - [ ] Reshape perturbation_library.csv to spec format"
echo "  - [ ] Reshape cell_data.parquet columns to spec format"
echo "  - [ ] Reshape aggregated_data.h5ad to spec format"
echo "  - [ ] Generate examples.zarr from image crops"
echo "  - [ ] Run ops-validate on the submission directory"
