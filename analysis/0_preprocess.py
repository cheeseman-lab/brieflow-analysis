"""0_preprocess.py — preprocess config + samples/combo TSVs (dual-mode marimo).

Hand-converted from `analysis/0.configure_preprocess_params.ipynb`. Preserves
the notebook's structure but reads parameters from a manifest YAML so it can
run unattended as a plugin subprocess.

## Two modes

Interactive (operator):
    marimo edit analysis/marimo/0_preprocess.py

Headless (plugin or smoke test):
    python analysis/marimo/0_preprocess.py --manifest <path> \
        --output-dir <path> --verbose-json

The notebook detects headless mode via `mo.running_in_notebook()` and skips
plot rendering, replacing it with stdout JSON.

## Manifest fields consumed

manifest.preprocess.{sbs,phenotype}.images_dir / path_pattern / path_metadata /
metadata_order_type / data_format / data_organization / channel_order /
channel_order_flip / n_z_planes / metadata_samples_df_fp
(plus phenotype.round_order; plus preprocess.sample_fraction / root_fp)

Source of truth: 0.configure_preprocess_params.ipynb (sibling).
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def imports():
    import argparse as _argparse
    import sys as _sys
    from pathlib import Path

    # Make brieflow's lib.* importable + load gen-helpers from sibling
    _SCRIPT_DIR = Path(__file__).resolve().parent
    _ANALYSIS_DIR = _SCRIPT_DIR  # gen lives at analysis/ root
    _BRIEFLOW_WORKFLOW = _ANALYSIS_DIR.parent / "brieflow" / "workflow"
    for _p in (str(_SCRIPT_DIR), str(_BRIEFLOW_WORKFLOW)):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)

    import marimo as mo
    import pandas as pd

    from _gen_common import GenResult, emit, emit_failure, load_manifest
    from lib.shared.configuration_utils import create_samples_df
    from lib.preprocess.file_utils import get_tile_count_from_well

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
        create_samples_df,
        emit,
        emit_failure,
        get_tile_count_from_well,
        load_manifest,
        mo,
        pd,
        sys,
    )


@app.cell
def cli_or_defaults(ANALYSIS_DIR, Path, argparse, mo, sys):
    """Resolve manifest path + output dir from CLI (headless) or defaults (notebook)."""
    headless = not mo.running_in_notebook()

    if headless:
        _p = argparse.ArgumentParser(description=__doc__)
        _p.add_argument("--manifest", required=True, type=Path)
        _p.add_argument("--output-dir", type=Path, default=Path("config"))
        _p.add_argument("--verbose-json", action="store_true", default=True)
        _args, _unknown = _p.parse_known_args()
        MANIFEST_PATH = _args.manifest
        OUTPUT_DIR = _args.output_dir
    else:
        MANIFEST_PATH = SCRIPT_DIR / "screen_manifest_baker.yaml"
        OUTPUT_DIR = ANALYSIS_DIR.parent / ".cache" / "preprocess_interactive"

    return MANIFEST_PATH, OUTPUT_DIR, headless


@app.cell
def load(MANIFEST_PATH, emit_failure, headless, load_manifest, sys):
    """Load manifest. In headless mode, bail with JSON on failure."""
    if not MANIFEST_PATH.exists():
        msg = f"manifest not found: {MANIFEST_PATH}"
        if headless:
            sys.exit(emit_failure(msg))
        raise FileNotFoundError(msg)

    try:
        manifest = load_manifest(MANIFEST_PATH)
    except Exception as e:
        msg = f"load_manifest({MANIFEST_PATH}) failed: {e}"
        if headless:
            sys.exit(emit_failure(msg))
        raise

    pp = manifest.get("preprocess", {}) or {}
    sbs_m = pp.get("sbs", {}) or {}
    ph_m = pp.get("phenotype", {}) or {}
    return manifest, pp, sbs_m, ph_m


@app.cell
def paths_intro(OUTPUT_DIR, mo, pp):
    """Echo resolved paths (interactive only)."""
    if mo.running_in_notebook():
        mo.md(
            f"""
            ### Resolved paths

            - **Output dir:** `{OUTPUT_DIR}`
            - **root_fp:** `{pp.get('root_fp', 'brieflow_output/')}`
            - **sample_fraction:** `{pp.get('sample_fraction', 1.0)}`
            """
        )
    return


@app.cell
def sbs_samples(
    OUTPUT_DIR, Path, create_samples_df, emit_failure, headless, sbs_m, sys
):
    """Cell-9 equivalent (SBS): create samples DataFrame + write TSV."""
    if not sbs_m.get("images_dir"):
        if headless:
            sys.exit(emit_failure("manifest.preprocess.sbs.images_dir required"))
        raise ValueError("manifest.preprocess.sbs.images_dir required")

    sbs_samples_fp = OUTPUT_DIR / "sbs_samples.tsv"
    sbs_samples_fp.parent.mkdir(parents=True, exist_ok=True)

    sbs_samples_df = create_samples_df(
        Path(sbs_m["images_dir"]).expanduser(),
        sbs_m["path_pattern"],
        sbs_m["path_metadata"],
        sbs_m.get("metadata_order_type", {}),
    )
    sbs_samples_df.to_csv(sbs_samples_fp, sep="\t", index=False)
    return sbs_samples_df, sbs_samples_fp


@app.cell
def sbs_combo(
    OUTPUT_DIR, get_tile_count_from_well, headless, mo, pd, sbs_m, sbs_samples_df
):
    """Cell-9 equivalent (SBS): expand combos. For 'well' org, opens one ND2 to
    detect tile count (the auto-derivation step we don't bypass)."""
    sbs_combo_fp = OUTPUT_DIR / "sbs_combo.tsv"
    sbs_data_org = sbs_m.get("data_organization", "well")

    if sbs_data_org == "tile":
        sbs_combo_df = (
            sbs_samples_df[sbs_m["path_metadata"]].drop_duplicates().astype(str)
        )
        sbs_n_tiles = None
    elif sbs_data_org == "well":
        sbs_n_tiles = get_tile_count_from_well(
            sbs_samples_df,
            plate=sbs_samples_df["plate"].iloc[0],
            well=sbs_samples_df["well"].iloc[0],
            cycle=sbs_samples_df["cycle"].iloc[0]
            if "cycle" in sbs_samples_df.columns
            else None,
            channel_order=sbs_m.get("channel_order"),
            verbose=False,
        )
        _base = sbs_samples_df[sbs_m["path_metadata"]].drop_duplicates().astype(str)
        sbs_combo_df = pd.DataFrame(
            [
                {**_row.to_dict(), "tile": str(_t)}
                for _, _row in _base.iterrows()
                for _t in range(sbs_n_tiles)
            ]
        )
    else:
        raise ValueError(f"unknown sbs data_organization: {sbs_data_org!r}")

    sbs_combo_df.to_csv(sbs_combo_fp, sep="\t", index=False)

    if not headless:
        mo.md(
            f"**SBS:** {len(sbs_samples_df)} samples → {len(sbs_combo_df)} combos "
            f"(org={sbs_data_org}, tiles/well={sbs_n_tiles})"
        )
    return sbs_combo_df, sbs_combo_fp, sbs_n_tiles


@app.cell
def phenotype_samples(
    OUTPUT_DIR, Path, create_samples_df, emit_failure, headless, ph_m, sys
):
    """Cell-9 equivalent (phenotype): create samples DataFrame + write TSV."""
    if not ph_m.get("images_dir"):
        if headless:
            sys.exit(emit_failure("manifest.preprocess.phenotype.images_dir required"))
        raise ValueError("manifest.preprocess.phenotype.images_dir required")

    ph_samples_fp = OUTPUT_DIR / "phenotype_samples.tsv"
    ph_samples_df = create_samples_df(
        Path(ph_m["images_dir"]).expanduser(),
        ph_m["path_pattern"],
        ph_m["path_metadata"],
        ph_m.get("metadata_order_type", {}),
    )
    ph_samples_df.to_csv(ph_samples_fp, sep="\t", index=False)
    return ph_samples_df, ph_samples_fp


@app.cell
def phenotype_combo(
    OUTPUT_DIR, get_tile_count_from_well, headless, mo, pd, ph_m, ph_samples_df
):
    """Cell-9 equivalent (phenotype): expand combos."""
    ph_combo_fp = OUTPUT_DIR / "phenotype_combo.tsv"
    ph_data_org = ph_m.get("data_organization", "well")

    if ph_data_org == "tile":
        ph_combo_df = (
            ph_samples_df[ph_m["path_metadata"]].drop_duplicates().astype(str)
        )
        ph_n_tiles = None
    elif ph_data_org == "well":
        ph_n_tiles = get_tile_count_from_well(
            ph_samples_df,
            plate=ph_samples_df["plate"].iloc[0],
            well=ph_samples_df["well"].iloc[0],
            round_order=ph_m.get("round_order"),
            channel_order=ph_m.get("channel_order"),
            verbose=False,
        )
        _base = ph_samples_df[ph_m["path_metadata"]].drop_duplicates().astype(str)
        ph_combo_df = pd.DataFrame(
            [
                {**_row.to_dict(), "tile": str(_t)}
                for _, _row in _base.iterrows()
                for _t in range(ph_n_tiles)
            ]
        )
    else:
        raise ValueError(f"unknown phenotype data_organization: {ph_data_org!r}")

    ph_combo_df.to_csv(ph_combo_fp, sep="\t", index=False)

    if not headless:
        mo.md(
            f"**Phenotype:** {len(ph_samples_df)} samples → {len(ph_combo_df)} combos "
            f"(org={ph_data_org}, tiles/well={ph_n_tiles})"
        )
    return ph_combo_df, ph_combo_fp, ph_n_tiles


@app.cell
def build_config(
    pp, ph_combo_fp, ph_m, ph_samples_fp, sbs_combo_fp, sbs_m, sbs_samples_fp
):
    """Cell-25 equivalent: assemble config sections from manifest + outputs."""
    all_section = {"root_fp": pp.get("root_fp", "brieflow_output/")}
    preprocess_section = {
        "sbs_samples_fp": str(sbs_samples_fp),
        "sbs_combo_fp": str(sbs_combo_fp),
        "phenotype_samples_fp": str(ph_samples_fp),
        "phenotype_combo_fp": str(ph_combo_fp),
        "sbs_data_format": sbs_m.get("data_format", "nd2"),
        "sbs_data_organization": sbs_m.get("data_organization", "well"),
        "sbs_channel_order": sbs_m.get("channel_order"),
        "sbs_channel_order_flip": sbs_m.get("channel_order_flip", False),
        "sbs_n_z_planes": sbs_m.get("n_z_planes"),
        "sbs_metadata_samples_df_fp": sbs_m.get("metadata_samples_df_fp"),
        "phenotype_data_format": ph_m.get("data_format", "nd2"),
        "phenotype_data_organization": ph_m.get("data_organization", "well"),
        "phenotype_channel_order": ph_m.get("channel_order"),
        "phenotype_channel_order_flip": ph_m.get("channel_order_flip", False),
        "phenotype_round_order": ph_m.get("round_order"),
        "phenotype_n_z_planes": ph_m.get("n_z_planes"),
        "phenotype_metadata_samples_df_fp": ph_m.get("metadata_samples_df_fp"),
        "sample_fraction": pp.get("sample_fraction", 1.0),
    }
    return all_section, preprocess_section


@app.cell
def finalize(
    GenResult,
    all_section,
    emit,
    headless,
    mo,
    ph_combo_fp,
    ph_n_tiles,
    ph_samples_df,
    ph_samples_fp,
    preprocess_section,
    sbs_combo_df,
    sbs_combo_fp,
    sbs_n_tiles,
    sbs_samples_df,
    sbs_samples_fp,
    sys,
):
    """Headless: emit verbose-JSON GenResult. Interactive: render summary."""
    result = GenResult(
        status="success",
        outputs={"all": all_section, "preprocess": preprocess_section},
        metrics={
            "n_sbs_samples": len(sbs_samples_df),
            "n_sbs_combo": len(sbs_combo_df),
            "n_sbs_tiles_per_well": sbs_n_tiles,
            "n_phenotype_samples": len(ph_samples_df),
            "n_phenotype_tiles_per_well": ph_n_tiles,
            "sbs_samples_tsv": str(sbs_samples_fp),
            "sbs_combo_tsv": str(sbs_combo_fp),
            "phenotype_samples_tsv": str(ph_samples_fp),
            "phenotype_combo_tsv": str(ph_combo_fp),
        },
        review_required=False,  # deterministic geometry; visual review is in 3_phenotype + 2_sbs
    )
    if headless:
        sys.exit(emit(result))
    else:
        mo.md(
            f"""
            ### Result

            Status: **{result.status}** (review_required={result.review_required})

            ```json
            {result.to_json()}
            ```
            """
        )
    return (result,)


if __name__ == "__main__":
    app.run()
