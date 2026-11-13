"""Left arm concept A: printable parts from the two masters (organic_master.py). Arm frame, mm.

Upper arm: front and back halves split on the side plane Z 5.99, each printed cut face down; two M3 seam posts in the neck
(inserts in the front half, heads from the back). Today's hub is held by an M3 seam bolt through each of its two lugs. The RS02
is screwed (6 x M3 x 16 button heads) to a separate mounting ring on the bench; ring and RS02 drop into the back half (the
ring behind a rib, the rib's four keys in its slots, the housing face on the thickened end wall) and the front half closes
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
import os
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
if M.R1C:      # R1c trial parts and exports go to cad/_wip/r1c, so R1's files stay as released
    DIRS['upper'] = M.WIP
    EXP['upper'] = M.WIP / 'exports'
CL = 0.1
# R1f (2026-11-12, hub rev D3 extended lugs; WIP, off by default): the lug slot faces sit SLOT_CL off the lug's Z faces
# (0.5 per side for the picked flat shim plates, nominal 0.5). ARM_SLOT_CL; default the printed 0.1.
SLOT_CL = float(os.environ.get('ARM_SLOT_CL', str(CL)))
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


FIN_END = 276.0      # R1c fins end inside the seam post (r 7 at Y 272), clear of its bolt counterbore / insert (to Y 275.25)


def r1d_post_trim(d):
    """R1d: the hub-post tops (and anything else inside the bore radius) cut back to the floor at Y 295.7, 0.3 under the hub spigot
    and its fill, so the end face on the disc at Y 302 is the only axial contact besides the ridge."""
    if M.R1D:
        M.y_revolve(d, 'R1D_POST_TRIM', [(0.0, M.FLOOR_Y), (M.SEAT_R, M.FLOOR_Y), (M.SEAT_R, 296.3), (0.0, 296.3)], cut=True)


SLOT_BREAK_X = [(139.75, 149.0), (192.0, 201.25)]      # the lug-root fillets X spans (bc16e97: 140.25-148.5, 192.5-200.75, by section) + 0.5


def r1d_slot_break(d, sg, zl):
    """R1d, ARM_SLOT_BREAK="a,b" (2026-11-12, prepared, not released): break the lug slot's top edges, where each post's lug-facing
    face (Z = zl) meets the floor / post top (Y FLOOR_Y), so they clear the R1.2 fillet the shoulder thread adds at the hub lug
    roots (lug Z faces meeting the spigot underside at Y 296). A chamfer a down the face (Y) by b across the post top (Z), along
    each lug's X span only, inside the seat (no outside surface). The thin end is on the face, so the print sees a slope a over b
    (steeper than 45 deg when b > a) under the face's own support. Not near the ridge, ribs, end face or bore."""
    v = os.environ.get('ARM_SLOT_BREAK')
    if not (M.R1D and v):
        return
    a, b = (float(t) for t in v.split(','))
    top = M.FLOOR_Y
    for i, (x0, x1) in enumerate(SLOT_BREAK_X):
        xm = (x0 + x1) / 2
        name = f'SLOT_BREAK{i}{"F" if sg > 0 else "B"}'
        with Sk(d, plane(d, 'X', xm, name + '_P'), name) as s:
            s.poly([(xm, top - a, zl - sg * 0.3), (xm, top - a, zl), (xm, top, zl + sg * b), (xm, top + 0.3, zl + sg * b), (xm, top + 0.3, zl - sg * 0.3)])
        feat(d, s.feat, name, x1 - x0, True, mode=MID, lo=0.01)


