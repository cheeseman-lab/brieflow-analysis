# Image-Based Stitching Core + Sub-Tile Hash Merge — Design

**Date:** 2026-07-07
**Branch:** `merge-rotation-fix`
**Status:** Design — approved for planning
**Related memory:** `project_vaishnavi_multiscope_merge`

## Problem

Brieflow's current `merge_approach: "stitch"` path is slow and memory-hungry, and
fails on the two-scope Vaishnavi data:

- **Memory:** assembles a monolithic in-memory `.npy` well canvas; full-well
  `regionprops` for cell extraction.
- **Speed:** sequential per-well tile assembly; no within-well parallelism.
- **Correctness:** global `stitch_alignment` (RANSAC on bbox ranges) is
  rotation-fragile (identity fallback on failure), and a single global affine
  cannot absorb the consistent ~1° cross-scope rotation + non-rigid distortion
  that displaces peripheral cells by 100s of px. Also crashes on 4D
  `(cycles, channels, H, W)` aligned SBS stacks.

Fast mode already solves the *matching* problem for this data (~92–97% SBS match
via TPS warp + find-optimal-site + local refinement, committed at submodule
`fdbf31e`). This work targets **stitching**: a holistic, image-based, memory-lean
engine that (a) fixes the stitch-mode failures and (b) is reusable beyond merge.

