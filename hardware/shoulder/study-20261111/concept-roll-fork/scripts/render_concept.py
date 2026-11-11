"""Pictures for the roll drum and fork concept (VTK off-screen + matplotlib sections).

    python render_concept.py STUDY_WORK CONCEPT_OUT PICTURE_DIR

STUDY_WORK: folder of the measurement study's torso.py / mesh.py output with rv.py; CONCEPT_OUT: build_concept.py output.
"""
import sys, os
import numpy as np, trimesh
from PIL import Image, ImageDraw, ImageFont

W, C, OUTD = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, W); os.chdir(W)
from rv import load_all, render
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RX, RY, PZ, YZ = 170.49, 424.86, -0.014, 5.99
TEAL, TEAL2, ORANGE, ORANGE2 = (0.05, 0.55, 0.55), (0.12, 0.64, 0.64), (0.93, 0.5, 0.15), (0.97, 0.62, 0.28)
WHITE, GREY, STEEL, RED, BLUE = (0.96, 0.96, 0.94), (0.45, 0.47, 0.5), (0.74, 0.77, 0.8), (0.85, 0.1, 0.1), (0.1, 0.25, 0.85)
FRAMEC, SAGE, ARM = (0.78, 0.8, 0.83), (0.62, 0.68, 0.6), (0.86, 0.87, 0.89)
d = load_all()
L = lambda k: trimesh.load(os.path.join(C, k + '.stl'))
cp = {k: L(k) for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'PITCH_cover',
                        'BRG_6808', 'VAR_E_sleeve', 'VAR_E_6816', 'VAR_E_hubband']}
wires = {}
for f in os.listdir(C):
    if f.startswith('WIRE_') and f.endswith('.stl'):
        wires[f[5:-4]] = trimesh.load(os.path.join(C, f))
COLC = dict(P1_drum=TEAL, P1_cap=TEAL2, FORK_front=ORANGE, FORK_rear=ORANGE, FORK_front_cap=ORANGE2, HUB_dished=WHITE,
            PITCH_cover=SAGE, BRG_6808=STEEL, ROLL=GREY, YAW=GREY, PITCH=GREY, FRAME=FRAMEC, PBRK=SAGE, UA=ARM)


def Rx(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def T(R, o):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = o - R @ o; return M


GROUP = dict(P1_drum='p', P1_cap='p', ROLL='p', BRG_6808='r', FORK_front='r', FORK_rear='r', FORK_front_cap='r', YAW='r',
             HUB_dished='y', UA='y', VAR_E_sleeve='r', VAR_E_6816='r', VAR_E_hubband='y',
             P1='p', P2='r', SPACER='r', HUB='y')


def posed(m, k, p=0, r=0, y=0):
    m = m.copy(); g = GROUP.get(k)
    if k.startswith('W:'):
        g = {'P1': 'p', 'CAP': 'p', 'STUB': 'p', 'FORK': 'r', 'YAWEXIT': 'r', 'YAWLOOP': 'y', 'HUBWIN': 'y'}.get(k[2:].split('_')[0])
    if g == 'y': m.apply_transform(T(Ry(y), np.array([RX, 0, YZ])))
    if g in ('y', 'r'): m.apply_transform(T(Rz(r), np.array([RX, RY, 0])))
    if g in ('y', 'r', 'p'): m.apply_transform(T(Rx(-p), np.array([0, RY, PZ])))
    return m


def concept_items(p=0, r=0, y=0, frame=True, arm=True, wire=True, offs=None, skip=()):
    it = []
    keys = ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'PITCH_cover', 'BRG_6808']
    for k in keys:
        if k in skip: continue
        m = posed(cp[k], k, p, r, y)
        if offs and k in offs: m.apply_translation(offs[k])
        it.append((m, COLC[k]))
    for k in ['ROLL', 'YAW', 'PITCH']:
        m = posed(d[k], k, p, r, y)
        if offs and k in offs: m.apply_translation(offs[k])
        it.append((m, GREY))
    if frame:
        it += [(d['FRAME'], FRAMEC), (d['PBRK'], SAGE)]
    if arm:
        m = posed(d['UA'], 'UA', p, r, y)
        if offs and 'UA' in offs: m.apply_translation(offs['UA'])
        it.append((m, ARM))
    if wire:
        for k, m in wires.items():
            mm = posed(m, 'W:' + k, p, r, y)
            grp = k.split('_')[0]
            o = None
            if offs:
                o = {'P1': 'P1_drum', 'CAP': 'P1_cap', 'STUB': 'P1_cap', 'FORK': 'FORK_rear', 'YAWEXIT': 'FORK_front',
                     'YAWLOOP': 'HUB_dished', 'HUBWIN': 'HUB_dished', 'PITCHLOOP': 'PITCH_cover'}.get(grp)
                if o in offs: mm.apply_translation(offs[o])
            it.append((mm, RED if k.endswith('power') else BLUE))
    return it


