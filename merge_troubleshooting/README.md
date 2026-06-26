# Merge troubleshooting — Vaishnavi Phadnis (Blainey lab) multi-scope screen

Branch: `merge-rotation-fix` (outer off `origin/speed`; submodule off `6f1a1dc`).
Data: `/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting/`
(4 files: `P-1_W-A1__{sbs,phenotype}_info.parquet` + `preprocess_metadata_{sbs,phenotype}/P-1_W-A1__combined_metadata.parquet`).
Repro driver: `scratchpad/run_merge_notebook.py` → QC figs in `scratchpad/merge_qc/`.

This is a **working diagnosis doc**, not a fix yet. Goal: (1) confirm we can run the
merge notebook on her data, (2) catalog every issue, (3) decide what's config vs code,
(4) line up fixes. Stitch debugging is deferred to the end.

---

## TL;DR

- **Root cause is real and physical:** two differently-configured Ti-2 scopes (SBS vs
  phenotype) → a consistent **~1° rotation** + **non-rigid distortion** between modalities,
  plus a large magnification/pixel-size difference. Confirmed across the Blainey lab; only
  bites **small, dense** cells (her neutrophils; Owen's neurons). PDAC/U2OS were fine.
- **Fast mode handles the rotation fine** (per-tile-pair affine absorbs the global ~1°).
  The residual that remains is **non-rigid distortion within each tile**, worst at tile
  edges — this is what caps merge rate and makes it vary tile-to-tile.
- **Her config has the wrong/incomplete merge settings**, and the published default
  `det_range` is off by ~16× for her optics. With the correct `det_range` the notebook
  runs end-to-end and all test pairs pass gating.
- **Most of her "weird plots" are red herrings** (coordinate-origin / rendering), per the
  Blainey lab — confirmed here.

---

## Empirical findings on her data (well A1, 1012 PH tiles / 308 SBS tiles)

Fast-mode `evaluate_match` / `initial_alignment` over 11 overlapping tile-pairs spread
across the well:

| quantity | value | meaning |
|---|---|---|
| determinant | **0.0717–0.0726** (rock-steady) | = `1/(M×B)²`, M×B = pheno_px/sbs_px = 3.72. Matches optics. |
| rotation angle | **+1.0° to +1.2°**, consistent, no reflection | genuine inter-scope rotation |
| per-pair score | 0.30–0.64 (all > `score=0.1`) | every pair passes gating with correct det_range |
| per-tile match rate | **best 86%, median 82%, worst 36% of PH cells** | the real problem: high variance, edge-driven |

Pixel sizes (from her metadata): **SBS 1.208548 µm/px, phenotype 0.325 µm/px**. One PH
tile (3200 px × 0.325 = 1040 µm) is *smaller* than one SBS tile (1480 px × 1.2085 = 1788 µm),
so a PH tile covers only ~34 % of an SBS tile's footprint — match rate must be measured
against **PH** cells, not SBS.

**Why ~1° is "big":** well diagonal ≈ 43 mm ≈ 35,800 SBS px. A 1° rotation = up to
~310 px displacement at the well periphery vs a **2 px** match threshold. This is fatal for
any *global* single-transform method (stitch), but fast mode re-fits per tile so it's
absorbed locally.

**Distortion is non-rigid:** in the best per-pair tile (86 %), unmatched PH cells cluster
at the tile **edges**, not randomly — a pure rigid/affine residual would be uniform. So a single affine per tile leaves an edge-growing residual;
this is what a sub-tile or non-rigid correction must remove.

---

## Honest region-level ceiling (why raw match rate is misleading)

Per-pair "% of PH/SBS matched" understates performance and hides the real limiter.
`scripts/region_ceiling.py` pools PH cells from **all** PH tiles overlapping a target SBS
tile (one SBS tile @1788 µm overlaps ~4 PH tiles @1040 µm), maps them in, and buckets SBS
cells by nearest-PH distance. Arrows = without → with `local_refinement`:

| SBS tile | matched <2px | misaligned 2–10px (alignment) | no partner >10px (segmentation) | vs achievable ceiling |
|---|---|---|---|---|
| 280 (per-pair "worst") | 67.4 → 79.0 % | 21.6 → 10.0 % | 11.0 % | 75.7 → **88.8 %** |
| 140 (median)           | 72.5 → 78.2 % | 10.7 →  5.0 % | 16.9 % | 87.2 → **94.0 %** |
| 168 (per-pair "best")  | 67.6 → 70.5 % |  7.3 →  4.3 % | 25.2 % | 90.3 → **94.2 %** |

Takeaways:
1. **The per-pair "worst tile 36 %" was mostly a geometry artifact** — pairing one SBS tile
   with only its single closest PH tile orphans the cells whose partner is in a neighbouring
   PH tile. Pooling overlapping PH tiles takes tile 280 to **67 %**; the real well-level
   pipeline already does this via multiple (tile,site) pairs + dedup.
2. **Segmentation/coverage is the dominant ceiling and is tile-dependent:** 11–25 % of SBS
   cells have **no PH cell within 10 px at all**. Tile 168 (best per-pair, 86 %) has the worst
   coverage (25 %). No registration can fix this — it's cells segmented in one modality but
   not the other (small ~10 µm neutrophils, two scopes, different SNR/focus).
3. **The no-partner bucket is genuinely segmentation, not misalignment:** refinement moves
   cells from *misaligned* → *matched* but leaves *no-partner* unchanged (280: 11.0→11.0 %;
   168: 25.2→25.2 %). If those were misaligned, refinement would have rescued them.

**Conclusion:** against the achievable ceiling (cells that have a partner), alignment is in
good shape — **76–90 % baseline → 89–94 % with `local_refinement`** (refinement ~halves the
alignment residual). The biggest remaining lever for her *overall* merge rate is **segmentation
consistency between the two modalities** (per-modality cellpose tuning), which is separate from
merge. (Caveat: the >10 px "no-partner" bucket assumes the per-pair transforms are roughly
right in that region; verified robust here since it's stable with vs without refinement.)

### Does raising `threshold` (2→3→4 px) help? (`scripts/threshold_sweep.py`)

Yes, and safely — it's the last easy alignment win. Cells are **~10–12 px apart**, so a 3–4 px
window is well under half the spacing (false-match danger starts ~5–6 px). With refinement on:

| tile | thr=2 | thr=3 | thr=4 | thr=5 | new-match quality | achievable ceiling |
|---|---|---|---|---|---|---|
| 280 | 79.0 % | 83.6 % | 85.7 % | 86.9 % | ~100 % mutual-NN | 89.0 % |
| 140 | 78.2 % | 81.4 % | 82.4 % | 82.7 % | ~100 % mutual-NN | 83.1 % |
| 168 | 70.5 % | 73.6 % | 74.3 % | 74.5 % | ~100 % mutual-NN | 74.8 % |

The matches added by a looser threshold are **~100 % mutual nearest-neighbours** (SBS and PH each
pick each other) — real partners just beyond 2 px from residual distortion, not wrong-neighbour
grabs. Ambiguity (2nd PH within threshold) barely rises (12→14 %). It's a **free config change**
(`merge.threshold: 3` or `4`), no code, stacks with refinement.

**At threshold≈4 + refinement we hit the ceiling** (gaps to achievable: 280 = 3.3 pp,
140 = 0.7 pp, 168 = 0.5 pp). Alignment is essentially **saturated** — beyond this the limiter is
segmentation/coverage (the no-partner bucket), not registration. So: bump threshold to 3–4 for
the last few points, then the remaining yield is a per-modality segmentation problem.

### Cutoff-free ceiling: unmatched cells INSIDE the confirmed-overlap region (`scripts/ceiling_bbox.py`)

The "no-partner within 10 px" ceiling above uses an arbitrary cutoff. A cleaner test: the
**convex hull of the matched cells** is the region where PH demonstrably overlaps SBS; an
unmatched SBS cell *inside* that hull is a genuine miss (no cutoff needed for the headline).
Threshold = 4, refinement on:

| SBS tile | SBS in overlap region | matched | unmatched | of unmatched: seg-gap (no PH) | PH present (align/dedup) |
|---|---|---|---|---|---|
| 280 | 2,860 | **94.9 %** | 5.1 % | 17 % | 83 % |
| 140 | 4,877 | **90.0 %** | 10.0 % | 89 % | 11 % |
| 168 | 4,228 | **97.1 %** | 2.9 % | 76 % | 24 % |

- **Within genuine overlap the merge captures 90–97 % of SBS cells** — the earlier 74–89 %
  "achievable ceiling" was pessimistic because it counted SBS cells sitting *outside* the
  PH-covered area (the SBS acquisition covers more ground than the overlapping PH tiles). Those
  are "outside overlap," not merge misses.
- The few in-region misses split by tile: tile 140 is mostly true segmentation gaps (89 %),
  tile 280 is mostly PH-present-but-unmatched (83 %, a sliver of alignment/dedup headroom).
- Use the **convex hull, not the bbox** (tile 140: bbox 17.5 % unmatched vs hull 10.0 % — the
  overlap is non-rectangular so the bbox includes empty corners). An alpha-shape would be tighter.

**Levers, in order:** (1) ensure *all* overlapping PH tiles are paired so the overlap region is
as large as possible (well-level pipeline does this via multi-pair + dedup); (2) per-modality
segmentation consistency (the seg-gap bucket); (3) a sliver of alignment/dedup headroom on some
tiles. This hull decomposition (matched / seg-gap / align-miss per tile) is the right operator
QC to add to the notebook.

### Before/after the augmentation × threshold (2×2) — `scripts/before_after.py`

Pooled-region %SBS matched (denominator = ALL SBS cells in the tile, including any outside
PH coverage). Figures `figures/ba_sbs{280,140}_thr2.png` show the spatial before/after at the
tight threshold, where the augmentation's lift is largest (recovered cells in orange):

| SBS tile | thr=2 off→on | thr=4 off→on |
|---|---|---|
| 280 | 67.4 → **79.0 %** (+11.6) | 82.8 → 85.7 % (+2.9) |
| 140 | 72.5 → 78.2 % (+5.7) | 82.1 → 82.4 % (+0.3) |
| 168 | 67.6 → 70.5 % (+2.9) | 74.2 → 74.3 % (+0.1) |

> **Note on tile labels:** earlier sections tag these tiles per-pair *worst/median/best*
> (from %PH on a single PH tile: 168 = 86 % "best", 280 = 36 % "worst"). That ranking
> **inverts** under pooled %SBS — tile 168 is *lowest* here (74 %) because it has the worst
> PH **coverage** (25 % of its area has no PH cell at all), even though its in-overlap matching
> is the *highest* (97 % — see hull table). A single worst/median/best label can't rank a tile
> across metrics; below we use bare tile IDs. The numbers are consistent (168: 74.3 % of all
> SBS = 97.1 % of in-overlap SBS = 4105 cells); only the per-pair labels were misleading.

**Key finding: threshold and `local_refinement` are partial substitutes.** Both capture the
2–10 px near-misses, so at thr=4 the loose window already grabs them and refinement adds little
(+0.1–2.9 pp); the augmentation's big lift is when the threshold is kept **tight** (thr=2:
+2.9–11.6 pp). In the images, thr=2 recovers a band of edge cells (the distortion residual);
thr=4 recovers few, and the cells still red at thr=4 are a **coverage gap** (no PH there at all),
not an alignment miss.

**Practical implication:** for *her* data (cell spacing ~11 px), simply setting `threshold: 4`
is safe (matches ~100 % mutual-NN) and gets most of the yield without refinement. The
augmentation's distinct value is **keeping a tight threshold for precision** — which matters more
for *denser* screens (spacing < ~8 px) where thr=4 would start grabbing wrong neighbours but
refinement+thr=2 would not. Best yield is thr=4 + refinement, and refinement is opt-in + cheap,
so enabling both is reasonable; on her data the marginal gain over thr=4-alone is small.

---

## Issue catalog

### A. Config issues (her `config.yml`)

1. **`approach: stitch` is wrong for her** — dense cells, and stitch failed anyway (see D).
   Should be **`approach: fast`**.
2. **Fast-mode keys are missing entirely**: no `det_range`, no `initial_sbs_tiles` /
   `initial_sites`. Fast mode cannot run without them.
3. **`det_range` direction/magnitude is the #1 gotcha (her point 3).** The fitted transform
   maps PH→SBS, so its determinant = `(pheno_px/sbs_px)² = 1/(M×B)²`. For her optics
   (20× vs 10× + 0.7× relay + binning, net M×B = 3.72) the determinant ≈ **0.0723**, so
   `det_range ≈ [0.065, 0.080]`. The brieflow default `(1.125, 1.186)` rejects **everything**
   (~16× off). Owen already worked this out manually; the recalculated dets land in range.

### B. Notebook issues (`analysis/5_merge.py`, speed branch)

4. **Path-layout mismatch (blocks loading her data).** The notebook reads **nested HCS**
   paths (`preprocess/metadata/{ph,sbs}/<plate>/<row>/<col>/combined_metadata.parquet`,
   `{ph,sbs}/parquets/.../*_info.parquet`). Her run produced **flat** `P-1_W-A1__*` files.
   Version skew — her data won't load in this notebook without relayout or a path shim.
5. **`DET_RANGE = None` crashes the validation cell** (`d0, d1 = DET_RANGE`) before any
   guidance is shown. The notebook should **auto-suggest** `det_range` from the pixel-size
   ratio (we have both pixel sizes in metadata) instead of leaving it None and crashing.
6. **No quantitative per-tile merge-rate readout.** `fast_merge_example` shows plots but
   the operator has to eyeball "best vs worst." A printed match-rate per pair (we computed
   86/82/36 %) would make the distortion problem legible immediately.

### B′. Is a location-based (stage-coordinate) alignment between the scopes needed?

**Yes, but only a coarse translation — not a rotation/flip.** Two *separate* alignments
exist and must not be conflated:

- **Global / location (stage coords, µm).** Fitting `phenotype_xy → sbs_xy` over tile centers
  gives `R ≈ identity` (det +1.003, scale 1.0015, rotation **+0.13°**) with **translation
  (+645, +26) µm**. So between the two scopes there is **no flip, no 90° rotation, no scale
  difference** — only a ~645 µm origin offset.
- **Local / per-tile-pair (cell coords, px).** Triangle-hash + affine per pair; this is what
  absorbs the ~1° *image* rotation and does the fine registration.

**Does the global step need to run?** It's largely **self-correcting**: `multistep_alignment`'s
`prioritize()` fits its own RANSAC on tile centers and learns the 645 µm offset. The one place
it bites is **seeding** — `find_closest_tiles` by raw nearest-neighbor mis-pairs border tiles:
**7/40** SBS tiles have their nearest PH tile >520 µm away (a PH half-width), risking a wrong
tile. This is exactly her **point 1**. Fix = enable `METADATA_ALIGN` (center-align, all flips
False) so seeds are robust. Note in `fast_alignment.py` `align_metadata` is **only called when
a flip/rotate is requested**, so with all-False the center-align is skipped — but `prioritize`
covers it. **This global alignment does NOT touch within-tile distortion** (the worst-tile 36 %
problem); that still needs the local fix.

### C. Confirmed red herrings (don't chase)

7. **Combined tile-grid "misalignment"** (her point 1) = coordinate-origin offset between
   scopes (measured center offset ≈ (300, −829) µm) + rendering. Cosmetic; the Blainey lab
   is right. `02_tile_grid_centeraligned.png` shows it lines up after centering.
8. **Large PH↔SBS tile distances** (her point 2; 127 vs 26 in Aconcagua) = different stage
   coordinate origins between the two scopes, absorbed by the per-pair translation. Not the
   problem.
9. **`METADATA_ALIGN` / flips / `rotate_90`** are **not** needed — the offset is ~1°, not a
   90°/flip; setting any flip would be wrong.

### D. Stitch issues (deferred — debug last)

10. **4D-tiff crash:** `assemble_aligned_tiff_well` fails on a `(11, 5, 1480, 1480)`
    `(cycles, channels, H, W)` aligned SBS stack → `Unexpected image dimensions`. Her run
    never produced the `sbs/images` labels dir.
11. **Switching to stitch re-ran the entire SBS ruleset** (Snakemake re-trigger / `ancient()`
    issue) — wasteful and confusing.
12. **Stitch is slow** (`stitched_image: true` assembles full-well images), and is the wrong
    tool for dense cells regardless.

---

## Is her config right? (quick verdict)

| key | her value | verdict |
|---|---|---|
| `approach` | `stitch` | ✗ → `fast` |
| `det_range` | *(absent)* | ✗ add `[0.065, 0.080]` |
| `initial_sbs_tiles` / `initial_sites` | *(absent)* | ✗ add (≥5 tiles spread across well) |
| `score` | `0.1` | ✓ |
| `threshold` | `2` | ✓ (2 px) |
| `sbs_metadata_cycle` | `1` | ✓ |
| `alignment_flip_x/y`, `alignment_rotate_90` | `false` | ✓ (do not flip) |
| `sbs_pixel_size` / `phenotype_pixel_size` | `1.208548` / `0.325` | ✓ |
| `stitched_image` | `true` | n/a once on fast; this is what makes stitch slow |
| `sbs_dedup_prior` / `pheno_dedup_prior` | set | ✓ (fine defaults) |

**Minimal config change to get her running (fast mode):**
```yaml
merge:
  approach: fast
  det_range: [0.065, 0.080]      # = 1/(M*B)^2 ± 10%, M*B = pheno_px/sbs_px = 3.72
  initial_sbs_tiles: [0, 28, 56, 84, 112, 140, 168, 196, 224, 252, 280]
  score: 0.1
  threshold: 2
  sbs_metadata_cycle: 1
  metadata_align: true           # center-align the two scopes' coord frames (translation)
  alignment_flip_x: false
  alignment_flip_y: false
  alignment_rotate_90: false
  local_refinement: polynomial   # correct residual within-tile distortion (two-scope)
  # (keep dedup priors)
```
This alone gets a working merge at ~82–86 % per good tile — but the worst tiles still sit
at ~36 % because of the non-rigid residual. That's the fix below.

---

## Proposed fixes (ranked; for sign-off before coding)

1. **Notebook rigidity / `metadata_align` (DONE — backward compatible).**
   - **`metadata_align` is now first-class:** persisted to `config['merge']['metadata_align']`
     (notebook) and honored by the fast pipeline — `fast_alignment.py` center-aligns the two
     scopes' stage frames when `metadata_align` is set, even with no flip/rotate. Default
     `False` → existing single-scope configs unchanged. Verified on her data: center-alignment
     drops the at-risk seed pairs (nearest PH tile >520 µm) from **7/40 → 3/40** (median
     419→350 µm), so initial-site selection picks the right overlapping tiles (her point 1).
   - **DET_RANGE no longer crashes on `None`** — the validation cell prints a starting point
     from the pixel-size ratio (`det = 1/(M×B)²`) as *guidance only*; it does **not** auto-set
     the value (operator confirms against the plot, per request).
   - The alignment cell prints the applied center offset so the operator can verify overlap.
   - *Known follow-up (not her case — flips all False):* `align_metadata` gets SBS as df1 in the
     notebook but phenotype as df1 in `fast_alignment.py`; symmetric for pure centering, but a
     requested flip/rotate would hit different modalities in preview vs run. Fix if flips needed.
   - *Deferred:* flat-vs-nested path shim (issue B4); per-tile match-rate print in
     `fast_merge_example`.

   Files touched: `brieflow/workflow/rules/merge.smk`, `.../scripts/merge/fast_alignment.py`,
   `analysis/5_merge.py`.

2. **The real fix — local distortion correction (DONE — `local_refinement`, opt-in).**
   Implemented as an optional **iterative degree-2 polynomial warp** applied at merge time,
   on cell centroids, on top of the existing per-tile affine. The fast-alignment contract is
   untouched (rotation/translation parquet unchanged); refinement lives entirely in
   `merge_sbs_phenotype`. Gated by `config['merge']['local_refinement']` (default off →
   byte-identical merges; verified 1133==1133 on tile 19).
   - **Why polynomial (vs piecewise/sub-tile):** smooth (no region-boundary artifacts),
     degrades gracefully to affine when correspondences are sparse → works on *all* screens,
     not just dense ones. Prototype showed piecewise 3×3 only ~1 pp better on dense tiles but
     fragile on sparse regions.
   - **Robustness:** the warp is fit ONLY on cells already matched within `threshold`
     (high-confidence), iterated twice — cannot be pulled by spurious loose matches.
   - **Result on her data (via the actual wired lib):** overall **65.5 % → 71.5 %** of PH
     matched; **worst tile 35.8 % → 58.2 %**; best/clean tiles unchanged (≤+0.1 pp). The lift
     lands where it's needed (the distorted tiles).
   - Files: `lib/merge/fast_merge.py` (`refine_local_warp` + wiring), `scripts/merge/fast_merge.py`,
     `rules/merge.smk`, `analysis/5_merge.py` (`LOCAL_REFINEMENT` param + persist).

   *Heavier alternative not pursued* (kept for reference): Luezhen's FFT non-rigid +
   morphology/topology matching on label images — more correct for severe non-rigid warp but
   needs stitched masks and new deps. The centroid polynomial gets most of the benefit with
   zero new inputs.

3. **Stitch debugging (last):** fix the 4D `(cycle, channel, H, W)` handling in
   `assemble_aligned_tiff_well`, the full-SBS re-trigger, and the slowness — even though
   stitch is not her recommended path.

---

## Open questions for Vaishnavi / Blainey lab

- Exact optics per scope (objective, relay, binning) to lock the expected `det_range` and to
  know whether the distortion is pure rotation+scale or includes higher-order terms.
- Can she share the aligned SBS/phenotype **label images** for one well? Needed to prototype
  the FFT non-rigid route (route 2b) and to debug stitch (D).
