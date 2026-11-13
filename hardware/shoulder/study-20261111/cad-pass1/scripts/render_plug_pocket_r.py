"""Plug pocket, radial plug: today's clocking (sockets 188 / 8 deg) against the mock-up LOOK=pp_r (RS02 re-clocked +40 deg,
sockets 228 / 48 deg, plug channel). The plug + folded lead envelope (radial from the socket face r 36.17 to 10 mm past the
flange, r 49.25; 15.5 wide; Y 353.9-361.1, the height assumed from the XT30(2+2) data) is drawn in orange: anything orange
in a picture breaks the outline. Also sections at Y 355 / 357.5 / 360, a radial section through the plug, an unrolled map
of the lead route along the socket tap, and the wall left outside the envelope.
python render_plug_pocket_r.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

import render_pass1 as R
from shapely.geometry import Polygon
from shapely import affinity
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
ORANGE = (0.95, 0.55, 0.1)
R0, R1, WID, YP = 36.17, 49.25, 15.5, (353.9, 361.1)


def yaw_rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    M = np.eye(4)
    M[0, 0], M[0, 2], M[2, 0], M[2, 2] = c, -s, s, c      # yaw angle atan2(z - YZ, x - RX) grows by deg
    M[0, 3] = RX - (c * RX - s * YZ)
    M[2, 3] = YZ - (s * RX + c * YZ)
    return M


def plug_box(theta, clip=None):
    """The envelope as a solid; clip: keep Z - YZ >= clip (pp_r: clear of the fork joint's insert bore)."""
    from shapely.geometry import box as sbox
    P_ = affinity.rotate(Polygon([(R0, -WID / 2), (R1, -WID / 2), (R1, WID / 2), (R0, WID / 2)]), theta, origin=(0, 0))
    if clip is not None:
        P_ = P_.intersection(sbox(-80, clip, 80, 80))
    xy = np.asarray(P_.exterior.coords)[:-1]       # convex: the hull of its corners at both heights
    pts = np.vstack([np.c_[xy[:, 0] + RX, np.full(len(xy), h), xy[:, 1] + YZ] for h in YP])
    b = trimesh.convex.convex_hull(pts)
    return b, P_


# build_asm.T_RS02 carries the clock in force (re-clocked +40 deg since the adoption): turn the other one from it
if RS02_RECLOCK:
    rs02_r = R.M['rs02']; rs02_now = R.M['rs02'].copy(); rs02_now.apply_transform(yaw_rot(-40.0))
else:
    rs02_now = R.M['rs02']; rs02_r = R.M['rs02'].copy(); rs02_r.apply_transform(yaw_rot(40.0))
VAR = {
    'now': ('Today: RS02 sockets 188 / 8 deg, plug envelope on 188 (orange)', W / 'stl_now_pre_pp_r', rs02_now, 188.0, None),
    'ppr': ('Mock-up pp_r: RS02 re-clocked +40 deg, plug on 228 (orange)', W / 'stl_look_pp_r', rs02_r, 228.0, -39.4),
}
F = np.array([RX - 30, 368.0, 0.0])
VIEWS = [('inboard_side', F + np.array([-600.0, 0.0, 0.0])), ('front_inboard34', F + np.array([-420.0, 60.0, 420.0])),
         ('back_inboard34', F + np.array([-420.0, 60.0, -420.0])), ('front', F + np.array([30.0, 20.0, 600.0])),
         ('back', F + np.array([30.0, 20.0, -600.0])), ('below_inboard', F + np.array([-380.0, -300.0, 150.0])),
         ('outboard_side', F + np.array([600.0, 0.0, 0.0])), ('back_outboard34', F + np.array([420.0, 60.0, -420.0]))]
for v, (title, d_, rs02, th, clip) in VAR.items():
    P = dict(R.P)
    P['fork_front'] = trimesh.load(d_ / 'fork_front.stl'); P['access_plugs'] = trimesh.load(d_ / 'access_plugs.stl')
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k != 'cover']
    it += [(m if k != 'rs02' else rs02, R.COL[k], 1.0) for k, m in R.M.items()]
    it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    it += [(plug_box(th, clip)[0], ORANGE, 1.0)]
    for vn, eye in VIEWS:
        R.render(it, OUT / f'{v}_{vn}.png', eye, F, size=(1000, 1000), angle=24, title=f'{title}: {vn}')
    # from above-inboard: the dome top, where the RS02 access plugs show (64 / 104 today, 104 / 144 in pp_r)
    R.render(it, OUT / f'{v}_top.png', F + np.array([-330.0, 520.0, 160.0]), F + np.array([10.0, 70.0, 0.0]), up=(0, 1, 0), size=(1000, 1000), angle=26,
             title=f'{title}: top (access plugs)')
