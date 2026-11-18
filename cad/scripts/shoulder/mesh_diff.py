"""Geometric difference between two meshes of the same part: surface samples of each, distance to the other (chunked, light).
python mesh_diff.py A.STL B.STL [samples]. Prints the max and 99.9th percentile both ways, and every sample over 0.005 mm
grouped into boxes (where the geometry changed)."""
import sys

import numpy as np
import trimesh

RX, YZ = 170.49, 5.99


def one_way(a, b, n, chunk=20000):
    p, _ = trimesh.sample.sample_surface_even(a, n, seed=3)
    d = np.empty(len(p))
    for s in range(0, len(p), chunk):
        _, dist, _ = trimesh.proximity.closest_point(b, p[s:s + chunk])
        d[s:s + chunk] = dist
    return p, d


A, B = trimesh.load(sys.argv[1]), trimesh.load(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 400000
for name, (x, y) in (('A to B', (A, B)), ('B to A', (B, A))):
    p, d = one_way(x, y, n)
    print(f'{name}: {len(p)} samples, max {d.max():.4f} mm, 99.9% {np.percentile(d, 99.9):.4f}, 99% {np.percentile(d, 99):.4f}')
    big = d > 0.005
    if big.any():
        q = p[big]
        r = np.hypot(q[:, 0] - RX, q[:, 2] - YZ)
        th = np.degrees(np.arctan2(q[:, 2] - YZ, q[:, 0] - RX))
        for lab, m in (('theta near 0', np.abs(th) < 30), ('theta near 180', np.abs(np.abs(th) - 180) < 30), ('elsewhere', (np.abs(th) >= 30) & (np.abs(np.abs(th) - 180) >= 30))):
            if m.any():
                print(f'   {lab}: {m.sum()} samples over 0.005, max {d[big][m].max():.4f}; r {r[m].min():.2f}..{r[m].max():.2f}, '
                      f'Y {q[m,1].min():.2f}..{q[m,1].max():.2f}, Z-YZ {(q[m,2]-YZ).min():+.2f}..{(q[m,2]-YZ).max():+.2f}, theta {th[m].min():.1f}..{th[m].max():.1f}')
