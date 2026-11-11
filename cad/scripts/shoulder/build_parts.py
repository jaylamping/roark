"""Left shoulder, roll drum and fork: the printed parts as SolidWorks parts (first pass).

    python build_parts.py [drum ring cap fork_front fork_rear fork_cap hub cover bearing]   (default: all)

Every part is modelled in the torso frame (dims.py), so the assembly places each at the origin. Saves to cad/shoulder/left/
and a fine STL of each to cad/_wip/shoulder-pass1/stl/ for the checks and pictures.
"""
import math
import sys

import numpy as np

from dims import *
from swk import *

STL = WIP / 'stl'
STL.mkdir(parents=True, exist_ok=True)
STEPD = WIP / 'step'
STEPD.mkdir(parents=True, exist_ok=True)
NAMES = {
    'drum': 'shoulder_roll_drum_left', 'ring': 'shoulder_pitch_flange_ring_left', 'cap': 'shoulder_roll_cap_left',
    'fork_front': 'shoulder_fork_front_left', 'fork_rear': 'shoulder_fork_rear_left', 'fork_cap': 'shoulder_fork_cap_left',
    'hub': 'shoulder_hub_left', 'cover': 'shoulder_pitch_loop_cover_left',
}
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
NX, NY, NZ = (-1, 0, 0), (0, -1, 0), (0, 0, -1)


# --------------------------------------------------------------------------------------------- revolve sketches by axis
def roll_rev(d, name, prof, radii=None, cut=False):
    """(r, z) profile about the roll axis."""
    pl = plane(d, 'Y', RY, 'P_Y_RY')
    with Sk(d, pl, name) as s:
        s.rpoly([(RX + r, RY, z) for r, z in prof], radii or [0] * len(prof))
        s.cline((RX, RY, -150), (RX, RY, 150))
    return revolve(d, s.feat, name, cut)


def pitch_rev(d, name, prof, radii=None, cut=False):
    """(r, x) profile about the pitch axis."""
    pl = plane(d, 'Z', PZ, 'P_Z_PZ')
    with Sk(d, pl, name) as s:
        s.rpoly([(x, RY + r, PZ) for r, x in prof], radii or [0] * len(prof))
        s.cline((0, RY, PZ), (250, RY, PZ))
    return revolve(d, s.feat, name, cut)


def yaw_rev(d, name, prof, radii=None, cut=False):
    """(r, y) profile about the yaw axis."""
    pl = plane(d, 'Z', YZ, 'P_Z_YZ')
    with Sk(d, pl, name) as s:
        s.rpoly([(RX + r, y, YZ) for r, y in prof], radii or [0] * len(prof))
        s.cline((RX, 250, YZ), (RX, 550, YZ))
    return revolve(d, s.feat, name, cut)


def zsk(d, z, name, draw):
    """Sketch on the plane Z = z; draw(s) adds the geometry."""
    with Sk(d, plane(d, 'Z', z, f'P_Z_{z:g}'.replace('.', 'p').replace('-', 'm')), name) as s:
        draw(s)
    return s.feat


def xsk(d, x, name, draw):
    with Sk(d, plane(d, 'X', x, f'P_X_{x:g}'.replace('.', 'p').replace('-', 'm')), name) as s:
        draw(s)
    return s.feat


def ysk(d, y, name, draw):
    with Sk(d, plane(d, 'Y', y, f'P_Y_{y:g}'.replace('.', 'p').replace('-', 'm')), name) as s:
        draw(s)
    return s.feat


def rpt(r, a, z):
    return roll_pt(r, a, z)


def radial_rect(c, r0, r1, a, w, z):
    """Rectangle along the radial direction a (deg) about centre c in the plane Z = z."""
    t = math.radians(a)
    u = (math.cos(t), math.sin(t), 0.0)
    v = (-math.sin(t), math.cos(t), 0.0)
    rm = (r0 + r1) / 2
    cc = (c[0] + rm * u[0], c[1] + rm * u[1], z)
    return rect_pts(cc, u, v, r1 - r0, w)


def finish_part(d, key, props=None):
    d.ForceRebuild3(False)
    stamp_props(d, dict(Material='PETG', Density='1.27 g/cc', **(props or {})))
    save(d)
    export(d, STL / f'{key}.stl')
    export(d, STEPD / f'{key}.step', stl_fine=False)
    v = vol(d)
    bb = [b for b in bodies(d)]
    log(f'== {NAMES.get(key, key)}: {len(bb)} bodies, {v:.0f} mm3, {v * PETG:.1f} g PETG', bb)
    app().CloseDoc(d.GetTitle)
    return v


