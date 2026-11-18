"""STEPDOWN_ROOM.png: the room for the 16 to 18 AWG splice and a fuse holder in the cavity behind the yaw RS02 (inside the
fork front's cuff, under the fork rear). Plan section at Y 332 and side section on the yaw axis, from the exported meshes
and the placed RS02 model.   python stepdown_room.py"""
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Rectangle

from dims import RX, YZ
from swk import CAD, WIP

E = CAD / 'exports' / 'shoulder'
OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'wiring' / 'STEPDOWN_ROOM.png'
P = dict(fork_front=trimesh.load(E / 'shoulder_fork_front_left.STL'), fork_rear=trimesh.load(E / 'shoulder_fork_rear_left.STL'),
         rs02=pickle.loads((WIP / 'yaw_section_rs02.pkl').read_bytes()), hub=trimesh.load(E / 'shoulder_hub_left.STL'))
COL = dict(fork_front='#8c6d3f', fork_rear='#1f77b4', rs02='0.45', hub='k')


def cut(ax, origin, normal, ia, ib, sa=1.0):
    for k, m in P.items():
        s = m.section(plane_origin=origin, plane_normal=normal)
        if s is None:
            continue
        for e in s.discrete:
            p = np.asarray(e) - (RX, 0, YZ)
            ax.plot(sa * p[:, ia], p[:, ib], color=COL[k], lw=1.3)


fig, axs = plt.subplots(1, 2, figsize=(20, 10))
ax = axs[0]
cut(ax, (0, 332.0, 0), (0, 1, 0), 0, 2)
ax.add_patch(Rectangle((-18, -57.5), 36, 14, fc='#e4002b', alpha=0.55, ec='k'))
ax.text(0, -50.5, 'fuse holder 36 x 14 x 9', ha='center', va='center', fontsize=12, weight='bold')
ax.set_xlim(-60, 60); ax.set_ylim(-75, 50); ax.set_aspect('equal'); ax.grid(alpha=0.3)
ax.set_title('Seen from above, cut 12 mm above the dish (Y 332)\nfront of the robot is up; the cavity is behind the yaw motor', fontsize=14, weight='bold')
ax.set_xlabel('mm across'); ax.set_ylabel('mm front to back')
ax = axs[1]
cut(ax, (RX, 0, 0), (1, 0, 0), 2, 1)
ax.add_patch(Rectangle((-57.5, 323.0), 9, 14, fc='#e4002b', alpha=0.55, ec='k'))
ax.annotate('fuse holder\n(9 thick, 14 high here)', (-53, 330), (-78, 318), fontsize=12, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('fork rear closes the cavity\nfrom above (six joint screws)', (-56, 342), (-86, 352), fontsize=12, weight='bold', color=COL['fork_rear'], arrowprops=dict(arrowstyle='->', color=COL['fork_rear']))
ax.annotate('yaw motor (RS02)', (-20, 345), (-12, 372), fontsize=12, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.annotate('wires go on down\nto the dish', (-50, 320.5), (-30, 308), fontsize=12, weight='bold', arrowprops=dict(arrowstyle='->'))
ax.set_xlim(-95, 50); ax.set_ylim(300, 380); ax.set_aspect('equal'); ax.grid(alpha=0.3)
ax.set_title('Seen from the side, cut on the yaw axis\nback of the robot is to the left', fontsize=14, weight='bold')
ax.set_xlabel('mm front to back'); ax.set_ylabel('height (Y), mm')
fig.suptitle('Room for the 16 to 18 AWG splice and a fuse holder behind the yaw motor: it fits, but the cavity cannot be opened once the fork rear is on', fontsize=17, weight='bold')
fig.text(0.5, 0.02, 'Outlines cut from the exported fork front (brown), fork rear (blue), hub (black) and the placed RS02 model (grey). The holder is a typical inline MINI blade holder, drawn to an assumed size: measure the one bought.',
         ha='center', fontsize=12)
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=70)
print(OUT)
