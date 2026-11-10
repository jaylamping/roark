"""Left arm concept A: printable parts from the two masters (organic_master.py). Arm frame, mm.

Upper arm: front and back halves split on the side plane Z 5.99, each printed cut face down; two M3 seam posts in the neck
(inserts in the front half, heads from the back). Today's hub is held by an M3 seam bolt through each of its two lugs. The RS02
is screwed (9 x M3 x 10 button heads) to a separate mounting ring on the bench; ring and RS02 drop into the back half (the
ring behind a rib, its two dogs in the rib notches, the housing face on the thickened end wall) and the front half closes
over them, so no screw has to be driven inside the closed drum.

Forearm: inboard and outboard shells split on X 170.49; the cheek discs come off on lap joint A so the RS02 mating face and
the 6808 seat print flat:
  outboard: disc = cheek inside r 30, plus the inner layer (X 199-205) of r 30-38.5 on phi 131-190; the shell keeps the
            outer layer. 4 x M3 from the outer face (under the cap ring) into M3 x 5.7 inserts in the disc.
  inboard:  the cap pocket takes the outer layer, so the lap runs the other way: the disc keeps the pocket-side layer
            (X 131.5-134.3) of r 30-38.5 on the sector, the shell keeps the slot-side layer (X 134.3-141, deep enough for the
            standard M3 x 5.7 insert). 4 x M3 x 8 button heads from inside the pocket (cap off) into the shell's inserts.
The outboard disc prints on its RS02 face (outer face down would put support in the visible M4 counterbores); three printed
Ø3.95 x 8.7 pins, printed lying down so the layers run along them, locate it on the RS02 output.
Caps press into their recesses (a lip with 0.05-0.15 mm interference) and lift out at a pry notch, so they come off with the arm assembled.

    python organic_parts.py [front back inboard outboard disc_in disc_out caps ring pin]
"""
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, box as sbox

import organic_master as M
from organic_master import CY, CZ, HX, CHEEKS, P, x_revolve, x_holes, arc_band, fillet_edges, edges_where, fine_stl, sw
from swg import *

CAD = M.CAD
EXP = {'upper': CAD / 'exports' / 'upper-arm', 'fore': CAD / 'exports' / 'forearm'}
NAMES = {'front': ('upper', 'upper_arm_organic_front_left'), 'back': ('upper', 'upper_arm_organic_back_left'),
         'inboard': ('fore', 'forearm_organic_shell_inboard_left'), 'outboard': ('fore', 'forearm_organic_shell_outboard_left'),
         'disc_in': ('fore', 'forearm_organic_cheek_inboard_left'), 'disc_out': ('fore', 'forearm_organic_cheek_outboard_left'),
         'ring': ('upper', 'upper_arm_organic_rs02_ring_left'), 'pin': ('fore', 'forearm_organic_output_pin'), 'cap_in': ('fore', 'forearm_organic_cap_inboard_left'), 'cap_out': ('fore', 'forearm_organic_cap_outboard_left')}
DIRS = {'upper': CAD / 'upper-arm', 'fore': CAD / 'forearm'}
CL = 0.1
SECTOR = (131.0, 190.0)
R_FULL, R_LAP = 30.0, 38.5
R_LAP_OUT = R_LAP                     # (45 put the disc edge on the saddle fillet: a feather edge, and no gain)
Y_SHELF = 171.5                       # above the saddle fillet, so the split plane doesn't feather it
SCREW_R, SCREW_PHI = 34.75, (138.0, 152.0, 170.0, 182.0)
IN = dict(outer=CHEEKS[0][0], inner=CHEEKS[0][1], lap=134.3, floor=M.CHEEKS[0][0] + M.CAP['recess'] + M.CAP['pocket'])  # floor 131.5
OUT = dict(outer=CHEEKS[1][1], inner=CHEEKS[1][0], lap=205.0)
UA_POSTS = [(151.0, 272.0), (190.0, 272.0)]
POST_R = 4.5
# today's hub: two lugs (Z CZ +-5) at the seam sides reach down from the spigot; a seam bolt through each ties both halves to it
HUB_COLS = [(147.5, 292.0), (193.5, 292.0)]
HUB_LUGS = [(141.0, 151.75), (189.25, 200.0)]
HUB_LUG_Y = (288.0, 300.0)
HUB_LUG_HZ = 5.0
FA_POSTS = [(150.5, CZ + 13.0), (150.5, CZ - 13.0)]   # (Y, Z): forearm seam posts above the RS00 (top Y 144.4), the harness passes between
FA_POST_R = 4.5
HUB_POST_Y = 291.4                    # post top 295.9, just under the spigot (Y 296)