The competitor Genentech/scallops demonstrates the target techniques (chunked
zarr fusion, masked cross-correlation registration, spanning-tree global
placement, radial correction, chunked relabeling). We build a **clean-room,
zarr3-native** implementation using those *published, generic* techniques — no
scallops code, no scallops dependency (it pins `zarr<3`, incompatible with
brieflow-speed's zarr3 stack).

## Goals

1. A **shared image-based stitching core** — assemble each modality's tiles into
   one coherent whole-well frame from image content alone, zarr3/dask-native,
   with bounded peak memory.
2. A **merge application** that uses the core to beat the two-scope
   rotation/distortion problem, reusing the proven fast-mode hash + TPS machinery.
3. Backward compatible: added alongside `fast` and legacy `stitch`; default paths
   byte-identical.

Non-goals for this deliverable (deferred): the preprocess-stage cross-cycle
stitch + retile application (Application 2); any aggregate/cluster changes;
replacing fast mode.

## Architecture

### Shared core: `lib/shared/stitching/` (new module, brieflow submodule)

Image-based, stage-coords-as-optional-prior-only, zarr3 + dask.

- **`register.py` — pairwise + global tile placement.**
  - Pairwise overlap registration from image content: masked/zero-normalized
    cross-correlation (ZNCC) on the DAPI channel over the tile-overlap strips,
    subpixel via upsampled cross-correlation. Optional stage-coord prior seeds
    the search window; it is never trusted as truth.
  - Statistical edge rejection: model the null ZNCC distribution, drop
    low-confidence tile-pair edges.
  - Global placement: build the tile-adjacency graph, solve a globally
    consistent set of per-tile **translation** offsets via spanning-tree
    propagation / least-squares. (Within a modality, one scope ⇒ translation
    only ⇒ well-posed.) Handles disconnected components by falling back to the
    stage-coord prior for unlinked tiles.
  - Output: `DataFrame[tile → (y_off, x_off)]` in a single per-modality well
    frame, plus per-edge QC (ncc, residual).

- **`fuse.py` — lazy chunked fusion (optional).**
  - Fuse tiles at their global offsets into a **chunked OME-Zarr v3** intensity
    mosaic via dask, linear blending in overlaps, bounded memory (no monolithic
    array). Produced only when requested (see config `fuse_mosaic`).

- **`place_cells.py` — global cell coordinates.**
  - Apply per-tile global offsets to each tile's existing cell centroids →
    per-modality global cell-position table. Reuses upstream per-tile
    segmentation; **no full-well `regionprops`**.

- **`io.py` — zarr3 helpers.** Read tiles lazily (iohub/zarr3), write OME-Zarr v3
  mosaic + offsets/QC parquet.

The core exposes a thin API (`stitch_well(tiles, metadata, channel, ...) ->
{offsets, cell_positions, mosaic?}`) callable by any pipeline stage.

### Merge application (`merge_approach: "image_stitch"`)

1. **Stitch SBS** tiles → SBS global frame + global SBS cell positions.
2. **Stitch phenotype** tiles → phenotype global frame + global phenotype cell
   positions.
3. **Coarse common scale:** rescale phenotype positions to SBS pixel size using
   the pixel-size ratio (image-based coarse rotation/translation handled per
   sub-tile in step 5, not globally).
4. **Re-tile into larger-than-FOV sub-tiles:** partition the well frame into a
   grid of sub-tiles sized `subtile_size` (config; default 2–4× the original
   FOV). Re-bucket the existing global centroids into sub-tiles — **no
   re-segmentation**.
5. **Hash-stitch per sub-tile:** run the existing triangle-hash + affine (+ TPS
   residual) cross-modality matching within each sub-tile. The per-sub-tile
   local affine absorbs the ~1° rotation + non-rigid distortion (piecewise
   affine over the well); larger sub-tiles give more cells ⇒ robust hashing and
   no small-FOV edge effects.
6. **Stitch/dedup** sub-tile matches → well-level merged cells (reuse existing
   dedup).

Reuses: `lib/merge/hash.py`, `lib/merge/fast_merge.py` (affine + TPS warp),
existing dedup. New code is confined to the stitching core + the retile/bucket
glue.

### Snakemake wiring (`rules/merge.smk`)

New rules gated on `merge.approach == "image_stitch"`:
- `image_stitch_sbs`, `image_stitch_phenotype` → offsets (+ optional mosaic) +
  global positions, per well.
- `retile_hash_merge` → sub-tile hash matches → merged cells + QC.
- `summarize_image_stitch` → plate-level QC.

Follows the existing per-well parallelism. Legacy `stitch` and `fast` rules
untouched.

## Configuration (all `config.get`, gated, defaults preserve current behavior)

Under `merge:`
- `approach`: `fast` | `stitch` | `image_stitch` (new). Default unchanged.
- `subtile_size`: int or [h, w] px for the retile grid. Validated default.
- `fuse_mosaic`: bool (default false) — write the OME-Zarr mosaic deliverable.
- `stitch_channel`: channel used for registration (default DAPI/nuclei).
- `stitch_overlap_fraction`: expected tile overlap for the search window.
- Reuses existing hash/TPS keys (`local_refinement`, `warp_smoothing`,
  `threshold`, `det_range`, …) at the sub-tile level.

## Data contracts

- **In:** per-tile images (zarr3/tiff), tile metadata (well, tile, stage x/y,
  pixel size), per-tile segmentation + centroids (existing).
- **Out:** per-modality offsets parquet, per-modality global cell positions
  parquet, optional OME-Zarr v3 mosaic + label mosaic, merged-cells parquet,
  QC (per-edge ncc, per-sub-tile match rate).

## Error handling

- Registration confidence below threshold on a tile-pair → edge dropped;
  disconnected tiles placed by stage-coord prior, flagged in QC.
- Sub-tile with too few cells to hash → fall back to neighbor-borrowed centroids
  or the well-global affine; flagged.
- Missing pixel-size metadata → error early (no silent fallback that corrupts
  scale).

## Testing & validation

- **Unit:** synthetic tile grids with known translation/rotation → recover
  offsets within subpixel; retile/bucket correctness; zarr3 round-trip.
- **Correctness:** Vaishnavi well A1 — actual tile **images** already local at
  `/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting/stitch_troubleshooting.zip`
  (166 GB, 1323 files): `sbs_images/P-1_W-A1_T-*__aligned.tiff` (~230 MB, 4D
  cycles×channels×H×W — the stack the legacy stitcher crashed on) and
  `phenotype_images/P-1_W-A1_T-*__aligned.tiff` (~98 MB). Prerequisite is just
  extraction (mind ~166 GB free space; can extract a tile subset first). Metric =
  the locked box-metrics contract (`sbs_box_match`, `ph_match`, `overlap_frac`,
  `median_dist`) from `merge_troubleshooting/harness/box_metrics.py`. Target:
  match or beat fast-mode headline (~92% sbs_box, sub-px median).
- **Memory/speed:** bounded peak RSS (chunked, no full-well array) and wall-time
  ≤ current stitch on the same well. Record peak RSS + wall-time explicitly.
- **Backward-compat:** `fast` and legacy `stitch` outputs byte-identical to
  pre-change.

## Open items to confirm in planning

1. ~~Vaishnavi A1 raw tile images~~ — RESOLVED: already local in
   `stitch_troubleshooting.zip` (see Testing & validation). Decide extraction
   scope (full 166 GB vs tile subset) and target scratch/data dir in planning.
2. Exact subtile_size default (tie to FOV px + cell density on this screen).
3. Whether the label mosaic (chunked relabel) is needed now or only with
   `fuse_mosaic` + re-segmentation (deferred).
