"""Free space around the hub lugs inside our arm (2026-11-12, shoulder thread question): Y-plane sections of both printed halves
(and the hub, for the lugs themselves) from Y 280 to 296, and per section where our material is near each lug: the smallest r of
arm material within each lug's angular window, arm material inside r 20, and our parts between the lug's outer end and the bore.
    python lug_envelope.py FRONT_STL BACK_STL HUB_STL      (run under capped.py)"""
import json
import sys

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely.geometry import LineString

HX, CZ = 170.49, 5.985875


def ysec(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return None
    lines = [LineString(s.vertices[e.points][:, [0, 2]]) for e in s.entities if len(e.points) > 1]
    polys = list(polygonize(lines))
    if not polys:
        return None
    g = polys[0]
    for q in polys[1:]:
        g = g.symmetric_difference(q)
    return g


def r_theta_samples(g, step=0.1):
    if g is None or g.is_empty:
        return np.zeros((0, 2))
    x0, z0, x1, z1 = g.bounds
    X, Z = np.meshgrid(np.arange(x0, x1, step), np.arange(z0, z1, step))
    pts = np.c_[X.ravel(), Z.ravel()]
    from shapely import contains_xy
    k = contains_xy(g, pts[:, 0], pts[:, 1])
    p = pts[k]
    r = np.hypot(p[:, 0] - HX, p[:, 1] - CZ)
    th = np.degrees(np.arctan2(p[:, 1] - CZ, p[:, 0] - HX)) % 360
    return np.c_[r, th, p]


arm = [trimesh.load(f) for f in sys.argv[1:3]]
hub = trimesh.load(sys.argv[3])
rows = []
for y in np.arange(280.0, 296.01, 0.5):
    ga = unary_union([g for g in (ysec(m, y) for m in arm) if g is not None])
    gh = ysec(hub, y)
    a = r_theta_samples(ga)
    h = r_theta_samples(gh)
    row = dict(Y=round(float(y), 2))
    for name, th0 in (('-X lug (theta 180)', 180.0), ('+X lug (theta 0)', 0.0)):
        dth = np.abs((a[:, 1] - th0 + 180) % 360 - 180) if len(a) else np.zeros(0)
        hth = np.abs((h[:, 1] - th0 + 180) % 360 - 180) if len(h) else np.zeros(0)
        lug = h[(hth < 25)] if len(h) else h
        row[name] = dict(
            lug_r=[round(float(lug[:, 0].min()), 2), round(float(lug[:, 0].max()), 2)] if len(lug) else None,
            arm_min_r_within_25deg=round(float(a[dth < 25, 0].min()), 2) if (dth < 25).any() else None,
            arm_min_r_within_10deg=round(float(a[dth < 10, 0].min()), 2) if (dth < 10).any() else None)
    row['arm_inside_r20'] = int((a[:, 0] < 20.0).sum()) if len(a) else 0
    row['arm_min_r_anywhere'] = round(float(a[:, 0].min()), 2) if len(a) else None
    rows.append(row)
print(json.dumps(rows, indent=0))