def ray_to_shelf(phi):
    f = math.radians(phi)
    t = (Y_SHELF - CY) / math.cos(f)
    return Y_SHELF, CZ - t * math.sin(f)


def root_region(r, grow=0.0):
    """(Y, Z) region that stays with the shell in a layer whose disc reaches r: the lap sector outside r, and everything
    below the shelf line."""
    arc = [P(r, a) for a in np.linspace(SECTOR[0], SECTOR[1], int(SECTOR[1] - SECTOR[0]) * 2 + 1)]
    pts = arc + [ray_to_shelf(SECTOR[1]), (Y_SHELF, 170.0), (20.0, 170.0), (20.0, -170.0), (Y_SHELF, -170.0), ray_to_shelf(SECTOR[0])]
    g = Polygon(pts)
    return g.buffer(-grow, join_style=2) if grow else g


def disc_region(r):
    return sbox(40.0, -150.0, 330.0, 150.0).difference(root_region(r, CL))


def region_x(d, name, g, x0, x1, cut=True):
    xm = (x0 + x1) / 2
    with Sk(d, plane(d, 'X', xm, name + '_P'), name) as s:
        s.poly([(xm, y, z) for y, z in list(g.exterior.coords)[:-1]])
    return feat(d, s.feat, name, abs(x1 - x0), cut, mode=MID, lo=0.01)


def open_copy(job):
    src = M.OUT[NAMES[job][0]]
    p = DIRS[NAMES[job][0]] / (NAMES[job][1] + '.SLDPRT')
    shutil.copy(src, p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    if d is None:
        raise SystemExit('open ' + str(p))
    return d, p


def cut_half_space(d, axis, at, keep_sign, name, span=150.0):
    """Remove everything on the -keep_sign side of the plane axis = at."""
    c = at - keep_sign * span / 2
    pl = plane(d, axis, c, name + '_P')
    big = 400.0
    with Sk(d, pl, name) as s:
        if axis == 'Z':
            s.poly([(0, -big, c), (big, -big, c), (big, big, c), (0, big, c)])
        else:
            s.poly([(c, -big, -big), (c, big, -big), (c, big, big), (c, -big, big)])
    feat(d, s.feat, name, span, True, mode=MID)


def finish(d, p, job):
    d.ForceRebuild3(False)
    bs = bodies(d)
    print('  bodies', bs, flush=True)
    for b in bs:
        if b[1] < 0.2:
            delete_body(d, b[0])
    if len(bodies(d)) != 1:
        raise SystemExit(f'{job}: expected one body, got {bodies(d)}')
    e, w = L(), L()
    d.Save3(1, e, w)
    region, name = NAMES[job]
    EXP[region].mkdir(parents=True, exist_ok=True)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP[region] / (name + ext)), 0, 1, NUL, e, w)
    fine_stl(d, M.WIP / f'{name}.stl')
    sw.CloseDoc(d.GetTitle)


def z_cyl(d, name, pts, r, z0, z1, cut):
    zm = (z0 + z1) / 2
    with Sk(d, plane(d, 'Z', zm, name + '_P'), name) as s:
        for x, y in pts:
            if cut:
                s.circle((x, y, zm), r)
            else:
                s.poly([(x + r * math.cos(a), y + r * math.sin(a), zm) for a in np.linspace(0, 2 * math.pi, 33)[:-1]])
    return feat(d, s.feat, name, abs(z1 - z0), cut, mode=MID, lo=0.01)


_MESH = {}
AX = {'Z': (2, CZ, (0, 1)), 'X': (0, HX, (1, 2))}       # axis: (index, seam coordinate, indices of the two other coordinates)


