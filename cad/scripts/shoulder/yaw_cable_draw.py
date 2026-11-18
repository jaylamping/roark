"""Draws YAW_CABLE_SECTION.png from the loops yaw_cable_section.py cut out of the meshes (run that first).

    python yaw_cable_draw.py
"""
import math
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, PathPatch, Wedge
from matplotlib.path import Path as MP
from scipy.interpolate import splev, splprep
from shapely.geometry import Polygon

from dims import HUB_WIN_A
from swk import CAD, WIP

OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'hub_print' / 'YAW_CABLE_SECTION.png'
COL = dict(hub='#3b4a5a', rs02='#c9ccd1', fork_front='#b9a27c', fork_rear='#b9a27c')
CAB, SIG, BLUE = '#e4002b', '#ff8c00', '#0a58ca'
STEP_R, FLOOR_R, TOP_R = 25.13, 39.3, 23.51      # measured from the hub export (yaw_cable_section.py prints them)


def main():
    loops = pickle.load(open(WIP / 'yaw_section_loops.pkl', 'rb'))
    fig = plt.figure(figsize=(25, 12.5), dpi=100)
    ax = fig.add_axes([0.01, 0.10, 0.63, 0.78])
    bx = fig.add_axes([0.645, 0.10, 0.35, 0.78])
    # ---------------- left: the section
    skirt_r = None
    for k in ('rs02', 'fork_front', 'fork_rear', 'hub'):
        polys = sorted((Polygon(l) for l in loops[k] if len(l) > 3), key=lambda q: -q.area)
        shape = None
        for q in polys:
            q = q.buffer(0)
            shape = q if shape is None else shape.symmetric_difference(q)
        if shape is None:
            continue
        if k == 'fork_front':
            skirt_r = shape.intersection(Polygon([(25, 318.5), (60, 318.5), (60, 323.5), (25, 323.5)])).bounds[0]
        for g in getattr(shape, 'geoms', [shape]):
            if g.geom_type != 'Polygon':
                continue
            vs, cs = [], []
            for ring in [g.exterior] + list(g.interiors):
                c = np.asarray(ring.coords)
                vs += list(c)
                cs += [MP.MOVETO] + [MP.LINETO] * (len(c) - 2) + [MP.CLOSEPOLY]
            ax.add_patch(PathPatch(MP(vs, cs), fc=COL[k], ec='k', lw=0.8, zorder=3 if k == 'hub' else 2))
    print('fork skirt inner radius at the window plane, Y 318.5-323.5:', round(skirt_r, 2))
    ax.plot([0, 0], [290, 334], color='k', lw=0.8, ls=(0, (12, 4, 2, 4)), zorder=6)

    # the cable: turns of the coil in the gap (two 2.3 mm power wires stacked, four 1.2 mm singles stacked beside them)
    def band(r, flip=1, y0=318.36):
        for i in range(2):
            ax.add_patch(Circle((r, y0 + 1.15 + 2.3 * i + 0.2), 1.15, fc=CAB, ec='k', lw=0.5, zorder=8))
        for i in range(4):
            ax.add_patch(Circle((r + flip * 1.75, y0 + 0.6 + 1.2 * i + 0.2), 0.6, fc=SIG, ec='k', lw=0.4, zorder=8))
    for r_ in (37.3, 33.0):
        band(r_)
    for r_ in (-35.2, -30.9, -27.0):
        band(r_, flip=-1)
    # down the slot and the bore: the same wires as a band 3.5 mm thick in this plane
    pts = np.array([(28.2, 320.9), (26.6, 318.6), (24.6, 313.2), (22.3, 308.6), (20.3, 304.6), (19.3, 300.5), (19.2, 296.5), (19.2, 291.5)])
    tck, _ = splprep(pts.T, s=0, k=3)
    c = np.array(splev(np.linspace(0, 1, 200), tck)).T
    d_ = np.gradient(c, axis=0)
    n_ = np.column_stack((-d_[:, 1], d_[:, 0]))
    n_ /= np.linalg.norm(n_, axis=1)[:, None]
    for off, w, col in ((-0.6, 2.3, CAB), (1.15, 1.2, SIG)):
        a_, b_ = c + n_ * (off - w / 2), c + n_ * (off + w / 2)
        ax.fill(np.r_[a_[:, 0], b_[::-1, 0]], np.r_[a_[:, 1], b_[::-1, 1]], fc=col, ec='k', lw=0.5, zorder=8)

    def dim_v(x, y0, y1, txt, side=1, col='k'):
        ax.annotate('', (x, y0), (x, y1), arrowprops=dict(arrowstyle='<->', color=col, lw=1.6), zorder=9)
        ax.text(x + side * 0.6, (y0 + y1) / 2, txt, bbox=dict(fc='w', ec='none', pad=1.0), fontsize=15, va='center', ha='left' if side > 0 else 'right', color=col, weight='bold', zorder=9)

    def dim_h(y, x0, x1, txt, col='k', dy=0.5):
        ax.annotate('', (x0, y), (x1, y), arrowprops=dict(arrowstyle='<->', color=col, lw=1.6), zorder=9)
        ax.text((x0 + x1) / 2, y + dy, txt, fontsize=15, ha='center', va='bottom' if dy > 0 else 'top', color=col, weight='bold', zorder=9)
    for y_ in (318.36, 319.86, 323.86):
        ax.plot([-43.5, -39.5], [y_, y_], color='k', lw=0.6, zorder=7)
    dim_v(-42.0, 318.36, 323.86, 'cable space\n5.5 mm high  ', side=-1, col=BLUE)
    ax.annotate('4.0 mm: the flange stands\nproud of the motor body', (-23.6, 322.0), (-52.0, 329.0), fontsize=14, weight='bold', ha='center', arrowprops=dict(arrowstyle='->', lw=1.4), zorder=9)
    ax.annotate('1.5 mm: step in\nthe hub top', (-24.3, 319.1), (-53.0, 311.0), fontsize=14, weight='bold', ha='center', arrowprops=dict(arrowstyle='->', lw=1.4), zorder=9)
    dim_h(326.3, STEP_R, skirt_r, 'cable space %.1f mm wide' % (skirt_r - STEP_R), col=BLUE)
    for x_ in (STEP_R, skirt_r):
        ax.plot([x_, x_], [323.0, 327.0], color=BLUE, lw=0.6, zorder=7)
    dim_h(312.6, -TOP_R, TOP_R, 'hub top, dia 47:\nthe only place the hub\nmeets the motor', dy=-0.5)
    for x_ in (-TOP_R, TOP_R):
        ax.plot([x_, x_], [311.8, 319.6], color='k', lw=0.6, ls=':', zorder=7)
    ax.annotate('slot in the hub\n9 mm x 16 mm', (26.6, 311.0), (41.0, 304.5), fontsize=15, weight='bold', arrowprops=dict(arrowstyle='->', lw=1.5), zorder=9)
    ax.annotate('18 AWG bundle, to scale:\n2 power wires (2.3 mm, red)\n4 signal wires (1.2 mm, orange)', (37.3, 321.2), (47.0, 329.0), fontsize=15, weight='bold', color=CAB,
                arrowprops=dict(arrowstyle='->', lw=1.5, color=CAB), zorder=9)
    ax.annotate('down the bore\nto the arm', (20.6, 293.0), (29.0, 290.6), fontsize=15, weight='bold', color=CAB, arrowprops=dict(arrowstyle='->', lw=1.5, color=CAB), zorder=9)
    ax.text(0, 329.3, 'RS02 MOTOR BODY (fixed to the fork)', fontsize=17, ha='center', weight='bold', zorder=9)
    ax.text(0, 321.9, 'motor output flange (turns)', fontsize=12.5, ha='center', weight='bold', zorder=9)
    ax.text(-34.0, 293.0, 'HUB (turns with the arm)', fontsize=17, ha='center', va='center', weight='bold', zorder=9)
    ax.text(skirt_r + 6.5, 316.6, 'fork skirt\n(fixed)', fontsize=14, ha='center', va='top', weight='bold', zorder=9)
    ax.set_xlim(-66, 72)
    ax.set_ylim(288.5, 334.5)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.text(0.325, 0.865, 'Cut straight through the middle and the cable slot (motor above, hub below)', fontsize=19, weight='bold', ha='center')

    # ---------------- right: plan of the dish from the motor side (X to the right, Z down the page)
    P = lambda r, a: (r * math.cos(math.radians(a)), -r * math.sin(math.radians(a)))
    bx.add_patch(Wedge((0, 0), 47.0, 0, 360, width=47.0 - skirt_r, fc=COL['fork_front'], ec='k', lw=0.8))
    bx.add_patch(Wedge((0, 0), FLOOR_R, 0, 360, width=FLOOR_R - STEP_R, fc='#dfe9f5', ec='k', lw=0.8))
    bx.add_patch(Circle((0, 0), STEP_R, fc=COL['hub'], ec='k', lw=0.8))
    for a_ in (-142, -82, -22, 38, 98, 158):
        bx.add_patch(Circle(P(12.0, a_), 2.15, fc='w', ec='k', lw=0.8))
    slot = [P(math.hypot(r_, w_), HUB_WIN_A + math.degrees(math.atan2(w_, r_))) for r_, w_ in ((22.5, -8), (32.5, -8), (32.5, 8), (22.5, 8))]
    bx.fill([q[0] for q in slot], [q[1] for q in slot], fc='k', ec='w', lw=1.2, zorder=4)
    n = 600
    a_sp = np.linspace(261.7, 261.7 + 720 + (HUB_WIN_A - 261.7) % 360, n)
    r_sp = np.linspace(37.6, 28.4, n)
    sp = np.array([P(r_, a_) for r_, a_ in zip(r_sp, a_sp)])
    bx.plot(sp[:, 0], sp[:, 1], color=CAB, lw=6.5, solid_capstyle='round', zorder=5)
    e0, e1 = P(52.0, 261.7), P(37.6, 261.7)
    bx.plot([e0[0], e1[0]], [e0[1], e1[1]], color=CAB, lw=6.5, solid_capstyle='round', zorder=5)
    for i in (50, 190, 330, 470):
        bx.annotate('', sp[i + 8], sp[i], arrowprops=dict(arrowstyle='-|>', fc='k', ec='k', lw=0, mutation_scale=32), zorder=6)
    bx.text(0, 0, 'motor\nflange\nbolts on\nhere', fontsize=12.5, ha='center', va='center', color='w', weight='bold', zorder=7)
    lab = dict(fontsize=16, weight='bold', zorder=9, bbox=dict(fc='w', ec='k', boxstyle='round,pad=0.3'))
    arr = dict(arrowstyle='->', lw=1.8)
    bx.annotate('1  Cable comes in\nfrom the fork (fixed)', P(48.5, 261.7), (-50.0, 55.0), arrowprops=arr, **lab)
    bx.annotate('2  Winds about 2 1/2 times round the\nring-shaped space. The coil tightens and\nloosens as the arm turns 90 deg each way', P(36.5, 150.0), (-53.0, -64.0), arrowprops=arr, **lab)
    bx.annotate('3  Drops through\nthe slot in the hub', P(27.5, HUB_WIN_A), (22.0, -52.0), arrowprops=arr, **lab)
    bx.text(6.0, 55.0, "4  Then down the hub's\nbore into the arm", **lab)
    bx.set_xlim(-56, 56)
    bx.set_ylim(-70, 64)
    bx.set_aspect('equal')
    bx.axis('off')
    bx.set_title('Looking down from the motor side (motor taken away)', fontsize=19, weight='bold')
    fig.text(0.5, 0.945, 'Where the yaw cable goes: the hub meets the motor only on its centre ring; the cable lives in the ring-shaped gap around it',
             fontsize=22, ha='center', weight='bold')
    fig.text(0.035, 0.012,
             'Measured from the models (hub and fork front exports; RobStride RS02 model as placed): motor body underside Y 323.86; motor flange face Y 319.86, flange dia 43; '
             'hub top face dia 47;\nhub floor Y 318.36 from r 25.1 to r 39.3; fork wall r 41.5 for 2 mm above the floor, then r %.1f. '
             'So the gap is 5.5 mm high (a 1.5 mm step in the hub top + the 4.0 mm that the flange stands proud of the motor body) and %.1f mm wide at its narrowest (16.4 at the floor).\nSlot 9 x 16 mm at 68 deg. '
             'Wires: 2 x 18 AWG (2.3 mm) + 4 x 28 AWG (1.2 mm), to scale; where they lie is drawn, not measured.' % (skirt_r, skirt_r - STEP_R),
             fontsize=13.5, va='bottom')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(OUT)


if __name__ == '__main__':
    main()
