"""Content-keyed cache for the expensive triangle-hashing step.

hash_cell_locations() dominates harness runtime and is INVARIANT to every swept lever
(it depends only on cell i,j). So compute it once per (dataset, modality) and reuse across
the entire config grid. Cache key = info-parquet size + sha1(hash.py source) so the cache
auto-invalidates if the hashing code changes.
"""
import hashlib
import pathlib
import sys

import pandas as pd

import datasets as D

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge import hash as merge_hash  # noqa: E402
from lib.merge.hash import hash_cell_locations  # noqa: E402

CACHE_HASH = D.MT_DIR / "cache" / "hashed"
_HASHPY_SHA = hashlib.sha1(pathlib.Path(merge_hash.__file__).read_bytes()).hexdigest()[:8]


def _key(info_path):
    size = pathlib.Path(info_path).stat().st_size
    return f"{size}_{_HASHPY_SHA}"


def hashed(name, modality):
    """Return the triangle-hash DataFrame (with a 'tile' column) for a dataset modality.

    modality: 'phenotype' or 'sbs'. Cached to cache/hashed/{name}/{modality}__{key}.parquet.
    """
    info_key = "phenotype_info" if modality == "phenotype" else "sbs_info"
    info_path = D.resolve_local(name, info_key)
    out = CACHE_HASH / name / f"{modality}__{_key(info_path)}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    df = pd.read_parquet(info_path)
    h = hash_cell_locations(df)
    out.parent.mkdir(parents=True, exist_ok=True)
    h.to_parquet(out)
    return h


if __name__ == "__main__":
    import time
    name = sys.argv[1] if len(sys.argv) > 1 else "vaishnavi"
    for mod in ("phenotype", "sbs"):
        t = time.time()
        h = hashed(name, mod)
        print(f"{name}/{mod}: {len(h)} triangles, {time.time()-t:.0f}s, "
              f"{h.tile.nunique()} tiles -> cached")