CW = 700
sheet = Image.new('RGB', (2 * CW, CW * len(VIEWS)), 'white')
for j, (vn, _) in enumerate(VIEWS):
    for i, v in enumerate(VAR):
        sheet.paste(Image.open(OUT / f'{v}_{vn}.png').convert('RGB').resize((CW, CW)), (i * CW, j * CW))
sheet.save(OUT / 'SHEET_radial_plug.png')
top = Image.new('RGB', (2 * CW, CW), 'white')
for i, v in enumerate(VAR):
    top.paste(Image.open(OUT / f'{v}_top.png').convert('RGB').resize((CW, CW)), (i * CW, 0))
top.save(OUT / 'SHEET_top_access_plugs.png')

# ------------------------------------------------------------------------------------------------ sections and numbers
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FF = {v: trimesh.load(VAR[v][1] / 'fork_front.stl') for v in VAR}
fig, axs = plt.subplots(2, 3, figsize=(18, 12.5), dpi=100)
for row, v in enumerate(VAR):
    th = VAR[v][3]
    for ax, y_ in zip(axs[row], (355.0, 357.5, 360.0)):
        s = FF[v].section(plane_origin=(0, y_, 0), plane_normal=(0, 1, 0))
        for p in s.discrete:
            p = np.asarray(p)[:, [0, 2]] - [RX, YZ]
            ax.fill(p[:, 0], p[:, 1], color='0.78', lw=0)
            ax.plot(np.r_[p[:, 0], p[0, 0]], np.r_[p[:, 1], p[0, 1]], color='0.3', lw=0.6)
        box = plug_box(th, VAR[v][4])[1]
        x, z = box.exterior.xy
        ax.fill(x, z, color='tab:orange', alpha=0.45 if YP[0] <= y_ <= YP[1] else 0.12, lw=1)
        t = np.linspace(0, 2 * np.pi, 300)
        ax.plot(R0 * np.cos(t), R0 * np.sin(t), 'k--', lw=0.6)
        ax.set_aspect('equal'); ax.set_xlim(-72, 72); ax.set_ylim(-72, 72)
        ax.set_title(f'{v}: fork front at Y {y_} (socket Y 354.9-360.1), plug on {th:.0f} deg', fontsize=9)
fig.suptitle('Grey: fork front section (X - RX, Z - YZ). Orange: plug + folded lead envelope (r 36.17-49.25, 15.5 wide). '
             'Dashed: socket face r 36.17.', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / 'sections_Y355_3575_360.png'); plt.close(fig)


def radial_section(m, th):
    """The section in the half-plane through the yaw axis at yaw angle th, as (r, Y) loops."""
    a = math.radians(th)
    n = (-math.sin(a), 0.0, math.cos(a))
    s = m.section(plane_origin=(RX, 0, YZ), plane_normal=n)
    out = []
    for p in s.discrete:
        p = np.asarray(p)
        r = (p[:, 0] - RX) * math.cos(a) + (p[:, 2] - YZ) * math.sin(a)
        out.append(np.c_[r, p[:, 1]])
    return out


