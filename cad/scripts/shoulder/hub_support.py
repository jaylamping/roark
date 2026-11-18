"""Where the hub's print file really puts support: reads the sliced G-code inside the 3MF (no slicing, no Bambu Studio),
collects every extrusion of the features 'Support', 'Support interface' and 'Support transition', and reports them in
the part's own terms (radius and angle about the yaw axis, height above the bed). Draws HUB_SUPPORT_REMOVAL.png.

    python hub_support.py [3MF] [--picture]
"""
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

F = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else Path(r'C:\joe\prints\shoulder-hub\shoulder_hub_left_revD3c7.3mf')
FIL_AREA = math.pi * 1.75 ** 2 / 4
RHO = 1.27e-3      # g/mm3, PETG


def parse(text):
    """(feature, x0, y0, x1, y1, z, e_mm) for every extruding move."""
    x = y = z = 0.0
    feat = ''
    out = []
    for ln in text.splitlines():
        if ln.startswith('; FEATURE: '):
            feat = ln[11:].strip()
            continue
        if ln.startswith('; Z_HEIGHT: '):
            z = float(ln[12:])
            continue
        if not (ln.startswith('G1 ') or ln.startswith('G0 ') or ln.startswith('G2 ') or ln.startswith('G3 ')):
            continue
        m = dict((k, float(v)) for k, v in re.findall(r'([XYZEIJ])(-?\d*\.?\d+)', ln.split(';')[0]))
        nx, ny = m.get('X', x), m.get('Y', y)
        if 'Z' in m and 'X' not in m and 'Y' not in m and 'E' not in m:
            pass
        e = m.get('E', 0.0)
        if e > 0 and (nx != x or ny != y):
            out.append((feat, x, y, nx, ny, z, e))
        x, y = nx, ny
    return out


def main():
    z = zipfile.ZipFile(F)
    text = z.read([n for n in z.namelist() if n.endswith('.gcode')][0]).decode(errors='replace')
    seg = parse(text)
    feats = sorted({s[0] for s in seg})
    arr = {f: np.array([s[1:] for s in seg if s[0] == f]) for f in feats}
    ow = arr['Outer wall']
    # the part's centre on the plate: the centre of the outer walls' bounding box in the spigot's layers (round, Z 9 to 20)
    m = (ow[:, 4] > 9.0) & (ow[:, 4] < 20.0)
    cx, cy = (ow[m, 0].min() + ow[m, 0].max()) / 2, (ow[m, 1].min() + ow[m, 1].max()) / 2
    print(f'part centre on the plate {cx:.2f}, {cy:.2f}; spigot outer radius {(ow[m, 0].max() - ow[m, 0].min()) / 2:.2f}')
    tot = sum(a[:, 5].sum() for a in arr.values()) * FIL_AREA * RHO
    print(f'all extrusion {tot:.1f} g')
    S = np.vstack([arr[f] for f in feats if f.startswith('Support')])
    lab = np.concatenate([[f] * len(arr[f]) for f in feats if f.startswith('Support')])
    mx, my = (S[:, 0] + S[:, 2]) / 2 - cx, (S[:, 1] + S[:, 3]) / 2 - cy
    r, ang, zz, g = np.hypot(mx, my), np.degrees(np.arctan2(my, mx)), S[:, 4], S[:, 5] * FIL_AREA * RHO
    print(f'support in all: {g.sum():.2f} g in {len(S)} moves, Z {zz.min():.1f} to {zz.max():.1f}')
    for f in sorted(set(lab)):
        k = lab == f
        print(f'  {f}: {g[k].sum():.2f} g, Z {zz[k].min():.1f}-{zz[k].max():.1f}, r {r[k].min():.1f}-{r[k].max():.1f}')
    print('by height band and radius band (g):')
    zb = [0, 0.3, 1.0, 1.7, 3, 6, 10, 15, 20, 25, 30, 45]
    rb = [0, 11, 16, 24.8, 30, 36, 45, 70]
    for i in range(len(zb) - 1):
        row = []
        for j in range(len(rb) - 1):
            k = (zz >= zb[i]) & (zz < zb[i + 1]) & (r >= rb[j]) & (r < rb[j + 1])
            row.append(g[k].sum())
        if sum(row) > 0.001:
            print(f'  Z {zb[i]:4.1f}-{zb[i + 1]:4.1f}: ' + '  '.join(f'r {rb[j]:g}-{rb[j + 1]:g}: {row[j]:.2f}' for j in range(len(rb) - 1) if row[j] > 0.001))
    return dict(cx=cx, cy=cy, S=S, lab=lab, r=r, ang=ang, z=zz, g=g, arr=arr)


if __name__ == '__main__' and '--picture' not in sys.argv:
    main()


