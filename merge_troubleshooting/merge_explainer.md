# How the two-scope merge works — cumulative explainer

_Auto-generated from the research sweep; do not edit by hand._

## 1. The problem

SBS and phenotype are imaged on different microscopes → a consistent ~1° rotation, a large magnification/pixel-size difference, and residual non-rigid within-tile distortion. The fast merge must recover a per-tile-pair transform robust to all three.

## 2. The pipeline funnel

Delaunay triangulate cell centroids per tile → **nine-edge hash** (scale/rotation-invariant) → match triangles across modalities by hash → **RANSAC affine** per (phenotype tile, SBS site) (`evaluate_match`) → **multistep_alignment** propagates from seed anchors to the whole well → **nearest-neighbour cell merge** within `threshold` (`merge_sbs_phenotype`) → optional **degree-2 polynomial warp** for residual distortion (`refine_local_warp`) → **dedup** to 1:1.

## 3. Datasets

| dataset | optics | SBS tiles | score: baseline (thr4, no refine) | score: winner |
|---|---|---|---|---|
| vaishnavi | 20x pheno / 10x 2x2-bin SBS | 308 | 0.804 | 0.8744 |
| pdac | 20x pheno / 10x 2x2-bin SBS | 333 | 0.902 | 0.9219 |
| owen_40x | 40x confocal pheno / 10x SBS | 16 | 0.929 | 0.9295 |
| owen_20x | 20x pheno / 10x SBS Blainey scopes | 333 | 0.738 | 0.7595 |


## 4. The 2px objective (segmentation-fair, bidirectional)

Within the phenotype bounding box, the fraction of SBS cells matched to a phenotype cell within **2px** — and vice versa — counting a cell as a miss **only when a partner exists** (judged by a fixed reference alignment), so missing segmentation never counts as a merge error. A k×k worst-subcell term rewards spatial uniformity (no dead corners).

## 5. Levers

| lever | location | default | controls |
|---|---|---|---|
| det_range | hash.py multistep_alignment | dataset-derived | scale gate = (ph_px/sbs_px)^2; per-dataset |
| score | hash.py / merge.smk | 0.1 | min fraction of triangle centers matched to accept a pair |
| threshold_triangle | hash.py:evaluate_match | 0.3 | max hash distance to call two triangles a match |
| threshold_point | hash.py:evaluate_match | 2 | px radius for scoring a matched triangle center |
| threshold_region | hash.py:evaluate_match | 50 | px region considered when scoring |
| ransac_residual_threshold | hash.py:evaluate_match RANSAC | sklearn default | RANSAC inlier tolerance for the affine fit |
| threshold | fast_merge.py:merge_sbs_phenotype | 2 | px match radius for cell-to-cell NN merge |
| local_refinement | fast_merge.py | None | enable degree-2 polynomial within-tile warp |
| warp_degree | fast_merge.py:refine_local_warp | 2 | polynomial degree of the local warp |
| warp_iterations | fast_merge.py:refine_local_warp | 2 | refine-and-rematch passes |
| warp_min_correspondences | fast_merge.py:refine_local_warp | 30 | min confident matches to fit the warp |


### Sensitivity (mean / max spread in dataset score across the lever's swept values)

| lever | mean spread | max spread |
|---|---|---|
| threshold | 0.0024 | 0.0066 |
| local_refinement | 0.043 | 0.0824 |
| threshold_triangle | 0.0223 | 0.0498 |
| ransac_residual_threshold | 0.0148 | 0.0534 |
| warp_degree | 0.0459 | 0.0881 |


## 6. Generalized winner

`local_refinement=polynomial|ransac_random_state=0|threshold=4|threshold_triangle=0.3|warp_degree=3|warp_iterations=2`  (worst-case ratio 0.9995)

| dataset | score | dataset optimum | generalization tax |
|---|---|---|---|
| owen_20x | 0.7595 | 0.7599 | 0.0004 |
| owen_40x | 0.9295 | 0.9295 | 0.0 |
| pdac | 0.9219 | 0.922 | 0.0001 |
| vaishnavi | 0.8744 | 0.8748 | 0.0005 |


## 7. Full-well merge with the winner

| dataset | aligned pairs | SBS rate % | PH rate % | median px | <2px % |
|---|---|---|---|---|---|
| vaishnavi | 2347 | 83.83 | 64.5 | 0.66 | 93.31 |
| pdac | 2272 | 82.41 | 73.69 | 0.2 | 99.31 |
| owen_40x | 183 | 31.81 | 88.96 | 0.317 | 97.88 |
| owen_20x | 2360 | 70.35 | 59.48 | 0.531 | 89.79 |


## 8. Remaining levers to push

- **Morphology (`area`) prior** in dedup tie-breaks (convert px²→µm² across pixel sizes).

- **Sub-tile / piecewise hashing** for datasets where one affine per tile leaves edge residual.

- **owen_40x coverage**: alignment is near-perfect where it lands (≈0.96) but only a subset of tiles align (sparse 40× confocal neurons) — the lever there is segmentation/anchoring, not merge.

## 9. Validation scope & caveats

| dataset | anchor + multistep derivation | per-pair alignment levers | merge + metric |
|---|---|---|---|
| vaishnavi | ✓ | ✓ | ✓ |
| pdac | ✓ | ✓ | ✓ |
| owen_40x | ✓ | ✓ | ✓ |
| owen_20x | ✓ | ✓ | ✓ |


- Datasets marked *rides existing align* are too sparse to re-derive seeds per tile (owen_40x: ~47 cells/tile), so they reuse the production `fast_alignment` and only the merge/per-pair-lever half is exercised there.

- **owen_40x metric (~0.96) is on its highest-confidence pairs** (favorable subset); the fair whole-well figure is its full-well rate (PH-side, since 40× neurons are sparse).

- **One well per dataset**; held-out eval sets are modest (15–25 contained pairs). Generalization is shown across datasets, not yet across wells within a dataset.

- **Dedup uses distance-only priors** (flat info parquets lack the gene/fov feature columns the production tie-breakers use) — affects same-distance ties, not matched counts.

- The sweep selects levers **per-pair**; the full-well merge applies them via **multistep** propagation (small train/apply difference).
