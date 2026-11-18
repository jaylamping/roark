"""Picture sheet for the fork front's RS02-seat revision: outside before and after, the skirt against the hub's rim, the
five screw seats, the key tunnel, and the table of figures against the released part.

    python fork_seat_sheet.py <candidate STL folder under cad/_wip/shoulder-pass1, e.g. stl_look_sf5> <figures.json> <out.png>

figures.json: {"title": "...", "rows": [[label, released, candidate], ...], "notes": ["...", ...]}
"""
import json
import math
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from dims import KEY_SLOT_DEG, RS02_SCREWS, RX, SEAT_Y, YZ
from swk import WIP
from view import render

GREY, RED, DARK = '#9aa0a6', '#c5221f', '#202124'


def sec(m, origin, normal, ax_u, ax_v):
    s = m.section(plane_origin=origin, plane_normal=normal)
    out = []
    if s is None:
        return out
    for e in s.entities:
        p = s.vertices[e.points] - np.asarray(origin)
        out.append((p @ np.asarray(ax_u), p @ np.asarray(ax_v)))
    return out


def draw(ax, segs, color, lw=1.0, label=None):
    for i, (u, v) in enumerate(segs):
        ax.plot(u, v, color=color, lw=lw, label=label if i == 0 else None)


def main(cand_dir, figs_json, out):
    figs = json.loads(Path(figs_json).read_text(encoding='utf-8'))
    rel = str(WIP / 'stl' / 'fork_front.stl')
    cand = str(WIP / cand_dir / 'fork_front.stl')
    hub = str(WIP / 'stl' / 'hub.stl')
    mr, mc, mh = trimesh.load(rel), trimesh.load(cand), trimesh.load(hub)
    fig = plt.figure(figsize=(24, 20), dpi=110)
    fig.suptitle(figs['title'], fontsize=22, fontweight='bold', x=0.02, ha='left', y=0.985)
    td = Path(tempfile.mkdtemp())
    # row 1: the outside, with the hub in place
    views = [('From the front, outboard', 30, 20), ('From below, front', 30, -35), ('From the back', 210, 10)]
    for r, (nm, f) in enumerate((('TODAY', rel), ('CANDIDATE', cand))):
        for c, (vn, az, el) in enumerate(views):
            p = str(td / f'o{r}{c}.png')
            render([f, hub], p, az=az, el=el, size=(900, 720), zoom=1.25, colors=[(0.93, 0.93, 0.91), (0.16, 0.17, 0.19)])
            ax = fig.add_axes([0.02 + c * 0.163 + r * 0.495, 0.70, 0.158, 0.24])
            ax.imshow(plt.imread(p)); ax.axis('off')
            ax.set_title(f'{nm}: {vn.lower()}', fontsize=12)
    fig.text(0.02, 0.955, 'OUTSIDE (fork front in light grey, hub rev E1 in black). The only outside change: the skirt is 3.00 mm longer, to cover the taller hub\'s rim as before.',
             fontsize=14)
    # row 2 left: into the cuff from above, the five screw seats
    for r, (nm, f) in enumerate((('TODAY', rel), ('CANDIDATE', cand))):
        p = str(td / f'i{r}.png')
        render([f], p, az=180, el=62, size=(900, 720), zoom=1.9, colors=[(0.86, 0.86, 0.84)])
        ax = fig.add_axes([0.02 + r * 0.165, 0.415, 0.16, 0.245])
        ax.imshow(plt.imread(p)); ax.axis('off'); ax.set_title(f'{nm}: the motor\'s seat ring from above', fontsize=12)
    fig.text(0.02, 0.672, 'INSIDE: where the yaw motor (RS02) is screwed in with five M3. All of this is hidden once the fork rear and the motor are on.', fontsize=14)
    # row 2 middle: sections through two screw seats
    for k, a in enumerate((104.0, -56.0)):
        t = math.radians(a)
        u = (math.cos(t), 0.0, math.sin(t)); n = (-math.sin(t), 0.0, math.cos(t))
        ax = fig.add_axes([0.37 + k * 0.155, 0.43, 0.14, 0.215])
        draw(ax, sec(mr, (RX, 0.0, YZ), n, u, (0, 1, 0)), GREY, 2.2, 'today')
        draw(ax, sec(mc, (RX, 0.0, YZ), n, u, (0, 1, 0)), RED, 1.2, 'candidate')
        ax.set_xlim(29.5, 44.5); ax.set_ylim(350, 366); ax.set_aspect('equal'); ax.grid(alpha=0.25)
        ax.axvline(36.5, color='k', lw=0.6, ls='-.')
        ax.set_title('Screw seat at %s' % ('104°, under the cheek' if a > 0 else '−56° (as the other three)'), fontsize=12)
        ax.set_xlabel('mm from the yaw axis'); ax.legend(loc='lower right', fontsize=10)
        ax.annotate('washer flat,\nfloor 8.0 (was 6.5)', (36.5, 359.9), (30.2, 363.2), fontsize=10, arrowprops=dict(arrowstyle='->', lw=0.8))
    # row 2 right: the key tunnel, cut on the screw's plane
    a = [q for q in RS02_SCREWS if YZ + 36.5 * math.sin(math.radians(q)) > 38.0][0]
    xk = RX + 36.5 * math.cos(math.radians(a))
    ax = fig.add_axes([0.70, 0.415, 0.28, 0.245])
    draw(ax, sec(mr, (xk, 0.0, YZ), (1, 0, 0), (0, 0, 1), (0, 1, 0)), GREY, 2.2, 'today: square-ended slot, 7.0 wide')
    draw(ax, sec(mc, (xk, 0.0, YZ), (1, 0, 0), (0, 0, 1), (0, 1, 0)), RED, 1.2, 'candidate: round tunnel, dia 7.8')
    zk = 36.5 * math.sin(math.radians(a))
    tt = math.radians(KEY_SLOT_DEG)
    ax.plot([zk, zk - 60 * math.sin(tt)], [SEAT_Y[1] - 0.5, SEAT_Y[1] - 0.5 + 60 * math.cos(tt)], color='#1a73e8', lw=1.0, ls='--', label='line of the hex key')
    ax.set_xlim(-2, 52); ax.set_ylim(347, 412); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.set_title('Key access to the 104° screw (cut on the screw\'s plane, seen from the side)', fontsize=12)
    ax.set_xlabel('mm from the yaw axis, toward the front'); ax.legend(loc='upper right', fontsize=10)
    # row 3 left: the skirt against the hub's rim
    ax = fig.add_axes([0.03, 0.05, 0.27, 0.32])
    o, n, u = (RX, 0.0, YZ), (0, 0, 1), (1, 0, 0)
    draw(ax, sec(mh, o, n, u, (0, 1, 0)), DARK, 1.4, 'hub rev E1')
    draw(ax, sec(mr, o, n, u, (0, 1, 0)), GREY, 2.2, 'fork front today')
    draw(ax, sec(mc, o, n, u, (0, 1, 0)), RED, 1.2, 'candidate')
    ax.set_xlim(33, 47); ax.set_ylim(304, 324); ax.set_aspect('equal'); ax.grid(alpha=0.25)
    ax.annotate("hub's rim", (39.3, 315.4), (34.0, 319.5), fontsize=11, arrowprops=dict(arrowstyle='->', lw=0.8))
    ax.annotate('skirt today:\ncovers the rim by 0.9 mm', (42.4, 314.5), (43.3, 320.5), fontsize=11, color=DARK, arrowprops=dict(arrowstyle='->', lw=0.8))
    ax.annotate('candidate: 3.00 mm longer,\ncovers it by 3.9 mm', (42.4, 311.5), (33.3, 308.2), fontsize=11, color=RED, arrowprops=dict(arrowstyle='->', lw=0.8, color=RED))
    ax.set_title('Skirt against the hub\'s rim (cut through the yaw axis)', fontsize=12)
    ax.set_xlabel('mm from the yaw axis'); ax.set_ylabel('height (mm)'); ax.legend(loc='upper left', fontsize=10)
    # row 3 right: the figures
    ax = fig.add_axes([0.33, 0.03, 0.65, 0.355]); ax.axis('off')
    tb = ax.table(cellText=figs['rows'], colLabels=['Safety factor (target 1.5 on the 1 mm reading, nothing under 1.0 on the 0.5 mm reading)', 'Today', 'Candidate'],
                  colWidths=[0.60, 0.20, 0.20], loc='upper left', cellLoc='left')
    tb.auto_set_font_size(False); tb.set_fontsize(12); tb.scale(1.0, 1.55)
    for (r, c), cell in tb.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight='bold'); cell.set_facecolor('#e8eaed')
    y = 0.98 - 0.064 * (len(figs['rows']) + 1.6)
    for line in figs['notes']:
        ax.text(0.0, y, line, fontsize=12.5, va='top', wrap=True, transform=ax.transAxes)
        y -= 0.052 * (1 + line.count('\n'))
    fig.savefig(out)
    print(out, Path(out).stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main(*sys.argv[1:4])
