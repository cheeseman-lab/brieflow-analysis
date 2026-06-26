"""Auto-generate the cumulative merge explainer (markdown + self-contained HTML) from the
live sweep results + winner + full-well runs. Generated, not hand-written, so it can't drift.
"""
import base64
import json
import sys

import numpy as np
import pandas as pd

import datasets as D

RESULTS = D.MT_DIR / "results"
FIGDIR = D.MT_DIR / "figures" / "harness"
OUT_MD = D.MT_DIR / "merge_explainer.md"
OUT_HTML = D.MT_DIR / "merge_explainer.html"

# Lever inventory: name -> (file:line, default, what it controls). Now all config-exposed.
LEVERS = [
    ("det_range", "hash.py multistep_alignment", "dataset-derived", "scale gate = (ph_px/sbs_px)^2; per-dataset"),
    ("score", "hash.py / merge.smk", "0.1", "min fraction of triangle centers matched to accept a pair"),
    ("threshold_triangle", "hash.py:evaluate_match", "0.3", "max hash distance to call two triangles a match"),
    ("threshold_point", "hash.py:evaluate_match", "2", "px radius for scoring a matched triangle center"),
    ("threshold_region", "hash.py:evaluate_match", "50", "px region considered when scoring"),
    ("ransac_residual_threshold", "hash.py:evaluate_match RANSAC", "sklearn default", "RANSAC inlier tolerance for the affine fit"),
    ("threshold", "fast_merge.py:merge_sbs_phenotype", "2", "px match radius for cell-to-cell NN merge"),
    ("local_refinement", "fast_merge.py", "None", "enable degree-2 polynomial within-tile warp"),
    ("warp_degree", "fast_merge.py:refine_local_warp", "2", "polynomial degree of the local warp"),
    ("warp_iterations", "fast_merge.py:refine_local_warp", "2", "refine-and-rematch passes"),
    ("warp_min_correspondences", "fast_merge.py:refine_local_warp", "30", "min confident matches to fit the warp"),
]


