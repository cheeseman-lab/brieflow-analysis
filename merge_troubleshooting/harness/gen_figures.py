"""Generate all figures for all datasets using the winner config, run the deterministic
figure auditor on each, and write figures/harness/audit.json (metrics + flags + captions)
for report.py. Prints any flags so artifacts self-surface.
"""
import json
import sys

import datasets as D
import run_config as RC
import figures as F

RESULTS = D.MT_DIR / "results"
AUDIT = D.MT_DIR / "figures" / "harness" / "audit.json"


def _clean(cfg):
    out = {}
    for k, v in cfg.items():
        if k in ("threshold", "warp_degree", "warp_iterations", "warp_min_correspondences",
                 "ransac_random_state", "threshold_point"):
            out[k] = int(float(v))
        elif k in ("threshold_triangle", "threshold_region", "ransac_residual_threshold"):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def run(names):
    cfg = _clean(json.loads((RESULTS / "winner.json").read_text())["winner_config"])
    print("winner cfg:", cfg)
    audit = {}
    if AUDIT.exists():
        audit = json.loads(AUDIT.read_text())
    for n in names:
        ctx = RC.load_context(n)
        for kind, call in [
            ("matching", lambda: F.matching_figure(n, cfg, ctx)),
            ("alignment_quality", lambda: F.alignment_quality_figure(n, cfg, ctx)),
            ("tile_grid", lambda: F.tile_grid_figure(n)),
            ("pooled_merge", lambda: F.pooled_merge_figure(n, cfg, ctx)),
        ]:
            try:
                res = call()
                if res is None:
                    continue
                path, aud = res
                audit[path.name] = aud
                tag = "  FLAGS: " + "; ".join(aud["flags"]) if aud["flags"] else "  ok"
                print(f"{path.name}{tag}")
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"{n} {kind} ERROR: {type(e).__name__}: {e}")
    AUDIT.write_text(json.dumps(audit, indent=2))
    print(f"\nwrote {AUDIT}")
    flagged = {k: v["flags"] for k, v in audit.items() if v["flags"]}
    print(f"FLAGGED FIGURES: {len(flagged)}")
    for k, fl in flagged.items():
        print(f"  {k}: {fl}")


if __name__ == "__main__":
    run(sys.argv[1:] or list(D.REGISTRY))
