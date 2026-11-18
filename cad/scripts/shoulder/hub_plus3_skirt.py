"""HUB_PLUS3_SKIRT.png: with the hub's centre 3 mm taller, how much of the cable gap can be seen under the fork's skirt,
for three skirt lengths: as today, 1.5 mm longer, 3 mm longer. From meshes only: the exported fork front and fork rear,
the +3.0 hub look build, the arm's STEP, a red ring where the outermost wire of the spiral lies, and for the longer
skirts the fork front's own bottom outline extruded downward.

    python hub_plus3_skirt.py
"""
import math
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Circle, Rectangle
from shapely.geometry import Polygon

import view
from dims import RX, YZ
from swk import CAD, WIP
from yaw_cable_section import section

H = 3.0
LOOKN = 'hubT30A'
OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'hub_print' / 'HUB_PLUS3_SKIRT.png'
T = WIP / 'taller_views'
FLOOR = 318.36 - H            # dish floor, assembly frame
SKIRT_Y, SKIRT_RI, RIM_R = 314.5, 41.5, 39.3
WIRE_R, WIRE_D = 39.75, 2.3   # outermost wire of the spiral: against the cuff (r 40.7) one layer up, over the rim's edge
A_SEC = 20.0                  # the rim section is cut at this angle (the front of the shoulder)
RED = '#e4002b'


def ring(r, y, d):
    t = trimesh.creation.torus(major_radius=r, minor_radius=d / 2, major_sections=96, minor_sections=16)
    t.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
    t.apply_translation((RX, y, YZ))
    return t


def main():
    E = CAD / 'exports' / 'shoulder'
    ff = trimesh.load(E / 'shoulder_fork_front_left.STL')
    hub = trimesh.load(WIP / f'stl_look_{LOOKN}' / 'hub.STL')
    hub.export(T / 'hub3.stl')
    arm = trimesh.load(T / 'arm0.stl')
    arm.apply_translation((0, -H, 0))
    arm.export(T / 'arm3.stl')
    trimesh.util.concatenate([ring(WIRE_R, FLOOR + 0.15 + WIRE_D / 2, WIRE_D), ring(WIRE_R, FLOOR + 0.15 + 1.5 * WIRE_D, WIRE_D)]).export(T / 'wire3.stl')
    cols = ((0.0, 'Skirt as today'), (1.5, 'Skirt 1.5 mm longer'), (3.0, 'Skirt 3 mm longer'))
    for g, _ in cols:
        if g:
            # the longer skirt: the fork front's own lowest slab (its bottom face included), moved down by g
            ext = trimesh.intersections.slice_mesh_plane(ff, (0, -1, 0), (0, SKIRT_Y + g + 0.05, 0))
            ext.apply_translation((0, -g, 0))
            ext.export(T / f'skirt_ext_{g}.stl')
        files = [str(T / 'ff.stl'), str(T / 'fr.stl'), str(T / 'hub3.stl'), str(T / 'arm3.stl'), str(T / 'wire3.stl')] + ([str(T / f'skirt_ext_{g}.stl')] if g else [])
        colors = [(0.93, 0.93, 0.92), (0.93, 0.93, 0.92), (0.15, 0.15, 0.16), (0.93, 0.93, 0.92), (0.9, 0.0, 0.1)] + ([(0.93, 0.93, 0.92)] if g else [])
        for nm, el in (('stand', 22.0), ('low', -32.0)):
            view.render(files, str(T / f'skirt_{g}_{nm}.png'), az=25, el=el, size=(900, 700), zoom=1.7, colors=colors)
    hub_l = section(hub, A_SEC)
    ff_l = section(ff, A_SEC)
    fig = plt.figure(figsize=(24, 21), dpi=85)
    for i, (g, ttl) in enumerate(cols):
        ov = 3.86 - H + g
        ang = math.degrees(math.atan2(ov, SKIRT_RI - RIM_R))
        band = 12.5 + H - g
        ax = fig.add_axes([0.02 + 0.33 * i, 0.66, 0.30, 0.25])
        for l in hub_l:
            ax.fill(l[:, 0], l[:, 1], fc='#3b4a5a', ec='k', lw=0.8, zorder=2)
        for l in ff_l:
            ax.fill(l[:, 0], l[:, 1], fc='#d9d2c3', ec='k', lw=0.8, zorder=2)
        if g:
            ax.add_patch(Rectangle((SKIRT_RI, SKIRT_Y - g), 2.1, g, fc='#7fbf7f', ec='k', lw=0.8, zorder=3))
        for k in range(2):
            ax.add_patch(Circle((WIRE_R, FLOOR + 0.15 + WIRE_D / 2 + k * WIRE_D), WIRE_D / 2, fc=RED, ec='k', lw=0.6, zorder=5))
        # the steepest sight line: under the skirt's inner edge, over the rim's outer top edge
        p0 = np.array((SKIRT_RI, SKIRT_Y - g))
        p1 = np.array((RIM_R, FLOOR))
        dv = (p1 - p0) / np.linalg.norm(p1 - p0)
        a_, b_ = p0 - dv * 9.0, p1 + dv * 3.5
        ax.plot([a_[0], b_[0]], [a_[1], b_[1]], color='#0a58ca', lw=2.5, zorder=6)
        ax.annotate('', b_, a_, arrowprops=dict(arrowstyle='->', color='#0a58ca', lw=2.5), zorder=6)
        ax.text(46.3, SKIRT_Y - g - 5.2, 'steepest line of sight\ninto the gap: %.0f deg up' % ang, color='#0a58ca', fontsize=15, weight='bold', ha='center')
        ax.text(34.6, FLOOR - 3.2, 'HUB', color='w', fontsize=15, weight='bold')
        ax.text(45.2, 320.5, 'fork\nskirt', fontsize=13, weight='bold', ha='center')
        ax.text(36.5, FLOOR + 3.3, 'outer wire', color=RED, fontsize=13, weight='bold', ha='right')
        ax.set_xlim(33.5, 51.5)
        ax.set_ylim(305.5, 323.5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('%s\ncovers the hub rim by %.1f mm; black band %.1f mm' % (ttl, ov, band), fontsize=16, weight='bold')
        for j, (nm, lab) in enumerate((('stand', 'Standing beside the robot, looking down at the shoulder'), ('low', 'Sitting or crouching, looking up at the shoulder'))):
            bx = fig.add_axes([0.02 + 0.33 * i, 0.345 - 0.325 * j, 0.30, 0.29])
            bx.imshow(mpimg.imread(T / f'skirt_{g}_{nm}.png'))
            bx.axis('off')
            bx.set_title(lab, fontsize=14, weight='bold')
    fig.text(0.5, 0.965, 'Hub centre 3 mm taller: how much of the cable gap shows under the fork skirt (the red ring is the outermost wire)', fontsize=24, ha='center', weight='bold')
    fig.text(0.5, 0.012, 'From the models: +3.0 hub, adopted fork front and fork rear, the arm 3 mm lower. Top row: cut through the rim at the front. The longer skirts (green) are the fork front\'s own bottom outline carried straight down; the fork front itself is not changed yet.',
             fontsize=13, ha='center')
    fig.savefig(OUT)
    print(OUT)


if __name__ == '__main__':
    main()