# ================================================================================================================= drum
def build_drum():
    d = new_part(OUT / f"{NAMES['drum']}.SLDPRT")
    # pitch adaptor first: pad and neck, clipped to the drum's Z span before anything else exists
    pitch_rev(d, 'PAD', [(0, PAD_X[0]), (PAD_R, PAD_X[0]), (PAD_R, PAD_X[1]), (0, PAD_X[1])], [0, 1.0, 0, 0])
    n = NECK
    pitch_rev(d, 'NECK', [(n['ri_core'], n['x0']), (n['ro'], n['x0']), (n['ro'], n['x1']), (n['ri'], n['x1']), (n['ri'], n['x_disc']),
                          (n['ri_core'], n['x_disc'])], [0, 2.0, 0, 0, 1.0, 0])
    fl = FLARE
    pitch_rev(d, 'FLARE', [(n['ri'], fl['x0']), (n['ro'], fl['x0']), (n['ro'], fl['x1']), (fl['r'], fl['x1']), (fl['r'], fl['x2']), (n['ri'], fl['x2'])],
              [0, 0, fl['fillet'], 3.0, 0, 0])
    # the flare's lower part is where the fork front's tap sector and the RS02 swing in at the inward stop: trim it
    extrude(d, zsk(d, DRUM_Z0 - 2, 'FLARE_TRIM', lambda s: s.poly(rect_pts(((108 + 127) / 2, RY - 41 - 30, DRUM_Z0 - 2), X, Y, 19, 60))), 'FLARE_TRIM', 80, Z, cut=True)
    sk = zsk(d, LIP_Z1, 'CLIP_FRONT', lambda s: s.poly(rect_pts((115, RY, LIP_Z1), X, Y, 60, 100)))
    extrude(d, sk, 'CLIP_FRONT', 40, Z, cut=True)
    sk = zsk(d, DRUM_Z0 + 1, 'CLIP_REAR', lambda s: s.poly(rect_pts((115, RY, DRUM_Z0 + 1), X, Y, 60, 100)))
    extrude(d, sk, 'CLIP_REAR', 40, NZ, cut=True)
    # drum: smooth revolved wall with a rounded rear rim and a rounded front lip
    # DRESSED: one closed drum, r 48-57, rounded rear rim and a full round on the front lip; pockets under the skin below
    roll_rev(d, 'DRUM', [(DRUM_RI, DRUM_Z0), (DRUM_RO, DRUM_Z0), (DRUM_RO, LIP_Z1), (LIP_RI, LIP_Z1), (LIP_RI, LIP_Z0), (DRUM_RI, LIP_Z0)],
             [0, 1.5, 5.0, 0.8, 0, 0])
    # cap ears
    extrude(d, zsk(d, DRUM_Z0, 'EARS', lambda s: [s.circle(rpt(EAR_PCD, a, DRUM_Z0), EAR_R) for a in EAR_ANGLES]), 'EARS', 9.0, Z)
    # spokes for the flange ring
    sp = SPOKES

    def spokes(s):
        for k in range(sp['n']):
            a = sp['a0'] + 360 / sp['n'] * k
            t = math.radians(a)
            u = (0, math.cos(t), math.sin(t))
            v = (0, -math.sin(t), math.cos(t))
            rm = (sp['r0'] + sp['r1']) / 2
            c = pitch_pt(rm, a, sp['x0'])
            s.rpoly(rect_pts(c, u, v, sp['r1'] - sp['r0'], sp['w']), [0, 2.0, 2.0, 0])
    extrude(d, xsk(d, sp['x0'], 'SPOKES', spokes), 'SPOKES', sp['x1'] - sp['x0'], X)
    # cable trunk: along X over the neck from the mouth at X 100.5, then down along -Z at X 140, and a branch to the top bay
    extrude(d, xsk(d, NECK['x0'], 'TRUNK_A', lambda s: s.rpoly(rect_pts((NECK['x0'], TRUNK_Y, 0.0), Z, Y, SHW, SHH), [2, 2, 2, 2])),
            'TRUNK_A', TRUNK_X + 4 + WALL - NECK['x0'], X)
    tu = np.array(TU) / np.linalg.norm(TU)
    tv = np.array([tu[1], -tu[0], 0.0])
    extrude(d, zsk(d, 4 + WALL, 'TRUNK_B', lambda s: s.rpoly(rect_pts((TRUNK_X, TRUNK_Y, 4 + WALL), tu, tv, SHW, SHH), [2, 2, 2, 2])),
            'TRUNK_B', 4 + WALL - DRUM_Z0, NZ)
    b0, b1 = (TRUNK_X, TRUNK_Y, -17.0 + SHW / 2), (RX - 8, 474.5, -17.0 + SHW / 2)
    bn_ = np.cross((0, 0, 1), np.subtract(b1, b0))
    extrude(d, zsk(d, b0[2], 'BRANCH', lambda s: s.rpoly(seg_rect(b0, b1, (0, 0, 0) if False else np.cross((0, 0, 1), np.subtract(b1, b0)), SHH, 2 + WALL, 2 + WALL),
                                                         [2, 2, 2, 2])), 'BRANCH', b0[2] - DRUM_Z0, NZ)
    # DRESSED 2: spine fairing over trunk B and the branch, hollow from the back (opens toward the cap spoke)
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    tbr = Polygon([(p[0], p[1]) for p in rect_pts((TRUNK_X, TRUNK_Y, 0), tu, tv, SHW, SHH)])
    brr = Polygon([(p[0], p[1]) for p in seg_rect(b0, b1, bn_, SHH, 2 + WALL, 2 + WALL)])
    arc = [(RX + DRUM_RO * math.cos(math.radians(a)), RY + DRUM_RO * math.sin(math.radians(a))) for a in np.linspace(78, 142, 17)]
    hullp = unary_union([tbr, brr, Polygon(arc + [(RX, RY)])]).convex_hull
    hv = list(hullp.exterior.coords)[:-1]
    zf = 4 + WALL
    extrude(d, zsk(d, DRUM_Z0, 'SPINE', lambda s: s.rpoly([(x, y, DRUM_Z0) for x, y in hv], [4.0] * len(hv))), 'SPINE', zf - DRUM_Z0, Z)
    q = hullp.buffer(-WALL).difference(Point(RX, RY).buffer(DRUM_RO + WALL, 96)).difference(tbr.buffer(0.3)).difference(brr.buffer(0.3))
    polys = [g for g in getattr(q, 'geoms', [q]) if g.area > 40.0]
    if polys:
        def spine_pock(s):
            for g in polys:
                pts = list(g.simplify(0.3).exterior.coords)[:-1]
                s.poly([(x, y, DRUM_Z0 - 1) for x, y in pts])
        extrude(d, zsk(d, DRUM_Z0 - 1, 'SPINE_POCKET', spine_pock), 'SPINE_POCKET', zf - WALL - (DRUM_Z0 - 1), Z, cut=True)
    # DRESSED: soften the trunk shells (long edges)
    along_x = lambda a, b: abs(a[0] - b[0]) > 10.0 and abs(a[1] - b[1]) < 0.05 and abs(a[2] - b[2]) < 0.05
    fillet(d, edges_where(d, lambda p: p[1] > 482.0, along_x), [3.0, 2.0], 'TRUNK_A_ROUND')
    along_z = lambda a, b: abs(a[2] - b[2]) > 10.0 and abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) < 0.05
    fillet(d, edges_where(d, lambda p: p[1] > 470.0 and abs(p[0] - TRUNK_X) < 25.0 and p[2] < 7.0, along_z), [3.0, 2.0], 'TRUNK_B_ROUND')
    # ---- cuts
    roll_rev(d, 'BORE', [(0, DRUM_Z0 - 1), (DRUM_RI, DRUM_Z0 - 1), (DRUM_RI, LIP_Z0), (0, LIP_Z0)], cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'LUG_SLOTS', lambda s: [s.poly(radial_rect((RX, RY), 44.0, SLOT_R, th, 2 * SLOT_HALF, DRUM_Z0)) for th in LUG_ANGLES]),
            'LUG_SLOTS', LIP_Z0 - DRUM_Z0, Z, cut=True)
    extrude(d, zsk(d, LIP_Z0, 'LIP_HOLES', lambda s: [s.circle(rpt(LIP_PCD_R, a, LIP_Z0), 2.25) for a in LUG_ANGLES]), 'LIP_HOLES', 20, Z, cut=True)
    extrude(d, zsk(d, LIP_Z1 - 4.2, 'LIP_CB', lambda s: [s.circle(rpt(LIP_PCD_R, a, LIP_Z1 - 4.2), 4.8) for a in LUG_ANGLES]), 'LIP_CB', 10, Z, cut=True)
    pitch_rev(d, 'PAD_BORE', [(0, 95.0), (10.75, 95.0), (10.75, PAD_X[1]), (21.0, PAD_X[1]), (21.0, 131.0), (0, 131.0)], cut=True)
    extrude(d, xsk(d, 96.0, 'PAD_HOLES', lambda s: [s.circle(pitch_pt(15.2, a, 96.0), 2.25) for a in PAD_HOLES]), 'PAD_HOLES', 14, X, cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'EAR_INSERTS', lambda s: [s.circle(rpt(EAR_PCD, a, DRUM_Z0), 2.8) for a in EAR_ANGLES]), 'EAR_INSERTS', 8.5, Z, cut=True)
    extrude(d, xsk(d, sp['x1'], 'RING_INSERTS', lambda s: [s.circle(pitch_pt(sp['screw_r'], sp['a0'] + 72 * k, sp['x1']), 2.0) for k in range(5)]),
            'RING_INSERTS', sp['insert_depth'], NX, cut=True)
    # trunk channels
    def tch_a(s):
        s.rpoly(rect_pts((NECK['x0'] - 1, TRUNK_Y, P_OFF), Z, Y, PW, PH), [1, 1, 1, 1])
        s.rpoly(rect_pts((NECK['x0'] - 1, TRUNK_Y, S_OFF), Z, Y, SW, SH), [1, 1, 1, 1])
    extrude(d, xsk(d, NECK['x0'] - 1, 'TRUNK_A_CH', tch_a), 'TRUNK_A_CH', TRUNK_X + 4 - NECK['x0'] + 1, X, cut=True)

    def tch_b(s):
        c = np.array([TRUNK_X, TRUNK_Y, 4.0])
        s.rpoly(rect_pts(c + tu * P_OFF, tu, tv, PW, PH), [1, 1, 1, 1])
        s.rpoly(rect_pts(c + tu * S_OFF, tu, tv, SW, SH), [1, 1, 1, 1])
    extrude(d, zsk(d, 4.0, 'TRUNK_B_CH', tch_b), 'TRUNK_B_CH', 4.0 - DRUM_Z0 + 1, NZ, cut=True)
    bn = np.cross((0, 0, 1), np.subtract(b1, b0))
    zp, zs = -17.0 + P_OFF + PW / 2, -17.0 + S_OFF + SW / 2
    extrude(d, zsk(d, zp, 'BRANCH_P', lambda s: s.rpoly(seg_rect((b0[0], b0[1], zp), (b1[0], b1[1], zp), bn, PH, 2, 6), [1, 1, 1, 1])),
            'BRANCH_P', PW, NZ, cut=True)
    extrude(d, zsk(d, zs, 'BRANCH_S', lambda s: s.rpoly(seg_rect((b0[0], b0[1], zs), (b1[0], b1[1], zs), bn, SH, 2, 6), [1, 1, 1, 1])),
            'BRANCH_S', SW, NZ, cut=True)
    # pockets between the lug ribs, under the skin (rib half-width 8 at r 53)
    def pockets(s):
        for th in LUG_ANGLES:
            sector(s, lambda r, a: rpt(r, a, POCKET_Z[0]), WALL_RO, SKIN_RI, th + 9.0, th + 36.0, 1.5)
    extrude(d, zsk(d, POCKET_Z[0], 'POCKETS', pockets), 'POCKETS', POCKET_Z[1] - POCKET_Z[0], Z, cut=True)
    # window over the roll RS03 top connector bay, inside the skin (the branch channels open the skin where they pass)
    tw = TOPWIN
    extrude(d, zsk(d, DRUM_Z0 - 1, 'TOP_WINDOW', lambda s: s.rpoly(rect_pts((RX, RY + 47.25, DRUM_Z0 - 1), X, Y, 2 * tw['x'], 14.5), [3, 3, 3, 3])),
            'TOP_WINDOW', tw['z1'] - DRUM_Z0 + 1, Z, cut=True)
    rb = RS03_BUMP
    extrude(d, zsk(d, rb['z0'], 'RS03_RELIEF', lambda s: s.rpoly(rect_pts(((rb['x0'] + rb['x1']) / 2, RY, rb['z0']), X, Y, rb['x1'] - rb['x0'], 2 * rb['y']), [2] * 4)),
            'RS03_RELIEF', LIP_Z0 - rb['z0'], Z, cut=True)
    # four windows in the drum wall between the ribs
    ax = ref_axis(d, plane(d, 'X', RX, 'P_X_RX'), plane(d, 'Y', RY, 'P_Y_RY'), 'ROLL_AXIS')
    for k, th in enumerate(WIN_ANGLES):
        tdir = (math.cos(math.radians(th + 90)), math.sin(math.radians(th + 90)), 0)
        pl, _ = plane_axis_angle(d, ax, d.FeatureByName('Top Plane'), (th + 90) % 180, tdir, f'P_WIN{k}')
        with Sk(d, pl, f'WIN{k}') as s:
            s.slot((RX, RY, -11.0), (RX, RY, 15.0), 14.0)
        port = abs(th - PORT_ANGLE) < 1e-6
        extrude(d, s.feat, f'PORT' if port else f'WIN{k}', 80 if port else SKIN_RI - 1.8, (math.cos(math.radians(th)), math.sin(math.radians(th)), 0), cut=True,
                mode=THRU_ALL if port else BLIND)
    return finish_part(d, 'drum')