def skin_hits(q, sign, axis='Z', master='upper'):
    """Inner and outer skin depth (along sign, from the seam plane) through the point q (the two other coordinates)."""
    if master not in _MESH:
        import trimesh
        _MESH[master] = trimesh.load(M.WIP / f'{master}_master.stl')
    i, c0, (j, k) = AX[axis]
    o = [0.0, 0.0, 0.0]
    o[i], o[j], o[k] = c0, q[0], q[1]
    dr = [0.0, 0.0, 0.0]
    dr[i] = sign
    loc, _, _ = _MESH[master].ray.intersects_location([o], [dr])
    t = sorted((loc[:, i] - c0) * sign)
    return t[0], t[1]


def pt3(axis, a, q):
    i, _, (j, k) = AX[axis]
    o = [0.0, 0.0, 0.0]
    o[i], o[j], o[k] = a, q[0], q[1]
    return tuple(o)


def post_z(d, name, q, sign, z0=None, inset=1.0, axis='Z', master='upper', r=None):
    """A post from z0 out to 'inset' mm inside the outer skin, its end following the skin (offset-from-surface end): the neck
    skin slopes more across a post than the skin is thick, so a flat end either gaps at the centre or breaks out at the rim."""
    r = r or POST_R
    c0 = AX[axis][1]
    z0 = c0 if z0 is None else z0
    t_in, t_out = skin_hits(q, sign, axis, master)
    zo = c0 + sign * t_out
    area = math.pi * r ** 2
    want = area * (t_in - abs(z0 - c0))           # the cavity part it fills (the skin overlap adds nothing)
    with Sk(d, plane(d, axis, z0, name + '_P'), name) as s:
        s.circle(pt3(axis, z0, q), r)
    fm = d.FeatureManager
    best = None
    for rev in (False, True):
        for orev in (False, True):
            v0 = vol(d)
            d.ClearSelection2(True)
            s.feat.Select2(False, 0)
            sd = d.SelectionManager.CreateSelectData
            sd.Mark = 1
            fp = pt3(axis, zo, q)
            d.Extension.SelectByID2('', 'FACE', fp[0] * m, fp[1] * m, fp[2] * m, True, 1, NUL, 0)
            f = fm.FeatureExtrusion3(True, False, rev, 5, 0, inset * m, inset * m, False, False, False, False, 0, 0, orev, False,
                                     False, False, True, False, True, 0, 0, False)
            if f is None:
                continue
            d.ForceRebuild3(False)
            dv = vol(d) - v0
            print(f'   {name} rev={rev} orev={orev}: dv {dv:.0f} (want ~{want:.0f})', flush=True)
            ia = AX[axis][0]
            vals = []
            for fc in (f.GetFaces or []):
                b = fc.GetBox
                vals += [b[ia] * 1e3, b[ia + 3] * 1e3]
            right_way = bool(vals) and (sum(vals) / len(vals) - z0) * sign > 0
            if abs(dv - want) < 0.1 * want and right_way:
                f.Name = name
                return f
            d.EditUndo2(1)
    raise SystemExit(name + ' failed')


def upper_half(front):
    job = 'front' if front else 'back'
    d, p = open_copy(job)
    cut_half_space(d, 'Z', CZ, 1 if front else -1, 'OTHER_HALF')
    sg = 1 if front else -1
    for i, q in enumerate(UA_POSTS):
        post_z(d, f'SEAM_POST{i}', q, sg)
    zl = CZ + sg * (HUB_LUG_HZ + CL)                                          # lug face in this half
    for i, q in enumerate(HUB_COLS):                                          # posts from the lug face out to the skin; the lug
        post_z(d, f'HUB_POST{i}', (q[0], HUB_POST_Y), sg, z0=zl)              # sits between them, its bolt locating it
    if front:
        z_cyl(d, 'SEAM_INSERTS', UA_POSTS, 2.0, CZ - 0.01, CZ + 6.5, True)
        z_cyl(d, 'SEAM_PILOTS', UA_POSTS, 1.6, CZ + 6.4, CZ + 10.0, True)
        z_cyl(d, 'HUB_INSERTS', HUB_COLS, 2.0, zl - 0.01, zl + 6.5, True)
        z_cyl(d, 'HUB_PILOTS', HUB_COLS, 1.6, zl + 6.4, zl + 10.0, True)
    else:
        z_cyl(d, 'SEAM_HOLES', UA_POSTS, 1.7, CZ + 0.5, CZ - 60.0, True)
        z_cyl(d, 'SEAM_CBORES', UA_POSTS, 3.25, CZ - 12.0, CZ - 60.0, True)   # heads 12 below the seam: M3 x 18 into 5.7
        z_cyl(d, 'HUB_HOLES', HUB_COLS, 1.7, zl + 0.5, CZ - 60.0, True)
        z_cyl(d, 'HUB_CBORES', HUB_COLS, 3.25, zl - 7.0, CZ - 60.0, True)    # M3 x 25 through the lug into 5.7
    finish(d, p, job)