# R1f lug pocket (hub rev D3: the lugs grown out to r 36.8 into seam-split pockets in our collar; coordinator / shoulder thread,
# 2026-11-12). Offsets are X from the yaw axis on each lug's side. Our pocket edge: the hub's outer edge + 0.2, the hub's edge
# capped so our wall to the skin keeps >= 1.2 (skin at Z 5.5: 36.3 at Y 288 ... 38.1 at Y 294 ... 38.5 at Y 298).
# D3 as built by the shoulder thread (coordinator 2026-11-13 01:35Z): lug Z faces Z 1.0 / 11.0; outer edge X offset 34.4 for
# Y 288-294.5, stepping to 36.35 for Y 294.5-297.6 (45 deg top chamfer 36.35 @ Y 296.7 to the land 35.45 @ 297.6); R1.2 Z roots
# along Y 296 out to X 35.45 (tangents Y 294.8, |Z| 6.2); R0.5 inside corner at (34.4, 294.5). Our pocket 0.2 outside:
# wall to the skin (at Z 5.5) 1.7 at Y 288, 1.55 at Y 294.3, 1.95 at Y 297.8.
R1F_POCKET = [(287.5, 34.6), (294.3, 34.6), (294.3, 36.55), (297.8, 36.55)]
R1F_LUG_SIDES = (-1, 1)      # the -X lug (theta 180) and the +X lug (theta 0)


def r1f_on():
    return M.R1D and os.environ.get('ARM_LUG_POCKET') == '1'


def r1f_lug_web(d, sg, zl):
    """R1f: a web from each hub post out to our wall, Y 288-295.7 (our floor), from the lug face (zl) to 12 off the seam, so the
    lug's Z face bears on one flat face r 18.5-35 instead of the cantilevered post. Outside the slot, clear of the bolt (r 20-26)
    and of the harness (it runs between the post pairs, X 151.75-189.25). Kept inside the skin: hypot(off, 12) < skin r."""
    if not r1f_on():
        return
    z1 = CZ + sg * 12.0
    zc, dz = (zl + z1) / 2, abs(z1 - zl)
    for k, side in enumerate(R1F_LUG_SIDES):
        name = f'R1F_WEB{k}{"F" if sg > 0 else "B"}'
        prof = [(27.0, 288.0), (34.0, 288.0), (35.6, 295.7), (27.0, 295.7)]
        with Sk(d, plane(d, 'Z', zc, name + '_P'), name) as s:
            s.poly([(HX + side * o, y, zc) for o, y in prof])
        feat(d, s.feat, name, dz, False, mode=MID, lo=0.01)


def r1f_lug_pocket(d, sg, zl):
    """R1f: (1) the seam pocket for the extended lug, |Z - CZ| < SLOT_CL + 5.0, out to R1F_POCKET, Y 287.5-297.8;
    (2) the root relief for the hub's R1.2 Z roots, which now run out to r 35.8 at Y 296 (tangent Y 294.8 / Z +-6.2): Y 294.3-296.4,
    from the face out to 1.3 past it with a 45 deg lower edge, offsets 18.3-36.3."""
    if not r1f_on():
        return
    zc, dz = CZ + sg * (abs(zl - CZ) - 0.5) / 2, abs(zl - CZ) + 0.5      # Z from -0.5 (into the cut-away half) to the face
    for k, side in enumerate(R1F_LUG_SIDES):
        tag = f'{k}{"F" if sg > 0 else "B"}'
        prof = [(18.3, 287.5)] + [(o, y) for y, o in R1F_POCKET] + [(18.3, 297.8)]
        with Sk(d, plane(d, 'Z', zc, f'R1F_POCKET{tag}_P'), f'R1F_POCKET{tag}') as s:
            s.poly([(HX + side * o, y, zc) for o, y in prof])
        feat(d, s.feat, f'R1F_POCKET{tag}', dz, True, mode=MID, lo=0.01)
        # (no relief needed for the hub's R0.5 inside corner at (34.4, 294.5): our wall's inner face there is at r 35.0-35.2,
        # 0.6+ outside it; a relief cut found nothing to remove, 2026-11-12)
        # root relief, extruded along X over offsets 18.3-36.3
        o0, o1 = 18.3, 36.3
        xm = HX + side * (o0 + o1) / 2
        zf = zl
        rel = [(294.3, zf - sg * 0.3), (294.3, zf), (295.6, zf + sg * 1.3), (296.4, zf + sg * 1.3), (296.4, zf - sg * 0.3)]
        with Sk(d, plane(d, 'X', xm, f'R1F_ROOTREL{tag}_P'), f'R1F_ROOTREL{tag}') as s:
            s.poly([(xm, y, z) for y, z in rel])
        feat(d, s.feat, f'R1F_ROOTREL{tag}', o1 - o0, True, mode=MID, lo=0.01)
        # (no 0.5 breaks at the bore edge: as planar cuts at offset 35.9 they left knife-thin slivers against the curved bore
        # (gate, 2026-11-12), and the D3 hub needs none: its column top is chamfered 45 deg and the strip's vertical edges are sharp)


