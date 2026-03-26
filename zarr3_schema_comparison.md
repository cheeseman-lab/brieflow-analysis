# Brieflow Zarr Output vs OPS Schema Example — Comparison Report

**Date:** 2026-03-26
**Reference:** `ops-schema/standards/ops/0.1.0/examples/zarr-example.md`
**Brieflow output compared:** `brieflow_output_zarr/phenotype/aligned_1.zarr` (tile A/1/2)
**Brieflow version:** `zarr3-transition` branch (post step 4a/4b)

This report compares every level of the Brieflow zarr output against the OPS schema reference example. For each divergence, a recommendation for Brieflow is provided.

---

## Level 0 — Plate Root

### What the example has
```yaml
attributes:
  ome:
    version: "0.5"
    plate:
      version: "0.5"
      name: "example_screen"
      field_count: 1
      acquisitions: [{id: 0}]
      rows: [{name: "A"}]
      columns: [{name: "1"}, ...]
      wells: [{path: "A/1", rowIndex: 0, columnIndex: 0}, ...]
  channels_metadata:
    - name: "GFP"
      index: 2
      channel_type: "fluorescence"       # note: not "fluorescent"
      biological_annotation:
        biological_target: "5xUPRE"
        marker: null
        marker_type: null
        full_label: "5xUPRE"
      description: "Max projected 5xUPRE"
      fluorophore: "GFP"
      excitation_wavelength_nm: 488
      emission_wavelength_nm: 510
      antibody_catalog_id: null
```

### What Brieflow currently outputs
```json
{
  "ome": {
    "plate": {
      "version": "0.5",
      "acquisitions": [{"id": 0}],
      "rows": [{"name": "A"}],
      "columns": [{"name": "1"}, {"name": "2"}],
      "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}, ...]
    },
    "version": "0.5"
  },
  "channels_metadata": [
    {
      "name": "DAPI",
      "index": 0,
      "channel_type": "fluorescent",
      "description": "Nuclear stain"
    }
  ]
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| `ome.plate.name` | `"example_screen"` | **MISSING** | Medium — REQUIRED by spec |
| `ome.plate.field_count` | `1` | **MISSING** | Medium — REQUIRED by spec |
| `channels_metadata[].channel_type` | `"fluorescence"` | `"fluorescent"` | Low — stale enum value |
| `channels_metadata[].biological_annotation` | present | **MISSING** | High — REQUIRED for fluorescence channels |
| `channels_metadata[].fluorophore` | present (null ok) | **MISSING** | Low — OPTIONAL |
| `channels_metadata[].excitation_wavelength_nm` | present (null ok) | **MISSING** | Low — OPTIONAL |
| `channels_metadata[].emission_wavelength_nm` | present (null ok) | **MISSING** | Low — OPTIONAL |
| `channels_metadata[].antibody_catalog_id` | present (null ok) | **MISSING** | Low — OPTIONAL |

### Recommendations

- **`channel_type` enum**: Change `"fluorescent"` → `"fluorescence"` in `write_hcs_metadata.py`. The schema has been updated and the example uses the new values (`"fluorescence"`, `"labelfree"`, `"predicted"`). One-line fix.

- **`ome.plate.name` and `field_count`**: These should be populated from config. `plate.name` = store filename stem (e.g., `"aligned_1"`); `field_count` = number of image paths per well (can be derived at write time). Low-effort addition to `write_hcs_metadata()` in `hcs.py`.

- **`biological_annotation`**: This is where the most thought is needed. The spec requires `biological_target`, `marker`, `marker_type`, `full_label` for fluorescence channels. For Brieflow, these would need to come from experiment config (the user knows what DAPI stains, what antibody was used for CENPA, etc.). **Recommendation:** Add an optional `channels_metadata` config block in the Snakemake config YAML that users can fill in if they want schema compliance. When absent, omit the field rather than writing empty/null values. Don't block pipeline execution on it.

- **Optional fields** (`fluorophore`, wavelengths): Same approach — pull from config if provided, omit if not.

---

## Level 1 — Row Group

### What the example has
```yaml
attributes: {}
```

### What Brieflow outputs
```json
{"attributes": {}}
```

✅ **Match.** No action needed.

---

## Level 2 — Well Group

### What the example has
```yaml
attributes:
  ome:
    version: "0.5"
    well:
      version: "0.5"
      images:
        - acquisition: 0
          path: "0"          # sequential 0-based image index
  microscopy:
    microscope_type: null
    objective: null
    magnification: null
    numerical_aperture: null
    acquisition_mode: null
    is_live_imaging: false
    is_fixed_imaging: true
  omero:
    name: "0"
    channels: [...]         # full OMERO rendering block at well level
    rdefs: {defaultT: 0, defaultZ: 0, model: "color"}
  container:
    container_uid: null
    container_type: null
    well_position: "A1"
    cell_line: null
    culture_conditions: {media: null, temperature_celsius: null, co2_percentage: null}
    cell_product_lot_id: null
    passage_number: null
  acquisition_uid: null
  acquisition_timestamp: null
