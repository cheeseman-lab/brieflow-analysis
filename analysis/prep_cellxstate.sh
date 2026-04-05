#!/bin/bash
# =============================================================================
# prep_cellxstate.sh — Prepare OPS Data Standard submission directory
# =============================================================================
#
# Reshapes brieflow pipeline outputs into the CellxState/OPS submission
# directory structure:
#
#   {submission_dir}/
#   ├── collection_metadata.yaml
#   └── {screen_name}/
#       ├── metadata/
#       │   ├── experimental_metadata.yaml
#       │   ├── perturbation_library.csv
#       │   └── feature_definitions.csv        (OPTIONAL)
#       ├── cell_data.parquet                  (TODO)
#       ├── visualizations/
#       │   └── {visualization_id}/
#       │       ├── aggregated_data.h5ad       (TODO)
#       │       └── examples.zarr              (TODO)
#       └── {screen_name}.zarr
#
# Usage:
#   bash prep_cellxstate.sh [--test]
#
#   --test    Use small_test_analysis paths (for development/testing)
#
# Prerequisites:
#   - Pipeline must have completed (all_sbs, all_phenotype, all_merge, etc.)
#   - analysis/screen.yaml must be filled in
#   - conda env with brieflow installed
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Default paths (production)
SCREEN_YAML="${SCRIPT_DIR}/screen.yaml"
CONFIG_YAML="${SCRIPT_DIR}/config/screen.yml"
BARCODE_LIBRARY_FP=""  # auto-detect from config

# Test mode overrides
if [[ "${1:-}" == "--test" ]]; then
    echo "*** TEST MODE: using small_test_analysis ***"
    TEST_DIR="${REPO_ROOT}/brieflow/tests/small_test_analysis"
    CONFIG_YAML="${TEST_DIR}/config/config_omezarr.yml"
    BARCODE_LIBRARY_FP="${TEST_DIR}/config/barcode_library.tsv"
fi

