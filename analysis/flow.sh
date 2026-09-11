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
#   --only-plate N          Run only plate N, no looping (mutually exclusive
#                           with --sequential-plates / --plates)
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
LATENCY_WAIT=5
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
SEQUENTIAL_PLATES=true
SEQUENTIAL_PLATES_EXPLICIT=false
PLATE_COUNT=""
ONLY_PLATE=""
FORCE_UNLOCK=false
CORES="all"
# --jobs (max concurrent jobs): an explicit --jobs wins; otherwise resolved from
# CORES after arg parsing (nproc when CORES=all). Must be an integer (or `unlimited`).
JOBS=""
PROFILE_MODE=false
NO_ARRAYS=false
MODULES=()
EXTRA_CONFIG=""
# Snakemake --forcerun passthrough (HARDENING #7 layer 1): comma-separated
# list of rules to force-rerun even if their outputs are up-to-date.
# Use after editing a rule's script so mtime-based caching doesn't silently
# skip the change.
FORCERUN=""

# HARDENING #23: resolve per-rule mem caps from scaling formulas + geometry
# + mem_recommendations.json before launching snakemake. The resolver lives
# in the brieflow-ops plugin; we invoke it once per flow.sh run and pass its
# output to snakemake as --set-resources. Set BRIEFLOW_SKIP_RESOLVE=1 to
# disable (falls back to slurm/config.yaml set-resources floor only).
# Plugin location is auto-discovered: BRIEFLOW_OPS_PLUGIN_DIR wins, then the
# Claude Code plugin cache, then on-VM /data checkouts, then the HPC paths.
# Before this auto-discovery the default pointed ONLY at the HPC path, so on a
# cloud VM the resolver silently no-op'd → no per-rule mem caps reached
# snakemake → aggregate OOM (damavand 2026-06-13). The HPC default still works
# unchanged.
_find_plugin_dir() {
    local cands=() d
    [ -n "${BRIEFLOW_OPS_PLUGIN_DIR:-}" ] && cands+=("${BRIEFLOW_OPS_PLUGIN_DIR}")
    cands+=( "${HOME}"/.claude/plugins/cache/brieflow-auto/brieflow-auto/* )
    cands+=( /data/*/brieflow-auto/plugins/brieflow-auto )
    cands+=( /data/*/.ba-push/plugins/brieflow-auto )
    cands+=( /lab/barcheese01/mdiberna/brieflow-auto/plugins/brieflow-auto )
    cands+=( /lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops )
    for d in "${cands[@]}"; do
        if [ -x "${d}/scripts/brieflow_resolve_resources.py" ]; then
            printf '%s\n' "${d}"; return 0
        fi
    done
    return 1
}
PLUGIN_DIR="$(_find_plugin_dir || echo "")"
RESOLVED_SET_RESOURCES=""
if [ -z "${BRIEFLOW_SKIP_RESOLVE:-}" ] && [ -n "${PLUGIN_DIR}" ] && [ -x "${PLUGIN_DIR}/scripts/brieflow_resolve_resources.py" ]; then
    RESOLVED_SET_RESOURCES=$(python "${PLUGIN_DIR}/scripts/brieflow_resolve_resources.py" \
        --analysis-dir "${SCRIPT_DIR}" --format snakemake 2>/dev/null || echo "")
fi

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
show_help() {
    # Marker-based (not a fixed line-count slice): prints from the first to the
    # last "# ===...===" separator line, so header edits never desync this from
    # the actual comment block above.
    local first last
    first=$(grep -n '^# =\{10,\}$' "$0" | head -1 | cut -d: -f1)
    last=$(grep -n '^# =\{10,\}$' "$0" | tail -1 | cut -d: -f1)
    sed -n "${first},${last}p" "$0"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)
            BACKEND="$2"; shift 2 ;;
        --dry-run|-n)
            DRY_RUN=true; shift ;;
        --sequential-plates)
            SEQUENTIAL_PLATES=true; SEQUENTIAL_PLATES_EXPLICIT=true; shift ;;
        --plates)
            SEQUENTIAL_PLATES=true; SEQUENTIAL_PLATES_EXPLICIT=true; PLATE_COUNT="$2"; shift 2 ;;
        --only-plate)
            ONLY_PLATE="$2"; shift 2 ;;
        --unlock)
            FORCE_UNLOCK=true; shift ;;
        --cores)
            CORES="$2"; shift 2 ;;
        --jobs)
            JOBS="$2"; shift 2 ;;
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

# --only-plate scopes a run to exactly one plate (no loop); it reuses the same
# plate_filter config key --sequential-plates/--plates use per iteration, so
# the two modes are mutually exclusive.
if [[ -n "$ONLY_PLATE" ]] && [[ "$SEQUENTIAL_PLATES_EXPLICIT" == true ]]; then
    echo "ERROR: --only-plate cannot be combined with --sequential-plates or --plates. Pick one plate-scoping mode."
    exit 1
fi

# Resolve --jobs after parsing: an explicit --jobs wins; otherwise derive from
# CORES (nproc when CORES=all). Keeps backend selection seamless — flow.sh emits
# a valid --jobs for both local and slurm without needing to be hand-edited.
if [[ -z "${JOBS}" ]]; then
    JOBS="$([ "${CORES}" = "all" ] && nproc || echo "${CORES}")"
fi

if [[ ${#MODULES[@]} -eq 0 ]]; then
    echo "ERROR: No module specified. Use --help for usage."
    exit 1
fi

# Expand "all" to all pipeline modules
if [[ " ${MODULES[*]} " == *" all "* ]]; then
    MODULES=(preprocess sbs phenotype merge aggregate cluster)
fi

PHASE_GATE_CONFIG=""
ALL_PIPELINE_PHASES=(preprocess sbs phenotype merge aggregate cluster)
disabled_phases=()
for phase in "${ALL_PIPELINE_PHASES[@]}"; do
    if [[ ! " ${MODULES[*]} " == *" ${phase} "* ]]; then
        disabled_phases+=("$phase")
        PHASE_GATE_CONFIG+=" ${phase}_rules_enabled=false"
    fi
done
if [[ ${#disabled_phases[@]} -gt 0 && ${#disabled_phases[@]} -lt ${#ALL_PIPELINE_PHASES[@]} ]]; then
    echo "Phase rule-gates: disabled $(IFS=,; echo "${disabled_phases[*]}") (targets still loaded)"
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
        # snakemake's slurm executor requires --jobs (max concurrent slurm jobs).
        cmd+=" --jobs ${JOBS}"
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
        cmd+=" --cores ${CORES} --jobs ${JOBS} --keep-going"
        # Local backend: snakemake only enforces memory throttling when a global
        # mem_mb *budget* is declared via --resources. Without it the per-rule
        # mem_mb caps (--set-resources, below) are ignored and heavy rules
        # over-schedule → OOM (hit live on damavand: 8× format_singlecell_anndata
        # at --cores 288 blew past 2.8 TB). Default the budget to ~90% of machine
        # RAM (OS/driver headroom); override with BRIEFLOW_LOCAL_MEM_MB.
        local _mem_budget="${BRIEFLOW_LOCAL_MEM_MB:-}"
        if [ -z "${_mem_budget}" ]; then
            local _mem_total
            _mem_total=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
            _mem_budget=$(( _mem_total * 90 / 100 ))
        fi
        if [ "${_mem_budget:-0}" -gt 0 ]; then
            cmd+=" --resources mem_mb=${_mem_budget}"
        fi
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
    # --set-resources from the HARDENING #23 resolver (formulas × geometry
    # × mem_recommendations.json). Appended BEFORE --until so snakemake's
    # arg parser treats them as positional set-resources entries.
    if [ -n "$RESOLVED_SET_RESOURCES" ]; then
        cmd+=" --set-resources ${RESOLVED_SET_RESOURCES}"
    fi
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

    # Config overrides (plate filter + phase gates + user-provided)
    local config_args=""
    if [[ -n "$plate_filter" ]]; then
        config_args+=" plate_filter=${plate_filter}"
    fi
    if [[ -n "$PHASE_GATE_CONFIG" ]]; then
        config_args+="${PHASE_GATE_CONFIG}"
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

    # --only-plate: scope to exactly one plate via the same plate_filter config
    # key the sequential loop below uses per-iteration, but without looping.
    local use_only_plate=false
    if [[ -n "$ONLY_PLATE" ]] && [[ " $PLATE_SEQUENTIAL_MODULES " == *" $module "* ]]; then
        use_only_plate=true
    fi

    if [[ "$use_only_plate" == true ]]; then
        echo "Single plate processing: plate ${ONLY_PLATE}"
        echo ""

        local cmd
        cmd=$(build_snakemake_cmd "$target" "$ONLY_PLATE")

        # Add groups for slurm
        if [[ "$BACKEND" == "slurm" ]]; then
            local groups
            groups=$(get_groups_flag "$module")
            if [[ -n "$groups" ]]; then
                cmd+=" ${groups}"
            fi
        fi

        eval "$cmd"
    elif [[ "$use_plates" == true ]]; then
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

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, "../brieflow/workflow")

try:
    from lib.cluster.mozzarellm_io import run_mozzarellm
except ImportError as err:
    print(f"ERROR: mozzarellm support is not installed ({err})")
    print('Install it with: python -m pip install -e "../brieflow[mozzarellm]"')
    sys.exit(1)

load_dotenv()

CONFIG_PATH = Path("config/config.yml")
SCREEN_PATH = Path("screen.yaml")

with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

if "mozzarellm" not in config:
    print("ERROR: mozzarellm section not found in config.yml")
    print("Please run notebook 12 to configure mozzarellm parameters.")
    sys.exit(1)

if not SCREEN_PATH.exists():
    print(f"ERROR: screen description not found: {SCREEN_PATH}")
    print("The screen context handed to the model is derived from screen.yaml.")
    sys.exit(1)

with open(SCREEN_PATH) as f:
    screen = yaml.safe_load(f)

mzlm_config = config["mozzarellm"]

ROOT_FP = Path(config["all"]["root_fp"])
CELL_CLASS = mzlm_config["cell_class"]
CHANNEL_COMBO = mzlm_config["channel_combo"]
COMPARTMENT_COMBO = mzlm_config.get("compartment_combo")
RESOLUTION = mzlm_config["leiden_resolution"]
MODEL = mzlm_config.get("model", "claude-sonnet-5")
MODE = mzlm_config.get("mode", "cot")
MCP = mzlm_config.get("mcp", False)
INCLUDE_FEATURES = mzlm_config.get("include_features", True)
N_FEATURES = mzlm_config.get("n_features", 5)
FDR_THRESHOLD = mzlm_config.get("fdr_threshold")
MAX_TOKENS = mzlm_config.get("max_tokens", 16000)

SPLIT_BY_COMPARTMENT = config["aggregate"].get("split_by_compartment", False)

if SPLIT_BY_COMPARTMENT and not COMPARTMENT_COMBO:
    print("ERROR: aggregate.split_by_compartment is on but mozzarellm.compartment_combo is not set")
    print("Please rerun notebook 12 with COMPARTMENT_COMBO set.")
    sys.exit(1)

# mozzarellm picks the provider from the model prefix, so check that provider's key
if MODEL.lower().startswith(("gpt", "o1", "o3", "o4")):
    API_KEY_VAR = "OPENAI_API_KEY"
elif MODEL.lower().startswith("gemini"):
    API_KEY_VAR = "GOOGLE_API_KEY"
else:
    API_KEY_VAR = "ANTHROPIC_API_KEY"

if not os.environ.get(API_KEY_VAR):
    print(f"ERROR: {API_KEY_VAR} not found (required by model '{MODEL}')")
    print("Add it to a .env file in the analysis directory.")
    sys.exit(1)

cluster_base = ROOT_FP / "cluster" / CHANNEL_COMBO
if SPLIT_BY_COMPARTMENT:
    cluster_base = cluster_base / COMPARTMENT_COMBO
cluster_dir = cluster_base / CELL_CLASS / str(RESOLUTION)
h5ad_path = cluster_base / CELL_CLASS / "h5ad" / "cluster.h5ad"

print("Mozzarellm Analysis")
print(f"{'=' * 60}")
print(f"Model: {MODEL}")
print(f"Mode: {MODE} (mcp={MCP}, include_features={INCLUDE_FEATURES})")
print(f"Cell class: {CELL_CLASS}")
print(f"Channel combo: {CHANNEL_COMBO}")
if SPLIT_BY_COMPARTMENT:
    print(f"Compartment combo: {COMPARTMENT_COMBO}")
print(f"Resolution: {RESOLUTION}")
print(f"Input: {h5ad_path}")
print(f"Output: {cluster_dir / 'mozzarellm'}")
print(f"{'=' * 60}")
print()

if not h5ad_path.exists():
    print(f"ERROR: Cluster AnnData not found: {h5ad_path}")
    print("Make sure you have run the cluster module first.")
    sys.exit(1)

result = run_mozzarellm(
    h5ad_path,
    cluster_dir,
    screen,
    config,
    RESOLUTION,
    MODEL,
    mode=MODE,
    mcp=MCP,
    include_features=INCLUDE_FEATURES,
    n_features=N_FEATURES,
    fdr_threshold=FDR_THRESHOLD,
    max_tokens=MAX_TOKENS,
)

errors = result.get("errors") or {}

print()
print(f"Run directory: {result['run_dir']}")
print(f"Total cost (USD): {result.get('total_cost_usd')}")
if errors:
    print(f"Clusters with errors: {len(errors)}")
    for cluster_id, message in errors.items():
        print(f"  cluster {cluster_id}: {message}")
else:
    print("No cluster errors")

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
    exec streamlit run ../brieflow/visualization/Cluster_Analysis.py --server.address=0.0.0.0 "$@"
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
