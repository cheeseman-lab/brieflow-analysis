# Zarr3 / OPS Schema Transition Notes

Tracks all code changes made to bring Brieflow's OME-Zarr output into alignment
with the OPS Data Standard v0.1.0 (`ops-schema/standards/ops/0.1.0/zarr-images.md`).

Changes were implemented across two branches of the `brieflow` submodule:
- `schema-updates` (Ege) — branched off `zarr3-transition`, then merged back
- `zarr3-schema-fixes` (Matteo) — also merged into `zarr3-transition`

All changes are now on `zarr3-transition`. Validated: 0 errors with ops-schema validator.

---

## Commit History

| Commit | Author | Description |
|--------|--------|-------------|
| `9a85ffb` | Ege | Schema compliance: plate.name, field_count, well.version, uppercase axes, label scales, segmentation_metadata |
| `a0e388b` | Matteo | Fix dtype to be spec compliant, fix gaussian scaling for saving images |
| `604894d` | Matteo | Latent ruff errors (formatting) |
| `f806ba1` | Matteo | Align downsamplingMethod declaration with actual method used |
| `2b6fbf2` | Matteo | Fix remaining schema compliance issues (axis units, n_cells, method.model, iohub strip fix) |

---

## Summary of All Changes

| Item | File(s) | Author |
|------|---------|--------|
| `plate.name` | `hcs.py` | Ege |
| `plate.field_count` | `hcs.py` | Ege |
| `well.version` | `hcs.py` | Ege |
| `channel_type` enum (`fluorescence`) | `hcs.py`, `config_omezarr.yml` | Ege |
| `biological_annotation` fields | `hcs.py`, `config_omezarr.yml` | Ege |
| Axis name casing (TCZYX uppercase) | `io.py` | Ege |
| Axis units at write time (T=second, Z/Y/X=micrometer) | `io.py` | Ege + Matteo |
| `downsamplingMethod` on multiscales | `io.py`, `write_hcs_metadata.py` | Ege + Matteo |
| Gaussian downsampling for non-label images | `io.py` | Matteo |
| Case-insensitive axis lookup (iohub compat) | `write_hcs_metadata.py` | Ege |
| Label coordinate scales | `write_hcs_metadata.py` | Ege |
| Label axis units (separate from scales) | `write_hcs_metadata.py` | Matteo |
| Re-inject `downsamplingMethod` after iohub `dump_meta` | `write_hcs_metadata.py` | Matteo |
| `segmentation_metadata` on label stores | `write_hcs_metadata.py` | Ege + Matteo |
| `segmentation.method` format (`cellpose.cyto3`) | `write_hcs_metadata.py` | Matteo |
| `segmentation.stitching` as string (`"none"`) | `write_hcs_metadata.py` | Matteo |
| `statistics.n_cells` (count unique labels) | `write_hcs_metadata.py` | Matteo |
| Label `data_type: uint32` | `segment.py` | Matteo |
| Snakemake rules — pass `modality` param | `sbs.smk`, `phenotype.smk` | Ege |

---

## Detailed Change Log

### 1. `hcs.py` — HCS metadata writer

**`write_hcs_metadata()` — added `field_count` computation**

```python
fields_by_well = {}
for row, col, tile in structure:
    fields_by_well.setdefault((row, col), []).append(tile)
field_count = max(len(tiles) for tiles in fields_by_well.values())
```

**`_write_plate_metadata()` — added `plate.name` and `plate.field_count`**

```python
plate_name = plate_path.stem  # e.g. "aligned_1"
"plate": {
    "version": "0.5",
    "name": plate_name,
    "field_count": field_count,
    ...
}
```

**`_write_well_metadata()` — added `well.version`**

```python
"well": {
    "version": "0.5",
    "images": [...]
}
```

**`_normalize_channels_metadata()` — fixed `channel_type` enum and `biological_annotation` field**

- `"fluorescent"` → `"fluorescence"` (DCA-aligned enum value)
- `"organelle"` → `"biological_target"` (field rename to match OPS schema)

