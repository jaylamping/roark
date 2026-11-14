"""Hub screw tubes: is every one whole?  python hub_tube_check.py HUB.STL

For each of the six boss tubes (r 12 about the yaw axis, 38 + 60k deg): the smallest wall round the screw hole in each 2 mm
of height, and how much of the head's seat ring at the tube's lower end (Y 298.1, hole edge to r 4.4) is there.
Fails (exit 1) if any wall is under 1.2 mm or any seat under 95 % of its ring. Written after the cable window was found to
cut the two tubes beside it (CAD_NOTES.md, "Hub cable window against the boss tubes").
"""
import math
import sys

import numpy as np
import trimesh

RX, YZ = 170.49, 5.99
m = trimesh.load(sys.argv[1])
p, fi = trimesh.sample.sample_surface_even(m, 1200000, seed=1)
n = m.face_normals[fi]
c, fn, fa = m.triangles_center, m.face_normals, m.area_faces
bad = False
for a in (38, 98, 158, -142, -82, -22):
    t = math.radians(a)
    ax = np.array([RX + 12 * math.cos(t), YZ + 12 * math.sin(t)])
    v = p[:, [0, 2]] - ax
    rad = np.hypot(v[:, 0], v[:, 1])
    outward = (n[:, 0] * v[:, 0] + n[:, 2] * v[:, 1]) / np.maximum(rad, 1e-9) > 0.3
    walls = []
    for y0 in np.arange(298.2, 312.0, 2.0):
        s = outward & (rad < 5.6) & (rad > 2.0) & (p[:, 1] >= y0) & (p[:, 1] < y0 + 2)
        h = (~outward) & (rad < 2.6) & (p[:, 1] >= y0) & (p[:, 1] < y0 + 2)
        if s.any() and h.any():
            walls.append(float(rad[s].min() - np.median(rad[h])))
    # seat ring: downward-facing flat faces at the tube's lower end
    d = np.hypot(c[:, 0] - ax[0], c[:, 2] - ax[1])
    hole_r = float(np.median(rad[(~outward) & (rad < 2.6) & (p[:, 1] < 302)]))
    seat = (fn[:, 1] < -0.99) & (np.abs(c[:, 1] - 298.1) < 0.3) & (d < 4.45)
    area = float(fa[seat].sum())
    full = math.pi * (4.4 ** 2 - hole_r ** 2)
    wmin = min(walls) if walls else float('nan')
    ok = wmin >= 1.2 and area >= 0.95 * full
    bad |= not ok
    print(f'tube {a:5d} deg: hole r {hole_r:.2f}; smallest wall {wmin:.2f} mm (by height: {" ".join(f"{w:.2f}" for w in walls)}); '
          f'seat ring {area:.1f} of {full:.1f} mm2 ({area / full * 100:.0f}%)  {"OK" if ok else "FAIL"}')
sys.exit(1 if bad else 0)
