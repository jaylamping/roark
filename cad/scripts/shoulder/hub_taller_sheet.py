"""HUB_TALLER_CENTRE.png: the hub's centre made 2 mm taller and stronger, before and after. Top: the section of
YAW_CABLE_SECTION.png (through the yaw axis and the cable window) for today's released hub and for the candidate, wires
to scale, added material in green. Bottom: the outside view of both, and the figures in plain words.

    python hub_taller_sheet.py            (needs yaw_cable_section.py's pickles and the look build hubT20)

The figures in the text box come from cad/_wip/shoulder-pass1/hub_taller_figs.json (written by hand from the FE read-outs).
"""
import json
import math
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path as MP
from scipy.interpolate import splev, splprep
from shapely.geometry import Polygon

import view
from dims import HUB_WIN_A, RX, YZ
from swk import CAD, WIP
from yaw_cable_section import section

H = 2.0
OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'hub_print' / 'HUB_TALLER_CENTRE.png'
T = WIP / 'taller_views'
COL = dict(hub='#3b4a5a', rs02='#c9ccd1', fork_front='#b9a27c', fork_rear='#b9a27c', arm='#e6e6e3', add='#2ca02c')
CAB, SIG, BLUE = '#e4002b', '#ff8c00', '#0a58ca'


def shape_of(loops):
    polys = sorted((Polygon(l) for l in loops if len(l) > 3), key=lambda q: -q.area)
    shape = None
    for q in polys:
        q = q.buffer(0)
        shape = q if shape is None else shape.symmetric_difference(q)
    return shape


def fill(ax, shape, fc, z, ec='k', lw=0.7):
    if shape is None or shape.is_empty:
        return
    for g in getattr(shape, 'geoms', [shape]):
        if g.geom_type != 'Polygon':
            continue
        vs, cs = [], []
        for ring in [g.exterior] + list(g.interiors):
            c = np.asarray(ring.coords)
            vs += list(c)
            cs += [MP.MOVETO] + [MP.LINETO] * (len(c) - 2) + [MP.CLOSEPOLY]
        ax.add_patch(PathPatch(MP(vs, cs), fc=fc, ec=ec, lw=lw, zorder=z))


def shift(loops, dy):
    return [l + np.array((0.0, dy)) for l in loops]


def panel(ax, loops, hub_loops, arm_loops, old_hub_loops, floor_y, n_sig, title, gap):
    for k in ('rs02', 'fork_front', 'fork_rear'):
        fill(ax, shape_of(loops[k]), COL[k], 2)
    fill(ax, shape_of(arm_loops), COL['arm'], 2)
    hub = shape_of(hub_loops)
    if old_hub_loops is not None:
        fill(ax, hub, COL['add'], 3)
        fill(ax, shape_of(old_hub_loops).intersection(hub), COL['hub'], 4, lw=0.4)
    else:
        fill(ax, hub, COL['hub'], 3)
    ax.plot([0, 0], [284, 334], color='k', lw=0.8, ls=(0, (12, 4, 2, 4)), zorder=6)

    def band(r, flip=1):
        for i in range(2):
            ax.add_patch(Circle((r, floor_y + 1.15 + 2.3 * i + 0.15), 1.15, fc=CAB, ec='k', lw=0.5, zorder=8))
        for i in range(n_sig):
            ax.add_patch(Circle((r + flip * 1.75, floor_y + 0.6 + 1.2 * i + 0.15), 0.6, fc=SIG, ec='k', lw=0.4, zorder=8))
    for r_ in (37.3, 33.0):
        band(r_)
    for r_ in (-35.2, -30.9, -27.2):
        band(r_, flip=-1)
    dy = floor_y - 318.36
    pts = np.array([(28.4, 320.9 + dy * 0.5), (26.6, 318.6 + dy), (24.6, 313.2 + dy), (22.3, 308.6 + dy), (20.3, 304.6 + dy), (19.3, 300.5 + dy), (19.2, 296.5 + dy), (19.2, 289.5)])
    tck, _ = splprep(pts.T, s=0, k=3)
    c = np.array(splev(np.linspace(0, 1, 200), tck)).T
    d_ = np.gradient(c, axis=0)
    n_ = np.column_stack((-d_[:, 1], d_[:, 0]))
    n_ /= np.linalg.norm(n_, axis=1)[:, None]
    for off, w, col in ((-0.6, 2.3, CAB), (1.15, 1.2, SIG)):
        a_, b_ = c + n_ * (off - w / 2), c + n_ * (off + w / 2)
        ax.fill(np.r_[a_[:, 0], b_[::-1, 0]], np.r_[a_[:, 1], b_[::-1, 1]], fc=col, ec='k', lw=0.5, zorder=8)
    ax.annotate('', (-42.0, floor_y), (-42.0, 323.86), arrowprops=dict(arrowstyle='<->', color=BLUE, lw=1.8), zorder=9)
    ax.text(-43.0, (floor_y + 323.86) / 2, 'cable space\n%.1f mm high  ' % gap, fontsize=16, ha='right', va='center', color=BLUE, weight='bold', zorder=9, bbox=dict(fc='w', ec='none', pad=1.0))
    for y_ in (floor_y, 323.86):
        ax.plot([-43.5, -39.5], [y_, y_], color='k', lw=0.6, zorder=7)
    ax.text(0, 329.3, 'RS02 MOTOR BODY', fontsize=15, ha='center', weight='bold', zorder=9)
    ax.text(54.0, 314.0, 'fork skirt', fontsize=12, ha='center', va='top', weight='bold', zorder=9)
    ax.text(-55.0, 294.0 + dy, 'upper arm', fontsize=12, ha='center', va='center', weight='bold', zorder=9)
    ax.set_xlim(-66, 64)
    ax.set_ylim(283.5, 334.0)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontsize=18, weight='bold')