def exit_chamfer(d, name, q, sign, axis, master, r0=3.25, w=2.5):
    """45 deg chamfer where a counterbore leaves the sloped skin: a cone from r0 2 mm inside the skin out to r0 + w + 2
    1 mm past it, so the hole edge is no knife edge."""
    t_out = skin_hits(q, sign, axis, master)[1]
    c0 = AX[axis][1]
    a0, a1 = c0 + sign * (t_out - 2.0), c0 + sign * (t_out + 1.0 + w)
    i, _, (j, k) = AX[axis]
    with Sk(d, plane(d, 'X' if axis == 'Z' else 'Z', q[0] if axis == 'Z' else q[1], name + '_P'), name) as s:
        prof = [(0.0, a0), (r0, a0), (r0 + 3.0 + w, a1), (0.0, a1)]
        if axis == 'Z':
            s.poly([(q[0], q[1] + rr, a) for rr, a in prof])
            centerline(s, (q[0], q[1], a0 - 5 * sign), (q[0], q[1], a1 + 5 * sign))
        else:
            s.poly([(a, q[0] + rr, q[1]) for rr, a in prof])
            centerline(s, (a0 - 5 * sign, q[0], q[1]), (a1 + 5 * sign, q[0], q[1]))
    revolve(d, s.feat, name, None, True)


def fore_shell(side):
    job = 'inboard' if side == 'in' else 'outboard'
    d, p = open_copy(job)
    cut_half_space(d, 'X', HX, -1 if side == 'in' else 1, 'OTHER_HALF')
    if side == 'out':
        # the disc: inside r 30 everywhere, and the inner layer of the lap band; the shell keeps the rest
        region_x(d, 'DISC_FULL', disc_region(R_FULL), OUT['inner'] - 3.0, OUT['outer'] + 1.0)
        region_x(d, 'DISC_LAP', disc_region(R_LAP_OUT), OUT['inner'] - 3.0, OUT['lap'])
        x_holes(d, 'LAP_HOLES', [P(SCREW_R, a) for a in SCREW_PHI], 1.7, OUT['lap'] - 0.1, OUT['outer'] + 1.0)
        x_holes(d, 'LAP_CBORES', [P(SCREW_R, a) for a in SCREW_PHI], 3.1, OUT['outer'] - 2.0, OUT['outer'] + 1.0)
    else:
        region_x(d, 'DISC_FULL', disc_region(R_FULL), IN['floor'] - 0.01, IN['inner'] + 3.0)
        region_x(d, 'DISC_LAP', disc_region(R_LAP), IN['floor'] - 0.01, IN['lap'])
        x_holes(d, 'LAP_INSERTS', [P(SCREW_R, a) for a in SCREW_PHI], 2.0, IN['lap'] - 0.1, IN['lap'] + 5.8)      # M3 x 5.7, 1 mm floor ring
        x_holes(d, 'LAP_TIPS', [P(SCREW_R, a) for a in SCREW_PHI], 1.6, IN['lap'] + 5.7, IN['inner'] + 0.1)
    sg = -1 if side == 'in' else 1
    for i, q in enumerate(FA_POSTS):
        post_z(d, f'FA_POST{i}', q, sg, axis='X', master='fore', r=FA_POST_R)
    if side == 'out':
        x_holes(d, 'FA_POST_INSERTS', FA_POSTS, 2.0, HX - 0.01, HX + 6.5)
        x_holes(d, 'FA_POST_PILOTS', FA_POSTS, 1.6, HX + 6.4, HX + 10.0)
    else:
        x_holes(d, 'FA_POST_HOLES', FA_POSTS, 1.7, HX - 60.0, HX + 0.5)
        x_holes(d, 'FA_POST_CBORES', FA_POSTS, 3.25, HX - 60.0, HX - 12.0)   # heads 12 from the seam: M3 x 18 into 5.7
    finish(d, p, job)