# ========================================================================================================== flange ring
def build_ring():
    d = new_part(OUT / f"{NAMES['ring']}.SLDPRT")
    rg = RING
    pitch_rev(d, 'RING', [(rg['ri'], rg['x0']), (rg['ro'], rg['x0']), (rg['ro'], rg['x1']), (rg['ri'], rg['x1'])], [0.5, 0.9, 0.9, 0.5])
    extrude(d, xsk(d, rg['x0'] - 1, 'TRUNK_HOLE', lambda s: s.rpoly(rect_pts((rg['x0'] - 1, TRUNK_Y, 0.0), Z, Y, SHW + 1.0, SHH + 1.0), [2.5] * 4)),
            'TRUNK_HOLE', 5, X, cut=True)
    extrude(d, xsk(d, rg['x0'] - 1, 'SCREWS', lambda s: [s.circle(pitch_pt(SPOKES['screw_r'], SPOKES['a0'] + 72 * k, rg['x0'] - 1), 1.7) for k in range(5)]),
            'SCREWS', 5, X, cut=True)
    return finish_part(d, 'ring')


# ================================================================================================================== cap
def stop_lug(d, ax, key, phi_deg, lug_side):
    """Printed stop lug. The plane STOP_<key>_AXIS holds the fork rear arm's centreline at the stop angle (driven by the
    global variable); the lug's contact face is the arm flank, ARM_HW off that plane, on the side the arm comes from."""
    alpha = phi_deg - 90.0                         # arm centreline direction at the stop (deg from +X)
    t = math.radians(alpha)
    dirv = np.array([math.cos(t), math.sin(t), 0.0])
    side = np.array([-math.sin(t), math.cos(t), 0.0]) * lug_side   # toward the lug
    pl, flip = plane_axis_angle(d, ax, d.FeatureByName('Top Plane'), alpha % 180, dirv, f'STOP_{key}_AXIS')
    fl = plane_offset_from(d, pl, ARM_HW, side, f'STOP_{key}_FLANK')
    z0, z1 = BACK_Z + 1.2, CAP_Z1 + 0.5
    base = np.array([RX, RY, 0.0]) + side * ARM_HW
    with Sk(d, fl, f'STOP_{key}') as s:
        q = lambda sv, z: tuple(base + dirv * sv + np.array([0, 0, z]))
        s.rpoly([q(40.5, z0), q(48.0, z0), q(48.0, z1), q(40.5, z1)], [3.0, 3.0, 0, 0])
    extrude(d, s.feat, f'STOP_{key}', 14.0, tuple(side))
    return pl


