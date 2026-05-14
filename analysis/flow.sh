#!/bin/bash
# =============================================================================
# flow.sh - Unified brieflow pipeline runner
# =============================================================================
#
# Usage:
#   bash flow.sh <module> [module2 ...] [options]
#
# Modules:
#   preprocess, sbs, phenotype, merge, aggregate, cluster, mozzarellm, viz, all
#
# Options:
#   --backend local|slurm   Execution backend (default: local)
#   --dry-run, -n           Show what would run without executing
#   --sequential-plates     Process plates one at a time (auto-detects count)
#   --plates N              Override plate count for sequential processing
#   --unlock                Force unlock before running
#   --cores N               Number of cores for local backend (default: all)
#   --profile               Enable profiling mode: keep all slurm logs, generate
#                           efficiency report, verbose job output (default: off)
#   --forcerun rule1,rule2  Force-rerun the listed rules even if outputs are
#                           up-to-date (snakemake --forcerun pass-through).
#                           Use after editing a rule's script so mtime caching
#                           doesn't silently skip the change.
#   --help, -h              Show this help message
#
# Examples:
#   bash flow.sh preprocess --dry-run
#   bash flow.sh sbs phenotype --backend slurm --sequential-plates
#   bash flow.sh aggregate --backend slurm --profile
#   bash flow.sh all --dry-run
#   bash flow.sh mozzarellm
#   bash flow.sh viz
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SNAKEFILE="../brieflow/workflow/Snakefile"
CONFIGFILE="config/config.yml"
LOG_DIR="logs"
SLURM_PROFILE="slurm/"
SLURM_ARRAY_LIMIT=10
LATENCY_WAIT=10
MAX_STATUS_CHECKS=""

# Rule groups per module (for slurm batching)
SBS_GROUPS=(
    "align_sbs=sbs_tile_group"
    "log_filter=sbs_tile_group"
    "max_filter=sbs_tile_group"
    "compute_standard_deviation=sbs_tile_group"
    "find_peaks=sbs_tile_group"
    "apply_ic_field_sbs=sbs_tile_group"
    "segment_sbs=sbs_tile_group"
    "extract_sbs_info=sbs_tile_group"
    "extract_bases=sbs_tile_group"
    "call_reads=sbs_tile_group"
    "call_cells=sbs_tile_group"
)

PHENOTYPE_GROUPS=(
    "apply_ic_field_phenotype=phenotype_tile_group"
    "align_phenotype=phenotype_tile_group"
    "segment_phenotype=phenotype_tile_group"
    "extract_phenotype_info=phenotype_tile_group"
    "identify_cytoplasm=phenotype_tile_group"
    "extract_phenotype=phenotype_tile_group"
)

# Modules that support sequential plate processing
PLATE_SEQUENTIAL_MODULES="preprocess sbs phenotype"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
BACKEND="local"
DRY_RUN=false
SEQUENTIAL_PLATES=false
PLATE_COUNT=""
FORCE_UNLOCK=false
CORES="all"
PROFILE_MODE=false
NO_ARRAYS=false
MODULES=()
EXTRA_CONFIG=""
# Snakemake --forcerun passthrough (HARDENING #7 layer 1): comma-separated
# list of rules to force-rerun even if their outputs are up-to-date.
# Use after editing a rule's script so mtime-based caching doesn't silently
# skip the change.
FORCERUN=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
show_help() {
    head -35 "$0" | tail -31
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)
            BACKEND="$2"; shift 2 ;;
        --dry-run|-n)
            DRY_RUN=true; shift ;;
        --sequential-plates)
            SEQUENTIAL_PLATES=true; shift ;;
        --plates)
            SEQUENTIAL_PLATES=true; PLATE_COUNT="$2"; shift 2 ;;
        --unlock)
            FORCE_UNLOCK=true; shift ;;
        --cores)
            CORES="$2"; shift 2 ;;
        --profile)
            PROFILE_MODE=true; shift ;;
        --config)
            EXTRA_CONFIG="$2"; shift 2 ;;
        --configfile)
            CONFIGFILE="$2"; shift 2 ;;
        --slurm-profile)
            SLURM_PROFILE="$2"; shift 2 ;;
        --slurm-array-limit)
            SLURM_ARRAY_LIMIT="$2"; shift 2 ;;
        --no-arrays)
            NO_ARRAYS=true; shift ;;
        --latency-wait)
            LATENCY_WAIT="$2"; shift 2 ;;
        --max-status-checks)
            MAX_STATUS_CHECKS="$2"; shift 2 ;;
        --forcerun)
            FORCERUN="$2"; shift 2 ;;
        --help|-h)
            show_help ;;
        -*)
            echo "ERROR: Unknown option: $1"; exit 1 ;;
        *)
            MODULES+=("$1"); shift ;;
    esac
