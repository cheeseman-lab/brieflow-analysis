"""Build a self-contained HTML report from README.md (rendered) + an embedded figure
gallery. Renders the README directly so the report can never drift from the doc.
Run from anywhere; paths are resolved relative to this file."""
import base64, pathlib, markdown

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FIG = ROOT / "figures"
OUT = ROOT / "report.html"

# captions for the gallery (filename -> caption); order here = order in the report.
CAPTIONS = {
    "01_tile_grid_raw.png": "Tile grid, raw stage coords — PH (white) / SBS (red) offset ~645 µm between the two scopes. A cosmetic origin difference, NOT the merge problem.",
    "02_tile_grid_centeraligned.png": "Same grid after METADATA_ALIGN (center, no flips): the two scopes overlap. This is the only location alignment the two-scope data needs.",
    "03_alignment_quality.png": "Per-tile-pair determinant after fixing det_range to [0.065,0.080]: all 11 test pairs pass gating (the default range was ~16x off and rejected everything).",
    "zoom_pooled_tile280.png": "Cell-level overlay, SBS tile 280, pooling ALL overlapping PH tiles + refinement (= what the well-level pipeline does). Red PH dots land inside green SBS circles, center AND edge — the merge is accurate wherever both modalities have cells.",
    "zoom_pooled_tile168.png": "Cell-level overlay, SBS tile 168 (pooled + refine). ~97% of in-overlap SBS cells matched; the unmatched are where one modality has no segmented cell (coverage gap), not misalignment.",
    "ba_sbs280_worst_thr2.png": "Before/after local_refinement at tight threshold=2, SBS tile 280. Orange = cells recovered by the augmentation (the edge distortion band). +11.6 pp.",
    "ba_sbs140_median_thr2.png": "Before/after local_refinement at threshold=2, SBS tile 140. +5.7 pp; recovered cells again concentrate where within-tile distortion is largest.",
}

def embed(name):
    b64 = base64.b64encode((FIG / name).read_bytes()).decode()
    cap = CAPTIONS.get(name, name)
    return (f'<figure><img src="data:image/png;base64,{b64}"/>'
            f'<figcaption><b>{name}</b> — {cap}</figcaption></figure>')

body_html = markdown.markdown(
    (ROOT / "README.md").read_text(),
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)

# gallery: ordered (known captions first, then any extras), all embedded
ordered = [f for f in CAPTIONS if (FIG / f).exists()]
extras = sorted(f.name for f in FIG.glob("*.png") if f.name not in CAPTIONS)
gallery = "\n".join(embed(f) for f in ordered + extras)

HTML = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Merge troubleshooting — Vaishnavi multi-scope</title>
<style>
body{{font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:1100px;
margin:2rem auto;padding:0 1.2rem;color:#1a1a1a}}
h1{{font-size:1.7rem;border-bottom:2px solid #ddd;padding-bottom:.4rem}}
h2{{font-size:1.3rem;margin-top:2rem;color:#0b3d66;border-bottom:1px solid #eee;padding-bottom:.2rem}}
h3{{font-size:1.1rem;margin-top:1.4rem;color:#11507a}}
table{{border-collapse:collapse;margin:1rem 0;font-size:.92rem}}
th,td{{border:1px solid #cdd6df;padding:.35rem .6rem;text-align:left}}
th{{background:#eef3f8}}
pre{{background:#0f1722;color:#e6edf3;padding:1rem;border-radius:8px;overflow-x:auto;font-size:.85rem}}
code{{background:#eef1f4;padding:.1rem .3rem;border-radius:3px}}
pre code{{background:none;padding:0}}
figure{{margin:1.2rem 0;border:1px solid #e2e2e2;border-radius:8px;padding:.6rem;background:#fafafa}}
figure img{{width:100%;height:auto;border-radius:4px}}
figcaption{{font-size:.88rem;color:#444;margin-top:.5rem}}
</style></head><body>
{body_html}
<h2>Figures</h2>
{gallery}
</body></html>"""

OUT.write_text(HTML)
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)  with {len(ordered)+len(extras)} figures")
