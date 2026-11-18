"""Three small pictures of the wiring pinch points checked on 2026-11-15 (OPEN_ASSUMPTIONS items 45 to 47), cut from the
adopted exports and the placed motor model.   python wiring_clash_pics.py"""
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Circle

from dims import RX, YZ
from swk import CAD, WIP

OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'wiring'
E = CAD / 'exports' / 'shoulder'
S = WIP / 'stl'
RED = '#e4002b'


def cut(ax, m, origin, normal, ia, ib, col, lw=1.4, off=(0, 0, 0)):
    s = m.section(plane_origin=origin, plane_normal=normal)
    if s is None:
        return
    for e in s.discrete:
        p = np.asarray(e) - off
        ax.plot(p[:, ia], p[:, ib], color=col, lw=lw)


def frame(ax, xl, yl, title, xlab, ylab):
    ax.set_xlim(*xl)
    ax.set_ylim(*yl)
    ax.set_aspect('equal')
    ax.grid(alpha=0.35)
    ax.set_title(title, fontsize=13, weight='bold')
    ax.set_xlabel(xlab)
    ax.set_ylabel(ylab)


drum = trimesh.load(E / 'shoulder_roll_drum_left.STL')
rs03 = pickle.loads((WIP / 'roll_rs03_mesh.pkl').read_bytes())
fig, ax = plt.subplots(figsize=(11, 7.5))
cut(ax, drum, (0, 0, -8.0), (0, 0, 1), 0, 1, 'k')
cut(ax, rs03, (0, 0, -8.0), (0, 0, 1), 0, 1, '0.45')
ax.add_patch(Circle((150.6, 475.0), 0.6, fc=RED, ec='k', zorder=5))
ax.annotate('1.2 mm wire against the roof:\nabout 0.8 mm left over the ear', (150.6, 475.0), (141.0, 479.6), fontsize=11, weight='bold', color=RED, arrowprops=dict(arrowstyle='->', color=RED))
ax.annotate('screw ear on the roll motor housing\n(vendor model): fills 8.4 of the\nbranch\'s 10 mm width', (152.0, 472.5), (156.5, 464.5), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('roof of the signal branch (drum)', (147.0, 474.2), (139.0, 476.3), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
frame(ax, (138, 168), (462, 482), 'Item 45: the drum\'s signal branch at the roll motor (cut 5 mm into the branch)\ndrum black, roll RS03 model grey', 'X, mm', 'Y, mm')
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / 'CLASH_45_drum_signal_branch.png', dpi=75)

cover, ring = trimesh.load(S / 'cover.stl'), trimesh.load(S / 'ring.stl')
fig, ax = plt.subplots(figsize=(11, 8.5))
cut(ax, drum, (0, 0, 0), (0, 0, 1), 0, 1, 'k')
cut(ax, ring, (0, 0, 0), (0, 0, 1), 0, 1, 'tab:green')
cut(ax, cover, (0, 0, 0), (0, 0, 1), 0, 1, 'tab:blue')
ax.plot([98.5, 100.5], [479.75, 475.4], color=RED, lw=2.5)
ax.text(96.4, 477.3, '4.7 mm', color=RED, fontsize=12, weight='bold', ha='right')
t = np.linspace(0, 1, 60)
path = np.array([(103.0, 486.0), (102.2, 481.5), (100.0, 478.2), (98.4, 476.0), (98.6, 472.6), (101.0, 470.4), (106.0, 470.0), (111.0, 470.0)])
ax.plot(path[:, 0], path[:, 1], color=RED, lw=5, alpha=0.5, solid_capstyle='round')
ax.annotate('loop channel\n(wires come down from here)', (102.6, 485.5), (88.0, 487.5), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('end of the cover\'s inner wall', (97.5, 481.0), (85.5, 484.0), fontsize=11, weight='bold', color='tab:blue', arrowprops=dict(arrowstyle='->', color='tab:blue'))
ax.annotate('nose of the drum\'s mouth block', (100.6, 475.3), (86.0, 473.5), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('trunk channel in the drum', (108.0, 470.0), (100.0, 466.6), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('flange ring', (105.4, 484.0), (107.5, 487.5), fontsize=11, weight='bold', color='tab:green', arrowprops=dict(arrowstyle='->', color='tab:green'))
frame(ax, (84, 112), (465, 490), 'Item 46: the trunk mouth at the flange ring (cut on the drum\'s centre plane)\nthe wires turn twice within about 10 mm, radius about 4 mm', 'X, mm', 'Y, mm')
fig.savefig(OUT / 'CLASH_46_trunk_mouth.png', dpi=75)

fr = trimesh.load(E / 'shoulder_fork_rear_left.STL')
fig, ax = plt.subplots(figsize=(10, 9))
cut(ax, fr, (0, 0, YZ - 57.3), (0, 0, 1), 0, 1, 'k', off=(RX, 0, 0))
for x0 in (6.0, 8.5, 11.0, 13.6):
    p = np.array([(x0, 374.0), (x0, 361.5), (x0 - 0.35 * (x0 - 1.5), 358.5), (1.6 - (13.6 - x0) * 0.45, 354.8), (1.6 - (13.6 - x0) * 0.45, 349.0)])
    ax.plot(p[:, 0], p[:, 1], color=RED, lw=2.2, alpha=0.8)
ax.annotate('the wall between the two channels\nends here (Y 360.5)', (3.5, 360.5), (-13.0, 367.5), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('one 16 x 6 channel from here down (Y 354)', (9.0, 354.0), (-4.0, 345.5), fontsize=11, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('signal wires: up to 11 mm\nsideways in 6.5 mm of height', (9.5, 357.6), (15.5, 351.0), fontsize=11, weight='bold', color=RED, arrowprops=dict(arrowstyle='->', color=RED))
ax.text(-5.5, 371.5, 'power\nchannel', fontsize=12, ha='center', weight='bold')
ax.text(9.5, 371.5, 'signal\nchannel', fontsize=12, ha='center', weight='bold')
frame(ax, (-20, 26), (342, 376), 'Item 47: where the fork rear\'s signal channel joins the power channel\n(cut through both channels, seen from the back)', 'mm across (0 = yaw axis)', 'Y, mm')
fig.savefig(OUT / 'CLASH_47_fork_rear_junction.png', dpi=75)
print('ok', OUT)
