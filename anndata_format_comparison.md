# AnnData Format Comparison

Comparing our current single-cell AnnData (`format_singlecell_anndata` output) against the OPS schema standard (ops-schema v0.1.0) and the Lundberg Lab (Stanford) format.

**Sources:**
- Brieflow: `brieflow/tests/small_test_analysis/brieflow_output_zarr/aggregate/anndata/ChCo-DAPI_COXIV_CENPA_WGA__singlecell.h5ad`
- OPS schema: `ops-schema/standards/ops/0.1.0/cell-data.md`, `feature-definitions.md`, `aggregated-data.md`
- Lundberg Lab: AnnData summary provided directly

---

## Current Brieflow Single-Cell AnnData

```
AnnData: 1016 cells × 1635 features
obs:  plate, well, tile, cell_0, i_0, j_0, site, cell_1, i_1, j_1, distance,
      fov_distance_0, fov_distance_1, cell_barcode_0, gene_symbol_0,
      cell_barcode_1, gene_symbol_1, mapped_single_gene, channels_min,
      nucleus_i, nucleus_j, nucleus_bounds_0-3, cell_i, cell_j,
      cell_bounds_0-3, cytoplasm_i, cytoplasm_j, cytoplasm_bounds_0-3,
      cell_stage, row, class, confidence, batch_values, is_control
var:  compartment, channel, feature_type
obsm: spatial ([cell_i, cell_j])
uns:  pipeline (normalization, channel_combo, channels)
```

---

## OPS Schema (`cell-data.md`) — Single-Cell Table

The schema defines required and optional fields for the single-cell feature table.

### Required fields — compliance

| Schema field | Type | Our field | Status |
|---|---|---|---|
| `plate` | String | `plate` | ✅ Present (stored as float, should be string) |
| `well_row` | String | `row` | ⚠️ Present but named differently |
| `well_col` | Integer | not present | ❌ We store `well` as "A1" — not split |
| `tile` | Integer | `tile` | ✅ Present |
| `x` | Float | `cell_j` (via obsm['spatial']) | ⚠️ Present but named differently, stored in obsm not obs |
| `y` | Float | `cell_i` (via obsm['spatial']) | ⚠️ Present but named differently, stored in obsm not obs |
| `cell_uid` | Integer | not present | ❌ No globally unique cell identifier |
| `cell_seq_id` | Integer | `cell_0` | ⚠️ Present but named differently |
| `barcode` | String | `cell_barcode_0` | ⚠️ Present but named differently |
| `perturbation_id` | String | `gene_symbol_0` | ⚠️ Closest match but different concept — gene symbol is not the same as perturbation_id |

### Optional fields — compliance

| Schema field | Our field | Status |
|---|---|---|
| `bounding_box` | `nucleus_bounds_0-3`, `cell_bounds_0-3`, `cytoplasm_bounds_0-3` | ⚠️ Present but as 4 separate columns per compartment, not a single bounding_box field |
| `cell_class` | `class` | ⚠️ Present but named differently |
| `global_x`, `global_y` | not present | ❌ Not computed |

### var index format

The schema specifies `feature_id` in the format `{compartment}__{channel_or_type}__{measurement}` (double underscores), e.g. `nucleus__dna__mean`.

Our `var` index uses the raw brieflow feature names with single underscores: `nucleus_DAPI_mean`. **Not compliant with the schema's feature ID format.**

### var metadata

| Schema field | Status |
|---|---|
| `feature_name` (human-readable) | ❌ Missing — we have `feature_type` but no human-readable name |
| `feature_type` | ✅ Present |
| `compartment` | ✅ Present |
| `channel` | ✅ Present (not required by schema but aligns with feature definitions CSV) |

### obs index

Schema does not explicitly define the obs index for single-cell data. We currently use a plain integer index — should be a unique cell identifier string.

### uns

Schema does not define `uns` for single-cell data. Our `uns['pipeline']` is extra — not required, not prohibited.

---

## Lundberg Lab (Stanford) — Single-Cell AnnData

```
AnnData: 567970 cells × 3072 features
obs:  region_cell_id, region, centroid_y, centroid_x,
      pheno_00_y_pixel, pheno_00_x_pixel,
      n_rounds_mapped, mapped_to_all_rounds,
      cell_mask_id, nuc_mask_id,
      iss_mapped, iss_cell_id, iss_mapping_distance_mm,
      iss_barcode_1, iss_barcode_2, iss_barcode_3,
      iss_barcode_1_q_score, iss_barcode_2_q_score, iss_barcode_3_q_score,
      iss_n_barcodes
uns:  feature_extraction, iss_mapping
```