---

### 2. `config_omezarr.yml` — test configuration

Updated all channel entries:

- `channel_type: fluorescent` → `channel_type: fluorescence` (all channels)
- `biological_annotation` blocks filled with real values:

| Channel | `biological_target` | `marker` | `marker_type` |
|---------|---------------------|----------|---------------|
| DAPI (phenotype) | `nucleus` | `DAPI` | `dye` |
| COXIV | `mitochondria` | `COXIV` | `antibody` |
| CENPA | `centromere` | `CENPA` | `antibody` |
| WGA | `cell_membrane` | `WGA` | `lectin` |
| DAPI (SBS) | `nucleus` | `DAPI` | `dye` |
| G / T / A / C | `in_situ_sequencing` | `SBS_G` … `SBS_C` | `sequencing_chemistry` |

---

### 3. `io.py` — unified image I/O

**Axis name casing: lowercase → uppercase (TCZYX)**

OPS schema and iohub v0.5 use uppercase axis names:

- `save_image()`: all axis strings `"tczyx"` → `"TCZYX"`
- `write_image_omezarr()`: default `axes="TCZYX"`, added `axes = axes.upper()` normalization
- All `axes.find()`/`axes.index()` calls updated to uppercase characters

**`_axes_str_to_dicts()` helper — solves ome_zarr uppercase incompatibility**

`ome_zarr.writer.write_image()` only recognises lowercase axis names for type
inference (`KNOWN_AXES` dict is all lowercase). Passing `"TCZYX"` caused all axes
to get `type=None`, failing the validator with:
`ValueError: Too many unknown axes types. 1 allowed, found: [None, None, None, None, None]`

Fix: convert the axes string to a list of dicts with explicit type and unit fields
before passing to `write_image()`. ome_zarr uses the dict values directly without
going through name-based lookup:

```python
_AXIS_TYPES = {"T": "time", "C": "channel", "Z": "space", "Y": "space", "X": "space"}
_AXIS_UNITS = {"T": "second", "Z": "micrometer", "Y": "micrometer", "X": "micrometer"}

def _axes_str_to_dicts(axes: str) -> list[dict]:
    # Each axis gets name + type + unit (where applicable) at write time
    ...
```

This means axis units are now set correctly at the point of image writing, not only
during the iohub patching step.

**Gaussian downsampling for non-label images (Matteo)**

```python
# before: always nearest-neighbor
method="nearest"

# after: gaussian for real images, nearest for labels (preserves integer values)
method="nearest" if is_label else "gaussian"
```

**`downsamplingMethod` on multiscales**

OPS schema RECOMMENDS `ome.multiscales[].downsamplingMethod`. Written at end of
`write_image_omezarr()` and matches the actual scaler:

```python
ms[0]["downsamplingMethod"] = "nearest" if is_label else "gaussian"
```

---

### 4. `write_hcs_metadata.py` — HCS finalize / iohub patching

**`_get_axis_index_ci()` — case-insensitive axis lookup**

Handles stores written with either old lowercase axes or new uppercase axes:

```python
def _get_axis_index_ci(pos, name: str) -> int:
    try:
        return pos.get_axis_index(name.upper())
    except (ValueError, KeyError):
        return pos.get_axis_index(name.lower())
```

Used by `_set_per_dataset_scales()`.

**`_patch_label_axis_units()` — label store axis units (Matteo)**

Separated from pixel scale patching so axis units are always set even when
preprocess metadata is unavailable:

```python
_AXIS_UNITS = {"X": "micrometer", "Y": "micrometer", "Z": "micrometer", "T": "second"}
```

Walks all `labels/*/zarr.json` and patches the `axes[].unit` field.

**`_patch_label_scales()` — pixel scales on label stores**

iohub does not expose label stores through its `Position` API. Direct JSON patching:

