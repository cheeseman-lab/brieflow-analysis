"""8_aggregate.py — aggregate config + aggregate_combo.tsv (dual-mode marimo).

Hand-converted from `analysis/8.configure_aggregate_params.ipynb`.

For v1 (classifier disabled), this is deterministic from manifest + the
upstream merge_combo.tsv:
  - Cross merge wildcard combos × cell_classes (= ["all"] in v1) × channel_combos
    → aggregate_combo.tsv
  - Pass manifest values through into aggregate config section
  - Optionally emit metadata_cols.tsv from brieflow's DEFAULT_METADATA_COLS

Heavy operations in the .ipynb (loading parquets, classification, PCA, alignment,
montages, NA summaries) are pure validation tooling — they don't shape the
config. Skipped in headless mode; remain visible if you `marimo edit` this file.

## Manifest fields consumed

  aggregate:
    channel_combos: list of lists, e.g. [[DAPI, COXIV, CENPA, WGA], [DAPI, CENPA]]
    agg_method, collapse_cols, filter_queries, perturbation_name_col,
    perturbation_id_col, batch_cols, control_key, variance_or_ncomp,
    num_align_batches, contamination, drop_cols_threshold, drop_rows_threshold,
    impute, skip_perturbation_score, ps_probability_threshold, ps_percentile_threshold,
    metadata_cols_fp, aggregate_combo_fp, merge_combo_fp
    bootstrap:  # optional
      cell_classes, channel_combos, feature_normalization, num_sims,
      exclusion_string, pseudogene_patterns
  classifier:
    enabled: bool (default false in v1)
    cell_classes: list (only used if enabled)

Source of truth: 8.configure_aggregate_params.ipynb (sibling).
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def imports():
    import argparse as _argparse
    import sys as _sys
    from itertools import product
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
    from lib.phenotype.constants import DEFAULT_METADATA_COLS

    SCRIPT_DIR = _SCRIPT_DIR
    ANALYSIS_DIR = _ANALYSIS_DIR
    sys = _sys
    argparse = _argparse

    return (
        ANALYSIS_DIR,
        DEFAULT_METADATA_COLS,
        GenResult,
        Path,
        SCRIPT_DIR,
        argparse,
        emit,
        emit_failure,
        load_manifest,
        mo,
        pd,
        product,
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
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "aggregate_interactive"
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
    agg_m = manifest.get("aggregate", {}) or {}
    classifier_m = manifest.get("classifier", {}) or {}
    return manifest, agg_m, classifier_m


@app.cell
def cell_classes(classifier_m):
    """v1: classifier disabled → ["all"]. Otherwise pull from manifest."""
    if classifier_m.get("enabled", False):
        cell_classes = list(classifier_m.get("cell_classes", []))
        if "all" not in cell_classes:
            cell_classes.append("all")
    else:
        cell_classes = ["all"]
    return (cell_classes,)


@app.cell
def channel_combos_cell(agg_m, emit_failure, headless, sys):
    """Compute the underscore-joined channel combo strings."""
    raw = agg_m.get("channel_combos")
    if not raw:
        _msg ="manifest.aggregate.channel_combos required (list of channel-name lists)"
        if headless:
            sys.exit(emit_failure(_msg))
        raise ValueError(_msg)
    channel_combos = ["_".join(c) for c in raw]
    return (channel_combos,)


@app.cell
def metadata_cols_tsv(
    DEFAULT_METADATA_COLS, OUTPUT_DIR, Path, agg_m, classifier_m, pd
):
    """Mirror cell-9 of the .ipynb: when classify disabled, write
    DEFAULT_METADATA_COLS to metadata_cols.tsv. If classify enabled, the
    classify gen owns this file — we just record the path.

    Output path is always OUTPUT_DIR / "cell_data_metadata_cols.tsv". Manifest's
    metadata_cols_fp is intentionally ignored as a write target so smoke tests
    (or any non-default --output-dir) never clobber baker's config/."""
    metadata_cols_fp = OUTPUT_DIR / "cell_data_metadata_cols.tsv"
    if not classifier_m.get("enabled", False):
        metadata_cols_fp.parent.mkdir(parents=True, exist_ok=True)
        pd.Series(DEFAULT_METADATA_COLS).to_csv(
            metadata_cols_fp, index=False, header=False, sep="\t"
        )
        wrote_metadata_cols = True
    else:
        wrote_metadata_cols = False
    return metadata_cols_fp, wrote_metadata_cols