def build_cap():
    d = new_part(OUT / f"{NAMES['cap']}.SLDPRT")
    roll_rev(d, 'CAP', [(0, DRUM_Z0), (BOSS_R, DRUM_Z0), (BOSS_R, CAP_Z1 + CAP_T), (DRUM_RO - RIM_T, CAP_Z1 + CAP_T), (DRUM_RO - RIM_T, DRUM_Z0),
                        (DRUM_RO, DRUM_Z0), (DRUM_RO, CAP_Z1), (LAND_R, CAP_Z1), (LAND_R, LAND_Z), (STUB_R, LAND_Z), (STUB_R, BRG_Z[1]),
                        (0, BRG_Z[1])], [0, 0.8, 1.5, 1.5, 0.5, 0.5, 6.0, 1.0, 0.3, 0.3, 0.6, 0])
    # spoke from the trunk end to the axis, carrying the radial channel
    dvec = np.array([RX - TRUNK_X, RY - TRUNK_Y, 0.0])
    dvec /= np.linalg.norm(dvec)
    cu = np.array([-dvec[1], dvec[0], 0.0])
    p0, p1 = (TRUNK_X, TRUNK_Y, DRUM_Z0), (RX, RY, DRUM_Z0)
    extrude(d, zsk(d, DRUM_Z0, 'SPOKE', lambda s: s.rpoly(seg_rect(p0, p1, cu, SHW, 5.5, 5.5), [6, 0, 0, 6])), 'SPOKE', DRUM_Z0 - CAP_Z1, NZ)
    extrude(d, zsk(d, DRUM_Z0, 'EARS', lambda s: [s.circle(rpt(EAR_PCD, a, DRUM_Z0), EAR_R) for a in EAR_ANGLES]), 'EARS', DRUM_Z0 - CAP_Z1, NZ)
    # stop lugs: the inward lug sits clockwise of the arm (the arm swings to smaller angles going inward)
    ax = ref_axis(d, plane(d, 'X', RX, 'P_X_RX'), plane(d, 'Y', RY, 'P_Y_RY'), 'ROLL_AXIS')
    stop_lug(d, ax, 'IN', ROLL_STOP_IN, -1)
    stop_lug(d, ax, 'OUT', ROLL_STOP_OUT, +1)
    # ---- cuts
    roll_rev(d, 'BORE', [(0, DRUM_Z0 + 1), (STUB_BORE, DRUM_Z0 + 1), (STUB_BORE, BRG_Z[1] - 1), (0, BRG_Z[1] - 1)], cut=True)
    extrude(d, zsk(d, CAP_Z1 - 1, 'EAR_HOLES', lambda s: [s.circle(rpt(EAR_PCD, a, CAP_Z1 - 1), 2.25) for a in EAR_ANGLES]), 'EAR_HOLES', 14, Z, cut=True)
    extrude(d, zsk(d, CAP_Z1 - 1, 'EAR_CB', lambda s: [s.circle(rpt(EAR_PCD, a, CAP_Z1 - 1), 4.0) for a in EAR_ANGLES]), 'EAR_CB', 4.5, Z, cut=True)
    zt = CAPZ + PH / 2
    extrude(d, zsk(d, zt, 'SPOKE_P', lambda s: s.rpoly(seg_rect((TRUNK_X, TRUNK_Y, zt), (RX, RY, zt), cu, PW, 4, 4, P_OFF), [1] * 4)), 'SPOKE_P', PH, NZ, cut=True)
    zt = CAPZ + SH / 2
    extrude(d, zsk(d, zt, 'SPOKE_S', lambda s: s.rpoly(seg_rect((TRUNK_X, TRUNK_Y, zt), (RX, RY, zt), cu, SW, 4, 4, S_OFF), [1] * 4)), 'SPOKE_S', SH, NZ, cut=True)
    tu = np.array(TU) / np.linalg.norm(TU)
    tv = np.array([tu[1], -tu[0], 0.0])
    c = np.array([TRUNK_X, TRUNK_Y, DRUM_Z0])
    extrude(d, zsk(d, DRUM_Z0, 'INLET_P', lambda s: s.rpoly(rect_pts(c + tu * P_OFF, tu, tv, PW, PH), [1] * 4)), 'INLET_P', DRUM_Z0 - (CAPZ - PH / 2), NZ, cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'INLET_S', lambda s: s.rpoly(rect_pts(c + tu * S_OFF, tu, tv, SW, SH), [1] * 4)), 'INLET_S', DRUM_Z0 - (CAPZ - SH / 2), NZ, cut=True)
    # stop angles as global variables driving the two stop planes
    add_global(d, 'ROLL_STOP_IN', ROLL_STOP_IN)
    add_global(d, 'ROLL_STOP_OUT', ROLL_STOP_OUT)
    link_dim(d, 'D1@STOP_IN_AXIS', '"ROLL_STOP_IN" + 90')
    link_dim(d, 'D1@STOP_OUT_AXIS', '"ROLL_STOP_OUT" - 90')
    return d