```

### What Brieflow outputs
```json
{
  "ome": {
    "version": "0.5",
    "well": {
      "images": [
        {"path": "141", "acquisition": 0},
        {"path": "2",   "acquisition": 0},
        {"path": "5",   "acquisition": 0}
      ]
    }
  }
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| `ome.well.version` | `"0.5"` | absent | Trivial — not required by spec |
| Image paths | `"0"`, `"1"`, ... | `"2"`, `"5"`, `"141"` | **Structural** — see below |
| `microscopy` block | present (nulls ok) | **MISSING** | Low — not in spec as REQUIRED |
| `omero` at well level | present | **MISSING** | Low — not required by spec |
| `container` block | present (nulls ok) | **MISSING** | Low — not in spec as REQUIRED |
| `acquisition_uid` | present (null ok) | **MISSING** | Low — not in spec as REQUIRED |
| `acquisition_timestamp` | present (null ok) | **MISSING** | Low — not in spec as REQUIRED |

### Structural note: tile IDs as image paths

The example uses sequential `"0"`, `"1"`, `"2"` as well image paths (one FOV per well). Brieflow uses **actual microscope tile IDs** (`"2"`, `"5"`, `"141"`) as paths — meaning each well can contain many tiles (one per FOV). This is a deliberate design choice in Brieflow that doesn't break spec compliance (the spec doesn't mandate sequential numbering), but it means `field_count` at the plate root would need to equal the maximum number of tiles in any well.

### Recommendations

- **`microscopy` block**: Valuable metadata that viewers and downstream tools could use. **Recommendation:** Add as an optional config block (`microscopy_metadata:` in config YAML). Populate `magnification`, `acquisition_mode`, `is_fixed_imaging` from config; leave instrument-specific fields as `null` when not provided. Low effort, high value for schema alignment.

- **`omero` at well level**: The example places OMERO rendering hints at both the well level and the image level. This is redundant with our tile-level omero but helps viewers that read only the well level. **Recommendation:** Defer — not required, adds complexity. Revisit if viewers have trouble finding rendering hints.

- **`container` and `acquisition_*`**: Useful for provenance. **Recommendation:** Add as optional config fields. `well_position` is derivable from row/col. Others require user input. Same optional config block approach.

---

## Level 3 — Image Group (Tile/FOV)

### What the example has
```yaml
attributes:
  ome:
    version: "0.5"
    multiscales:
      - version: "0.5"
        name: "0"
        axes:
          - {name: "T", type: "time",    unit: "second"}
          - {name: "C", type: "channel"}
          - {name: "Z", type: "space",   unit: "micrometer"}
          - {name: "Y", type: "space",   unit: "micrometer"}
          - {name: "X", type: "space",   unit: "micrometer"}
        datasets:
          - path: "0"
            coordinateTransformations:
              - {type: "scale", scale: [1.0, 1.0, 2.0, 0.65, 0.65]}
        downsamplingMethod: "gaussian"
    omero:
      version: "0.5"
      id: 0
      name: "0"
      channels: [...]
      rdefs: {defaultT: 0, defaultZ: 0, model: "color", projection: "normal"}
  custom_metadata:
    normalization: {channel: {dataset_statistics: {...}, fov_statistics: {...}}}
    clims_per_level: {"1": {contrast_limits: [...], per_channel: {...}}, ...}
```

