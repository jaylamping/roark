"""Clearance of our parts (closed halves, lug plates) to a hub's R1.2 Z-root fillets and lug-root zone (2026-11-13, D3c4 check 3).
Distances from our surface samples (zone X offset 17-27, Y 292-298.5, |Z - CZ| < 9) to the hub surface, signed by the closest
face's outward normal, in the fillet zone X offset 18-27, Y 294-296.5, |Z - CZ| 4.9-9. The plates' own contact face on the lug
(|Z - CZ| within 0.02 of 5.0, contact by design) is left out. Prints the minimum per part and where, for each hub given.
    python root_clearance.py HALVES_DIR PLATES_STL HUB_STL [HUB_STL ...]      (under capped.py)"""
import sys

import numpy as np
import trimesh

HX, CZ = 170.49, 5.985875
X, platesp = sys.argv[1], sys.argv[2]
parts = {n: trimesh.load(f'{X}/upper_arm_organic_{n}_left.STL') for n in ('front', 'back')}
parts['plates'] = trimesh.load(platesp)
samples = {}
for n, m in parts.items():
    pts, _ = trimesh.sample.sample_surface_even(m, 600000)
    pts = np.vstack([pts, m.vertices])
    dz = np.abs(pts[:, 2] - CZ)
    z = (np.abs(np.abs(pts[:, 0] - HX) - 22.5) < 4.5) & (pts[:, 1] > 294.0) & (pts[:, 1] < 296.5) & (dz > 4.9) & (dz < 9.0)
    if n == 'plates':
        z &= np.abs(dz - 5.0) > 0.02
    samples[n] = pts[z]
for hp in sys.argv[3:]:
    hub = trimesh.load(hp)
    pq = trimesh.proximity.ProximityQuery(hub)
    print(f'== {hp.split("/")[-1]}')
    for n, pts in samples.items():
        d = np.empty(len(pts)); keep = np.zeros(len(pts), bool); sgn = np.ones(len(pts))
        for i in range(0, len(pts), 20000):
            cp, dd, tid = pq.on_surface(pts[i:i + 20000])
            nrm = hub.face_normals[tid]
            d[i:i + 20000] = dd
            sgn[i:i + 20000] = np.where(np.einsum('ij,ij->i', pts[i:i + 20000] - cp, nrm) < -1e-6, -1.0, 1.0)
            keep[i:i + 20000] = True
        ds = (d * sgn)[keep]
        q = pts[keep]
        if not len(q):
            print(f'   {n}: no points'); continue
        k = int(np.argmin(ds))
        p = q[k]
        print(f'   {n:6s}: min {ds[k]:+.3f} mm at X {p[0]:.2f} Y {p[1]:.2f} Z {p[2]:.2f} (X offset {abs(p[0] - HX):.2f}, Z - CZ {p[2] - CZ:+.2f}); '
              f'points under 0.30: {int((ds < 0.3).sum())}, under 0.10: {int((ds < 0.1).sum())} of {len(ds)}')
