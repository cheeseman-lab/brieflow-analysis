# Plan: Raw single-cell h5ad with Stanford-style obs columns

## Context

The brieflow pipeline currently ships a single-cell `*.h5ad` whose feature matrix is **per-batch z-scored on controls** (via `centerscale_on_controls` in `generate_feature_table.py`). Two problems:

1. Downstream consumers expect raw measurements; the z-score is a pipeline-internal alignment step that doesn't belong in the canonical single-cell artifact.
2. The current `obs` is missing several mapping/QC columns that Stanford/Lundberg-style AnnData carries (per `anndata_format_comparison.md`). Brieflow already produces equivalents — they just aren't surfaced under recognizable names. The one genuine gap is **global pixel coordinates** (Stanford's `centroid_x/y`).

Fix scope: only `format_singlecell_anndata` and its rule wiring. The construct/bootstrap pipeline keeps its normalized feed; the final exported parquet (`cell_data.parquet` from `prep_cellxstate.sh`) is unaffected — extras live only in the h5ad.

---

## Brieflow obs columns available in filtered parquet (ground truth)

From `brieflow_output_well/aggregate/parquets/P-1_W-A1_CeCl-all_ChCo-*__filtered.parquet`:

```
plate, well, tile, site, cell_0, cell_1,
i_0, j_0, i_1, j_1,
distance, fov_distance_0, fov_distance_1,
cell_barcode_0, cell_barcode_1, gene_symbol_0, gene_symbol_1, mapped_single_gene,
channels_min,
nucleus_i, nucleus_j, nucleus_bounds_0..3,
cell_i, cell_j, cell_bounds_0..3,
cytoplasm_i, cytoplasm_j, cytoplasm_bounds_0..3
```

Config-dependent (only present with SBS recomb-detection enabled): `Q_min_0/1`, `Q_recomb_0/1`, `no_recomb_0/1`, `gene_id_0/1`.

## Stanford ↔ brieflow mapping

| Stanford | Brieflow | Status |
|---|---|---|
| `region_cell_id` | `cell_uid` (set as obs.index) | ✓ have |
| `region` | derive: `plate + "_" + well` | ✓ derivable |
| `centroid_x`, `centroid_y` (global pixel) | tile-local only today | ✗ **gap — need to derive global coords** |
| `pheno_00_y/x_pixel` | `nucleus_i/j`, `cell_i/j` | △ have one centroid, not per-round |
| `cell_mask_id` | `cell_0` | ✓ have (different name) |
| `nuc_mask_id` | — | ✗ missing (brieflow derives nucleus from cell mask) |
| `iss_cell_id` | `cell_1` | ✓ have (different name) |
| `iss_mapping_distance_mm` | `distance` (units: pixels) | ✓ have (different name + units) |
| `iss_mapped` | `mapped_single_gene` | △ different semantics (uniquely-mapped vs mapped-at-all) |
| `iss_n_barcodes` | derive: `cell_barcode_0.notna() + cell_barcode_1.notna()` | ✓ derivable |
| `iss_barcode_1/2/3` | `cell_barcode_0/1` | △ top-K ranked vs per-cycle |
| `iss_barcode_*_q_score` | `Q_min_0/1` (config-dependent) | △ min-Q per barcode, not per-cycle |
| `n_rounds_mapped`, `mapped_to_all_rounds` | — | ✗ would need SBS pipeline refactor |

**Brieflow-only columns Stanford lacks** (we keep all of them): `cytoplasm_*`, `*_bounds_*`, `gene_symbol_0/1`, `mapped_single_gene`, `fov_distance_0/1`.

---

## Step 1: Plumb stage metadata through the merge pipeline (the hard part)

**Problem**: `combined_metadata.parquet` (with `x_pos`, `y_pos`, `pixel_size_x/y` per tile) lives at `preprocess/metadata/phenotype/{plate}/{row}/{col}/`. The merge step uses it for stitching alignment but **does not propagate it into the merged-cells parquet** that flows downstream into filter/generate_feature_table/format_singlecell_anndata. To compute global pixel positions on every cell, those columns need to be **carried through** the pipeline so they end up as columns in `filtered.parquet`.

