"""Yoke fork front (LOOK=yoke, look build only until Joey says go): the outline of the fork front's cheek with everything
above the hub taken away, as one closed curve, and its insets for the crowned edge.

  today      hull of the dome circle (r 55 on the roll axis) and the two lower circles
  yoke       today's outline below two shoulder lines through the roll axis (YOKE['wedge'] deg below the horizontal), plus
             the hub disc (YOKE['r']); the shoulders run into the hub on a YOKE['fillet'] radius and round over at the
             sides on YOKE['round']. No ears, tabs or bosses: one outline, crowned like the lower cheek.

The shoulder angle is set by the drum's lip screws (r 49, every 45 deg from 22.5): at 36 deg the two lowest exposed screws
(-22.5 and 202.5 deg) stand 8 mm clear of the shoulder's edge, and six show, evenly, over the top.

    python yoke.py        writes cad/_wip/shoulder-pass1/yoke_outline.png (outline, insets, pockets, lip screws)
"""
import math

import numpy as np
from shapely.geometry import Point, Polygon

from dims import DOME, LIP_PCD_R, LIP_RI, LUG_ANGLES, RX, RY, YOKE


def today_hull(k=0.0, xl=33.8, yl=372.0, rl=10.0, n=180):
    from scipy.spatial import ConvexHull
    cs = [(RX, RY, DOME['r'] - k), (RX - xl, yl + 0.5 * k, max(rl - k, 3.0)), (RX + xl, yl + 0.5 * k, max(rl - k, 3.0))]
    pts = np.array([(x + r * math.cos(t), y + r * math.sin(t)) for (x, y, r) in cs for t in np.linspace(0, 2 * math.pi, n, endpoint=False)])
    return Polygon(pts[ConvexHull(pts).vertices])


def wedge():
    a, L = math.radians(YOKE['wedge']), 400.0
    return Polygon([(RX, RY), (RX - L * math.cos(a), RY - L * math.sin(a)), (RX - L, RY - L), (RX + L, RY - L), (RX + L * math.cos(a), RY - L * math.sin(a))])


def poly():
    # YOKE['half_w'] (0: off) would trim the lower body to the cuff's width. It is OFF: the flare of today's outline below
    # the shoulders is what stands outside the drum's envelope (r 59) and runs full depth beside the drum, the two side
    # beams that carry the cheek's bending. Trimmed to +-43.8 they were gone and the lower cheek's stress went up 2.5 times
    # (FF_MX, 2026-11-14). So the shoulder ends keep today's width.
    from shapely.geometry import box
    body = today_hull().intersection(wedge())
    if YOKE.get('half_w'):
        body = body.intersection(box(RX - YOKE['half_w'], 0.0, RX + YOKE['half_w'], 1000.0))
    p = body.union(Point(RX, RY).buffer(YOKE['r'], 128))
    f, r = YOKE['fillet'], YOKE['round']
    return p.buffer(f, 64).buffer(-f, 64).buffer(-r, 64).buffer(r, 64)


_P = []


def outline(k=0.0, out=120):
    """The outline inset by k, as `out` points, from the topmost point, clockwise seen from the front (+Z)."""
    if not _P:
        _P.append(poly())
    ex = _P[0].buffer(-k, 64).exterior if k > 0 else _P[0].exterior
    if ex.is_ccw:
        ex = type(ex)(list(ex.coords)[::-1])
    d0 = ex.project(Point(RX, RY + 400.0))
    return np.array([ex.interpolate((d0 + ex.length * i / out) % ex.length).coords[0] for i in range(out)])


def pockets():
    """Today's two lower dome pockets (from the back), kept inside the yoke's outline with today's 2.4 mm wall."""
    if not _P:
        _P.append(poly())
    inner = _P[0].buffer(-(DOME['r'] - DOME['pocket_r'][1]), 64).intersection(wedge().buffer(-YOKE['pocket_wall']))
    out = []
    for a0, a1 in DOME['pockets']:
        if a0 < 200.0:
            continue
        arc = lambda r, rev=False: [(RX + r * math.cos(math.radians(a)), RY + r * math.sin(math.radians(a))) for a in (np.linspace(a1, a0, 40) if rev else np.linspace(a0, a1, 40))]
        s = Polygon(arc(DOME['pocket_r'][1]) + arc(DOME['pocket_r'][0], True)).intersection(inner).buffer(-3.0, 32).buffer(3.0, 32)
        for g in getattr(s, 'geoms', [s]):
            if g.area > 30.0:
                out.append(np.array(g.simplify(0.03).exterior.coords)[:-1])
    return out


if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from swk import WIP
    fig, ax = plt.subplots(figsize=(8, 9))
    t = np.array(today_hull().exterior.coords)
    ax.plot(t[:, 0], t[:, 1], color='0.6', lw=1, label='today')
    for k in (0.0, 3.0, 6.0, 9.0):
        o = outline(k)
        o = np.vstack([o, o[:1]])
        ax.plot(o[:, 0], o[:, 1], 'k', lw=1.6 if k == 0 else 0.6)
    for p in pockets():
        ax.fill(p[:, 0], p[:, 1], color='0.85')
    th = np.linspace(0, 2 * math.pi, 200)
    for r in (LIP_RI, 56.0, 24.0):
        ax.plot(RX + r * np.cos(th), RY + r * np.sin(th), 'b', lw=0.5)
    P = poly()
    for a in LUG_ANGLES:
        c = Point(RX + LIP_PCD_R * math.cos(math.radians(a)), RY + LIP_PCD_R * math.sin(math.radians(a)))
        ax.add_patch(plt.Circle((c.x, c.y), 4.8, fill=False, color='r'))
        print('lip screw at %6.1f deg: %s, counterbore edge to the yoke outline %.1f mm' % (a, 'covered' if P.contains(c) else 'shows', P.exterior.distance(c) - 4.8))
    print('area today %.0f, yoke %.0f mm2; width at Y 392.5 today %.1f, yoke %.1f' % (today_hull().area, P.area,
          today_hull().intersection(Polygon([(0, 392.4), (400, 392.4), (400, 392.6), (0, 392.6)])).bounds[2] - today_hull().intersection(Polygon([(0, 392.4), (400, 392.4), (400, 392.6), (0, 392.6)])).bounds[0],
          P.intersection(Polygon([(0, 392.4), (400, 392.4), (400, 392.6), (0, 392.6)])).bounds[2] - P.intersection(Polygon([(0, 392.4), (400, 392.4), (400, 392.6), (0, 392.6)])).bounds[0]))
    ax.set_aspect('equal')
    ax.axhline(392.0, color='g', lw=0.5)
    fig.savefig(WIP / 'yoke_outline.png', dpi=110)
