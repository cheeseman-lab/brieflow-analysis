# Initial sites report — fast-mode seeds (Vaishnavi well A1)

**What these are:** the anchor (tile, site) pairs that seed `multistep_alignment`. They are
selected *after* `metadata_align` (center), validated by triangle hash, and must satisfy
`det_range=[0.065, 0.08]` and `score > 0.1`. They bootstrap a global model that then
propagates to every overlapping tile-pair in the well; they are not the merge scope.

**Selection rule:** best-match PH per SBS tile (nearest after centering), nested cleanly in
one SBS frame (small `nearest_um`, large `margin_um` to the 2nd-nearest PH so it does not
straddle two tiles), validated by det/score, then spread across the well by farthest-point
sampling, with a score floor (>=0.55) so no weak seeds.

## The 6 chosen initial sites

`initial_sbs_tiles: [8, 61, 112, 122, 209, 294]`

| sbs_tile | ph_tile | determinant | rotation_deg | scale | translation_px | score | nearest_um | margin_um | in_det_range | pass_score |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 45 | 0.0723 | 1.225 | 0.2688 | 924.2 | 0.627 | 96.0 | 768.5 | True | True |
| 61 | 253 | 0.0724 | 1.158 | 0.269 | 923.1 | 0.581 | 144.5 | 650.8 | True | True |
| 112 | 359 | 0.0722 | 1.153 | 0.2687 | 861.5 | 0.627 | 95.8 | 768.8 | True | True |
| 122 | 418 | 0.0724 | 1.172 | 0.2691 | 941.4 | 0.604 | 110.2 | 730.8 | True | True |
| 209 | 676 | 0.0724 | 1.201 | 0.2691 | 955.3 | 0.657 | 130.2 | 703.0 | True | True |
| 294 | 957 | 0.0721 | 1.163 | 0.2684 | 782.8 | 0.56 | 95.8 | 769.1 | True | True |

- **determinant** = (scale)^2 = (sbs_px/pheno_px)^-2; ~0.072 across all seeds = consistent optics.
- **rotation_deg** = inter-scope image rotation recovered per seed (the two-scope tilt).
- **translation_px** = offset of the per-pair affine (PH→SBS pixel frame).
- **nearest_um / margin_um** = PH nesting and unambiguity (next PH tile is >600 um away).

## Validated candidate pool (39 tiles passing det+score)

The 6 above were drawn from this pool (full data in `initial_sites.csv` /
`_anchor_run/anchor_pool.csv`). Top by score:

| sbs_tile | ph_tile | nearest | margin | determinant | score |
|---|---|---|---|---|---|
| 209.0 | 676.0 | 130.2 | 703.0 | 0.0724 | 0.657 |
| 253.0 | 823.0 | 144.9 | 649.4 | 0.0721 | 0.635 |
| 126.0 | 411.0 | 169.4 | 602.3 | 0.0724 | 0.635 |
| 252.0 | 821.0 | 127.4 | 689.5 | 0.0723 | 0.633 |
| 125.0 | 413.0 | 110.2 | 730.4 | 0.0722 | 0.632 |
| 132.0 | 401.0 | 142.7 | 661.9 | 0.072 | 0.63 |
| 205.0 | 669.0 | 169.3 | 602.1 | 0.0723 | 0.629 |
| 186.0 | 591.0 | 169.6 | 602.1 | 0.0721 | 0.628 |
| 112.0 | 359.0 | 95.8 | 768.8 | 0.0722 | 0.627 |
| 8.0 | 45.0 | 96.0 | 768.5 | 0.0723 | 0.627 |
| 259.0 | 833.0 | 167.4 | 614.8 | 0.0725 | 0.627 |
| 185.0 | 593.0 | 109.9 | 730.9 | 0.0723 | 0.623 |
| 12.0 | 52.0 | 142.3 | 662.7 | 0.0723 | 0.623 |
| 189.0 | 586.0 | 17.6 | 901.8 | 0.0722 | 0.619 |
| 256.0 | 828.0 | 18.1 | 901.5 | 0.0723 | 0.614 |