### What Brieflow outputs
```json
{
  "ome": {
    "multiscales": [{
      "axes": [
        {"name": "t", "type": "time"},
        {"name": "c", "type": "channel"},
        {"name": "z", "type": "space", "unit": "micrometer"},
        {"name": "y", "type": "space", "unit": "micrometer"},
        {"name": "x", "type": "space", "unit": "micrometer"}
      ],
      "datasets": [
        {"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [1.0, 1.0, 1.0, 1.625, 1.625]}]},
        ...
      ],
      "name": "/"
    }],
    "omero": {
      "version": "0.5",
      "channels": [...],
      "rdefs": {"defaultT": 0, "defaultZ": 0, "model": "color", "projection": "normal"}
    },
    "version": "0.5"
  }
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| Axis name casing | `"T"`, `"C"`, `"Z"`, `"Y"`, `"X"` | `"t"`, `"c"`, `"z"`, `"y"`, `"x"` | Low — OME-NGFF spec doesn't mandate case |
| `t` axis unit | `"second"` | absent | Low — no time-series data, singleton T |
| `multiscales[].name` | `"0"` | `"/"` | Low — cosmetic |
| `multiscales[].version` | `"0.5"` | absent | Low |
| `omero.id` | `0` | absent | Trivial |
| `omero.name` | `"0"` | absent | Trivial |
| `downsamplingMethod` | `"gaussian"` | **MISSING** | Low — RECOMMENDED by spec |
| `custom_metadata` (normalization, clims) | present | **MISSING** | Medium — not required but valuable |
| Z scale | `2.0` (non-trivial Z step) | `1.0` (singleton Z) | Structural — Brieflow is 2D |

### Recommendations

- **Axis name casing**: OME-NGFF v0.5 spec uses lowercase in its own examples. The schema example's uppercase is inconsistent with the spec. **Recommendation: keep lowercase** — it's more consistent with OME-NGFF spec and iohub.

- **`t` axis unit**: The example adds `"second"` for the time axis. For Brieflow (singleton T, no time series), this is unnecessary. **Recommendation: leave absent** — adding `"second"` to a dummy T axis is misleading.

- **`downsamplingMethod`**: Easy one-line addition. `ome_zarr.writer` uses Gaussian downsampling by default via the `Scaler` class. **Recommendation: add `"gaussian"`** to the multiscales metadata in `write_image_omezarr()`. Low effort, improves compliance.

- **`custom_metadata` (normalization stats and contrast limits per pyramid level)**: The example stores per-channel dataset statistics (mean, std, median, IQR) and empirical contrast limits at each pyramid level. This is very useful for viewers to set initial display ranges intelligently, rather than defaulting to 0–65535. **Recommendation:** This is worth implementing as a future enhancement, but requires a post-write statistics pass over the data (compute percentile-based contrast limits per channel per pyramid level). Not trivial — defer to a separate step/PR.

---

## Level 4 — Resolution Arrays

### What the example has
```yaml
data_type: float32
shape: [1, 6, 1, 65536, 65536]
chunk_grid:
  name: regular
  configuration:
    chunk_shape: [1, 6, 1, 8192, 8192]   # outer shard shape
codecs:
  - name: sharding_indexed
    configuration:
      chunk_shape: [1, 1, 1, 512, 512]   # inner chunk
      codecs:
        - {name: bytes, configuration: {endian: little}}
        - {name: blosc, configuration: {cname: zstd, clevel: 1, shuffle: bitshuffle}}
      index_codecs:
        - {name: bytes, configuration: {endian: little}}
        - {name: crc32c}
      index_location: end
