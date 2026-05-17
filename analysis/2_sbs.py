"""2_sbs.py — sbs config (dual-mode marimo).

Hand-converted from `analysis/2.configure_sbs_params.ipynb`.

v1 scope (manifest passthrough; review_required=True):
  - Derive channel + cycle indices from channel_names + dapi_cycle / cyto_cycle
  - Pass through every other sbs param from manifest
  - Flag review_required=True — the 9 tuned sbs params (cell_diameter,
    nuclei_diameter, threshold_peaks, call_reads_method, q_min, max_filter_width,
    peak_width, upsample_factor, window) really do need visual validation:
    threshold_peaks from background statistics, diameters from
    estimate_diameters, call_reads_method from peak distribution shape.

The .ipynb's heavy work (test image segmentation, spot detection viz, barcode
calling, automated parameter search) is config-irrelevant validation tooling —
kept available in `marimo edit` mode but skipped headlessly.

## Manifest fields consumed (sbs section)

  channel_names: list [DAPI, G, T, A, C]
  dapi_channel, cyto_channel: names → indices
  dapi_cycle, cyto_cycle: int → 1-based cycle, ints; -1 → 0-based indices
  extra_channel_indices: list of int (typically [0] for DAPI)
  # Alignment / preprocess
  alignment_method, upsample_factor, window, skip_cycles_indices,
  manual_background_cycle_index, manual_channel_mapping, max_filter_width
  # Spot detection
  spot_detection_method, peak_width, threshold_peaks
  # Segmentation
  segmentation_method, cellpose_model, cyto_model, reconcile, segment_cells, gpu
  nuclei_diameter, cell_diameter
  nuclei_flow_threshold, nuclei_cellprob_threshold,
  cell_flow_threshold, cell_cellprob_threshold
  # Read calling + barcode mapping
  call_reads_method, bases, q_min, error_correct, sort_calls, max_distance
  df_barcode_library_fp
  # Barcode mode
  barcode_type: "simple" | "multi"
  # simple: barcode_col, prefix_col
  # multi: map_start/end/col, recomb_*, etc.
  # Heatmap
  heatmap_plate, heatmap_shape

Source of truth: 2.configure_sbs_params.ipynb (sibling).
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
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "sbs_interactive"
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
    sbs_m = manifest.get("sbs", {}) or {}
    return manifest, sbs_m


@app.cell
def derive_indices(emit_failure, headless, sbs_m, sys):
    """Derive channel + cycle indices from manifest names."""
    channel_names = sbs_m.get("channel_names")
    if not channel_names:
        _msg = "manifest.sbs.channel_names required (list of channel labels)"
        if headless:
            sys.exit(emit_failure(_msg))
        raise ValueError(_msg)

    def _ch_idx(name, label):
        if name is None:
            return None
        if name not in channel_names:
            raise ValueError(
                f"manifest.sbs.{label}={name!r} not in channel_names={channel_names}"
            )
        return channel_names.index(name)

    try:
        dapi_index = _ch_idx(sbs_m.get("dapi_channel", "DAPI"), "dapi_channel")
        cyto_index = _ch_idx(sbs_m.get("cyto_channel"), "cyto_channel")
    except ValueError as e:
        if headless:
            sys.exit(emit_failure(str(e)))
        raise

    # Per .ipynb cell-16: when skip_cycles is set, the cycle→index mapping is
    # not just (cycle - 1) — skipped cycles compress the index space. Mirror
    # the .ipynb's skip-aware derivation:
    #   SBS_CYCLES.index(DAPI_CYCLE) - len([s for s in SKIP_CYCLES if s < DAPI_CYCLE])
    # SBS_CYCLES is the full per-screen cycle list (1..N); skip_cycles_indices
    # is the 0-based indices of cycles to skip. Without skips, this collapses
    # back to (cycle - 1).
    dapi_cycle = sbs_m.get("dapi_cycle", 1)
    cyto_cycle = sbs_m.get("cyto_cycle")
    _skip = sbs_m.get("skip_cycles_indices") or []

    def _cycle_to_index(cycle):
        if cycle is None:
            return None
        base = cycle - 1
        # 0-based skip indices that are strictly before this cycle's 0-based position
        compress = sum(1 for s in _skip if s < base)
        return base - compress

    dapi_cycle_index = _cycle_to_index(dapi_cycle)
    cyto_cycle_index = _cycle_to_index(cyto_cycle)
    return cyto_cycle_index, cyto_index, dapi_cycle_index, dapi_index


@app.cell
def build_config(
    cyto_cycle_index, cyto_index, dapi_cycle_index, dapi_index, sbs_m
):
    """Mirror cell-46 of the .ipynb: assemble sbs section."""
    sbs_section = {
        "alignment_method": sbs_m.get("alignment_method"),
        "channel_names": sbs_m.get("channel_names"),
        "upsample_factor": sbs_m.get("upsample_factor", 2),
        "window": sbs_m.get("window", 2),
        "skip_cycles_indices": sbs_m.get("skip_cycles_indices"),
        "manual_background_cycle_index": sbs_m.get("manual_background_cycle_index"),
        "manual_channel_mapping": sbs_m.get("manual_channel_mapping"),
        "extra_channel_indices": sbs_m.get("extra_channel_indices", [0]),
        "max_filter_width": sbs_m.get("max_filter_width", 3),
        "spot_detection_method": sbs_m.get("spot_detection_method", "standard"),
        "dapi_cycle": sbs_m.get("dapi_cycle", 1),
        "dapi_cycle_index": dapi_cycle_index,
        "cyto_cycle": sbs_m.get("cyto_cycle"),
        "cyto_cycle_index": cyto_cycle_index,
        "dapi_index": dapi_index,
        "cyto_index": cyto_index,
        "segmentation_method": sbs_m.get("segmentation_method", "cellpose"),
        "gpu": sbs_m.get("gpu", False),
        "reconcile": sbs_m.get("reconcile", "contained_in_cells"),
        "segment_cells": sbs_m.get("segment_cells", True),
        "df_barcode_library_fp": sbs_m.get("df_barcode_library_fp"),
        "threshold_peaks": sbs_m.get("threshold_peaks"),
        "call_reads_method": sbs_m.get("call_reads_method", "median"),
        "bases": sbs_m.get("bases", ["G", "T", "A", "C"]),
        "q_min": sbs_m.get("q_min", 0),
        "error_correct": sbs_m.get("error_correct", False),
        "sort_calls": sbs_m.get("sort_calls"),
        "barcode_type": sbs_m.get("barcode_type", "simple"),
        "heatmap_plate": sbs_m.get("heatmap_plate", "6W"),
        "heatmap_shape": sbs_m.get("heatmap_shape", "6W_sbs"),
    }

    # Cellpose-specific (if segmentation_method == "cellpose")
    # Note: cyto_model dropped — .ipynb cell-46 does NOT write it (only cellpose_model).
    if sbs_section["segmentation_method"] == "cellpose":
        sbs_section.update(
            {
                "cellpose_model": sbs_m.get("cellpose_model", "cyto3"),
                "nuclei_diameter": sbs_m.get("nuclei_diameter"),
                "cell_diameter": sbs_m.get("cell_diameter"),
                "nuclei_flow_threshold": sbs_m.get("nuclei_flow_threshold", 0.4),
                "nuclei_cellprob_threshold": sbs_m.get("nuclei_cellprob_threshold", 0.0),
                "cell_flow_threshold": sbs_m.get("cell_flow_threshold", 1),
                "cell_cellprob_threshold": sbs_m.get("cell_cellprob_threshold", 0),
            }
        )

    if sbs_m.get("peak_width") is not None:
        sbs_section["peak_width"] = sbs_m.get("peak_width")

    if sbs_m.get("max_distance") is not None:
        sbs_section["max_distance"] = sbs_m.get("max_distance")

    # Barcode mode specifics
    if sbs_section["barcode_type"] == "simple":
        sbs_section.update(
            {
                "barcode_col": sbs_m.get("barcode_col"),
                "prefix_col": sbs_m.get("prefix_col"),
            }
        )
    elif sbs_section["barcode_type"] == "multi":
        for _k in ("map_start", "map_end", "map_col", "recomb_start", "recomb_end", "recomb_col"):
            sbs_section[_k] = sbs_m.get(_k)
        for _k in ("recomb_filter_col", "recomb_q_thresh", "barcode_info_cols"):
            if sbs_m.get(_k) is not None:
                sbs_section[_k] = sbs_m.get(_k)

    return (sbs_section,)


@app.cell
def finalize(GenResult, emit, headless, mo, sbs_section, sys):
    result = GenResult(
        status="needs_review",
        outputs={"sbs": sbs_section},
        metrics={
            "n_channels": len(sbs_section.get("channel_names", [])),
            "dapi_index": sbs_section.get("dapi_index"),
            "cyto_index": sbs_section.get("cyto_index"),
            "dapi_cycle": sbs_section.get("dapi_cycle"),
            "cyto_cycle": sbs_section.get("cyto_cycle"),
            "barcode_type": sbs_section.get("barcode_type"),
            "segmentation_method": sbs_section.get("segmentation_method"),
            "cellpose_model": sbs_section.get("cellpose_model"),
            "nuclei_diameter": sbs_section.get("nuclei_diameter"),
            "cell_diameter": sbs_section.get("cell_diameter"),
            "threshold_peaks": sbs_section.get("threshold_peaks"),
            "call_reads_method": sbs_section.get("call_reads_method"),
        },
        review_required=True,
        review_prompt=(
            "Confirm SBS spot detection, segmentation, and barcode calling. "
            "9 tuned sbs params (cell/nuclei diameter, threshold_peaks, "
            "call_reads_method, q_min, max_filter_width, peak_width, "
            "upsample_factor, window) carry manifest values in v1; real auto-"
            "derivation (estimate_diameters, background threshold from image "
            "statistics, peak-distribution-based call_reads_method) lands when "
            "test-tile images are available at gen time."
        ),
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