def disc(side):
    job = 'disc_in' if side == 'in' else 'disc_out'
    d, p = open_copy(job)
    if side == 'out':
        cut_half_space(d, 'X', OUT['inner'] - 5.5, 1, 'PAST_DISC')            # keeps X > 193.5 (output boss and locating bosses)
        region_x(d, 'ROOT_OUTER', root_region(R_FULL), OUT['lap'], OUT['outer'] + 1.0)
        region_x(d, 'ROOT_INNER', root_region(R_LAP_OUT), OUT['inner'] - 6.0, OUT['lap'])
        x_holes(d, 'LAP_INSERTS', [P(SCREW_R, a) for a in SCREW_PHI], 2.0, OUT['inner'] - 0.5, OUT['lap'] + 0.1)
        # lightening: six pockets under the cap ring (r 19.5-31, 8.6 deep from the recess floor), 3 mm spokes between them
        for k in range(6):
            arc_band(d, f'LIGHTEN{k}', 19.5, 31.0, 60.0 * k + 3.5, 60.0 * k + 56.5, 203.0, OUT['outer'] - 1.4, cut=True)
    else:
        cut_half_space(d, 'X', IN['inner'] + 0.5, -1, 'PAST_DISC')
        cut_half_space(d, 'X', IN['floor'], 1, 'UNDER_POCKET')
        region_x(d, 'ROOT_POCKET_SIDE', root_region(R_LAP), IN['floor'] - 1.0, IN['lap'])
        region_x(d, 'ROOT_SLOT_SIDE', root_region(R_FULL), IN['lap'], IN['inner'] + 1.0)
        x_holes(d, 'LAP_HOLES', [P(SCREW_R, a) for a in SCREW_PHI], 1.7, IN['floor'] - 1.0, IN['lap'] + 0.1)
        x_holes(d, 'LAP_CBORES', [P(SCREW_R, a) for a in SCREW_PHI], 3.1, IN['floor'] - 1.0, IN['floor'] + 1.2)   # button heads 0.45 proud of the pocket floor
    finish(d, p, job)


def ring():
    """RS02 mounting ring: bore for the RS02's Ø65 back, 9 x M3 on Ø73 (button heads in 2 mm counterbores on the rib side),
    two dogs on the rib side into the rib notches. Prints flat on its RS02 face."""
    region, name = NAMES['ring']
    p = DIRS[region] / (name + '.SLDPRT')
    d = M.new_part(p)
    x0, x1 = M.BULKHEAD[0] + 0.1, M.BULKHEAD[1]
    r_in, r_out = 32.75, M.DRUM['r'] - M.SHELL_T - 0.2
    x_revolve(d, 'RING', [(x0, r_in), (x1, r_in), (x1, r_out), (x0, r_out)])
    for k, q in enumerate(M.KEYS):
        M.rect_x(d, f'KEY{k}', q, M.RIB[0] + 0.2, x0 + 0.01, cut=False)
    # R1 root fillets where the keys leave the ring face (the keys bend across the print layers there)
    roots = edges_where(d, lambda p: abs(p[0] - x0) < 0.05 and any(q[0] - 0.05 <= p[1] - CY <= q[1] + 0.05 and q[2] - 0.05 <= p[2] - CZ <= q[3] + 0.05 for q in M.KEYS))
    print('  key root edges', len(roots), flush=True)
    fillet_edges(d, roots, (1.0, 0.8, 0.5), 'KEY_ROOTS')
    holes = [P(36.5, 20.0 + 40.0 * k) for k in range(9)]
    # 1.2 x 45 deg chamfer on the rib-side outer edge: clears the R1 fillet where the rib meets the drum wall
    x_revolve(d, 'RIB_CLEAR', [(x0 - 0.1, r_out - 1.3), (x0 + 1.3, r_out + 0.1), (x0 - 0.1, r_out + 0.1)], cut=True)   # clears the R1 rib fillet, not the keys
    x_holes(d, 'RS02_SCREWS', holes, 1.7, x0 - 1, x1 + 1)
    x_holes(d, 'RS02_CBORES', holes, 3.1, x0 - 0.01, x0 + 2.0)
    d.ForceRebuild3(False)
    e, w = L(), L()
    d.Save3(1, e, w)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP[region] / (name + ext)), 0, 1, NUL, e, w)
    fine_stl(d, M.WIP / f'{name}.stl')
    print('  bodies', bodies(d), flush=True)
    sw.CloseDoc(d.GetTitle)