def r1c_fins(d, sg, zl):
    # R1c fins: each hub post carries the hub joint's lift-off tie as Y-shear at its lug face (about 155 N per post at G90,
    # 43 MPa across the layers at a bare Dia 9 post root). A 9 mm fin from the post toward -Y (Y 276 to the post's centre),
    # from the lug-face level out to 0.4 into the skin, makes the root about 9 x 16: about 8 MPa. Cut by the bolt holes below.
    for i, q in enumerate(HUB_COLS):
        x = q[0]
        ys = list(np.round(np.arange(HUB_POST_Y, FIN_END - 0.01, -0.7), 2)) + [FIN_END]   # grown (2026-11-11): into the seam post; dense samples follow the skin
        top = []
        for y in ys:
            t_in, t_out = skin_hits((x, y), sg)
            top.append((y, CZ + sg * min(t_in + 0.4, t_out - 1.5)))      # 0.4 into the skin: clear of the bolt counterbore's exit chamfer (starts 2 inside the outer skin)
        pts = [(HUB_POST_Y, zl)] + top + [(FIN_END, zl)]      # full depth from the lug-face level to the skin
        with M.Sk(d, M.plane(d, 'X', x, f'R1C_FIN{i}_P'), f'R1C_FIN{i}') as s_:
            s_.poly([(x, y, z) for y, z in pts])
        M.feat(d, s_.feat, f'R1C_FIN{i}', 9.0, False, mode=M.MID, lo=0.01)