def main():
    figs = json.load(open(WIP / 'hub_taller_figs.json')) if (WIP / 'hub_taller_figs.json').exists() else {}
    loops = pickle.load(open(WIP / 'yaw_section_loops.pkl', 'rb'))
    new = trimesh.load(WIP / 'stl_look_hubT20' / 'hub.stl')
    new_loops = shift(section(new, HUB_WIN_A), -H)
    ua = pickle.load(open(WIP / 'ua_meshes.pkl', 'rb'))
    arm_loops = [l for m in ua[:2] for l in section(m, HUB_WIN_A)]
    arm_loops = [l for l in arm_loops if l[:, 1].max() > 280]
    fig = plt.figure(figsize=(25, 17), dpi=100)
    a0 = fig.add_axes([0.005, 0.50, 0.495, 0.42])
    a1 = fig.add_axes([0.50, 0.50, 0.495, 0.42])
    panel(a0, loops, loops['hub'], arm_loops, None, 318.36, 4, 'TODAY (the hub now printing): gap 5.5 mm', 5.5)
    panel(a1, loops, new_loops, shift(arm_loops, -H), shift(loops['hub'], -H), 318.36 - H, 6, 'PROPOSED: centre 2 mm taller, gap 7.5 mm (green = added material)', 5.5 + H)
    a0.annotate('step in the hub top: 1.5 mm', (-24.3, 319.1), (-65.0, 309.0), fontsize=13, weight='bold', ha='left', arrowprops=dict(arrowstyle='->', lw=1.3), zorder=9)
    a0.annotate('thin slits right through the top\n(six, each 0.5 mm wide): found today', (-19.25, 318.0), (-8.0, 303.0), fontsize=13, weight='bold', ha='center', color='#b00020',
                arrowprops=dict(arrowstyle='->', lw=1.3, color='#b00020'), zorder=9)
    a0.annotate('pocket that needed\nsupport to print', (30.0, 307.5), (63.0, 300.0), fontsize=13, weight='bold', ha='right', arrowprops=dict(arrowstyle='->', lw=1.3), zorder=9)
    a1.annotate('step 3.5 mm: the centre is\n2 mm thicker, slits filled', (-21.0, 319.0), (-65.0, 306.5), fontsize=13, weight='bold', ha='left', color='#1a7a1a',
                arrowprops=dict(arrowstyle='->', lw=1.3, color='#1a7a1a'), zorder=9)
    a1.annotate('pocket filled on a slope:\nprints without support inside', (31.0, 302.0), (63.0, 293.5), fontsize=13, weight='bold', ha='right', color='#1a7a1a',
                arrowprops=dict(arrowstyle='->', lw=1.3, color='#1a7a1a'), zorder=9)
    a1.annotate('room for the third\nsignal pair (6 wires)', (38.9, 320.5), (63.0, 329.5), fontsize=13, weight='bold', ha='right', color=CAB, arrowprops=dict(arrowstyle='->', lw=1.3, color=CAB), zorder=9)
    a1.annotate('arm sits 2 mm lower', (-39.0, 299.5), (-65.0, 288.0), fontsize=13, weight='bold', ha='left', arrowprops=dict(arrowstyle='->', lw=1.3), zorder=9)
    # outside views
    for tag in ('0', '1'):
        view.render([str(T / 'ff.stl'), str(T / 'fr.stl'), str(T / f'hub{tag}.stl'), str(T / f'arm{tag}.stl')], str(T / f'out{tag}.png'), az=25, el=5, size=(900, 800), zoom=1.6,
                    colors=[(0.93, 0.93, 0.92), (0.93, 0.93, 0.92), (0.15, 0.15, 0.16), (0.93, 0.93, 0.92)])
    for i, (tag, ttl) in enumerate((('0', 'Outside, today: black hub band 12.5 mm'), ('1', 'Outside, proposed: band 14.5 mm, nothing else changes'))):
        bx = fig.add_axes([0.01 + 0.235 * i, 0.03, 0.225, 0.40])
        bx.imshow(mpimg.imread(T / f'out{tag}.png'))
        bx.axis('off')
        bx.set_title(ttl, fontsize=15, weight='bold')
    lines = figs.get('lines') or ['(figures pending)']
    fig.text(0.495, 0.455, 'What it buys and what it costs', fontsize=20, weight='bold', va='top')
    fig.text(0.495, 0.428, '\n'.join(lines), fontsize=14.5, va='top', linespacing=1.32)
    fig.text(0.5, 0.965, 'Hub centre 2 mm taller and stronger: before and after (same cut as the cable picture; wires to scale)', fontsize=23, ha='center', weight='bold')
    fig.savefig(OUT)
    print(OUT)


if __name__ == '__main__':
    main()
