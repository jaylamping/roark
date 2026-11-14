"""Two more sketches for checks/CABLE_TRAVEL.md: the roll spiral deck as a section (today against the proposal), and the
pitch service loop in the void under the frame's step. Schematic, from the model's dimensions.
python render_cable_travel2.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)


def box(ax, z0, z1, r0, r1, c, lab=None, fs=7, **k):
    ax.fill([z0, z1, z1, z0], [r0, r0, r1, r1], color=c, **k)
    if lab:
        ax.text((z0 + z1) / 2, (r0 + r1) / 2, lab, fontsize=fs, ha='center', va='center')


# ------------------------------------------------------------ roll: section along the roll axis, upper half
fig, axs = plt.subplots(1, 2, figsize=(17, 7.2), dpi=105)
for ax, new in zip(axs, (False, True)):
    box(ax, -25.96, 30.6, 0, 49, '0.93', 'roll RS03 (solid)', 9)
    box(ax, -28.5, 30.0, 51.5, 57.0, '0.8', 'drum wall')
    # rear cap: plate Z -28.5..-39.3 out to r 54.5, stub r 12.5-20 back to -47.3
    box(ax, -39.3, -28.5, 0, 54.5, 'tab:blue', alpha=0.25)
    ax.text(-34, 50.5, 'rear cap (on the drum)', fontsize=8, ha='center')
    box(ax, -47.3, -39.3, 12.5, 20.0, 'tab:blue', alpha=0.25)
    ax.text(-43.3, 16, 'stub', fontsize=7, ha='center')
    box(ax, -47.3, -40.3, 20.0, 26.0, 'tab:green', '6808', alpha=0.5)
    # fork rear cheek and housing
    box(ax, -56.7, -47.8, 0, 60, 'tab:red', alpha=0.18)
    box(ax, -47.8, -41.8, 26.1, 35.0, 'tab:red', alpha=0.18)
    ax.text(-52.2, 52, 'fork rear (rolls)', fontsize=8, ha='center')
    if not new:
        box(ax, -39.3, -31.0, 28.0, 42.0, 'w', 'stop slot\n(r 28-42)', 7)
        box(ax, -41.5, -31.5, 30.0, 40.0, 'tab:red', alpha=0.45)
        ax.text(-36.5, 35, 'tooth', fontsize=7, ha='center', color='darkred')
        ax.plot([-33.9, -33.9, -51.3, -51.3], [50, 4, 4, 50], color='tab:orange', lw=4, alpha=0.8)
        ax.text(-42.6, 6.5, 'cable: in on the cap channel, along the axis\nthrough the stub bore (18 mm), out on the fork channel', fontsize=7, ha='center')
        ax.set_title('Today: the cable crosses on the roll axis. Two right-angle bends 18 mm apart, turning 121 deg', fontsize=9)
    else:
        box(ax, -39.3, -31.0, 27.0, 41.0, 'w')
        for r_ in (28.5, 31.5, 34.5, 37.5):
            box(ax, -38.6, -32.0, r_ - 1.4, r_ + 1.4, 'tab:orange', alpha=0.8)
        ax.text(-35.2, 43.3, 'spiral deck r 27-41,\n8.3 deep: 1 to 1.34 turns', fontsize=7, ha='center')
        box(ax, -47.8, -39.6, 27.0, 30.0, 'tab:red', alpha=0.5)
        ax.text(-44.5, 31.6, 'post with the\ninner anchor', fontsize=7, color='darkred')
        ax.plot([-33.9, -33.9], [50, 39.0], color='tab:orange', lw=4, alpha=0.8)
        ax.plot([-35.3, -51.3, -51.3], [28.5, 28.5, 50], color='tab:orange', lw=4, alpha=0.8)
        box(ax, -41.0, -39.3, 44.5, 53.0, 'tab:red', alpha=0.45)
        ax.text(-36.0, 47.3, 'stop moves out\nto r 44-53', fontsize=7, color='darkred')
        ax.set_title('Proposal: a spiral deck in the cap where the stop slot is now. Depth and outline unchanged; the stop moves out', fontsize=9)
    ax.axhline(0, color='k', lw=0.6, ls='-.')
    ax.set_xlim(-60, -20); ax.set_ylim(-3, 62); ax.set_aspect('equal'); ax.grid(lw=0.3)
    ax.set_xlabel('Z along the roll axis (rear to the left)'); ax.set_ylabel('radius from the roll axis')
fig.suptitle('Roll crossing, section along the roll axis (upper half). Blue: rear cap. Red: fork rear. Green: 6808. Orange: cable.', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / 'roll_deck_section.png'); plt.close(fig)

# ------------------------------------------------------------ pitch: wrap on the channel wall with a bight in the void under the step
RY = 424.86
fig, axs = plt.subplots(1, 3, figsize=(17, 8.6), dpi=100)
for ax, pit in zip(axs, (-50, 65, 180)):
    t = np.linspace(0, 2 * np.pi, 300)
    ax.plot(57.4 * np.cos(t), RY + 57.4 * np.sin(t), color='0.4', lw=0.8)
    ax.plot(73.5 * np.cos(t), RY + 73.5 * np.sin(t), color='k', lw=1.0)
    ax.fill(49.5 * np.cos(t), RY + 49.5 * np.sin(t), color='0.9'); ax.text(0, RY, 'pitch RS03', ha='center', fontsize=8)
    # frame: step side rail and the lower box's post (seen along X): the void is Z +-50, Y 175-353
    ax.fill([-70, 70, 70, -70], [353.6, 353.6, 373.6, 373.6], color='0.75', alpha=0.5); ax.text(-68, 361, 'step rail', fontsize=7)
    ax.plot([-50, -50, 50, 50], [353.6, 175, 175, 353.6], color='0.5', lw=0.8, ls='--'); ax.text(-48, 180, 'void under the step: 38 deep (X), 100 wide, to Y 175', fontsize=7)
    # wrap from the bottom of the channel (270 deg position, Y low) round to the moving clamp
    a_feed = -90.0
    a_m = a_feed - (pit + 50) - 20.0            # moving clamp, turning clockwise seen from outboard as pitch rises
    aa = np.radians(np.linspace(a_feed, a_m, 200))
    ax.plot(60.0 * np.cos(aa), RY + 60.0 * np.sin(aa), color='tab:orange', lw=3)
    ax.plot([60 * math.cos(math.radians(a_m))], [RY + 60 * math.sin(math.radians(a_m))], 'ks', ms=7)
    # bight: total length constant; wrapped length = 60 * (pit + 50 + 20) deg
    wrap = math.radians(pit + 50 + 20) * 60.0
    Lb = 60.0 + (math.radians(230 + 20) * 60.0 - wrap)        # bight length: 60 spare + what is not wrapped
    depth = (Lb - math.pi * 30.0) / 2 + 30.0
    y_top = RY - 60.0
    ax.plot([0, 0], [y_top, y_top - depth + 30], color='tab:orange', lw=3)
    tb = np.radians(np.linspace(180, 360, 60))
    ax.plot(-30 + 30 * np.cos(tb) * -1, y_top - depth + 30 + 30 * np.sin(tb), color='tab:orange', lw=3)
    ax.plot([-60, -60], [y_top - depth + 30, 350], color='tab:orange', lw=3)
    ax.plot([-60], [350], 'b^', ms=8)
    ax.set_aspect('equal'); ax.set_xlim(-85, 85); ax.set_ylim(165, 505); ax.grid(lw=0.3)
    ax.set_xlabel('Z'); ax.set_ylabel('Y')
    ax.set_title(f'Pitch {pit:+d}: {wrap:.0f} mm wrapped on the channel wall,\nbight {depth:.0f} mm deep below the channel (R 30)', fontsize=9)
fig.suptitle('Pitch, 230 deg (-50 to +180): the cable wraps on the loop channel\'s inner wall; what is not wrapped hangs as a bight in the void under the frame\'s step.\n'
             'Blue: fixed clamp on the frame. Black: clamp on the drum\'s flange. The bight needs a light pull-down (weight or elastic) to follow. Seen along the pitch axis.', fontsize=9)
fig.tight_layout(); fig.savefig(OUT / 'pitch_bight.png'); plt.close(fig)
print('done')
