"""Pull ONLY the flat info+metadata parquets for the GCS datasets into cache/raw/{name}/.
Never mirrors images. Idempotent (skips files already present). owen_20x additionally tries
to fetch an existing per-tile alignment from old_merge (it has no metadata to re-derive one).
"""
import subprocess
import sys

from datasets import REGISTRY, raw_path, CACHE_RAW


def _cp(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print(f"  skip (exists): {dst.name}")
        return True
    print(f"  cp {src} -> {dst}")
    r = subprocess.run(["gsutil", "-m", "cp", src, str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAILED: {r.stderr.strip().splitlines()[-1] if r.stderr else r.returncode}")
        return False
    return True


def main(names):
    for name in names:
        spec = REGISTRY[name]
        if "gcs" not in spec:
            print(f"[{name}] local — nothing to pull")
            continue
        print(f"[{name}] pulling -> {CACHE_RAW / name}")
        for key, src in spec["gcs"].items():
            _cp(src, raw_path(name, key))
        # owen_20x: grab an existing alignment parquet (no metadata to rederive one)
        opt = spec.get("gcs_optional", {})
        if "fast_alignment" in opt:
            base = opt["fast_alignment"]
            ls = subprocess.run(["gsutil", "ls", base], capture_output=True, text=True)
            cands = [l for l in ls.stdout.splitlines()
                     if any(k in l.lower() for k in ("fast_alignment", "alignment"))]
            if cands:
                _cp(cands[0], raw_path(name, "fast_alignment"))
            else:
                print(f"  no alignment parquet found under {base}:")
                print("   ", "\n    ".join(ls.stdout.splitlines()[:12]))
    print("done")


if __name__ == "__main__":
    names = sys.argv[1:] or [n for n, s in REGISTRY.items() if "gcs" in s]
    main(names)
