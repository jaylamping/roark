"""Thin-gap scan of exported parts: finds places where two faces of the same part face each other across a gap narrower
than GAP (0.8 mm), the kind left when two features meant to meet miss by a fraction of a millimetre (the hub top's
r 19.0-19.5 slits, 2026-11-15). Thin walls are not reported, only thin air.

    python gap_scan.py [STL ...]          (default: every STL in cad/exports/shoulder)

Method: the surface sampled at about 0.25 mm; for each sample, the samples within GAP whose normal is opposed (dot under
-0.7) and which lie in front of it (along its outward normal, by 0.05 mm or more, and within 0.3 mm sideways per mm).
Hits are grouped into clusters 2 mm apart; clusters under 3 mm2 are dropped (fillet run-outs and mesh noise).
"""
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from swk import CAD

GAP, STEP = 0.8, 0.25


def scan(path):
    m = trimesh.load(path)
    n_s = int(m.area / STEP ** 2)
    pts, fi = trimesh.sample.sample_surface(m, n_s, seed=3)
    nrm = m.face_normals[fi]
    tree = cKDTree(pts)
    hit = np.zeros(len(pts), bool)
    width = np.full(len(pts), np.nan)
    for i0 in range(0, len(pts), 50000):
        sl = slice(i0, min(i0 + 50000, len(pts)))
        nb = tree.query_ball_point(pts[sl], GAP)
        for j, lst in enumerate(nb):
            i = i0 + j
            if len(lst) < 2:
                continue
            lst = np.asarray(lst)
            d = pts[lst] - pts[i]
            along = d @ nrm[i]
            side = np.linalg.norm(d - np.outer(along, nrm[i]), axis=1)
            k = (nrm[lst] @ nrm[i] < -0.7) & (along > 0.05) & (side < 0.3 * along + 0.15)
            if k.any():
                hit[i] = True
                width[i] = along[k].min()
    out = []
    if hit.any():
        hp = pts[hit]
        lab = trimesh.grouping.clusters(hp, 2.0)
        for c in lab:
            area = len(c) * STEP ** 2 / 2          # both sides of a gap are hit
            if area < 3.0:
                continue
            q = hp[c]
            out.append(dict(area=round(area, 1), lo=q.min(axis=0).round(1).tolist(), hi=q.max(axis=0).round(1).tolist(),
                            width=(round(float(np.nanmin(width[hit][c])), 2), round(float(np.nanmedian(width[hit][c])), 2))))
    return m, sorted(out, key=lambda o: -o['area'])


if __name__ == '__main__':
    files = sys.argv[1:] or sorted(str(p) for p in (CAD / 'exports' / 'shoulder').glob('*.STL') if 'candidate' not in p.name and 'rev' not in p.name)
    for f in files:
        m, res = scan(f)
        print(f'== {f.split(chr(92))[-1].split("/")[-1]}: area {m.area:.0f} mm2, {len(res)} thin gaps under {GAP} mm', flush=True)
        for o in res[:25]:
            print(f"   {o['area']:7.1f} mm2  gap {o['width'][0]:.2f} min / {o['width'][1]:.2f} median   X {o['lo'][0]}..{o['hi'][0]}  Y {o['lo'][1]}..{o['hi'][1]}  Z {o['lo'][2]}..{o['hi'][2]}", flush=True)
