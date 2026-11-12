"""End-face bearing on the hub disc (2026-11-12): sigma y (normal to the Y 302 face) at the nodes on the end face, both sides of
the contact, from the solver .npz. Interior band r 36.45-37.55 (the face runs r 36.4-37.6 after the 0.5 chamfer) for the mean and
peak; the inner-edge corner (r 36.35-36.45) separately. Compression is negative. Against PETG 45 MPa (the model's yield).
    python endface_pressure.py NPZ [NPZ...]      (run under capped.py)"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
out = {}
for f in sys.argv[1:]:
    d = np.load(f)
    p, s = d['pos'], d['s']
    r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ)
    on = np.abs(p[:, 1] - 302.0) < 0.03
    band = on & (r > 36.45) & (r < 37.55)
    edge = on & (r >= 36.35) & (r <= 36.45)
    sy = s[:, 2]
    th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
    row = {}
    if band.any():
        q = np.flatnonzero(band)
        i = q[np.argmin(sy[q])]
        row['band_nodes'] = int(len(q))
        row['mean_sigma_y_MPa'] = round(float(sy[q].mean()), 2)
        row['mean_compressive_only_MPa'] = round(float(sy[q][sy[q] < 0].mean()), 2) if (sy[q] < 0).any() else None
        row['peak_compression_MPa'] = round(float(sy[i]), 2)
        row['peak_at'] = p[i].round(2).tolist() + [round(float(th[i]), 1)]
        tr = cKDTree(p[q])
        for rr in (0.5, 1.0):
            worst = min(float(sy[q][tr.query_ball_point(p[j], rr)].mean()) for j in q[np.argsort(sy[q])[:300]])
            row[f'worst_avg_{rr}mm_MPa'] = round(worst, 2)
            row[f'sf_avg_{rr}mm'] = round(45.0 / abs(worst), 2) if worst < 0 else None
        row['sf_peak'] = round(45.0 / abs(sy[i]), 2) if sy[i] < 0 else None
    if edge.any():
        q = np.flatnonzero(edge)
        i = q[np.argmin(sy[q])]
        row['inner_edge_peak_compression_MPa'] = round(float(sy[i]), 2)
        row['inner_edge_at'] = p[i].round(2).tolist() + [round(float(th[i]), 1)]
    out[f.replace('\\', '/').split('/')[-2]] = row
print(json.dumps(out, indent=1))
