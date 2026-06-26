"""Diagnose why owen_40x yields no score-passing anchor candidates."""
import sys
import numpy as np
import pandas as pd
import datasets as D
import cache as C

WF = "/lab/ops_analysis_ssd/test_matteo/brieflow-speed/brieflow/workflow"
if WF not in sys.path:
    sys.path.insert(0, WF)
from lib.merge.merge_utils import align_metadata, find_closest_tiles
from lib.merge.hash import evaluate_match

ds = D.load("owen_40x")
ph_meta = ds["ph_meta"].drop_duplicates("tile").copy()
sbs_meta = ds["sbs_meta"].drop_duplicates("tile").copy()
for m in (ph_meta, sbs_meta):
    for c in ("x_pos", "y_pos"):
        m[c] = m[c].astype(float)
ph_a, sb_a, _ = align_metadata(ph_meta, sbs_meta, x_col="x_pos", y_col="y_pos")

ph_h = C.hashed("owen_40x", "phenotype")
sbs_h = C.hashed("owen_40x", "sbs").rename(columns={"tile": "site"})
ph_info = ds["phenotype_info"]; sbs_info = ds["sbs_info"]

print(f"PH tiles {ph_a.tile.nunique()}, SBS tiles {sb_a.tile.nunique()}")
print("cells/PH-tile:", ph_info.groupby('tile').size().describe()[['min','25%','50%','max']].to_dict())
print("triangles/PH-tile:", ph_h.groupby('tile').size().describe()[['min','50%','max']].to_dict())

# for each SBS tile, nearest few PH tiles, evaluate_match at a few thresholds
for st in list(sb_a.tile)[:6]:
    c = find_closest_tiles(sb_a, ph_a, st, verbose=False).head(3)
    for _, row in c.iterrows():
        pt = int(row.tile)
        t0 = ph_h[ph_h.tile == pt]; s0 = sbs_h[sbs_h.site == st]
        npc = (ph_info.tile == pt).sum()
        line = f"SBS {st} <- PH {pt} (dist {row.distance:.0f}um, {npc} ph cells, {len(t0)} ph tris): "
        for tt in (0.3, 0.5, 0.7):
            R, t, sc = evaluate_match(t0, s0, threshold_triangle=tt, threshold_point=4)
            det = None if R is None else float(np.linalg.det(R))
            line += f"[tt={tt}: score={sc:.2f} det={det if det is None else round(det,4)}] "
        print(line)