```

### What Brieflow outputs
```json
{
  "data_type": "uint16",
  "shape": [1, 4, 1, 2400, 2400],
  "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": [1, 4, 1, 1024, 1024]}},
  "codecs": [
    {"name": "bytes", "configuration": {"endian": "little"}},
    {"name": "zstd",  "configuration": {"level": 0, "checksum": false}}
  ]
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| **Codec: sharding** | `sharding_indexed` outer | flat `bytes`+`zstd` | **High — REQUIRED by spec** |
| Inner chunk shape | `[1,1,1,512,512]` | N/A (no sharding) | High |
| Index codecs | `bytes` + `crc32c` | N/A (no sharding) | High |
| Compression | `blosc/zstd, bitshuffle` | `zstd level=0` | Low — both accepted by spec |
| `data_type` | `float32` (virtual stains) / `uint16` | `uint16` | OK — data-dependent |

### What sharding actually does vs flat chunks

Sharding and flat chunks store **identical pixel data** — the only difference is packaging:

- **Flat chunks (current):** each chunk is its own file on disk. For a `2400×2400` tile with `1024×1024` chunks, that's **9 files per pyramid level** (~17 files across all 5 levels for one tile).
- **Sharding:** all chunks for a tile are concatenated into **1 shard file**, with an index table at the end recording the byte offset and length of each inner chunk. A reader opens the file, reads the index, then seeks directly to the chunk it needs.

The compressed bytes inside are identical. Sharding is purely a packaging change that reduces file count.

### Sharding and Slurm: data race risk

With flat chunks, Slurm jobs writing different tiles never touch the same file — no coordination needed. With sharding, if multiple jobs write chunks that land in the **same shard file**, they create a data race: both read the shard, write their chunk's bytes, then write the shard back — the last writer silently overwrites the first's data.

**Option 1 — shard boundaries = tile boundaries** eliminates this: make the outer shard shape equal to the full tile (`[1, C, 1, full_Y, full_X]`). Each Slurm job writes exactly one complete shard file with no overlap. This is what the OPS example does with its `[1, 6, 1, 8192, 8192]` outer shard.

However, this is **functionally nearly identical to what we already have**. Our current setup: 9 chunk files per tile per pyramid level. Option 1 sharding: 1 shard file per tile per pyramid level containing those same 9 chunks internally. The parallel write safety is identical in both cases — each job still owns exactly one file (or set of files) that no other job touches.

The only practical gain over what we have is **reduced file count** on the filesystem (~9× fewer files per pyramid level). This matters at scale (large screens, object storage like S3 where per-file overhead is significant) but is not urgent for a single-lab HPC setup.

### Why sharding is not urgent for Brieflow

1. **Functionally correct today** — flat chunks read and write fine with napari, ome-zarr-py, and iohub
2. **Parallel write safety already achieved** — our tile-per-job layout gives the same safety as Option 1 sharding
3. **Implementation blocked** — `ome-zarr-py` doesn't support `sharding_indexed` yet; implementing it now requires custom array code or a separate rechunking pass
4. **Schema is still a draft** — the sharding requirement may evolve before v1.0.0
5. **Not a data race risk** — our current layout already avoids the race condition that sharding can introduce

### Implementation options when the time comes

1. **Write with ome-zarr then re-shard with `zarr-rechunk` or `tensorstore`** — post-processing step after writing. Decouples pipeline from sharding complexity but adds a rewrite pass.
2. **Write directly with `tensorstore`** — bypasses ome-zarr-py entirely; full control over shard config but higher implementation cost.
3. **Wait for ome-zarr-py sharding support** — the project is tracking Zarr v3 sharding; when it lands, enabling it in `write_image_omezarr()` would be a config change.

**Recommendation for Brieflow:** Defer sharding until either `ome-zarr-py` adds native support or data is being prepared for an OPS submission. Document it as a known divergence. When implemented, use Option 1 shard boundaries (shard = full tile) to preserve parallel write safety.

---

## Level 5 — Labels Container

### What the example has
```yaml
attributes:
  ome:
    version: "0.5"
    labels:
      - nuclear_seg
      - cell_seg
      - mitochondria_seg
      ...
```

