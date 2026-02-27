# Zarr Metadata Improvements: `io.py` Guide

## Context

Every zarr store in our pipeline is written by `save_image()` in `workflow/lib/shared/io.py`, which calls `write_image_omezarr()`. Currently, the metadata written to each store is minimal — generic channel names (`c0, c1, ...`), no pixel sizes, no axis units, sparse `omero` rendering info. This guide covers what to fix and where the data comes from.

## Current state vs target

Here's what `aligned.zarr/zarr.json` looks like today:

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
          {"path": "0", "coordinateTransformations": [{"scale": [1.0, 1.0, 1.0], "type": "scale"}]},
          {"path": "1", "coordinateTransformations": [{"scale": [1.0, 1.0, 1.0], "type": "scale"}]}
        ]
      }]
    },
    "omero": {
      "channels": [
        {"label": "c0", "active": true, "color": "FFFFFF"},
        {"label": "c1", "active": true, "color": "FFFFFF"}
      ]
    }
  }
}
```

Target (what it should look like):

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
          {"path": "0", "coordinateTransformations": [{"scale": [1.0, 0.325, 0.325], "type": "scale"}]},
          {"path": "1", "coordinateTransformations": [{"scale": [1.0, 0.65, 0.65], "type": "scale"}]}
        ]
      }]
    },
    "omero": {
      "version": "0.5",
      "channels": [
        {"label": "DAPI", "active": true, "color": "0000FF", "coefficient": 1.0, "family": "linear", "inverted": false},
        {"label": "COXIV", "active": true, "color": "00FF00", "coefficient": 1.0, "family": "linear", "inverted": false}
      ],
      "rdefs": {"defaultT": 0, "defaultZ": 0, "model": "color", "projection": "normal"}
    },
    "image-label": {"version": "0.5"}
  }
}
```

---

## Fix 1: Axis units

**File:** `io.py` → `write_image_omezarr()`

**Problem:** Axes are written as `{"name": "y", "type": "space"}` — no `"unit"` field. Spatial axes should have `"unit": "micrometer"`.

**How it works:** The `ome_zarr.writer.write_image()` function from `ome-zarr-py` accepts axes as either a string like `"cyx"` or a list of dicts. We currently pass the string form. To add units, pass structured dicts instead:

```python
# Current
axes = "cyx"

# Target
axes = [
    {"name": "c", "type": "channel"},
    {"name": "y", "type": "space", "unit": "micrometer"},
    {"name": "x", "type": "space", "unit": "micrometer"},
]
```

**What to do:** In `write_image_omezarr()`, convert the `axes` string parameter into a list of dicts before passing to `write_image()`. Add `"unit": "micrometer"` to any axis with `type == "space"`. The unit should probably be a parameter with `"micrometer"` as default.

**Verify:** Check that `ome_zarr.writer.write_image()` accepts list-of-dict axes. If not, write the string form and post-process `root.attrs` after the call.

---

## Fix 2: Pixel sizes in `coordinateTransformations`

**File:** `io.py` → `write_image_omezarr()`

**Problem:** All scales are `[1.0, 1.0, 1.0]` because no script passes `pixel_size` to `save_image()`.

**How it works:** `write_image_omezarr()` already computes `coordinateTransformations` correctly from the `pixel_size_um` parameter (lines 177-186). The math is right — it scales by `coarsening_factor**i` per pyramid level. The problem is upstream: nothing passes the value.

**Where the data comes from:** The preprocessing step already extracts pixel sizes from the raw ND2 files and saves them in `combined_metadata.parquet`:

```
pixel_size_x: 0.325  (phenotype 20x)
pixel_size_y: 0.325
pixel_size_x: 1.3    (sbs 10x)
pixel_size_y: 1.3
```

These are in microns. The values are per-well (can vary if magnification differs between wells, which is rare but possible).

