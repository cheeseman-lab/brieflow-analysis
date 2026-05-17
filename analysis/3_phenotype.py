"""3_phenotype.py — phenotype config (dual-mode marimo).

Hand-converted from `analysis/3.configure_phenotype_params.ipynb`.

v1 scope (manifest passthrough; review_required=True):
  - Derive DAPI/cyto/source/target/riders/foci channel indices from CHANNEL_NAMES
  - Pass through every other phenotype param from manifest
  - Flag review_required=True — cellpose `nuclei_diameter` / `cell_diameter`
    are normally auto-estimated by `estimate_diameters(image, ...)` against a
    test tile (.ipynb cell-14); v1 manifest carries operator-curated values,
    real auto-derivation lands when test-tile images are available at gen time.

The .ipynb's heavy visual validation (segmentation overlays, alignment viz,
feature extraction with cp_emulator/cp_measure) doesn't shape the config —
kept available in `marimo edit` mode but skipped headlessly.

## Manifest fields consumed (phenotype section)

  channel_names: list [DAPI, COXIV, CENPA, WGA]  # echoed/inherited from preprocess
  dapi_channel: "DAPI"           # → dapi_index
  cyto_channel: "COXIV"          # → cyto_index
  foci_channel: "CENPA"          # str or list of str → foci_channel_index
  align: bool
  target, source: channel name  # → target_index, source_index
  riders: list of channel names  # → list of int indices
  remove_channel: "source" | "target" | "riders" | null
  upsample_factor, window: int
  custom_channel_offsets: dict or null
  # Segmentation
  segmentation_method, cellpose_model (default cyto3), stardist_model
  reconcile, segment_cells, gpu, cp_method
  nuclei_diameter, cell_diameter (cellpose, tuned)
  nuclei_flow_threshold, nuclei_cellprob_threshold,
  cell_flow_threshold, cell_cellprob_threshold (cellpose)
  nuclei_prob_threshold, nuclei_nms_threshold,
  cell_prob_threshold, cell_nms_threshold (stardist)
  helper_index (cpsam)
  # Heatmap viz
  heatmap_plate, heatmap_shape

Source of truth: 3.configure_phenotype_params.ipynb (sibling).
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
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "phenotype_interactive"
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
    ph_m = manifest.get("phenotype", {}) or {}
    return manifest, ph_m


@app.cell
def derive_indices(emit_failure, headless, ph_m, sys):
    """Derive channel indices from channel-name fields. The brieflow notebook
    does CHANNEL_NAMES.index(...) for DAPI, CYTO, FOCI, TARGET, SOURCE, RIDERS."""
    channel_names = ph_m.get("channel_names")
    if not channel_names:
        _msg = "manifest.phenotype.channel_names required (list of channel labels)"
        if headless:
            sys.exit(emit_failure(_msg))
        raise ValueError(_msg)

    def _idx(name, label):
        if name is None:
            return None
        if name not in channel_names:
            raise ValueError(
                f"manifest.phenotype.{label}={name!r} not in channel_names={channel_names}"
            )
        return channel_names.index(name)

    try:
        dapi_index = _idx(ph_m.get("dapi_channel", "DAPI"), "dapi_channel")
        cyto_index = _idx(ph_m.get("cyto_channel"), "cyto_channel")

        foci_channel = ph_m.get("foci_channel")
        if isinstance(foci_channel, list):
            foci_channel_index = [_idx(c, "foci_channel") for c in foci_channel]
        else:
            foci_channel_index = _idx(foci_channel, "foci_channel")

        target_index = _idx(ph_m.get("target"), "target") if ph_m.get("align") else None
        source_index = _idx(ph_m.get("source"), "source") if ph_m.get("align") else None
        rider_indexes = (
            [_idx(r, "riders") for r in ph_m.get("riders", [])]
            if ph_m.get("align")
            else None
        )

        custom_offsets_raw = ph_m.get("custom_channel_offsets") or {}
        custom_channel_offsets_indexed = (
            {channel_names.index(k): v for k, v in custom_offsets_raw.items()}
            if custom_offsets_raw
            else None
        )
    except ValueError as e:
        if headless:
            sys.exit(emit_failure(str(e)))
        raise

    return (
        custom_channel_offsets_indexed,
        cyto_index,
        dapi_index,
        foci_channel_index,
        rider_indexes,
        source_index,
        target_index,
    )


@app.cell
def build_config(
    custom_channel_offsets_indexed,
    cyto_index,
    dapi_index,
    foci_channel_index,
    ph_m,
    rider_indexes,
    source_index,
    target_index,
):
    """Mirror cell-24 of the .ipynb: build phenotype section."""
    seg_method = ph_m.get("segmentation_method", "cellpose")
    phenotype_section = {
        "foci_channel_index": foci_channel_index,
        "channel_names": ph_m.get("channel_names"),
        "align": ph_m.get("align", False),
        "dapi_index": dapi_index,
        "cyto_index": cyto_index,
        "segmentation_method": seg_method,
        "reconcile": ph_m.get("reconcile", "contained_in_cells"),
        "gpu": ph_m.get("gpu", False),
        "segment_cells": ph_m.get("segment_cells", True),
        "cp_method": ph_m.get("cp_method", "cp_emulator"),
        "heatmap_plate": ph_m.get("heatmap_plate", "6W"),
        "heatmap_shape": ph_m.get("heatmap_shape", "6W_ph"),
    }

    if seg_method == "cellpose":
        phenotype_section.update(
            {
                "nuclei_diameter": ph_m.get("nuclei_diameter"),
                "cell_diameter": ph_m.get("cell_diameter"),
                "nuclei_flow_threshold": ph_m.get("nuclei_flow_threshold", 0.4),
                "nuclei_cellprob_threshold": ph_m.get("nuclei_cellprob_threshold", 0.0),
                "cell_flow_threshold": ph_m.get("cell_flow_threshold", 1),
                "cell_cellprob_threshold": ph_m.get("cell_cellprob_threshold", 0),
                "cellpose_model": ph_m.get("cellpose_model", "cyto3"),
            }
        )
        if ph_m.get("helper_index") is not None:
            phenotype_section["helper_index"] = ph_m.get("helper_index")
    elif seg_method == "stardist":
        phenotype_section.update(
            {
                "stardist_model": ph_m.get("stardist_model", "2D_versatile_fluo"),
                "nuclei_prob_threshold": ph_m.get("nuclei_prob_threshold", 0.479071),
                "nuclei_nms_threshold": ph_m.get("nuclei_nms_threshold", 0.3),
                "cell_prob_threshold": ph_m.get("cell_prob_threshold", 0.479071),
                "cell_nms_threshold": ph_m.get("cell_nms_threshold", 0.3),
            }
        )

    if ph_m.get("align"):
        phenotype_section.update(
            {
                "target": target_index,
                "source": source_index,
                "riders": rider_indexes,
                "remove_channel": ph_m.get("remove_channel"),
                "upsample_factor": ph_m.get("upsample_factor", 2),
                "window": ph_m.get("window", 2),
            }
        )

    if custom_channel_offsets_indexed:
        phenotype_section["custom_channel_offsets"] = custom_channel_offsets_indexed

    return (phenotype_section,)


@app.cell
def finalize(GenResult, emit, headless, mo, phenotype_section, sys):
    result = GenResult(
        status="needs_review",
        outputs={"phenotype": phenotype_section},
        metrics={
            "n_channels": len(phenotype_section.get("channel_names", [])),
            "dapi_index": phenotype_section.get("dapi_index"),
            "cyto_index": phenotype_section.get("cyto_index"),
            "foci_channel_index": phenotype_section.get("foci_channel_index"),
            "align": phenotype_section.get("align"),
            "segmentation_method": phenotype_section.get("segmentation_method"),
            "cellpose_model": phenotype_section.get("cellpose_model"),
            "nuclei_diameter": phenotype_section.get("nuclei_diameter"),
            "cell_diameter": phenotype_section.get("cell_diameter"),
        },
        review_required=True,
        review_prompt=(
            "Confirm phenotype segmentation + alignment look correct via marimo. "
            "5 tuned params (nuclei_diameter, cell_diameter, source, target, align) "
            "carry operator values from manifest in v1; real auto-derivation via "
            "estimate_diameters + cross-correlation alignment lands when test-tile "
            "image is available at gen time."
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
