"""Small sheet for the fork rear's two wiring changes (OPEN_ASSUMPTIONS items 47 and 51): the taller opening between the
signal and power channels, and the tie bar at the underside. Cuts of the adopted export against the candidate look build.

    python fork_rear_wiring_sheet.py <candidate STL folder under cad/_wip/shoulder-pass1, e.g. stl_look_fr2>
"""
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from dims import CH_DX, P_OFF, RX, RZ
from swk import CAD, WIP
from view import render

OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'wiring'
GREY, RED, BLUE = '#9aa0a6', '#c5221f', '#1a73e8'


def cut(ax, m, o, n, iu, iv, col, lw, label, du=0.0):
    s = m.section(plane_origin=o, plane_normal=n)
    if s is None:
        return
    for i, e in enumerate(s.discrete):
        p = np.asarray(e)
        ax.plot(p[:, iu] - du, p[:, iv], color=col, lw=lw, label=label if i == 0 else None)


def main(cand_dir):
    a = trimesh.load(str(CAD / 'exports' / 'shoulder' / 'shoulder_fork_rear_left.STL'))
    b = trimesh.load(str(WIP / cand_dir / 'fork_rear.STL'))
    xb = RX + P_OFF + CH_DX + 3.4
    fig = plt.figure(figsize=(22, 12.5), dpi=100)
    fig.suptitle('Fork rear: two small changes inside for the wiring. The outside is unchanged. Nothing real is changed yet.', fontsize=20, fontweight='bold', x=0.02, ha='left', y=0.975)
    # outside, before and after
    td = Path(tempfile.mkdtemp())
    for k, (nm, f) in enumerate((('TODAY', a), ('CANDIDATE', b))):
        p = str(td / f'{k}.stl'); f.export(p)
        q = str(td / f'{k}.png')
        render([p], q, az=205, el=12, size=(700, 620), zoom=1.3, colors=[(0.9, 0.9, 0.88)])
        ax = fig.add_axes([0.02 + k * 0.125, 0.52, 0.12, 0.36]); ax.imshow(plt.imread(q)); ax.axis('off'); ax.set_title(f'{nm}: from the back', fontsize=12)
    # 1. the channel junction
    ax = fig.add_axes([0.30, 0.50, 0.30, 0.40])
    o, n = (0, 0, RZ - 0.5), (0, 0, 1)
    cut(ax, a, o, n, 0, 1, GREY, 2.4, 'today', RX); cut(ax, b, o, n, 0, 1, RED, 1.2, 'candidate', RX)
    ax.set_xlim(-22, 28); ax.set_ylim(346, 384); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.annotate('today the dividing wall\nends here (Y 360.3)', (3.6, 360.3), (9.0, 350.0), fontsize=11.5, arrowprops=dict(arrowstyle='->', lw=0.9))
    ax.annotate('candidate: it ends 12 mm higher,\nwith a sloped end', (3.6, 371.0), (9.5, 376.5), fontsize=11.5, color=RED, arrowprops=dict(arrowstyle='->', lw=0.9, color=RED))
    ax.text(-13.5, 381.0, 'power\nchannel', fontsize=11, ha='center', va='top'); ax.text(9.6, 365.5, 'signal\nchannel', fontsize=11, ha='center', va='top')
    ax.set_title('1. Where the signal channel joins the power channel (cut through both, seen from the back)', fontsize=13, fontweight='bold', loc='left')
    ax.set_xlabel('mm across (0 = yaw axis)'); ax.set_ylabel('height (mm)'); ax.legend(loc='lower left', fontsize=10)
    # 2. the tie bar, from below and from the side
    ax = fig.add_axes([0.64, 0.50, 0.34, 0.40])
    o, n = (0, 341.0, 0), (0, 1, 0)
    cut(ax, a, o, n, 0, 2, GREY, 2.4, 'today', RX); cut(ax, b, o, n, 0, 2, RED, 1.2, 'candidate', RX)
    ax.set_xlim(-26, 28); ax.set_ylim(-63, -44); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.annotate('tie bar, 2 x 2 mm,\nfrom the front wall to the skin', (xb - RX, -53.0), (6.0, -60.5), fontsize=11.5, color=RED, arrowprops=dict(arrowstyle='->', lw=0.9, color=RED))
    ax.text(-13.0, -53.0, 'wires pass here', fontsize=11, color=BLUE, ha='center'); ax.text(7.0, -53.2, 'and here', fontsize=11, color=BLUE, ha='center')
    ax.set_title('2. Tie bar at the underside (cut 1 mm up, seen from above)', fontsize=13, fontweight='bold', loc='left')
    ax.set_xlabel('mm across (0 = yaw axis)'); ax.set_ylabel('mm front to back'); ax.legend(loc='upper right', fontsize=10)
    ax = fig.add_axes([0.02, 0.07, 0.26, 0.36])
    o, n = (xb, 0, 0), (1, 0, 0)
    cut(ax, a, o, n, 2, 1, GREY, 2.4, 'today'); cut(ax, b, o, n, 2, 1, RED, 1.2, 'candidate')
    ax.set_xlim(-63, -43); ax.set_ylim(338, 352); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.annotate('the bar stops inside the skin:\nnothing shows outside', (-57.2, 341.0), (-62.5, 346.5), fontsize=11.5, color=RED, arrowprops=dict(arrowstyle='->', lw=0.9, color=RED))
    ax.set_title('The tie bar from the side (cut along it)', fontsize=13, fontweight='bold', loc='left')
    ax.set_xlabel('mm front to back (outer skin on the left)'); ax.set_ylabel('height (mm)'); ax.legend(loc='upper right', fontsize=10)
    # text
    ax = fig.add_axes([0.31, 0.03, 0.67, 0.42]); ax.axis('off')
    lines = [
        ('WHY', True),
        ('1. Today the wall between the two channels ends only 6.5 mm above the single channel below, so the signal wires are bent to about R 2 over a', False),
        ('    sharp corner. With the wall ending 12 mm higher they cross over about 18 mm of height (about R 10).', False),
        ('2. Today nothing holds the cable where it leaves the fork rear for the yaw joint. The yaw spiral needs that end clamped. The bar gives a small', False),
        ('    cable tie something to go round. It lies on the print plate, so it needs no support. The hollow there is about 40 mm wide and 8 mm', False),
        ('    deep; the bar crosses it 2 mm left of the yaw axis, and the wires thread past it on either side.', False),
        ('', False),
        ('STRENGTH (fork with the motor bolted in, washers as real parts, bearing race snug; plastic read alone, nothing left out; 0.5 / 1 mm reading):', True),
        ('    Roll stop at 17 N.m, lowest in the fork away from the motor screws:   today 1.85 / 1.91 layer, 1.62 / 2.21 shear      candidate 1.90 / 1.90, 1.77 / 2.18', False),
        ('    Arm\'s design load, same region:                                                      today 1.85 / 2.24 layer, 1.91 / 2.39 shear      candidate 2.16 / 2.37, 1.93 / 2.45', False),
        ('    No measurable change: the differences are mesh noise. The motor screw seats read the same in both.', False),
        ('', False),
        ('SIZE OF THE CHANGE: 66 mm3 less plastic (68.3 g against 68.4 g). Outline, bearing seat, joint face and screw positions unchanged.', True),
        ('NOT CHECKED: threaded with real wire; a print. The bar is 2 x 2 mm of PETG: it holds a cable tie, not a pull on the cable.', True),
    ]
    y = 0.98
    for t, bold in lines:
        ax.text(0.0, y, t, fontsize=12.5, va='top', fontweight='bold' if bold else 'normal', transform=ax.transAxes)
        y -= 0.068
    out = OUT / 'FORK_REAR_WIRING_CANDIDATE.png'
    fig.savefig(str(out))
    print(out, out.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main(sys.argv[1])