### What Brieflow outputs
```json
{
  "ome": {
    "version": "0.5",
    "labels": ["cells", "identified_cytoplasms", "nuclei"]
  }
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| Label naming convention | `nuclear_seg`, `cell_seg` | `nuclei`, `cells`, `identified_cytoplasms` | Low — cosmetic |

### Recommendation

The example uses a `_seg` suffix convention. Brieflow's names are readable and not incorrect. **Recommendation: no change required**, but consider adopting a consistent suffix if the schema formalizes this in a future version.

---

## Level 6 — Label Group

### What the example has
```yaml
attributes:
  segmentation_metadata:
    label_name: "cell_seg"
    annotation_type: "cell_segmentation"
    is_ome_label: true
    source_channel:
      index: 5
    biological_annotation:
      biological_target: "cell_membrane"
      marker: "virtual stain"
      marker_type: "virtual_stain"
      full_label: "cell membrane, virtual stain"
    segmentation:
      method: "cellpose-sam"
      version: "cell_seg-v1"
      stitching: "hybrid_iou"
      parameters: {diameter: 100, flow_threshold: 0.7, ...}
    statistics:
      n_cells: 12000000
    description: "Cell segmentation from membrane virtual stain..."
```

### What Brieflow outputs
```json
{
  "ome": {
    "version": "0.5",
    "multiscales": [{
      "datasets": [
        {"path": "0", "coordinateTransformations": [{"scale": [1.0,1.0,1.0,1.0,1.0], "type": "scale"}]},
        ...
      ],
      "name": "/",
      "axes": [
        {"name": "t", "type": "time"},
        {"name": "c", "type": "channel"},
        {"name": "z", "type": "space"},
        {"name": "y", "type": "space"},
        {"name": "x", "type": "space"}
      ]
    }],
    "omero": {"channels": [{"label": "c0", "active": true}]},
    "image-label": {"version": "0.5"}
  }
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| `segmentation_metadata` block | **present** (entire block) | **MISSING** | High — all fields REQUIRED by spec |
| Label coordinate scales | per-dataset physical scales | all `[1.0,1.0,1.0,1.0,1.0]` | High — pixel sizes not applied to label stores |
| Axis units on z/y/x | not shown (example is a group) | absent | Medium — should have `micrometer` like parent |
| `omero` on label group | absent in example | present (`c0`) | Low — harmless, iohub adds it automatically |

### Recommendations

- **`segmentation_metadata`**: This requires the pipeline to know, for each label store: what method was used, what version, what biological target, and how many cells were found. `n_cells` can be computed at write time from the label array (count unique non-zero values). Method/version/parameters should come from config or be written by the segmentation rule itself. **Recommendation:** Have each segmentation Snakemake rule write a sidecar `segmentation_info.json` at the time of segmentation, which `_patch_label_versions` (or a new `_patch_label_metadata` function) can read and inject. This makes the metadata authoritative and co-located with the computation that generates it.

- **Label coordinate scales**: Currently `_patch_label_versions()` only sets `image-label.version`. It should also call `_set_per_dataset_scales()` on label stores using the same pixel size as the parent image. **Recommendation: extend `_patch_label_versions()` (or add a `_patch_label_scales()` function) to apply pixel sizes to label zarr multiscales**.

- **`omero` on label group**: iohub writes this automatically. It's harmless — leave it.

---

## Level 7 — Label Resolution Array

### What the example has
```yaml
data_type: int32
shape: [1, 1, 1, 65536, 65536]
chunk_grid:
  configuration:
    chunk_shape: [1, 1, 1, 16384, 16384]  # outer shard
codecs:
  - name: sharding_indexed
    configuration:
      chunk_shape: [1, 1, 1, 512, 512]    # inner chunk
      codecs: [bytes, zstd]
      index_codecs: [bytes, crc32c]
```

### What Brieflow outputs
```json
{
  "data_type": "uint16",
  "shape": [1, 1, 1, 2400, 2400],
  "chunk_grid": {"configuration": {"chunk_shape": [1, 1, 1, 1024, 1024]}},
  "codecs": [
    {"name": "bytes"},
    {"name": "zstd"}
  ]
}
```

### Divergences

| Field | Example | Brieflow | Severity |
|-------|---------|----------|----------|
| Codec: sharding | `sharding_indexed` | flat `bytes`+`zstd` | High — same issue as Level 4 |
| `data_type` | `int32` | `uint16` | Medium — spec says `uint32`; `uint16` limits max cell count to 65535 |

### Recommendations

- **Sharding**: Same recommendation as Level 4 — defer to a rechunking post-step.

- **`data_type` for label arrays**: `uint16` caps the number of uniquely labeled objects at 65,535. For large screens with many cells per tile, this may be insufficient. The spec recommends `uint32` (supports ~4 billion labels). **Recommendation: change label array dtype to `uint32` in the segmentation output rules.** This is a low-risk change that prevents a hard limit being hit on large datasets.

---

## Summary Table

| # | Level | Issue | Severity | Recommendation |
|---|-------|-------|----------|----------------|
| 1 | L0 | `channel_type` uses `"fluorescent"` not `"fluorescence"` | Low | One-line fix in `write_hcs_metadata.py` |
| 2 | L0 | `ome.plate.name` missing | Medium | Derive from store filename, add to `write_hcs_metadata()` |
| 3 | L0 | `ome.plate.field_count` missing | Medium | Count well images at write time |
| 4 | L0 | `channels_metadata[].biological_annotation` missing | High | Add optional config block; omit gracefully when not provided |
| 5 | L0 | Optional channel fields absent (`fluorophore`, wavelengths, etc.) | Low | Add as optional config fields |
| 6 | L3 | `downsamplingMethod` not set | Low | Add `"gaussian"` to multiscales in `write_image_omezarr()` |
| 7 | L3 | Axis name casing (lowercase vs uppercase) | Low | Keep lowercase — consistent with OME-NGFF spec |
| 8 | L3 | `custom_metadata` (normalization stats, per-level contrast limits) | Medium | Defer — requires post-write statistics pass; high value for viewers |
| 9 | L4+L7 | **No sharding** — flat chunks instead of `sharding_indexed` | High | Defer — implement as optional post-write rechunking step; track ome-zarr-py sharding support |
| 10 | L6 | `segmentation_metadata` entirely missing | High | Segmentation rules write sidecar `segmentation_info.json`; inject at finalize step |
| 11 | L6 | Label pixel scales all `[1.0,1.0,1.0,1.0,1.0]` | High | Extend `_patch_label_versions()` to also apply pixel scales to label multiscales |
| 12 | L7 | Label `data_type: uint16` instead of `uint32` | Medium | Change segmentation output dtype to `uint32` |
| 13 | L2 | Well-level `microscopy`, `container`, `acquisition_*` blocks absent | Low | Add as optional config; useful for provenance |

---

## Prioritized Recommendations for Brieflow

### Immediate / Low Effort
These are small fixes that improve compliance without architectural changes:

1. **Fix `channel_type` enum** (`"fluorescent"` → `"fluorescence"`) in `write_hcs_metadata.py`
2. **Add `ome.plate.name` and `field_count`** in `hcs.py` at plate write time
3. **Add `downsamplingMethod: "gaussian"`** to multiscales metadata in `io.py`
4. **Change label dtype to `uint32`** in segmentation rules

### Medium Effort
5. **Apply pixel scales to label stores** — extend `_patch_label_versions()` to call `_set_per_dataset_scales()` for each label zarr
6. **Add optional `biological_annotation` config** — allow users to supply per-channel biological metadata via config YAML; inject at finalize time
7. **Add optional well-level metadata** (`microscopy`, `container`) via config YAML

### Larger / Deferred
8. **`segmentation_metadata`** — requires sidecar JSON from segmentation rules + injection at finalize. Significant but high value for schema compliance.
9. **`custom_metadata` (per-level contrast limits)** — requires post-write statistics computation. High value for downstream viewers.
10. **Sharding** — requires either ome-zarr-py upgrade or a separate rechunking tool. The highest-impact compliance gap but also the most complex to implement within the current write pipeline.