# ===================================================================================================== fork front cheek
def loft(d, sketches, name):
    v0 = vol(d)
    for merge in (True, False):
        d.ClearSelection2(True)
        for k in sketches:
            k.Select2(True, 1)
        f = d.FeatureManager.InsertProtrusionBlend2(False, True, False, 1.0, 0, 0, 1.0, 1.0, True, True, False, 0, 0, 0, True, merge, merge, 0)
        if f is not None:
            f.Name = name
            d.ForceRebuild3(False)
            log(f'  {name}: added {vol(d) - v0:.0f} mm3')
            return f
    raise SystemExit(name + ' loft failed')


def hull_pts(circles, n=36, out=48):
    from scipy.spatial import ConvexHull
    pts = np.array([(x + r * math.cos(t), y + r * math.sin(t)) for (x, y, r) in circles for t in np.linspace(0, 2 * math.pi, n, endpoint=False)])
    P = pts[ConvexHull(pts).vertices]
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))]
    s = np.linspace(0, seg[-1], out, endpoint=False)
    return np.c_[np.interp(s, seg, np.r_[P[:, 0], P[0, 0]]), np.interp(s, seg, np.r_[P[:, 1], P[0, 1]])]


def ypt(r, a, y):
    return yaw_pt(r, a, y)


def build_fork_front():
    d = new_part(OUT / f"{NAMES['fork_front']}.SLDPRT")
    dm = DOME
    hull = lambda k: hull_pts([(RX, RY, dm['r'] - k), (RX - 22, 362.0, 10.0 - k), (RX + 22, 362.0, 10.0 - k)])
    z0, z1, e = FRONT_Z[0], FRONT_Z[1], dm['edge']
    extrude(d, zsk(d, z0, 'CHEEK', lambda s: s.spline([(x, y, z0) for x, y in hull(0.0)])), 'CHEEK', z1 - e - z0, Z)
    # soft front edge: loft through insets of a quarter round (R5)
    secs = []
    for i, a in enumerate((0.0, 30.0, 60.0, 85.0)):
        t = math.radians(a)
        zz, k = z1 - e + e * math.sin(t), e * (1 - math.cos(t))
        secs.append(zsk(d, zz, f'CHEEK_EDGE{i}', lambda s, zz=zz, k=k: s.spline([(x, y, zz) for x, y in hull(k)])))
    loft(d, secs, 'CHEEK_EDGE')
    extrude(d, zsk(d, ROLL_OUT, 'BOSS', lambda s: s.circle((RX, RY, ROLL_OUT), 22.0)), 'BOSS', FRONT_Z[0] + 0.5 - ROLL_OUT, Z)
    def seat(s):
        s.circle((RX, SEAT_Y[0], YZ), SEAT_RO)
        s.circle((RX, SEAT_Y[0], YZ), SEAT_RI)
    extrude(d, ysk(d, SEAT_Y[0], 'SEAT', seat), 'SEAT', SEAT_Y[1] - SEAT_Y[0], Y)
    extrude(d, ysk(d, SEAT_Y[0], 'TAP_SECTOR', lambda s: sector(s, lambda r, a: ypt(r, a, SEAT_Y[0]), SEAT_RI + 1, 49.0, -170, -100, 3.0)),
            'TAP_SECTOR', SEAT_Y[1] - SEAT_Y[0], Y)
    # DRESSED: cuff round the RS02 housing, down to just above the hub
    cf = CUFF
    yaw_rev(d, 'CUFF', [(cf['ri'], cf['y0']), (cf['ro_bot'], cf['y0']), (cf['ro_top'], SEAT_Y[0] - 2.0), (cf['ro_top'], SEAT_Y[0] + 2.0),
                        (cf['ri'], SEAT_Y[0] + 2.0)], [0.8, 1.2, 6.0, 0, 0])
    ym = (SEAT_Y[0] + SEAT_Y[1]) / 2
    extrude(d, zsk(d, JZ0, 'JOINT_PAD', lambda s: s.rpoly(rect_pts((RX, ym, JZ0), X, Y, 2 * JX, SEAT_Y[1] - SEAT_Y[0]), [4, 4, 4, 4])),
            'JOINT_PAD', -30.0 - JZ0, Z)
    # DRESSED 2: web from the cuff back to the fork rear arm (0.5 mm static gap), so the rear arm reads as part of the cuff
    zw = JZ0 + 0.5
    extrude(d, zsk(d, zw, 'REAR_WEB', lambda s: s.rpoly(rect_pts((RX - 6.0, (cf['y0'] + 8.7 + SEAT_Y[0]) / 2, zw), X, Y, 16.0 + 2 * WALL, SEAT_Y[0] - cf['y0'] - 8.7),
                                                            [3, 3, 0, 0])), 'REAR_WEB', YZ - cf['ri'] + 1.0 - zw, Z)
    # ---- cuts
    extrude(d, zsk(d, z0 - 1, 'DOME_POCKETS', lambda s: [sector(s, lambda r, a: rpt(r, a, z0 - 1), dm['pocket_r'][0], dm['pocket_r'][1], a0, a1, 3.0)
                                                         for a0, a1 in dm['pockets']]), 'DOME_POCKETS', z1 - z0 - dm['back_t'] + 1, Z, cut=True)
    extrude(d, ysk(d, cf['y0'] - 1, 'CUFF_NOTCH', lambda s: sector(s, lambda r, a: ypt(r, a, cf['y0'] - 1), cf['ri'] - 1, cf['ro_top'] + 2, cf['notch'][0], cf['notch'][1], 2.0)),
            'CUFF_NOTCH', Y_EX + 3 + WALL + 1.5 - (cf['y0'] - 1), Y, cut=True)
    extrude(d, ysk(d, SEAT_Y[0] - 1, 'SEAT_BORE', lambda s: s.circle((RX, SEAT_Y[0] - 1, YZ), SEAT_RI)), 'SEAT_BORE', 12, Y, cut=True)
    extrude(d, zsk(d, ROLL_OUT - 1, 'ROLL_BORE', lambda s: s.circle((RX, RY, ROLL_OUT - 1), 10.75)), 'ROLL_BORE', 30, Z, cut=True)
    extrude(d, zsk(d, ROLL_OUT - 1, 'OUT_HOLES', lambda s: [s.circle(rpt(15.2, 30 + 60 * k, ROLL_OUT - 1), 2.25) for k in range(6)]), 'OUT_HOLES', 30, Z, cut=True)
    extrude(d, zsk(d, FRONT_Z[1] - 4, 'OUT_CB', lambda s: [s.circle(rpt(15.2, 30 + 60 * k, FRONT_Z[1] - 4), 4.25) for k in range(6)]), 'OUT_CB', 10, Z, cut=True)
    extrude(d, zsk(d, FRONT_Z[1] - 2, 'CAP_RECESS', lambda s: s.circle((RX, RY, FRONT_Z[1] - 2), 24.0)), 'CAP_RECESS', 5, Z, cut=True)
    extrude(d, ysk(d, SEAT_Y[0] - 5, 'RS02_HOLES', lambda s: [s.circle(ypt(36.5, a, SEAT_Y[0] - 5), 1.8) for a in RS02_SCREWS]), 'RS02_HOLES', 30, Y, cut=True)
    extrude(d, ysk(d, SEAT_Y[1] - 3.5, 'RS02_CB', lambda s: [s.circle(ypt(36.5, a, SEAT_Y[1] - 3.5), 3.3) for a in RS02_SCREWS]), 'RS02_CB', 10, Y, cut=True)
    extrude(d, ysk(d, SEAT_Y[0] - 1, 'SOCKETS', lambda s: [sector(s, lambda r, a: ypt(r, a, SEAT_Y[0] - 1), 30.0, 40.5, a0, a1, 1.5) for a0, a1 in SOCKET_POCKETS]),
            'SOCKETS', 10, Y, cut=True)
    extrude(d, ysk(d, TAP_Y[0], 'TAP_ARC', lambda s: sector(s, lambda r, a: ypt(r, a, TAP_Y[0]), 40.5, 47.5, -168, -94)), 'TAP_ARC', TAP_Y[1] - TAP_Y[0], Y, cut=True)
    tz = YZ - 41.0
    extrude(d, zsk(d, tz, 'TAP_LINK', lambda s: s.poly(rect_pts((RX - 4.0, sum(TAP_Y) / 2, tz), X, Y, 7.0, 6.0))), 'TAP_LINK', tz - RZ, NZ, cut=True)
    extrude(d, zsk(d, JZ0 - 1, 'JOINT_INSERTS', lambda s: [s.circle((RX + dx, (SEAT_Y[0] + SEAT_Y[1]) / 2, JZ0 - 1), 2.8) for dx in (-JX + 4.5, JX - 4.5)]),
            'JOINT_INSERTS', 12, Z, cut=True)
    return finish_part(d, 'fork_front')


