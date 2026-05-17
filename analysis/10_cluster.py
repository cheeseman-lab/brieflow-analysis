"""10_cluster.py — cluster config + cluster_combo.tsv (dual-mode marimo).

Hand-converted from `analysis/10.configure_cluster_params.ipynb`.

For autonomous mode, the only config-shaping work is:
  - Read aggregate_combo.tsv from upstream
  - Cross unique (cell_class, channel_combo) × leiden_resolutions → cluster_combo.tsv
  - Build cluster config section from manifest

The notebook's heavy work (uniprot scraping, CORUM/KEGG/STRING benchmark generation,
PHATE-Leiden test runs, cluster visualization) is config-irrelevant validation
tooling — kept available in `marimo edit` mode but skipped headlessly. Operator
runs the benchmark-scraping cells once per environment (output cached in
config/benchmark_clusters/) and the file paths get recorded in the config section.

## Manifest fields consumed

  cluster:
    leiden_resolutions: list of ints, e.g. [2,3,4,5,6,7,8,9,10]
    min_cell_cutoffs: dict, e.g. {all: 5, Interphase: 5, Mitotic: 5}
    phate_distance_metric: "cosine" or "euclidean"
    perturbation_auc_threshold: number or null
    aggregate_combo_fp: path (input from upstream gen_aggregate)
    # Benchmark file paths (operator-provided; gen records, doesn't generate)
    uniprot_data_fp, string_pair_benchmark_fp,
    corum_group_benchmark_fp, kegg_group_benchmark_fp

Source of truth: 10.configure_cluster_params.ipynb (sibling).
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def imports():
    import argparse as _argparse
    import sys as _sys
    from pathlib import Path

    _SCRIPT_DIR = Path(__file__).resolve().parent
    _ANALYSIS_DIR = _SCRIPT_DIR  # gen lives at analysis/ root
    _BRIEFLOW_WORKFLOW = _ANALYSIS_DIR.parent / "brieflow" / "workflow"
    for _p in (str(_SCRIPT_DIR), str(_BRIEFLOW_WORKFLOW)):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)

    import marimo as mo
    import pandas as pd

    from _gen_common import GenResult, emit, emit_failure, load_manifest

    SCRIPT_DIR = _SCRIPT_DIR
    ANALYSIS_DIR = _ANALYSIS_DIR
    sys = _sys
    argparse = _argparse

    return (
        ANALYSIS_DIR,
        GenResult,
        Path,
        SCRIPT_DIR,
        argparse,
        emit,
        emit_failure,
        load_manifest,
        mo,
        pd,
        sys,
    )


@app.cell
def cli_or_defaults(ANALYSIS_DIR, Path, argparse, mo, sys):
    headless = not mo.running_in_notebook()
    if headless:
        _p = argparse.ArgumentParser(description=__doc__)
        _p.add_argument("--manifest", required=True, type=Path)
        _p.add_argument("--output-dir", type=Path, default=Path("config"))
        _p.add_argument("--verbose-json", action="store_true", default=True)
        _args, _ = _p.parse_known_args()
        MANIFEST_PATH = _args.manifest
        OUTPUT_DIR = _args.output_dir
    else:
        MANIFEST_PATH = SCRIPT_DIR / "screen_manifest_baker.yaml"
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "cluster_interactive"
    return MANIFEST_PATH, OUTPUT_DIR, headless


@app.cell
def load(MANIFEST_PATH, emit_failure, headless, load_manifest, sys):
    if not MANIFEST_PATH.exists():
        if headless:
            sys.exit(emit_failure(f"manifest not found: {MANIFEST_PATH}"))
        raise FileNotFoundError(MANIFEST_PATH)
    try:
        manifest = load_manifest(MANIFEST_PATH)
    except Exception as e:
        if headless:
            sys.exit(emit_failure(f"load_manifest({MANIFEST_PATH}) failed: {e}"))
        raise
    cluster_m = manifest.get("cluster", {}) or {}
    return manifest, cluster_m


@app.cell
def cluster_combo(
    OUTPUT_DIR, Path, cluster_m, emit_failure, headless, pd, sys
):
    """Mirror cell-17 of the .ipynb: read aggregate_combo.tsv, cross unique
    (cell_class, channel_combo) × leiden_resolutions → cluster_combo.tsv."""
    cluster_combo_fp = OUTPUT_DIR / "cluster_combo.tsv"
    aggregate_combo_fp = Path(
        cluster_m.get("aggregate_combo_fp") or (OUTPUT_DIR / "aggregate_combo.tsv")
    )
    if not aggregate_combo_fp.exists():
        _msg = (
            f"aggregate_combo not found at {aggregate_combo_fp}. "
            f"Cluster depends on gen_aggregate output; set "
            f"manifest.cluster.aggregate_combo_fp or run gen_aggregate first."
        )
        if headless:
            sys.exit(emit_failure(_msg))
        raise FileNotFoundError(_msg)

    leiden_resolutions = cluster_m.get("leiden_resolutions")
    if not leiden_resolutions:
        _msg = "manifest.cluster.leiden_resolutions required (list of ints)"
        if headless:
            sys.exit(emit_failure(_msg))
        raise ValueError(_msg)

    aggregate_combos = pd.read_csv(aggregate_combo_fp, sep="\t")
    unique_pairs = aggregate_combos[["cell_class", "channel_combo"]].drop_duplicates()
    unique_pairs["leiden_resolution"] = [list(leiden_resolutions)] * len(unique_pairs)
    cluster_combo_df = unique_pairs.explode("leiden_resolution", ignore_index=True)

    cluster_combo_fp.parent.mkdir(parents=True, exist_ok=True)
    cluster_combo_df.to_csv(cluster_combo_fp, sep="\t", index=False)
    return cluster_combo_df, cluster_combo_fp


@app.cell
def build_config(cluster_combo_fp, cluster_m):
    """Mirror cell-23 of the .ipynb."""
    cluster_section = {
        "min_cell_cutoffs": cluster_m.get("min_cell_cutoffs"),
        "leiden_resolutions": list(cluster_m.get("leiden_resolutions", [])),
        "phate_distance_metric": cluster_m.get("phate_distance_metric", "cosine"),
        "cluster_combo_fp": str(cluster_combo_fp),
        "uniprot_data_fp": cluster_m.get("uniprot_data_fp"),
        "string_pair_benchmark_fp": cluster_m.get("string_pair_benchmark_fp"),
        "corum_group_benchmark_fp": cluster_m.get("corum_group_benchmark_fp"),
        "kegg_group_benchmark_fp": cluster_m.get("kegg_group_benchmark_fp"),
        "perturbation_auc_threshold": cluster_m.get("perturbation_auc_threshold"),
    }
    return (cluster_section,)


@app.cell
def finalize(
    GenResult,
    cluster_combo_df,
    cluster_combo_fp,
    cluster_section,
    emit,
    headless,
    mo,
    sys,
):
    result = GenResult(
        status="success",
        outputs={"cluster": cluster_section},
        metrics={
            "n_cluster_combos": len(cluster_combo_df),
            "leiden_resolutions": cluster_section["leiden_resolutions"],
            "phate_distance_metric": cluster_section["phate_distance_metric"],
            "cluster_combo_tsv": str(cluster_combo_fp),
        },
        review_required=False,
    )
    if headless:
        sys.exit(emit(result))
    else:
        mo.md(
            f"""
            ### Result
            Status: **{result.status}** (review={result.review_required})

            ```json
            {result.to_json()}
            ```
            """
        )
    return (result,)


if __name__ == "__main__":
    app.run()
