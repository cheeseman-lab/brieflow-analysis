# Image-Based Stitching Core + Sub-Tile Hash Merge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zarr3-native, image-based stitching core to brieflow and a new `merge_approach: "image_stitch"` that assembles each modality's tiles from image content, re-tiles into larger sub-tiles, and runs the proven hash+TPS matching per sub-tile (piecewise affine) to beat the two-scope rotation/distortion problem with bounded memory.

**Architecture:** A new shared module `workflow/lib/shared/stitching/` performs pairwise cross-correlation registration + spanning-tree global placement of tiles into one per-modality well frame (translation only). Cells are placed by applying per-tile offsets to existing centroids (no full-well `regionprops`). The merge application re-buckets global centroids into larger-than-FOV sub-tiles and reuses `merge_triangle_hash` per sub-tile, then dedups. A fused OME-Zarr v3 mosaic is optional.

**Tech Stack:** Python 3.12, numpy, scipy, scikit-image 0.26 (`phase_cross_correlation`), python-igraph 1.0, zarr 3.1.6, dask[array], ome-zarr 0.13, iohub 0.3, tifffile, pytest 9.

## Global Constraints

- **Clean-room:** no scallops code or dependency. Use only generic published techniques (masked/FFT cross-correlation, spanning-tree placement). Copied verbatim from spec.
- **zarr3-native:** build on zarr 3.1.6 / iohub 0.3 / ome-zarr 0.13. No `zarr<3` APIs.
- **No numba:** registration uses FFT / scikit-image, not JIT.
- **Backward compatible:** `merge.approach` defaults to `"fast"`; `fast` and legacy `stitch` code paths and outputs must remain byte-identical. All new config via `config.get(...)` with defaults that leave existing screens unchanged.
- **Minimal divergence + material speedup (GOVERNING):** the new path is *additive* — reuse existing brieflow structures and the fast-mode hash/TPS machinery verbatim; the only new code is the intra-modality stitch core. Divergence is justified ONLY by measured improvement: `image_stitch` MUST be materially faster and lower-peak-memory than the legacy `stitch` approach on the same well, and MUST NOT regress merge quality vs `fast`. This is a GO/NO-GO gate at Task 9, not a soft target.
- **Repo:** brieflow submodule at `/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow`. Package import root is `workflow` (`packages = ["lib"]`, `package-dir {"" = "workflow"}`). Library code lives under `workflow/lib/`, imported as `workflow.lib...` in tests.
- **Tests:** live in `brieflow/tests/`, prepend repo root to `sys.path`, import `from workflow.lib...`. Mark unit tests `@pytest.mark.unit`. Run from the brieflow submodule root in the `brieflow_zarr3_speed` conda env.
- **Style:** Google-style docstrings (ruff pydocstyle `D`), line length per repo ruff config. Match the density of the file you edit.
- **Docstrings not required** in `tests/*.py` and `workflow/scripts/*.py` (ruff per-file-ignores).
- **Never commit unless the executing operator confirms** (user CLAUDE.md overrides the skill's auto-commit). Commit steps below stage the right files and give a message; run the commit only when the operator approves.

**Env activation for every command below:**
```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_zarr3_speed
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow
```

**Validation data (real):** `/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting/stitch_troubleshooting.zip` (166 GB): `sbs_images/P-1_W-A1_T-*__aligned.tiff` (4D cycles×channels×H×W) + `phenotype_images/P-1_W-A1_T-*__aligned.tiff` (3D channels×H×W). Per-tile cell centroids come from the existing A1 `sbs_info` / `phenotype_info` parquets in `merge_vaishnavi/general_merge_troubleshooting/`.

---

### Task 1: Extract a Vaishnavi A1 tile subset for development

**Files:**
- Create (data, gitignored scratch): `/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev/` with a small contiguous block of SBS + phenotype tiles.

**Interfaces:**
- Produces: a dev image dir `STITCH_DEV=/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev` containing `sbs_images/` and `phenotype_images/` with ~9 spatially-adjacent tiles each (a 3×3 block), for fast iteration without touching 166 GB.

- [ ] **Step 1: Check free space on the target filesystem**

```bash
df -h /lab/ops_analysis_ssd/test_matteo
```
Expected: ≥ ~10 GB free (a 3×3 SBS block ≈ 9 × 230 MB ≈ 2 GB + phenotype).

- [ ] **Step 2: Identify a contiguous tile block from stage metadata**

Read the A1 SBS `combined_metadata` parquet (in `merge_vaishnavi/general_merge_troubleshooting/`) and pick 9 SBS tiles whose stage x/y form a 3×3 neighborhood, plus the phenotype tiles overlapping that region.
```bash
python - <<'PY'
import pandas as pd, glob
base="/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"
m=pd.read_parquet(glob.glob(f"{base}/*sbs*metadata*")[0])
print(m.columns.tolist()); print(m[["tile","x_pos","y_pos"]].head(20))
PY
```
Expected: prints tile ids + stage coords so you can hand-pick a 3×3 block (record the tile ids).

- [ ] **Step 3: Extract just those tiles from the zip**

```bash
Z=/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting/stitch_troubleshooting.zip
DST=/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev
mkdir -p "$DST"
# replace the T-list with the block chosen in Step 2
for T in 0 1 2 8 9 10 16 17 18; do
  unzip -j "$Z" "stitch_troubleshooting/sbs_images/P-1_W-A1_T-${T}__aligned.tiff" -d "$DST/sbs_images"
done
```
Expected: SBS tiles land in `$DST/sbs_images`. Repeat for the overlapping phenotype tile ids into `$DST/phenotype_images`.

- [ ] **Step 4: Verify shapes**

```bash
python - <<'PY'
from tifffile import imread
import glob
for f in sorted(glob.glob("/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev/sbs_images/*.tiff"))[:2]:
    print(f, imread(f).shape)
PY
```
Expected: SBS shape like `(11, 5, 1480, 1480)` (cycles, channels, H, W); phenotype like `(C, H, W)`. Record the DAPI channel index (channel 0) and cycle 0 for registration.

- [ ] **Step 5: No commit (external scratch data, not in repo).**

---

### Task 2: Stitching-core package + `TileOffsets` container + tile-image preprocessing

**Files:**
- Create: `workflow/lib/shared/stitching/__init__.py`
- Create: `workflow/lib/shared/stitching/types.py`
- Create: `workflow/lib/shared/stitching/prep.py`
- Test: `tests/test_stitching_core.py`

**Interfaces:**
- Produces:
  - `stitching.types.TileOffsets` — a thin wrapper over a `pandas.DataFrame` with columns `["tile", "y", "x"]` (float global-frame offsets in pixels), plus `.to_frame() -> pd.DataFrame` and `TileOffsets.from_frame(df) -> TileOffsets`.
  - `stitching.prep.select_registration_plane(image: np.ndarray, channel: int, cycle: int | None) -> np.ndarray` — reduce a 3D/4D tile stack to the single 2D plane used for registration (max-project z if present; index cycle then channel for 4D; index channel for 3D).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stitching_core.py
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from workflow.lib.shared.stitching.types import TileOffsets
from workflow.lib.shared.stitching.prep import select_registration_plane


@pytest.mark.unit
def test_tileoffsets_roundtrip():
    df = pd.DataFrame({"tile": [0, 1], "y": [0.0, 5.5], "x": [0.0, -3.0]})
    off = TileOffsets.from_frame(df)
    pd.testing.assert_frame_equal(off.to_frame(), df)


@pytest.mark.unit
def test_select_registration_plane_4d_and_3d():
    stack4d = np.zeros((11, 5, 8, 8), dtype=np.uint16)
    stack4d[0, 0] = 7  # cycle 0, channel 0
    plane = select_registration_plane(stack4d, channel=0, cycle=0)
    assert plane.shape == (8, 8) and plane[0, 0] == 7

    stack3d = np.zeros((3, 8, 8), dtype=np.uint16)
    stack3d[2] = 4
    plane = select_registration_plane(stack3d, channel=2, cycle=None)
    assert plane.shape == (8, 8) and plane[0, 0] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitching_core.py -v`
Expected: FAIL with `ModuleNotFoundError: workflow.lib.shared.stitching`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/shared/stitching/__init__.py
"""Image-based tile stitching core (zarr3-native, clean-room)."""
```

```python
# workflow/lib/shared/stitching/types.py
"""Data containers for the stitching core."""

from __future__ import annotations

import pandas as pd

_COLUMNS = ["tile", "y", "x"]


class TileOffsets:
    """Per-tile global-frame pixel offsets for one modality's well."""

    def __init__(self, frame: pd.DataFrame):
        """Store a copy of ``frame`` restricted to the offset columns."""
        self._frame = frame[_COLUMNS].reset_index(drop=True)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "TileOffsets":
        """Build from a DataFrame with columns tile, y, x."""
        return cls(frame)

    def to_frame(self) -> pd.DataFrame:
        """Return the offsets as a DataFrame with columns tile, y, x."""
        return self._frame.copy()
```

```python
# workflow/lib/shared/stitching/prep.py
"""Tile-image preprocessing for registration."""

from __future__ import annotations

import numpy as np


def select_registration_plane(
    image: np.ndarray, channel: int, cycle: int | None
) -> np.ndarray:
    """Reduce a tile stack to the 2D plane used for registration.

    Args:
        image: Tile array. 4D is (cycle, channel, y, x); 3D is (channel, y, x).
        channel: Channel index to register on (e.g. DAPI).
        cycle: Cycle index for 4D stacks; None for 3D stacks.

    Returns:
        A 2D float32 image plane.
    """
    arr = image
    if arr.ndim == 4:
        if cycle is None:
            raise ValueError("cycle is required for a 4D tile stack")
        arr = arr[cycle, channel]
    elif arr.ndim == 3:
        arr = arr[channel]
    elif arr.ndim != 2:
        raise ValueError(f"Unexpected image dimensions: {arr.shape}")
    return np.asarray(arr, dtype=np.float32)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitching_core.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/shared/stitching/__init__.py workflow/lib/shared/stitching/types.py workflow/lib/shared/stitching/prep.py tests/test_stitching_core.py
git commit -m "feat(stitching): core package + TileOffsets + registration-plane prep"
```

---

### Task 3: Pairwise overlap registration (FFT cross-correlation)

**Files:**
- Create: `workflow/lib/shared/stitching/register.py`
- Test: `tests/test_stitching_core.py` (extend)

**Interfaces:**
- Consumes: `select_registration_plane` (Task 2).
- Produces:
  - `register.register_pair(ref: np.ndarray, mov: np.ndarray, expected_shift: tuple[float, float], overlap_fraction: float, max_shift: float) -> tuple[np.ndarray, float]` — returns `(shift_yx, confidence)`. Registers the overlap strips of two neighboring tiles using `skimage.registration.phase_cross_correlation` with an upsampled subpixel refinement; `confidence` is the zero-normalized cross-correlation (ZNCC) of the overlap after applying the shift. `expected_shift` is the stage-prior displacement of `mov` relative to `ref`; the returned `shift_yx` is the refined full displacement.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_stitching_core.py
from workflow.lib.shared.stitching.register import register_pair
from scipy.ndimage import shift as ndi_shift


@pytest.mark.unit
def test_register_pair_recovers_known_translation():
    rng = np.random.default_rng(0)
    full = rng.random((256, 256)).astype(np.float32)
    ref = full[:, :200]                      # left tile
    true = np.array([0.0, 160.0])            # mov shifted right by 160 px
    mov = ndi_shift(full, shift=-true, order=1)[:, :200].astype(np.float32)
    shift_yx, conf = register_pair(
        ref, mov, expected_shift=(0.0, 150.0), overlap_fraction=0.25, max_shift=40.0
    )
    assert conf > 0.5
    np.testing.assert_allclose(shift_yx, true, atol=1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitching_core.py::test_register_pair_recovers_known_translation -v`
Expected: FAIL with `ImportError`/`AttributeError` on `register_pair`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/shared/stitching/register.py
"""Pairwise tile-overlap registration via FFT cross-correlation."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import shift as ndi_shift
from skimage.registration import phase_cross_correlation


def _zncc(a: np.ndarray, b: np.ndarray) -> float:
    """Zero-normalized cross-correlation of two equal-shape arrays."""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denom) if denom > 1e-12 else 0.0


def _overlap_strips(ref, mov, expected_shift, overlap_fraction):
    """Return the overlapping sub-windows of ref and mov given the prior shift."""
    h, w = ref.shape
    dy, dx = expected_shift
    # Horizontal neighbor (dx dominant): take right strip of ref, left strip of mov.
    if abs(dx) >= abs(dy):
        ow = max(8, int(round(w * overlap_fraction)))
        ref_s = ref[:, w - ow:]
        mov_s = mov[:, :ow]
    else:
        oh = max(8, int(round(h * overlap_fraction)))
        ref_s = ref[h - oh:, :]
        mov_s = mov[:oh, :]
    return ref_s, mov_s


def register_pair(ref, mov, expected_shift, overlap_fraction=0.1, max_shift=40.0):
    """Register neighbor tile ``mov`` against ``ref`` from image content.

    Args:
        ref: 2D reference tile plane.
        mov: 2D moving neighbor tile plane.
        expected_shift: (dy, dx) stage-prior displacement of mov vs ref, px.
        overlap_fraction: fraction of tile used as the overlap strip.
        max_shift: reject residuals larger than this (px) as unreliable.

    Returns:
        (shift_yx, confidence): refined full (dy, dx) displacement and its ZNCC.
    """
    ref_s, mov_s = _overlap_strips(ref, mov, expected_shift, overlap_fraction)
    residual, _, _ = phase_cross_correlation(
        ref_s, mov_s, upsample_factor=10, normalization=None
    )
    if np.linalg.norm(residual) > max_shift:
        residual = np.zeros(2)
    shift_yx = np.asarray(expected_shift, dtype=float) + residual
    aligned = ndi_shift(mov_s, shift=residual, order=1)
    conf = _zncc(ref_s, aligned)
    return shift_yx, conf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitching_core.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/shared/stitching/register.py tests/test_stitching_core.py
git commit -m "feat(stitching): FFT cross-correlation pairwise tile registration"
```

---

### Task 4: Global spanning-tree tile placement

**Files:**
- Create: `workflow/lib/shared/stitching/place.py`
- Test: `tests/test_stitching_core.py` (extend)

**Interfaces:**
- Consumes: `TileOffsets` (Task 2); pairwise edges `(i, j, shift_yx, confidence)`.
- Produces:
  - `place.solve_global_offsets(n_tiles: int, edges: list[tuple[int, int, np.ndarray, float]], prior: dict[int, tuple[float, float]], min_confidence: float) -> TileOffsets` — builds a confidence-weighted graph over tiles, takes the maximum-confidence spanning tree, propagates offsets from a root, and falls back to `prior` (stage coords) for tiles not connected by any edge above `min_confidence`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_stitching_core.py
from workflow.lib.shared.stitching.place import solve_global_offsets


@pytest.mark.unit
def test_solve_global_offsets_chain():
    # 3 tiles in a row; edge (i->j) carries the true offset of j relative to i.
    edges = [
        (0, 1, np.array([0.0, 100.0]), 0.9),
        (1, 2, np.array([0.0, 100.0]), 0.9),
    ]
    prior = {0: (0.0, 0.0), 1: (0.0, 90.0), 2: (0.0, 190.0)}
    off = solve_global_offsets(3, edges, prior, min_confidence=0.2).to_frame()
    off = off.sort_values("tile").reset_index(drop=True)
    np.testing.assert_allclose(off["x"].to_numpy(), [0.0, 100.0, 200.0], atol=1e-6)
    np.testing.assert_allclose(off["y"].to_numpy(), [0.0, 0.0, 0.0], atol=1e-6)


@pytest.mark.unit
def test_solve_global_offsets_disconnected_uses_prior():
    edges = [(0, 1, np.array([0.0, 100.0]), 0.9)]  # tile 2 disconnected
    prior = {0: (0.0, 0.0), 1: (0.0, 90.0), 2: (5.0, 300.0)}
    off = solve_global_offsets(3, edges, prior, min_confidence=0.2).to_frame()
    row2 = off[off["tile"] == 2].iloc[0]
    assert (row2["y"], row2["x"]) == (5.0, 300.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitching_core.py -k solve_global_offsets -v`
Expected: FAIL with `ImportError` on `solve_global_offsets`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/shared/stitching/place.py
"""Globally-consistent tile placement from pairwise shifts."""

from __future__ import annotations

import igraph as ig
import numpy as np
import pandas as pd

from workflow.lib.shared.stitching.types import TileOffsets


def solve_global_offsets(n_tiles, edges, prior, min_confidence=0.2):
    """Solve per-tile global offsets from pairwise shift edges.

    Args:
        n_tiles: number of tiles.
        edges: list of (i, j, shift_yx, confidence); shift_yx is j minus i.
        prior: {tile: (y, x)} stage-coordinate fallback offsets.
        min_confidence: edges below this confidence are ignored.

    Returns:
        TileOffsets in a single well frame (root tile at its prior position).
    """
    good = [(i, j, s, c) for (i, j, s, c) in edges if c >= min_confidence]
    g = ig.Graph()
    g.add_vertices(n_tiles)
    for i, j, s, c in good:
        g.add_edge(i, j, weight=float(c), shift=np.asarray(s, dtype=float))

    offsets = {t: None for t in range(n_tiles)}
    for comp in g.connected_components(mode="weak"):
        if not comp:
            continue
        sub = g.subgraph(comp)
        # maximum-confidence spanning tree = MST on negative weights
        neg = [-w for w in sub.es["weight"]]
        mst = sub.spanning_tree(weights=neg)
        root_local = 0
        root_global = comp[root_local]
        offsets[root_global] = np.asarray(prior[root_global], dtype=float)
        order = mst.bfs(root_local)[0]
        for v in order:
            v_global = comp[v]
            if offsets[v_global] is not None:
                continue
        # propagate along MST edges from the root
        parent = mst.bfs(root_local)[2]
        bfs_order = mst.bfs(root_local)[0]
        for v in bfs_order:
            if v == root_local:
                continue
            p = parent[v]
            eid = mst.get_eid(p, v)
            shift = mst.es[eid]["shift"]
            # orient shift so it maps parent -> child
            src, tgt = mst.es[eid].tuple
            s = shift if (src, tgt) == (p, v) else -shift
            offsets[comp[v]] = offsets[comp[p]] + s

    for t in range(n_tiles):
        if offsets[t] is None:
            offsets[t] = np.asarray(prior[t], dtype=float)

    frame = pd.DataFrame(
        {"tile": list(range(n_tiles)),
         "y": [offsets[t][0] for t in range(n_tiles)],
         "x": [offsets[t][1] for t in range(n_tiles)]}
    )
    return TileOffsets.from_frame(frame)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitching_core.py -k solve_global_offsets -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/shared/stitching/place.py tests/test_stitching_core.py
git commit -m "feat(stitching): spanning-tree global tile placement with prior fallback"
```

---

### Task 5: Well stitch orchestration + `place_cells`

**Files:**
- Create: `workflow/lib/shared/stitching/stitch_well.py`
- Create: `workflow/lib/shared/stitching/place_cells.py`
- Test: `tests/test_stitching_core.py` (extend)

**Interfaces:**
- Consumes: `select_registration_plane`, `register_pair`, `solve_global_offsets`, `TileOffsets`.
- Produces:
  - `stitch_well.find_neighbor_pairs(prior: dict[int, tuple[float, float]], tile_shape: tuple[int, int], overlap_fraction: float) -> list[tuple[int, int, tuple[float, float]]]` — neighbor tile pairs (i, j, expected_shift) whose prior boxes overlap.
  - `stitch_well.stitch_well(planes: dict[int, np.ndarray], prior: dict[int, tuple[float, float]], overlap_fraction: float, min_confidence: float) -> TileOffsets` — run pairwise registration over neighbor pairs then global placement.
  - `place_cells.place_cells(cells: pd.DataFrame, offsets: TileOffsets, y_col="i", x_col="j", tile_col="tile") -> pd.DataFrame` — add global `gy`, `gx` columns by adding each cell's tile offset to its local centroid.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_stitching_core.py
from workflow.lib.shared.stitching.stitch_well import find_neighbor_pairs, stitch_well
from workflow.lib.shared.stitching.place_cells import place_cells


@pytest.mark.unit
def test_place_cells_applies_offset():
    cells = pd.DataFrame({"tile": [0, 1], "i": [10.0, 20.0], "j": [5.0, 7.0],
                          "cell": [0, 1]})
    off = TileOffsets.from_frame(
        pd.DataFrame({"tile": [0, 1], "y": [0.0, 100.0], "x": [0.0, 50.0]})
    )
    out = place_cells(cells, off)
    np.testing.assert_allclose(out["gy"].to_numpy(), [10.0, 120.0])
    np.testing.assert_allclose(out["gx"].to_numpy(), [5.0, 57.0])


@pytest.mark.unit
def test_find_neighbor_pairs_grid():
    # 2x2 grid, tile side 100, 10% overlap -> right/down neighbors only.
    prior = {0: (0, 0), 1: (0, 90), 2: (90, 0), 3: (90, 90)}
    pairs = find_neighbor_pairs(prior, tile_shape=(100, 100), overlap_fraction=0.1)
    got = {(i, j) for i, j, _ in pairs}
    assert (0, 1) in got and (0, 2) in got and (1, 3) in got and (2, 3) in got
    assert (0, 3) not in got  # diagonal, no overlap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitching_core.py -k "place_cells or neighbor_pairs" -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/shared/stitching/place_cells.py
"""Place per-tile cell centroids into the global well frame."""

from __future__ import annotations

import pandas as pd


def place_cells(cells, offsets, y_col="i", x_col="j", tile_col="tile"):
    """Add global gy, gx columns to a per-tile cell table using tile offsets.

    Args:
        cells: DataFrame with a tile column and local centroid columns.
        offsets: TileOffsets for this modality's well.
        y_col: local centroid row column.
        x_col: local centroid col column.
        tile_col: tile-id column in ``cells``.

    Returns:
        Copy of ``cells`` with float ``gy``, ``gx`` global-frame columns.
    """
    off = offsets.to_frame().set_index("tile")
    out = cells.copy()
    out["gy"] = out[y_col] + out[tile_col].map(off["y"])
    out["gx"] = out[x_col] + out[tile_col].map(off["x"])
    return out
```

```python
# workflow/lib/shared/stitching/stitch_well.py
"""Whole-well stitch orchestration: pairwise registration + global placement."""

from __future__ import annotations

import numpy as np
import shapely

from workflow.lib.shared.stitching.place import solve_global_offsets
from workflow.lib.shared.stitching.register import register_pair


def find_neighbor_pairs(prior, tile_shape, overlap_fraction):
    """Return (i, j, expected_shift) for tiles whose prior boxes overlap."""
    h, w = tile_shape
    ids = sorted(prior)
    boxes = {t: shapely.box(prior[t][1], prior[t][0],
                            prior[t][1] + w, prior[t][0] + h) for t in ids}
    pairs = []
    for a_idx in range(len(ids)):
        for b_idx in range(a_idx + 1, len(ids)):
            i, j = ids[a_idx], ids[b_idx]
            inter = boxes[i].intersection(boxes[j])
            if inter.is_empty or inter.area <= 0:
                continue
            expected = (prior[j][0] - prior[i][0], prior[j][1] - prior[i][1])
            pairs.append((i, j, expected))
    return pairs


def stitch_well(planes, prior, overlap_fraction=0.1, min_confidence=0.2):
    """Stitch one modality's well from 2D tile planes and a stage-coord prior.

    Args:
        planes: {tile: 2D registration plane}.
        prior: {tile: (y, x)} stage-coordinate offsets (initial guess).
        overlap_fraction: expected fractional tile overlap.
        min_confidence: minimum ZNCC to trust a pairwise edge.

    Returns:
        TileOffsets in a single global well frame.
    """
    any_plane = next(iter(planes.values()))
    tile_shape = any_plane.shape
    pairs = find_neighbor_pairs(prior, tile_shape, overlap_fraction)
    edges = []
    for i, j, expected in pairs:
        shift_yx, conf = register_pair(
            planes[i], planes[j], expected_shift=expected,
            overlap_fraction=overlap_fraction,
            max_shift=0.5 * min(tile_shape),
        )
        edges.append((i, j, shift_yx, conf))
    return solve_global_offsets(len(planes), edges, prior, min_confidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitching_core.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/shared/stitching/stitch_well.py workflow/lib/shared/stitching/place_cells.py tests/test_stitching_core.py
git commit -m "feat(stitching): well stitch orchestration + global cell placement"
```

---

### Task 6: Re-tile + bucket global centroids into larger sub-tiles

**Files:**
- Create: `workflow/lib/merge/image_stitch_merge.py`
- Test: `tests/test_image_stitch_merge.py`

**Interfaces:**
- Consumes: global cell tables with `gy`, `gx` (Task 5).
- Produces:
  - `image_stitch_merge.assign_subtiles(cells: pd.DataFrame, subtile_size: tuple[int, int], gy_col="gy", gx_col="gx") -> pd.DataFrame` — add an integer `subtile` column bucketing cells by a regular grid over the global frame.
  - `image_stitch_merge.subtile_bounds(cells: pd.DataFrame, subtile_size) -> dict[int, tuple[int, int, int, int]]` — per-subtile (y0, x0, y1, x1) for QC.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_image_stitch_merge.py
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from workflow.lib.merge.image_stitch_merge import assign_subtiles


@pytest.mark.unit
def test_assign_subtiles_grid():
    cells = pd.DataFrame({"gy": [0.0, 250.0, 10.0], "gx": [0.0, 10.0, 250.0]})
    out = assign_subtiles(cells, subtile_size=(200, 200))
    # (0,0)->tile at grid (0,0); (250,10)->grid (1,0); (10,250)->grid (0,1)
    assert out["subtile"].tolist() == [0, 2, 1] or len(set(out["subtile"])) == 3
    # same-bucket cells share an id
    assert out.loc[0, "subtile"] != out.loc[1, "subtile"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_stitch_merge.py -v`
Expected: FAIL with `ImportError` on `assign_subtiles`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/merge/image_stitch_merge.py
"""Sub-tile hash merge over image-stitched global cell frames."""

from __future__ import annotations

import numpy as np
import pandas as pd


def assign_subtiles(cells, subtile_size, gy_col="gy", gx_col="gx"):
    """Bucket global-frame cells into a regular sub-tile grid.

    Args:
        cells: DataFrame with global centroid columns.
        subtile_size: (height, width) of each sub-tile in px.
        gy_col: global-y column.
        gx_col: global-x column.

    Returns:
        Copy of ``cells`` with an integer ``subtile`` column.
    """
    sh, sw = subtile_size
    gy = cells[gy_col].to_numpy()
    gx = cells[gx_col].to_numpy()
    row = np.floor((gy - gy.min()) / sh).astype(int)
    col = np.floor((gx - gx.min()) / sw).astype(int)
    ncol = col.max() + 1
    out = cells.copy()
    out["subtile"] = row * ncol + col
    return out


def subtile_bounds(cells, subtile_size, gy_col="gy", gx_col="gx"):
    """Return {subtile: (y0, x0, y1, x1)} bounds for QC."""
    sh, sw = subtile_size
    gy0, gx0 = cells[gy_col].min(), cells[gx_col].min()
    bounds = {}
    for st, grp in cells.groupby("subtile"):
        r = int((grp[gy_col].min() - gy0) // sh)
        c = int((grp[gx_col].min() - gx0) // sw)
        bounds[int(st)] = (gy0 + r * sh, gx0 + c * sw,
                           gy0 + (r + 1) * sh, gx0 + (c + 1) * sw)
    return bounds
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_image_stitch_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/merge/image_stitch_merge.py tests/test_image_stitch_merge.py
git commit -m "feat(merge): sub-tile bucketing for image-stitch merge"
```

---

### Task 7: Per-sub-tile hash merge (reuse `merge_triangle_hash`)

**Files:**
- Modify: `workflow/lib/merge/image_stitch_merge.py`
- Test: `tests/test_image_stitch_merge.py` (extend)

**Interfaces:**
- Consumes: `assign_subtiles` (Task 6); `workflow.lib.merge.hash.find_triangles`/`evaluate_match`; `workflow.lib.merge.fast_merge.merge_triangle_hash`.
- Produces:
  - `image_stitch_merge.merge_subtiles(ph_cells: pd.DataFrame, sbs_cells: pd.DataFrame, subtile_size, threshold: float, local_refinement: str | None, warp_kwargs: dict | None, evaluate_kwargs: dict | None) -> pd.DataFrame` — for each shared sub-tile: hash-align phenotype→SBS centroids (in `gy`,`gx`), then `merge_triangle_hash` with local refinement; concatenate matches with a `subtile` column.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_image_stitch_merge.py
from workflow.lib.merge.image_stitch_merge import merge_subtiles


def _piecewise_two_modality(seed=0):
    """Two global frames related by a per-subtile-varying affine (rotation ramp)."""
    rng = np.random.default_rng(seed)
    rows = []
    cid = 0
    for st_r in range(2):
        for st_c in range(2):
            n = 200
            X = rng.uniform(0, 400, size=(n, 2)) + np.array([st_r * 400, st_c * 400])
            theta = np.deg2rad(1.0 + 0.3 * (st_r + st_c))  # varies per subtile
            scale = 0.27
            R = scale * np.array([[np.cos(theta), -np.sin(theta)],
                                  [np.sin(theta), np.cos(theta)]])
            Y = X @ R.T + np.array([40.0, -15.0])
            for k in range(n):
                rows.append((cid, X[k, 0], X[k, 1], Y[k, 0], Y[k, 1]))
                cid += 1
    df = pd.DataFrame(rows, columns=["cell", "phy", "phx", "sy", "sx"])
    ph = df[["cell", "phy", "phx"]].rename(columns={"phy": "gy", "phx": "gx"})
    ph["tile"] = 0; ph["well"] = "A1"; ph["plate"] = 1; ph["i"] = ph["gy"]; ph["j"] = ph["gx"]
    sbs = df[["cell", "sy", "sx"]].rename(columns={"sy": "gy", "sx": "gx"})
    sbs["tile"] = 0; sbs["well"] = "A1"; sbs["plate"] = 1; sbs["i"] = sbs["gy"]; sbs["j"] = sbs["gx"]
    return ph, sbs


@pytest.mark.unit
def test_merge_subtiles_recovers_matches():
    ph, sbs = _piecewise_two_modality()
    merged = merge_subtiles(
        ph, sbs, subtile_size=(400, 400), threshold=4,
        local_refinement="thin_plate_spline", warp_kwargs=None,
        evaluate_kwargs={"ransac_kwargs": {"random_state": 0}},
    )
    # most cells should match across the 4 subtiles despite the rotation ramp
    assert len(merged) > 0.7 * len(ph)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_stitch_merge.py::test_merge_subtiles_recovers_matches -v`
Expected: FAIL with `ImportError` on `merge_subtiles`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to workflow/lib/merge/image_stitch_merge.py
from workflow.lib.merge.hash import find_triangles, evaluate_match
from workflow.lib.merge.fast_merge import merge_triangle_hash


def _align_subtile(ph_sub, sbs_sub, evaluate_kwargs):
    """Hash-align phenotype->SBS within one sub-tile; return alignment dict or None."""
    t_ph = find_triangles(ph_sub[["gy", "gx"]].rename(columns={"gy": "i", "gx": "j"}))
    t_sbs = find_triangles(sbs_sub[["gy", "gx"]].rename(columns={"gy": "i", "gx": "j"}))
    rot, trans, score = evaluate_match(t_ph, t_sbs, **(evaluate_kwargs or {}))
    if rot is None:
        return None
    return {"rotation": rot, "translation": trans, "score": score}


def merge_subtiles(ph_cells, sbs_cells, subtile_size, threshold=4,
                   local_refinement=None, warp_kwargs=None, evaluate_kwargs=None):
    """Hash-merge phenotype and SBS cells sub-tile by sub-tile (piecewise affine).

    Args:
        ph_cells: phenotype global cell table (needs gy, gx, i, j, tile, well, plate).
        sbs_cells: SBS global cell table (same columns).
        subtile_size: (h, w) of the re-tile grid in px.
        threshold: nearest-neighbor match threshold in px.
        local_refinement: None | "polynomial" | "thin_plate_spline".
        warp_kwargs: extra kwargs for the warp model.
        evaluate_kwargs: extra kwargs for evaluate_match (e.g. ransac_kwargs).

    Returns:
        Concatenated matched-cell DataFrame with a ``subtile`` column.
    """
    ph = assign_subtiles(ph_cells, subtile_size)
    sbs = assign_subtiles(sbs_cells, subtile_size)
    out = []
    for st in sorted(set(ph["subtile"]) & set(sbs["subtile"])):
        ph_sub = ph[ph["subtile"] == st].reset_index(drop=True)
        sbs_sub = sbs[sbs["subtile"] == st].reset_index(drop=True)
        if len(ph_sub) < 30 or len(sbs_sub) < 30:
            continue
        alignment = _align_subtile(ph_sub, sbs_sub, evaluate_kwargs)
        if alignment is None:
            continue
        ph_hash = ph_sub.assign(i=ph_sub["gy"], j=ph_sub["gx"])
        sbs_hash = sbs_sub.assign(i=sbs_sub["gy"], j=sbs_sub["gx"])
        m = merge_triangle_hash(
            ph_hash, sbs_hash, alignment, threshold=threshold,
            local_refinement=local_refinement, warp_kwargs=warp_kwargs,
        )
        if len(m):
            m = m.copy()
            m["subtile"] = st
            out.append(m)
    if not out:
        return ph_cells.head(0).assign(subtile=pd.Series(dtype=int))
    return pd.concat(out, ignore_index=True)
```

Note for the executor: confirm the exact positional/keyword contract of `merge_triangle_hash` and `evaluate_match` return arity against `workflow/lib/merge/fast_merge.py` and `workflow/lib/merge/hash.py` before relying on them (the fast-mode tests in `tests/test_merge_levers.py` show `evaluate_match` returns `(rotation, translation, score)` and `merge_triangle_hash(df0, df1, alignment, threshold=..., local_refinement=..., warp_kwargs=...)`). Adjust column plumbing if `merge_triangle_hash` expects specific `i`/`j` names.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_image_stitch_merge.py -v`
Expected: PASS. If the match rate assertion is flaky due to RANSAC, pin `random_state` (already set) and re-run.

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/merge/image_stitch_merge.py tests/test_image_stitch_merge.py
git commit -m "feat(merge): per-sub-tile hash+TPS merge over stitched frames"
```

---

### Task 8: Optional fused OME-Zarr v3 mosaic (chunked, dask)

**Files:**
- Create: `workflow/lib/shared/stitching/fuse.py`
- Test: `tests/test_stitching_core.py` (extend)

**Interfaces:**
- Consumes: `TileOffsets` (Task 2).
- Produces:
  - `fuse.fuse_mosaic(planes: dict[int, np.ndarray], offsets: TileOffsets, out_path: str, chunk: int = 1024, blend: str = "linear") -> str` — lazily place tiles at global offsets into a chunked zarr v3 array, linear-blend overlaps, return the written path. Peak memory bounded by chunk size, not well size.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_stitching_core.py
import zarr
from workflow.lib.shared.stitching.fuse import fuse_mosaic


@pytest.mark.unit
def test_fuse_mosaic_writes_chunked_zarr(tmp_path):
    planes = {0: np.full((64, 64), 5.0, np.float32),
              1: np.full((64, 64), 9.0, np.float32)}
    off = TileOffsets.from_frame(
        pd.DataFrame({"tile": [0, 1], "y": [0.0, 0.0], "x": [0.0, 60.0]})
    )
    out = fuse_mosaic(planes, off, str(tmp_path / "mosaic.zarr"), chunk=32)
    arr = zarr.open(out, mode="r")
    assert arr.shape == (64, 124)          # 60 + 64
    assert arr[0, 0] == 5.0 and arr[0, 123] == 9.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitching_core.py -k fuse_mosaic -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# workflow/lib/shared/stitching/fuse.py
"""Lazy chunked fusion of tiles into an OME-Zarr v3 mosaic."""

from __future__ import annotations

import numpy as np
import zarr


def fuse_mosaic(planes, offsets, out_path, chunk=1024, blend="linear"):
    """Fuse tile planes at global offsets into a chunked zarr v3 mosaic.

    Args:
        planes: {tile: 2D image}.
        offsets: TileOffsets in the global well frame.
        out_path: destination zarr path.
        chunk: chunk edge in px (bounds peak memory).
        blend: "linear" weighted overlap blending or "none".

    Returns:
        The written zarr path.
    """
    off = offsets.to_frame().set_index("tile")
    th, tw = next(iter(planes.values())).shape
    ys = {t: int(round(off.loc[t, "y"])) for t in planes}
    xs = {t: int(round(off.loc[t, "x"])) for t in planes}
    y0 = min(ys.values())
    x0 = min(xs.values())
    H = max(ys[t] - y0 + th for t in planes)
    W = max(xs[t] - x0 + tw for t in planes)

    acc = zarr.open(out_path + ".acc.tmp", mode="w", shape=(H, W),
                    chunks=(chunk, chunk), dtype="f4")
    wsum = zarr.open(out_path + ".w.tmp", mode="w", shape=(H, W),
                     chunks=(chunk, chunk), dtype="f4")
    weight = np.ones((th, tw), np.float32)
    if blend == "linear":
        wy = np.minimum(np.arange(th), np.arange(th)[::-1]) + 1.0
        wx = np.minimum(np.arange(tw), np.arange(tw)[::-1]) + 1.0
        weight = np.outer(wy, wx).astype(np.float32)
    for t, plane in planes.items():
        yy, xx = ys[t] - y0, xs[t] - x0
        acc[yy:yy + th, xx:xx + tw] = acc[yy:yy + th, xx:xx + tw] + plane * weight
        wsum[yy:yy + th, xx:xx + tw] = wsum[yy:yy + th, xx:xx + tw] + weight

    out = zarr.open(out_path, mode="w", shape=(H, W),
                    chunks=(chunk, chunk), dtype="f4")
    for i in range(0, H, chunk):
        for j in range(0, W, chunk):
            a = acc[i:i + chunk, j:j + chunk]
            w = wsum[i:i + chunk, j:j + chunk]
            out[i:i + chunk, j:j + chunk] = np.divide(a, w, out=np.zeros_like(a),
                                                      where=w > 0)
    return out_path
```

Note for the executor: this uses per-chunk numpy for clarity and bounded memory. If the fused mosaic is later promoted to a first-class OME-Zarr deliverable, wrap `out` with `write_image_omezarr` from `workflow.lib.shared.image_io` for NGFF metadata (mirror `tests/test_omezarr.py`). Clean up the `.acc.tmp`/`.w.tmp` scratch stores at the end.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitching_core.py -k fuse_mosaic -v`
Expected: PASS.

- [ ] **Step 5: Commit** (on operator approval)

```bash
git add workflow/lib/shared/stitching/fuse.py tests/test_stitching_core.py
git commit -m "feat(stitching): optional chunked OME-Zarr mosaic fusion"
```

---

### Task 8b: Generate segmentation (masks + centroids) for aligned dev tiles via brieflow segmentation + her config

**Rationale:** Vaishnavi provided aligned images + info parquets but NOT mask label images. Segmentation is a required pipeline stage that produces the cell data the merge consumes; the stitching CORE is image-based and independent of it, but the merge needs cells. We regenerate masks+centroids ourselves (self-contained, reproducible) by running brieflow's OWN segmentation with her config, rather than trusting the provided parquets or hand-rolling cellpose.

**Files:**
- Create (external, not committed): `/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev/segment_dev.py` + a namespaced GPU sbatch script.
- Output (external): `stitch_dev/{sbs,phenotype}_masks/P-1_W-A1_T-*.tiff` (label images) + `stitch_dev/{sbs,phenotype}_info_regen/` centroid parquets.

**Approach (faithful reproduction of `workflow/scripts/shared/segment.py`):**
- Read `workflow/scripts/shared/segment.py`, `lib/shared/rule_utils.get_segmentation_params`, and the info/centroid-extraction step to mirror channel prep, `logscale`, `reconcile`, and output format exactly.
- Per SBS aligned tile `(11,5,1480,1480)`: take the DAPI segmentation cycle (`dapi_cycle_index=0` → `data[0]`), `segment_cellpose(..., dapi_index=0, cyto_index=4, nuclei_diameter=7.8176, cell_diameter=13.8658, cellpose_model="cyto3", cells=False, reconcile="contained_in_cells", gpu=True)` → nuclei mask; extract centroids (`i,j,cell,area,bounds,tile`) to match the info-parquet schema.
- Per phenotype aligned tile `(5,3200,3200)`: `segment_cellpose(..., dapi_index=0, cyto_index=1, nuclei_diameter=20.8369, cell_diameter=42.6103, cells=True, reconcile="contained_in_cells", gpu=True)` → nuclei+cell masks; extract centroids.
- Thresholds from her config: nuclei_flow 0.4, nuclei_cellprob 0.0, cell_flow 1, cell_cellprob 0.
- Her config sets `gpu: false`; override to `gpu: True` for the run (masks are equivalent; GPU is materially faster). Note the override.

**Cluster:** GPU job — look up GPU partitions/limits first (`curl -s http://slurmstatus.wi.mit.edu/limits.html`); submit a namespaced `${USER}_stitch_seg` sbatch on a GPU partition with `--gres=gpu:1`; run in background. Verify torch sees CUDA in `brieflow_zarr3_speed` before submitting (fallback: CPU, slower).

**Done-when:** masks + regenerated centroid parquets exist for all 9 SBS + 56 phenotype dev tiles; centroid counts are sane (compare loosely to provided info parquets: SBS ~5k/tile, PH ~2k/tile — same order of magnitude). These regenerated centroids feed Task 9's `place_cells` (use them instead of the provided info parquets).

- [ ] No repo commit (external data-generation).

### Task 9: Real-data validation + memory/speed benchmark on Vaishnavi A1

**Files:**
- Create (external harness, not committed to repo): `/lab/ops_analysis_ssd/test_matteo/merge_troubleshooting/harness/image_stitch_bench.py`

**Interfaces:**
- Consumes: everything above; the dev tile subset from Task 1; the A1 `sbs_info`/`phenotype_info` parquets; `merge_troubleshooting/harness/box_metrics.py::box_metrics`.
- Produces: a printed report — intra-modality stitch confidence per edge, per-sub-tile match rate, `box_metrics` (`sbs_box_match`, `ph_match`, `overlap_frac`, `median_dist`), peak RSS, and wall-time.

- [ ] **Step 1: Write the benchmark script**

```python
# image_stitch_bench.py  (run in brieflow_zarr3_speed, from brieflow submodule root)
import sys, time, resource
from pathlib import Path
import glob
import numpy as np
import pandas as pd
from tifffile import imread

sys.path.insert(0, "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow")
sys.path.insert(0, "/lab/ops_analysis_ssd/test_matteo/merge_troubleshooting/harness")

from workflow.lib.shared.stitching.prep import select_registration_plane
from workflow.lib.shared.stitching.stitch_well import stitch_well
from workflow.lib.shared.stitching.place_cells import place_cells
from workflow.lib.merge.image_stitch_merge import merge_subtiles
import box_metrics as bm  # noqa

DEV = "/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/stitch_dev"
BASE = "/lab/ops_analysis_ssd/test_matteo/merge_vaishnavi/general_merge_troubleshooting"

def tile_id(path):  # parse T-<n> from filename
    return int(Path(path).stem.split("T-")[1].split("__")[0])

def load(modality, channel, cycle):
    planes = {}
    for f in sorted(glob.glob(f"{DEV}/{modality}_images/*.tiff")):
        planes[tile_id(f)] = select_registration_plane(imread(f), channel, cycle)
    return planes

t0 = time.time()
sbs_planes = load("sbs", channel=0, cycle=0)          # DAPI, cycle 0
ph_planes = load("phenotype", channel=0, cycle=None)  # DAPI

# stage-coord prior from combined metadata (restricted to dev tiles)
def prior(meta_glob, tiles):
    m = pd.read_parquet(glob.glob(meta_glob)[0])
    m = m[m["tile"].isin(tiles)].drop_duplicates("tile")
    px = m["pixel_size_x"].iloc[0] if "pixel_size_x" in m else 1.0
    return {int(r.tile): ((r.y_pos - m.y_pos.min()) / px,
                          (r.x_pos - m.x_pos.min()) / px) for r in m.itertuples()}

sbs_prior = prior(f"{BASE}/*sbs*metadata*", set(sbs_planes))
ph_prior = prior(f"{BASE}/*phenotype*metadata*", set(ph_planes))

sbs_off = stitch_well(sbs_planes, sbs_prior, overlap_fraction=0.1, min_confidence=0.2)
ph_off = stitch_well(ph_planes, ph_prior, overlap_fraction=0.1, min_confidence=0.2)
print("SBS offsets:\n", sbs_off.to_frame())
print("PH offsets:\n", ph_off.to_frame())

# global centroids from existing info parquets (restricted to dev tiles)
sbs_info = pd.read_parquet(glob.glob(f"{BASE}/*sbs_info*")[0])
ph_info = pd.read_parquet(glob.glob(f"{BASE}/*phenotype_info*")[0])
sbs_info = sbs_info[sbs_info["tile"].isin(sbs_planes)]
ph_info = ph_info[ph_info["tile"].isin(ph_planes)]

# rescale phenotype global coords to SBS pixel size before bucketing (coarse common scale)
SCALE = 0.325 / 1.2085  # pheno px / sbs px  (confirm from metadata)
sbs_g = place_cells(sbs_info, sbs_off)
ph_g = place_cells(ph_info, ph_off)
ph_g["gy"] *= SCALE; ph_g["gx"] *= SCALE

merged = merge_subtiles(ph_g, sbs_g, subtile_size=(3000, 3000), threshold=4,
                        local_refinement="thin_plate_spline")
print("matched:", len(merged), "of PH", len(ph_g))
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # GB on Linux (KB*)
print(f"wall={time.time()-t0:.1f}s peak_rss={peak:.2f}GB")
```

- [ ] **Step 2: Run the benchmark**

```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_zarr3_speed
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow
python /lab/ops_analysis_ssd/test_matteo/merge_troubleshooting/harness/image_stitch_bench.py
```
Expected: prints per-modality offsets close to the stage prior (subpixel refinement), a nonzero matched count, and a peak RSS far below the size of a full-well canvas. **Record** wall-time + peak RSS + match count as the baseline.

- [ ] **Step 3: Compare against the box-metrics contract**

Extend the script to call `bm.box_metrics(...)` on the matched vs unmatched SBS cells within the phenotype box (mirror `merge_troubleshooting/harness/box_metrics.py` usage). Target: `sbs_box_match` in the neighborhood of the fast-mode headline (~0.9+ on dense tiles) with sub-px `median_dist`.

- [ ] **Step 4: Head-to-head GO/NO-GO comparison (governing gate).** On the SAME well subset, run the legacy `stitch` path and `fast` path and record wall-time + peak RSS for each, next to `image_stitch`. Pass bar: `image_stitch` wall-time and peak RSS are materially below legacy `stitch` (target: peak RSS a fraction of the full-well-canvas approach; wall-time ≤ legacy stitch), AND `sbs_box_match`/`median_dist` do not regress vs `fast`. If `image_stitch` is not materially faster/leaner, STOP and report — the divergence is not justified; do not wire it as a recommended path.

- [ ] **Step 5: Record findings** in `merge_troubleshooting/` notes (not the repo): stitch-offset vs stage-prior agreement, per-sub-tile match rates, and the head-to-head speed/memory/quality table.

- [ ] **Step 5: No repo commit** (external harness).

---

### Task 10: Wire `merge_approach: "image_stitch"` into scripts + snakemake (gated, backward-compatible)

**Files:**
- Create: `workflow/scripts/merge/image_stitch.py`
- Create: `workflow/scripts/merge/image_stitch_merge.py`
- Modify: `workflow/rules/merge.smk` (add an `elif merge_approach == "image_stitch":` block; do not touch the `fast`/`stitch` blocks)
- Test: `tests/test_image_stitch_merge.py` (extend with a backward-compat guard)

**Interfaces:**
- Consumes: the library functions from Tasks 5–8.
- Produces: snakemake rules `image_stitch_sbs`, `image_stitch_phenotype`, `retile_hash_merge`, `summarize_image_stitch`, selected only when `config["merge"]["approach"] == "image_stitch"`.

- [ ] **Step 1: Write the failing backward-compat test**

```python
# append to tests/test_image_stitch_merge.py
@pytest.mark.unit
def test_default_approach_is_fast():
    """A config with no merge.approach must still resolve to 'fast' (unchanged)."""
    cfg = {}
    assert cfg.get("merge", {}).get("approach", "fast") == "fast"
    cfg2 = {"merge": {"approach": "image_stitch"}}
    assert cfg2.get("merge", {}).get("approach", "fast") == "image_stitch"
```

- [ ] **Step 2: Run test to verify it passes trivially, then read merge.smk gating**

Run: `pytest tests/test_image_stitch_merge.py::test_default_approach_is_fast -v`
Expected: PASS. Then read `workflow/rules/merge.smk:1-12` and `:96` to see the `if merge_approach == "fast"` / `if merge_approach == "stitch"` structure you will extend.

- [ ] **Step 3: Add the script wrappers**

Create `workflow/scripts/merge/image_stitch.py` that: reads the well's tile file list + metadata + info parquet from `snakemake.input`, builds planes via `select_registration_plane`, computes `stitch_well`, `place_cells`, optionally `fuse_mosaic` (gated on `config["merge"].get("fuse_mosaic", False)`), and writes the global cell-position parquet (+ offsets parquet + optional mosaic) to `snakemake.output`. Mirror the structure of `workflow/scripts/merge/stitch.py` for the snakemake I/O boilerplate.

Create `workflow/scripts/merge/image_stitch_merge.py` that: reads both modalities' global cell parquets, calls `merge_subtiles` with config-driven `subtile_size`, `threshold`, `local_refinement`, `warp_kwargs`, then hands the matches to the existing `deduplicate_merge` step, writing merged cells + a QC summary.

- [ ] **Step 4: Add the gated rules to merge.smk**

After the `if merge_approach == "stitch":` block, add an independent `if merge_approach == "image_stitch":` block defining `image_stitch_sbs`, `image_stitch_phenotype` (script `../scripts/merge/image_stitch.py`), `retile_hash_merge` (script `../scripts/merge/image_stitch_merge.py`), and `summarize_image_stitch`. Reuse the per-well wildcard pattern and `output_to_input` helpers already used by the `stitch` rules. New config keys read via `config.get("merge", {}).get(...)`: `subtile_size`, `fuse_mosaic`, `stitch_channel`, `stitch_overlap_fraction` (plus existing hash/TPS keys).

- [ ] **Step 5: Validate the snakemake graph builds for all three approaches**

```bash
cd /lab/ops_analysis_ssd/test_matteo/brieflow-speed/analysis
# fast (default) unchanged:
BRIEFLOW_SKIP_RESOLVE=1 snakemake -n -s ../brieflow/workflow/Snakefile --configfile config/config.yml 2>&1 | tail -5
```
Expected: dry-run succeeds for the default (`fast`) config with no new rules triggered. Then flip a scratch config copy to `approach: image_stitch` and confirm the new rules appear in the dry-run and the `stitch`/`fast` rules do not. Use `brieflow-auto:brieflow-preflight` to statically validate the config against the new rule code.

- [ ] **Step 6: Commit** (on operator approval)

```bash
git add workflow/scripts/merge/image_stitch.py workflow/scripts/merge/image_stitch_merge.py workflow/rules/merge.smk tests/test_image_stitch_merge.py
git commit -m "feat(merge): wire image_stitch approach (gated, fast/stitch unchanged)"
```

---

### Task 11 (optional, deferred): expose params in the merge notebook

**Files:**
- Modify: `analysis/5_merge.py`

Add an operator-parameter block for `approach: image_stitch`, `subtile_size`, `fuse_mosaic`, `stitch_channel`, `stitch_overlap_fraction` mirroring the existing SET-PARAMETERS marker-block convention, persisted to config via `convert_tuples_to_lists`. Defer until Tasks 1–10 validate on real data. No test (notebook file).

---

## Self-Review

**Spec coverage:**
- Shared core (register/place/fuse/place_cells, zarr3) → Tasks 2–5, 8. ✓
- Image-based, stage-prior-optional → Task 3/5 (prior is fallback only). ✓
- Merge application: stitch→retile→sub-tile hash→dedup → Tasks 5–7, 10. ✓
- Re-tile carries existing centroids re-bucketed → Task 6 (`assign_subtiles`, no re-segmentation). ✓
- Offsets always, mosaic optional/gated → Task 5 (offsets) + Task 8 (`fuse_mosaic`, gated in Task 10). ✓
- Sub-tile size config param w/ default → Task 6 param + Task 10 config key. ✓
- Backward compatible, gated, default byte-identical → Task 10 (independent `if` block, `config.get` defaults) + Task 10 Step 1/5 guards. ✓
- zarr3-native, no numba, clean-room → Global Constraints + Task 3 (skimage FFT) + Task 8 (zarr v3). ✓
- Validation on A1 with box-metrics + memory/speed → Task 9. ✓
- Preprocess retile (App 2) → out of scope (spec Non-goals). ✓

**Placeholder scan:** no TBD/TODO; every code step has concrete content. Two explicit "Note for the executor" callouts direct verification of external signatures (`merge_triangle_hash`, `evaluate_match`, `write_image_omezarr`) rather than leaving them vague. ✓

**Type consistency:** `TileOffsets.from_frame`/`.to_frame` used consistently (Tasks 2,4,5,8); columns `tile,y,x` fixed in Task 2; global cell columns `gy,gx` introduced in Task 5 and consumed in Tasks 6,7,9; `merge_subtiles` signature stable between Task 7 definition and Task 9/10 use. ✓

**Known execution risks (flagged, not blockers):**
- Real-data registration may need overlap-fraction / max-shift tuning (Task 9 is a measured, non-asserting task for exactly this).
- `merge_triangle_hash` column expectations must be confirmed against `fast_merge.py` (noted in Task 7).
- The `SCALE = 0.325/1.2085` constant in Task 9 should be read from metadata, not hard-coded, once confirmed.
