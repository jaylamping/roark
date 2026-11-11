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
        tt = b.get('top_taper')
        top = float(np.interp(x, [q[0] for q in tt], [q[1] for q in tt])) if tt and x > tt[0][0] else b['top']
        a = (top if c >= 0 else b['bot']) - inset
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


# ---- SLEEVE (back-view round 2): the cuff and the fork rear arm's lower duct are one outline about the yaw axis, split
# only at the joint plane (fork front Z >= JZ0 + 0.5, fork rear Z <= JZ0). Round at the front, one rearward swell that takes
# the 16 x 6 passage with its wall, the socket-tap arc and the joint screws; a skirt to Y 313.6 hides the yaw exit.
SLEEVE = dict(y_bot=314.5, bore_skirt=41.5, a_c=-100.0, p=1.0, top_round=4.0, round_free=(30.0, 60.0),
              ys=[314.5, 320.36, 336.0, SEAT_Y[0] - 2.0, SEAT_Y[0] + 2.0, SEAT_Y[1]] if not SHAPE_A else
                 [314.5, 320.36, 330.0, 340.0, SEAT_Y[0] + 2.0, SEAT_Y[1]],     # option a: waist at Y 330, clear of the socket pockets (r 40.5 from Y 340.9)
              ro=[43.6, 43.4, 42.9, 43.0, 43.4, 43.8] if not SHAPE_A else [43.6, 43.0, 42.1, 42.6, 43.4, 43.8],   # option a: waisted like the upper arm's neck      # no flare at the top (round 1 flared to 45.3: read as a flange)
              # the back holds the real channel boxes with their 2.4 mm wall: power Z -54.3..-48.3 (centred on RZ), signal from
              # Y 354 at X +4..+14 (round 1 took the power channel as -51.3..-45.3 and left 1.0 mm over its inboard corner)
              rb_ys=[314.5, 350.0, 354.0], rb=[66.5, 66.5, 67.0],
              x_in=48.9, shape_y=[345.0, 351.0], a_c_y=[-95.0, -100.0], p_y=[2.5, 1.0])


def sleeve_r(a_deg, y, inset=0.0, top=0.0):
    c = SLEEVE
    ro = float(np.interp(y, c['ys'], c['ro']))
    rb = float(np.interp(y, c['rb_ys'], c['rb']))
    # the swell reaches round to the inboard side only at the socket tap (Y 353-359); lower down it is held to the 16 x 6
    # duct behind the axis, clear of the shell skin when the fork rolls inward (round 1 touched it at roll -9 to -10)
    a_c = float(np.interp(y, c['shape_y'], c['a_c_y']))
    p_ = float(np.interp(y, c['shape_y'], c['p_y']))
    da = abs(((a_deg - a_c) + 180.0) % 360.0 - 180.0)
    w = max(0.0, math.cos(math.radians(da))) ** p_
    r = ro + (rb - ro) * w
    # inboard reach held to X >= RX - x_in (smooth min): the pitch flange ring passes 2 mm off it at the -11 stop, and the
    # socket-tap arc (r 47.5, -168..-94 deg) keeps about 2 mm of skin
    ca = math.cos(math.radians(a_deg))
    if ca < -1e-3:
        cap, k = c['x_in'] / -ca, 0.4
        r = -k * math.log(math.exp(-r / k) + math.exp(-cap / k))
    r -= inset
    if top:
        f0, f1 = c['round_free']
        t = min(1.0, max(0.0, (da - f0) / (f1 - f0)))
        r -= top * t * t * (3 - 2 * t)                 # rounded top edge at the front and sides, none where the arm rises
    return r


def sleeve_section(y, inset=0.0, top=0.0, n=144):
    out = []
    for k in range(n):
        a = 360.0 * k / n
        r = sleeve_r(a, y, inset, top)
        out.append((RX + r * math.cos(math.radians(a)), y, YZ + r * math.sin(math.radians(a))))
    return out


def sleeve_clip(y, side, inset=0.0, top=0.0, n=720, zc=None):
    """Open curve of the outline on one side of the joint plane plus its two end points on the plane:
    side 'front' keeps Z >= JZ0 + 0.5, 'rear' keeps Z <= JZ0. Returns (curve pts, start, end) ordered so the closing
    line runs end -> start along the plane."""
    if zc is None:
        zc = JZ0 + 0.5 if side == 'front' else JZ0
    keep = (lambda z: z >= zc) if side == 'front' else (lambda z: z <= zc)
    pts = sleeve_section(y, inset, top, n)
    m = len(pts)
    flags = [keep(p[2]) for p in pts]
    # start at the first kept point after a dropped one
    i0 = next(i for i in range(m) if flags[i] and not flags[i - 1])
    seq = []
    i = i0
    while flags[i % m]:
        seq.append(pts[i % m])
        i += 1
    # exact crossings on the plane
    def cross(pa, pb):
        t = (zc - pa[2]) / (pb[2] - pa[2])
        return (pa[0] + t * (pb[0] - pa[0]), y, zc)
    a = cross(pts[(i0 - 1) % m], pts[i0 % m])
    b = cross(pts[(i - 1) % m], pts[i % m])
    # thin the curve to about 40 points
    step = max(1, len(seq) // 40)
    seq = [a] + seq[1:-1:step] + [b]
    return seq