@app.cell
def aggregate_combo(
    OUTPUT_DIR,
    Path,
    agg_m,
    cell_classes,
    channel_combos,
    emit_failure,
    headless,
    pd,
    product,
    sys,
):
    """Mirror cell-17 of the .ipynb: cross merge_combo × cell_classes × channel_combos.

    Output path is always OUTPUT_DIR / "aggregate_combo.tsv" — manifest's
    aggregate_combo_fp is ignored as a write target. Input merge_combo_fp does
    come from the manifest (operator can point at the upstream file)."""
    aggregate_combo_fp = OUTPUT_DIR / "aggregate_combo.tsv"
    merge_combo_fp = Path(agg_m.get("merge_combo_fp") or (OUTPUT_DIR / "merge_combo.tsv"))
    if not merge_combo_fp.exists():
        _msg_mc = (
            f"merge_combo not found at {merge_combo_fp}. "
            f"Aggregate depends on upstream merge output; either run gen_merge first "
            f"or set manifest.aggregate.merge_combo_fp to a valid path."
        )
        if headless:
            sys.exit(emit_failure(_msg_mc))
        raise FileNotFoundError(_msg_mc)

    merge_combos = pd.read_csv(merge_combo_fp, sep="\t")
    # merge_combo cols are at least [plate, well]; .ipynb consumes the row as
    # an unnamed tuple. We do the same for parity.
    rows = []
    for _row in merge_combos.itertuples(index=False, name=None):
        for _cls in cell_classes:
            for _combo in channel_combos:
                rows.append(
                    {
                        "cell_class": _cls,
                        "channel_combo": _combo,
                        "plate": _row[0],
                        "well": _row[1],
                    }
                )
    aggregate_combo_df = pd.DataFrame(
        rows, columns=["cell_class", "channel_combo", "plate", "well"]
    )
    aggregate_combo_fp.parent.mkdir(parents=True, exist_ok=True)
    aggregate_combo_df.to_csv(aggregate_combo_fp, sep="\t", index=False)
    return aggregate_combo_df, aggregate_combo_fp


@app.cell
def build_config(
    agg_m, aggregate_combo_fp, metadata_cols_fp, pd, product
):
    """Mirror cell-40 of the .ipynb: assemble aggregate section from manifest."""
    boot_m = (agg_m.get("bootstrap") or {}) if isinstance(agg_m.get("bootstrap"), dict) else {}

    aggregate_section = {
        "metadata_cols_fp": str(metadata_cols_fp),
        "collapse_cols": agg_m.get("collapse_cols"),
        "aggregate_combo_fp": str(aggregate_combo_fp),
        "filter_queries": agg_m.get("filter_queries"),
        "perturbation_name_col": agg_m.get("perturbation_name_col"),
        "drop_cols_threshold": agg_m.get("drop_cols_threshold", 0.1),
        "drop_rows_threshold": agg_m.get("drop_rows_threshold", 0.01),
        "impute": agg_m.get("impute", True),
        "contamination": agg_m.get("contamination", 0.01),
        "batch_cols": agg_m.get("batch_cols", ["plate", "well"]),
        "control_key": agg_m.get("control_key"),
        "perturbation_id_col": agg_m.get("perturbation_id_col"),
        "variance_or_ncomp": agg_m.get("variance_or_ncomp", 0.99),
        "num_align_batches": agg_m.get("num_align_batches", 1),
        "agg_method": agg_m.get("agg_method", "median"),
        "skip_perturbation_score": agg_m.get("skip_perturbation_score", False),
        "ps_probability_threshold": agg_m.get("ps_probability_threshold"),
        "ps_percentile_threshold": agg_m.get("ps_percentile_threshold"),
    }

    boot_classes = boot_m.get("cell_classes")
    boot_combos = boot_m.get("channel_combos")
    if boot_classes and boot_combos:
        boot_classes_l = boot_classes if isinstance(boot_classes, list) else [boot_classes]
        boot_combos_l = boot_combos if isinstance(boot_combos, list) else [boot_combos]
        bootstrap_combinations = [
            {"cell_class": cc, "channel_combo": ch}
            for cc, ch in product(boot_classes_l, boot_combos_l)
        ]
        aggregate_section.update(
            {
                "feature_normalization": boot_m.get("feature_normalization", "standard"),
                "num_sims": boot_m.get("num_sims"),
                "exclusion_string": boot_m.get("exclusion_string"),
                "bootstrap_combinations": bootstrap_combinations,
                "pseudogene_patterns": boot_m.get("pseudogene_patterns"),
            }
        )
    return (aggregate_section,)


@app.cell
def finalize(
    GenResult,
    aggregate_combo_df,
    aggregate_combo_fp,
    aggregate_section,
    cell_classes,
    channel_combos,
    emit,
    headless,
    metadata_cols_fp,
    mo,
    sys,
    wrote_metadata_cols,
):
    result = GenResult(
        status="success",
        outputs={"aggregate": aggregate_section},
        metrics={
            "n_aggregate_combos": len(aggregate_combo_df),
            "n_channel_combos": len(channel_combos),
            "n_cell_classes": len(cell_classes),
            "channel_combos": channel_combos,
            "cell_classes": cell_classes,
            "aggregate_combo_tsv": str(aggregate_combo_fp),
            "metadata_cols_tsv": str(metadata_cols_fp),
            "wrote_metadata_cols": wrote_metadata_cols,
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