# ====================================================================================================== fork rear cheek
def build_fork_rear():
    d = new_part(OUT / f"{NAMES['fork_rear']}.SLDPRT")
    roll_rev(d, 'CHEEK', [(0, JZ0), (CHEEK_R, JZ0), (CHEEK_R, BACK_Z), (0, BACK_Z)], [0, 1.0, 6.0, 0])   # DRESSED 2: R6 back edge (arm drum R7)
    extrude(d, zsk(d, HOUSE_Z0, 'HOUSING', lambda s: s.circle((RX, RY, HOUSE_Z0), HOUSE_R)), 'HOUSING', HOUSE_Z0 - JZ0, NZ)
    extrude(d, zsk(d, JZ0, 'ARM', lambda s: s.poly(rect_pts((RX, (RY + SEAT_Y[0]) / 2, JZ0), X, Y, 2 * ARM_HW, RY - SEAT_Y[0]))), 'ARM', JZ0 - BACK_Z, NZ)
    extrude(d, zsk(d, JZ0, 'DUCT', lambda s: s.rpoly(rect_pts((RX - 6.0, (SEAT_Y[0] + 4.0 + Y_BOT) / 2, JZ0), X, Y, 16.0 + 2 * WALL, SEAT_Y[0] + 4.0 - Y_BOT),
                                                      [0, 0, 0, 0])), 'DUCT', JZ0 - BACK_Z, NZ)
    ym = (SEAT_Y[0] + SEAT_Y[1]) / 2
    extrude(d, zsk(d, JZ0, 'LUGS', lambda s: s.rpoly(rect_pts((RX, ym, JZ0), X, Y, 2 * JX, SEAT_Y[1] - SEAT_Y[0]), [2, 2, 2, 2])), 'LUGS', JZ0 - BACK_Z, NZ)
    extrude(d, zsk(d, RZ, 'EXIT', lambda s: s.poly(rect_pts((RX - 6.0, Y_EX, RZ), X, Y, 16.0 + 2 * WALL, 6.0 + 2 * WALL))), 'EXIT', (YZ - 37.0) - RZ, Z)
    # ---- cuts
    roll_rev(d, 'SEAT', [(0, HOUSE_Z0 + 1), (BRG_SEAT_R, HOUSE_Z0 + 1), (BRG_SEAT_R, BRG_Z[1]), (BRG_LIP_R, BRG_Z[1]), (BRG_LIP_R, RZ), (0, RZ)],
             [0, 0, 0, 0, 0, 0], cut=True)
    zc = RZ + PH / 2
    extrude(d, zsk(d, zc, 'CH_P', lambda s: s.rpoly(rect_pts((RX + P_OFF, (RY + 9.0 + Y_EX - 3.0) / 2, zc), X, Y, PW, RY + 9.0 - (Y_EX - 3.0)), [1] * 4)),
            'CH_P', PH, NZ, cut=True)
    zc = RZ + SH / 2
    sig_end = SEAT_Y[0] + WALL

    def ch_s(s):
        s.rpoly(rect_pts((RX + S_OFF, (RY + 9.0 + sig_end) / 2, zc), X, Y, SW, RY + 9.0 - sig_end), [1] * 4)
    extrude(d, zsk(d, zc, 'CH_S', ch_s), 'CH_S', SH, NZ, cut=True)
    extrude(d, zsk(d, zc, 'CH_JOIN', lambda s: s.poly(rect_pts((RX + 3.0, sig_end + 3.0, zc), X, Y, 6.0, 6.0))), 'CH_JOIN', SH, NZ, cut=True)
    extrude(d, zsk(d, RZ - 3.0, 'EXIT_CH', lambda s: s.poly(rect_pts((RX - 6.0, Y_EX, RZ - 3.0), X, Y, 16.0, 6.0))), 'EXIT_CH', (YZ - 37.0) - RZ + 3.0 + 1, Z, cut=True)
    extrude(d, zsk(d, BACK_Z - 1, 'JOINT_HOLES', lambda s: [s.circle((RX + dx, ym, BACK_Z - 1), 2.25) for dx in (-JX + 4.5, JX - 4.5)]), 'JOINT_HOLES', SHH + 2, Z, cut=True)
    extrude(d, zsk(d, BACK_Z - 1, 'JOINT_CB', lambda s: [s.circle((RX + dx, ym, BACK_Z - 1), 4.0) for dx in (-JX + 4.5, JX - 4.5)]), 'JOINT_CB', 4.5, Z, cut=True)
    tz = YZ - 41.0
    extrude(d, zsk(d, JZ0 + 0.5, 'TAP_LINK', lambda s: s.poly(rect_pts((RX - 4.0, sum(TAP_Y) / 2, JZ0 + 0.5), X, Y, 7.0, 6.0))), 'TAP_LINK', JZ0 + 0.5 - RZ, NZ, cut=True)
    extrude(d, ysk(d, Y_BOT - 5, 'YAW_CLEAR', lambda s: s.circle((RX, Y_BOT - 5, YZ), 41.5)), 'YAW_CLEAR', SEAT_Y[0] - (Y_BOT - 5), Y, cut=True)
    # DRESSED: round the arm and duct along their length, and the joint lugs
    along_y = lambda a, b: abs(a[1] - b[1]) > 8.0 and abs(a[0] - b[0]) < 0.05 and abs(a[2] - b[2]) < 0.05
    fillet(d, edges_where(d, lambda p: p[2] < JZ0 - 0.5 and p[1] < RY - 30, along_y), [4.0, 3.0, 2.0], 'ARM_ROUND')
    # DRESSED: soft back edges
    fillet(d, edges_where(d, lambda p: abs(p[2] - BACK_Z) < 0.05 and np.hypot(p[0] - (RX + 30), p[1] - 357) > 6.0 and np.hypot(p[0] - (RX - 30), p[1] - 357) > 6.0), [3.0, 2.0, 1.5], 'BACK_ROUND')
    return finish_part(d, 'fork_rear')