### Key differences from our format

| Aspect | Lundberg | Ours | Notes |
|---|---|---|---|
| Cell identifier | `region_cell_id` (unique string) | integer index | Their approach is cleaner — `region` is equivalent to plate+well, combined with a cell ID |
| Well representation | `region` (single field) | `well` + `row` (split) | Their single `region` field is simpler |
| Spatial coordinates | `centroid_x`, `centroid_y` in `obs` | `cell_i`, `cell_j` in `obsm['spatial']` | Both valid; putting in obs is more accessible, obsm is more scverse-idiomatic |
| Barcode per round | `iss_barcode_1/2/3` with `iss_barcode_1/2/3_q_score` | `cell_barcode_0/1` without per-round quality | They expose per-round barcodes and quality scores; we only expose the final assigned barcode |
| Barcode mapping quality | `iss_mapping_distance_mm`, `n_rounds_mapped`, `mapped_to_all_rounds` | `distance`, `fov_distance_0/1` | They have more interpretable quality fields with explicit naming |
| Modality prefix | `iss_*` prefix for all sequencing fields | no prefix — mixed with phenotype fields | Their prefix makes it immediately clear which modality each column comes from |
| `uns` structure | `feature_extraction`, `iss_mapping` (separate keys per modality) | `pipeline` (single key) | Their separation is cleaner — two modalities, two uns keys |
| `var` metadata | none | `compartment`, `channel`, `feature_type` | We have more structured feature metadata |
| `obsm` | none | `spatial` | We follow scverse conventions more closely |

---

## Summary: What Needs to Change for Schema Compliance

### High priority (required fields)

1. **`well_row` / `well_col`**: Split `well` ("A1") into `well_row` ("A") and `well_col` (1), or at minimum keep `row` (already present) and add `col`
2. **`cell_uid`**: Add a globally unique cell identifier — likely `{plate}_{well}_{tile}_{cell_0}` as a string
3. **`perturbation_id`**: Add a proper `perturbation_id` column that maps to the perturbation library (currently `cell_barcode_0` or `gene_symbol_0` are closest but neither is a stable perturbation ID)
4. **`var` index format**: Rename feature IDs from `nucleus_DAPI_mean` → `nucleus__DAPI__mean` (double underscores)
5. **`feature_name`**: Add human-readable feature names to `var`

### Medium priority (naming alignment)

6. **`cell_seq_id`**: Rename `cell_0` → `cell_seq_id`
7. **`barcode`**: Rename `cell_barcode_0` → `barcode`
8. **`cell_class`**: Rename `class` → `cell_class`
9. **`x` / `y`**: Move `cell_j` / `cell_i` from `obsm['spatial']` into `obs` as `x` and `y` (or keep both)

### Low priority (uns alignment with Lundberg)

10. **`uns` structure**: Split `uns['pipeline']` into separate keys by modality (e.g. `uns['feature_extraction']`, `uns['iss_mapping']`) to match Lundberg's approach
11. **`schema_version`**: Add `uns['schema_version'] = "0.1.0"` once we decide to formally comply

---

## Changes Made

Based on the comparison, the following "do now" changes were applied to `format_singlecell_anndata.py`:

### 1. `cell_uid` as obs index
Added a globally unique cell identifier as the obs index, formatted as `{plate}_{well}_{tile}_{cell_0}`. This is the primary schema-required change and enables cross-experiment cell linking.

### 2. Drop internal pipeline columns
Removed the following columns from `obs` as they have no meaning outside the brieflow pipeline:
- `batch_values` — internal batch correction label
- `channels_min` — pipeline-internal channel quality flag
- `site` — internal tile site index
- `i_0`, `j_0`, `i_1`, `j_1` — raw SBS centroid coordinates (not the phenotype centroids)
- `fov_distance_0`, `fov_distance_1` — distance to field-of-view edge

**Deferred (pending alignment with Matteo):**
- Field renaming (`class` → `cell_class`, `cell_barcode_0` → `barcode`, etc.)
- var index double-underscore format (`nucleus__DAPI__mean`)
- `feature_name` in var

---

### What we have that neither schema nor Lundberg has

- `cytoplasm_*` bounds and centroids (we segment cytoplasm explicitly)
- `batch_values` (pipeline-internal, probably not needed in the AnnData)
- `is_control` boolean (useful for downstream tools — worth keeping)
- `confidence` (classifier confidence — not in either format, but valuable)
- Structured `var` metadata with `compartment`, `channel`, `feature_type`