def today_items(frame=True, arm=True):
    it = [(d['P1'], TEAL), (d['P2'], ORANGE), (d['SPACER'], ORANGE2), (d['HUB'], WHITE)]
    it += [(d[k], GREY) for k in ['ROLL', 'YAW', 'PITCH']]
    if frame: it += [(d['FRAME'], FRAMEC), (d['PBRK'], SAGE)]
    if arm: it.append((d['UA'], ARM))
    return it


try:
    FONT = ImageFont.truetype('arialbd.ttf', 26); FONTS = ImageFont.truetype('arial.ttf', 20)
except Exception:
    FONT = FONTS = ImageFont.load_default()


def title(path, text, sub=None):
    im = Image.open(path).convert('RGB'); dr = ImageDraw.Draw(im)
    dr.text((24, 18), text, fill=(30, 30, 35), font=FONT)
    if sub: dr.text((24, 52), sub, fill=(70, 70, 80), font=FONTS)
    im.save(path)


def legend(path, entries, x0=24, y0=None):
    im = Image.open(path).convert('RGB'); dr = ImageDraw.Draw(im); H = im.size[1]
    y = y0 if y0 is not None else H - 30 * len(entries) - 20
    for lab, col in entries:
        dr.rectangle([x0, y + 4, x0 + 22, y + 22], fill=tuple(int(255 * c) for c in col), outline=(80, 80, 80))
        dr.text((x0 + 32, y + 2), lab, fill=(40, 40, 45), font=FONTS); y += 30
    im.save(path)