# ==================================================================================================== fork press-in cap
def build_fork_cap():
    d = new_part(OUT / f"{NAMES['fork_cap']}.SLDPRT")
    z0 = FRONT_Z[1] - 2
    roll_rev(d, 'CAP', [(0, z0), (23.8, z0), (23.8, FRONT_Z[1]), (18.0, FRONT_Z[1] + 1.1), (0, FRONT_Z[1] + 1.5)], [0, 0.4, 0.8, 4.0, 0])
    return finish_part(d, 'fork_cap')


# ========================================================================================================== pitch cover
def feed_outline(xa, xc, yr, y0, y1, h, z):
    """Closed L/J outline (plane Z = z) of a duct of half-thickness h: up at X xa from y0 to the run at Y yr, along +X to
    xc, up to y1."""
    return [(xa - h, y0, z), (xa + h, y0, z), (xa + h, yr - h, z), (xc + h, yr - h, z), (xc + h, y1, z), (xc - h, y1, z),
            (xc - h, yr + h, z), (xa - h, yr + h, z)]


def build_cover():
    d = new_part(OUT / f"{NAMES['cover']}.SLDPRT")
    c = COVER
    f = FEED
    pitch_rev(d, 'WALLS', [(c['in_'][0], c['back_x'][0]), (c['out'][1], c['back_x'][0]), (c['out'][1], c['x1']), (c['out'][0], c['x1']),
                           (c['out'][0], c['back_x'][1]), (c['in_'][1], c['back_x'][1]), (c['in_'][1], c['in_x1']), (c['in_'][0], c['in_x1'])],
              [0.5, 3.0, 1.19, 1.19, 1.5, 1.5, 0.9, 0.9])     # DRESSED: full round on the exposed rim (clean band)
    # fixing tabs (placeholders): local 5 mm pads on the back wall, M5 clearance, screws from outboard into T-nuts
    bx = c['back_x'][0]
    extrude(d, xsk(d, c['back_x'][1], 'TABS', lambda s: [s.circle((c['back_x'][1], y, z), 7.0) for y, z in COVER_TABS]), 'TABS', 5.0 - (c['back_x'][1] - bx), X)
    extrude(d, xsk(d, bx - 1, 'TAB_HOLES', lambda s: [s.circle((bx - 1, y, z), 2.75) for y, z in COVER_TABS]), 'TAB_HOLES', 8.0, X, cut=True)
    # bottom feed (FEED_*): riser in the void under the step overhang, run outboard under the cover, up into its bottom
    ytop = RY - c['out'][0] - 0.3            # shells stop just inside the outer wall
    h2 = SHH / 2
    xa, xc, yr = f['x_rise'], f['x_up'], f['y_run']
    extrude(d, zsk(d, f['z'] - SHW / 2, 'FEED_SHELL', lambda s: s.rpoly(feed_outline(xa, xc, yr, f['y0'], ytop, h2, f['z'] - SHW / 2), [0, 0, 4, 6, 0, 0, 4, 6])),
            'FEED_SHELL', SHW, Z)
    for nm, off, w, h in (('POWER', P_OFF, PW, PH), ('SIGNAL', S_OFF, SW, SH)):
        z0 = f['z'] + off - w / 2
        extrude(d, zsk(d, z0, f'FEED_{nm}', lambda s, h=h, z0=z0: s.rpoly(feed_outline(xa, xc, yr, f['y0'] - 1, ytop + 6.0, h / 2, z0), [0, 0, 2, 4, 0, 0, 2, 4])),
                f'FEED_{nm}', w, Z, cut=True)
    return finish_part(d, 'cover', dict(Note='Feed (FEED_*) and fixing tabs are placeholders: rev A frame, 2026-11-11'))