def _load_results():
    frames = []
    for n in D.REGISTRY:
        p = RESULTS / f"{n}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sensitivity(df):
    """For each swept lever, the max spread in dataset_score it induces (per dataset, mean)."""
    rows = []
    for lever in ["threshold", "local_refinement", "threshold_triangle", "ransac_residual_threshold",
                  "warp_degree"]:
        col = f"cfg_{lever}"
        if col not in df.columns:
            continue
        spreads = []
        for ds, g in df.groupby("dataset"):
            if g[col].nunique(dropna=False) > 1:
                m = g.groupby(col, dropna=False).dataset_score.mean()
                spreads.append(m.max() - m.min())
        if spreads:
            rows.append((lever, round(float(np.mean(spreads)), 4), round(float(np.max(spreads)), 4)))
    return rows


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def build():
    df = _load_results()
    winner = json.loads((RESULTS / "winner.json").read_text()) if (RESULTS / "winner.json").exists() else None
    fulls = {n: json.loads((RESULTS / f"full_{n}.json").read_text())
             for n in D.REGISTRY if (RESULTS / f"full_{n}.json").exists()}

    md = ["# How the two-scope merge works — cumulative explainer\n",
          "_Auto-generated from the research sweep; do not edit by hand._\n",
          "## 1. The problem\n",
          "SBS and phenotype are imaged on different microscopes → a consistent ~1° rotation, a large "
          "magnification/pixel-size difference, and residual non-rigid within-tile distortion. The fast "
          "merge must recover a per-tile-pair transform robust to all three.\n",
          "## 2. The pipeline funnel\n",
          "Delaunay triangulate cell centroids per tile → **nine-edge hash** (scale/rotation-invariant) → "
          "match triangles across modalities by hash → **RANSAC affine** per (phenotype tile, SBS site) "
          "(`evaluate_match`) → **multistep_alignment** propagates from seed anchors to the whole well → "
          "**nearest-neighbour cell merge** within `threshold` (`merge_sbs_phenotype`) → optional "
          "**degree-2 polynomial warp** for residual distortion (`refine_local_warp`) → **dedup** to 1:1.\n"]

    # datasets table: baseline (no refinement, thr=4) vs generalized winner
    win_by_ds = {d["dataset"]: d["score"] for d in winner["per_dataset"]} if winner else {}
    no_refine = df[df.get("cfg_local_refinement").isna()] if "cfg_local_refinement" in df else df.iloc[0:0]
    rows = []
    for n in D.REGISTRY:
        ds = D.load(n)
        base = no_refine[no_refine.dataset == n]
        rows.append([n, D.REGISTRY[n]["optics"].split(",")[0],
                     int(ds["sbs_info"].tile.nunique()),
                     round(float(base.dataset_score.max()), 3) if len(base) else "—",
                     win_by_ds.get(n, "—")])
    md += ["## 3. Datasets\n",
           _md_table(["dataset", "optics", "SBS tiles", "score: baseline (thr4, no refine)", "score: winner"], rows),
           "\n"]

    # metric
    md += ["## 4. The 2px objective (segmentation-fair, bidirectional)\n",
           "Within the phenotype bounding box, the fraction of SBS cells matched to a phenotype cell "
           "within **2px** — and vice versa — counting a cell as a miss **only when a partner exists** "
           "(judged by a fixed reference alignment), so missing segmentation never counts as a merge "
           "error. A k×k worst-subcell term rewards spatial uniformity (no dead corners).\n"]

    # lever inventory + sensitivity
    md += ["## 5. Levers\n", _md_table(["lever", "location", "default", "controls"], LEVERS), "\n",
           "### Sensitivity (mean / max spread in dataset score across the lever's swept values)\n",
           _md_table(["lever", "mean spread", "max spread"], _sensitivity(df)) if len(df) else "(no results)", "\n"]

    # winner
    if winner:
        md += ["## 6. Generalized winner\n",
               f"`{winner['winner_config_id']}`  (worst-case ratio {winner['worst_ratio']})\n",
               _md_table(["dataset", "score", "dataset optimum", "generalization tax"],
                         [[d["dataset"], d["score"], d["optimum"], d["tax"]] for d in winner["per_dataset"]]),
               "\n"]
    # full-well
    if fulls:
        md += ["## 7. Full-well merge with the winner\n",
               _md_table(["dataset", "aligned pairs", "SBS rate %", "PH rate %", "median px", "<2px %"],
                         [[n, f["aligned_pairs"], f["sbs_rate_pct"], f["ph_rate_pct"],
                           f["median_dist_px"], f["frac_under_2px"]] for n, f in fulls.items()]), "\n"]

    md += ["## 8. Remaining levers to push\n",
           "- **Morphology (`area`) prior** in dedup tie-breaks (convert px²→µm² across pixel sizes).\n",
           "- **Sub-tile / piecewise hashing** for datasets where one affine per tile leaves edge residual.\n",
           "- **owen_40x coverage**: alignment is near-perfect where it lands (≈0.96) but only a subset of "
           "tiles align (sparse 40× confocal neurons) — the lever there is segmentation/anchoring, not merge.\n"]

    # validation scope (honest about which stages each dataset exercised)
    scope = []
    for n in D.REGISTRY:
        full = not D.REGISTRY[n].get("use_existing_alignment")
        scope.append([n, "✓" if full else "rides existing align", "✓", "✓"])
    md += ["## 9. Validation scope & caveats\n",
           _md_table(["dataset", "anchor + multistep derivation", "per-pair alignment levers", "merge + metric"], scope),
           "\n",
           "- Datasets marked *rides existing align* are too sparse to re-derive seeds per tile "
           "(owen_40x: ~47 cells/tile), so they reuse the production `fast_alignment` and only the "
           "merge/per-pair-lever half is exercised there.\n",
           "- **owen_40x metric (~0.96) is on its highest-confidence pairs** (favorable subset); the fair "
           "whole-well figure is its full-well rate (PH-side, since 40× neurons are sparse).\n",
           "- **One well per dataset**; held-out eval sets are modest (15–25 contained pairs). Generalization "
           "is shown across datasets, not yet across wells within a dataset.\n",
           "- **Dedup uses distance-only priors** (flat info parquets lack the gene/fov feature columns the "
           "production tie-breakers use) — affects same-distance ties, not matched counts.\n",
           "- The sweep selects levers **per-pair**; the full-well merge applies them via **multistep** "
           "propagation (small train/apply difference).\n"]

    OUT_MD.write_text("\n".join(md))

    # HTML with embedded harness figures
    try:
        import markdown
        body = markdown.markdown("\n".join(md), extensions=["tables", "fenced_code"])
    except Exception:
        body = "<pre>" + "\n".join(md) + "</pre>"
    audit = {}
    ap = FIGDIR / "audit.json"
    if ap.exists():
        audit = json.loads(ap.read_text())
    figs = ""
    for p in sorted(FIGDIR.glob("*.png")) if FIGDIR.exists() else []:
        b64 = base64.b64encode(p.read_bytes()).decode()
        aud = audit.get(p.name, {})
        cap = aud.get("caption", p.name)
        flags = aud.get("flags", [])
        flag_html = (f'<div class="flag">&#9888; AUDIT: {"; ".join(flags)}</div>' if flags else "")
        figs += (f'<figure><figcaption><b>{p.name}</b> — {cap}</figcaption>{flag_html}'
                 f'<img src="data:image/png;base64,{b64}"/></figure>')
    html = (f"<!doctype html><meta charset='utf-8'><title>Merge explainer</title>"
            f"<style>body{{font:15px/1.55 -apple-system,Segoe UI,Arial;max-width:1000px;margin:2rem auto;padding:0 1rem}}"
            f"table{{border-collapse:collapse}}th,td{{border:1px solid #ccc;padding:.3rem .6rem}}th{{background:#eef3f8}}"
            f"figure img{{width:100%}}figcaption{{color:#333;font-size:.9rem;margin-bottom:.3rem}}"
            f".flag{{color:#b00;font-size:.85rem;font-weight:bold;margin-bottom:.3rem}}</style>"
            f"{body}<h2>Figures (auto-captioned + audited)</h2>{figs}")
    OUT_HTML.write_text(html)
    print(f"wrote {OUT_MD} and {OUT_HTML} ({OUT_HTML.stat().st_size//1024} KB)")


if __name__ == "__main__":
    build()