**Where to inject the join**: in the merge step that produces the per-cell merged parquet (the one whose output flows into aggregate's filter rule). Concretely:

- `brieflow/workflow/lib/merge/merge.py` (function that builds the final merged DataFrame, currently selecting `cols_final = ["plate","well","tile","cell_0","i_0","j_0","site","cell_1","i_1","j_1","distance"]`)
- `brieflow/workflow/lib/merge/fast_merge.py` (analogous fast-path implementation, needs the same change)
- `brieflow/workflow/rules/merge.smk` rules `fast_merge` / equivalent: add `combined_metadata.parquet` (phenotype side) as an input (and SBS side if SBS-frame globals are also wanted later — for now phenotype is sufficient since `cell_i/cell_j` and `i_0/j_0` are phenotype centroids)

Implementation sketch in the merge function: after producing the merged frame, left-join the phenotype `combined_metadata` on `(plate, well, tile)` to attach four columns:

- `x_pos_phenotype` — tile-center stage position, μm
- `y_pos_phenotype` — tile-center stage position, μm
- `pixel_size_x` — μm/pixel
- `pixel_size_y` — μm/pixel

Add these to `cols_final`. Update the schema/contract for `merge_cells.parquet` accordingly.

**Why hard**: changes the merge output schema; any downstream code that asserts the column set, or does PyArrow schema unification across batches, needs to handle the new columns. Filter rule (`aggregate/parquets/...filtered.parquet`) needs to pass them through unchanged. Generate-feature-table needs to treat them as metadata, not features (i.e., included in `metadata_cols`).

**Why necessary**: side-loading combined_metadata only at h5ad time means every consumer needs to redo the join. Plumbing it through means the canonical cell-data parquet is self-contained.

## Step 2: Switch h5ad input from normalized to raw parquets

**File**: `brieflow/workflow/rules/aggregate.smk` (rule `format_singlecell_anndata`)

Currently the rule wires `snakemake.input.singlecell_paths` to the `__features_singlecell.parquet` produced by `generate_feature_table` (output[0], normalized). Replace `singlecell_paths` input with the **filtered parquets** that `generate_feature_table` already consumes (one per `plate × well × cell_class × channel_combo`) — same cells, no `centerscale_on_controls` transform applied. After Step 1, those filtered parquets already carry `x_pos_phenotype`, `y_pos_phenotype`, `pixel_size_x/y`.

Keep the output filename unchanged (`aggregate/anndata/{channel_combo}__singlecell.h5ad`).

Add `params: tile_h, tile_w` (the phenotype tile pixel dimensions; read from config or hardcode 2048 for the brieflow-test data).

**Blast radius**: only the h5ad changes. Construct medians, gene medians, bootstrap, and align all keep reading the existing normalized parquet.

## Step 3: Read raw parquets in the script + drop normalization stamp

**File**: `brieflow/workflow/scripts/aggregate/format_singlecell_anndata.py`

- Update `snakemake.input` reference to match the new wiring (loop over `filtered_paths`).
- Stage-position columns (`x_pos_phenotype`, `y_pos_phenotype`, `pixel_size_x`, `pixel_size_y`) arrive as obs columns directly from Step 1's plumbing — no extra read/join needed here.
- Replace `"normalization": "zscore"` with `"normalization": "raw"` in `adata.uns["pipeline"]`.
- Keep all existing logic for: cell_uid index, `is_control`, `obsm['spatial']`, `var` parsing.

## Step 4: Compute global pixel positions

Now that stage metadata is plumbed through (Step 1), compute global pixel coordinates per cell. This is the only genuine gap vs Stanford-style AnnDatas.

### 4a. Convention

- `x_pos_phenotype, y_pos_phenotype` = phenotype tile **center** stage position in μm (per tile, joined in via Step 1).
- `pixel_size_x, pixel_size_y` = μm/pixel.
- `cell_i, cell_j` = phenotype cell mask centroid in **tile-local** pixels (row, col).
- `tile_h, tile_w` = phenotype tile pixel dimensions (params).

### 4b. Anchoring origin per well

Define the well origin (top-left, in μm) as the minimum tile-corner across all tiles in that `(plate, well)`:

```
x_origin_um[plate, well] = min_over_tiles(x_pos_phenotype - tile_w/2 * pixel_size_x)
y_origin_um[plate, well] = min_over_tiles(y_pos_phenotype - tile_h/2 * pixel_size_y)
```

Compute once per `(plate, well)` group inside `format_singlecell_anndata.py`.

### 4c. Per-cell global pixel coords

```python
# tile-corner in μm
tile_corner_x_um = obs["x_pos_phenotype"] - tile_w / 2 * obs["pixel_size_x"]
tile_corner_y_um = obs["y_pos_phenotype"] - tile_h / 2 * obs["pixel_size_y"]

# global cell position in μm
cell_x_um = tile_corner_x_um + obs["cell_j"] * obs["pixel_size_x"]
cell_y_um = tile_corner_y_um + obs["cell_i"] * obs["pixel_size_y"]

# convert to global pixels relative to per-well origin
obs["global_x"] = ((cell_x_um - obs["x_origin_um"]) / obs["pixel_size_x"]).round().astype("int32")
obs["global_y"] = ((cell_y_um - obs["y_origin_um"]) / obs["pixel_size_y"]).round().astype("int32")
```

Drop `x_pos_phenotype`, `y_pos_phenotype`, `pixel_size_x`, `pixel_size_y`, `x_origin_um`, `y_origin_um` from final `obs` — they were temporary.

### 4d. Cheap derivations

Same block, before `cell_uid`:

- `mapped_n_barcodes = cell_barcode_0.notna().astype(int) + cell_barcode_1.notna().astype(int)` — count of ranked barcodes called for the cell. Guard each source column.
- `region = plate.astype(str) + "_" + well.astype(str)` — combined plate+well key, useful for grouping across wells.

### 4e. Caveats (document in `anndata_format_comparison.md`)

- **Stage convention assumption**: `x_pos`/`y_pos` is the tile **center** in μm. If a microscope reports the tile origin (top-left corner) instead, our globals are offset by half a tile in each direction — still valid for visualization and within-well ordering, but absolute pixel coords would need a different offset.
- **Per-well origin**: globals are relative to the min stage position **within that (plate, well)**. Cells from different wells are not directly comparable in `global_x/y` — use `region` to group.
- **Phenotype frame only**: globals are computed from the phenotype tile coordinate system. SBS-cycle centroids (`i_sbs`, `j_sbs`) remain tile-local; globalizing the SBS frame would need an analogous join with SBS-side `combined_metadata`.

## Step 5: Stop dropping the centroid/QC columns

**File**: `brieflow/workflow/scripts/aggregate/format_singlecell_anndata.py`

The `PIPELINE_INTERNAL_COLS` set currently strips: `batch_values`, `channels_min`, `site`, `i_0`, `j_0`, `i_1`, `j_1`, `fov_distance_0`, `fov_distance_1`. Of these:

- **Keep**: `i_0`, `j_0`, `i_1`, `j_1` (raw SBS centroids in **tile-local** pixel coords), `fov_distance_0`, `fov_distance_1` (edge-effect filtering).
- **Continue dropping**: `batch_values` (only exists post-`prepare_alignment_data`, won't be in raw parquets anyway), `channels_min`, `site`.

Effective change: shrink `PIPELINE_INTERNAL_COLS` to `{"batch_values", "channels_min", "site"}`.

## Step 6: Rename merge-suffix columns from `_0/_1` to `_phenotype/_sbs`

**File**: `brieflow/workflow/scripts/aggregate/format_singlecell_anndata.py`

The `_0` / `_1` suffix is opaque. Inside the merge pipeline it consistently means **`_0` = phenotype dataset, `_1` = SBS dataset** (`merge.py:111`). Rename those columns in the h5ad's `obs` for clarity:

| Current | New | Meaning |
|---|---|---|
| `cell_0` | `cell_phenotype` | Phenotype cell-mask label (skimage `regionprops` `label`) |
| `cell_1` | `cell_sbs` | SBS cell-mask label |
| `i_0` | `i_phenotype` | Phenotype cell centroid — row, tile-local pixels (post-merge copy) |
| `j_0` | `j_phenotype` | Phenotype cell centroid — col, tile-local pixels |
| `i_1` | `i_sbs` | SBS cell centroid — row, tile-local pixels |
| `j_1` | `j_sbs` | SBS cell centroid — col, tile-local pixels |
| `fov_distance_0` | `fov_distance_phenotype` | Distance to phenotype FOV edge |
| `fov_distance_1` | `fov_distance_sbs` | Distance to SBS FOV edge |

**Do NOT rename** these — their `_0/_1` means "top-ranked barcode #0 / #1", not phenotype/SBS:
- `cell_barcode_0`, `cell_barcode_1`
- `gene_symbol_0`, `gene_symbol_1`
- `gene_id_0`, `gene_id_1` (when present)
- `Q_min_0`, `Q_min_1` (when present)
- `Q_recomb_0`, `Q_recomb_1` (when present)
- `no_recomb_0`, `no_recomb_1` (when present)

These stay as-is because the suffix is a rank within the SBS pipeline, not a dataset identifier.

**Implications**:
- `cell_uid` formula changes: `{plate}_{well}_{tile}_{cell_phenotype}` (was `{cell_0}`).
- `format_singlecell_anndata.py` should perform the rename on `obs` immediately after building it from the filtered parquet, before the `cell_uid` block, so all downstream code in the script sees the new names.

**Note on `cell_i, cell_j`** (compartment centroids from feature extraction): these stay as-is. They are conceptually the same as `i_phenotype, j_phenotype` (both are the phenotype cell mask centroid in tile-local pixels) but come from different code paths (`cp_emulator.py:908` vs `merge.py:111`). Keep both for now to preserve the existing data shape; we can dedupe later if confirmed identical.

---

## Verification

```bash
cd brieflow/tests/small_test_analysis
rm -rf brieflow_output_zarr
snakemake --cores 4 --snakefile ../../workflow/Snakefile \
          --configfile config/config_omezarr.yml \
          --until all_aggregate
```

Then inspect the resulting h5ad:

```python
import anndata as ad
a = ad.read_h5ad("brieflow_output_zarr/aggregate/anndata/ChCo-DAPI_COXIV_CENPA_WGA__singlecell.h5ad")
assert a.uns["pipeline"]["normalization"] == "raw"
# brieflow names retained
assert {"cell_barcode_0", "cell_barcode_1", "distance",
        "cell_phenotype", "cell_sbs", "mapped_single_gene"} <= set(a.obs.columns)
# old _0/_1 names should be gone
assert not ({"cell_0", "cell_1", "i_0", "j_0", "i_1", "j_1",
             "fov_distance_0", "fov_distance_1"} & set(a.obs.columns))
# new derived columns
assert {"mapped_n_barcodes", "region", "global_x", "global_y"} <= set(a.obs.columns)
# restored + renamed centroid/QC cols
assert {"i_phenotype", "j_phenotype", "i_sbs", "j_sbs",
        "fov_distance_phenotype", "fov_distance_sbs"} <= set(a.obs.columns)
# Sanity: global pixel coords span more than a single tile (well > tile_w)
assert int(a.obs["global_x"].max() - a.obs["global_x"].min()) > 2048
# global pixel coords are non-negative integers (origin at well top-left)
assert (a.obs["global_x"] >= 0).all() and (a.obs["global_y"] >= 0).all()
# Sanity-check that X is not z-scored: feature means should be far from 0 / std far from 1
print("X[:, 0] mean/std:", a.X[:, 0].mean(), a.X[:, 0].std())
```

A z-scored matrix has per-column mean ≈ 0 / std ≈ 1; raw intensity features should have means in the hundreds-to-thousands and varied stds.

Confirm `prep_cellxstate.sh --test` still produces a passing submission (the `cell_data.parquet` step reads this h5ad — it will get extra columns, which the OPS schema is permissive about; no schema-required column changes).

---

## Critical files

- `brieflow/workflow/lib/merge/merge.py`, `fast_merge.py` (Step 1 — add stage-position join, extend `cols_final`)
- `brieflow/workflow/rules/merge.smk` (Step 1 — add `combined_metadata.parquet` as rule input where merged-cells parquet is produced)
- `brieflow/workflow/lib/aggregate/cell_data_utils.py` / `metadata_cols` config (Step 1 — make sure `x_pos_phenotype`, `y_pos_phenotype`, `pixel_size_x/y` are treated as metadata, not features, by the filter / generate_feature_table consumers)
- `brieflow/workflow/rules/aggregate.smk` (Step 2 — `format_singlecell_anndata` input rewires from `singlecell_paths` → `filtered_paths`)
- `brieflow/workflow/scripts/aggregate/format_singlecell_anndata.py` (Steps 3–6 — raw read, global pixel derivation, mapped_n_barcodes/region, shrink PIPELINE_INTERNAL_COLS, `_0/_1` → `_phenotype/_sbs` renames, `uns["pipeline"]["normalization"] = "raw"`)
- `anndata_format_comparison.md` (document conventions, caveats, and the new column set)
- No test data changes
