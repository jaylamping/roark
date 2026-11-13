"""Hub D3c4 candidate against R1g / r1g4 (2026-11-13): watertightness and mass; section diff D3b vs D3c4 (where the hub changed);
clearance of D3c4 to our closed halves and to the r1g4 lug plates (with lips) in the lug-root zone; our material inside r 22 at
Y 296-298 (the r 20 bore fill); the as-built cable window slot at theta 248 against our halves, and whether the old window at
theta about 8 is closed. Theta (ours = the hub's): atan2(Z - CZ, X - HX), 0 = +X, + toward +Z (front).
    python d3c4_check.py D3C4_STL D3B_STL HALVES_DIR PLATES_STL OUT_JSON      (under capped.py)"""
import json
import sys

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
c4p, d3bp, X, platesp, OUT = sys.argv[1:6]
c4, d3b = trimesh.load(c4p), trimesh.load(d3bp)
halves = {n: trimesh.load(f'{X}/upper_arm_organic_{n}_left.STL') for n in ('front', 'back')}
plates = trimesh.load(platesp)
res = {}


def sec(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return g.buffer(0)


def th(x, z):
    return float(np.degrees(np.arctan2(z - CZ, x - HX)) % 360)


# 1 watertight and mass (PETG 1.27 g/cm3 as the shoulder thread)
res['1'] = dict(watertight=bool(c4.is_watertight), volume_mm3=round(float(c4.volume), 1), mass_g_petg127=round(float(c4.volume) * 1.27e-3, 1),
                bounds=np.round(c4.bounds, 2).tolist())
# 2 section diff D3b vs D3c4
diff = []
for y in np.round(np.arange(286.0, 321.0, 0.1), 2):
    a, b = sec(d3b, y), sec(c4, y)
    dd = a.symmetric_difference(b)
    for p in (dd.geoms if hasattr(dd, 'geoms') else [dd]):
        if p.is_empty or p.area < 0.05:
            continue
        c = np.array(p.exterior.coords)
        r = np.hypot(c[:, 0] - HX, c[:, 1] - CZ)
        xo = np.abs(c[:, 0] - HX)
        added = b.intersection(p).area > a.intersection(p).area
        diff.append(dict(y=float(y), area=round(p.area, 2), kind='added in D3c4' if added else 'removed in D3c4',
                         r=[round(float(r.min()), 2), round(float(r.max()), 2)], xoff=[round(float(xo.min()), 2), round(float(xo.max()), 2)],
                         theta=round(th(p.centroid.x, p.centroid.y), 1), z=[round(float(c[:, 1].min()), 2), round(float(c[:, 1].max()), 2)]))
res['2_diff_pieces'] = diff
lo = [d for d in diff if d['y'] < 296.0]
arm = [d for d in diff if 296.0 <= d['y'] <= 302.3 and d['r'][1] > 23.5]      # arm-facing: spigot / groove / land / disc (r > 23.5)
res['2_summary'] = dict(
    below_Y296=dict(n=len(lo), y=[min(d['y'] for d in lo), max(d['y'] for d in lo)] if lo else None,
                    r=[min(d['r'][0] for d in lo), max(d['r'][1] for d in lo)] if lo else None,
                    xoff=[min(d['xoff'][0] for d in lo), max(d['xoff'][1] for d in lo)] if lo else None,
                    kinds=sorted({d['kind'] for d in lo})),
    arm_facing_Y296_302p3_r_over_23p5=dict(n=len(arm), pieces=arm[:20]),
    above_Y302p3=dict(n=len([d for d in diff if d['y'] > 302.3])))
# 3 clearance in the lug-root zone: hub D3c4 against our halves and the plates, by closest point (sampled surfaces)
zone = lambda P: (np.abs(np.abs(P[:, 0] - HX) - 22.0) < 5.0) & (P[:, 1] > 292.0) & (P[:, 1] < 298.5) & (np.abs(P[:, 2] - CZ) < 9.0)
pq = trimesh.proximity.ProximityQuery(c4)
for nm, m in list(halves.items()) + [('plates', plates)]:
    pts, _ = trimesh.sample.sample_surface_even(m, 400000)
    pts = np.vstack([pts, m.vertices])
    pts = pts[zone(pts)]
    if not len(pts):
        res[f'3_{nm}'] = 'no points in the zone'
        continue
    d = np.full(len(pts), np.inf)
    inside = np.zeros(len(pts), bool)
    for i in range(0, len(pts), 20000):      # signed by the closest face's outward normal (no ray casting: too heavy here)
        cp, d[i:i + 20000], tid = pq.on_surface(pts[i:i + 20000])
        inside[i:i + 20000] = np.einsum('ij,ij->i', pts[i:i + 20000] - cp, c4.face_normals[tid]) < -1e-6
    d = np.where(inside, -d, d)
    k = int(np.argmin(d))
    q = pts[k]
    res[f'3_{nm}'] = dict(points=int(len(pts)), min_clearance=round(float(d[k]), 3), at=np.round(q, 2).tolist(),
                          xoff=round(float(abs(q[0] - HX)), 2), dz=round(float(q[2] - CZ), 2), n_under_0p3=int((d < 0.3).sum()))
# 6 our material inside r 22 at Y 296-298 and the smallest hub-to-ours gap there
r6 = []
for y in np.round(np.arange(296.0, 298.01, 0.1), 2):
    ours = unary_union([sec(m, y) for m in halves.values()])
    inner = ours.intersection(Point(HX, CZ).buffer(22.0, 256)).area
    gap = sec(c4, y).distance(ours) if not ours.is_empty else None
    r6.append((float(y), round(inner, 3), None if gap is None else round(gap, 3)))
res['6'] = dict(ours_inside_r22_max_mm2=max(a for _, a, _ in r6), hub_to_ours_min_gap=min(g for _, _, g in r6 if g is not None))
# 5 the as-built window slot at 248: centre line (r 15.5, Y 298) -> (r 31, Y 320.4), 9 radial, +-8 across, against our halves
t = np.radians(248.0)
er, et = np.array([np.cos(t), np.sin(t)]), np.array([-np.sin(t), np.cos(t)])
w5 = []
for y in np.round(np.arange(298.0, 320.41, 0.2), 2):
    rc = 15.5 + (31.0 - 15.5) * (y - 298.0) / (320.4 - 298.0)
    c = np.array([HX, CZ])
    slot = Polygon([c + (rc - 4.5) * er - 8 * et, c + (rc + 4.5) * er - 8 * et, c + (rc + 4.5) * er + 8 * et, c + (rc - 4.5) * er + 8 * et])
    for n, m in halves.items():
        g = sec(m, y)
        if not g.is_empty:
            w5.append((float(y), n, round(slot.distance(g), 3), round(slot.intersection(g).area, 3)))
# also: is the slot open in D3c4 (material-free) and the old window at 8 closed? sample at r 15.5, Y 300-312
occ = {}
for y in (300.0, 302.0, 306.0, 310.0):
    g = sec(c4, y)
    occ[y] = {a: bool(g.contains(Point(HX + 15.5 * np.cos(np.radians(a)), CZ + 15.5 * np.sin(np.radians(a))))) for a in (0, 8, 20, 248, 330, 350)}
res['5'] = dict(slot_vs_ours_min_distance=min((d for _, _, d, _ in w5), default=None),
                slot_vs_ours_overlap_mm2=max((a for _, _, _, a in w5), default=0.0),
                our_sections_in_slot_span=len(w5), hub_material_at_r15p5=occ)
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != '2_diff_pieces'}, indent=1))