**What to do:**
1. Add `pixel_size_um` to the config YAML (one value per module since SBS and phenotype have different magnifications):
   ```yaml
   sbs:
     pixel_size_um: 1.3
   phenotype:
     pixel_size_um: 0.325
   ```
2. Pass it through Snakemake rules as a `params` value
3. Forward to `save_image(..., pixel_size=snakemake.params.pixel_size_um)`

**Alternative (auto-detect):** Read from `combined_metadata.parquet` at runtime. The metadata parquet exists before any image-writing step runs. Could have a helper that reads the parquet for the current plate/well and extracts pixel size. More complex but avoids manual config.

**Recommendation:** Start with config, validate against metadata parquet. Auto-detection can come later.

---

## Fix 3: Channel names

**File:** Every script that calls `save_image()`

**Problem:** Only `convert_image.py` (preprocessing) passes `channel_names=`. All other scripts (16 call sites) pass no channel names, so `write_image_omezarr()` generates `c0, c1, c2, ...`.

**Where the data comes from:** Channel names already exist in config:

```yaml
sbs:
  channel_names: [DAPI, G, T, A, C]
phenotype:
  channel_names: [DAPI, COXIV, CENPA, WGA]
```

They're also embedded in the ND2 filenames (`Channel_Cy7,Cy5,AF594,Cy3_SBS,DAPI_SBS`), but the config values are the canonical source.

**What to do:** For each script that calls `save_image()`:
1. Accept channel names via `snakemake.params.channel_names`
2. Pass to `save_image(..., channel_names=channel_names)`

**Complication — not all outputs have the same channels:**
- `aligned.zarr`: full channel set (all SBS or phenotype channels)
- `illumination_corrected.zarr`: same as aligned
- `max_filtered.zarr`: reduced channels (SBS-specific processing)
- `peaks.zarr`: single channel
- `standard_deviation.zarr`: single channel
- `nuclei.zarr` / `cells.zarr`: label images (single channel, `is_label=True`)

Label images don't need channel names (they're segmentation masks). For single-channel derived outputs, a descriptive name (e.g. `"max_filtered"`, `"peaks"`) is more useful than `"c0"`.

**Recommendation:** Pass full channel list for multi-channel outputs (aligned, illumination_corrected). For single/reduced-channel derived outputs, pass a descriptive name from the rule. Labels can keep the default.

---

## Fix 4: `omero.channels` rendering defaults

**File:** `io.py` → `write_image_omezarr()`

**Problem:** Each channel entry only has `{"label": "...", "active": true, "color": "FFFFFF"}`. Missing fields that viewers use.

**What to add (all have sensible defaults):**

```python
{
    "label": name,
    "active": True,
    "color": color,           # see below
    "coefficient": 1.0,       # always 1.0
    "family": "linear",       # always linear
    "inverted": False,        # always false
}
```

**Channel colors:** Currently everything is white (`"FFFFFF"`). For fluorescence channels, conventional colors would be better:
- DAPI → `"0000FF"` (blue)
- GFP/FITC → `"00FF00"` (green)
- Cy3/mCherry → `"FF0000"` (red)
- Cy5 → `"FF00FF"` (magenta)

**Option:** Accept an optional `channel_colors` list in `save_image()`. Default to white if not provided. Could also be config-driven.

**`window` (contrast limits):** The spec says these SHOULD be present but the schema doesn't require them (see ome/ngff#192, #430). Adding them makes napari display images with useful initial contrast instead of min/max of dtype. Computing them requires reading the data (e.g. 1st/99th percentile). This is a nice-to-have — skip for now, add later as a separate pass.

---

## Fix 5: `omero.rdefs`

**File:** `io.py` → `write_image_omezarr()`

**Problem:** Not written at all. These are rendering defaults that viewers read.

**What to add:**

```python
omero["rdefs"] = {
    "defaultT": 0,
    "defaultZ": 0,
    "model": "color",
    "projection": "normal",
}
```

Static values. Add unconditionally when `omero` is being written.

---

## Fix 6: `omero.version`

