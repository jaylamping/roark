"""Cable travel sheets for checks/CABLE_TRAVEL.md: the path at both ends of travel and the middle, for the options that
are alive at each joint. Schematic plan views from the model's dimensions. python render_cable_travel.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)


def ring(ax, r, **k):
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(r * np.cos(t), r * np.sin(t), **k)


def wedge(ax, r0, r1, a0, a1, **k):
    t = np.radians(np.linspace(a0, a1, 120))
    ax.fill(np.r_[r0 * np.cos(t), r1 * np.cos(t[::-1])], np.r_[r0 * np.sin(t), r1 * np.sin(t[::-1])], **k)


def spiral(ax, a_out, r_out, a_in, r_in, turns, pack, t, hug, **k):
    """Spiral from the outer anchor (a_out, r_out) to the inner anchor (a_in, r_in), `turns` turns, wound on the inner wall
    (hug='in') or lying against the outer wall (hug='out'); t = radial pitch per turn."""
    n = 600
    th = np.linspace(0, 2 * np.pi * turns, n)
    if hug == 'in':
        r = r_in + t * (2 * np.pi * turns - th) / (2 * np.pi)
        r = np.minimum(r, r_out)
        lead = int(n * 0.06)
        r[:lead] = np.linspace(r_out, r[lead], lead)
    else:
        r = r_out - t * th / (2 * np.pi)
        lead = int(n * 0.06)
        r[-lead:] = np.linspace(r[-lead], r_in, lead)
    a = math.radians(a_out) - th * pack
    ax.plot(r * np.cos(a), r * np.sin(a), **k)


# ---------------------------------------------------------------- yaw
EX, W = 261.7, 68.0
fig, axs = plt.subplots(2, 3, figsize=(17, 11.4), dpi=100)
for j, yaw in enumerate((-90, 0, 90)):
    for i, opt in enumerate(('C', 'E')):
        ax = axs[i, j]
        ring(ax, 25, color='0.4', lw=0.8); ring(ax, 39.3, color='0.6', lw=0.6); ring(ax, 41.5, color='k', lw=1.2)
        wedge(ax, 36.5, 44, EX - 13, EX + 13, color='tab:blue', alpha=0.6, lw=0)
        lim = 37
        y_e = max(-lim, min(lim, yaw * lim / 90.0))
        w = W - (yaw if opt == 'C' else y_e)
        wedge(ax, 24, 34.6, w - 14, w + 14, color='0.78', lw=0)
        if opt == 'C':
            turns = 2.25 + yaw / 360.0           # winds on the hub as yaw goes positive
            # the spiral runs from the exit (outer) round to the window (inner), turning the +X way
            n = 800
            th = np.linspace(0, 2 * np.pi * turns, n)
            frac = (yaw + 90) / 180.0           # 0 = loose (on the skirt), 1 = tight (on the hub)
            r_loose = 39.8 - 4.0 * th / (2 * np.pi)
            r_tight = 27.0 + 4.0 * (2 * np.pi * turns - th) / (2 * np.pi)
            r = (1 - frac) * r_loose + frac * r_tight
            lead = 50
            r[:lead] = np.linspace(39.8, r[lead], lead); r[-lead:] = np.linspace(r[-lead], 27.5, lead)
            a = math.radians(EX) + (math.radians(w) - math.radians(EX) - 2 * np.pi * math.floor(turns)) * th / th[-1] if False else None
            # end angle must equal the window's: total sweep = (w - EX) mod 360 - 360 * whole turns, turning negative (toward +X)
            sweep = -(((EX - w) % 360) + 360 * round(turns - ((EX - w) % 360) / 360.0))
            aa = np.radians(EX + sweep * th / th[-1])
            ax.plot(r * np.cos(aa), r * np.sin(aa), color='tab:orange', lw=2.2)
            ax.set_title(f'Yaw {yaw:+d}. C: spiral, {abs(sweep) / 360:.2f} turns, band 4 mm radial\n'
                         f'{"loose, against the skirt" if frac < 0.3 else "wound on the hub" if frac > 0.7 else "mid"}; every radius 25 mm or more', fontsize=9)
        else:
            y = y_e
            arc = (EX - w) % 360                 # one-way arc from the window round the -X side to the exit
            # fixed length: the arc lies on the outer wall when short and on the inner wall when long
            a0, a1 = w, w + arc
            L = math.radians(166.3 + lim) * 29.0
            r = min(37.5, max(29.0, L / math.radians(arc)))
            t = np.radians(np.linspace(a0, a1, 200))
            ax.plot(r * np.cos(t), r * np.sin(t), color='tab:orange', lw=5, alpha=0.6, solid_capstyle='butt')
            for a_, r_ in ((a0, 29.0), (a1, 39.5)):       # short clamped leads into the window and out of the exit
                ax.plot([r * math.cos(math.radians(a_)), r_ * math.cos(math.radians(a_))], [r * math.sin(math.radians(a_)), r_ * math.sin(math.radians(a_))],
                        color='tab:orange', lw=5, alpha=0.6, solid_capstyle='butt')
            ax.set_title(f'E: plain arc clamped at both ends, shown at yaw {y:+.0f} (limit +-{lim})\n'
                         f'arc {arc:.0f} deg at r {r:.1f}: 8 mm wide bundle shifts between the walls', fontsize=9)
        ax.set_aspect('equal'); ax.set_xlim(-48, 48); ax.set_ylim(-48, 48); ax.grid(lw=0.3)
        ax.set_xlabel('X - RX'); ax.set_ylabel('Z - YZ')
fig.suptitle('Yaw crossing, dish under the RS02 (plan, fork frame). Blue: yaw exit (fixed). Grey: hub window at 68 deg (turns with the arm). Orange: bundle. '
             'Clamps at the exit and at the window.', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / 'yaw_paths.png'); plt.close(fig)

# ---------------------------------------------------------------- roll
fig, axs = plt.subplots(1, 4, figsize=(21, 5.6), dpi=100)
ax = axs[0]
# section along the roll axis (Z horizontal, radius vertical): cap channel, stub bore, fork channel
ax.fill([-26, -39.3, -39.3, -26], [0, 0, 54.5, 54.5], color='0.85'); ax.text(-38.5, 46, 'rear cap\n(on the drum)', fontsize=8)
ax.fill([-40.3, -47.3, -47.3, -40.3], [20, 20, 26, 26], color='tab:green', alpha=0.5); ax.text(-47, 27.5, '6808', fontsize=8)
ax.fill([-39.3, -47.3, -47.3, -39.3], [12.5, 12.5, 20, 20], color='0.7'); ax.text(-47, 14.5, 'stub, bore dia 25', fontsize=7)
ax.fill([-47.8, -56.7, -56.7, -47.8], [0, 0, 60, 60], color='0.92'); ax.text(-56.2, 46, 'fork rear\n(rolls)', fontsize=8)
ax.plot([-33.3, -33.3, -51.3, -51.3], [45, 3, 3, 45], color='tab:orange', lw=4, alpha=0.7)
ax.annotate('18 mm axial run\n121 deg of roll', (-42.3, 3), (-45, -9), fontsize=8, arrowprops=dict(arrowstyle='->'))
ax.set_xlim(-60, -22); ax.set_ylim(-14, 62); ax.set_aspect('equal'); ax.grid(lw=0.3)
ax.set_xlabel('Z (roll axis)'); ax.set_ylabel('radius from the roll axis')
ax.set_title('Roll crossing as drawn: section along the roll axis', fontsize=9)
for j, roll in enumerate((-11, 50, 110)):
    ax = axs[j + 1]
    ring(ax, 27, color='0.4', lw=0.8); ring(ax, 41, color='k', lw=1.0); ring(ax, 20, color='tab:green', lw=3, alpha=0.4)
    turns = 1.0 + (roll + 11) / 360.0
    frac = (roll + 11) / 121.0
    th = np.linspace(0, 2 * np.pi * turns, 500)
    r_l = 39.5 - 3.0 * th / (2 * np.pi); r_t = 28.5 + 3.0 * (2 * np.pi * turns - th) / (2 * np.pi)
    r = (1 - frac) * r_l + frac * r_t
    r[:30] = np.linspace(39.5, r[30], 30); r[-30:] = np.linspace(r[-30], 28.5, 30)
    aa = np.radians(135.0) - th
    ax.plot(r * np.cos(aa), r * np.sin(aa), color='tab:orange', lw=2.2)
    ax.plot([r[-1] * math.cos(aa[-1])], [r[-1] * math.sin(aa[-1])], 'ks', ms=6); ax.plot([39.5 * math.cos(aa[0])], [39.5 * math.sin(aa[0])], 'b^', ms=7)
    ax.set_aspect('equal'); ax.set_xlim(-46, 46); ax.set_ylim(-46, 46); ax.grid(lw=0.3)
    ax.set_title(f'Roll {roll:+d}. Spiral round the stub, {turns:.2f} turns, r 27-41, band 3 mm\n(blue: anchor on the cap; black: anchor on the fork rear)', fontsize=9)
fig.suptitle('Roll crossing. Left: today (two right-angle bends 18 mm apart in the stub bore). Right: a flat spiral round the stub, which needs its own 6-7 mm deck between cap and fork rear.', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / 'roll_paths.png'); plt.close(fig)

# ---------------------------------------------------------------- pitch
fig, axs = plt.subplots(1, 3, figsize=(17, 6), dpi=100)
T = 115.0
for j, pit in enumerate((-25, 32.5, 90)):
    ax = axs[j]
    ring(ax, 57.4, color='0.4', lw=0.8); ring(ax, 73.5, color='k', lw=1.0); ring(ax, 49, color='0.7', lw=6, alpha=0.5)
    turns = 2.0 + (pit + 25) / 360.0
    frac = (pit + 25) / T
    th = np.linspace(0, 2 * np.pi * turns, 700)
    r_l = 72.0 - 3.0 * th / (2 * np.pi); r_t = 58.9 + 3.0 * (2 * np.pi * turns - th) / (2 * np.pi)
    r = (1 - frac) * r_l + frac * r_t
    r[:30] = np.linspace(72.0, r[30], 30); r[-30:] = np.linspace(r[-30], 58.9, 30)
    aa = np.radians(250.0) - th
    ax.plot(r * np.cos(aa), r * np.sin(aa), color='tab:orange', lw=2.2)
    ax.plot([72.0 * math.cos(aa[0])], [72.0 * math.sin(aa[0])], 'b^', ms=7); ax.plot([r[-1] * math.cos(aa[-1])], [r[-1] * math.sin(aa[-1])], 'ks', ms=6)
    ax.set_aspect('equal'); ax.set_xlim(-80, 80); ax.set_ylim(-80, 80); ax.grid(lw=0.3)
    ax.set_title(f'Pitch {pit:+.0f}. Spiral in the loop channel (r 57.4-73.5), {turns:.2f} turns, band 3 mm\n(blue: feed from the cover, fixed; black: trunk mouth on the flange)', fontsize=9)
fig.suptitle('Pitch crossing: what the present channel can do with the real wires: a spiral of 2 to 2.3 turns covers about 115 deg (shown -25 to +90), not 270. Every radius 57 mm or more.', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / 'pitch_paths.png'); plt.close(fig)
print('done')
