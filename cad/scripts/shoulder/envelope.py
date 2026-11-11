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


def cuff_section(y, inset=0.0, n=N_ANG):
    """Cuff round the RS02 about the yaw axis: the round cuff profile (CUFF), swelled toward the back to meet the fork rear
    arm (0.5 mm static gap), so cuff and arm read as one sleeve."""
    c = CUFF
    ys = [c['y0'], c['ro_mid'][1], SEAT_Y[0] - 2.0, SEAT_Y[0] + 2.0, SEAT_Y[1]]
    rs = [c['ro_bot'], c['ro_mid'][0], c['ro_top'], c['ro_top'] + 1.0, SEAT_RO + 0.3]
    ro = float(np.interp(y, ys, rs)) - inset
    rear = (YZ - (JZ0 + 0.5)) - inset           # to Z JZ0 + 0.5 straight behind the axis
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        w = max(0.0, -math.sin(a)) ** 1.5      # wide enough at the back-inboard to take the socket-tap sector (r 49)
        r = ro + (rear - ro) * w
        pts.append((RX + r * math.cos(a), y, YZ + r * math.sin(a)))
    return pts


# fork rear arm: (Y, centre X offset from RX, half width, back depth) stations; the front is the flat joint plane Z JZ0
ARM_STATIONS = [(402.0, 0.0, 17.0, 10.3), (380.0, 0.0, 18.0, 11.8), (364.0, 0.0, 23.0, 13.0), (352.0, 0.0, 23.0, 13.0),
                (344.0, -3.0, 15.0, 12.0), (334.0, -6.0, 11.4, 11.6), (318.0, -6.0, 11.4, 11.6)]


def arm_section(y, cx, w, depth, n=25, e=2.6):
    """D section: flat front on the joint plane, soft superellipse back."""
    pts = []
    for k in range(n):
        t = math.pi * k / (n - 1)                 # 0 -> pi: from +X round the back to -X
        c, s_ = math.cos(t), math.sin(t)
        x = w * math.copysign(abs(c) ** (2 / e), c)
        z = depth * abs(s_) ** (2 / e)
        pts.append((RX + cx + x, y, JZ0 - z))
    return pts