def pin():
    """Locating pin, Ø3.95 x 8.7 with 0.4 chamfers and a 0.3 flat (prints lying on the flat)."""
    region, name = NAMES['pin']
    p = DIRS[region] / (name + '.SLDPRT')
    d = M.new_part(p)
    r, L_, c = 1.975, 8.7, 0.4
    x_revolve(d, 'PIN', [(150.0, 0.0), (150.0, r - c), (150.0 + c, r), (150.0 + L_ - c, r), (150.0 + L_, r - c), (150.0 + L_, 0.0)])
    with Sk(d, plane(d, 'X', 150.0 + L_ / 2, 'FLAT_P'), 'FLAT') as s:
        yc = CY - r + 0.3
        s.poly([(150.0 + L_ / 2, yc - 3, CZ - 3), (150.0 + L_ / 2, yc, CZ - 3), (150.0 + L_ / 2, yc, CZ + 3), (150.0 + L_ / 2, yc - 3, CZ + 3)])
    feat(d, s.feat, 'FLAT', L_ + 2, True, mode=MID, lo=0.01)
    d.ForceRebuild3(False)
    e, w = L(), L()
    d.Save3(1, e, w)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP[region] / (name + ext)), 0, 1, NUL, e, w)
    print('  bodies', bodies(d), flush=True)
    sw.CloseDoc(d.GetTitle)


