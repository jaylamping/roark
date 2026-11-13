"""Before and after picture of the rear cap screw fix candidate (checks/cap_screw_fix.png).

Top row: section through the roll axis and the screw at 0 deg (radius against Z). Bottom row: section across the axis at
Z -30.0, through the collar and its socket. Left: the baseline look build (fix off). Right: LOOK=capfix.

    python render_cap_fix.py        (under capped.py; needs stl_look_capbase and stl_look_capfix in cad/_wip/shoulder-pass1)
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'cad' / 'scripts' / 'shoulder'))
import dims as D  # noqa: E402

W = ROOT / 'cad' / '_wip' / 'shoulder-pass1'
OUT = ROOT / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'cap_screw_fix.png'
RX, RY = D.RX, D.RY
COL = dict(drum='#4c78a8', cap='#f58518')


def draw(ax, name, to3d, xlim, ylim, step=0.1):
    """Material map by point-in-solid tests on a 0.1 mm grid: exact about holes and cavities, whatever the section loops."""
    from matplotlib.colors import to_rgb
    xs = np.arange(xlim[0] + step / 2, xlim[1], step)
    ys = np.arange(ylim[0] + step / 2, ylim[1], step)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.array([to3d(u, v) for u, v in zip(gx.ravel(), gy.ravel())])
    img = np.ones(gx.shape + (3,))
    for part in ('cap', 'drum'):
        m = trimesh.load(W / name / f'{part}.STL')
        inside = np.concatenate([m.contains(pts[i:i + 500]) for i in range(0, len(pts), 500)]).reshape(gx.shape)
        img[inside] = to_rgb(COL[part])
    ax.imshow(img, origin='lower', extent=(xlim[0], xlim[1], ylim[0], ylim[1]), interpolation='nearest')
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect('equal')
    ax.grid(alpha=0.25)


fig, axs = plt.subplots(2, 2, figsize=(13, 11), dpi=120)
for j, (name, title) in enumerate((('stl_look_capbase', 'Today: M3 at r 50, located by the screws alone'),
                                   ('stl_look_capfix', 'Candidate: M2.5 at r 50.6, collar on the drum in a socket in the cap'))):
    ax = axs[0, j]
    draw(ax, name, lambda r, z: (RX + r, RY, z), (43, 58), (-42, -17))
    ax.set_title(title + '\nsection through the screw at 0 deg', fontsize=10)
    ax.set_xlabel('radius from the roll axis, mm')
    ax.set_ylabel('Z, mm')
    ax.axvline(48.0, color='g', ls=':', lw=1)
    ax.text(48.1, -18.0, 'drum bore r 48', color='g', fontsize=8)
    ax = axs[1, j]
    draw(ax, name, lambda t, r: (RX + r, RY + t, -30.0), (-14, 14), (43, 58))
    ax.set_title('section at Z -30.0 (1.5 mm behind the drum\'s rear face), looking along the axis', fontsize=10)
    ax.set_xlabel('across, mm')
    ax.set_ylabel('radius, mm')
axs[0, 0].plot([], [], color=COL['drum'], lw=6, label='drum')
axs[0, 0].plot([], [], color=COL['cap'], lw=6, label='rear cap')
axs[0, 0].legend(loc='lower left', fontsize=9)
fig.tight_layout()
fig.savefig(OUT)
print(OUT)
