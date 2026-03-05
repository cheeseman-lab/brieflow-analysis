# Brieflow Zarr3 Transition Plan

## Overview

**Goal:** Transition brieflow modules 0-2 (preprocess, SBS, phenotype) to OME-Zarr v3 image outputs that conform to the [OME-NGFF HCS plate layout](https://ngff.openmicroscopy.org/latest/#hcs-layout) and match the BioHub reference implementation (`zarr3_biohub_spec.md`).

**Branch:** `zarr3-transition` in the brieflow submodule. Analysis repo stays on `main`.

**Merge to main happens after all steps below are complete.**

---

## Completed Work

Built on PR #179 (Claire Peterson's zarr v2 I/O layer). All core conversion for modules 0-2 is done and validated:

- Format-agnostic `read_image()` / `save_image()` in `lib/shared/io.py` (TIFF + OME-Zarr v3)
- All SBS/phenotype scripts converted from `tifffile.imwrite()` to `save_image()`
- Config-driven format selection (`image_output_format: "tiff"` or `"zarr"`)
- Nested directory paths via `get_nested_path()` / `parse_nested_path()`
- Unified OME-Zarr with pyramids (eliminated dual standard-zarr + OME-Zarr streams)
- End-to-end tested: 294/294 zarr steps pass, 291/291 TIFF steps pass (3 extra zarr steps are HCS finalize rules), bit-identical numerical outputs between TIFF and Zarr
- Dead code removal, IO deduplication, lib/script cleanup

**Bugs fixed during testing (2026-02-05):**
1. Missing `directory()` on zarr targets — fixed with unified `_img_mapping`
2. Singleton dim squeeze — `save_image()` normalizes 2D->`(1,Y,X)` for OME-Zarr; `read_image()` squeezes back
3. `extract_phenotype.py` still used `tifffile.imread` — fixed to `read_image()`

**Bugs fixed during HCS work (2026-02-08):**
4. TIFF `temp()` regression — zarr3 branch used a single `_img_mapping` (`temp` for TIFF) for all image outputs, but `main` had some as `None` (kept). Fixed with two mapping vars: `_img_temp` (directory/temp) and `_img_keep` (directory/None). Affected: `segment_sbs`, `align_phenotype`, `segment_phenotype`. Preprocess mappings were already correct. Both pipelines re-verified at 291/291.

**Bugs fixed during direct-write refactor (2026-02-09):**
5. `KeyError: 'well'` in `call_reads.py` — In zarr mode, Snakemake wildcards are `{plate, row, col, tile}` (no `well`). Scripts that pass `dict(snakemake.wildcards)` to library functions add each wildcard as a DataFrame column. Downstream code (`call_reads.py`, `call_cells.py`, `eval_mapping.py`) sorts by `well` column and crashes. Fixed by adding wildcard normalization in 3 scripts (`extract_bases.py`, `extract_phenotype_minimal.py`, `extract_phenotype.py`): `if "row" in wc and "col" in wc and "well" not in wc: wc["well"] = wc["row"] + wc["col"]`.

---

## HCS Direct-Write Architecture

**Architecture:** Snakemake writes zarr stores directly into HCS-compliant plate zarr directories. The `{well}` wildcard is replaced with `{row}/{col}` in zarr mode so output paths naturally form `plate.zarr/row/col/tile/` hierarchies. A lightweight finalize step writes metadata-only `zarr.json` files at plate, row, and well levels — **no symlinks, no copies, no separate `hcs/` directory**.

**Direct-write layout (zarr mode):**
```
sbs/1.zarr/                            ← plate zarr (Snakemake writes directly here)
├── zarr.json                          ← plate metadata (written by finalize step)
├── A/                                 ← row group
│   ├── zarr.json                      ← row group metadata (finalize)
│   └── 1/                             ← column group (well A1 = A/1)
│       ├── zarr.json                  ← well metadata listing fields (finalize)
│       └── 0/                         ← field (tile) — Snakemake writes below
│           ├── aligned.zarr/          ← intensity image (with pyramids)
│           ├── nuclei.zarr/           ← label image
│           ├── cells.zarr/            ← label image
│           ├── max_filtered.zarr/     ← additional image
│           ├── peaks.zarr/            ← additional image
│           ├── standard_deviation.zarr/
│           └── aligned_cycle{N}.zarr/ ← per-cycle images
```

**Key design decisions:**
- **`{well}` → `{row}/{col}` wildcards** in zarr mode. HCS spec requires `row/column` paths (e.g. `A/1`). All output paths (images, TSVs, parquets) use `{row}/{col}` to keep wildcards consistent across mixed-output rules. Combo DataFrames get `row`/`col` derived from `well` via `_split_well_to_cols()` in the Snakefile.
- **Wildcard normalization in scripts**: Scripts that pass wildcards as DataFrame columns (`extract_bases.py`, `extract_phenotype_minimal.py`, `extract_phenotype.py`) synthesize `well = row + col` so downstream library code (which sorts by `well`) works unchanged.
- **Metadata-only fusion**: The finalize step (`write_hcs_metadata.py`) discovers the plate structure by walking `{plate}.zarr/` and writes `zarr.json` at plate/row/well/field levels. No data is moved or linked.
- **One plate zarr per plate** — all intensity images and labels for all tiles are reachable from one zarr store
- **All metadata** wrapped in `"ome"` key per NGFF v0.5 (plate, well, labels)
- **TIFF mode completely unaffected** — all conditional logic is gated on `IMG_FMT == "zarr"`

**Path dispatcher functions (Snakefile):**
```python
# _get_path: flat filename (TIFF) or nested directory path (zarr)
def _get_path(location, info_type, file_type):
    if IMG_FMT == "zarr":
        return get_nested_path(_well_to_rowcol(location), info_type, file_type)
    return get_filename(location, info_type, file_type)

# _get_image_path: flat image under images/ (TIFF) or HCS nested path (zarr)
def _get_image_path(location, info_type, subdirectory=None):
    if IMG_FMT == "zarr":
        return get_hcs_nested_path(_well_to_rowcol(location), info_type, subdirectory=subdirectory)
    return str(Path("images") / get_filename(location, info_type, "tiff"))
```

All target files use canonical `{well}` location dicts and these dispatchers:
```python
# Canonical location dicts (same for both modes)
_sbs_tile_loc = {"plate": "{plate}", "well": "{well}", "tile": "{tile}"}

# Non-image helpers use _get_path (no conditionals)
def _sbs_tsv(info):
    return SBS_FP / "tsvs" / _get_path(_sbs_tile_loc, info, "tsv")

# Image helpers still need internal if for directory structure differences
def _sbs_img(info):
    if SBS_IMG_FMT == "zarr":
        return SBS_FP / _get_image_path(_sbs_tile_loc, info)
    return SBS_FP / "images" / get_filename(_sbs_tile_loc, info, SBS_IMG_FMT)

# Expansion helpers remain conditional
_sbs_well_expand = ["row", "col"] if SBS_IMG_FMT == "zarr" else ["well"]
_sbs_tile_expand = ["row", "col", "tile"] if SBS_IMG_FMT == "zarr" else ["well", "tile"]
```

**TIFF mode produces flat filenames (like `main` branch):**
```
sbs/images/P-1_W-A1_T-0__aligned.tiff
sbs/tsvs/P-1_W-A1_T-0__bases.tsv
sbs/parquets/P-1_W-A1__reads.parquet
```

**Zarr mode produces nested HCS paths:**
```
sbs/1.zarr/A/1/0/aligned.zarr/
sbs/tsvs/1/A/1/0/bases.tsv
sbs/parquets/1/A/1/reads.parquet
```

---

## Roadmap

### Step 1: HCS Structural Conformance (Matteo) — DONE (2026-02-09)

Refactored the pipeline to write zarr stores directly into HCS-compliant plate zarr directories, replacing the previous symlink-based assembly approach.

**What was done:**
1. **`{well}` → `{row}/{col}` wildcards** — Added `_split_well_to_cols()` in Snakefile to derive `row`/`col` from `well` in combo DataFrames. All targets files (`preprocess.smk`, `sbs.smk`, `phenotype.smk`) define conditional path helpers and expansion variables (`_*_well_expand`, `_*_tile_expand`) for zarr vs TIFF mode.
2. **`get_hcs_nested_path()`** — New helper in `file_utils.py` generates `{plate}.zarr/{row}/{col}/{tile}/` paths for zarr mode.
3. **Metadata-only fusion** — `hcs.py` rewritten with `discover_plate_structure()` + `write_hcs_metadata()` that walk existing plate zarr dirs and write `zarr.json` files. No symlinks or copies.
4. **Wildcard normalization** — Scripts that pass wildcards as DataFrame columns (`extract_bases.py`, `extract_phenotype_minimal.py`, `extract_phenotype.py`) synthesize `well = row + col` for library compatibility.
5. **`get_expansion_values()`** updated to exclude `row`/`col` from expansion (like `plate` and `well`).

**Files modified:** `Snakefile`, `file_utils.py`, `hcs.py`, `write_hcs_metadata.py`, `targets/{preprocess,sbs,phenotype,merge}.smk`, `rules/{preprocess,sbs,phenotype,merge}.smk`, `lib/preprocess/file_utils.py`, `scripts/{extract_bases,extract_phenotype_minimal,extract_phenotype}.py`

**Verified:** 294/294 zarr steps pass, 291/291 TIFF steps pass.

**Subsequent refactor (2026-02-09):** Unified wildcards + dispatcher pattern. See "Unified Wildcards + Dispatcher Refactor" section below.

---

### Step 2: Starter Notebook (Matteo) — DONE (2026-02-08)

Created `tests/small_test_analysis/notebooks/metadata_enrichment.ipynb`:

- **Directory exploration** — walks zarr output tree, shows plate/well/tile structure
- **Metadata parquet** — loads combo DataFrames to understand wildcard combos
- **zarr.json inspection** — reads and displays plate/well/field metadata from all 3 modules (sbs, phenotype, preprocess per-modality)
- **HCS plate navigation** — demonstrates traversing plate → row → column → field hierarchy
- **Enrichment templates** — axes units, pixel sizes, channel names, contrast limits, labels metadata
- **Roundtrip demo** — read metadata, modify, write back, verify

Also cleaned up `load_omezarr_in_napari.py` and deleted the redundant `load_omezarr_notebook.py`.

---

### Step 3: Metadata Loading (Undergrad — branches off Matteo's work)

The undergrad branches off the `zarr3-transition` branch and enriches zarr stores with metadata. Start in the notebook, prototype each item on real test data:

- **Axis units** — `"unit": "micrometer"` on spatial axes (`ome.multiscales[0].axes[].unit`)
- **Pixel sizes** — physical scale factors from config into `coordinateTransformations`
- **Channel names** — meaningful labels (DAPI, GFP, etc.) into `omero.channels[].label`
- **Contrast limits** — 1st/99th percentile intensity windows into `omero.channels[].window`
- **Label dtype** — coerce segmentation masks to int32
- **Segmentation metadata** — method name, label identity on label stores

These are based on the BioHub reference spec but the undergrad should also consult the [OME-NGFF v0.5 spec](https://ngff.openmicroscopy.org/latest/) directly — there may be additional metadata fields worth adding beyond what BioHub uses.

---

### Step 4: Validate and Build Metadata Passing Logic

The key question: when the pipeline reads a zarr and writes a new zarr, does the metadata propagate?

- Test round-trip: write metadata to a store, read it with `read_image()`, write to a new store with `save_image()` — is the metadata preserved?
- Identify what propagates automatically vs. what needs explicit forwarding
- Once validated in the notebook, integrate into pipeline code:
  - `save_image()` / `omezarr_writer.py` accept and write richer metadata
  - Scripts forward metadata from snakemake params
  - Rules pass config values as params
  - Config YAML gets `pixel_size_um`, channel name lists, etc.

---

### Step 5: Napari Integration

Set up a local napari environment and use it as the ground truth for whether everything works:

- Channel names visible (not `c0`, `c1`, ...)
- Scale bar shows correct physical coordinates
- Contrast limits produce sensible default rendering
- Segmentation labels overlay correctly on images
- Plate zarr navigable as plate -> well -> tile hierarchy

```bash
# Local setup (laptop, not cluster)
conda create -n napari-viz -c conda-forge python=3.11 napari napari-ome-zarr -y
conda activate napari-viz
napari --plugin napari-ome-zarr path/to/sbs/1.zarr
```

Validate at each pipeline step — not just final outputs but intermediates (illumination corrected, aligned, segmented) should all render correctly.

---

### Step 6: Downstream Module Compatibility

The merge module now uses the `_get_path()` dispatcher (done in the unified wildcards refactor). Remaining modules:

- **Aggregate module** — reads merged parquets and per-tile tables. Parquet paths may not change, but any image references need updating.
- **Cluster module** — PHATE + Leiden on aggregated data. Mostly tabular, but verify no hardcoded TIFF assumptions.
- `montage_utils.py`, `classify/apply.py`, `aggregate/*`, `cluster_eval` — all use `get_filename()` / `parse_filename()` and need migration to `_get_path()`.

Run the full pipeline (all 6 modules) on test data in zarr mode and confirm outputs match TIFF baseline.

---

### Step 7: Tabular Data Format and Storage (Open)

**Status:** The community has not reached consensus on how to store tables alongside OME-NGFF images. The main OME-NGFF tables proposal ([ome/ngff#64](https://github.com/ome/ngff/pull/64)) was closed in September 2023 without merging. Key tensions included AnnData being too Python-centric for a universal spec, scope disputes, and governance questions. The community acknowledged the need for a governance framework before revisiting.

**Formats we've used / are considering:**

| Format | Pros | Cons |
|--------|------|------|
| **Parquet** (current) | Simple, language-agnostic, fast columnar reads | No standard for linking to zarr images; no spatial metadata |
| **AnnData (`.h5ad`)** | scverse ecosystem (scanpy, squidpy, SpatialData); standard in single-cell | Python-centric; HDF5 backend doesn't nest in zarr |
| **AnnData-Zarr** | Could live inside the zarr store hierarchy | Spec not finalized (ome/ngff#64 closed) |
| **SpatialData** | Unified image + table + spatial workflows | Heavy dependency; still maturing |

**Current approach:** We write parquets alongside zarr stores in a nested directory structure (`parquets/{plate}/{row}/{col}/`). This works but lacks a formal link between image data and tabular measurements.

**Potential path forward:**
- **[iohub](https://github.com/czbiohub-sf/iohub)** — CZ Biohub's I/O library for OME-Zarr. Could be used to process/write metadata more efficiently and potentially automate metadata enrichment based on pipeline data (channel names from config, pixel sizes from hardware metadata, etc.). Worth evaluating as an alternative or complement to our manual zarr.json writing.
- Keep parquet for now, but design the pipeline so the tabular format can be swapped later
- Evaluate whether AnnData-Zarr becomes viable once the NGFF governance process advances

**Resources:**
- [ome/ngff#64 — Tables spec discussion](https://github.com/ome/ngff/pull/64)
- [iohub documentation](https://czbiohub-sf.github.io/iohub/)
- [SpatialData](https://spatialdata.scverse.org/)

### Other Stretch Goals

- **Lazy zarr sampling** — Dask-backed dataloaders that read chunks on demand instead of loading full plates
- **Sharded zarr codecs** — zarr v3 sharding for HPC-friendly I/O on large merged arrays

---

### Unified Wildcards + Dispatcher Refactor — DONE (2026-02-09)

Previously, zarr mode used a dual wildcard system: image-processing rules used `{row}/{col}` while metadata/merge rules used `{well}`. Also, TIFF mode had been inadvertently changed from flat `get_filename()` paths to nested `get_nested_path()` paths (diverging from `main` branch).

**What was done:**
1. **Unified wildcards** — `_split_well_to_cols()` now applied to ALL combo DataFrames (sbs, phenotype, metadata, merge). All rules use `{row}/{col}` wildcards in zarr mode. Wildcard constraints (`row="[A-Za-z]+"`, `col="[0-9]+"`) enable Snakemake to parse `A1` back into `row=A, col=1`.
2. **Dispatcher functions** — `_get_path()` and `_get_image_path()` in Snakefile dispatch to `get_filename()` (TIFF, flat) or `get_nested_path()`/`get_hcs_nested_path()` (zarr, nested). All target files use canonical `{well}` location dicts; the dispatcher handles `{well}` → `{row}/{col}` conversion for zarr.
3. **TIFF mode restored to flat** — TIFF output now uses `get_filename()` (like `main` branch), producing flat files like `P-1_W-A1_T-0__aligned.tiff`. No more nested directories in TIFF mode.
4. **merge.smk targets** — Removed conditional `_merge_well_loc`, replaced all `get_filename()` calls with `_get_path()` calls using canonical `{well}` location dicts.
5. **merge.smk rules** — All `wildcards.well` → `_get_well(wildcards)`, all `expansion_values=["well"]` → `_merge_well_expand`.

**Files modified:** `Snakefile`, `targets/{preprocess,sbs,phenotype,merge}.smk`, `rules/{preprocess,merge}.smk`, `lib/preprocess/file_utils.py`

**Verified:** 294/294 zarr steps pass, 291/291 TIFF steps pass. Bit-identical numerical outputs between formats (confirmed 2026-02-10).

---

### Verified Output Structure (2026-02-10)

Clean-directory end-to-end run confirmed both pipelines produce correct outputs. Zarr parquets carry 2 extra columns (`row`, `col`) from wildcard normalization — harmless, since `well` is also present and used by downstream code.

#### Zarr: SBS Module (`brieflow_output_zarr/sbs/`)

```
sbs/
├── 1.zarr/                                      # plate store (plate=1)
│   ├── zarr.json                                # HCS plate metadata (OME v0.5)
│   └── A/                                       # row
│       ├── zarr.json                            # row group metadata
│       ├── 1/                                   # col  (well = A1)
│       │   ├── zarr.json                        # well metadata (lists fields)
│       │   ├── 0/                               # tile (field of view)
│       │   │   ├── aligned.zarr/                #   multiscale image (levels 0..4)
│       │   │   ├── illumination_corrected.zarr/
│       │   │   ├── log_filtered.zarr/
│       │   │   ├── max_filtered.zarr/
│       │   │   ├── peaks.zarr/
│       │   │   ├── standard_deviation.zarr/
│       │   │   └── labels/
│       │   │       ├── zarr.json                # labels group metadata
│       │   │       ├── cells.zarr/
│       │   │       └── nuclei.zarr/
│       │   ├── 2/                               # tile
│       │   │   └── (same image + label stores)
│       │   └── 32/                              # tile
│       │       └── (same image + label stores)
│       └── 2/                                   # col  (well = A2)
│           └── (same structure per well)
├── parquets/
│   └── 1/A/{1,2}/                               # plate/row/col/
│       ├── cells.parquet
│       ├── reads.parquet
│       └── sbs_info.parquet
├── tsvs/
│   └── 1/A/{1,2}/{0,2,32}/                     # plate/row/col/tile/
│       └── segmentation_stats.tsv
└── eval/
    ├── mapping/1/                               # plate/
    │   ├── mapping_overview.tsv
    │   └── *.png (heatmaps, histograms)
    └── segmentation/1/
        ├── cell_density_heatmap.{png,tsv}
        └── segmentation_overview.tsv



sbs/
├── aligned_1.zarr/                              # HCS plate: primary image
│   └── A/
│       ├── 1/                                 # well A1
│       │   ├── {0,2,32}/                      # tiles
│       │   │   ├── zarr.json                  # multiscales + omero
│       │   │   ├── 0/, 1/, 2/, ...
│       │   │   └── labels/
│       │   │       ├── nuclei.zarr/
│       │   │       └── cells.zarr/
│       └── 2/                                 # well A2
│           └── (same structure)
├── illumination_corrected_1.zarr/               # HCS plate: derived image
│   └── A/1/{0,2,32}/ ...
├── log_filtered_1.zarr/
│   └── A/1/{0,2,32}/ ...
├── max_filtered_1.zarr/
│   └── A/1/{0,2,32}/ ...
├── peaks_1.zarr/
│   └── A/1/{0,2,32}/ ...
├── standard_deviation_1.zarr/
│   └── A/1/{0,2,32}/ ...
├── parquets/
│   └── 1/A/{1,2}/                             # plate/row/col/
│       ├── cells.parquet
│       ├── reads.parquet
│       └── sbs_info.parquet
├── tsvs/
│   └── 1/A/{1,2}/{0,2,32}/                    # plate/row/col/tile/
│       └── segmentation_stats.tsv
└── eval/
    ├── mapping/1/                             # plate/
    │   ├── mapping_overview.tsv
    │   └── *.png (heatmaps, histograms)
    └── segmentation/1/
        ├── cell_density_heatmap.{png,tsv}
        └── segmentation_overview.tsv


```

#### Zarr: Phenotype Module (`brieflow_output_zarr/phenotype/`)

```
phenotype/
├── 1.zarr/                                      # plate store
│   └── A/
│       ├── 1/                                   # well A1
│       │   ├── {2,5,141}/                       # tiles
│       │   │   ├── aligned.zarr/
│       │   │   ├── illumination_corrected.zarr/
│       │   │   └── labels/
│       │   │       ├── cells.zarr/
│       │   │       ├── nuclei.zarr/
│       │   │       └── identified_cytoplasms.zarr/  # phenotype-only
│       └── 2/                                   # well A2
│           └── (same structure)
├── parquets/
│   └── 1/A/{1,2}/
│       ├── phenotype_cp.parquet
│       ├── phenotype_cp_min.parquet
│       └── phenotype_info.parquet
├── tsvs/
│   └── 1/A/{1,2}/{2,5,141}/segmentation_stats.tsv
└── eval/
    ├── features/1/cell_{DAPI,COXIV,CENPA,WGA}_min_heatmap.{png,tsv}
    └── segmentation/1/{cell_density_heatmap,segmentation_overview}.*



phenotype/
├── aligned_1.zarr/                              # HCS plate: primary image
│   └── A/
│       ├── 1/                                 # well A1
│       │   ├── {2,5,141}/                     # tiles
│       │   │   ├── zarr.json                  # multiscales + omero
│       │   │   ├── 0/, 1/, 2/, ...
│       │   │   └── labels/
│       │   │       ├── cells.zarr/
│       │   │       ├── nuclei.zarr/
│       │   │       └── identified_cytoplasms.zarr/   # phenotype-only
│       └── 2/                                 # well A2
│           └── (same structure)
├── illumination_corrected_1.zarr/               # HCS plate: derived image
│   └── A/1/{2,5,141}/ ...
│
├── parquets/
│   └── 1/A/{1,2}/
│       ├── phenotype_cp.parquet
│       ├── phenotype_cp_min.parquet
│       └── phenotype_info.parquet
├── tsvs/
│   └── 1/A/{1,2}/{2,5,141}/segmentation_stats.tsv
└── eval/
    ├── features/1/cell_{DAPI,COXIV,CENPA,WGA}_min_heatmap.{png,tsv}
    └── segmentation/1/{cell_density_heatmap,segmentation_overview}.*


```

#### Zarr: Preprocess Module (`brieflow_output_zarr/preprocess/`)

```
preprocess/
├── sbs/1.zarr/                                  # SBS plate store
│   └── A/{1,2}/                                 # row/col
│       └── {0,2,32}/                            # tiles
│           └── {1..11}/image.zarr/              # per-cycle images
├── phenotype/1.zarr/                            # phenotype plate store
│   └── A/{1,2}/
│       └── {2,5,141}/image.zarr/               # single acquisition
├── ic_fields/
│   ├── sbs/1/A/{1,2}/{1..11}/ic_field.zarr/    # per-cycle IC fields
│   └── phenotype/1/A/{1,2}/ic_field.zarr/
└── metadata/
    ├── sbs/1/A/{1,2}/combined_metadata.parquet
    └── phenotype/1/A/{1,2}/combined_metadata.parquet
```

#### TIFF (flat naming, for comparison)

```
sbs/
├── images/P-1_W-A1_T-0__{nuclei,cells}.tiff    # flat: P-{plate}_W-{well}_T-{tile}__{type}
├── parquets/P-1_W-A1__{cells,reads,sbs_info}.parquet
├── tsvs/P-1_W-A1_T-0__segmentation_stats.tsv
└── eval/{mapping,segmentation}/P-1__*.{png,tsv}

phenotype/
├── images/P-1_W-A1_T-2__{aligned,nuclei,cells}.tiff
├── parquets/P-1_W-A1__{phenotype_cp,phenotype_cp_min,phenotype_info}.parquet
├── tsvs/P-1_W-A1_T-2__segmentation_stats.tsv
└── eval/{features,segmentation}/P-1__*.{png,tsv}
```

**Key structural difference:** Zarr replaces the flat `P-{plate}_W-{well}_T-{tile}__` naming with the OME-Zarr HCS hierarchy `{plate}.zarr/{row}/{col}/{tile}/`. Non-image outputs (parquets, tsvs, eval) use the analogous nested `{plate}/{row}/{col}/` directory path.

---

### Final: Merge to Main

After Steps 1-6 are validated:

- Review and merge `zarr3-transition` branch in brieflow submodule
- Update submodule pointer in analysis repo
- Confirm full pipeline passes with HCS structure + metadata

---

## Key Files

| File | Purpose |
|------|---------|
| `zarr3_biohub_spec.md` | BioHub reference spec we're aligning to |
| `workflow/lib/shared/io.py` | `read_image()` / `save_image()` dispatchers |
| `workflow/lib/shared/omezarr_writer.py` | Zarr writing logic (pyramids, metadata) |
| `workflow/lib/shared/file_utils.py` | `get_nested_path()` / `get_hcs_nested_path()` / `parse_nested_path()` |
| `workflow/lib/shared/hcs.py` | `discover_plate_structure()` + `write_hcs_metadata()` (metadata-only fusion) |
| `workflow/scripts/shared/write_hcs_metadata.py` | HCS finalize script (calls `write_hcs_metadata()` per plate) |
| `workflow/targets/{preprocess,sbs,phenotype,merge}.smk` | Module-specific path helpers using `_get_path()`/`_get_image_path()` dispatchers |
| `tests/small_test_analysis/` | Test data + run scripts |
| `tests/small_test_analysis/notebooks/metadata_enrichment.ipynb` | Starter notebook for metadata enrichment |

## Contacts and Collaboration

| Person | Affiliation | Role |
|--------|-------------|------|
| **Mikala** | CZ Initiative (CZI) | Point of contact for OME-Zarr / iohub questions |
| **Ege** | Cheeseman Lab | Needs to join the BioHub Slack channel (see below) |

**BioHub Slack channel:** There is a Slack channel with CZ BioHub collaborators where OME-Zarr implementation decisions, iohub updates, and spec discussions happen. Ege needs to be added to this channel. Matteo can facilitate the invite.

The BioHub team is a valuable resource for:
- OME-Zarr best practices and spec interpretation
- iohub usage and feature requests
- Feedback on our HCS layout and metadata approach
- Guidance on the tables/AnnData question

## References

- [OME-NGFF v0.5 Spec](https://ngff.openmicroscopy.org/latest/)
- [HCS Plate Layout](https://ngff.openmicroscopy.org/latest/#hcs-layout)
- [Zarr v3 Migration Guide](https://zarr.readthedocs.io/en/stable/user-guide/v3_migration/)
- [ome-zarr-py Docs](https://ome-zarr.readthedocs.io/)
- [BioHub Reference Implementation](zarr3_biohub_spec.md)
- [Brieflow Docs](https://brieflow.readthedocs.io/)
- [PR #179](https://github.com/cheeseman-lab/brieflow/pull/179)
- [ome/ngff#64 — Tables spec discussion](https://github.com/ome/ngff/pull/64)
- [iohub — CZ Biohub OME-Zarr I/O](https://github.com/czbiohub-sf/iohub)