def fea_upper():
    """Upper-arm FEA model for the drum, neck and stop: the master (halves as one body) with the RS02 ring merged into the rib
    and the drum wall, the load going in through the ring bore. The key torque path is checked by hand (the merged ring
    carries the torque by its bond, so the zone within 3 mm of the ring is excluded from the drum results). Contact pads on
    the lug end faces carry the stop load where the slot end bears (X 135.7-139.4)."""
    sim = CAD / '_sim' / 'upper-arm'
    sim.mkdir(parents=True, exist_ok=True)
    p = sim / 'UA_ORGANIC_BONDED_v11.SLDPRT'
    shutil.copy(M.OUT['upper'], p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    r_wall = M.DRUM['r'] - M.SHELL_T
    x_revolve(d, 'RING_BONDED', [(M.RIB[1] - 0.05, 32.75), (M.BULKHEAD[1], 32.75), (M.BULKHEAD[1], r_wall + 0.05), (M.RIB[1] - 0.05, r_wall + 0.05)])
    lo_, hi_ = M.STOP['lug_phi'] - M.STOP['lug_span'] / 2, M.STOP['lug_phi'] + M.STOP['lug_span'] / 2
    arc_band(d, 'PAD_LO', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, lo_ - 0.4, lo_ + 0.05, 135.7, 139.4, cut=False)
    arc_band(d, 'PAD_HI', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, hi_ - 0.05, hi_ + 0.4, 135.7, 139.4, cut=False)
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    if len(bodies(d)) != 1:
        raise SystemExit('expected one body')
    d.Save3(1, e, w)
    sw.CloseDoc(d.GetTitle)


def fea_contact():
    """Upper-arm FEA model with the RS02 ring as its own body in its printed clearances (0.2 radial, 0.1 axial, dogs in their
    notches), for no-penetration contact: the housing torque then has to go through the two dogs."""
    sim = CAD / '_sim' / 'upper-arm'
    p = sim / 'UA_ORGANIC_CONTACT_v7.SLDPRT'
    shutil.copy(M.OUT['upper'], p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    f = d.InsertPart3(str(DIRS['upper'] / (NAMES['ring'][1] + '.SLDPRT')), 1, '')
    d.ForceRebuild3(False)
    print('  insert', f is not None, 'bodies', bodies(d), flush=True)
    if len(bodies(d)) != 2:
        raise SystemExit('expected 2 bodies')
    d.Save3(1, e, w)
    sw.CloseDoc(d.GetTitle)


def fea_fore():
    """Bonded FEA model of the forearm: the master (shells and cheek discs as one body)."""
    sim = CAD / '_sim' / 'upper-arm'
    p = sim / 'FA_ORGANIC_BONDED_v10.SLDPRT'
    shutil.copy(M.OUT['fore'], p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    lo_ = M.STOP['lug_phi'] - M.STOP['travel'] - M.STOP['lug_span'] / 2
    hi_ = M.STOP['lug_phi'] + M.STOP['lug_span'] / 2
    # contact pads on the slot ends, where the lug bears (X 136.7-140.0), for the fixtures of the stop cases
    arc_band(d, 'PAD_LO', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, lo_ - 0.05, lo_ + 0.4, 135.7, 139.4, cut=False)
    arc_band(d, 'PAD_HI', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, hi_ - 0.4, hi_ + 0.05, 135.7, 139.4, cut=False)
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    d.Save3(1, e, w)
    sw.CloseDoc(d.GetTitle)


def cap(side):
    """Caps: revolved discs with a snap lip; the outboard one is a ring that shows the RS02 output bolt circle."""
    job = 'cap_in' if side == 'in' else 'cap_out'
    region, name = NAMES[job]
    p = DIRS[region] / (name + '.SLDPRT')
    d = M.new_part(p)
    rec = M.CAP['recess']
    if side == 'in':
        x_face, sg, r_out, r_in = IN['outer'], -1, M.CAP['r'], 0.0
        lip_r0, lip_r1 = M.CAP['r'] - 2.4, M.CAP['r'] - 1.0 + 0.15   # press-fit lip in the pocket wall, 0.15 interference
    else:
        x_face, sg, r_out, r_in = OUT['outer'], 1, 35.0, 17.0
        lip_r0, lip_r1 = 32.5, 33.65                         # press-fit lip in the groove (r 32.4-33.6), 0.05 interference
    x_top = x_face + sg * 1.4                                # 1.4 proud of the cheek face
    x_seat = x_face - sg * rec                               # bottom of the recess
    lip = x_seat - sg * 1.8
    prof = [(x_top, r_in), (x_top, r_out - 1.2), (x_top - sg * 1.2, r_out), (x_seat, r_out), (x_seat, lip_r1),
            (lip, lip_r1), (lip, lip_r0), (x_seat, lip_r0), (x_seat, r_in)]
    x_revolve(d, 'CAP', prof)
    # hollow underside: 1.3 mm off the inside of the disc (prints top face down, so the recess opens upward)
    if side == 'in':
        x_revolve(d, 'UNDERSIDE', [(x_seat - sg * 0.5, 0.0), (x_seat - sg * 0.5, r_out - 3.5), (x_top - sg * 1.6, r_out - 3.5), (x_top - sg * 1.6, 0.0)], cut=True)
    else:
        x_revolve(d, 'UNDERSIDE', [(x_seat - sg * 0.5, r_in + 2.0), (x_seat - sg * 0.5, 31.0), (x_top - sg * 1.6, 31.0), (x_top - sg * 1.6, r_in + 2.0)], cut=True)
    # pry notch at the back (phi 90): a 6 x 1.2 slot in the rim
    with Sk(d, plane(d, 'X', x_top - sg * 0.6, 'PRY_P'), 'PRY') as s:
        yc, zc = P(r_out - 0.5, 90.0)
        s.poly([(x_top - sg * 0.6, yc - 3, zc - 1.5), (x_top - sg * 0.6, yc + 3, zc - 1.5), (x_top - sg * 0.6, yc + 3, zc + 1.5), (x_top - sg * 0.6, yc - 3, zc + 1.5)])
    feat(d, s.feat, 'PRY', 1.2, True, mode=MID, lo=0.01)
    d.ForceRebuild3(False)
    e, w = L(), L()
    d.Save3(1, e, w)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP[region] / (name + ext)), 0, 1, NUL, e, w)
    fine_stl(d, M.WIP / f'{name}.stl')
    print('  bodies', bodies(d), flush=True)
    sw.CloseDoc(d.GetTitle)


if __name__ == '__main__':
    jobs = dict(front=lambda: upper_half(True), back=lambda: upper_half(False), inboard=lambda: fore_shell('in'),
                outboard=lambda: fore_shell('out'), disc_in=lambda: disc('in'), disc_out=lambda: disc('out'),
                caps=lambda: (cap('in'), cap('out')), ring=ring, pin=pin, fea_upper=fea_upper, fea_fore=fea_fore, fea_contact=fea_contact)
    for k in sys.argv[1:] or jobs:
        print('==', k, flush=True)
        jobs[k]()