**File:** `io.py` → `write_image_omezarr()`

**Problem:** `omero` dict has no version field.

**What to add:** `omero["version"] = "0.5"`. One line.

---

## Fix 7: `image-label` version

**File:** `io.py` → `write_image_omezarr()`

**Problem:** Label stores get `"image-label": {}` (empty dict). Should include version.

**What to change:**

```python
# Current
if is_label:
    metadata["image-label"] = {}

# Target
if is_label:
    metadata["image-label"] = {"version": "0.5"}
```

---

## Summary: what changes where

### `io.py` changes (self-contained, no config needed):

| Fix | Lines to change | Effort |
|-----|----------------|--------|
| Axis units | Convert axes string → list of dicts with units | ~15 lines |
| `omero.channels` defaults | Add `coefficient`, `family`, `inverted` | ~5 lines |
| `omero.rdefs` | Add static dict | ~5 lines |
| `omero.version` | Add `"version": "0.5"` | 1 line |
| `image-label` version | Change `{}` → `{"version": "0.5"}` | 1 line |

### Config + rules + scripts changes (threading metadata):

| Fix | What | Where |
|-----|------|-------|
| Pixel sizes | Add `pixel_size_um` to config, pass through rules → scripts → `save_image()` | Config YAML, every `.smk` rule with image output, every script |
| Channel names | Pass `channel_names` from config through rules → scripts → `save_image()` | Same scope, but need per-output logic for derived/reduced-channel images |
| Channel colors | Optional: add `channel_colors` to config or derive from channel names | Config YAML, `io.py` |

### Data sources already available:

| Metadata | Source | Location |
|----------|--------|----------|
| Pixel size (µm) | Extracted from ND2 headers during preprocessing | `preprocess/metadata/{modality}/{plate}/{well}/combined_metadata.parquet` → columns `pixel_size_x`, `pixel_size_y`, `pixel_size_z` |
| Channel count | Extracted from ND2 headers | Same parquet → column `channels` |
| Channel names | Config YAML (canonical) | `config.sbs.channel_names`, `config.phenotype.channel_names` |
| Objective magnification | Extracted from ND2 headers | Same parquet → column `objective_magnification` |

### Call sites that need `channel_names` and `pixel_size` threading:

| Script | Module | Output type | Channels |
|--------|--------|-------------|----------|
| `convert_image.py` | preprocess | raw image | Already passes channel_names ✓ |
| `apply_ic_field_sbs.py` | sbs | illumination_corrected | Full SBS channels |
| `align_cycles.py` | sbs | aligned | Full SBS channels |
| `log_filter.py` | sbs | log_filtered | Full SBS channels |
| `max_filter.py` | sbs | max_filtered | Reduced (base channels only) |
| `find_peaks.py` | sbs | peaks | 1 channel |
| `compute_standard_deviation.py` | sbs | standard_deviation | 1 channel |
| `apply_ic_field_phenotype.py` | phenotype | illumination_corrected | Full phenotype channels |
| `align_phenotype.py` | phenotype | aligned | Full phenotype channels |
| `segment.py` | shared | nuclei, cells | Label (no channel names needed) |
| `identify_cytoplasm_cellpose.py` | phenotype | cytoplasms | Label |
| `calculate_ic_field.py` | preprocess | ic_field | IC-specific |

---

## Suggested order of implementation

1. **Fixes 4-7** (`io.py` only) — omero defaults, rdefs, version, image-label version. Pure `io.py` changes, no config threading. ~30 lines total. Test by running the zarr pipeline and checking any output zarr.json.

2. **Fix 1** (axis units) — also `io.py` only, but need to verify `ome-zarr-py` accepts structured axes.

3. **Fix 2** (pixel sizes) — add `pixel_size_um` to config, thread through rules and scripts. Start with SBS and phenotype modules. Validate against metadata parquet values.

4. **Fix 3** (channel names) — thread config channel names through rules and scripts. Handle reduced-channel outputs separately.
