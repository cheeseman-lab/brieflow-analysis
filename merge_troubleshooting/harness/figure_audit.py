"""Deterministic figure auditor: encode what each figure SHOULD depict as checks that run
on every regeneration, so visual artifacts (partial-tile coverage, density blur, scale
split, unrelated frames) self-surface instead of relying on eyeballing.

Each figure function computes a metrics dict and calls evaluate(kind, metrics) -> flags.
gen_figures collects {figure: {metrics, flags, caption}} into audit.json; report.py uses it.
"""

# rule: (metric_key, predicate(value) -> bad?, message)
RULES = {
    "matching": [
        ("n_in_view", lambda v: v > 250, "illegible: >250 cells in window (shrink win)"),
        ("matched_frac", lambda v: v < 0.5, "low in-window match rate (<50%)"),
    ],
    "pooled_merge": [
        ("coverage", lambda v: v < 0.6, "PARTIAL tile coverage <60% — not a fully merged tile"),
        ("empty_frac", lambda v: v > 0.4, "large empty region (>40%) — check alignment/coverage"),
        ("matched_frac", lambda v: v < 0.5, "low matched fraction in covered region (<50%)"),
    ],
    "tile_grid": [
        ("frame_overlap", lambda v: v < 0.1, "PH/SBS stage frames barely overlap — unrelated coords"),
    ],
    "alignment_quality": [
        ("n_points", lambda v: v < 5, "<5 alignment points plotted"),
        ("det_cv", lambda v: v > 0.15, "determinant spread >15% — inconsistent scale"),
    ],
}

CAPTIONS = {
    "matching": "Zoomed cell overlay (green=SBS, red=mapped PH); affine vs tuned. {matched_frac:.0%} matched <2px in window.",
    "pooled_merge": "Full SBS tile merged from ALL {n_ph_tiles} overlapping phenotype tiles (what the well-level pipeline does). Coverage {coverage:.0%}, {matched_frac:.0%} of covered SBS matched <2px.",
    "tile_grid": "PH/SBS tile-position grid (conventional). Stage-frame overlap {frame_overlap:.0%}.",
    "alignment_quality": "Per-pair determinant vs score (conventional). {n_points} pairs, det CV {det_cv:.1%}.",
}


def evaluate(kind, m):
    flags = [msg for key, bad, msg in RULES.get(kind, []) if key in m and bad(m[key])]
    try:
        caption = CAPTIONS.get(kind, "").format(**m)
    except (KeyError, ValueError):
        caption = CAPTIONS.get(kind, "")
    return {"metrics": m, "flags": flags, "caption": caption}