def fin(path, name):
    im = Image.open(path).convert('RGB').quantize(256, dither=Image.Dither.NONE)
    out = os.path.join(OUTD, name); im.save(out, optimize=True)
    print(name, os.path.getsize(out) // 1024, 'kB')


LEG = [('P1 drum and rear cap', TEAL), ('fork (P2) and caps', ORANGE), ('shoulder hub (dished top)', WHITE),
       ('RobStride motors (vendor models)', GREY), ('6808 bearing', STEEL), ('power passage', RED), ('signal passage', BLUE),
       ('pitch loop cover (torso side)', SAGE)]
tmp = os.path.join(W, '_r.png')

# 1 overall front-outboard
render(concept_items(), tmp, pos=(520, 560, 520), focal=(140, 380, 0), size=(1400, 1050))
title(tmp, 'Roll drum and fork concept: front-outboard view', 'neutral pose, cage corner, torso pitch mount, frozen upper arm')
legend(tmp, LEG); fin(tmp, 'C1_overall_front_outboard.png')
# 2 back view
render(concept_items(), tmp, pos=(420, 560, -560), focal=(130, 395, -10), size=(1400, 1050))
title(tmp, 'Back-outboard view', 'rear cap with stub, 6808 in the fork rear cheek, cable duct down the rear arm, roll stop lugs')
legend(tmp, LEG); fin(tmp, 'C2_overall_back.png')
# 3 exploded
offs = {'PITCH_cover': (-45, 0, 0), 'ROLL': (0, 0, -95), 'P1_cap': (0, 0, -175), 'BRG_6808': (0, 0, -205),
        'FORK_rear': (0, 0, -240), 'FORK_front': (0, 0, 75), 'FORK_front_cap': (0, 0, 115), 'YAW': (0, -45, 75),
        'HUB_dished': (0, -95, 75), 'UA': (0, -150, 75)}
render(concept_items(frame=False, offs=offs), tmp, pos=(750, 720, 420), focal=(150, 345, -60), size=(1500, 1100), scale=250)
title(tmp, 'Exploded along the chain', 'service order: fork rear -> cap -> roll RS03 slides out of the drum to the rear; fork front with RS02/hub/arm off the roll output')
legend(tmp, LEG); fin(tmp, 'C3_exploded.png')


# 4 sagittal section through the roll and yaw axes (plane X = 170.49) with the projected cable path
def section(ax, meshes, origin, normal, ix, wire_alpha=0.85):
    for m, col, lab in meshes:
        s = m.section(plane_origin=origin, plane_normal=normal)
        if s is None: continue
        for e in s.discrete:
            P_ = e[:, ix]
            closed = np.linalg.norm(P_[0] - P_[-1]) < 1e-3
            if closed: ax.fill(P_[:, 0], P_[:, 1], color=col, alpha=wire_alpha if lab == 'w' else 0.55, lw=0)
            ax.plot(P_[:, 0], P_[:, 1], color=np.array(col) * 0.6, lw=0.8)


fig, ax = plt.subplots(figsize=(11, 11))
ms = [(posed(cp[k], k), COLC[k], k) for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'BRG_6808']]
ms += [(d[k], GREY, k) for k in ['ROLL', 'YAW']] + [(d['UA'], ARM, 'UA')]
ms += [(m, RED if k.endswith('power') else BLUE, 'w') for k, m in wires.items()]
section(ax, ms, (RX, 0, 0), (1, 0, 0), [2, 1])
# projected route centreline (fixed cage side -> pitch loop -> P1 trunk -> cap -> stub -> fork rear arm -> finger -> yaw loop -> hub window)
route = np.array([(-79, 430.9), (-64, 430.9), (0, 489), (-28.5, 489), (-34.5, 489), (-34.5, RY), (-52, RY), (-52, 364),
                  (2.99, 364), (2.99, 319.5), (YZ, 319.5), (YZ + 8, 307), (YZ + 2, 296)])
ax.plot(route[:, 0], route[:, 1], color=RED, lw=2.2, ls='--', label='cable route, projected onto this plane')
for (z, y, t) in [(-79, 436, 'from cage back face'), (-2, 494, 'P1 trunk over the drum'), (-60, 452, 'stub bore\n(roll crossing)'),
                  (-74, 380, 'down the\nfork rear arm'), (12, 340, 'finger beside\nthe RS02'), (30, 314, 'yaw loop under\nthe RS02 (7.5 mm)'),
                  (22, 297, 'hub window into\nthe arm opening')]:
    ax.annotate(t, (z, y), fontsize=8.5, bbox=dict(fc='white', ec='0.6', alpha=0.85))
ax.axhline(RY, color='k', ls='-.', lw=0.7); ax.axvline(YZ, color='k', ls='-.', lw=0.7)
ax.text(62, RY + 1, 'pitch axis height', fontsize=8); ax.text(YZ + 1, 268, 'yaw axis', fontsize=8)
ax.set_xlim(-95, 75); ax.set_ylim(260, 505); ax.set_aspect('equal'); ax.grid(alpha=0.25)
ax.set_xlabel('Z (mm, + forward)'); ax.set_ylabel('Y (mm, up)')
ax.set_title('Section X = 170.49 (through the roll and yaw axes), looking inboard; cable route projected', fontsize=11)
hs = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.6) for _, c in LEG[:7]] + [plt.Line2D([0], [0], color=RED, ls='--')]
ax.legend(hs, [l for l, _ in LEG[:7]] + ['cable route (projected)'], fontsize=8, loc='lower left')
fig.tight_layout(); fig.savefig(tmp, dpi=100); plt.close(fig); fin(tmp, 'C4_section_roll_yaw_cable.png')


# 5 yaw crossing close-up: 3D cut-away (everything cut at Z = YZ - 3, the finger centreline; keep the back half)
def cut(m, o, n):
    try:
        return trimesh.intersections.slice_mesh_plane(m, plane_normal=n, plane_origin=o, cap=True)
    except Exception:
        return trimesh.intersections.slice_mesh_plane(m, plane_normal=n, plane_origin=o, cap=False)


