#!/bin/bash
# =============================================================================
# 13.run_mozzarellm.sh - Run mozzarellm analysis from config
# =============================================================================
#
# This script runs mozzarellm LLM analysis on clustering results.
# Configuration is read from config/config.yml (set up in notebook 12).
#
# Features:
#   - Config-driven: All parameters read from config.yml
#   - Resume support: Automatically skips completed clusters (via output_dir)
#   - Incremental saving: Results saved after each cluster
#
# Usage:
#   bash 13.run_mozzarellm.sh
#
# =============================================================================

set -e
cd "$(dirname "$0")"

echo "Running mozzarellm analysis..."
echo "Reading configuration from config/config.yml"
echo ""

python3 << 'MOZZARELLM_SCRIPT'
"""Mozzarellm analysis - reads all configuration from config.yml"""

import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from mozzarellm import ClusterAnalyzer, reshape_to_clusters

# Load environment variables (.env file for API keys)
load_dotenv()

# =============================================================================
# Load configuration
# =============================================================================

CONFIG_PATH = Path("config/config.yml")
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

# Check if mozzarellm is configured
if "mozzarellm" not in config:
    print("ERROR: mozzarellm section not found in config.yml")
    print("Please run notebook 12 to configure mozzarellm parameters.")
    sys.exit(1)

mzlm_config = config["mozzarellm"]

# Extract parameters
ROOT_FP = Path(config["all"]["root_fp"])
CELL_CLASS = mzlm_config["cell_class"]
CHANNEL_COMBO = mzlm_config["channel_combo"]
RESOLUTION = mzlm_config["leiden_resolution"]
MODEL = mzlm_config.get("model", "claude-sonnet-4-5-20250929")
TEMPERATURE = mzlm_config.get("temperature", 0.0)
SCREEN_CONTEXT = mzlm_config.get("screen_context", "")
GENE_COL = config["aggregate"]["perturbation_name_col"]

# Build paths
cluster_path = ROOT_FP / "cluster" / CHANNEL_COMBO / CELL_CLASS / str(RESOLUTION)

cluster_file = cluster_path / "phate_leiden_clustering.tsv"
output_dir = cluster_path / "mozzarellm"

print(f"Mozzarellm Analysis")
print(f"{'=' * 60}")
print(f"Model: {MODEL}")
print(f"Cell class: {CELL_CLASS}")
print(f"Channel combo: {CHANNEL_COMBO}")
print(f"Resolution: {RESOLUTION}")
print(f"Input: {cluster_file}")
print(f"Output: {output_dir}")
print(f"{'=' * 60}")
print()

# Verify input exists
if not cluster_file.exists():
    print(f"ERROR: Clustering file not found: {cluster_file}")
    print(f"Make sure you have run the cluster module first.")
    sys.exit(1)

# =============================================================================
# Run analysis
# =============================================================================

# Load clustering data
print("Loading clustering data...")
gene_df = pd.read_csv(cluster_file, sep="\t")

# Handle gene column variations
if GENE_COL not in gene_df.columns:
    for alt in ["gene_symbol_0", "gene_symbol", "gene"]:
        if alt in gene_df.columns:
            gene_df = gene_df.rename(columns={alt: GENE_COL})
            break

print(f"Loaded {len(gene_df)} genes across {gene_df['cluster'].nunique()} clusters")

# Reshape to cluster format
print("Reshaping data to cluster format...")
cluster_df, gene_annotations = reshape_to_clusters(
    input_df=gene_df,
    gene_col=GENE_COL,
    cluster_col="cluster",
    uniprot_col="uniprot_function",
    verbose=True,
)
print(f"Reshaped to {len(cluster_df)} clusters")

# Initialize analyzer and run with built-in resume/save support
print("\nRunning LLM analysis...")
analyzer = ClusterAnalyzer(model=MODEL, temperature=TEMPERATURE, show_progress=True)

results = analyzer.analyze(
    cluster_df,
    gene_annotations=gene_annotations,
    screen_context=SCREEN_CONTEXT,
    output_dir=output_dir,  # Enables resume + incremental saving
)

print(f"\nDone!")
print(f"Results saved to: {output_dir}")

MOZZARELLM_SCRIPT
