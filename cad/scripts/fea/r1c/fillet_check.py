"""Hub lug-root fillet check (2026-11-12): compare the filleted hub (bc16e97) with 556cc44 by plane sections only (no point-in-mesh
over whole meshes), find where the two differ, and measure the clearance from our lug slot (post faces at |Z - CZ| = 5.1 up to the
floor at Y 295.7, with the ARM_SLOT_BREAK chamfer a x b along given X spans) to the new hub surface.
    python fillet_check.py NEW_STL OLD_STL a b x0,x1 x0,x1      (run under capped.py)"""
import json
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

CZ = 5.985875
FACE, TOP = 5.1, 295.7


def section(m, origin, normal):
    """Section polygons in FIXED axes (X plane -> (Y, Z), Y plane -> (X, Z)), so two meshes' sections line up (Path3D.to_2D picks
    its own frame per section)."""
    from shapely.geometry import Polygon
    from shapely.ops import polygonize
    sec = m.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None, None
    cols = (1, 2) if abs(normal[0]) > 0.5 else (0, 2)
    lines = [sec.vertices[e.points][:, cols] for e in sec.entities]
    from shapely.geometry import LineString
    polys = list(polygonize([LineString(l) for l in lines if len(l) > 1]))
    if not polys:
        return None, None
    # even-odd fill: XOR of all closed rings
    g = polys[0]
    for q in polys[1:]:
        g = g.symmetric_difference(q)
    return g, None


def xsec_points(m, x):
    """Section of the mesh at X = x, returned as (z_rel, y) polylines in mm."""
    sec = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    if sec is None:
        return np.zeros((0, 2))
    pts = []
    for ent in sec.entities:
        v = sec.vertices[ent.points]
        # densify each segment so distances are measured to the surface, not just its vertices
        for p0, p1 in zip(v[:-1], v[1:]):
            n = max(2, int(np.linalg.norm(p1 - p0) / 0.02))
            pts.append(np.linspace(p0, p1, n))
    if not pts:
        return np.zeros((0, 2))
    q = np.vstack(pts)
    return np.c_[q[:, 2] - CZ, q[:, 1]]


def arm_clear(zy, a, b, broken):
    """Distance from hub-surface points (z_rel, y) to our post solid (|z| >= 5.1, y <= 295.7, minus the chamfer if broken).
    Positive = clearance, negative = inside the post."""
    z = np.abs(zy[:, 0]); y = zy[:, 1]
    out = np.full(len(zy), np.inf)
    # post solid region in (u = |z| - FACE >= 0, v = TOP - y >= 0); chamfer removes v < a * (1 - u / b) for u < b
    u, v = z - FACE, TOP - y
    inside = (u >= 0) & (v >= 0)
    if broken:
        inside &= ~((u < b) & (v < a * (1 - u / b)))
    # distance to the region boundary, by dense sampling of the boundary
    s = np.linspace(0, 6, 1201)
    edges = [np.c_[np.zeros_like(s) + 0, a + s] if broken else np.c_[np.zeros_like(s), s],           # face (u = 0)
             np.c_[b + s, np.zeros_like(s)] if broken else np.c_[s, np.zeros_like(s)]]                # top (v = 0)
    if broken:
        t = np.linspace(0, 1, 401)
        edges.append(np.c_[b * t, a * (1 - t)])                                                       # chamfer
    bnd = np.vstack(edges)
    from scipy.spatial import cKDTree
    d = cKDTree(bnd).query(np.c_[u, v])[0]
    return np.where(inside, -d, d)


if __name__ == '__main__':
    new, old = trimesh.load(sys.argv[1]), trimesh.load(sys.argv[2])
    a, b = float(sys.argv[3]), float(sys.argv[4])
    spans = [tuple(float(t) for t in s.split(',')) for s in sys.argv[5:7]]
    res = {}
    # 1) where do the meshes differ? sections at X planes across the hub, symmetric difference area per X
    diffs = []
    for x in np.arange(132.5, 209.5, 0.5):
        pn, _ = section(new, [x, 0, 0], [1, 0, 0]); po, _ = section(old, [x, 0, 0], [1, 0, 0])
        if pn is None or po is None:
            continue
        dd = pn.symmetric_difference(po)
        if dd.area > 0.01:
            bx = dd.bounds
            diffs.append((round(float(x), 1), round(dd.area, 3)))
    res['x_sections_with_difference (x, mm2)'] = diffs
    # 2) Y-plane sections: where in Y does the new mesh differ?
    ydiff = []
    for y in np.arange(288.25, 320.0, 0.25):
        pn, _ = section(new, [0, y, 0], [0, 1, 0]); po, _ = section(old, [0, y, 0], [0, 1, 0])
        if pn is None or po is None:
            continue
        dd = pn.symmetric_difference(po)
        if dd.area > 0.01:
            ydiff.append((round(float(y), 2), round(dd.area, 3)))
    res['y_sections_with_difference (y, mm2)'] = ydiff
    # 3) the fillet's X extent and our clearance along X, at both Z sides, with and without the break
    rows = []
    for x in np.arange(136.0, 205.0, 0.25):
        zy = xsec_points(new, x)
        if not len(zy):
            continue
        near = (np.abs(zy[:, 0]) > 5.001) & (np.abs(zy[:, 0]) < 6.5) & (zy[:, 1] > 294.79) & (zy[:, 1] < 296.0)      # the fillet surface (above its tangent line at Y 294.8; the flat lug face is |Z| 5.000)
        if not near.any():
            continue
        in_span = any(s0 <= x <= s1 for s0, s1 in spans)
        for side in (1, -1):
            k = near & (np.sign(zy[:, 0]) == side)
            if not k.any():
                continue
            c = arm_clear(zy[k], a, b, in_span)
            c0 = arm_clear(zy[k], a, b, False)
            rows.append(dict(x=round(float(x), 2), side='+Z (front)' if side > 0 else '-Z (back)', broken=in_span,
                             clearance=round(float(c.min()), 3), clearance_unbroken=round(float(c0.min()), 3)))
    res['clearance_rows'] = len(rows)
    worst = sorted(rows, key=lambda r: r['clearance'])[:12]
    res['worst'] = worst
    need = [r for r in rows if r['clearance_unbroken'] < 0.2]
    res['x_where_break_needed'] = [min(r['x'] for r in need), max(r['x'] for r in need)] if need else None
    for lo, hi, nm in ((136, 170, '-X'), (170, 205, '+X')):
        q = [r['x'] for r in need if lo <= r['x'] < hi]
        res[f'break_needed_{nm}'] = [min(q), max(q)] if q else None
    per = {}
    for r_ in rows:
        k_ = ('-X' if r_['x'] < 170 else '+X') + ' ' + r_['side']
        if r_['broken'] or r_['clearance_unbroken'] < 0.3:
            per.setdefault(k_, []).append(r_)
    res['per_lug_side'] = {k_: dict(x_span=[min(q['x'] for q in v), max(q['x'] for q in v)], min_clearance=min(q['clearance'] for q in v),
                                    at_x=min(v, key=lambda q: q['clearance'])['x'], ends=[v[0]['clearance'], v[-1]['clearance']]) for k_, v in per.items()}
    fs = [(140.25, 148.5), (192.5, 200.75)]      # the fillet's X spans (from the section difference above)
    res['fillet_span_min'] = {('-X' if lo < 170 else '+X') + ' ' + sd: min((q['clearance'] for q in rows if lo <= q['x'] <= hi and q['side'] == sd), default=None)
                              for lo, hi in fs for sd in ('+Z (front)', '-Z (back)')}
    print(json.dumps(res, indent=1))
