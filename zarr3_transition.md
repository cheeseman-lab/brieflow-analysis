# Brieflow Zarr3 Transition

**Cheeseman Lab | Whitehead Institute for Biomedical Research**

---

## 1. Overview

**Goal:** Transition brieflow modules 0–2 (preprocess, SBS, phenotype) to OME-Zarr v3 image outputs conforming to the [OME-NGFF HCS plate layout](https://ngff.openmicroscopy.org/latest/#hcs-layout) and aligned with the BioHub reference implementation.

**Branch:** `ege/zarr3-transition` in the brieflow submodule (merging back into `zarr3-transition` → `main`). Analysis repo stays on `main`.

**BioHub specs (kept separately):**

| File | Description |
|------|-------------|
| [`zarr3_biohub_v1.md`](zarr3_biohub_v1.md) | Original BioHub reference spec (v1) |
| [`zarr3_biohub_v2.md`](zarr3_biohub_v2.md) | Updated BioHub reference spec (v2) |

---

## 2. Completed Work

Built on PR [#179](https://github.com/cheeseman-lab/brieflow/pull/179) (Claire Peterson's zarr v2 I/O layer). All core conversion for modules 0–2 is done and validated.

### Core I/O

- Format-agnostic `read_image()` / `save_image()` in `lib/shared/io.py` (TIFF + OME-Zarr v3)
- All SBS/phenotype scripts converted from `tifffile.imwrite()` to `save_image()`
- Config-driven format selection (`image_output_format: "tiff"` or `"zarr"`)
- Unified OME-Zarr with pyramids (eliminated dual standard-zarr + OME-Zarr streams)

### HCS Direct-Write (Option D)

- `{well}` → `{row}/{col}` wildcards in zarr mode via `split_well_to_cols()`
- **Option D layout:** each image type is its own plate zarr (`aligned_1.zarr/`, `peaks_1.zarr/`, etc.) tracked by a `zarr.json` sentinel file — no `directory()` wrapper needed for image stores
- Label stores nest inside the aligned image store (`aligned_1.zarr/.../labels/nuclei.zarr`) as `directory()` outputs, OME-NGFF compliant
- Metadata-only finalize step (`hcs.py`) discovers plate structure and writes `zarr.json` at plate/row/well/field levels — no symlinks, no copies, no separate `hcs/` directory
- Wildcard normalization in scripts that pass wildcards as DataFrame columns (`extract_bases.py`, `extract_phenotype_minimal.py`, `extract_phenotype.py`) synthesize `well = row + col`

### Test Status

- **295/295 zarr steps** pass (4 extra HCS finalize rules vs TIFF)
- **291/291 TIFF steps** pass
- Bit-identical numerical outputs between TIFF and zarr

### Bug History

1. **Missing `directory()` on zarr targets** — fixed with unified `_img_mapping`
2. **Singleton dim squeeze** — `save_image()` normalizes 2D→`(1,Y,X)` for OME-Zarr; `read_image()` squeezes back
3. **`extract_phenotype.py` still used `tifffile.imread`** — fixed to `read_image()`
4. **TIFF `temp()` regression** — zarr3 branch used single `_img_mapping` for all outputs, but `main` had some as `None` (kept). Fixed with two mapping vars: `_img_temp` (directory/temp) and `_img_keep` (directory/None)
5. **`KeyError: 'well'` in `call_reads.py`** — zarr mode wildcards are `{plate, row, col, tile}` (no `well`). Scripts that pass `dict(snakemake.wildcards)` to library functions add each wildcard as a DataFrame column; downstream code sorts by `well` and crashes. Fixed via wildcard normalization in 3 scripts.

---

## 3. Current Architecture (Option D)

### Design Decisions

| Decision | Details |
|----------|---------|
| **Sentinel tracking** | Image stores tracked by the tile-level `zarr.json` — this file IS the image group metadata (multiscales + omero) and doubles as the Snakemake sentinel (a regular file, no `directory()` needed) |
| **Label nesting** | Label stores are `directory()` outputs nested inside the aligned image store at `.../labels/` |
| **Dispatchers** | `get_image_output_path()` / `get_data_output_path()` in `file_utils.py` dispatch between TIFF (flat) and zarr (HCS nested) |
| **Wildcard normalization** | Scripts synthesize `well = row + col` so downstream library code (which sorts by `well`) works unchanged |
| **TIFF unaffected** | All conditional logic gated on `IMG_FMT == "zarr"` — TIFF mode identical to `main` branch |

### Dispatcher Functions

```python
# file_utils.py — top-level dispatchers used by all target files

def get_image_output_path(data_location, info_type, img_fmt, subdirectory=None, image_subdir=None):
    """TIFF: images/P-1_W-A1_T-0__aligned.tiff
    zarr:  aligned_1.zarr/A/1/0/zarr.json  (image group metadata + Snakemake sentinel)
    zarr labels: aligned_1.zarr/A/1/0/labels/nuclei.zarr  (directory)"""

def get_data_output_path(data_location, info_type, file_type, img_fmt):
    """TIFF: P-1_W-A1_T-0__bases.tsv  (flat)
    zarr:  1/A/1/0/bases.tsv  (nested)"""
```

Lower-level helpers called internally:
- `get_hcs_nested_path()` — generates `{info_type}_{plate}.zarr/{row}/{col}/{tile}/zarr.json` paths
- `get_nested_path()` — generates `{plate}/{row}/{col}/{tile}/{info_type}.{ext}` paths
- `_well_to_rowcol()` — converts `{well}` key to `{row}/{col}` for zarr HCS nesting

### SBS Module Layout

Every `*.zarr/` directory is a full plate zarr containing image data (pyramid levels + chunk data) at each tile. The tile-level `zarr.json` is the **image group metadata** (`ome.multiscales` + `omero.channels`) and doubles as the Snakemake output sentinel.

```
sbs/
├── aligned_1.zarr/                              # plate store (5-ch SBS aligned)
│   ├── zarr.json                                # HCS plate metadata ✓
│   └── A/                                       # row
│       ├── zarr.json                            # row group ✓
│       └── 1/                                   # col (well A1)
│           ├── zarr.json                        # well metadata (lists tiles) ✓
│           └── 0/                               # tile
│               ├── zarr.json                    # image metadata (multiscales + omero)
│               ├── 0/ 1/ 2/ 3/ 4/              # pyramid levels (each has zarr.json + c/ chunks)
│               └── labels/
│                   ├── zarr.json                # labels group
│                   ├── nuclei.zarr/             # directory() output (pyramids inside)
│                   └── cells.zarr/
├── illumination_corrected_1.zarr/               # plate store (5-ch IC-corrected)
│   └── A/1/0/                                   # same tile structure as aligned
│       ├── zarr.json                            # image metadata (multiscales + omero)
│       └── 0/ 1/ 2/ 3/ 4/                      # pyramid levels
├── log_filtered_1.zarr/                         # plate store (5-ch log-filtered)
│   └── A/1/0/
│       ├── zarr.json                            # image metadata
│       └── 0/ 1/ 2/ 3/ 4/
├── max_filtered_1.zarr/                         # plate store (reduced channels)
│   └── A/1/0/ ...
├── peaks_1.zarr/                                # plate store (1-ch)
│   └── A/1/0/ ...
├── standard_deviation_1.zarr/                   # plate store (1-ch)
│   └── A/1/0/ ...
├── parquets/1/A/1/reads.parquet
├── tsvs/1/A/1/0/segmentation_stats.tsv
└── eval/
    ├── mapping/1/mapping_overview.tsv
    └── segmentation/1/cell_density_heatmap.{png,tsv}
```

**Current gap:** Only `aligned_1.zarr` has HCS plate/row/well-level `zarr.json` (marked ✓ above). All other image stores have valid image data and tile-level metadata but are **missing plate-level HCS metadata** — the finalize step needs to be extended to cover them (see Section 4b).

### Phenotype Module Layout

```
phenotype/
├── aligned_1.zarr/                              # plate store (4-ch phenotype aligned)
│   ├── zarr.json                                # HCS plate metadata ✓
│   └── A/1/2/                                   # tile
│       ├── zarr.json                            # image metadata (multiscales + omero)
│       ├── 0/ 1/ 2/ 3/ 4/                      # pyramid levels
│       └── labels/
│           ├── zarr.json                        # labels group
│           ├── nuclei.zarr/
│           ├── cells.zarr/
│           └── identified_cytoplasms.zarr/      # phenotype-only
├── illumination_corrected_1.zarr/               # plate store (4-ch IC-corrected)
│   └── A/1/2/
│       ├── zarr.json                            # image metadata
│       └── 0/ 1/ 2/ 3/ 4/
├── parquets/1/A/1/phenotype_cp.parquet
├── tsvs/1/A/1/2/segmentation_stats.tsv
└── eval/
    ├── features/1/cell_DAPI_min_heatmap.{png,tsv}
    └── segmentation/1/segmentation_overview.tsv
```

**Same gap:** Only `aligned_1.zarr` has full HCS plate metadata.

### Preprocess Module Layout

```
preprocess/
├── sbs/image_1.zarr/                            # SBS plate store
│   ├── zarr.json                                # HCS plate metadata ✓
│   └── A/1/0/
│       └── 1/                                   # per-cycle (cycle=1..11)
│           ├── zarr.json                        # image metadata
│           └── 0/ 1/ 2/ 3/ 4/                  # pyramid levels
├── phenotype/image_1.zarr/                      # phenotype plate store
│   ├── zarr.json                                # HCS plate metadata ✓
│   └── A/1/2/
│       ├── zarr.json                            # image metadata
│       └── 0/ 1/ 2/ 3/ 4/
├── ic_fields/
│   ├── sbs/1/A/1/1/ic_field.zarr/              # per-cycle IC fields
│   └── phenotype/1/A/1/ic_field.zarr/
└── metadata/
    ├── sbs/1/A/1/combined_metadata.parquet
    └── phenotype/1/A/1/combined_metadata.parquet
```

### TIFF Mode (flat naming, for comparison)

```
sbs/
├── images/P-1_W-A1_T-0__{aligned,nuclei,cells}.tiff
├── parquets/P-1_W-A1__{cells,reads,sbs_info}.parquet
├── tsvs/P-1_W-A1_T-0__segmentation_stats.tsv
└── eval/{mapping,segmentation}/P-1__*.{png,tsv}
```

**Key difference:** Zarr replaces the flat `P-{plate}_W-{well}_T-{tile}__` naming with the HCS hierarchy `{info_type}_{plate}.zarr/{row}/{col}/{tile}/`. Non-image outputs (parquets, tsvs, eval) use the analogous nested `{plate}/{row}/{col}/` directory path.

---

## 4. Remaining Work — Metadata

The remaining work has two parts: enriching the **tile-level** image metadata (channel names, pixel sizes, axis units, omero rendering defaults) and extending the **plate-level** HCS finalize step to all image stores (not just `aligned`).

### Current vs Target Tile-Level `zarr.json`

Every tile-level `zarr.json` (e.g., `aligned_1.zarr/A/1/0/zarr.json`) is the image group metadata written by `save_image()` → `write_image_omezarr()` in `io.py`. Currently it's minimal:

**Current:**
```json
{
  "attributes": {
    "ome": {
      "multiscales": [{
        "axes": [
          {"name": "c", "type": "channel"},
          {"name": "y", "type": "space"},
          {"name": "x", "type": "space"}
        ],
        "datasets": [
          {"path": "0", "coordinateTransformations": [{"scale": [1.0, 1.0, 1.0], "type": "scale"}]}
        ]
      }]
    },
    "omero": {
      "channels": [
        {"label": "c0", "active": true, "color": "FFFFFF"}
      ]
    }
  }
}
```

**Target:**
```json
{
  "attributes": {
    "ome": {
      "multiscales": [{
        "axes": [
          {"name": "c", "type": "channel"},
          {"name": "y", "type": "space", "unit": "micrometer"},
          {"name": "x", "type": "space", "unit": "micrometer"}
        ],
        "datasets": [
          {"path": "0", "coordinateTransformations": [{"scale": [1.0, 0.325, 0.325], "type": "scale"}]}
        ]
      }]
    },
    "omero": {
      "version": "0.5",
      "channels": [
        {"label": "DAPI", "active": true, "color": "0000FF", "coefficient": 1.0, "family": "linear", "inverted": false}
      ],
      "rdefs": {"defaultT": 0, "defaultZ": 0, "model": "color", "projection": "normal"}
    },
    "image-label": {"version": "0.5"}
  }
}
```

### 4a. Recommended Approach: Enrich in the Finalize Step

**The recommended approach is to do all metadata enrichment in the finalize step**, rather than threading metadata through every script and rule. The pipeline steps continue writing images with minimal metadata (as they do now — zero script changes), and the finalize step patches every store's metadata after all images are written.

This works because the metadata sources are already available at finalize time:
- **Pixel sizes** → `combined_metadata.parquet` (extracted from ND2 headers during preprocessing)
- **Channel names** → config YAML (`sbs.channel_names`, `phenotype.channel_names`)
- **Channel count per store** → read from the actual array shape in each tile's zarr store
- **Static spec fields** (axis units, omero version/rdefs, image-label version) → hardcoded defaults

**What the finalize step needs to do for each plate zarr:**

1. **Write plate/row/well `zarr.json`** — already done for `aligned`, needs extending to all stores
2. **Patch each tile's `zarr.json`** with:
   - Axis units (`"unit": "micrometer"` on spatial axes)
   - Pixel sizes in `coordinateTransformations` (from `combined_metadata.parquet`)
   - Real channel names in `omero.channels` (matched to store's channel count)
   - Channel colors (DAPI→`0000FF`, GFP→`00FF00`, Cy3→`FF0000`, Cy5→`FF00FF`)
   - `omero` rendering defaults (`version`, `rdefs`, `coefficient`, `family`, `inverted`)
   - `image-label` version for label stores

**Implementation options for tile-level patching:**

| Approach | How | Pros | Cons |
|----------|-----|------|------|
| **Direct zarr attrs** | Open each tile's `zarr.json`, patch `root.attrs` dict, write back | No new dependencies, consistent with current `hcs.py` approach | Manual, must handle spec details ourselves |
| **iohub patching API** | Use `open_ome_zarr(mode="r+")` with `set_scale()`, `rename_channel()`, etc. | Clean API, spec-compliant by construction, handles HCS iteration | New dependency, v0.3.0 alpha for zarr v3 (see Section 4e) |

Either approach avoids modifying any of the 16 pipeline scripts.

### 4b. Extend HCS Finalize to All Image Stores

Currently, the HCS finalize rules only write plate/row/well-level `zarr.json` for `aligned_{plate}.zarr`. **All other image stores are missing plate-level HCS metadata.**

| Module | Currently finalized | Needs finalize added |
|--------|-------------------|---------------------|
| SBS | `aligned_{p}.zarr` only | `illumination_corrected_{p}.zarr`, `log_filtered_{p}.zarr`, `max_filtered_{p}.zarr`, `peaks_{p}.zarr`, `standard_deviation_{p}.zarr` |
| Phenotype | `aligned_{p}.zarr` only | `illumination_corrected_{p}.zarr` |
| Preprocess | `image_{p}.zarr` (both modalities) | Already covered |

Each store needs its own correct `channels_metadata` in the plate-level `zarr.json`, reflecting the actual channels in that store. The finalize rules in `sbs.smk` (line 287) and `phenotype.smk` (line 167) currently hardcode `aligned_{p}.zarr` in `params.plate_zarr_dirs` — these need to be extended to list all image stores for that module.

### 4c. Per-Store Channel Mapping

The finalize step needs to know what channels each store contains to write correct metadata. The store's array shape gives the channel count; the mapping below gives the names:

| Store | Module | Channels | Channel names |
|-------|--------|----------|---------------|
| `aligned` | sbs | 11 (5 SBS ch × cycles) | Full SBS channels per cycle |
| `illumination_corrected` | sbs | 11 | Same as aligned |
| `log_filtered` | sbs | 11 | Same as aligned |
| `max_filtered` | sbs | Reduced (base channels) | Base channel subset |
| `peaks` | sbs | 1 | `"peaks"` |
| `standard_deviation` | sbs | 1 | `"standard_deviation"` |
| `aligned` | phenotype | 4 | Full phenotype channels |
| `illumination_corrected` | phenotype | 4 | Same as aligned |
| `nuclei` / `cells` | shared | 1 | Label (no channel names) |
| `identified_cytoplasms` | phenotype | 1 | Label |
| `image` | preprocess | Varies by modality | From config channel_names |
| `ic_field` | preprocess | IC-specific | IC-specific |

### 4d. Data Sources Already Available

| Metadata | Source | Location |
|----------|--------|----------|
| Pixel size (µm) | Extracted from ND2 headers | `preprocess/metadata/{modality}/{plate}/{row}/{col}/combined_metadata.parquet` → `pixel_size_x`, `pixel_size_y` |
| Channel count | Extracted from ND2 headers | Same parquet → `channels` |
| Channel names | Config YAML (canonical) | `config.sbs.channel_names`, `config.phenotype.channel_names` |
| Objective magnification | Extracted from ND2 headers | Same parquet → `objective_magnification` |

**Pixel sizes from `combined_metadata.parquet`:**
```
pixel_size_x: 0.325  (phenotype 20x)
pixel_size_y: 0.325
pixel_size_x: 1.3    (sbs 10x)
pixel_size_y: 1.3
```

### 4e. iohub for Metadata Patching

[iohub](https://github.com/czbiohub-sf/iohub) (CZ Biohub's OME-Zarr I/O library) was evaluated as a potential tool for metadata enrichment. Key findings:

**What iohub can do:**
- **Post-hoc metadata patching** — open existing zarr stores in `mode="r+"` and use `set_scale()`, `rename_channel()`, `set_contrast_limits()` to enrich tile-level metadata. This is its strongest feature for our use case.
- **HCS plate support** — first-class creation, iteration, and management of plate/well/position hierarchies
- **Zarr v3 support** — available in pre-release v0.3.0a6 via `version="0.5"` parameter
- **Auto OMERO display metadata** — channel color assignment based on name keywords (DAPI→blue, GFP→lime, etc.), contrast limits

**What iohub cannot do:**
- **No ND2 reading** — iohub has zero support for Nikon ND2 files. It only reads Micro-Manager formats.
- **No generic TIFF reading** — only Micro-Manager OME-TIFF, single-page TIFF sequences, and ND-TIFF. Won't work with arbitrary TIFFs from other microscope software.
- **No automatic metadata propagation** — when reading a zarr and writing a new one, metadata must be manually read and forwarded. There is no "copy metadata forward" function.

**Recommendation:** iohub is useful for the finalize-step patching approach (Section 4a), not for data ingestion. However, v0.3.0 is still alpha for zarr v3 — we could start with direct zarr attr patching (consistent with our current `hcs.py` approach) and migrate to iohub once v0.3.0 stabilizes. Alternatively, evaluate iohub v0.3.0a6 in the starter notebook to see if it works reliably with our stores.

```python
# Example: iohub patching in finalize step
from iohub import open_ome_zarr

with open_ome_zarr("sbs/aligned_1.zarr", mode="r+", version="0.5") as plate:
    for path, pos in plate.positions():
        pos.rename_channel("c0", "DAPI")
        pos.set_scale("0", "x", 0.325)
        pos.set_scale("0", "y", 0.325)
        pos.set_contrast_limits("DAPI", {"start": 100, "end": 5000})
```

---

## 5. Remaining Work — Downstream Modules

The merge module now uses `get_data_output_path()` dispatchers. Remaining modules:

- **Aggregate module** — reads merged parquets and per-tile tables. Parquet paths may not change, but any image references need updating.
- **Cluster module** — PHATE + Leiden on aggregated data. Mostly tabular, but verify no hardcoded TIFF assumptions.
- `montage_utils.py`, `classify/apply.py`, `aggregate/*`, `cluster_eval` — all use `get_filename()` / `parse_filename()` and need migration to `get_image_output_path()` / `get_data_output_path()`.

Run the full pipeline (all 6 modules) on test data in zarr mode and confirm outputs match TIFF baseline.

---

## 6. Remaining Work — Future / Open

### Tabular Data Format

The community has not reached consensus on how to store tables alongside OME-NGFF images. The main tables proposal ([ome/ngff#64](https://github.com/ome/ngff/pull/64)) was closed in September 2023 without merging. Key tensions: AnnData being too Python-centric for a universal spec, scope disputes, and governance questions.

| Format | Pros | Cons |
|--------|------|------|
| **Parquet** (current) | Simple, language-agnostic, fast columnar reads | No standard for linking to zarr images |
| **AnnData (`.h5ad`)** | scverse ecosystem (scanpy, squidpy); single-cell standard | Python-centric; HDF5 doesn't nest in zarr |
| **AnnData-Zarr** | Could live inside the zarr store hierarchy | Spec not finalized |
| **SpatialData** | Unified image + table + spatial workflows | Heavy dependency; still maturing |

**Current approach:** Parquets alongside zarr stores in a nested directory structure (`parquets/{plate}/{row}/{col}/`). Keep using parquets; design so the tabular format can be swapped later.

### Other Stretch Goals

- **Lazy zarr sampling** — Dask-backed dataloaders that read chunks on demand instead of loading full plates
- **Sharded zarr codecs** — zarr v3 sharding for HPC-friendly I/O on large merged arrays
- **Merge to main** — after all steps validated, merge `ege/zarr3-transition` → `zarr3-transition` → `main`

### References

- [OME-NGFF v0.5 Spec](https://ngff.openmicroscopy.org/latest/)
- [HCS Plate Layout](https://ngff.openmicroscopy.org/latest/#hcs-layout)
- [Image.sc: HCS zarrs with multiple image types per FOV](https://forum.image.sc/t/how-to-build-hcs-zarrs-with-multiple-image-types-per-fov/119329) — discussion that informed our Option D layout
- [Zarr v3 Migration Guide](https://zarr.readthedocs.io/en/stable/user-guide/v3_migration/)
- [ome-zarr-py Docs](https://ome-zarr.readthedocs.io/)
- [BioHub Reference Spec v1](zarr3_biohub_v1.md) / [v2](zarr3_biohub_v2.md)
- [PR #179](https://github.com/cheeseman-lab/brieflow/pull/179)
- [ome/ngff#64 — Tables spec discussion](https://github.com/ome/ngff/pull/64)
- [iohub — CZ Biohub OME-Zarr I/O](https://github.com/czbiohub-sf/iohub)
- [SpatialData](https://spatialdata.scverse.org/)
- [napari-ome-zarr](https://github.com/ome/napari-ome-zarr)
- [Brieflow Docs](https://brieflow.readthedocs.io/)

---

*This document consolidates and supersedes `development_guide.md`, `zarr3_final_plan.md`, and `zarr3_io_metadata_guide.md` (originals kept for reference).*