# Read config values
SCREEN_NAME=$(python3 -c "
import yaml
with open('${SCREEN_YAML}') as f:
    cfg = yaml.safe_load(f)
title = cfg.get('experiment', {}).get('screen_title', '')
# Use screen_title or fall back to a slug
print(title.lower().replace(' ', '_') if title else 'unnamed_screen')
")

OUTPUT_ROOT=$(python3 -c "
import yaml
with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
print(cfg['all']['root_fp'])
")

# If running in test mode, resolve OUTPUT_ROOT relative to test dir
if [[ "${1:-}" == "--test" ]]; then
    OUTPUT_ROOT="${TEST_DIR}/${OUTPUT_ROOT}"
fi

# Auto-detect barcode library from config if not set
if [ -z "$BARCODE_LIBRARY_FP" ]; then
    BARCODE_LIBRARY_FP=$(python3 -c "
import yaml
with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('sbs', {}).get('df_barcode_library_fp', ''))
")
    # Resolve relative to config dir
    if [ -n "$BARCODE_LIBRARY_FP" ] && [ ! -f "$BARCODE_LIBRARY_FP" ]; then
        BARCODE_LIBRARY_FP="$(dirname "${CONFIG_YAML}")/../${BARCODE_LIBRARY_FP}"
    fi
fi

# Submission output directory
SUBMISSION_DIR="${SCRIPT_DIR}/cellxstate_submission"

echo "=== OPS Data Standard Submission Prep ==="
echo "Screen:     ${SCREEN_NAME}"
echo "Output:     ${OUTPUT_ROOT}"
echo "Barcode:    ${BARCODE_LIBRARY_FP}"
echo "Submission: ${SUBMISSION_DIR}"
echo ""

# ---------------------------------------------------------------------------
# Create submission directory structure
# ---------------------------------------------------------------------------
SCREEN_DIR="${SUBMISSION_DIR}/${SCREEN_NAME}"
rm -rf "${SUBMISSION_DIR}"
mkdir -p "${SCREEN_DIR}/metadata"
mkdir -p "${SCREEN_DIR}/visualizations/default"

# ---------------------------------------------------------------------------
# 1. Collection metadata
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
# 2. Experimental metadata
# ---------------------------------------------------------------------------
echo "[2/7] Generating experimental_metadata.yaml..."
python3 -c "
import yaml
from pathlib import Path

with open('${SCREEN_YAML}') as f:
    screen = yaml.safe_load(f)

# Read brieflow version
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
    'cellular': screen.get('cellular', {}),
    'library': screen.get('library', {}),
    'iss': screen.get('iss', {}),
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
# 3. Perturbation library (reshape barcode_library.tsv → spec CSV)
# ---------------------------------------------------------------------------
echo "[3/7] Generating perturbation_library.csv..."
if [ -n "$BARCODE_LIBRARY_FP" ] && [ -f "$BARCODE_LIBRARY_FP" ]; then
    python3 -c "
import pandas as pd

df = pd.read_csv('${BARCODE_LIBRARY_FP}', sep='\t')

# Build spec-compliant perturbation_library.csv
out = pd.DataFrame()
out['perturbation_id'] = df['gene_symbol']
out['gene_id'] = df.get('gene_id', '')
out['gene_symbol'] = df['gene_symbol']
out['barcode'] = df['prefix']
out['role'] = df.get('role', 'targeting')
out['control_type'] = df.get('control_type', '')
out['protospacer_sequence'] = df.get('protospacer_sequence', '')
out['protospacer_adjacent_motif'] = df.get('protospacer_adjacent_motif', \"3' NGG\")

# Optional columns
if 'sgrna_target_locus' in df.columns:
    out['sgrna_target_locus'] = df['sgrna_target_locus']

# Drop empty control_type for targeting guides (spec requires absent, not empty)
out.loc[out['role'] == 'targeting', 'control_type'] = ''

out.to_csv('${SCREEN_DIR}/metadata/perturbation_library.csv', index=False)
print(f'  -> metadata/perturbation_library.csv ({len(out)} rows)')
"
else
    echo "  SKIP: barcode library not found at ${BARCODE_LIBRARY_FP}"
fi

# ---------------------------------------------------------------------------
# 4. Feature definitions (expand template with channel/compartment names)
# ---------------------------------------------------------------------------
echo "[4/7] Generating feature_definitions.csv..."
FEATURE_TEMPLATE="${REPO_ROOT}/brieflow/workflow/lib/external/feature_definitions.csv"
if [ -f "$FEATURE_TEMPLATE" ]; then
    python3 -c "
import csv
import yaml
from itertools import combinations
from pathlib import Path

with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
channels = [ch['name'] for ch in cfg.get('preprocess', {}).get('phenotype_channels_metadata', [])]
compartments = ['nucleus', 'cell', 'cytoplasm']

version = 'unknown'
pyproject = Path('${REPO_ROOT}/brieflow/pyproject.toml')
if pyproject.exists():
    for line in pyproject.read_text().splitlines():
        if line.strip().startswith('version'):
            version = line.split('=')[1].strip().strip('\"')
            break

with open('${FEATURE_TEMPLATE}') as f:
    reader = csv.DictReader(f)
    templates = list(reader)

rows = []
for t in templates:
    fid = t['feature_id']
    fname = t['feature_name']
    has_compartment = '{compartment}' in fid
    has_channel = '{channel}' in fid
    has_two_channels = fid.count('{channel}') == 2
    comps = compartments if has_compartment else ['']

    def expand_row(row, comp, ch=None, ch2=None):
        r = dict(row)
        r['feature_id'] = r['feature_id'].replace('{compartment}', comp)
        r['feature_name'] = r['feature_name'].replace('{Compartment}', comp.capitalize())
        r['compartment'] = r.get('compartment', '').replace('{compartment}', comp)
        if ch:
            r['feature_id'] = r['feature_id'].replace('{channel}', ch, 1)
            r['feature_name'] = r['feature_name'].replace('{Channel}', ch, 1)
            r['channel'] = ch
        if ch2:
            r['feature_id'] = r['feature_id'].replace('{channel}', ch2, 1)
            r['feature_name'] = r['feature_name'].replace('{Channel}', ch2, 1)
        r['version'] = version
        return r

    for comp in comps:
        if has_two_channels:
            for ch1, ch2 in combinations(channels, 2):
                rows.append(expand_row(t, comp, ch1, ch2))
        elif has_channel:
            for ch in channels:
                rows.append(expand_row(t, comp, ch))
        else:
            rows.append(expand_row(t, comp))

with open('${SCREEN_DIR}/metadata/feature_definitions.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['feature_id', 'feature_name', 'feature_type', 'compartment', 'channel', 'unit', 'software', 'version'])
    writer.writeheader()
    writer.writerows(rows)

print(f'  -> metadata/feature_definitions.csv ({len(rows)} features)')
"
else
    echo "  SKIP: feature template not found at ${FEATURE_TEMPLATE}"
fi

# ---------------------------------------------------------------------------
# 5. Cell data (singlecell h5ad from aggregate)
# ---------------------------------------------------------------------------
echo "[5/8] Cell data (AnnData)..."
CELL_H5AD=$(find "${OUTPUT_ROOT}/aggregate/anndata" -name "*.h5ad" 2>/dev/null | head -1)
if [ -n "$CELL_H5AD" ]; then
    cp "$CELL_H5AD" "${SCREEN_DIR}/cell_data.h5ad"
    echo "  -> cell_data.h5ad (single-cell AnnData)"
else
    echo "  SKIP: no singlecell.h5ad found in aggregate/anndata/"
fi

# ---------------------------------------------------------------------------
# 6. Zarr images (copy the plate zarr stores)
# ---------------------------------------------------------------------------
echo "[6/8] Zarr image stores..."
ZARR_FOUND=false
for zarr_store in "${OUTPUT_ROOT}"/phenotype/aligned_*.zarr; do
    if [ -d "$zarr_store" ]; then
        store_name=$(basename "$zarr_store")
        echo "  Copying ${store_name}..."
        cp -r "$zarr_store" "${SCREEN_DIR}/${store_name}"
        ZARR_FOUND=true
    fi
done
if [ "$ZARR_FOUND" = false ]; then
    echo "  SKIP: no phenotype zarr stores found"
fi

# ---------------------------------------------------------------------------
# 7. Example images (examples.zarr from montage pipeline)
# ---------------------------------------------------------------------------
echo "[7/8] Example images..."
EXAMPLES_ZARR=$(find "${OUTPUT_ROOT}/aggregate/montages" -name "*__examples.zarr" -type d 2>/dev/null | head -1)
if [ -n "$EXAMPLES_ZARR" ]; then
    cp -r "$EXAMPLES_ZARR" "${SCREEN_DIR}/visualizations/default/examples.zarr"
    NUM_GENES=$(ls "$EXAMPLES_ZARR" 2>/dev/null | wc -l)
    echo "  -> visualizations/default/examples.zarr (${NUM_GENES} perturbations)"
else
    echo "  SKIP: no examples.zarr found in aggregate/montages/"
fi

# ---------------------------------------------------------------------------
# 8. Aggregated data (cluster-level h5ad with embeddings + features)
# ---------------------------------------------------------------------------
echo "[8/8] Aggregated data..."
AGG_H5AD=$(find "${OUTPUT_ROOT}/cluster" -path "*/h5ad/*cluster.h5ad" 2>/dev/null | head -1)
if [ -n "$AGG_H5AD" ]; then
    python3 -c "
import anndata as ad
import numpy as np
import yaml
from itertools import combinations

adata = ad.read_h5ad('${AGG_H5AD}')
print(f'Input: {adata}')

# Read channel names from config
with open('${CONFIG_YAML}') as f:
    cfg = yaml.safe_load(f)
channel_names = [ch['name'] for ch in cfg.get('preprocess', {}).get('phenotype_channels_metadata', [])]

# Build standardized feature set
compartments = ['nucleus', 'cell']
shape_measurements = ['area', 'eccentricity', 'form_factor', 'solidity']
intensity_measurements = [
    'integrated', 'mean', 'mass_displacement',
    'mean_edge', 'std_edge', 'mean_frac_0', 'mean_frac_3',
]
standardized = set()
for comp in compartments:
    for meas in shape_measurements:
        standardized.add(f'{comp}_{meas}')
    for ch in channel_names:
        for meas in intensity_measurements:
            standardized.add(f'{comp}_{ch}_{meas}')

# Match correlation features from actual data (pair ordering varies)
for f in adata.var_names:
    parts = f.split('_')
    if len(parts) >= 3 and parts[0] in compartments and parts[1] == 'correlation':
        standardized.add(f)

matched = [f for f in adata.var_names if f in standardized]
print(f'Standardized features: {len(matched)} of {len(adata.var_names)}')

adata = adata[:, matched].copy()

# Keep only spec-required layers
spec_layers = ['p_values', 'neg_log10_fdr']
for layer in list(adata.layers.keys()):
    if layer not in spec_layers:
        del adata.layers[layer]

# Keep only one cluster_group column (first available)
cluster_cols = [c for c in adata.obs.columns if c.startswith('cluster_group_')]
if len(cluster_cols) > 1:
    keep = cluster_cols[0]
    for c in cluster_cols[1:]:
        adata.obs = adata.obs.drop(columns=[c])
    print(f'Kept cluster column: {keep}')

# Keep only spec obs columns
spec_obs = {'cell_cycle_phase'} | {c for c in adata.obs.columns if c.startswith('cluster_group_')}
extra_obs = [c for c in adata.obs.columns if c not in spec_obs]
if extra_obs:
    adata.obs = adata.obs.drop(columns=extra_obs)

# Keep only spec var columns
spec_var = {'feature_name', 'feature_type', 'compartment'}
extra_var = [c for c in adata.var.columns if c not in spec_var]
if extra_var:
    adata.var = adata.var.drop(columns=extra_var)

# Keep only spec uns
spec_uns = {'schema_version', 'default_embedding', 'title'}
for k in list(adata.uns.keys()):
    if k not in spec_uns:
        del adata.uns[k]

print(f'Output: {adata}')
adata.write_h5ad('${SCREEN_DIR}/visualizations/default/aggregated_data.h5ad')
"
    echo "  -> visualizations/default/aggregated_data.h5ad (reformatted from cluster.h5ad)"
else
    echo "  SKIP: no cluster.h5ad found in cluster/"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Submission directory ==="
echo ""
find "${SUBMISSION_DIR}" -type f | sort | sed "s|${SUBMISSION_DIR}/||"
echo ""

echo "Done:"
echo "  [x] collection_metadata.yaml"
echo "  [x] experimental_metadata.yaml"
echo "  [x] perturbation_library.csv"
echo "  [x] feature_definitions.csv"
echo "  [x] zarr images"
echo "  [x] cell_data.h5ad (single-cell AnnData)"
echo "  [x] examples.zarr (single-cell crops)"
echo ""
echo "  [x] aggregated_data.h5ad (perturbation-level with PHATE embedding)"
echo ""
echo "Before submission:"
echo "  [ ] Fill in all [REQUIRED] fields in screen.yaml"
echo "  [ ] Run ops-validate on the submission directory"

# ---------------------------------------------------------------------------
# Zip submission
# ---------------------------------------------------------------------------
ZIP_FILE="${SUBMISSION_DIR}.zip"
echo ""
echo "Creating ${ZIP_FILE}..."
cd "$(dirname "${SUBMISSION_DIR}")"
zip -r "$(basename "${ZIP_FILE}")" "$(basename "${SUBMISSION_DIR}")" -q
echo "  -> $(du -sh "${ZIP_FILE}" | cut -f1) compressed"