# ================================================================================================================== hub
def build_hub():
    sw = app()
    step = CAD / 'reference' / 'shoulder' / 'upper_arm_hub_left.step'
    e = L()
    dd = sw.GetImportFileData(str(step))
    d = sw.LoadFile4(str(step), 'r', dd, e)
    if d is None:
        raise SystemExit(f'hub import failed {e.value}')
    e2, w2 = L(), L()
    d.Extension.SaveAs(str(OUT / f"{NAMES['hub']}.SLDPRT"), 0, 1, NUL, e2, w2)
    log('hub imported', bodies(d))
    yaw_rev(d, 'DISH', [(DISH_R0, DISH_Y), (45.0, DISH_Y), (45.0, 330.0), (DISH_R0, 330.0)], cut=True)
    yaw_rev(d, 'STEP_RING', [(19.5, 312.8), (DISH_R0 + 0.01, 312.8), (DISH_R0 + 0.01, RS02_OUT), (19.5, RS02_OUT)])
    yaw_rev(d, 'FLOOR', [(DISH_R0 - 0.5, 312.8), (38.6, 312.8), (38.6, DISH_Y), (DISH_R0 - 0.5, DISH_Y)], [0, 0, 0.8, 0])
    yaw_rev(d, 'RIM', [(38.5, 305.0), (39.3, 305.0), (39.3, DISH_Y), (38.5, DISH_Y)])
    ax = ref_axis(d, plane(d, 'X', RX, 'P_X_RX'), plane(d, 'Z', YZ, 'P_Z_YZ'), 'YAW_AXIS')
    t = math.radians(HUB_WIN_A)
    u = (math.cos(t), 0.0, math.sin(t))
    pl, _ = plane_axis_angle(d, ax, d.FeatureByName('Front Plane'), HUB_WIN_A, u, 'P_HUB_WIN')
    p0 = (RX + 31.0 * u[0], DISH_Y + 2, YZ + 31.0 * u[2])
    p1 = (RX + 15.5 * u[0], 298.0, YZ + 15.5 * u[2])
    with Sk(d, pl, 'HUB_WIN') as s:
        s.rpoly(seg_rect(p0, p1, np.cross(np.subtract(p1, p0), (-u[2], 0, u[0])), 9.0), [1.5] * 4)
    extrude(d, s.feat, 'HUB_WIN', 16.0, (0, 0, 0), cut=True, mode=MID)
    # ---- prepared, suppressed by default: spigot extension below Y 296 (length, taper) and a second lug pair (angle)
    hb = HUB
    sk = ysk(d, hb['spigot_y0'], 'SPIGOT_EXT', lambda s: [s.circle((RX, hb['spigot_y0'], YZ), hb['spigot_ro']), s.circle((RX, hb['spigot_y0'], YZ), hb['spigot_ri'])])
    d.ClearSelection2(True); sk.Select2(False, 0)
    f = None
    for rev in (False, True):
        f = d.FeatureManager.FeatureExtrusion3(True, False, rev, 0, 0, hb['spigot_ext_len'] * m, 0, True, False, False, False,
                                                math.radians(max(hb['spigot_taper'], 0.01)), 0, False, False, False, False, True, False, True, 0, 0, False)
        if f is not None:
            d.ForceRebuild3(False)
            lo, hi = f.GetFaces[0].GetBox[1] * 1e3, f.GetFaces[0].GetBox[4] * 1e3
            if min(lo, hi) < hb['spigot_y0'] - 1:
                break
            d.EditUndo2(1); d.ClearSelection2(True); sk.Select2(False, 0); f = None
    if f is not None:
        f.Name = 'SPIGOT_EXT'
    t2 = math.radians(hb['lug2_angle'])
    u2 = (math.cos(t2), 0.0, math.sin(t2))
    pl2, _ = plane_axis_angle(d, ax, d.FeatureByName('Front Plane'), hb['lug2_angle'] % 180, u2, 'P_LUG2')
    w2 = 2 * hb['lug_r'][1] * math.sin(math.radians(hb['lug_half_deg']))
    with Sk(d, pl2, 'LUG2') as s:
        for sg in (1, -1):
            r0, r1 = hb['lug_r']
            s.rpoly([(RX + sg * r0 * u2[0], hb['lug_y'][0], YZ + sg * r0 * u2[2]), (RX + sg * r1 * u2[0], hb['lug_y'][0], YZ + sg * r1 * u2[2]),
                     (RX + sg * r1 * u2[0], hb['lug_y'][1], YZ + sg * r1 * u2[2]), (RX + sg * r0 * u2[0], hb['lug_y'][1], YZ + sg * r0 * u2[2])], [0, 1.5, 0, 0])
    extrude(d, s.feat, 'LUG2', w2, (0, 0, 0), mode=MID)
    for k, v in (('SPIGOT_EXT_ON', hb['spigot_ext_on']), ('SPIGOT_EXT_LEN', hb['spigot_ext_len']), ('SPIGOT_TAPER', hb['spigot_taper']),
                 ('LUG2_ON', hb['lug2_on']), ('LUG2_ANGLE', hb['lug2_angle'])):
        add_global(d, k, v)
    for dims_ in (('D1@SPIGOT_EXT', '"SPIGOT_EXT_LEN"'), ('D1@P_LUG2', '"LUG2_ANGLE"')):
        link_dim(d, *dims_)
    em = d.GetEquationMgr
    for feat_, var in (('SPIGOT_EXT', 'SPIGOT_EXT_ON'), ('LUG2', 'LUG2_ON')):
        em.Add2(-1, f'"{feat_}" = IIF("{var}" = 1, "unsuppressed", "suppressed")', True)
    d.ForceRebuild3(False)
    log('  hub prepared features:', [(n, d.FeatureByName(n).IsSuppressed2(1, NUL)[0] if d.FeatureByName(n) else None) for n in ('SPIGOT_EXT', 'LUG2')])
    return finish_part(d, 'hub', dict(Note='Interface frozen: spigot, lugs, seam bolts, hub screws from upper_arm_hub_left'))


BUILD = dict(drum=build_drum, ring=build_ring, cap=lambda: finish_part(build_cap(), 'cap'), fork_front=build_fork_front, fork_rear=build_fork_rear,
             fork_cap=build_fork_cap, cover=build_cover, hub=build_hub)

if __name__ == '__main__':
    which = sys.argv[1:] or list(BUILD)
    res = {}
    for k in which:
        log('#### build', k)
        res[k] = BUILD[k]()
    for k, v in res.items():
        log(f'{k:12s} {v:10.0f} mm3 {v * PETG:7.1f} g')
