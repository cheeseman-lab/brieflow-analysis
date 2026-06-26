"""Config grid for the merge sweep. expand() -> list of flat config dicts.

Axes chosen from the tunable levers. Warp-internal axes only apply when refinement is on.
ransac_random_state is pinned for reproducibility across the sweep.
"""
import itertools

# Each axis: name -> list of values. None means "use brieflow default".
GRID = {
    "threshold": [2, 3, 4],
    "local_refinement": [None, "polynomial"],
    "threshold_triangle": [0.3, 0.4],
    "ransac_residual_threshold": [None, 2.0],
    "ransac_random_state": [0],
}
# applied only when local_refinement is on
WARP_GRID = {
    "warp_degree": [2, 3],
    "warp_iterations": [2],
}


def expand():
    base_keys = list(GRID)
    configs = []
    for combo in itertools.product(*GRID.values()):
        cfg = {k: v for k, v in zip(base_keys, combo) if v is not None or k == "local_refinement"}
        cfg = {k: v for k, v in cfg.items() if v is not None}
        if cfg.get("local_refinement"):
            for wcombo in itertools.product(*WARP_GRID.values()):
                c = dict(cfg)
                c.update({k: v for k, v in zip(WARP_GRID, wcombo)})
                configs.append(c)
        else:
            configs.append(cfg)
    # dedupe by config_id
    seen, out = set(), []
    for c in configs:
        cid = "|".join(f"{k}={c[k]}" for k in sorted(c))
        if cid not in seen:
            seen.add(cid); out.append(c)
    return out


if __name__ == "__main__":
    cfgs = expand()
    print(f"{len(cfgs)} configs")
    for c in cfgs[:8]:
        print(" ", c)