def upper_half(front):
    job = 'front' if front else 'back'
    d, p = open_copy(job)
    cut_half_space(d, 'Z', CZ, 1 if front else -1, 'OTHER_HALF')
    sg = 1 if front else -1
    for i, q in enumerate(UA_POSTS):
        post_z(d, f'SEAM_POST{i}', q, sg)
    zl = CZ + sg * (HUB_LUG_HZ + SLOT_CL)                                     # lug face in this half (R1f: ARM_SLOT_CL)
    for i, q in enumerate(HUB_COLS):                                          # posts from the lug face out to the skin; the lug
        post_z(d, f'HUB_POST{i}', (q[0], HUB_POST_Y), sg, z0=zl)              # sits between them, its bolt locating it
    if M.R1C:
        r1c_fins(d, sg, zl)
        r1d_post_trim(d)
        r1f_lug_web(d, sg, zl)
        r1d_slot_break(d, sg, zl)
        r1f_lug_pocket(d, sg, zl)
    if front:
        z_cyl(d, 'SEAM_INSERTS', UA_POSTS, 2.0, CZ - 0.01, CZ + 6.5, True)
        z_cyl(d, 'SEAM_PILOTS', UA_POSTS, 1.6, CZ + 6.4, CZ + 10.0, True)
        z_cyl(d, 'HUB_INSERTS', HUB_COLS, 2.0, zl - 0.01, zl + 6.5, True)
        z_cyl(d, 'HUB_PILOTS', HUB_COLS, 1.6, zl + 6.4, zl + 10.0, True)
    else:
        z_cyl(d, 'SEAM_HOLES', UA_POSTS, 1.7, CZ + 0.5, CZ - 60.0, True)
        z_cyl(d, 'SEAM_CBORES', UA_POSTS, 3.25, CZ - 12.0, CZ - 60.0, True)   # heads 12 below the seam: M3 x 18 into 5.7
        z_cyl(d, 'HUB_HOLES', HUB_COLS, 1.7, zl + 0.5, CZ - 60.0, True)
        z_cyl(d, 'HUB_CBORES', HUB_COLS, 3.0 if M.R1D else 3.25, zl - 7.0, CZ - 60.0, True)    # M3 x 25 through the lug into 5.7; R1d: Dia 6.0 (DIN 912 socket head Dia 5.5) so the post top at Y 295.7 keeps 0.7 over it
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
            arc_band(d, f'LIGHTEN{k}', 19.5, 31.0, 60.0 * k + 3.5, 60.0 * k + 56.5, 201.0, OUT['outer'] - 1.4, cut=True)
    else:
        cut_half_space(d, 'X', IN['inner'] + 0.5, -1, 'PAST_DISC')
        cut_half_space(d, 'X', IN['floor'], 1, 'UNDER_POCKET')
        region_x(d, 'ROOT_POCKET_SIDE', root_region(R_LAP), IN['floor'] - 1.0, IN['lap'])
        region_x(d, 'ROOT_SLOT_SIDE', root_region(R_FULL), IN['lap'], IN['inner'] + 1.0)
        x_holes(d, 'LAP_HOLES', [P(SCREW_R, a) for a in SCREW_PHI], 1.7, IN['floor'] - 1.0, IN['lap'] + 0.1)
        x_holes(d, 'LAP_CBORES', [P(SCREW_R, a) for a in SCREW_PHI], 3.1, IN['floor'] - 1.0, IN['floor'] + 1.2)   # button heads 0.45 proud of the pocket floor
    finish(d, p, job)


