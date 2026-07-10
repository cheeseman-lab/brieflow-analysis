# Pseudotile Merge Redesign — Plan to Wrap Up

**Date:** 2026-07-09
**Branch:** `merge-rotation-fix` (submodule + outer, unpushed)
**Supersedes the merge step of:** `docs/superpowers/plans/2026-07-07-image-based-stitch-merge.md`

---

## 1. Where we are (honest status)

**What works and is committed:**
- **Image-based stitching core** (`lib/shared/stitching/`): pairwise cross-correlation → spanning-tree placement → `place_cells` → optional chunked zarr mosaic + `reconcile_overlap_cells`. Fast, memory-bounded (no whole-well canvas), scales past legacy, **tight within-modality (~2–3 px)**. Fully unit-tested. This is the validated win.
- Coarse DAPI align, per-PH-tile hash merge, neg-det fallback, overlap reconcile — all committed/tested (~25 commits).
- Where matches are found, they are exact: strict 1:1, ~0.019 px.

**What fails:**
- **Full-well merge = 42.7%** (vs fast mode 83.8%; `FULLWELL_PARITY.md`). The per-tile hash converges for only ~25/308 tiles; the rest sit ~35%.
- **Root cause (verified):** the merge does a **single global coarse alignment** of the whole well. A single global (rotation+affine) transform cannot represent the well's **spatially-varying non-rigid distortion**, so footprint assignment is wrong for ~90% of tiles → the hash never sees the true partners. The 3×3 dev subset (72.8%) was misleading — its coarse was fit to that local region.
- This is **the same failure mode as the legacy stitch approach** ("a single alignment step based on the entire well").
- Merge is also **slow** (~3 h/well, sequential).

**Conclusion:** better stitching, but we reproduced the old merge failure. The fix is to remove the single global alignment entirely.

---

## 2. The design: pseudotile merge (correspondence by construction)

**Principle:** *stop doing any whole-well alignment.* Use the stitch + physical (stage) coordinates to establish **per-tile correspondence deterministically**, then let the hash do only local fine alignment.

**Pipeline:**
1. **Stitch** each modality into its own coherent global frame (DONE — image-based).
2. **Stage-frame registration (translation only):** align the two modalities' stage-coordinate frames with a single **robust translation** (~645 µm origin offset; rotation ~0.13° negligible). This is the *only* global step, and it's a translation — not the problematic global rotation/affine.
3. **Pseudotile cutting:** for each **SBS tile**, cut a **phenotype pseudotile covering the same physical (µm) footprint** (+ a margin to capture the ~1° rotational displacement, up to ~300 px peripheral). Cells come from the *stitched* phenotype frame, so a pseudotile cleanly spans the ~3–4 PH tiles under that footprint.
4. **Per-pair hash (fine alignment only):** hash each (SBS tile ↔ its pseudotile) pair with the existing machinery (`find_triangles` → `evaluate_match` → `merge_triangle_hash` + TPS). The pair already overlaps well by construction, so the hash resolves the local ~1° rotation + non-rigid distortion — the easy, robust regime.
5. **Dedup:** union all pairs → `deduplicate_cells` (strict 1:1) + intra-modality overlap reconcile.

**Why correspondence is "by construction":** once both modalities are stitched and the pseudotile is cut to the SBS footprint, it is already clear what matches what — no `find-optimal-site`, no `initial_sites`, no `det_range` gating, no `multistep_alignment` seeding. The operator sets nothing about correspondence. Tile-level pairing is free (physical position); the hash only does cell-level fine alignment.

**Why it fixes each failure:**
| Failure | Fix |
|---|---|
| 42.7% full-well (global align wrong everywhere) | No global affine — every pair is correct by physical position |
| Slow (~3 h) | ~300 small bounded hashes; no flooded footprints, no multistep discovery |
| Config burden (det_range, seeds, find-optimal-site) | Eliminated — correspondence is deterministic |
| "Too few cells" / "misaligned tile" pairing failures | Pseudotile is always cut to the populated SBS footprint |

**Expected outcome:** this is fast mode's proven per-tile logic run on tighter stitched positions with clean pseudotile cuts → should reach ~fast-mode parity (80%+) full-well and be fast. **The full-well run is the honest test — no predictions until the number is in.**

---

## 3. Implementation tasks

Reuse committed code; the net-new is pseudotile cutting + stage-frame translation. Do NOT modify `hash.py` / `fast_merge.py` / `deduplicate_merge.py` / the stitching core.

### Task A — stage-frame translation registration
- New `lib/merge/pseudotile_merge.py::register_stage_frames(sbs_meta, ph_meta) -> dict{translation, (rotation≈I)}`.
- From the two `combine_metadata` tables' `x_pos`/`y_pos`: estimate a single robust translation (median offset) mapping the PH stage frame onto the SBS stage frame in µm. Optionally a tiny global rotation; default translation-only.
- TDD: synthetic two frames offset by a known translation → recover it.