def picture(d, out):
    """Three panels: a vertical section through the lugs with the support near that plane; the part cut at Z 12 seen from
    above with the tall support; the part seen from below (the bed side) with the thin support under the dish."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import trimesh
    from dims import RX, YZ
    from swk import CAD
    m = trimesh.load(CAD / 'exports' / 'shoulder' / 'shoulder_hub_left.STL')
    R = np.eye(4)
    R[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    m.apply_transform(R)
    m.apply_translation((-RX, -YZ, -m.bounds[0, 2]))          # yaw axis at the origin, RS02 face on Z 0
    S, zz, g = d['S'], d['z'], d['g']
    sx, sy = (S[:, 0] + S[:, 2]) / 2 - d['cx'], (S[:, 1] + S[:, 3]) / 2 - d['cy']
    tall = zz > 2.0
    fig, axs = plt.subplots(1, 3, figsize=(19, 7.2))
    RED, ORA = '#d62728', '#ff7f0e'

    def outline(ax, sec, ia, ib, **kw):
        for e in sec.entities:
            q = sec.vertices[e.points]
            ax.plot(q[:, ia], q[:, ib], **kw)
    # 1: vertical section through the lugs (plane y = 0)
    ax = axs[0]
    outline(ax, m.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0)), 0, 2, color='k', lw=1.0)
    k = np.abs(sy) < 4.0
    ax.scatter(sx[k & tall], zz[k & tall], s=3, color=RED, label='support inside the hub (3.9 g, tree)')
    ax.scatter(sx[k & ~tall], zz[k & ~tall], s=3, color=ORA, label='support under the dish and the top face (2.6 g)')
    ax.annotate('out through the top opening,\nbetween the six screw bosses', xy=(-24, 14), xytext=(-8, 44), color=RED, fontsize=10, ha='center',
                arrowprops=dict(arrowstyle='<-', color=RED, lw=2.2))
    ax.annotate('pulls out sideways\nat the open rim', xy=(40, 0.9), xytext=(58, 12), color=ORA, fontsize=10, ha='center', arrowprops=dict(arrowstyle='<-', color=ORA, lw=2.2))
    ax.axhline(0, color='0.5', lw=3)
    ax.text(-52, -3.2, 'print bed (the RS02 face is down)', fontsize=9, color='0.3')
    ax.set_xlim(-55, 70); ax.set_ylim(-6, 52); ax.set_aspect('equal'); ax.set_title('Section through the two lugs, as it sits on the plate', fontsize=11)
    ax.set_xlabel('mm'); ax.set_ylabel('height above the bed, mm'); ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.16), fontsize=9, markerscale=4)
    # 2: cut at Z 12, from above
    ax = axs[1]
    outline(ax, m.section(plane_origin=(0, 0, 12.0), plane_normal=(0, 0, 1)), 0, 1, color='k', lw=1.0)
    outline(ax, m.section(plane_origin=(0, 0, 21.5), plane_normal=(0, 0, 1)), 0, 1, color='tab:blue', lw=0.8)
    ax.scatter(sx[tall], sy[tall], s=1.5, color=RED)
    ax.plot([], [], 'k', label='the hub cut 12 mm above the bed')
    ax.plot([], [], color='tab:blue', label='the spigot and the bosses 21.5 mm above the bed')
    ax.plot([], [], color=RED, lw=3, label='support, 2 to 20 mm above the bed')
    a = math.radians(68.0)
    ax.annotate('cable window: a second way in\n(9 mm slot)', xy=(30 * math.cos(a), 30 * math.sin(a)), xytext=(34, 47), fontsize=9, ha='center', arrowprops=dict(arrowstyle='->', color='0.2'))
    ax.set_xlim(-50, 60); ax.set_ylim(-50, 56); ax.set_aspect('equal'); ax.legend(loc='lower left', fontsize=8)
    ax.set_title('Seen from above (the arm side): the support stands under the inner ledge of the spigot,\nin a pocket open only through the bore and at the cable window', fontsize=11)
    # 3: from below
    ax = axs[2]
    outline(ax, m.section(plane_origin=(0, 0, 0.75), plane_normal=(0, 0, 1)), 0, 1, color='k', lw=1.0)
    outline(ax, m.section(plane_origin=(0, 0, 2.5), plane_normal=(0, 0, 1)), 0, 1, color='0.6', lw=0.7)
    ax.scatter(sx[~tall], sy[~tall], s=1.5, color=ORA)
    ax.plot([], [], 'k', label='the hub cut 0.75 mm above the bed')
    ax.plot([], [], color='0.6', label='the dish floor above it (2.5 mm)')
    ax.plot([], [], color=ORA, lw=3, label='support, 0.2 to 1.9 mm above the bed')
    for t in (20, 140, 260):
        t = math.radians(t)
        ax.annotate('', xy=(52 * math.cos(t), 52 * math.sin(t)), xytext=(36 * math.cos(t), 36 * math.sin(t)), arrowprops=dict(arrowstyle='->', color=ORA, lw=2.2))
    ax.set_xlim(-58, 62); ax.set_ylim(-58, 58); ax.set_aspect('equal'); ax.legend(loc='lower left', fontsize=8)
    ax.set_title('Seen from the bed side: the thin support under the dish\npeels off outward all round', fontsize=11)
    fig.suptitle('Hub rev D3c7 print file: where the support is (6.5 g of 81.9 g) and how it comes out', fontsize=14)
    fig.tight_layout()
    fig.savefig(out, dpi=105)
    print('saved', out)


if __name__ == '__main__' and '--picture' in sys.argv:
    from swk import WIP as _W
    picture(main(), _W.parents[2] / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'hub_print' / 'HUB_SUPPORT_REMOVAL.png')
