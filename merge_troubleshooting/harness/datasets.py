"""Dataset registry + loaders for the merge research harness.

Four optically-diverse two-scope OPS datasets. Each is normalized to four flat parquets in
a local cache dir (`cache/raw/{name}/`): phenotype_info, sbs_info, ph_meta, sbs_meta.
GCS sources are pulled by pull_data.py; vaishnavi is already local.

det handling: the PH->SBS affine determinant = (ph_px/sbs_px)^2. We DERIVE it empirically
per dataset from the determinants of score-passing anchor candidates (see anchors.py) — this
needs no metadata pixel sizes, so it works even when metadata is missing (owen_20x) or uses
nonstandard magnification fields (owen_40x). Pixel size, when present, is only a cross-check.
"""
import pathlib
import pandas as pd
import numpy as np

HARNESS_DIR = pathlib.Path(__file__).resolve().parent
MT_DIR = HARNESS_DIR.parent                      # merge_troubleshooting/
CACHE_RAW = MT_DIR / "cache" / "raw"

_VAISHNAVI = "/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"

# Per-dataset GCS source maps: normalized_name -> gs:// path. vaishnavi has no gcs (local).
# Owen_20x has NO preprocess/metadata (ph_meta/sbs_meta absent) and lives under old_* dirs.
REGISTRY = {
    "vaishnavi": {
        "optics": "20x pheno / 10x 2x2-bin SBS, neutrophils",
        "sbs_cycle": 1,
        "local": {
            "phenotype_info": f"{_VAISHNAVI}/P-1_W-A1__phenotype_info.parquet",
            "sbs_info": f"{_VAISHNAVI}/P-1_W-A1__sbs_info.parquet",
            "ph_meta": f"{_VAISHNAVI}/preprocess_metadata_phenotype/P-1_W-A1__combined_metadata.parquet",
            "sbs_meta": f"{_VAISHNAVI}/preprocess_metadata_sbs/P-1_W-A1__combined_metadata.parquet",
        },
    },
    "pdac": {
        "optics": "20x pheno / 10x 2x2-bin SBS, PDAC",
        "sbs_cycle": 1,
        "gcs": {
            "phenotype_info": "gs://pdac-ops/primary_OPS_analysis_outputs/brieflow_output/phenotype/parquets/P-10_W-A1__phenotype_info.parquet",
            "sbs_info": "gs://pdac-ops/primary_OPS_analysis_outputs/brieflow_output/sbs/parquets/P-10_W-A1__sbs_info.parquet",
            "ph_meta": "gs://pdac-ops/primary_OPS_analysis_outputs/brieflow_output/preprocess/metadata/phenotype/P-10_W-A1__combined_metadata.parquet",
            "sbs_meta": "gs://pdac-ops/primary_OPS_analysis_outputs/brieflow_output/preprocess/metadata/sbs/P-10_W-A1__combined_metadata.parquet",
        },
    },
    "owen_40x": {
        "optics": "40x confocal pheno / 10x SBS, neurons",
        "sbs_cycle": 1,
        "gcs": {
            "phenotype_info": "gs://lasagna-als-central/lasagna-als/260316_CP19/Brieflow_processed_final_061526/brieflow_output_plate_1/phenotype/parquets/P-1_W-B02__phenotype_info.parquet",
            "sbs_info": "gs://lasagna-als-central/lasagna-als/260316_CP19/Brieflow_processed_final_061526/brieflow_output_plate_1/sbs/parquets/P-1_W-B02__sbs_info.parquet",
            "ph_meta": "gs://lasagna-als-central/lasagna-als/260316_CP19/Brieflow_processed_final_061526/brieflow_output_plate_1/preprocess/metadata/phenotype/P-1_W-B02__combined_metadata.parquet",
            "sbs_meta": "gs://lasagna-als-central/lasagna-als/260316_CP19/Brieflow_processed_final_061526/brieflow_output_plate_1/preprocess/metadata/sbs/P-1_W-B02__combined_metadata.parquet",
        },
        # stage frames are unrelated + too sparse to discover seeds blind, so we seed
        # multistep with the production run's validated good pairs (make_owen40x_anchors.py).
        "gcs_optional": {
            "fast_alignment": "gs://lasagna-als-central/lasagna-als/260316_CP19/Brieflow_processed_final_061526/brieflow_output_plate_1/merge/parquets/P-1_W-B02__fast_alignment.parquet",
        },
    },
    "owen_20x": {
        "optics": "20x pheno / 10x SBS Blainey scopes, neurons",
        "sbs_cycle": 1,
        # metadata copied over by Owen 2026-06-25 -> can run the full anchor->multistep path
        # (sbs and old_sbs metadata are identical for alignment per Owen).
        "gcs": {
            "phenotype_info": "gs://lasagna-als-central/lasagna-als/250923_TDP43_GWS_Attempt2/brieflow_output/well_A1_first_pass/old_phenotype/parquets/P-4_W-A1__phenotype_info.parquet",
            "sbs_info": "gs://lasagna-als-central/lasagna-als/250923_TDP43_GWS_Attempt2/brieflow_output/well_A1_first_pass/old_sbs/parquets/P-4_W-A1__sbs_info.parquet",
            "ph_meta": "gs://lasagna-als-central/lasagna-als/250923_TDP43_GWS_Attempt2/brieflow_output/well_A1_first_pass/preprocess/metadata/phenotype/P-4_W-A1__combined_metadata.parquet",
            "sbs_meta": "gs://lasagna-als-central/lasagna-als/250923_TDP43_GWS_Attempt2/brieflow_output/well_A1_first_pass/preprocess/metadata/sbs/P-4_W-A1__combined_metadata.parquet",
        },
    },
}

FILE_KEYS = ("phenotype_info", "sbs_info", "ph_meta", "sbs_meta")


def raw_path(name, key):
    """Local cache path for a normalized file of a dataset."""
    return CACHE_RAW / name / f"{key}.parquet"


def resolve_local(name, key):
    """Where a file lives locally: vaishnavi points at source; others at the cache."""
    spec = REGISTRY[name]
    if "local" in spec and key in spec["local"]:
        return pathlib.Path(spec["local"][key])
    return raw_path(name, key)


def load(name):
    """Load a dataset's available frames. Returns dict; ph_meta/sbs_meta may be None."""
    out = {}
    for key in ("phenotype_info", "sbs_info"):
        out[key] = pd.read_parquet(resolve_local(name, key))
    for key in ("ph_meta", "sbs_meta"):
        p = resolve_local(name, key)
        out[key] = pd.read_parquet(p) if p.exists() else None
    return out


def pixel_size(meta_df):
    """Best-effort pixel size (um/px) from a metadata frame; None if not derivable."""
    if meta_df is None:
        return None
    for col in ("pixel_size_x", "pixel_size", "pixel_size_y"):
        if col in meta_df.columns and meta_df[col].notna().any():
            return float(meta_df[col].dropna().median())
    # magnification fallback (e.g. owen_40x): needs a camera pixel size we don't store -> None
    return None


def predicted_det(ds):
    """Cross-check det center from pixel sizes: (ph_px/sbs_px)^2. None if unavailable."""
    ph_px = pixel_size(ds.get("ph_meta"))
    sbs_px = pixel_size(ds.get("sbs_meta"))
    if ph_px and sbs_px:
        return (ph_px / sbs_px) ** 2
    return None
