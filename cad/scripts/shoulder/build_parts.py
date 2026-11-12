"""Left shoulder, roll drum and fork: the printed parts as SolidWorks parts (first pass).

    python build_parts.py [drum ring cap fork_front fork_rear fork_cap hub cover bearing]   (default: all)

Every part is modelled in the torso frame (dims.py), so the assembly places each at the origin. Saves to cad/shoulder/left/
and a fine STL of each to cad/_wip/shoulder-pass1/stl/ for the checks and pictures.
"""
import inspect
import os
import math
import sys

import numpy as np

from dims import *
from swk import *
from swk import vol_com

STL = WIP / ('stl' if not LOOK else f'stl_look_{LOOK}')
STL.mkdir(parents=True, exist_ok=True)
STEPD = WIP / ('step' if not LOOK else f'step_look_{LOOK}')
STEPD.mkdir(parents=True, exist_ok=True)
NAMES = {
    'drum': 'shoulder_roll_drum_left', 'ring': 'shoulder_pitch_flange_ring_left', 'cap': 'shoulder_roll_cap_left',
    'fork_front': 'shoulder_fork_front_left', 'fork_rear': 'shoulder_fork_rear_left', 'fork_cap': 'shoulder_fork_cap_left',
    'hub': 'shoulder_hub_left', 'cover': 'shoulder_pitch_loop_cover_left', 'port_cap': 'shoulder_roll_drum_port_cap_left',
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
    # SMOOTH: neck disc only (the bell below is the structure from the pad to the drum)
    pitch_rev(d, 'NECK', [(n['ri_core'], n['x0']), (BELL['bot'], n['x0']), (BELL['bot'], BELL['x'][0] + 0.5), (n['ri_core'], BELL['x'][0] + 0.5)], [0, 2.0, 0, 0])
    import envelope as EV
    bsecs = [xsk(d, x_, f'BELL_S{i}', lambda s, x_=x_: s.spline(EV.bell_section(x_))) for i, x_ in enumerate(BELL['x'])]
    loft(d, bsecs, 'BELL')
    ix = [PAD_X[1] + 0.5] + list(BELL['x'][2:])
    isecs = [xsk(d, x_, f'BELL_IN_S{i}', lambda s, x_=x_: s.spline(EV.bell_section(x_, BELL['wall']))) for i, x_ in enumerate(ix)]
    d.ClearSelection2(True)
    for k in isecs:
        k.Select2(True, 1)
    fcut = d.FeatureManager.InsertCutBlend(False, True, False, 1.0, 0, 0, False, 0, 0, 0, True, True)
    log('  BELL_HOLLOW', fcut is not None)
    # (the bell's bottom is r 41: clear of the fork front's tap sector and the RS02 where they swing in at the inward stop)
    sk = zsk(d, LIP_Z1, 'CLIP_FRONT', lambda s: s.poly(rect_pts((115, RY, LIP_Z1), X, Y, 60, 100)))
    extrude(d, sk, 'CLIP_FRONT', 40, Z, cut=True)
    sk = zsk(d, DRUM_Z0 + 1, 'CLIP_REAR', lambda s: s.poly(rect_pts((115, RY, DRUM_Z0 + 1), X, Y, 60, 100)))
    extrude(d, sk, 'CLIP_REAR', 40, NZ, cut=True)
    # SMOOTH: the drum skin is a loft through sections that are the crown circle swelled (convex hull) over the cable ducts
    zst = [DRUM_Z0, -24.0, -14.0, -4.0, 4.0, 10.0, 16.0, 20.0, 27.0, 33.0, LIP_Z1] if not SHAPE_A else [z_ for z_, _ in DRUM_CROWN]
    secs = [zsk(d, z, f'DRUM_S{i}', lambda s, z=z: s.spline([(x, y, z) for x, y in EV.drum_section(z)])) for i, z in enumerate(zst)]
    loft(d, secs, 'DRUM')
    roll_rev(d, 'LIP_BORE', [(0, LIP_Z0), (LIP_RI, LIP_Z0), (LIP_RI, LIP_Z1 + 1), (0, LIP_Z1 + 1)], cut=True)
    # blend where the bell's surface comes out of the drum swell (the intersection edges outboard of X 118, above the axis)
    blend = edges_where(d, lambda p: 117.0 < p[0] < 150.0 and p[1] > RY + 20 and -27.0 < p[2] < 35.0
                        and np.hypot(p[0] - RX, p[1] - RY) > DRUM_RO - 1.5)
    def ends(e_):
        cp = e_.GetCurveParams3
        cp = cp() if inspect.ismethod(cp) else cp
        return np.array(cp.StartPoint[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3
    keys = [ends(e_) for e_ in blend]
    log('  BELL_BLEND edges', len(blend), [tuple(np.round((a_ + b_) / 2, 1)) for a_, b_ in keys])
    fillet(d, blend, [6.0, 4.0, 3.0, 2.0], 'BELL_BLEND')      # with the tapered top, a light blend on the shallow intersection
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
    # cable trunk inside the bell and the swell: along X over the neck from the mouth at X 100.5, down along -Z at X 140, and a
    # branch to the RS03 top bay
    extrude(d, xsk(d, NECK['x0'], 'TRUNK_A', lambda s: s.rpoly(rect_pts((NECK['x0'], TRUNK_AY, 0.0), Z, Y, SHW, SHH), [2, 2, 2, 2])),
            'TRUNK_A', TRUNK_X + 2.0 - NECK['x0'], X, lo=-1.0)
    tu = np.array(TU) / np.linalg.norm(TU)
    tv = np.array([tu[1], -tu[0], 0.0])
    zb = TRUNK_B_ZTOP
    try:     # the drum outline may already hold the whole duct shell: nothing to add
        extrude(d, zsk(d, zb, 'TRUNK_B', lambda s: s.rpoly(rect_pts((TRUNK_X, TRUNK_Y, zb), tu, tv, SHW, SHH), [2, 2, 2, 2])), 'TRUNK_B', zb - DRUM_Z0, NZ, lo=-1.0)
    except SystemExit:
        log('  TRUNK_B: inside the drum outline, nothing added')
    b0, b1 = (TRUNK_X, TRUNK_Y, -17.0 + SHW / 2), (BRANCH_END[0], BRANCH_END[1], -17.0 + SHW / 2)
    bn_ = np.cross((0, 0, 1), np.subtract(b1, b0))
    try:
        extrude(d, zsk(d, b0[2], 'BRANCH', lambda s: s.rpoly(seg_rect(b0, b1, bn_, SHH, 2 + WALL, 2 + WALL), [2, 2, 2, 2])), 'BRANCH', b0[2] - DRUM_Z0, NZ, lo=-1.0)
    except SystemExit:
        log('  BRANCH: inside the drum outline, nothing added')
    # SMOOTH: hollow the swell from the rear (opens into the cap's interior), leaving 2.4 mm skin and the duct walls
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    hull0 = Polygon(EV.drum_section(DRUM_Z0))
    keep = unary_union([p_.buffer(0.3) for p_, z0_, z1_ in EV.ducts()] + [Point(RX, RY).buffer(DRUM_RO + 0.5, 96)])
    q = hull0.buffer(-WALL).difference(keep)
    polys = [g for g in getattr(q, 'geoms', [q]) if g.area > 30.0]
    if polys:
        def sw_pock(s):
            for g in polys:
                s.poly([(x, y, DRUM_Z0 - 1) for x, y in list(g.simplify(0.3).exterior.coords)[:-1]])
        extrude(d, zsk(d, DRUM_Z0 - 1, 'SWELL_POCKET', sw_pock), 'SWELL_POCKET', (-SHW / 2 - 1.0) - (DRUM_Z0 - 1), Z, cut=True)
    # ---- cuts
    roll_rev(d, 'BORE', [(0, DRUM_Z0 - 1), (DRUM_RI, DRUM_Z0 - 1), (DRUM_RI, LIP_Z0), (0, LIP_Z0)], cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'LUG_SLOTS', lambda s: [s.poly(radial_rect((RX, RY), 44.0, SLOT_R, th, 2 * SLOT_HALF, DRUM_Z0)) for th in LUG_ANGLES]),
            'LUG_SLOTS', LIP_Z0 - DRUM_Z0, Z, cut=True)
    extrude(d, zsk(d, LIP_Z0, 'LIP_HOLES', lambda s: [s.circle(rpt(LIP_PCD_R, a, LIP_Z0), 2.25) for a in LUG_ANGLES]), 'LIP_HOLES', 20, Z, cut=True)
    extrude(d, zsk(d, LIP_Z1 - 4.2, 'LIP_CB', lambda s: [s.circle(rpt(LIP_PCD_R, a, LIP_Z1 - 4.2), 4.8) for a in LUG_ANGLES]), 'LIP_CB', 10, Z, cut=True)
    pitch_rev(d, 'PAD_BORE', [(0, 95.0), (10.75, 95.0), (10.75, PAD_X[1]), (21.0, PAD_X[1]), (21.0, 131.0), (0, 131.0)], cut=True)
    extrude(d, xsk(d, 96.0, 'PAD_HOLES', lambda s: [s.circle(pitch_pt(15.2, a, 96.0), 2.25) for a in PAD_HOLES]), 'PAD_HOLES', 14, X, cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'CAP_PILOTS', lambda s: [s.circle(rpt(CAP_SCREW_R, a, DRUM_Z0), 1.3) for a in CAP_SCREW_ANGLES]), 'CAP_PILOTS', 8.5, Z, cut=True)
    extrude(d, xsk(d, sp['x1'], 'RING_INSERTS', lambda s: [s.circle(pitch_pt(sp['screw_r'], sp['a0'] + 72 * k, sp['x1']), 2.0) for k in range(5)]),
            'RING_INSERTS', sp['insert_depth'], NX, cut=True)
    # trunk channels
    def tch_a(s):
        s.rpoly(rect_pts((NECK['x0'] - 1, TRUNK_AY, P_OFF), Z, Y, PW, PH), [1, 1, 1, 1])
        s.rpoly(rect_pts((NECK['x0'] - 1, TRUNK_AY, S_OFF), Z, Y, SW, SH), [1, 1, 1, 1])
    extrude(d, xsk(d, NECK['x0'] - 1, 'TRUNK_A_CH', tch_a), 'TRUNK_A_CH', TRUNK_X + 1.0 - NECK['x0'] + 1, X, cut=True)

    def tch_b(s):
        c = np.array([TRUNK_X, TRUNK_Y, TRUNK_B_ZTOP - WALL])
        s.rpoly(rect_pts(c + tu * P_OFF, tu, tv, PW, PH), [1, 1, 1, 1])
        s.rpoly(rect_pts(c + tu * S_OFF, tu, tv, SW, SH), [1, 1, 1, 1])
    extrude(d, zsk(d, TRUNK_B_ZTOP - WALL, 'TRUNK_B_CH', tch_b), 'TRUNK_B_CH', TRUNK_B_ZTOP - WALL - DRUM_Z0 + 1, NZ, cut=True)
    # junctions trunk A -> trunk B, each channel into its own (hull of the two channel ends, over the channel's Z band)
    from shapely.geometry import Polygon as _P, MultiPoint as _MP
    ax_ = TRUNK_X + 1.0
    for nm_, off_, w_, h_ in (('JUNCTION_P', P_OFF, PW, PH), ('JUNCTION_S', S_OFF, SW, SH)):
        a_pts = [(ax_ - 3.0, TRUNK_AY - h_ / 2), (ax_, TRUNK_AY - h_ / 2), (ax_, TRUNK_AY + h_ / 2), (ax_ - 3.0, TRUNK_AY + h_ / 2)]
        bc = np.array([TRUNK_X, TRUNK_Y]) + tu[:2] * off_
        b_pts = [tuple(p_[:2]) for p_ in rect_pts((bc[0], bc[1], 0), tu, tv, w_, h_)]
        hv_ = list(_MP(a_pts + b_pts).convex_hull.exterior.coords)[:-1]
        z0_, z1_ = off_ - w_ / 2, off_ + w_ / 2
        extrude(d, zsk(d, z1_, nm_, lambda s, hv_=hv_, z1_=z1_: s.poly([(x, y, z1_) for x, y in hv_])), nm_, w_, NZ, cut=True)
    bn = np.cross((0, 0, 1), np.subtract(b1, b0))
    zp, zs = -17.0 + P_OFF + PW / 2, -17.0 + S_OFF + SW / 2
    extrude(d, zsk(d, zp, 'BRANCH_P', lambda s: s.rpoly(seg_rect((b0[0], b0[1], zp), (b1[0], b1[1], zp), bn, PH, 2, 6), [1, 1, 1, 1])),
            'BRANCH_P', PW, NZ, cut=True)
    extrude(d, zsk(d, zs, 'BRANCH_S', lambda s: s.rpoly(seg_rect((b0[0], b0[1], zs), (b1[0], b1[1], zs), bn, SH, 2, 6), [1, 1, 1, 1])),
            'BRANCH_S', SW, NZ, cut=True)
    # pockets between the lug ribs, under the skin (rib half-width 8 at r 53)
    # pockets under the crowned skin: r 54 at the ends, r 55 over the middle band where the crown is r 57
    for nm, z0_, z1_, ro_ in ((('POCKETS', POCKET_Z[0], POCKET_Z[1], SKIN_RI), ('POCKETS_MID', -13.0, 13.0, SKIN_RI + 1.0)) if not SHAPE_A else
                              (('POCKETS', POCKET_Z[0], POCKET_Z[1], SKIN_RI),)):     # option a: no deeper middle band (the waist is r 56.1)
        def pockets(s, z0_=z0_, ro_=ro_):
            for th in LUG_ANGLES:
                if abs(((th + 22.5) - TRUNK_ANG + 180) % 360 - 180) < 30:      # the bay under trunk B stays solid
                    continue
                sector(s, lambda r, a: rpt(r, a, z0_), WALL_RO, ro_, th + 9.0, th + 36.0, 0.8)
        extrude(d, zsk(d, z0_, nm, pockets), nm, z1_ - z0_, Z, cut=True, lo=-1.0)
    # window over the roll RS03 top connector bay, inside the skin (the branch channels open the skin where they pass)
    tw = TOPWIN
    # option a: the window's top corners are clipped to r 54.5 so the skin over them stays 1.6 under the r 56.1 waist
    from shapely.geometry import box as _box, Point as _Pt
    _w = _box(RX - tw['x'], RY + 40.0, RX + tw['x'], RY + 54.5).intersection(_Pt(RX, RY).buffer(54.5, 128))
    _w = _w.buffer(-2.0, join_style=1).buffer(2.0, join_style=1)
    _wp = [(x_, y_, DRUM_Z0 - 1) for x_, y_ in list(_w.simplify(0.05).exterior.coords)[:-1]]
    extrude(d, zsk(d, DRUM_Z0 - 1, 'TOP_WINDOW', lambda s: s.poly(_wp)), 'TOP_WINDOW', tw['z1'] - DRUM_Z0 + 1, Z, cut=True)
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


# ======================================================================================================= drum port cap
def build_port_cap():
    """Press-in cap that closes the drum's driver port (pitch pad screws) flush with the skin. Outer face = the drum skin
    (sampled from the built drum along the slot's long edges), 13.9 wide in the 14 slot, inner face r 54, and a 0.8 mm hook
    at each end that snaps under the skin into the pocket (r 51.5-54 there)."""
    import trimesh
    m_ = trimesh.load(STL / 'drum.stl')
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(m_)
    prof = []
    for z in np.arange(-20.0, 24.01, 1.0):
        rr = []
        for dy in (-7.6, 7.6):
            loc, _, _ = ray.intersects_location([[RX + 100, RY + dy, z]], [[-1.0, 0, 0]])
            rr.append(float(np.hypot(loc[:, 0].max() - RX, dy)))
        prof.append((float(np.mean(rr)), float(z)))
    d = new_part(OUT / f"{NAMES['port_cap']}.SLDPRT")
    extrude(d, xsk(d, RX + 45.0, 'CAP_SLOT', lambda s: s.slot((RX + 45.0, RY, -11.0), (RX + 45.0, RY, 15.0), 13.9)), 'CAP_SLOT', 20.0, X)
    roll_rev(d, 'SKIN_TRIM', prof + [(80.0, prof[-1][1]), (80.0, prof[0][1])], cut=True)
    ri_ = 54.0                           # the skin's inner radius at the port
    roll_rev(d, 'INNER', [(0.0, -30.0), (ri_, -30.0), (ri_, 30.0), (0.0, 30.0)], cut=True)
    # end hooks: under the skin past the slot ends (slot ends Z -18 / +22, pocket Z -19 to 25.3)
    extrude(d, xsk(d, RX + ri_ - 0.8, 'HOOKS', lambda s: [s.rpoly(rect_pts((RX + ri_ - 0.8, RY, zc), Y, Z, 8.0, 2.4), [0.6] * 4) for zc in (-17.4, 21.4)]), 'HOOKS', 0.8, X)
    return finish_part(d, 'port_cap', dict(Note='press-in cap for the drum driver port, flush with the skin'))


def hub_lug_roots():
    """REV C+: R1.0 at the lugs' X-facing roots (flat outer faces at r 29.5 meeting the spigot underside at Y 296), on the
    saved hub (the edges are not found inside the build). Nothing on the Z-facing sides; no lug thickening."""
    e_, w_ = L(), L()
    d = app().OpenDoc6(str(OUT / f"{NAMES['hub']}.SLDPRT"), 1, 1, '', e_, w_)
    _r = lambda q: math.hypot(q[0] - RX, q[2] - YZ)
    roots = edges_where(d, lambda p: abs(p[1] - 296.0) < 0.05 and abs(p[2] - YZ) < 9.0,
                        pair=lambda p0, p1: all(29.2 < _r(q) < 31.0 for q in (p0, p1)))
    log('  LUG_ROOTS (post) edges', len(roots))
    fillet(d, roots, [1.0], 'LUG_ROOTS')
    return finish_part(d, 'hub')


def build_access_plugs():
    """FRONT BLEND mock-up: press-in plugs (Ø6.9 in the Ø7 RS02 access holes) at the dome's top, 7 deep, top trimmed to
    the dome's r 55 surface about the roll axis; a 2 x 1 mm pry notch on the back edge (toward the drum, out of sight)
    lifts them out with a small screwdriver."""
    d = new_part(OUT / 'shoulder_fork_access_plugs_left.SLDPRT')
    for i_, a_ in enumerate((64.0, 104.0)):
        x_, _, z_ = ypt(36.5, a_, 0.0)
        y_top = RY + math.sqrt(55.0 ** 2 - (x_ - RX) ** 2)
        extrude(d, ysk(d, y_top - 7.0, f'PLUG{i_}', lambda s_, x_=x_, z_=z_, y_top=y_top: s_.circle((x_, y_top - 7.0, z_), 3.45)),
                f'PLUG{i_}', 9.0, Y, merge=(i_ == 0))
    roll_rev(d, 'PLUG_TRIM', [(55.0, -30.0), (90.0, -30.0), (90.0, 80.0), (55.0, 80.0)], cut=True)
    for i_, a_ in enumerate((64.0, 104.0)):
        x_, _, z_ = ypt(36.5, a_, 0.0)
        y_top = RY + math.sqrt(55.0 ** 2 - (x_ - RX) ** 2)
        extrude(d, ysk(d, y_top - 1.0, f'PRY{i_}', lambda s_, x_=x_, z_=z_, y_top=y_top: s_.poly(rect_pts((x_, y_top - 1.0, z_ - 3.2), X, Z, 2.0, 1.2))),
                f'PRY{i_}', 3.0, Y, cut=True, lo=-1.0)
    return finish_part(d, 'access_plugs', dict(Note='mock-up: press-in plugs for the RS02 access holes (front blend)'))


# ========================================================================================================== flange ring
def build_ring():
    d = new_part(OUT / f"{NAMES['ring']}.SLDPRT")
    rg = RING
    pitch_rev(d, 'RING', [(rg['ri'], rg['x0']), (rg['ro'], rg['x0']), (rg['ro'], rg['x1']), (rg['ri'], rg['x1'])], [0.5, 0.9, 0.9, 0.5])
    extrude(d, xsk(d, rg['x0'] - 1, 'TRUNK_HOLE', lambda s: s.rpoly(rect_pts((rg['x0'] - 1, TRUNK_AY, 0.0), Z, Y, SHW + 1.0, SHH + 1.0), [2.5] * 4)),
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
        s.rpoly([q(40.5, z0), q(48.0, z0), q(48.0, z1), q(40.5, z1)], [3.7, 3.7, 0, 0])
    extrude(d, s.feat, f'STOP_{key}', 14.0, tuple(side))
    return pl


def build_cap():
    import envelope as EV
    d = new_part(OUT / f"{NAMES['cap']}.SLDPRT")
    # SMOOTH: the outline continues the drum's rear section exactly, with a small round onto the flat rear face (arm caps)
    secs = [zsk(d, z_, f'CAP_S{i}', lambda s, z_=z_, k_=k_: s.spline([(x, y, z_) for x, y in EV.drum_section(DRUM_Z0, k_)]))
            for i, (z_, k_) in enumerate([(DRUM_Z0, 1.0), (CAP_Z1 + 1.3, 1.0), (CAP_Z1, 0.985)])]
    loft(d, secs, 'CAP_BODY')
    roll_rev(d, 'CAVITY', [(BOSS_R, DRUM_Z0 - 1), (CAP_RIM_R - RIM_T, DRUM_Z0 - 1), (CAP_RIM_R - RIM_T, CAP_Z1 + CAP_T), (BOSS_R, CAP_Z1 + CAP_T)],
             [0, 0, 1.5, 1.5], cut=True)
    roll_rev(d, 'STUB', [(0, CAP_Z1 + 0.5), (LAND_R, CAP_Z1 + 0.5), (LAND_R, LAND_Z), (STUB_R, LAND_Z), (STUB_R, BRG_Z[1] + STUB_LEAD), (STUB_R - STUB_LEAD, BRG_Z[1]), (0, BRG_Z[1])],
             [0, 0, 0.3, 0.3, 0, 0, 0])
    # spoke from the trunk end to the axis, carrying the radial channel (inside the outline)
    dvec = np.array([RX - TRUNK_X, RY - TRUNK_Y, 0.0])
    dvec /= np.linalg.norm(dvec)
    cu = np.array([-dvec[1], dvec[0], 0.0])
    p0, p1 = (TRUNK_X, TRUNK_Y, DRUM_Z0), (RX, RY, DRUM_Z0)
    extrude(d, zsk(d, DRUM_Z0, 'SPOKE', lambda s: s.rpoly(seg_rect(p0, p1, cu, SHW, 2.0, 5.5), [3, 0, 0, 3])), 'SPOKE', DRUM_Z0 - CAP_Z1, NZ, lo=-1.0)
    # screw bosses inside the cavity
    extrude(d, zsk(d, DRUM_Z0, 'SCREW_BOSSES', lambda s: [s.circle(rpt(CAP_SCREW_R, a, DRUM_Z0), 5.0) for a in CAP_SCREW_ANGLES]), 'SCREW_BOSSES',
            DRUM_Z0 - CAP_Z1, NZ, lo=-1.0)
    # SMOOTH: stop ring on the inside of the rear face; the fork rear's tooth runs in an arc slot in it
    ss = STOP_SLOT
    a_lo = ss['tooth_angle'] - ss['tooth_half'] + ROLL_STOP_IN - ss['ring_past']
    a_hi = ss['tooth_angle'] + ss['tooth_half'] + ROLL_STOP_OUT + ss['ring_past']       # only round the slot, ring_past deg past each end
    extrude(d, zsk(d, DRUM_Z0 - 1.0, 'STOP_RING', lambda s: sector(s, lambda r, a: rpt(r, a, DRUM_Z0 - 1.0), ss['ring_r'][0], ss['ring_r'][1], a_lo, a_hi, 2.0)),
            'STOP_RING', (DRUM_Z0 - 1.0) - (CAP_Z1 + 0.5), NZ, lo=-1.0)
    # ---- cuts
    roll_rev(d, 'BORE', [(0, DRUM_Z0 + 1), (STUB_BORE, DRUM_Z0 + 1), (STUB_BORE, BRG_Z[1] - 1), (0, BRG_Z[1] - 1)], cut=True)
    extrude(d, zsk(d, CAP_Z1 - 1, 'SCREW_HOLES', lambda s: [s.circle(rpt(CAP_SCREW_R, a, CAP_Z1 - 1), 1.7) for a in CAP_SCREW_ANGLES]),
            'SCREW_HOLES', 14, Z, cut=True)
    extrude(d, zsk(d, CAP_Z1 - 1, 'SCREW_POCKETS', lambda s: [s.circle(rpt(CAP_SCREW_R, a, CAP_Z1 - 1), 3.25) for a in CAP_SCREW_ANGLES]),
            'SCREW_POCKETS', 3.5, Z, cut=True)
    zt = CAPZ + PH / 2
    extrude(d, zsk(d, zt, 'SPOKE_P', lambda s: s.rpoly(seg_rect((TRUNK_X, TRUNK_Y, zt), (RX, RY, zt), cu, PW, 2, 4, P_OFF), [1] * 4)), 'SPOKE_P', PH, NZ, cut=True)
    zt = CAPZ + SH / 2
    extrude(d, zsk(d, zt, 'SPOKE_S', lambda s: s.rpoly(seg_rect((TRUNK_X, TRUNK_Y, zt), (RX, RY, zt), cu, SW, 2, 4, S_OFF), [1] * 4)), 'SPOKE_S', SH, NZ, cut=True)
    tu = np.array(TU) / np.linalg.norm(TU)
    tv = np.array([tu[1], -tu[0], 0.0])
    c = np.array([TRUNK_X, TRUNK_Y, DRUM_Z0])
    extrude(d, zsk(d, DRUM_Z0, 'INLET_P', lambda s: s.rpoly(rect_pts(c + tu * P_OFF, tu, tv, PW, PH), [1] * 4)), 'INLET_P', DRUM_Z0 - (CAPZ - PH / 2), NZ, cut=True)
    extrude(d, zsk(d, DRUM_Z0, 'INLET_S', lambda s: s.rpoly(rect_pts(c + tu * S_OFF, tu, tv, SW, SH), [1] * 4)), 'INLET_S', DRUM_Z0 - (CAPZ - SH / 2), NZ, cut=True)
    # the arc slot: a revolve-cut from the plane SLOT_START (angle driven by ROLL_STOP_IN) through the stop travel plus the
    # tooth's width (sweep driven by ROLL_STOP_OUT - ROLL_STOP_IN)
    ax = ref_axis(d, plane(d, 'X', RX, 'P_X_RX'), plane(d, 'Y', RY, 'P_Y_RY'), 'ROLL_AXIS')
    a0 = ss['tooth_angle'] - ss['tooth_half'] + ROLL_STOP_IN
    sweep = ROLL_STOP_OUT - ROLL_STOP_IN + 2 * ss['tooth_half']
    t0 = math.radians(a0)
    u0 = np.array([math.cos(t0), math.sin(t0), 0.0])
    pl, _ = plane_axis_angle(d, ax, d.FeatureByName('Top Plane'), a0 % 180, u0, 'SLOT_START')
    with Sk(d, pl, 'STOP_SLOT') as s_:
        q = lambda r, z: (RX + u0[0] * r, RY + u0[1] * r, z)
        s_.poly([q(ss['r'][0], CAP_Z1 - 1), q(ss['r'][1], CAP_Z1 - 1), q(ss['r'][1], ss['z_floor']), q(ss['r'][0], ss['z_floor'])])
        s_.cline((RX, RY, -80), (RX, RY, 40))
    want = math.radians(a0 + sweep / 2)
    done = False
    for rev in (False, True):
        v0, m0 = vol_com(d)
        d.ClearSelection2(True)
        s_.feat.Select2(False, 0)
        f = d.FeatureManager.FeatureRevolve2(True, True, False, True, rev, False, 0, 0, math.radians(sweep), 0, False, False, 0, 0, 0, 0, 0, True, False, True)
        d.ForceRebuild3(False)
        v1, m1 = vol_com(d)
        if f is not None and v0 - v1 > 1:
            cen = (m0 - m1) / (v0 - v1)
            ang = math.atan2(cen[1] - RY, cen[0] - RX)
            if abs(((ang - want + math.pi) % (2 * math.pi)) - math.pi) < 0.3:
                f.Name = 'STOP_SLOT'
                log(f'  STOP_SLOT: cut {v0 - v1:.0f} mm3 centred at {math.degrees(ang):.1f} deg (rev={rev})')
                done = True
                break
        if f is not None:
            d.EditUndo2(1)
            d.ForceRebuild3(False)
    if not done:
        raise SystemExit('STOP_SLOT failed')
    add_global(d, 'ROLL_STOP_IN', ROLL_STOP_IN)
    add_global(d, 'ROLL_STOP_OUT', ROLL_STOP_OUT)
    for f_ in ('SLOT_START', 'STOP_SLOT'):
        ft = d.FeatureByName(f_)
        dd = ft.GetFirstDisplayDimension
        while dd:
            dm = dd.GetDimension2(0)
            log('   dim', dm.FullName, round(math.degrees(dm.SystemValue), 2))
            dd = ft.GetNextDisplayDimension(dd)
    plane_val = round(math.degrees(d.FeatureByName('SLOT_START').GetFirstDisplayDimension.GetDimension2(0).SystemValue), 3)
    link_dim(d, 'D1@SLOT_START', f'"ROLL_STOP_IN" + {plane_val - ROLL_STOP_IN:g}')
    link_dim(d, 'D1@STOP_SLOT', f'"ROLL_STOP_OUT" - "ROLL_STOP_IN" + {2 * ss["tooth_half"]:g}')
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


SC = bool(SIDE_CENTRE)
SC47 = SIDE_CENTRE == '47'
Y_SPLIT = 340.0       # SC47: below this the sleeve is a closed ring on the fork front; the fork rear sits on its top
SC_BEND_R = 24.0      # side-centre: the power channel bends into the yaw exit on this radius (centreline), no sharp corner


def exit_bend(d, name):
    """SIDE CENTRE: the 16 x 6 power channel turns from straight down (centre Z RZ) into the yaw exit (centre Y Y_EX)
    on a SC_BEND_R arc about an axis along X, instead of the old square corner (vertical run to Y 316.6, radial exit)."""
    ys_, za = Y_EX + SC_BEND_R, RZ + SC_BEND_R
    pl_ = plane(d, 'Y', ys_, 'P_SC_BEND')
    with Sk(d, pl_, name) as s_:
        s_.poly(rect_pts((RX + P_OFF + CH_DX, ys_, RZ + CH_DZ), X, Z, PW, PH))
        s_.cline((RX - 80, ys_, za + CH_DZ), (RX + 80, ys_, za + CH_DZ))
    for rev in (False, True):
        v0, m0 = vol_com(d)
        d.ClearSelection2(True)
        s_.feat.Select2(False, 0)
        f = d.FeatureManager.FeatureRevolve2(True, True, False, True, rev, False, 0, 0, math.radians(90.0), 0, False, False, 0, 0, 0, 0, 0, True, False, True)
        d.ForceRebuild3(False)
        v1, m1 = vol_com(d)
        if f is not None and v0 - v1 > 1:
            cen = (m0 - m1) / (v0 - v1)
            if cen[1] < ys_ - 1.0:
                f.Name = name
                log(f'  {name}: cut {v0 - v1:.0f} mm3, centroid Y {cen[1]:.1f} Z {cen[2]:.1f} (rev={rev})')
                return f
        if f is not None:
            d.EditUndo2(1)
            d.ForceRebuild3(False)
    log(f'  {name}: nothing to cut on the bend side')


def ypt(r, a, y):
    return yaw_pt(r, a, y)


def build_fork_front():
    d = new_part(OUT / f"{NAMES['fork_front']}.SLDPRT")
    dm = DOME
    FB = os.environ.get('FRONT_BLEND', FRONT_BLEND)   # look-options/front_blend: '3' true wrap (adopted 2026-11-12); '1'/'2' earlier variants; '0' the old cheek
    FB = '' if FB == '0' else FB
    # FB: the two lower circles move up and out, so the cheek flares to the cuff's width; the chin / cowl below takes it in
    xl_, yl_, rl_ = (33.8, 372.0, 10.0) if FB == '3' else (22.0, 362.0, 10.0)   # FB 3: the cheek reaches the cuff's full width (+-43.8): no waist
    Y_CUT = 372.0 if FB in ('1', '2') else 392.0   # FB: the cheek is cut flat here; the chin / wrap loft continues its exact section
    hull = lambda k: hull_pts([(RX, RY, dm['r'] - k), (RX - xl_, yl_ + 0.5 * k, max(rl_ - k, 3.0)), (RX + xl_, yl_ + 0.5 * k, max(rl_ - k, 3.0))])
    fc = FRONT_CROWN
    z0, z1 = FRONT_Z[0], fc['z1']
    extrude(d, zsk(d, z0, 'CHEEK', lambda s: s.spline([(x, y, z0) for x, y in hull(0.0)])), 'CHEEK', fc['z0'] - z0, Z)
    # ORGANIC: the face crowns forward, an elliptical quarter (12 mm in, 7 mm forward) lofted through insets
    secs = []
    for i, a in enumerate((0.0, 25.0, 50.0, 70.0, 86.0)):
        t = math.radians(a)
        zz, k = fc['z0'] + (fc['z1'] - fc['z0']) * math.sin(t), fc['inset'] * (1 - math.cos(t))
        secs.append(zsk(d, zz, f'CHEEK_EDGE{i}', lambda s, zz=zz, k=k: s.spline([(x, y, zz) for x, y in hull(k)])))
    loft(d, secs, 'CHEEK_EDGE')
    if FB:
        extrude(d, ysk(d, Y_CUT, 'CHEEK_CUT', lambda s_: s_.poly(rect_pts((RX, Y_CUT, 0.0), X, Z, 140.0, 120.0))), 'CHEEK_CUT', 40.0, NY, cut=True)
    extrude(d, zsk(d, ROLL_OUT, 'BOSS', lambda s: s.circle((RX, RY, ROLL_OUT), 22.0)), 'BOSS', FRONT_Z[0] + 0.5 - ROLL_OUT, Z)
    def seat(s):
        s.circle((RX, SEAT_Y[0], YZ), 41.0)          # SLEEVE: the outer material is the sleeve loft
        s.circle((RX, SEAT_Y[0], YZ), SEAT_RI)
    extrude(d, ysk(d, SEAT_Y[0], 'SEAT', seat), 'SEAT', SEAT_Y[1] - SEAT_Y[0], Y)
    extrude(d, ysk(d, SEAT_Y[0], 'TAP_SECTOR', lambda s: sector(s, lambda r, a: ypt(r, a, SEAT_Y[0]), SEAT_RI + 1, 49.0, -170, -100, 3.0)),
            'TAP_SECTOR', SEAT_Y[1] - SEAT_Y[0], Y)
    cf = CUFF
    # SLEEVE: the cuff is the front half of the sleeve outline (envelope.SLEEVE); skirt down to Y 313.6 over the yaw exit,
    # rounded top edge at the front and sides
    import envelope as EV
    SL = EV.SLEEVE

    def clip_sk(y_, inset=0.0, top=0.0, nm=''):
        def drw(s_):
            pts = EV.sleeve_clip(y_, 'front', inset, top)
            s_.spline(pts, closed=False)
            s_.line(pts[-1], pts[0])
        return ysk(d, y_, nm, drw)
    cst = ((SL['y_bot'], 0.8, 0.0), (SL['y_bot'] + 1.2, 0.25, 0.0), (cf['y0'], 0.0, 0.0), (325.0, 0.0, 0.0), (330.0, 0.0, 0.0), (335.0, 0.0, 0.0), (340.0, 0.0, 0.0), (344.0, 0.0, 0.0), (348.0, 0.0, 0.0),
           (SEAT_Y[0], 0.0, 0.0), (356.0, 0.0, 0.0), (358.5, 0.0, 0.8), (360.5, 0.0, 2.0), (SEAT_Y[1], 0.0, SL['top_round']))
    if SC47:
        # the lower sleeve is a closed ring (the RS02 slides up through it: vendor body r 39.30 max against the r 39.75 bore);
        # above Y_SPLIT the cuff is the front half as before and the fork rear sits on the ring's flat top
        rst_ = [(y_, min(k_, 0.3 if y_ < SL['y_bot'] + 0.5 else 0.1), t_) for y_, k_, t_ in cst if y_ < Y_SPLIT - 1.0]   # small bottom insets: lean <= 40 deg
        rsecs = [ysk(d, y_, f'RING_S{i}', lambda s_, y_=y_, k_=k_, t_=t_: s_.spline(EV.sleeve_section(y_, k_, t_)))
                 for i, (y_, k_, t_) in enumerate(rst_ + [(Y_SPLIT, 0.0, 0.0)])]
        loft(d, rsecs, 'RING')
        cst = [(Y_SPLIT - 0.5, 0.0, 0.0)] + [q for q in cst if q[0] > Y_SPLIT + 1.0]
    csecs = [clip_sk(y_, k_, t_, f'CUFF_S{i}') for i, (y_, k_, t_) in enumerate(cst)]
    loft(d, csecs, 'CUFF')
    yaw_rev(d, 'CUFF_BORE', [(0, SL['y_bot'] - 1), (SL['bore_skirt'], SL['y_bot'] - 1), (SL['bore_skirt'], cf['y0']), (cf['ri'], cf['y0']),
                             (cf['ri'], SEAT_Y[0]), (0, SEAT_Y[0])], cut=True)
    # hollow the sleeve to a 2 mm skin (open at the bottom and toward the joint plane, where the fork rear closes it)
    hsecs = [ysk(d, y_, f'CUFF_IN_S{i}', lambda s, y_=y_: s.spline(EV.sleeve_section(y_, 2.0))) for i, y_ in enumerate([SL['y_bot'] - 0.5] + list(np.arange(318.0, 347.0, 4.0)) + [SEAT_Y[0] - 2.5])]   # every 4 mm: follows the waist, no loft bulge
    d.ClearSelection2(True)
    for k in hsecs:
        k.Select2(True, 1)
    fh = d.FeatureManager.InsertCutBlend(False, True, False, 1.0, 0, 0, False, 0, 0, 0, True, True)
    log('  CUFF_HOLLOW', fh is not None)
    ym = (SEAT_Y[0] + SEAT_Y[1]) / 2
    # the joint face: the 0.5 mm from the sleeve's back (JZ0 + 0.5) down to the joint plane, over the bolted pad
    _py0 = min([SEAT_Y[0]] + [y_ - 4.0 for _, y_ in JOINT_PTS])   # r 47: the pad reaches down past the lower screw pair
    _pw = max([2 * JX] + [2 * (abs(x_) + 5.0) for x_, y_ in JOINT_PTS if y_ < SEAT_Y[0]])
    extrude(d, zsk(d, JZ0 + 1.0, 'JOINT_PAD', lambda s: s.rpoly(rect_pts((RX, (_py0 + SEAT_Y[1]) / 2, JZ0 + 1.0), X, Y, _pw, SEAT_Y[1] - _py0), [4, 4, 4, 4])),
            'JOINT_PAD', 1.0, NZ, lo=-1.0)
    if FB == '3':
        # FRONT BLEND 3, true wrap: ONE loft from the cuff's whole front half (+-90 deg about the yaw axis) at the seat top up
        # into the cheek's exact crowned section at Y 392 (and on inside the cheek), so cuff, skirt and cheek are one
        # surface. Then the drum's 2 mm envelope (everything within 59 of the roll axis, behind Z 38.5, below Y 392) and the
        # RS02 rear cap (r 34.5 below Y 367.3) are cut out: the wrap hugs the drum's underside with an even shut line.
        from shapely.geometry import Polygon as _Poly, Point as _Pt, LineString as _LS, box as _box
        H_ = _Poly(hull(0.0))

        def cheek_sec(y_, n=41):
            cut = H_.intersection(_LS([(RX - 100, y_), (RX + 100, y_)]))
            xa, xb = cut.bounds[0], cut.bounds[2]
            pts = []
            for i in range(n):
                x_ = xa + (xb - xa) * i / (n - 1)
                dd = H_.exterior.distance(_Pt(x_, y_))
                t_ = math.acos(max(-1.0, 1.0 - min(dd, fc['inset']) / fc['inset']))
                pts.append((x_, fc['z0'] + (fc['z1'] - fc['z0']) * math.sin(t_)))
            return pts + [(xb, z0), (xa, z0)]

        def cuff_front(y_):
            P_ = _Poly([(q[0], q[2]) for q in EV.sleeve_section(y_)]).buffer(0).intersection(_box(RX - 90, YZ, RX + 90, 90))
            return list(P_.exterior.coords)[:-1]

        def ring(pts, n=72):
            # matched by four anchors (top centre, outboard side, bottom centre, inboard side) so every station's points
            # correspond: the cuff's side runs to the cheek's side, not to a point on its crown (that made the waist)
            P_ = _Poly(pts).buffer(0)
            ex = P_.exterior
            if ex.is_ccw:
                ex = type(ex)(list(ex.coords)[::-1])
            L_ = ex.length
            zc = P_.centroid.y
            an = [ex.project(_Pt(q)) for q in ((RX, 300.0), (RX + 400.0, zc), (RX, -300.0), (RX - 400.0, zc))]
            out = []
            for k in range(4):
                a0, a1 = an[k], an[(k + 1) % 4]
                span = (a1 - a0) % L_
                out += [ex.interpolate((a0 + span * i / (n // 4)) % L_).coords[0] for i in range(n // 4)]
            return out
        rA, rB = ring(cuff_front(361.9)), ring(cheek_sec(Y_CUT + 0.5))
        def lerp(t):
            # soft-start ease-out: leaves the cuff tangentially, then reaches the cheek's shape early, so the front skin
            # stays >= 4.4 mm above the drum cut (Z 38.5) where the drum's 59 circle widens (smoothstep left 0.7: slits)
            s_ = (1 - (1 - t) ** 2) * (lambda u: u * u * (3 - 2 * u))(min(1.0, t / 0.25))
            return [(a[0] + (b[0] - a[0]) * s_, a[1] + (b[1] - a[1]) * s_) for a, b in zip(rA, rB)]
        ys = [354.0, 357.5, 361.9, 364.0, 366.5, 369.0, 372.0, 375.0, 378.5, 382.0, 386.0, Y_CUT + 0.5, Y_CUT + 6.0]
        secs_ = []
        for i_, y_ in enumerate(ys):
            if y_ <= 361.9:
                pts = ring(cuff_front(y_))
            elif y_ >= Y_CUT + 0.4:
                pts = ring(cheek_sec(y_))
            else:
                pts = lerp((y_ - 361.9) / (Y_CUT + 0.5 - 361.9))
            secs_.append(ysk(d, y_, f'WRAP_S{i_}', lambda s_, pts=pts, y_=y_: s_.spline([(x, y_, z) for x, z in pts])))
        loft(d, secs_, 'WRAP')
        # the drum's 2 mm envelope: within 59 of the roll axis, Z -31..38.5, below Y 392 (nothing else of the part is there)
        from shapely.geometry import box as _bx
        env = _Pt(RX, RY).buffer(59.0, 180).intersection(_bx(RX - 70, 300.0, RX + 70, Y_CUT))
        env_pts = [(x, y, -31.0) for x, y in list(env.exterior.coords)[:-1]]
        extrude(d, zsk(d, -31.0, 'DRUM_ENV', lambda s_: s_.poly(env_pts)), 'DRUM_ENV', 38.5 + 31.0, Z, cut=True, lo=-1.0)
        yaw_rev(d, 'WRAP_RS02_CLEAR', [(0, 361.0), (34.5, 361.0), (34.5, 367.3), (0, 367.3)], cut=True)
        extrude(d, ysk(d, SEAT_Y[1] - 3.5, 'RS02_ACCESS', lambda s_: [s_.circle(ypt(36.5, a_, SEAT_Y[1] - 3.5), 3.5) for a_ in (64.0, 104.0)]),
                'RS02_ACCESS', 140.0, Y, cut=True)
    elif FB:
        # FRONT BLEND: one loft from the cuff's own front (Y 356) into the cheek's exact crowned section at the flat cut
        # (Y 372), so the cheek runs down into the cuff as one surface. '1' plain: the cuff front from Z 40.5;
        # '2' wrap: from Z 24, so the bottom wraps round the cuff. Above Y 361 the chin keeps r >= 34.5 (RS02 rear cap,
        # r 32.5) and, where it is within 59 of the roll axis, Z >= 38.5 (2.5 off the drum's front).
        from shapely.geometry import Polygon as _Poly, Point as _Pt, LineString as _LS, box as _box
        z0_ = 40.5 if FB == '1' else 24.0
        H_ = _Poly(hull(0.0))

        def cheek_sec(y_, n=41):
            cut = H_.intersection(_LS([(RX - 100, y_), (RX + 100, y_)]))
            xa, xb = cut.bounds[0], cut.bounds[2]
            pts = []
            for i in range(n):
                x_ = xa + (xb - xa) * i / (n - 1)
                dd = H_.exterior.distance(_Pt(x_, y_))
                t_ = math.acos(max(-1.0, 1.0 - min(dd, fc['inset']) / fc['inset']))
                pts.append((x_, fc['z0'] + (fc['z1'] - fc['z0']) * math.sin(t_)))
            return pts + [(xb, z0), (xa, z0)]      # front crown left to right, then the back on the cheek's back face (Z 39)

        def cuff_sec(y_, zl):
            P_ = _Poly([(q[0], q[2]) for q in EV.sleeve_section(y_)]).buffer(0).intersection(_box(RX - 80, zl, RX + 80, 90))
            return list(P_.exterior.coords)[:-1]

        def ring(pts, n=60):
            P_ = _Poly(pts).buffer(0)
            ex = P_.exterior
            if ex.is_ccw:
                ex = type(ex)(list(ex.coords)[::-1])
            L_ = ex.length
            c0 = max(ex.coords, key=lambda q: q[1])
            d0 = ex.project(_Pt(c0))
            return [ex.interpolate((d0 + L_ * i / n) % L_).coords[0] for i in range(n)]
        r0, r3 = ring(cuff_sec(356.0, z0_)), ring(cheek_sec(Y_CUT + 0.5))
        lerp = lambda t: [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(r0, r3)]
        # the drum rule (Z >= 38.5) only where the chin is within 59 of the roll axis: near the centre; the sides stay low
        # (they are what carries the cheek into the seat ring, as the lobes did)
        def drum_ok(pts, y_):
            out = []
            for x, z in pts:
                if math.hypot(x - RX, RY - y_) < 59.0:
                    z = max(z, 40.5)
                out.append((x, z))
            return out
        r1 = drum_ok(lerp(0.35), 361.5)
        r2 = drum_ok(lerp(0.65), 366.5)
        r4 = ring(cheek_sec(Y_CUT + 6.0))
        secs_ = []
        for i_, (y_, pts) in enumerate(((356.0, r0), (361.5, r1), (366.5, r2), (Y_CUT + 0.5, r3), (Y_CUT + 6.0, r4))):
            secs_.append(ysk(d, y_, f'CHIN_S{i_}', lambda s_, pts=pts, y_=y_: s_.spline([(x, y_, z) for x, z in pts])))
        loft(d, secs_, 'CHIN')
        # keep the RS02 rear cap clear (r 32.5 + 2 above the seat)
        yaw_rev(d, 'CHIN_RS02_CLEAR', [(0, 361.0), (34.5, 361.0), (34.5, 367.0), (0, 367.0)], cut=True)
        # chin root: the load path from the cheek into the seat ring, as the lobes carried it: a ring segment r 34.5-41 over the
        # front (40-140 deg) from the seat top to Y 367, inside the chin's outer surface (RS02 cap r 32.5 + 2; drum rule held)
        extrude(d, ysk(d, SEAT_Y[1], 'CHIN_ROOT', lambda s_: sector(s_, lambda r, a: ypt(r, a, SEAT_Y[1]), 34.5, 41.0, 40.0, 140.0, 2.0)),
                'CHIN_ROOT', 367.0 - SEAT_Y[1], Y, lo=-1.0)
        # driver access to the two front RS02 screws (64 / 104 deg), blocked by the cheek: Ø7 straight up, plugged flush after
        extrude(d, ysk(d, SEAT_Y[1] - 3.5, 'RS02_ACCESS', lambda s_: [s_.circle(ypt(36.5, a_, SEAT_Y[1] - 3.5), 3.5) for a_ in (64.0, 104.0)]),
                'RS02_ACCESS', 140.0, Y, cut=True)
    # (the round-2 rear web is dropped: it sat 0.5 mm off the fork rear arm, carried no load and cost 6.5 g)
    # ---- cuts
    extrude(d, zsk(d, z0 - 1, 'DOME_POCKETS', lambda s: [sector(s, lambda r, a: rpt(r, a, z0 - 1), dm['pocket_r'][0], dm['pocket_r'][1], a0, a1, 3.0)
                                                         for a0, a1 in dm['pockets']]), 'DOME_POCKETS', z1 - z0 - dm['back_t'] + 1, Z, cut=True)
    try:     # the sleeve's back is open toward the fork rear, so the notch may find nothing left to cut
        if SC47:
            raise SystemExit('closed ring: the exit runs inside it, no notch')
        extrude(d, ysk(d, SL['y_bot'] - 1, 'CUFF_NOTCH', lambda s: sector(s, lambda r, a: ypt(r, a, SL['y_bot'] - 1), cf['ri'] - 1, YZ - JZ0 + 3.0, cf['notch'][0], cf['notch'][1], 2.0)),
                'CUFF_NOTCH', Y_EX + 3 + WALL + 1.5 - (SL['y_bot'] - 1), Y, cut=True)
    except SystemExit:
        log('  CUFF_NOTCH: nothing to cut (sleeve open at the back)')
    if SC:
        exit_bend(d, 'EXIT_BEND')
    extrude(d, ysk(d, SEAT_Y[0] - 1, 'SEAT_BORE', lambda s: s.circle((RX, SEAT_Y[0] - 1, YZ), SEAT_RI)), 'SEAT_BORE', 12, Y, cut=True)
    extrude(d, zsk(d, ROLL_OUT - 1, 'ROLL_BORE', lambda s: s.circle((RX, RY, ROLL_OUT - 1), 10.75)), 'ROLL_BORE', 30, Z, cut=True)
    extrude(d, zsk(d, ROLL_OUT - 1, 'OUT_HOLES', lambda s: [s.circle(rpt(15.2, 30 + 60 * k, ROLL_OUT - 1), 2.25) for k in range(6)]), 'OUT_HOLES', 30, Z, cut=True)
    extrude(d, zsk(d, CAP_FLOOR - 2, 'OUT_CB', lambda s: [s.circle(rpt(15.2, 30 + 60 * k, CAP_FLOOR - 2), 4.25) for k in range(6)]), 'OUT_CB', 10, Z, cut=True)
    extrude(d, zsk(d, CAP_FLOOR, 'CAP_RECESS', lambda s: s.circle((RX, RY, CAP_FLOOR), 24.0)), 'CAP_RECESS', 8, Z, cut=True)
    extrude(d, ysk(d, SEAT_Y[0] - 5, 'RS02_HOLES', lambda s: [s.circle(ypt(36.5, a, SEAT_Y[0] - 5), 1.8) for a in RS02_SCREWS]), 'RS02_HOLES', 30, Y, cut=True)
    extrude(d, ysk(d, SEAT_Y[1] - 3.5, 'RS02_CB', lambda s: [s.circle(ypt(36.5, a, SEAT_Y[1] - 3.5), 3.3) for a in RS02_SCREWS]), 'RS02_CB', 10, Y, cut=True)
    extrude(d, ysk(d, SEAT_Y[0] - 1, 'SOCKETS', lambda s: [sector(s, lambda r, a: ypt(r, a, SEAT_Y[0] - 1), 30.0, 40.5, a0, a1, 1.5) for a0, a1 in SOCKET_POCKETS]),
            'SOCKETS', 10, Y, cut=True)
    extrude(d, ysk(d, TAP_Y[0], 'TAP_ARC', lambda s: sector(s, lambda r, a: ypt(r, a, TAP_Y[0]), 40.5, 47.5, -168, -94)), 'TAP_ARC', TAP_Y[1] - TAP_Y[0], Y, cut=True)
    tz = YZ - 41.0
    extrude(d, zsk(d, tz, 'TAP_LINK', lambda s: s.poly(rect_pts((RX - 4.0, sum(TAP_Y) / 2, tz), X, Y, 7.0, 6.0))), 'TAP_LINK', tz - RZ, NZ, cut=True)
    if os.environ.get('PLUG_POCKET', 'a') == 'a':      # adopted 2026-11-12 (hidden; PLUG_POCKET=0 builds without it)
        # PLUG POCKET (a) mock-up (look-options/plug_pocket): a hidden column straight up from the 173 deg RS02 socket, inside
        # the wall (2-4 mm to the outer skin), opening only into the drum-facing surface: room for the XT30(2+2)-F pushed
        # down from above and its lead's U-turn into the socket pocket and tap
        extrude(d, ysk(d, 360.0, 'PLUG_COLUMN', lambda s_: sector(s_, lambda r, a: ypt(r, a, 360.0), 30.5, 41.0, 159.0, 187.0, 2.0)),
                'PLUG_COLUMN', 374.0 - 360.0, Y, cut=True)
    if LOOK == 'c':
        # LOOK c: the arm's front/back seam (upper_arm_organic_front/back split plane through the yaw axis, seen on the arm's
        # outboard and inboard sides) carried up the cuff as a 1.0 x 0.6 mm shut line at yaw 0 and 180 deg
        prof = []
        for y_ in np.arange(EV.SLEEVE['y_bot'], SEAT_Y[1] - 4.0 + 0.01, 1.0):
            prof.append(y_)
        pl0 = plane(d, 'Z', YZ, 'P_Z_YZ')
        with Sk(d, pl0, 'SEAM_LINES') as s_:
            for sg, a_ in ((1, 0.0), (-1, 180.0)):
                inner = [(RX + sg * (EV.sleeve_r(a_, y_) - 0.6), y_, YZ) for y_ in prof]
                outer = [(RX + sg * (EV.sleeve_r(a_, y_) + 3.0), y_, YZ) for y_ in prof[::-1]]
                s_.poly(inner + outer)
        extrude(d, s_.feat, 'SEAM_LINES', 1.0, (0, 0, 1), cut=True, mode=MID)
    # the outer joint pair (X +-27): insert bosses inside the sleeve's hollow, from the joint face 13 mm in
    for i_, (dx, jy) in enumerate(JOINT_PTS[2:]):
        extrude(d, zsk(d, JZ0 + 0.5, f'INSERT_BOSS_{i_}', lambda s, dx=dx, jy=jy: s.circle((RX + dx, jy, JZ0 + 0.5), 4.5)),
                f'INSERT_BOSS_{i_}', 11.0, Z, lo=-1.0)   # 11: 1.1 mm off the socket-tap arc (r 47.5); the cuff is mostly solid at Y 357
    extrude(d, zsk(d, JZ0 - 1, 'JOINT_INSERTS', lambda s: [s.circle((RX + dx, jy, JZ0 - 1), 2.8) for dx, jy in JOINT_PTS]),
            'JOINT_INSERTS', 12, Z, cut=True)
    return finish_part(d, 'fork_front')


# ====================================================================================================== fork rear cheek
def build_fork_rear():
    d = new_part(OUT / f"{NAMES['fork_rear']}.SLDPRT")
    roll_rev(d, 'CHEEK', [(0, JZ0), (CHEEK_R, JZ0), (CHEEK_R, BACK_Z), (0, BACK_Z)], [0, 1.0, 6.0, 0])   # DRESSED 2: R6 back edge (arm drum R7)
    extrude(d, zsk(d, HOUSE_Z0, 'HOUSING', lambda s: s.circle((RX, RY, HOUSE_Z0), HOUSE_R)), 'HOUSING', HOUSE_Z0 - JZ0, NZ)
    # STOP REV 2: a pad on the housing under the tooth (sector outside the housing's r 33, between the housing face and
    # the joint plane, so nothing outside the present outline changes)
    _ss = STOP_SLOT
    extrude(d, zsk(d, HOUSE_Z0, 'STOP_PAD', lambda s: sector(s, lambda r, a: rpt(r, a, HOUSE_Z0), _ss['pad_r'][0] - 1.0, _ss['pad_r'][1],
                                                            _ss['tooth_angle'] - _ss['pad_half'], _ss['tooth_angle'] + _ss['pad_half'], _ss['pad_corner'])),
            'STOP_PAD', HOUSE_Z0 - JZ0, NZ)
    # SLEEVE: above the cuff the arm is the D-section loft; from the cuff top down it is the rear half of the sleeve
    # outline the fork front's cuff shares (envelope.SLEEVE), so cuff and arm read as one surface split at the joint plane
    import envelope as EV
    SL = EV.SLEEVE
    asecs = []

    def clip_sk(y_, side, inset=0.0, top=0.0, nm='', zc=None):
        def drw(s_):
            pts = EV.sleeve_clip(y_, side, inset, top, zc=zc)
            if side == 'rear':
                pts = pts[::-1]
            s_.spline(pts, closed=False)
            s_.line(pts[-1], pts[0])
        return ysk(d, y_, nm, drw)
    rst = ((SL['y_bot'], 0.8, 0.0), (SL['y_bot'] + 1.2, 0.25, 0.0), (320.0, 0.0, 0.0), (325.0, 0.0, 0.0), (330.0, 0.0, 0.0), (335.0, 0.0, 0.0), (340.0, 0.0, 0.0), (344.0, 0.0, 0.0), (348.0, 0.0, 0.0), (352.0, 0.0, 0.0),
           (356.0, 0.0, 0.0), (358.5, 0.0, 0.8), (360.5, 0.0, 2.0), (SEAT_Y[1], 0.0, SL['top_round']))
    if SC47:      # the fork rear starts on the ring's flat top
        rst = [(Y_SPLIT, 0.0, 0.0)] + [q for q in rst if q[0] > Y_SPLIT + 1.0]
    for i, (y_, k_, top_) in enumerate(rst):
        asecs.append(clip_sk(y_, 'rear', k_, top_, f'SLEEVE_R{i}'))
    for i, (y_, cx_, w_, dp_) in enumerate(EV.ARM_STATIONS[:2][::-1]):
        def drw(s_, y_=y_, cx_=cx_, w_=w_, dp_=dp_):
            pts = EV.arm_section(y_, cx_, w_, dp_)
            s_.spline(pts, closed=False)
            s_.line(pts[-1], pts[0])
        asecs.append(ysk(d, y_, f'ARM_S{i}', drw))
    loft(d, asecs, 'ARM')
    ym = (SEAT_Y[0] + SEAT_Y[1]) / 2
    # SMOOTH: the stop tooth on the housing's front face runs in the cap's arc slot (2 mm all round, contact at the stops)
    ss = STOP_SLOT
    extrude(d, zsk(d, HOUSE_Z0, 'STOP_TOOTH', lambda s: sector(s, lambda r, a: rpt(r, a, HOUSE_Z0), ss['tooth_r'][0], ss['tooth_r'][1],
                                                               ss['tooth_angle'] - ss['tooth_half'], ss['tooth_angle'] + ss['tooth_half'], 0.8)),
            'STOP_TOOTH', (ss['z_floor'] - 2.0) - HOUSE_Z0, Z)
    def _in_root(p):
        r_ = math.hypot(p[0] - RX, p[1] - RY)
        a_ = math.degrees(math.atan2(p[1] - RY, p[0] - RX)) % 360.0
        return abs(p[2] - HOUSE_Z0) < 0.05 and ss['tooth_r'][0] - 0.6 < r_ < ss['tooth_r'][1] + 0.6 and abs(a_ - ss['tooth_angle']) < ss['tooth_half'] + 2.0
    fillet(d, edges_where(d, _in_root), [ss['root_r'], 1.0], 'TOOTH_ROOT')
    # the hollow stops 1.6 short of the joint plane: a front plate, so the skin does not run out to a knife edge where the
    # outline meets the plane at a shallow angle (the cable channel cuts through the plate where the cables pass)
    hy = [y_ for y_ in ((Y_SPLIT - 0.5, 344.0, 349.0) if SC47 else (SL['y_bot'] + 2.0, 322.0, 330.0, 338.0, 344.0, 349.0)) if min(q[2] for q in EV.sleeve_section(y_, 2.0)) < JZ0 - 1.6 - 1.0]
    hs = [clip_sk(y_, 'rear', 2.0, 0.0, f'SLEEVE_R_IN{i}', zc=JZ0 - 1.6) for i, y_ in enumerate(hy)]   # SIDE CENTRE: the thin bottom stays solid
    d.ClearSelection2(True)
    for k in hs:
        k.Select2(True, 1)
    v0 = vol(d)
    fh = d.FeatureManager.InsertCutBlend(False, True, False, 1.0, 0, 0, False, 0, 0, 0, True, True)
    d.ForceRebuild3(False)
    log('  SLEEVE_R_HOLLOW', fh is not None, round(v0 - vol(d), 1))
    # ---- cuts
    roll_rev(d, 'SEAT', [(0, HOUSE_Z0 + 1), (BRG_SEAT_R, HOUSE_Z0 + 1), (BRG_SEAT_R, BRG_LIP_Z), (BRG_LIP_R, BRG_LIP_Z), (BRG_LIP_R, RZ), (0, RZ)],
             [0, 0, 0, 0, 0, 0], cut=True)
    # flat-topped teardrop over the housing bore (the fork rear prints upright, so the bore's top is an overhang): 45 deg
    # flanks tangent to the bore, cut flat 0.4 above it
    _t, _f = BRG_SEAT_R / math.sqrt(2), BRG_SEAT_R * math.sqrt(2) - (BRG_SEAT_R + 0.4)
    extrude(d, zsk(d, HOUSE_Z0 + 1, 'SEAT_TEARDROP', lambda s_: s_.poly([(RX - _t, RY + _t, HOUSE_Z0 + 1), (RX - _f, RY + BRG_SEAT_R + 0.4, HOUSE_Z0 + 1),
                                                                          (RX + _f, RY + BRG_SEAT_R + 0.4, HOUSE_Z0 + 1), (RX + _t, RY + _t, HOUSE_Z0 + 1), (RX, RY, HOUSE_Z0 + 1)])),
            'SEAT_TEARDROP', (HOUSE_Z0 + 1) - BRG_LIP_Z, NZ, cut=True, lo=-1.0)
    zc = RZ + PH / 2 + CH_DZ
    ch_lo = (Y_EX + SC_BEND_R) if SC else (Y_EX - 3.0)       # SIDE CENTRE: the straight run stops where the bend starts
    extrude(d, zsk(d, zc, 'CH_P', lambda s: s.rpoly(rect_pts((RX + P_OFF + CH_DX, (RY + 9.0 + ch_lo) / 2, zc), X, Y, PW, RY + 9.0 - ch_lo), [1] * 4)),
            'CH_P', PH, NZ, cut=True)
    zc = RZ + SH / 2 + CH_DZ
    sig_end = SEAT_Y[0] + WALL

    def ch_s(s):
        s.rpoly(rect_pts((RX + S_OFF + CH_DX, (RY + 9.0 + sig_end) / 2, zc), X, Y, SW, RY + 9.0 - sig_end), [1] * 4)
    extrude(d, zsk(d, zc, 'CH_S', ch_s), 'CH_S', SH, NZ, cut=True)
    extrude(d, zsk(d, zc, 'CH_JOIN', lambda s: s.poly(rect_pts((RX + 3.0 + CH_DX, sig_end + 3.0, zc), X, Y, 6.0, 6.0))), 'CH_JOIN', SH, NZ, cut=True)
    if SC:
        exit_bend(d, 'EXIT_BEND')
    else:
        extrude(d, zsk(d, RZ - 3.0, 'EXIT_CH', lambda s: s.poly(rect_pts((RX - 6.0 + CH_DX, Y_EX, RZ - 3.0), X, Y, 16.0, 6.0))), 'EXIT_CH', (YZ - 37.0) - RZ + 3.0 + 1, Z, cut=True, lo=-1.0)
    # the outer joint pair (X +-27): bosses through the sleeve's hollow, from the joint plane back to 1 mm inside the outline
    for i_, (dx, jy) in enumerate(JOINT_PTS[2:]):
        _sec = EV.sleeve_section(jy, 0.0, 0.0, 720)
        zs_ = [q[2] for q in _sec if abs(q[0] - (RX + dx)) <= 4.5 and q[2] < JZ0]
        z_end = max(zs_) + 1.0
        extrude(d, zsk(d, JZ0, f'JOINT_BOSS_{i_}', lambda s, dx=dx, jy=jy: s.circle((RX + dx, jy, JZ0), 4.5)), f'JOINT_BOSS_{i_}', JZ0 - z_end, NZ, lo=-1.0)
    extrude(d, zsk(d, BACK_Z - 4, 'JOINT_HOLES', lambda s: [s.circle((RX + dx, jy, BACK_Z - 4), 2.25) for dx, jy in JOINT_PTS]), 'JOINT_HOLES', SHH + 5, Z, cut=True)
    # counterbores one at a time: the inner pair seats 5.5 behind the joint plane; the others, where the sleeve is only
    # about 6 mm deep behind it, 3.0
    for dx, jy in JOINT_PTS:
        nm_ = f'JOINT_CB_{dx:+.0f}_{jy:.0f}'.replace('+', 'p').replace('-', 'm')
        zf_ = JZ0 - (5.5 if abs(dx) < 20 else 3.0)
        try:
            extrude(d, zsk(d, BACK_Z - 4, nm_, lambda s, dx=dx, jy=jy: s.circle((RX + dx, jy, BACK_Z - 4), 4.0)), nm_, zf_ - (BACK_Z - 4), Z, cut=True)
        except SystemExit as e_:
            log(f'  {nm_} failed: {e_}')
    tz = YZ - 41.0
    extrude(d, zsk(d, JZ0 + 0.5, 'TAP_LINK', lambda s: s.poly(rect_pts((RX - 4.0, sum(TAP_Y) / 2, JZ0 + 0.5), X, Y, 7.0, 6.0))), 'TAP_LINK', JZ0 + 0.5 - RZ, NZ, cut=True, lo=-1.0)
    # (YAW_CLEAR, the r 41.5 cylinder, no longer touches the fork rear: everything of it is behind the joint plane)
    # DRESSED: soft back edges
    fillet(d, edges_where(d, lambda p: abs(p[2] - BACK_Z) < 0.05 and np.hypot(p[0] - (RX + 30), p[1] - 357) > 6.0 and np.hypot(p[0] - (RX - 30), p[1] - 357) > 6.0), [3.0, 2.0, 1.5], 'BACK_ROUND')
    return finish_part(d, 'fork_rear')


# ==================================================================================================== fork press-in cap
def build_fork_cap():
    d = new_part(OUT / f"{NAMES['fork_cap']}.SLDPRT")
    z0 = CAP_FLOOR
    zt = FRONT_CROWN['z1'] - 1.5           # recessed 1.5 below the crown at its rim, like the arm's caps
    roll_rev(d, 'CAP', [(0, z0), (23.8, z0), (23.8, zt - 1.0), (18.0, zt), (0, zt + 0.8)], [0, 0.4, 1.0, 6.0, 0])
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
    yaw_rev(d, 'FLOOR', [(DISH_R0 - 0.5, 312.8), (38.6, 312.8), (38.6, DISH_Y), (DISH_R0 + DISH_FILLET, DISH_Y), (DISH_R0 - 0.5, min(DISH_Y + DISH_FILLET, RS02_OUT - 0.01))],
            [0, 0, 0.8, 1.0, 0])     # HUB REV B: thicker floor, with a fillet into the step ring
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
    # ---- the spigot groove (arm thread's ridge section); full depth over the centre arcs, stepped run-outs at the ends
    g = hb['groove']
    def groove_profile(k):
        d_ = (g['r_out'] - g['r_bot']) * k
        rb = g['r_out'] - d_
        # mouth corners stay at Y 297.0 / 301.0; the bottom narrows with depth along the same flank angles
        y0b = g['y_open'][0] + (g['y_bot'][0] - g['y_open'][0]) * k
        y1b = g['y_open'][1] - (g['y_open'][1] - g['y_bot'][1]) * k
        return [(g['r_out'] + 1.0, g['y_open'][0] - 0.58), (g['r_out'], g['y_open'][0]), (rb, y0b), (rb, y1b), (g['r_out'], g['y_open'][1]),
                (g['r_out'] + 3.0, g['y_open'][1])]
    # REV C+ (arm thread, 2026-11-11 19:40Z): 0.4 rounds at both groove bottom corners; the high flank blends into the disc
    # underside at Y 302 with R1.2 (as large as the 45 deg flank allows while the Y 302 bearing face stays from r 37)
    GR = [0.0, 0.0, 0.4, 1.0, 1.2, 0.0]     # 19:27Z: the 45 deg side bottom corner 1.0 (the arm tries the same), the load side 0.4
    # full-depth arcs as revolve cuts; run-outs as loft cuts through sections of growing depth (smooth)
    def gplane(a_deg, tag):
        ta = math.radians(a_deg)
        ua = (math.cos(ta), 0.0, math.sin(ta))
        plg, _ = plane_axis_angle(d, ax, d.FeatureByName('Front Plane'), a_deg % 180, ua, f'P_GROOVE_{tag}')
        return plg, ua
    for ci, cen in enumerate(g['centres']):
        a0, a1 = cen - g['full_half'], cen + g['full_half']
        plg, ua = gplane(a0, f'{ci}_full')
        with Sk(d, plg, f'GROOVE_{ci}_full') as s_:
            s_.rpoly([(RX + r_ * ua[0], y_, YZ + r_ * ua[2]) for r_, y_ in groove_profile(1.0)], GR)
            s_.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
        want = math.radians(cen)
        done = False
        for rev in (False, True):
            v0, m0 = vol_com(d)
            d.ClearSelection2(True)
            s_.feat.Select2(False, 0)
            f = d.FeatureManager.FeatureRevolve2(True, True, False, True, rev, False, 0, 0, math.radians(a1 - a0), 0, False, False, 0, 0, 0, 0, 0, True, False, True)
            d.ForceRebuild3(False)
            v1, m1 = vol_com(d)
            if f is not None and v0 - v1 > 1e-3:
                cen_ = (m0 - m1) / (v0 - v1)
                ang = math.atan2(cen_[2] - YZ, cen_[0] - RX)
                if abs(((ang - want + math.pi) % (2 * math.pi)) - math.pi) < 0.2:
                    f.Name = f'GROOVE_{ci}_full'
                    done = True
                    break
            if f is not None:
                d.EditUndo2(1)
                d.ForceRebuild3(False)
        log(f'  GROOVE_{ci}_full {a0:.0f}-{a1:.0f}', done)
        # REV C+: each run-out is one revolve of the full section about an axis parallel to the yaw axis at r 55 on the
        # radial plane where the full arc ends: the cut leaves the arc tangentially and its depth falls to zero at 10 deg
        # (1.48 / 1.28 / 0.90 / 0.34 / 0 mm at 1.3 / 3.9 / 6.5 / 8.9 / 10 deg); plain, no lofts
        E_RO = 54.988
        for side, a_end, sgn in (('lo', a0, -1), ('hi', a1, 1)):
            plg, ua = gplane(a_end, f'{ci}_{side}_ro')
            with Sk(d, plg, f'GROOVE_{ci}_{side}') as s_:
                s_.rpoly([(RX + r_ * ua[0], y_, YZ + r_ * ua[2]) for r_, y_ in groove_profile(1.0)], GR)
                s_.cline((RX + E_RO * ua[0], 280.0, YZ + E_RO * ua[2]), (RX + E_RO * ua[0], 330.0, YZ + E_RO * ua[2]))
            want_ = math.radians(a_end + sgn * 4.0)
            ok_ = False
            for rev in (False, True):
                v0, m0 = vol_com(d)
                d.ClearSelection2(True)
                s_.feat.Select2(False, 0)
                f = d.FeatureManager.FeatureRevolve2(True, True, False, True, rev, False, 0, 0, math.radians(19.0), 0, False, False, 0, 0, 0, 0, 0, True, False, True)
                d.ForceRebuild3(False)
                v1, m1 = vol_com(d)
                if f is not None and v0 - v1 > 1e-3:
                    cen_ = (m0 - m1) / (v0 - v1)
                    ang = math.atan2(cen_[2] - YZ, cen_[0] - RX)
                    if abs(((ang - want_ + math.pi) % (2 * math.pi)) - math.pi) < 0.06:
                        f.Name = f'GROOVE_{ci}_{side}'
                        ok_ = True
                        log(f'  GROOVE_{ci}_{side} run-out revolve: cut {v0 - v1:.1f} mm3 centroid {math.degrees(ang):.1f} deg')
                        break
                if f is not None:
                    d.EditUndo2(1)
                    d.ForceRebuild3(False)
            if not ok_:
                log(f'  GROOVE_{ci}_{side} run-out revolve FAILED')
    # REV C: fill the window band over the fore-aft sectors
    bf = hb['band_fill']
    if bf['on']:
        extrude(d, ysk(d, bf['y'][0], 'BAND_FILL', lambda s: [sector(s, lambda r, a: ypt(r, a, bf['y'][0]), bf['r'][0], bf['r'][1], a0_, a1_, 2.0)
                                                             for a0_, a1_ in bf['sectors']]), 'BAND_FILL', bf['y'][1] - bf['y'][0], Y, lo=-1.0)
    # REV C+ lever (a): wall fill inside the spigot over the groove arcs (parametric: HUB['wall_fill'], global WALL_FILL_ON)
    wf = hb['wall_fill']
    if wf['on']:
        extrude(d, ysk(d, wf['y'][0], 'WALL_FILL', lambda s: [sector(s, lambda r, a: ypt(r, a, wf['y'][0]), wf['r'][0], wf['r'][1], a0_, a1_, wf['end_r'])
                                                             for a0_, a1_ in wf['sectors']]), 'WALL_FILL', wf['y'][1] - wf['y'][0], Y, lo=-1.0)
    # REV C+: R0.3 in the concave corner between the spigot (r 35.8) and the disc face (Y 302.0); the arm breaks its bore-to-end-face
    # edge by 0.5 (20:33Z). A revolve boss of the fillet region, overlapping the solid by 0.05
    rc_ = hb['disc_corner_r']
    pl0 = plane(d, 'Z', YZ, 'P_Z_YZ')
    with Sk(d, pl0, 'DISC_CORNER') as s_:
        sm_ = d.SketchManager
        P = lambda r_, y_: s_.p((RX + r_, y_, YZ))
        A, B, E1, E2, O = P(35.75, 302.05), P(35.75, 302.0 - rc_), P(35.8, 302.0 - rc_), P(35.8 + rc_, 302.0), P(35.8 + rc_, 302.0 - rc_)
        C = P(35.8 + rc_, 302.05)
        for u_, v_ in ((A, B), (B, E1), (E2, C), (C, A)):
            sm_.CreateLine(u_[0], u_[1], 0, v_[0], v_[1], 0)
        sm_.CreateArc(O[0], O[1], 0, E1[0], E1[1], 0, E2[0], E2[1], 0, -1)     # the short quarter (the long way made a bead proud of r 35.8)
        s_.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
    try:
        revolve(d, s_.feat, 'DISC_CORNER')
    except SystemExit:
        log('  DISC_CORNER revolve FAILED')
    # REV C+ (required by the arm: its bore corner gets a 0.25 fillet): R0.4 round on the spigot's bottom outer edge
    # (r 35.8, Y 296), made as a revolve cut of the exact corner region (the fillet feature will not build on the imported
    # edge): the square r 35.4-35.8 x Y 296-296.4 less the quarter disc about (35.4, 296.4)
    pl0 = plane(d, 'Z', YZ, 'P_Z_YZ')
    with Sk(d, pl0, 'SPIGOT_EDGE') as s_:
        sm_ = d.SketchManager
        P = lambda r_, y_: s_.p((RX + r_, y_, YZ))
        A, B, C, O = P(35.4, 295.6), P(36.2, 295.6), P(36.2, 296.4), P(35.4, 296.4)
        E1, E2 = P(35.8, 296.4), P(35.4, 296.0)
        # outline: from the bottom face below (Y 295.6) round to the cylinder side (r 36.2), then the arc closes it
        for u_, v_ in ((E2, A), (A, B), (B, C), (C, E1)):
            sm_.CreateLine(u_[0], u_[1], 0, v_[0], v_[1], 0)
        sm_.CreateArc(O[0], O[1], 0, E1[0], E1[1], 0, E2[0], E2[1], 0, -1)
        s_.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
    try:
        revolve(d, s_.feat, 'SPIGOT_EDGE', cut=True)
    except SystemExit:
        log('  SPIGOT_EDGE revolve cut FAILED')
    # REV C: root fillets where the seam lugs meet the spigot's underside
    # REV C+ (arm side): 1.0 only on the lugs' X-facing sides (the arcs at r 19 and r 30); nothing on the Z-facing sides,
    # where the arm's hub posts sit 0.1 under the spigot; no lug thickening
    d.ForceRebuild3(False)
    def _r(q):
        return math.hypot(q[0] - RX, q[2] - YZ)
    roots = edges_where(d, lambda p: abs(p[1] - 296.0) < 0.05 and abs(p[2] - YZ) < 9.0,
                        pair=lambda p0, p1: all(29.2 < _r(q) < 31.0 for q in (p0, p1)))     # the flat outer (X-facing) face at r 29.5; the inner side runs into the bore with no root corner
    log('  LUG_ROOTS edges', len(roots))
    fillet(d, roots, [1.0], 'LUG_ROOTS')
    for k, v in (('GROOVE_ON', hb['groove_on']), ('WALL_FILL_ON', hb['wall_fill']['on']), ('SPIGOT_EXT_ON', hb['spigot_ext_on']), ('SPIGOT_EXT_LEN', hb['spigot_ext_len']), ('SPIGOT_TAPER', hb['spigot_taper']),
                 ('LUG2_ON', hb['lug2_on']), ('LUG2_ANGLE', hb['lug2_angle'])):
        add_global(d, k, v)
    for dims_ in (('D1@SPIGOT_EXT', '"SPIGOT_EXT_LEN"'), ('D1@P_LUG2', '"LUG2_ANGLE"')):
        link_dim(d, *dims_)
    em = d.GetEquationMgr
    for feat_, var in (('SPIGOT_EXT', 'SPIGOT_EXT_ON'), ('LUG2', 'LUG2_ON')):
        em.Add2(-1, f'"{feat_}" = IIF("{var}" = 1, "unsuppressed", "suppressed")', True)
    d.ForceRebuild3(False)
    log('  hub prepared features:', [(n, d.FeatureByName(n).IsSuppressed2(1, NUL)[0] if d.FeatureByName(n) else None) for n in ('SPIGOT_EXT', 'LUG2')])
    if HUB_RIM_CHAMFER:
        # hub-top fix: a small chamfer on the six screw-hole rims at the RS02 output face (case A's layer peak sat on a rim)
        hc = []
        for a_ in (-142.0, -82.0, -22.0, 38.0, 98.0, 158.0):
            t_ = math.radians(a_)
            cx_, cz_ = RX + 12.0 * math.cos(t_), YZ + 12.0 * math.sin(t_)
            hc += edges_where(d, lambda p, cx_=cx_, cz_=cz_: abs(p[1] - RS02_OUT) < 0.05 and math.hypot(p[0] - cx_, p[2] - cz_) < 2.6,
                              pair=lambda p0, p1, cx_=cx_, cz_=cz_: all(abs(math.hypot(q[0] - cx_, q[2] - cz_) - 2.15) < 0.15 for q in (p0, p1)))
        d.ClearSelection2(True)
        for e_ in hc:
            e_.Select4(True, NUL)
        f_ = d.FeatureManager.InsertFeatureChamfer(4, 1, HUB_RIM_CHAMFER * 1e-3, math.radians(45.0), 0, 0, 0, 0)
        d.ForceRebuild3(False)
        log('  HOLE_RIM_CHAMFER', len(hc), 'edges', f_ is not None)
    return finish_part(d, 'hub', dict(Note='Interface frozen: spigot, lugs, seam bolts, hub screws from upper_arm_hub_left'))


BUILD = dict(drum=build_drum, ring=build_ring, cap=lambda: finish_part(build_cap(), 'cap'), fork_front=build_fork_front, fork_rear=build_fork_rear,
             fork_cap=build_fork_cap, cover=build_cover, hub=lambda: (build_hub(), hub_lug_roots())[-1], port_cap=build_port_cap, access_plugs=build_access_plugs)

if __name__ == '__main__':
    which = sys.argv[1:] or list(BUILD)
    res = {}
    try:
        for k in which:
            log('#### build', k)
            res[k] = BUILD[k]()
    finally:
        if not os.environ.get('SW_KEEP'):      # one instance per run: exit it (a long-lived instance grew to 24 GB)
            try:
                app().CloseAllDocuments(True)
            except Exception:
                pass
            finish()
    for k, v in res.items():
        log(f'{k:12s} {v:10.0f} mm3 {v * PETG:7.1f} g')