def ring():
    """RS02 mounting ring: bore for the RS02's Ø65 back, 6 x M3 on Ø73 (button heads in 2 mm counterbores on the rib side),
    four slots on the rib side for the halves' keys, a window for the RS02's plug and a notch for its unused socket. Prints
    flat on its RS02 face."""
    region, name = NAMES['ring']
    p = DIRS[region] / (name + '.SLDPRT')
    d = M.new_part(p)
    x0, x1 = M.BULKHEAD[0] + 0.1, M.BULKHEAD[1]
    r_in, r_out = 32.75, M.DRUM['r'] - M.SHELL_T - 0.2
    x_revolve(d, 'RING', [(x0, r_in), (x1, r_in), (x1, r_out), (x0, r_out)])
    # slots for the halves' four keys, each running out through the rim the way its key comes in (back half -Z, front +Z)
    for k, q in enumerate(M.RIB_KEYS):
        c, cf = M.KEY_CL, (M.KEY_CL_FREE if q[0] > -20 else M.KEY_CL)    # keys 0 and 3: their +Y faces never bear first
        out = (q[2] - 20.0, q[3] + c) if q[2] < 0 else (q[2] - c, q[3] + 20.0)
        M.rect_x(d, f'KEY_SLOT{k}', (q[0] - c, q[1] + cf, out[0], out[1]), x0 - 1.0, x1 + 1.0, cut=True)     # right through
        g = M.KEY_ROOT_R + 0.1      # mouth relief for the keys' root rounds, all round
        inner = (out[0], out[1] + g) if q[2] < 0 else (out[0] - g, out[1])
        M.rect_x(d, f'SLOT_MOUTH{k}', (q[0] - c - g, q[1] + cf + (g if cf == c else 0.0), *inner), x0 - 1.0, x0 + g, cut=True)   # the free faces' 1 mm clears the root round
    # trim the wedges where a slot wall meets the rim at a grazing angle (they would print as slivers)
    for k, q in enumerate(M.RIB_KEYS):
        sz = -1 if q[2] < 0 else 1
        if q[0] < -20:      # keys 1 and 2: the slot's outer wall runs out almost along the rim
            inner = q[3] if q[2] < 0 else q[2]
            box_ = (-45.0, q[0] + 0.2, *sorted((sz * (abs(inner) - M.KEY_ROOT_R - 0.1), sz * 60.0)))   # from the mouth relief's inner edge
        else:               # keys 0 and 3: the tip of the wedge beside the slot's outer wall, below the flank
            box_ = (q[1] + M.KEY_CL_FREE - 0.3, q[1] + M.KEY_CL_FREE + 3.0, *sorted((sz * 38.4, sz * 44.0)))
        M.rect_x(d, f'SLOT_TRIM{k}', box_, x0 - 1.0, x1 + 1.0, cut=True)
        if q[0] > -20:      # keys 0 and 3: clear the round where the key meets the drum wall, at the flank's outer end
            M.rect_x(d, f'SLOT_WALL_ROUND{k}', (q[0] - 2.5, q[0] + 0.1, *sorted((sz * 40.3, sz * 44.0))), x0 - 1.0, x1 + 1.0, cut=True)
    holes = [P(36.5, a) for a in M.RING_SCREWS]
    # 1.2 x 45 deg chamfer on the rib-side outer edge: clears the R1 fillet where the rib meets the drum wall
    x_revolve(d, 'RIB_CLEAR', [(x0 - 0.1, r_out - 2.3), (x0 + 2.3, r_out + 0.1), (x0 - 0.1, r_out + 0.1)], cut=True)   # 2.2 x 45 deg: clears the R2 rib corner round
    x_holes(d, 'RS02_SCREWS', holes, 1.7, x0 - 1, x1 + 1)
    x_holes(d, 'RS02_CBORES', holes, 3.1, x0 - 0.01, x0 + 2.0)
    # socket window (the plug goes in through it on the bench and its cable leaves up the neck) and the notch for the unused socket
    S = M.SOCKET
    arc_band(d, 'SOCKET_WINDOW', r_in - 1.0, r_out + 1.0, S['phi'] - S['half'], S['phi'] + S['half'], x0 - 1.0, x1 + 1.0, cut=True)
    # the screw heads that hold the socket tabs stand 2.4 proud of the flange (Ø5.6 on r 36.5 at phi 20, 180 and 340)
    # (the two beside the window as 3 mm deep steps running on from the window edges, so no sliver is left between them)
    x_holes(d, 'TAB_HEAD_BOTTOM', [P(36.5, 180.0)], 3.7, x1 - 3.0, x1 + 1.0)
    arc_band(d, 'TAB_HEAD_STEP_HI', r_in - 1.0, 40.4, S['phi'] + S['half'] - 0.5, 26.0, x1 - 3.0, x1 + 1.0, cut=True)
    arc_band(d, 'TAB_HEAD_STEP_LO', r_in - 1.0, 40.4, 334.0, 360.0 + S['phi'] - S['half'] + 0.5, x1 - 3.0, x1 + 1.0, cut=True)
    arc_band(d, 'SOCKET_NOTCH', r_in - 1.0, S['notch_r'], S['other'] - S['half'], S['other'] + S['half'], x0 - 1.0, x1 + 1.0, cut=True)
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
    p = sim / ('UA_ORGANIC_BONDED_v29.SLDPRT' if M.R2 else 'UA_ORGANIC_BONDED_v30.SLDPRT' if M.R1B else (os.environ.get('ARM_FEA_NAME', 'UA_ORGANIC_BONDED_v32.SLDPRT') if M.R1D else 'UA_ORGANIC_BONDED_v31.SLDPRT') if M.R1C else 'UA_ORGANIC_BONDED_v28.SLDPRT')     # v29: R2 trial, v30: R1b, v31: R1c
    shutil.copy(M.OUT['upper'], p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    r_wall = M.DRUM['r'] - M.SHELL_T
    x_revolve(d, 'RING_BONDED', [(M.RIB[1] - 0.05, 32.75), (M.BULKHEAD[1], 32.75), (M.BULKHEAD[1], r_wall + 0.05), (M.RIB[1] - 0.05, r_wall + 0.05)])
    S = M.SOCKET
    arc_band(d, 'RING_WINDOW', 31.0, r_wall - 0.2, S['phi'] - S['half'], S['phi'] + S['half'], M.RIB[1] + 0.05, M.BULKHEAD[1] + 0.5, cut=True)
    arc_band(d, 'RING_NOTCH', 31.0, S['notch_r'], S['other'] - S['half'], S['other'] + S['half'], M.RIB[1] + 0.05, M.BULKHEAD[1] + 0.5, cut=True)
    lo_, hi_ = M.STOP['lug_phi'] - M.STOP['lug_span'] / 2, M.STOP['lug_phi'] + M.STOP['lug_span'] / 2
    arc_band(d, 'PAD_LO', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, lo_ - 0.4, lo_ + 0.05, 135.7, 139.4, cut=False)
    arc_band(d, 'PAD_HI', M.STOP['r0'] + 0.6, M.STOP['r1'] - 0.6, hi_ - 0.05, hi_ + 0.4, 135.7, 139.4, cut=False)
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    if len(bodies(d)) != 1:
        raise SystemExit('expected one body')
    d.Save3(1, e, w)
    sw.CloseDoc(d.GetTitle)


OLD_KEYS = [(0.4, 12.0, -37.8, -33.6), (0.4, 12.0, 33.6, 37.8), (33.6, 39.0, -6.0, 6.0)]     # the ring before 2026-11-10


def fea_ring(old=False):
    """RS02 ring FEA model: the ring with 0.3 mm pads on its keys' bearing faces over X 150.9-155.5, where the rib notch
    bears (the notch mouth is relieved over the last 1.2 mm, so the rib never touches the key root). Each pad face is a fixture;
    the torque comes in through the screw holes. old: the ring before 2026-11-10 (9 screws, a top key, no window)."""
    sim = CAD / '_sim' / 'upper-arm'
    src = sim / 'RING_OLD.SLDPRT' if old else DIRS['upper'] / (NAMES['ring'][1] + '.SLDPRT')
    p = sim / ('RING_OLD_PADS.SLDPRT' if old else 'RING_PADS_v3.SLDPRT')
    shutil.copy(src, p)
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    keys, bears = (OLD_KEYS, ['y', 'y', 'z']) if old else (M.KEYS, M.BEARS)
    for k, (q, bear) in enumerate(zip(keys, bears)):
        if bear == 'y':
            for s_, v in ((0, q[0]), (1, q[1])):
                pad = (v - 0.3, v, q[2] + 0.3, q[3] - 0.3) if s_ == 0 else (v, v + 0.3, q[2] + 0.3, q[3] - 0.3)
                M.rect_x(d, f'PAD{k}{s_}', pad, 150.9, 155.5, cut=False)
        else:
            for s_, v in ((0, q[2]), (1, q[3])):
                pad = (q[0] + 0.3, q[1] - 0.3, v - 0.3, v) if s_ == 0 else (q[0] + 0.3, q[1] - 0.3, v, v + 0.3)
                M.rect_x(d, f'PAD{k}{s_}', pad, 150.9, 155.5, cut=False)
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
                caps=lambda: (cap('in'), cap('out')), ring=ring, pin=pin, fea_upper=fea_upper, fea_fore=fea_fore, fea_contact=fea_contact, fea_ring_old=lambda: fea_ring(True))
    for k in sys.argv[1:] or jobs:
        print('==', k, flush=True)
        jobs[k]()