o, n = (0, 0, YZ - 3), (0, 0, -1)
it = [(cut(posed(cp[k], k), o, n), COLC[k]) for k in ['FORK_front', 'HUB_dished']]
it += [(cut(d['YAW'], o, n), GREY), (cut(d['UA'], o, n), ARM)]
for k in ['FORK_power', 'FORK_signal', 'YAWEXIT_power', 'YAWLOOP_power', 'YAWLOOP_signal', 'HUBWIN_power']:
    if k in wires: it.append((cut(wires[k], o, n), RED if k.endswith('power') else BLUE))
render(it, tmp, pos=(260, 380, 330), focal=(160, 333, -8), size=(1400, 1000), scale=62)
title(tmp, 'Yaw crossing close-up (cut at the finger centreline, looking at the cut face)',
      'finger down the inboard side of the RS02 -> annular loop in the dished hub top (7.5 mm under the RS02) -> hub window -> arm opening')
legend(tmp, [('fork with finger', ORANGE), ('hub, dished top', WHITE), ('RS02 / upper arm', GREY), ('power / arm bundle', RED), ('signal', BLUE)])
fin(tmp, 'C5_yaw_crossing_closeup.png')

# 6 roll pose strip: -20 / 0 / +110, from the front
ims = []
for r_ in (-20, 0, 110):
    render(concept_items(r=r_), tmp, pos=(140, 420, 700), focal=(140, 400, 0), size=(800, 1000), scale=230)
    title(tmp, f'roll {r_:+d} deg' if r_ else 'roll 0'); ims.append(Image.open(tmp).convert('RGB'))
strip = Image.new('RGB', (2400, 1000), (245, 247, 250))
for i, im in enumerate(ims): strip.paste(im, (800 * i, 0))
strip.save(tmp); title(tmp, '', None)
dr = ImageDraw.Draw(strip)
strip.save(tmp); fin(tmp, 'C6_roll_pose_strip.png')

# 7 today vs concept, front and back
pairs = []
for name, view in [('front', dict(pos=(170, 420, 700), focal=(150, 395, 0))), ('back', dict(pos=(170, 420, -700), focal=(150, 395, 0)))]:
    row = []
    for lab, items in [('today (P1 L01, P2 L04B, PF03, hub)', today_items()), ('concept (drum, cap, fork, dished hub)', concept_items(wire=False))]:
        render(items, tmp, size=(900, 900), scale=170, **view)
        title(tmp, f'{lab}: {name}'); row.append(Image.open(tmp).convert('RGB'))
    pairs.append(row)
grid = Image.new('RGB', (1800, 1800), (245, 247, 250))
for i, row in enumerate(pairs):
    for j, im in enumerate(row): grid.paste(im, (900 * j, 900 * i))
grid.save(tmp); fin(tmp, 'C7_today_vs_concept.png')

# 8 variant e: yaw ring (sleeve + 6816 + enlarged hub band), cut-away
o, n = (0, 0, YZ), (0, 0, -1)
it = [(cut(posed(cp[k], k), o, n), c) for k, c in [('VAR_E_sleeve', ORANGE), ('VAR_E_6816', STEEL), ('VAR_E_hubband', WHITE),
                                                     ('FORK_front', ORANGE2)]]
it += [(cut(d['YAW'], o, n), GREY), (cut(d['HUB'], o, n), WHITE), (cut(d['UA'], o, n), ARM), (cut(d['ROLL'], o, n), GREY),
       (cut(cp['P1_drum'], o, n), TEAL)]
render(it, tmp, pos=(420, 420, 380), focal=(165, 345, -5), size=(1400, 1000), scale=82)
title(tmp, 'Variant e "yaw ring": fork seat extended as a sleeve round the RS02, 6816 (80x100x10) on a Ø80 hub band',
      'cut at the yaw axis; cuff OD 108; the sleeve closes the side entry used by the yaw cable loop (see CONCEPT.md)')
legend(tmp, [('sleeve (fork)', ORANGE), ('6816', STEEL), ('hub band Ø80 (on the hub)', WHITE), ('RS02', GREY)])
fin(tmp, 'C8_variant_e_yaw_ring.png')
print('done')