### Task B — pseudotile cutting
- `pseudotile_merge.py::cut_pseudotile(ph_cells_um, sbs_tile_footprint_um, margin_um) -> ph_pseudotile_cells`.
- Work in a common physical (µm) frame: convert each modality's stitched global cell positions to µm (global px × pixel size). Apply the stage translation to PH. For an SBS tile's physical footprint (its stage position ± tile physical extent), gather PH cells within footprint+margin.
- TDD: synthetic cells; assert the pseudotile contains the footprint cells (+margin) and excludes far cells.

### Task C — pseudotile merge
- `pseudotile_merge.py::merge_pseudotiles(sbs_cells, ph_cells, sbs_meta, ph_meta, sbs_offsets, ph_offsets, sbs_um_per_px, ph_um_per_px, margin_um=..., threshold=4, local_refinement="thin_plate_spline", align_subsample_ratio=..., evaluate_kwargs=...) -> merged_1to1`.
- Register stage frames (Task A). For each SBS tile: cut its pseudotile (Task B); hash the pair (rescale to a common local px scale; `find_triangles`/`evaluate_match`; skip det<0; `merge_triangle_hash` + TPS); tag with SBS tile. Subsample the pseudotile for the *alignment* step if its density ≫ SBS (reuse the existing `align_ratio` idea). Concatenate → `deduplicate_cells` (approach="fast", distance priors) → 1:1.
- TDD: synthetic where SBS tiles map to physically-corresponding pseudotiles under a per-tile-varying rotation + a global translation; assert >70% match + strict 1:1, and that it does NOT depend on any global rotation estimate.

### Task D — full-well validation (harness, no commit)
- `merge_troubleshooting/harness/pseudotile_fullwell.py`: reuse `full_well_parity.py` scaffold (stitch offsets are checkpointed at `fullwell_{sbs,ph}_offsets.parquet` — reuse them, skip re-stitching). Run `merge_pseudotiles` on PROVIDED full-well centroids.
- Report to `PSEUDOTILE_FULLWELL.md`: overall/interior/edge recall, per-tile distribution, median dist, 1:1, **wall-time**, peak RSS. Compare vs fast mode 83.8% and the 42.7% baseline.

### Task E — wire it (only if D passes) — the wrap-up
- Replace/augment the `image_stitch` merge script to call `merge_pseudotiles`.
- Task 10 snakemake wiring per `WIRING_DRAFT.md`: additive `merge.approach: image_stitch`, gated, feeding the shared tail (`format_merge → deduplicate_merge → final_merge`). New per-well rules `image_stitch_sbs`/`image_stitch_phenotype`/`image_stitch_merge` + `summarize`. `ancient()` on upstream inputs. mem_recommendations entries.
- Notebook (`analysis/5_merge.py`) param exposure: `approach: image_stitch`, `pseudotile_margin_um`, `fuse_mosaic`, `stitch_overlap_fraction`.

---

## 4. Success criteria (the gate for wrapping up)

- **Recall:** full-well SBS recall ≥ ~fast-mode parity (target ≥ 80%), and NOT the 42.7% collapse — recall must be spatially uniform (interior ≈ edge, no radial degradation).
- **Speed:** merge wall-time ≪ 3 h/well (target tens of minutes; the pairs are small and independent → parallelizable if needed).
- **Memory:** bounded (no whole-well canvas).
- **Correctness:** strict 1:1, overlap-reconciled unique cells, sub-px median.
- **Config:** no per-screen correspondence tuning required.

If the gate passes → **Task E (wire) → done.**

---

## 5. Contingency

If the pseudotile merge does **not** reach ~fast-mode parity full-well: fall back to **scoping the stitch as an image/QC + whole-well-positions producer** (the validated win — scalable, memory-lean mosaic) and **let fast mode keep doing the cross-modal merge**. Wire the stitch as a producer, not a merge replacement. This banks the real value without over-claiming the merge.

---

## 6. Risks / open items

- **Stitch drift at full-well scale:** the 1012-PH spanning-tree placement could accumulate error far from the anchor → pseudotiles off. Check the intra-modality duplicate-placement disagreement on the *full* well (we measured ~2–3 px on the dev block only).
- **Pseudotile margin sizing:** must cover the peripheral rotational displacement (~300 px) without over-flooding density. Fixed geometric parameter; validate a couple of values.
- **Density in pseudotiles:** phenotype ~1.8× denser → subsample for the *alignment* step (keep full set for matching), reusing the `align_ratio` knob.
- **`fuse_mosaic` blends overlaps but the merge uses centroids** — confirm the mask-overlap (not centroid) reconciliation if output cell-precision matters; recall-neutral either way.