done

if [[ ${#MODULES[@]} -eq 0 ]]; then
    echo "ERROR: No module specified. Use --help for usage."
    exit 1
fi

# Expand "all" to all pipeline modules
if [[ " ${MODULES[*]} " == *" all "* ]]; then
    MODULES=(preprocess sbs phenotype merge aggregate cluster)
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
timestamp() {
    date +%Y%m%d_%H%M%S
}

elapsed() {
    local duration=$1
    printf "%dh %dm %ds" $((duration / 3600)) $(((duration % 3600) / 60)) $((duration % 60))
}

setup_logging() {
    local module_name="$1"
    mkdir -p "${SCRIPT_DIR}/${LOG_DIR}"
    local log_file="${SCRIPT_DIR}/${LOG_DIR}/${module_name}-$(timestamp).log"
    echo "$log_file"
}

auto_detect_plates() {
    # Count plates from SBS samples file (fallback to phenotype samples)
    local plates
    plates=$(python3 -c "
import yaml, pandas as pd
with open('${CONFIGFILE}') as f:
    config = yaml.safe_load(f)
for key in ['sbs_samples_fp', 'phenotype_samples_fp']:
    fp = config.get('preprocess', {}).get(key, '')
    if fp:
        try:
            df = pd.read_csv(fp, sep='\t')
            print(df['plate'].nunique())
            break
        except Exception:
            continue
" 2>/dev/null)
    echo "${plates:-0}"
}

check_unlock() {
    if [[ -d "${SCRIPT_DIR}/.snakemake/locks" ]] && [[ -n "$(ls -A "${SCRIPT_DIR}/.snakemake/locks" 2>/dev/null)" ]]; then
        echo "Detected snakemake lock. Unlocking..."
        snakemake --unlock \
            --snakefile "$SNAKEFILE" \
            --configfile "$CONFIGFILE" 2>/dev/null || true
    fi
}

# ---------------------------------------------------------------------------
# Snakemake invocation builder
# ---------------------------------------------------------------------------
build_snakemake_cmd() {
    local target="$1"
    local plate_filter="${2:-}"

    local cmd="snakemake"

    # Backend-specific flags
    if [[ "$BACKEND" == "slurm" ]]; then
        cmd+=" --executor slurm"
        cmd+=" --workflow-profile ${SLURM_PROFILE}"
        if [[ "$NO_ARRAYS" != true ]]; then
            cmd+=" --slurm-array-jobs=all"
            cmd+=" --slurm-array-limit=${SLURM_ARRAY_LIMIT}"
        fi
        cmd+=" --slurm-jobname-prefix=brieflow"
        cmd+=" --slurm-logdir=slurm/slurm_output/rule"
        cmd+=" --latency-wait ${LATENCY_WAIT}"
        if [[ -n "$MAX_STATUS_CHECKS" ]]; then
            cmd+=" --max-status-checks-per-second ${MAX_STATUS_CHECKS}"
        fi
        cmd+=" --keep-going"

        # Profile mode: retain all logs + efficiency report
        if [[ "$PROFILE_MODE" == true ]]; then
            cmd+=" --slurm-keep-successful-logs"
            cmd+=" --slurm-efficiency-report"
            cmd+=" --slurm-efficiency-report-path=${SCRIPT_DIR}/${LOG_DIR}/efficiency_$(timestamp).log"
        fi
    else
        cmd+=" --cores ${CORES} --keep-going"
    fi

    # Common flags
    cmd+=" --snakefile ${SNAKEFILE}"
    cmd+=" --configfile ${CONFIGFILE}"
    cmd+=" --rerun-triggers mtime"
    # --rerun-incomplete: snakemake tracks files whose write-side started but
    # whose job never marked completion (slurm OOM-kill, SIGKILL, node crash).
    # Default behavior throws IncompleteFilesException at DAG-build time,
    # blocking ALL execution. With --rerun-incomplete, snakemake re-runs
    # those specific jobs to completion. Caught 2026-05-10 baker v22 phase 2:
    # 222 align_phenotype zarr.json files marked incomplete from v20's
    # OOM-killed attempts blocked DAG build entirely.
    cmd+=" --rerun-incomplete"
    # --forcerun: HARDENING #7 layer 1. Comma-separated list translated into
    # snakemake's space-separated --forcerun rules. Use after editing a
    # rule's script — mtime-only triggers will silently skip the change
    # otherwise (caught 2026-05-12 baker v26 format_merge silent skip).
    if [[ -n "$FORCERUN" ]]; then
        local forcerun_rules="${FORCERUN//,/ }"
        cmd+=" --forcerun ${forcerun_rules}"
    fi
    cmd+=" --until ${target}"
    # --verbose: preserves the plugin's array-submission debug logs ("call with array:")
    # so every run captures the wrap content per chunk. Cheap, useful for diagnosing the
    # wrap-target collision documented in COLLAB.md Phase 7.
    cmd+=" --verbose"

    # Dry run
    if [[ "$DRY_RUN" == true ]]; then
        cmd+=" -n"
    fi

    # Config overrides (plate filter + user-provided)
    local config_args=""
    if [[ -n "$plate_filter" ]]; then
        config_args+=" plate_filter=${plate_filter}"
    fi
    if [[ -n "$EXTRA_CONFIG" ]]; then
        config_args+=" ${EXTRA_CONFIG}"
    fi
    if [[ -n "$config_args" ]]; then
        cmd+=" --config${config_args}"
    fi

    echo "$cmd"
}

get_groups_flag() {
    # ALWAYS emit both SBS and PHENOTYPE groups regardless of which module is
    # being run. The grouping is metadata about how rules should be bundled
    # when their wildcards align — declaring it doesn't force any rule to run.
    # Without this, downstream phases (merge/aggregate/cluster) that incidentally
    # need to re-materialize per-tile sbs/phenotype outputs schedule them as
    # standalone slurm jobs at the un-grouped per-rule mem cap, which OOMs
    # because phenotype tile dimensions need ~4× per-rule mem (2400×2400 vs
    # 1200×1200 for sbs). Caught 2026-05-10 baker v20 phase 4: 1247
    # align_phenotype OOMs in one attempt before the cap was bumped.
    # The module argument is now unused but kept for API compat.
    local _module_unused="$1"
    local groups_flag="--groups"
    for g in "${SBS_GROUPS[@]}"; do
        groups_flag+=" ${g}"
    done
    for g in "${PHENOTYPE_GROUPS[@]}"; do
        groups_flag+=" ${g}"
    done
    echo "$groups_flag"
}

# ---------------------------------------------------------------------------
# Module runners
# ---------------------------------------------------------------------------
run_snakemake_module() {
    local module="$1"
    local target="all_${module}"

    echo ""
    echo "===== ${module^^} ====="
    echo "Backend: ${BACKEND} | Dry run: ${DRY_RUN} | Started: $(date)"
    echo ""

    local module_start
    module_start=$(date +%s)

    # Check if this module should run with sequential plates
    local use_plates=false
    if [[ "$SEQUENTIAL_PLATES" == true ]] && [[ " $PLATE_SEQUENTIAL_MODULES " == *" $module "* ]]; then
        use_plates=true
    fi

    if [[ "$use_plates" == true ]]; then
        # Determine plate count
        local num_plates="${PLATE_COUNT}"
        if [[ -z "$num_plates" ]]; then
            num_plates=$(auto_detect_plates)
        fi

        if [[ "$num_plates" -eq 0 ]] || [[ -z "$num_plates" ]]; then
            echo "ERROR: Could not determine plate count. Use --plates N to specify."
            return 1
        fi

        echo "Sequential plate processing: ${num_plates} plates"
        echo ""

        for plate in $(seq 1 "$num_plates"); do
            echo "--- Plate ${plate}/${num_plates} ($(date)) ---"
            local plate_start
            plate_start=$(date +%s)

            local cmd
            cmd=$(build_snakemake_cmd "$target" "$plate")

            # Add groups for slurm
            if [[ "$BACKEND" == "slurm" ]]; then
                local groups
                groups=$(get_groups_flag "$module")
                if [[ -n "$groups" ]]; then
                    cmd+=" ${groups}"
                fi
            fi

            eval "$cmd"
            local exit_code=$?

            local plate_end
            plate_end=$(date +%s)
            echo "Plate ${plate} finished in $(elapsed $((plate_end - plate_start)))"

            if [[ $exit_code -ne 0 ]]; then
                echo "ERROR: Plate ${plate} failed (exit code ${exit_code})"
                return $exit_code
            fi

            # Brief pause between plates (skip on dry run)
            if [[ "$DRY_RUN" != true ]] && [[ "$plate" -lt "$num_plates" ]]; then
                sleep 5
            fi
        done
    else
        local cmd
        cmd=$(build_snakemake_cmd "$target")

        # Add groups for slurm
        if [[ "$BACKEND" == "slurm" ]]; then
            local groups
            groups=$(get_groups_flag "$module")
            if [[ -n "$groups" ]]; then
                cmd+=" ${groups}"
            fi
        fi

        eval "$cmd"
    fi

    local module_end
    module_end=$(date +%s)
    echo ""
    echo "${module^^} completed in $(elapsed $((module_end - module_start)))"
}

run_mozzarellm() {
    echo ""
    echo "===== MOZZARELLM ====="
    echo "Started: $(date)"
    echo ""

    cd "$SCRIPT_DIR"
    python3 << 'MOZZARELLM_SCRIPT'
"""Mozzarellm analysis - reads all configuration from config.yml"""

import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from mozzarellm import ClusterAnalyzer, reshape_to_clusters

load_dotenv()

CONFIG_PATH = Path("config/config.yml")
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

if "mozzarellm" not in config:
    print("ERROR: mozzarellm section not found in config.yml")
    print("Please run notebook 12 to configure mozzarellm parameters.")
    sys.exit(1)

mzlm_config = config["mozzarellm"]

ROOT_FP = Path(config["all"]["root_fp"])
CELL_CLASS = mzlm_config["cell_class"]
CHANNEL_COMBO = mzlm_config["channel_combo"]
RESOLUTION = mzlm_config["leiden_resolution"]
MODEL = mzlm_config.get("model", "claude-sonnet-4-5-20250929")
TEMPERATURE = mzlm_config.get("temperature", 0.0)
SCREEN_CONTEXT = mzlm_config.get("screen_context", "")
GENE_COL = config["aggregate"]["perturbation_name_col"]

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

if not cluster_file.exists():
    print(f"ERROR: Clustering file not found: {cluster_file}")
    print(f"Make sure you have run the cluster module first.")
    sys.exit(1)

print("Loading clustering data...")
gene_df = pd.read_csv(cluster_file, sep="\t")

if GENE_COL not in gene_df.columns:
    for alt in ["gene_symbol_0", "gene_symbol", "gene"]:
        if alt in gene_df.columns:
            gene_df = gene_df.rename(columns={alt: GENE_COL})
            break

print(f"Loaded {len(gene_df)} genes across {gene_df['cluster'].nunique()} clusters")

print("Reshaping data to cluster format...")
cluster_df, gene_annotations = reshape_to_clusters(
    input_df=gene_df,
    gene_col=GENE_COL,
    cluster_col="cluster",
    uniprot_col="uniprot_function",
    verbose=True,
)
print(f"Reshaped to {len(cluster_df)} clusters")

print("\nRunning LLM analysis...")
analyzer = ClusterAnalyzer(model=MODEL, temperature=TEMPERATURE, show_progress=True)

results = analyzer.analyze(
    cluster_df,
    gene_annotations=gene_annotations,
    screen_context=SCREEN_CONTEXT,
    output_dir=output_dir,
)

print(f"\nDone!")
print(f"Results saved to: {output_dir}")

MOZZARELLM_SCRIPT
}

run_viz() {
    echo ""
    echo "===== VISUALIZATION ====="
    echo "Starting Streamlit server..."
    echo ""

    cd "$SCRIPT_DIR"
    export BRIEFLOW_OUTPUT_PATH="brieflow_output/"
    export CONFIG_PATH="config/config.yml"
    export SCREEN_PATH="screen.yaml"
    exec streamlit run ../brieflow/visualization/Experimental_Overview.py --server.address=0.0.0.0 "$@"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
cd "$SCRIPT_DIR"

# Set up logging (tee all output to log file)
log_label=$(IFS=_; echo "${MODULES[*]}")
LOG_FILE=$(setup_logging "$log_label")
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo "  flow.sh | $(date)"
echo "  Modules: ${MODULES[*]}"
echo "  Backend: ${BACKEND}"
echo "  Profile: ${PROFILE_MODE}"
echo "  Dry run: ${DRY_RUN}"
echo "  Log: ${LOG_FILE}"
echo "============================================================"

# Start timing
TOTAL_START=$(date +%s)

# Auto-unlock if needed
if [[ "$FORCE_UNLOCK" == true ]]; then
    check_unlock
elif [[ -d ".snakemake/locks" ]] && [[ -n "$(ls -A .snakemake/locks 2>/dev/null)" ]]; then
    echo ""
    echo "Detected snakemake lock. Auto-unlocking..."
    check_unlock
fi

# Run each module
for module in "${MODULES[@]}"; do
    case "$module" in
        preprocess|sbs|phenotype|merge|aggregate|cluster)
            run_snakemake_module "$module"
            ;;
        mozzarellm)
            run_mozzarellm
            ;;
        viz)
            run_viz
            ;;
        *)
            echo "ERROR: Unknown module: ${module}"
            echo "Valid modules: preprocess, sbs, phenotype, merge, aggregate, cluster, mozzarellm, viz, all"
            exit 1
            ;;
    esac
done

# Final summary
TOTAL_END=$(date +%s)
echo ""
echo "============================================================"
echo "  All modules completed in $(elapsed $((TOTAL_END - TOTAL_START)))"
echo "  Log saved to: ${LOG_FILE}"
echo "============================================================"