- Reads `pixel_map` (same per-tile pixel sizes used for the parent image)
- Finds Y and X axis indices (case-insensitive)
- Reads base array shape from level-0 `zarr.json` to compute downsampling factors
- Writes `coordinateTransformations` with absolute pixel scales per pyramid level

**`_patch_segmentation_metadata()` — segmentation_metadata on label stores**

Injects OPS-required `segmentation_metadata` block at `attributes.segmentation_metadata`.
Supported label stems and mappings:

| Label dir stem | `annotation_type` | `source_channel_key` |
|----------------|-------------------|----------------------|
| `nuclei` | `nucleus` | `dapi_index` |
| `cells` | `cell` | `cyto_index` |
| `identified_cytoplasms` | `cytoplasm` | `cyto_index` |

Fields populated per label:
- `label_name`, `annotation_type`, `is_ome_label: true`
- `source_channel.index` — from config `dapi_index` / `cyto_index`
- `biological_annotation` — pulled from `channels_metadata` for the source channel
- `segmentation.method` — `"method.model"` format e.g. `"cellpose.cyto3"` (Matteo)
- `segmentation.stitching` — `"none"` string (Matteo; schema requires string not boolean)
- `segmentation.parameters` — diameter, flow_threshold, cellprob_threshold
- `statistics.n_cells` — count of unique non-zero labels in the full-resolution array (Matteo)

**Re-inject `downsamplingMethod` after iohub `dump_meta` (Matteo)**

iohub's `dump_meta()` writes back only fields it knows about, stripping any
non-standard fields including `downsamplingMethod`. A post-iohub JSON patching
pass re-injects it on all tile-level image zarr.json files:

```python
for zj in sorted(store_path.rglob("*/zarr.json")):
    if "labels" in zj.parts:
        continue
    ...
    if ms_list and "downsamplingMethod" not in ms_list[0]:
        ms_list[0]["downsamplingMethod"] = "gaussian"
```

---

### 5. `segment.py` — segmentation script (Matteo)

**Label arrays cast to `uint32`**

`uint16` caps unique labeled objects at 65,535. For large screens this can be hit.
OPS schema recommends `uint32`:

```python
nuclei_data = nuclei_data.astype(np.uint32)
cells_data = cells_data.astype(np.uint32)
```

---

### 6. `sbs.smk` + `phenotype.smk` — Snakemake rules

Added `modality` param so `write_hcs_metadata.py` reads the correct config section
for segmentation parameters:

```python
# sbs.smk
params:
    ...
    modality="sbs",

# phenotype.smk
params:
    ...
    modality="phenotype",
```

---

## Deferred Changes

### Sharding (`sharding_indexed` codec)

**Why deferred:** `ome-zarr-py` does not yet support `sharding_indexed`. For
Brieflow's tile-per-job parallelism, shard-per-tile is functionally identical to
the current flat-chunk layout — no data race risk and same I/O pattern. Sharding
only becomes meaningful for whole-plate viewers reading across tiles or for
object storage (S3) where per-file overhead matters.

**Plan:** Revisit after `ome-zarr-py` adds shard support or when preparing data for
an OPS submission. Use shard boundaries = tile boundaries to preserve parallel write safety.

### Label directory naming convention

**Current:** `labels/nuclei.zarr`, `labels/cells.zarr`, `labels/identified_cytoplasms.zarr`

**Schema convention:** `_seg` suffix (e.g. `nuclei_seg`, `cell_seg`)

**Why deferred:** Renaming touches ~30+ occurrences across 16+ workflow scripts.
`segmentation_metadata.label_name` records the name in metadata, satisfying the
informational requirement.

---

## Pending: CZI / Biohub Feedback Items

Intentionally omitted pending feedback before the Brieflow → ops-schema PR:

- `microscopy` block (instrument, objective, pixel_size_um at plate level)
- `container` block (DOI, external links)
- `custom_metadata` block (per-level contrast limits, normalization stats)
- `segmentation_metadata.segmentation.version` (model version string — not easily available at runtime)
- Well-level `acquisition_uid`, `acquisition_timestamp`
