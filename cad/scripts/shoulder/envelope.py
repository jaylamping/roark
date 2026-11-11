"""Smooth outer outlines that swallow the cable ducts (Joey, 2026-11-11: nothing may stand proud of the skin).

drum_section(z): the drum's outline at Z = z, about the roll axis: the convex hull of the crown circle and every cable duct
that is active at that Z (trunk along the neck top, the down-run, the branch to the RS03 top bay), each with a small margin.
Sampled at fixed roll angles, so every loft section has matching points (no twist), and the cap reuses the same section.

bell_section(x): the pitch adaptor's outline at X = x, about the pitch axis: an egg, full on top where the trunk runs, and
held inside the drum's Z span at the sides.
"""
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from dims import *

N_ANG = 72
MARGIN = 0.6


def crown(z):
    zs, rs = zip(*DRUM_CROWN)
    return float(np.interp(z, zs, rs))


def _rect(c, u, w, h):
    c, u = np.array(c, float), np.array(u, float)
    u /= np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    return Polygon([tuple(c + su * u * w / 2 + sv * v * h / 2) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


def ducts():
    """(polygon in XY, z_lo, z_hi) of the duct shells that must lie inside the drum outline."""
    tu = np.array(TU[:2]) / np.linalg.norm(TU[:2])
    out = []
    # (trunk A runs inside the bell, which is its own outline)
    # down-run (trunk B) at TRUNK_X
    out.append((_rect((TRUNK_X, TRUNK_Y), tu, SHW, SHH), DRUM_Z0, TRUNK_B_ZTOP))
    # branch into the RS03 top bay
    b0, b1 = np.array([TRUNK_X, TRUNK_Y]), np.array(BRANCH_END)
    dvec = (b1 - b0) / np.linalg.norm(b1 - b0)
    a, b = b0 - dvec * (2 + WALL), b1 + dvec * (2 + WALL)
    out.append((_rect((a + b) / 2, dvec, np.linalg.norm(b - a), SHH), DRUM_Z0, -17.0 + SHW / 2))
    return out


def drum_section(z, scale=1.0):
    shapes = [Point(RX, RY).buffer(crown(z), 256)]
    for poly, z0, z1 in ducts():
        if z0 - 0.01 <= z <= z1 + 1.5:
            shapes.append(poly.buffer(MARGIN, join_style=1))
    hull = unary_union(shapes).convex_hull
    pts = []
    for k in range(N_ANG):
        t = 2 * math.pi * k / N_ANG
        far = (RX + 200 * math.cos(t), RY + 200 * math.sin(t))
        hit = LineString([(RX, RY), far]).intersection(hull.exterior)
        geoms = getattr(hit, 'geoms', [hit])
        r = max(math.hypot(g.x - RX, g.y - RY) for g in geoms if g.geom_type == 'Point')
        pts.append((RX + scale * r * math.cos(t), RY + scale * r * math.sin(t)))
    return pts


def bell_section(x, inset=0.0):
    """Egg about the pitch axis: top a_top, bottom a_bot (held clear of the fork and RS02 swing), Z half-widths front/rear."""
    b = BELL
    pts = []
    for k in range(N_ANG):
        t = 2 * math.pi * k / N_ANG              # psi from +Y toward +Z
        c, s = math.cos(t), math.sin(t)
        a = (b['top'] if c >= 0 else b['bot']) - inset
        bz = (b['front'] if s >= 0 else b['rear']) - inset
        # superellipse-ish blend so the top stays full over the trunk
        e = 2.4
        yy = a * math.copysign(abs(c) ** (2 / e), c)
        zz = bz * math.copysign(abs(s) ** (2 / e), s)
        pts.append((x, RY + yy, PZ + zz))
    return pts