fig, axs = plt.subplots(1, 2, figsize=(14, 7), dpi=110)
for ax, v in zip(axs, VAR):
    th = VAR[v][3]
    for p in radial_section(FF[v], th):
        ax.plot(p[:, 0], p[:, 1], color='0.25', lw=0.8)
    ax.add_patch(plt.Rectangle((R0, YP[0]), R1 - R0, YP[1] - YP[0], color='tab:orange', alpha=0.4))
    ax.add_patch(plt.Rectangle((R0, 354.9), 0.6, 5.2, color='k'))
    ax.set_xlim(20, 75); ax.set_ylim(335, 395); ax.set_aspect('equal'); ax.grid(lw=0.3)
    ax.set_xlabel('r from the yaw axis (mm)'); ax.set_ylabel('Y (mm)')
    ax.set_title(f'{v}: radial section through the plug at {th:.0f} deg (orange: plug + lead envelope; black: socket face)', fontsize=9)
fig.tight_layout(); fig.savefig(OUT / 'section_radial_through_plug.png'); plt.close(fig)

# lead route: material at r 42 / 45 / 48 against yaw angle and Y (rays along +Y), unrolled from -180 to -80 deg
fig, axs = plt.subplots(len(VAR), 1, figsize=(13, 9), dpi=100)
for ax, v in zip(axs, VAR):
    m = FF[v]
    for rr, col in ((42.0, '0.25'), (45.0, '0.5'), (48.0, '0.75')):
        ths = np.arange(-180.0, -79.0, 0.5)
        o = np.c_[RX + rr * np.cos(np.radians(ths)), np.full(len(ths), 330.0), YZ + rr * np.sin(np.radians(ths))]
        loc, idx, _ = m.ray.intersects_location(o, np.tile([0, 1.0, 0], (len(o), 1)), multiple_hits=True)
        for i in range(len(ths)):
            ys = np.sort(loc[idx == i, 1]); ys = ys[ys < 380.0]
            for a_, b_ in zip(ys[0::2], ys[1::2]):
                ax.plot([ths[i], ths[i]], [a_, b_], color=col, lw=1.6, alpha=0.6)
    th = VAR[v][3] - 360.0
    ax.add_patch(plt.Rectangle((th - 12.0, YP[0]), 24.0, YP[1] - YP[0], fill=False, ec='tab:orange', lw=1.2))
    ax.set_xlim(-180, -80); ax.set_ylim(345, 372); ax.grid(lw=0.3)
    ax.set_title(f'{v}: fork front material at r 42 (dark) / 45 / 48 (light) along the socket tap; orange: plug envelope', fontsize=9)
axs[-1].set_xlabel('yaw angle (deg)')
fig.tight_layout(); fig.savefig(OUT / 'lead_route_unrolled.png'); plt.close(fig)

# the wall outside the envelope: from the envelope's outer face and sides, outward to the first surface
for v in VAR:
    m, th = FF[v], VAR[v][3]
    a = math.radians(th); u = np.array([math.cos(a), 0, math.sin(a)]); t_ = np.array([-math.sin(a), 0, math.cos(a)])
    c0 = np.array([RX, 0.0, YZ])
    res = []
    for y_ in np.linspace(YP[0] + 0.3, YP[1] - 0.3, 7):
        for w_ in np.linspace(-WID / 2 + 0.3, WID / 2 - 0.3, 9):
            o = c0 + u * 20.0 + t_ * w_ + np.array([0, y_, 0])
            loc, _, _ = m.ray.intersects_location([o], [u], multiple_hits=True)
            if len(loc):
                res.append(np.linalg.norm(loc - o, axis=1).max() + 20.0 - R1)   # outermost skin along the ray, past r 49.25
    res = np.array(res)
    print(f'{v}: wall from the envelope (r {R1}) to the outer skin along the radial: min {res.min():.2f}, median {np.median(res):.2f} mm '
          f'(negative: the envelope breaks through), {len(res)} rays')
print('done')
