"""One sheet of the shoulder's wiring pinch points for Joey (OPEN_ASSUMPTIONS items 44 to 47 and 51): what is in the way,
the proposed fix, and whether it needs a shape change. Uses the pictures made by wiring_clash_pics.py and stepdown_room.py
and adds the place where the cable leaves the fork rear, cut from the adopted fork rear, fork front and hub.   python wiring_clash_sheet.py"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

import dims
from dims import RX, YZ, Y_EX
from swk import CAD, WIP

OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'wiring'
S = WIP / 'stl'
RED, GREY, DARK = '#c5221f', '#80868b', '#202124'
DISH_FLOOR = 315.36      # top of the adopted hub's cable floor, assembly frame (read from the hub export)

PANELS = [
    ('CLASH_45_drum_signal_branch.png', '1. Drum: the roll motor\'s screw ear stands in the signal channel',
     ['IN THE WAY: the ear fills 8.4 of the channel\'s 10 mm; 2.0 mm is left over it.',
      'A twisted signal pair (2.4 mm) does not pass.',
      'FIX: run the signal pair through the power channel beside it (9.5 mm free).',
      'SHAPE CHANGE: none. FIRST: look at the real motor, is the ear there?']),
    ('CLASH_46_trunk_mouth.png', '2. Drum and cover: the trunk\'s mouth at the flange ring',
     ['IN THE WAY: a 4.7 mm gap, then an S-turn within about 10 mm.',
      'The two power wires pass single file, bent far tighter than their 15 mm rule.',
      'FIX: cut the cover\'s inner wall back about 12 mm at the mouth,',
      'and round the nose of the drum\'s block.',
      'SHAPE CHANGE: yes, cover and drum, inside. After the pitch rig.']),
    ('CLASH_47_fork_rear_junction.png', '3. Fork rear: where the signal channel joins the power channel',
     ['IN THE WAY: the wall between the two channels ends only 6.5 mm above',
      'the single channel: signal wires bent to about R 2 over a sharp corner.',
      'FIX: end the dividing wall 12 mm higher (about R 10 for the wires).',
      'SHAPE CHANGE: yes, fork rear, inside. With its next print.']),
]


def cut(ax, m, x, col, lw, label):
    s = m.section(plane_origin=(x, 0, 0), plane_normal=(1, 0, 0))
    if s is None:
        return
    for i, e in enumerate(s.discrete):
        p = np.asarray(e)
        ax.plot(p[:, 2] - YZ, p[:, 1], color=col, lw=lw, label=label if i == 0 else None)


def caption(fig, x, y, lines):
    for i, t in enumerate(lines):
        fig.text(x, y - i * 0.0155, t, fontsize=12.5, color=RED if t.startswith('SHAPE CHANGE') else DARK,
                 fontweight='bold' if t.startswith('SHAPE CHANGE') else 'normal')


def main():
    fig = plt.figure(figsize=(24, 17), dpi=100)
    fig.suptitle('Shoulder wiring: five places where the cable is pinched or cannot be reached, and what to do about each', fontsize=22,
                 fontweight='bold', x=0.02, ha='left', y=0.985)
    fig.text(0.02, 0.955, 'Measured on the adopted parts and the motor models. Nothing here is built or changed yet. Red line under each picture: does it need a shape change?', fontsize=14)
    for k, (png, title, lines) in enumerate(PANELS):
        ax = fig.add_axes([0.02 + k * 0.33, 0.585, 0.30, 0.33])
        ax.imshow(plt.imread(str(OUT / png))); ax.axis('off'); ax.set_title(title, fontsize=14, fontweight='bold', loc='left')
        caption(fig, 0.02 + k * 0.33, 0.572, lines)
    # 4. where the cable leaves the fork for the yaw joint
    ax = fig.add_axes([0.03, 0.155, 0.27, 0.30])
    x0 = RX - 6.0 + getattr(dims, 'CH_DX', 0.0)
    for f, col, lw, lab in (('hub.stl', DARK, 1.6, 'hub rev E1 (turns)'), ('fork_front.stl', GREY, 1.2, 'fork front (outer skin)'), ('fork_rear.STL', RED, 1.6, 'fork rear (cable channel)')):
        cut(ax, trimesh.load(str(S / f)), x0, col, lw, lab)
    ax.set_xlim(-70, -18); ax.set_ylim(304, 350); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.annotate("the channel ends here\n(fork rear's underside, Y 340)", (-53.0, 340.0), (-45.0, 343.0), fontsize=11.5, arrowprops=dict(arrowstyle='->', lw=0.9))
    ax.annotate('', (-45.0, 316.0), (-52.5, 339.0), arrowprops=dict(arrowstyle='->', lw=1.6, color='#1a73e8'))
    ax.text(-47.5, 328.5, '25 mm of free drop,\nnothing to tie to', fontsize=11.5, color='#1a73e8')
    ax.annotate('floor of the cable space', (-32.0, DISH_FLOOR), (-36.0, 307.0), fontsize=11.5, arrowprops=dict(arrowstyle='->', lw=0.9))
    ax.set_title('4. Fork rear: where the cable leaves for the yaw joint', fontsize=14, fontweight='bold', loc='left')
    ax.set_xlabel('mm from the yaw axis, toward the back'); ax.set_ylabel('height (mm)'); ax.legend(loc='lower left', fontsize=10)
    caption(fig, 0.02, 0.092, ['IN THE WAY: nothing holds the cable where it leaves the channel.',
                               'The yaw spiral only works if this end is clamped; loose, it can reach the turning hub.',
                               "FIX: a tie slot (or clip) at the channel's end on the fork rear.",
                               "SHAPE CHANGE: yes, fork rear, inside. With the fork rear's next print."])
    # 5. the step-down splice and its fuse
    ax = fig.add_axes([0.35, 0.115, 0.36, 0.33])
    ax.imshow(plt.imread(str(OUT / 'STEPDOWN_ROOM.png'))); ax.axis('off')
    ax.set_title('5. Behind the yaw motor: the 16 to 18 AWG splice and its 10 A fuse', fontsize=14, fontweight='bold', loc='left')
    caption(fig, 0.35, 0.092, ['IN THE WAY: the splice and one fuse holder fit in the cavity (44 x 20 x 20 mm),',
                               'but nothing there can be reached once the fork rear is on:',
                               'a blown fuse means taking the shoulder apart.',
                               'SHAPE CHANGE: only for option D below. This one is a decision, not a fix.'])
    # options and summary
    ax = fig.add_axes([0.735, 0.03, 0.255, 0.43]); ax.axis('off')
    t = ['Options for the 10 A fuse (5):',
         ' A. In the cavity. Fits. A blown fuse = strip-down.',
         ' B. No separate fuse: every motor below has its own',
         '     (11 A in all); the board\'s 15 A trip covers a short.',
         '     Weak case: a partial short of 11 to 15 A.',
         ' C. Just below the yaw joint, in the upper arm, where',
         '     the arm opens. About 0.5 m of 18 AWG stays',
         '     upstream of it. No shoulder change.',
         ' D. A flush door about 45 x 20 mm at the back of the',
         '     shoulder. Reachable; a visible seam.',
         ' E. Step down on the drum instead. Not recommended:',
         '     it puts 18 AWG through the roll joint.',
         '',
         'My suggestion: C, with B as the fallback.',
         '',
         'What needs a shape change:',
         '  1  none           2  cover and drum (inside)',
         '  3  fork rear (inside)   4  fork rear (inside)',
         '  5  none, unless the door (D) is wanted',
         '',
         '3 and 4 can ride on the fork rear revision that is',
         'being adopted now, if you say so before it prints.',
         'Not checked by hand: none of this has been threaded',
         'with real wire; the cable rigs have not been run.']
    for i, line in enumerate(t):
        ax.text(0.0, 0.99 - i * 0.041, line, fontsize=13, va='top', fontweight='bold' if line.endswith(':') or line.startswith('My') else 'normal',
                transform=ax.transAxes)
    out = OUT / 'WIRING_CLASHES.png'
    fig.savefig(str(out))
    print(out, out.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
