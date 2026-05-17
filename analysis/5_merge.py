"""5_merge.py — merge config + merge_combo.tsv (dual-mode marimo).

Hand-converted from `analysis/5.configure_merge_params.ipynb`.

v1 scope (manifest passthrough; review_required=True):
  - Read sbs_combo.tsv + phenotype_combo.tsv (from gen_preprocess output)
  - Intersect (plate, well) → merge_combo.tsv (deterministic)
  - Pass through every other field from manifest into the merge config section
  - Flag review_required=True so operator confirms via email-ping (Stage 1.5),
    because the 4 tuned merge params (det_range, initial_sites/initial_sbs_tiles,
    score, threshold) really do need visual validation — the .ipynb auto-derives
    candidate pairs via find_closest_tiles + initial_alignment then plots
    alignment_quality.

Follow-on (not in v1): real auto-derivation using brieflow's `lib.merge.hash`
(`hash_cell_locations`, `initial_alignment`, `find_closest_tiles`) — requires
upstream pipeline output (sbs_info / phenotype_info parquets), which doesn't
exist at config-time. The hard auto-derivation is post-preprocess; for now
manifest carries operator-curated values.

## Manifest fields consumed (merge section)

  approach: "fast" | "stitch"
  phenotype_dimensions, sbs_dimensions: lists [h, w]
  sbs_metadata_cycle, sbs_metadata_channel, ph_metadata_channel
  alignment_flip_x, alignment_flip_y, alignment_rotate_90
  metadata_align: bool
  sbs_dedup_prior, pheno_dedup_prior: dicts
  # fast-approach
  initial_sites_approach: "auto" | "manual"
  initial_sbs_tiles, initial_sites: list (use one per approach)
  det_range: [low, high]
  score, threshold: floats
  # stitch-approach
  stitched_image, flipud, fliplr, rot90, mask_type, sbs_pixel_size, phenotype_pixel_size
  # Input paths
  sbs_combo_fp, phenotype_combo_fp (from gen_preprocess output)

Source of truth: 5.configure_merge_params.ipynb (sibling).
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def imports():
    import argparse as _argparse
    import sys as _sys
    import warnings
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
        warnings,
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
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "merge_interactive"
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
    merge_m = manifest.get("merge", {}) or {}
    return manifest, merge_m


@app.cell
def merge_combo(
    OUTPUT_DIR, Path, emit_failure, headless, merge_m, pd, sys, warnings
):
    """Mirror cell-6 of the .ipynb: intersect sbs_combo × phenotype_combo on (plate, well)."""
    merge_combo_fp = OUTPUT_DIR / "merge_combo.tsv"
    sbs_combo_fp = Path(merge_m.get("sbs_combo_fp") or (OUTPUT_DIR / "sbs_combo.tsv"))
    ph_combo_fp = Path(
        merge_m.get("phenotype_combo_fp") or (OUTPUT_DIR / "phenotype_combo.tsv")
    )
    for _label, _fp in (("sbs_combo", sbs_combo_fp), ("phenotype_combo", ph_combo_fp)):
        if not _fp.exists():
            _msg = (
                f"{_label} not found at {_fp}. Merge depends on gen_preprocess "
                f"output; either run gen_preprocess first or set "
                f"manifest.merge.{_label}_fp."
            )
            if headless:
                sys.exit(emit_failure(_msg))
            raise FileNotFoundError(_msg)

    sbs_wildcard_combos = pd.read_csv(sbs_combo_fp, sep="\t")
    ph_wildcard_combos = pd.read_csv(ph_combo_fp, sep="\t")
    sbs_pw = set(zip(sbs_wildcard_combos["plate"], sbs_wildcard_combos["well"]))
    ph_pw = set(zip(ph_wildcard_combos["plate"], ph_wildcard_combos["well"]))

    if sbs_pw == ph_pw:
        merge_combo_df = pd.DataFrame(
            sorted(sbs_pw), columns=["plate", "well"]
        ).astype({"plate": "int", "well": "object"})
    else:
        warnings.warn(
            "SBS and PHENOTYPE do not have matching plate-well combinations. "
            "Merging requires identical sets."
        )
        merge_combo_df = pd.DataFrame(columns=["plate", "well"])

    # Optional per-screen subset (operator chose to process only some wells).
    # manifest.merge.wells_subset: [{plate: 1, well: A1}, ...]
    _subset = merge_m.get("wells_subset")
    if _subset:
        _wanted = {(s["plate"], s["well"]) for s in _subset}
        merge_combo_df = merge_combo_df[
            merge_combo_df.apply(
                lambda r: (r["plate"], r["well"]) in _wanted, axis=1
            )
        ].reset_index(drop=True)

    merge_combo_fp.parent.mkdir(parents=True, exist_ok=True)
    merge_combo_df.to_csv(merge_combo_fp, sep="\t", index=False)
    return merge_combo_df, merge_combo_fp


@app.cell
def build_config(merge_combo_fp, merge_m):
    """Mirror cell-35 of the .ipynb: build merge section. Manifest passthrough
    for all tuned values; gen_merge does not auto-derive dimensions or initial
    sites in v1."""
    stitch = bool(merge_m.get("stitch", False))

    merge_section = {
        "approach": "stitch" if stitch else "fast",
        "merge_combo_fp": str(merge_combo_fp),
        "phenotype_dimensions": merge_m.get("phenotype_dimensions"),
        "sbs_dimensions": merge_m.get("sbs_dimensions"),
        "sbs_metadata_cycle": merge_m.get("sbs_metadata_cycle", 1),
        "score": merge_m.get("score"),
        "threshold": merge_m.get("threshold"),
        "sbs_metadata_channel": merge_m.get("sbs_metadata_channel"),
        "ph_metadata_channel": merge_m.get("ph_metadata_channel"),
        "alignment_flip_x": merge_m.get("alignment_flip_x", False),
        "alignment_flip_y": merge_m.get("alignment_flip_y", False),
        "alignment_rotate_90": merge_m.get("alignment_rotate_90", False),
        "sbs_dedup_prior": merge_m.get("sbs_dedup_prior"),
        "pheno_dedup_prior": merge_m.get("pheno_dedup_prior"),
    }

    if stitch:
        merge_section.update(
            {
                "stitched_image": merge_m.get("stitched_image", False),
                "flipud": merge_m.get("flipud", False),
                "fliplr": merge_m.get("fliplr", False),
                "rot90": merge_m.get("rot90", 0),
                "mask_type": merge_m.get("mask_type", "nuclei"),
                "sbs_pixel_size": merge_m.get("sbs_pixel_size"),
                "phenotype_pixel_size": merge_m.get("phenotype_pixel_size"),
            }
        )
    else:
        _approach = merge_m.get("initial_sites_approach", "manual")
        if _approach == "auto":
            merge_section["initial_sbs_tiles"] = merge_m.get("initial_sbs_tiles")
        else:
            merge_section["initial_sites"] = merge_m.get("initial_sites")
        merge_section["det_range"] = merge_m.get("det_range")

    return (merge_section,)


@app.cell
def finalize(
    GenResult, emit, headless, merge_combo_df, merge_combo_fp, merge_section, mo, sys
):
    result = GenResult(
        status="needs_review",
        outputs={"merge": merge_section},
        metrics={
            "n_merge_combos": len(merge_combo_df),
            "approach": merge_section["approach"],
            "merge_combo_tsv": str(merge_combo_fp),
            "phenotype_dimensions": merge_section["phenotype_dimensions"],
            "sbs_dimensions": merge_section["sbs_dimensions"],
            "det_range": merge_section.get("det_range"),
            "score": merge_section.get("score"),
            "threshold": merge_section.get("threshold"),
            "n_initial_sites": len(merge_section.get("initial_sites") or [])
            if merge_section.get("initial_sites")
            else None,
            "n_initial_sbs_tiles": len(merge_section.get("initial_sbs_tiles") or [])
            if merge_section.get("initial_sbs_tiles")
            else None,
        },
        review_required=True,
        review_prompt=(
            "Confirm merge alignment looks correct. Operator should verify in marimo "
            "that the 4 tuned params (det_range, initial_sites/initial_sbs_tiles, "
            "score, threshold) yield a working alignment via plot_alignment_quality + "
            "fast_merge_example. In v1, these come from the manifest; real auto-"
            "derivation lands as a follow-on once upstream sbs_info/phenotype_info "
            "parquets are available at config-time."
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
