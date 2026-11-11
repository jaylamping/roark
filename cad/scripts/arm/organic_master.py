"""Left arm, concept A "drum and caps": upper-arm and forearm masters. Arm frame, mm (elbow axis along X at Y 209.86,
Z 5.99; forearm axis along Y at X 170.49). The skins are single lofts through a few superellipse sections resampled to even
arc length; drum, cheeks and caps are true revolves about the elbow axis; the skin meets the drum and cheeks in fillets;
then a 3 mm shell. Splits and details come after, in the part scripts.

    python organic_master.py [upper] [fore]
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point as SPoint, box as sbox

from swg import *

sw = sw_app()
sw.CloseAllDocuments(True)
CAD = Path(__file__).resolve().parents[2]
CY, CZ, HX = 209.860668, 5.985875, 170.49
HUB_Y = 319.86
N = 40
SHELL_T = 3.0
FORE_T = 2.1              # forearm belly skin: belly FEA bulk SF 7.8 at 2.4 mm; 2.1 saves about 8 g more
OUT = {'upper': CAD / 'upper-arm' / 'upper_arm_organic_master_left.SLDPRT',
       'fore': CAD / 'forearm' / 'forearm_organic_master_left.SLDPRT'}
WIP = CAD / '_wip' / 'organic-arm' / 'cad'

# (y, x+ half-width, x- half-width, z front, z back, superellipse n); concept A after the flex sweep
HUB_JOINT = 302.0                      # today's hub disc (Y 302-319.86) stays: the skin starts under it
UPPER = [(HUB_JOINT, 39.0, 39.0, 39.0, 39.0, 2.0), (294, 38.3, 38.3, 37.5, 39, 2.2), (284, 35, 35, 29, 38, 2.5),
         (266, 29, 29, 17.5, 34, 2.4), (250, 26, 26, 13.5, 30, 2.3), (232, 26, 26, 13.5, 28, 2.2)]
FORE = [(98.3, 36.0, 36.0, 36.0, 36.0, 2.0), (108, 35.5, 35.5, 35.0, 36.0, 2.0), (128, 38.5, 38.5, 33, 36.5, 2.2),
        (148, 42.0, 43.0, 31.5, 38.5, 3.2), (165, 42.51, 43.49, 27, 39, 10.0)]
# from Y 165 the sides sit on the cheek outer faces (X 127.0 / 213.0); the cheeks are plates whose side outline is the r 42
# circle with tangent lines down to the belly's front and back at Y 165, so each side runs up into its cheek
DRUM = dict(x0=141.5, x1=198.5, r=44.5, edge=7.0)
CHEEKS = [(127.0, 141.0), (199.0, 213.0)]
CHEEK_R, CHEEK_EDGE, CLEAR_R = 42.0, 5.0, 48.0


def section(y, xp, xm, zp, zm, n):
    dense = []
    for i in range(1440):
        a = 2 * math.pi * i / 1440
        c, s = math.cos(a), math.sin(a)
        dense.append((HX + math.copysign(abs(c) ** (2 / n), c) * (xp if c >= 0 else xm), CZ + math.copysign(abs(s) ** (2 / n), s) * (zp if s >= 0 else zm)))
    q = np.array(dense + dense[:1])
    sl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])
    t = np.linspace(0, sl[-1], N + 1)[:-1]
    return [(float(np.interp(v, sl, q[:, 0])), y, float(np.interp(v, sl, q[:, 1]))) for v in t]


def spline_section(d, pts, name):
    y = pts[0][1]
    pl = plane(d, 'Y', y, name + '_P')
    with Sk(d, pl, name) as s:
        arr = []
        for q in pts + pts[:1]:
            u, v = s.p(q)
            arr += [u, v, 0.0]
        if d.SketchManager.CreateSpline2(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, arr), True) is None:
            raise SystemExit('spline failed ' + name)
    return s.feat


def loft(d, sketches, name, start=0, end=0):
    v0 = vol(d)
    fm = d.FeatureManager
    for st, en, merge in ((start, end, True), (start, end, False), (0, 0, True), (0, 0, False)):
        d.ClearSelection2(True)
        for k in sketches:
            k.Select2(True, 1)
        f = fm.InsertProtrusionBlend2(False, True, False, 1.0, st, en, 1.0, 1.0, True, True, False, 0, 0, 0, True, merge, merge, 0)
        print(f'   loft try start {st} end {en} merge {merge}:', f is not None, flush=True)
        if f is not None:
            f.Name = name
            d.ForceRebuild3(False)
            print(f'  {name}: added {vol(d) - v0:.0f} mm3', flush=True)
            return f
    raise SystemExit(name + ' loft failed')


def x_revolve(d, name, prof, cut=False):
    """Revolve a (X, r) profile about the elbow axis."""
    pl = plane(d, 'Z', CZ, name + '_P')
    with Sk(d, pl, name) as s:
        s.poly([(x, CY + r, CZ) for x, r in prof])
        centerline(s, (90, CY, CZ), (260, CY, CZ))
    return revolve(d, s.feat, name, None, cut)


def edges_where(d, test):
    out = []
    for b in d.GetBodies2(0, True):
        es = b.GetEdges
        for e in ((es() if callable(es) else es) or []):
            cp = e.GetCurveParams3
            p0 = np.array(cp.StartPoint[:3]) * 1000.0
            p1 = np.array(cp.EndPoint[:3]) * 1000.0
            if test(p0) and test(p1):
                out.append(e)
    return out


def fillet_edges(d, edges, radii, name):
    for r in radii:
        d.ClearSelection2(True)
        for e in edges:
            e.Select4(True, NUL)
        f = d.FeatureManager.FeatureFillet3(3, r * m, 0, 0, 0, 0, 0, NUL, NUL, NUL, NUL, NUL, NUL, NUL)
        if f is not None:
            f.Name = name
            print(f'  {name}: R{r} on {len(edges)} edges', flush=True)
            return r
    print(f'  {name}: no fillet built on {len(edges)} edges', flush=True)
    return None


def shell(d, face_pts, t, name):
    d.ClearSelection2(True)
    ok = [d.Extension.SelectByID2('', 'FACE', p[0] * m, p[1] * m, p[2] * m, True, 0, NUL, 0) for p in face_pts]
    v0 = vol(d)
    d.InsertFeatureShell(t * m, False)
    d.ForceRebuild3(False)
    f = d.FeatureByPositionReverse(0)
    if f is None or f.GetTypeName2 != 'Shell' or v0 - vol(d) < 1000:
        raise SystemExit(f'{name} failed (faces selected {ok}, last feature {f.GetTypeName2 if f else None})')
    f.Name = name
    d.ForceRebuild3(False)
    print(f'  {name}: {t} mm, vol {vol(d):.0f} mm3', flush=True)


def new_part(path):
    sw.CloseAllDocuments(True)       # a failed build leaves its part open, and the next NewDocument then throws
    tpl = sw.GetUserPreferenceStringValue(8)
    d = sw.NewDocument(tpl, 0, 0, 0)
    e, w = L(), L()
    d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    return d


def fine_stl(d, path):
    old = sw.GetUserPreferenceIntegerValue(78)
    sw.SetUserPreferenceIntegerValue(78, 2)
    try:
        e, w = L(), L()
        d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    finally:
        sw.SetUserPreferenceIntegerValue(78, old)


def save(d, job):
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    e, w = L(), L()
    d.Save3(1, e, w)
    WIP.mkdir(parents=True, exist_ok=True)
    fine_stl(d, WIP / f'{job}_master.stl')
    sw.CloseDoc(d.GetTitle)


# ---- elbow internals. Positions are from the vendor model (marengo cad/_wip/left-arm-layout-import/envelope/stl/ELBOW_RS02.STL,
# checked by cad/_wip/organic-arm/cad/rs02_fit.py): body Ø78.5 x 28 with the 9 x M3 x 8 flange face 28 behind the front;
# back Ø65, 13.4 long behind the flange; output Ø43, 3.5 proud; 6 x M4 x 7 and 3 x Ø4 pins on Ø24. Two radial sockets
# (power + CAN, in parallel) stand on the back, 180 deg apart, 26 deg wide, out to r 36.2, from the flange to 8.2 behind it.
# Each covers one or two of the flange holes (vendor holes at 6.5 + 40k: 86.5 under one tab, 246.5 and 286.5 beside the other),
# so 6 of the 9 can take screws. (Until 2026-11-10 the flange sat 30.9 behind the front here, a misreading of the drawing.)
RS02_X = dict(back=152.3, shoulder=165.7, front=193.7, output=197.2)
STOP_PLAY = 0.4          # RS02 front face to the end-wall stop, nominal (R1, 2026-11-11: 0.2 could bind at +-0.1 per face; 0.4 gives 0.5 total axial freedom)
BULKHEAD = (153.8, 165.7)              # RS02 mounting ring (a separate part, organic_parts.py): screwed to the RS02 on the bench,
RIB = (147.4, 153.8)                   # then dropped into the halves behind this rib (ring 11.8 thick since 2026-11-11), keyed by the rib's keys
RIB_R0 = 33.5
# RS02 clocking on the ring: the used socket faces the neck (phi 1.5), the only place a plug and its cable have room; the plug
# goes in on the bench through a window in the ring. The other socket (phi 181.5) is not used (one trunk drop per motor, no
# pass-through via a drive's second port: marengo hardware/electrical/pdb/PLAN.md) and sits in a clearance notch in the bore.
SOCKET = dict(phi=1.5, other=181.5, half=16.0, notch_r=36.9)
RING_SCREWS = [60.0, 100.0, 140.0, 220.0, 260.0, 300.0]     # the 6 usable flange holes; 20, 180 and 340 are under the tabs
# Torque path ring -> halves (2026-11-11): four straight keys on the halves' rib, two per half, running from the rib face (+X)
# through open slots in the ring to 0.3 mm short of the RS02 flange, so the key load reaches the flange with no lever through the
# ring's thickness. Each key's bearing faces are Y-normal and it merges into the drum wall on its outer side.
# Both parts carry the key load in their layer plane: the halves print seam face down (layers normal to Z), so the key's
# bending (sigma x) and shear (tau xy) lie in the layers; the ring prints flat (layers normal to X) and its slot flanks take the
# key in bearing (sigma y) and in-plane shear. Any one key carries the full 34 N.m (organic_fea.py RINGK / HALFK cases).
# The ring drops into the back half along -Z and the front half closes along -Z, so every slot in the ring runs out through the
# ring's rim in the direction its key comes from. (dy0, dy1, dz0, dz1) from the elbow axis; phi 80 and 120 in the back half,
# 240 and 280 in the front half, between the ring screws. Keys 0 and 3 (phi 80, 280) are the main ones: each bears on either
# face, so each alone carries 34 N.m in either direction. Keys 1 and 2 are smaller (the RS02 back and the skin squeeze them)
# and only share load.
RIB_KEYS = [(0.6, 13.6, -41.8, -34.6), (-24.2, -12.4, -42.5, -32.3), (-24.2, -12.4, 32.3, 42.5), (0.6, 13.6, 34.6, 41.8)]   # clipped to r 42.1, so every key runs into the drum wall; inner sides 0.85+ mm off the ring bore after the slot relief
KEY_TIP = BULKHEAD[1] - 0.3   # the keys run the ring's full thickness, 0.3 short of the RS02 flange; the ring slots go right through
KEY_CL = 0.1             # slot clearance on the bearing faces; the crush ribs close it
CRUSH = 0.25             # crush-rib height on the bearing faces
KEY_CL_FREE = 1.0        # on the faces that must never bear first (keys 0 and 3, their +Y faces)
KEY_ROOT_R = 0.8         # root round; the ring slot mouths are relieved 0.9 mm for it
STUB = dict(x0=134.0, r_out=20.0, r_in=16.0)        # hollow inboard stub; 6808 (Ø40 / Ø52 x 7) on X 134-141
STOP = dict(r0=29.5, r1=36.5, lug_phi=90.0, lug_span=60.0, travel=124.0, depth=6.0)   # the printed lug (commit b3f3984), kept for STOP_KIND 'lug'
STOP_KIND = os.environ.get('STOP_KIND', 'lug')        # Joey 2026-11-10: printed lug, rated to the RS02's 17 N.m
# Stop as a steel dowel (Ø8 x 15 hardened, h6): the printed lug's root fails the 889 N back-driven stop (FEA SF 0.88). The
# pin sits at r 35 on the drum's inboard end, 9 mm in a printed socket (boss inside the drum, stopping short of the RS02
# back), 5 mm proud into a slot in the inboard cheek whose ends are R4.1, conformal with it. Ø3 knock-out hole behind it.
PIN = dict(r=35.0, phi=90.0, d=8.0, proud=5.0, embed=9.0, hole=8.15, boss=8.0)   # 5 mm rim outside the slot
CAP = dict(r=38.3, recess=1.5, pocket=3.0)       # inboard cap Ø76.6 over a 3 mm pocket: the flat bundle coils at r 22-35 in one layer (seat inside the R6 rim round)
OUT_HOLES = [(12.0, 30.0 + 60.0 * k) for k in range(6)]          # 6 x M4 on Ø24
OUT_PINS = [(12.0, 120.0 * k) for k in range(3)]                  # 3 printed Ø3.95 x 8.7 pins (organic_parts.py) in Ø4.05 holes, into the RS02 output's Ø4 pin holes on Ø24


def P(r, phi):
    f = math.radians(phi)
    return CY + r * math.cos(f), CZ - r * math.sin(f)


def y_revolve(d, name, prof, cut=False):
    """Revolve an (r, Y) profile about the upper-arm (yaw) axis, X 170.49, Z 5.99."""
    pl = plane(d, 'Z', CZ, name + '_P')
    with Sk(d, pl, name) as s:
        s.poly([(HX + r, y, CZ) for r, y in prof])
        centerline(s, (HX, 150, CZ), (HX, 340, CZ))
    return revolve(d, s.feat, name, None, cut)


def x_holes(d, name, pts, r, x0, x1, cut=True):
    xm = (x0 + x1) / 2
    with Sk(d, plane(d, 'X', xm, name + '_P'), name) as s:
        for y, z in pts:
            s.circle((xm, y, z), r)
    return feat(d, s.feat, name, abs(x1 - x0), cut, mode=MID, lo=0.01)


def rect_x(d, name, q, x0, x1, cut):
    """A block (dy0, dy1, dz0, dz1 from the elbow axis) between X x0 and x1."""
    xm = (x0 + x1) / 2
    dy0, dy1, dz0, dz1 = q
    with Sk(d, plane(d, 'X', xm, name + '_P'), name) as s:
        s.poly([(xm, CY + dy0, CZ + dz0), (xm, CY + dy1, CZ + dz0), (xm, CY + dy1, CZ + dz1), (xm, CY + dy0, CZ + dz1)])
    return feat(d, s.feat, name, abs(x1 - x0), cut, mode=MID, lo=0.01)


def arc_band(d, name, r0, r1, phi0, phi1, x0, x1, cut, n=60):
    xm = (x0 + x1) / 2
    pts = [P(r1, a) for a in np.linspace(phi0, phi1, n)] + [P(r0, a) for a in np.linspace(phi1, phi0, n)]
    with Sk(d, plane(d, 'X', xm, name + '_P'), name) as s:
        s.poly([(xm, y, z) for y, z in pts])
    return feat(d, s.feat, name, abs(x1 - x0), cut, mode=MID, lo=0.01)


def upper_details(d):
    # hub seat: today's hub spigot (r 35.8, Y 296-302) sits in a bore; it is held by the two seam bolts through its lugs
    # (organic_parts.py), as in today's upper arm
    y_revolve(d, 'HUB_SEAT', [(0.0, 296.0), (35.9, 296.0), (35.9, HUB_JOINT + 1), (0.0, HUB_JOINT + 1)], cut=True)
    # drum ends: the output passes the outboard end wall; the inboard end carries the hollow stub for the 6808
    x_revolve(d, 'OUTPUT_BORE', [(RS02_X['front'], 0), (DRUM['x1'] + 1, 0), (DRUM['x1'] + 1, 22.5), (RS02_X['front'], 22.5)], cut=True)
    x_revolve(d, 'STUB', [(STUB['x0'], STUB['r_in']), (DRUM['x0'] + 1.5, STUB['r_in']), (DRUM['x0'] + 1.5, STUB['r_out']), (STUB['x0'], STUB['r_out'])])
    x_revolve(d, 'STUB_BORE', [(STUB['x0'] - 1, 0), (DRUM['x0'] + 4, 0), (DRUM['x0'] + 4, STUB['r_in']), (STUB['x0'] - 1, STUB['r_in'])], cut=True)
    # RS02 seat: bulkhead ring at the shoulder, bore for the Ø65 back, 9 x M3 on Ø73
    x_revolve(d, 'RS02_RIB', [(RIB[0], RIB_R0), (RIB[1], RIB_R0), (RIB[1], DRUM['r'] - SHELL_T + 0.3), (RIB[0], DRUM['r'] - SHELL_T + 0.3)])   # just into the wall: under the neck opening it ends as a free edge, no lip
    # the harness passes the rib at the top, from the neck to the stub: the rib is open there (phi -15 to 15)
    arc_band(d, 'RIB_HARNESS_GAP', RIB_R0 - 0.5, DRUM['r'] - SHELL_T + 0.6, -15.0, 15.0, RIB[0] - 0.1, RIB[1] + 0.1, cut=True)
    # outboard end wall thickened to X 193.9: the RS02 housing face (r 22.5-39) stops on it, 0.2 mm axial play to the ring
    x_revolve(d, 'RS02_STOP', [(RS02_X['front'] + STOP_PLAY, 22.5), (DRUM['x1'] - 2.0, 22.5), (DRUM['x1'] - 2.0, DRUM['r'] - 1.0), (RS02_X['front'] + STOP_PLAY, DRUM['r'] - 1.0)])
    # hard stop: a lug on the drum's inboard end, running in a slot in the inboard cheek
    if STOP_KIND == 'lug':
        arc_band(d, 'STOP_LUG', STOP['r0'], STOP['r1'], STOP['lug_phi'] - STOP['lug_span'] / 2, STOP['lug_phi'] + STOP['lug_span'] / 2,
                 DRUM['x0'] - STOP['depth'], DRUM['x0'] + 1.5, cut=False)
        # backing behind the lug: the 3 mm end wall alone bends under the 889 N stop load (FEA SF 0.55); 4.6 mm more wall over
        # the lug's sector, inside the bay (the harness enters the stub from the top, away from it)
        arc_band(d, 'LUG_BACKING', STUB['r_out'], DRUM['r'] - SHELL_T + 0.05, STOP['lug_phi'] - 40.0, STOP['lug_phi'] + 40.0,
                 DRUM['x0'] + SHELL_T - 0.1, DRUM['x0'] + SHELL_T + 4.6, cut=False)
        # R1 root fillets on the lug (a sharp root is a stress singularity under the 889 N stop load); the slot mouth is relieved for them
        def at_lug_root(p):
            r = math.hypot(p[1] - CY, p[2] - CZ)
            ph = math.degrees(math.atan2(-(p[2] - CZ), p[1] - CY)) % 360
            return abs(p[0] - DRUM['x0']) < 0.05 and STOP['r0'] - 0.1 < r < STOP['r1'] + 0.1 and STOP['lug_phi'] - STOP['lug_span'] / 2 - 0.5 < ph < STOP['lug_phi'] + STOP['lug_span'] / 2 + 0.5
        root = edges_where(d, at_lug_root)
        print('  lug root edges', len(root), flush=True)
        fillet_edges(d, root, (2.0, 1.5, 1.0), 'LUG_ROOT')
    else:
        # backing behind the pin over the same sector, and a boss round the socket inside the drum (ends 0.3 short of the RS02 back)
        arc_band(d, 'LUG_BACKING', STUB['r_out'], DRUM['r'] - SHELL_T + 0.05, STOP['lug_phi'] - 40.0, STOP['lug_phi'] + 40.0,
                 DRUM['x0'] + SHELL_T - 0.1, DRUM['x0'] + SHELL_T + 4.6, cut=False)
        px, pz = P(PIN['r'], PIN['phi'])
        x_holes(d, 'PIN_BOSS', [(px, pz)], PIN['boss'], DRUM['x0'] + SHELL_T - 0.1, DRUM['x0'] + PIN['embed'] + 1.0, cut=False)
        x_holes(d, 'PIN_SOCKET', [(px, pz)], PIN['hole'] / 2, DRUM['x0'] - 1.0, DRUM['x0'] + PIN['embed'])
        x_holes(d, 'PIN_KNOCKOUT', [(px, pz)], 1.5, DRUM['x0'] + PIN['embed'] - 0.5, DRUM['x0'] + PIN['embed'] + 2.0)
    # the rib meets the drum wall in a concave corner on both faces: R1.5
    rib_c = edges_where(d, lambda p: abs(math.hypot(p[1] - CY, p[2] - CZ) - (DRUM['r'] - SHELL_T)) < 0.1 and abs(p[0] - RIB[1]) < 0.05)   # ring side only: on the back face it left slivers at the neck opening
    print('  rib corner edges', len(rib_c), flush=True)
    fillet_edges(d, rib_c, (2.0, 1.5, 1.0), 'RIB_CORNER')   # R2 (2026-11-11: the elbow torque peaks here at the neck-opening edges); the ring's 2.2 chamfer clears it
    for k, q in enumerate(RIB_KEYS):                  # after the corner round: their outer sides merge into the wall
        # each key is its rectangle clipped to r 42.1 (0.6 into the 3 mm wall): its outer side follows the wall, inside the skin
        r_c = DRUM['r'] - SHELL_T + 0.6
        lo, hi = sorted((q[2], q[3]))
        box_ = sbox(q[0], lo, q[1], hi).intersection(SPoint(0, 0).buffer(r_c, 256))
        xm = (RIB[1] - 0.5 + KEY_TIP) / 2
        with Sk(d, plane(d, 'X', xm, f'RIB_KEY{k}_P'), f'RIB_KEY{k}') as s_:
            s_.poly([(xm, CY + a_, CZ + b_) for a_, b_ in list(box_.exterior.coords)[:-1]])
        feat(d, s_.feat, f'RIB_KEY{k}', KEY_TIP - RIB[1] + 0.5, False, mode=MID, lo=0.01)
    # past each key's tip, a wall thickening that tapers out over 4.5 mm in three steps (r 39.8 / 40.6 / 41.4 to the wall),
    # outside the RS02 body (r 39.25): the key's joint to the wall no longer ends abruptly at its tip
    for k, q in enumerate(RIB_KEYS):
        a0, a1 = sorted(math.degrees(math.acos(v / 41.0)) for v in (q[0], q[1]))
        if q[2] > 0:
            a0, a1 = 360.0 - a1, 360.0 - a0
        for j, (r0, x0_, x1_) in enumerate(((39.8, KEY_TIP - 0.5, KEY_TIP + 1.5), (40.6, KEY_TIP + 1.5, KEY_TIP + 3.0), (41.4, KEY_TIP + 3.0, KEY_TIP + 4.5))):
            arc_band(d, f'KEY_TAPER{k}{j}', r0, DRUM['r'] - SHELL_T + 0.8, a0 + 1.0, a1 - 1.0, x0_, x1_, cut=False)   # 1 deg inside the key's faces: clear of the ring's slot flanks
    # root rounds where the keys leave the rib face (all round, except where they run into the wall)
    def key_root(p0, p1):
        if abs(p0[0] - RIB[1]) > 0.05 or abs(p1[0] - RIB[1]) > 0.05:
            return False
        r_wall = DRUM['r'] - SHELL_T - 0.05
        if math.hypot(p0[1] - CY, p0[2] - CZ) > r_wall and math.hypot(p1[1] - CY, p1[2] - CZ) > r_wall:
            return False
        for q in RIB_KEYS:
            inside = all(q[0] - 0.05 <= p[1] - CY <= q[1] + 0.05 and min(q[2], q[3]) - 0.05 <= p[2] - CZ <= max(q[2], q[3]) + 0.05 for p in (p0, p1))
            on_y = any(abs(p0[1] - CY - v) < 0.05 and abs(p1[1] - CY - v) < 0.05 for v in (q[0], q[1]))
            on_z = any(abs(p0[2] - CZ - v) < 0.05 and abs(p1[2] - CZ - v) < 0.05 for v in (q[2], q[3]))
            if inside and (on_y or on_z):
                return True
        return False
    roots = []
    for b_ in d.GetBodies2(0, True):
        es = b_.GetEdges
        for e_ in ((es() if callable(es) else es) or []):
            cp = e_.GetCurveParams3
            if key_root(np.array(cp.StartPoint[:3]) * 1000.0, np.array(cp.EndPoint[:3]) * 1000.0):
                roots.append(e_)
    print('  key root edges', len(roots), flush=True)
    fillet_edges(d, roots, (KEY_ROOT_R, 0.8), 'KEY_ROOTS')
    # (the key-to-wall corners stay sharp: SolidWorks won't round them, and 45 deg gussets raised the peak, 2026-11-11)
    # crush ribs on each key's bearing face: two 0.8-wide ribs standing 0.25 proud into the 0.1 slot clearance, running along Z
    # (the way the ring slides on). They crush as the ring goes in, so both bearing keys of each direction start in contact.
    for k, q in enumerate(RIB_KEYS):
        lo, hi = sorted((q[2], q[3]))
        face = (q[0] - CRUSH, q[0]) if k in (0, 3) else (q[1], q[1] + CRUSH)
        for j, x in enumerate((RIB[1] + 2.0, RIB[1] + 8.0)):
            rect_x(d, f'CRUSH{k}{j}', (face[0], face[1], lo + 0.6, hi - 0.6), x, x + 0.8, cut=False)


def fore_details(d):
    ox, ix = CHEEKS[1], CHEEKS[0]
    # outboard cheek on the RS02 output: boss on the inner face, 6 x M4 counterbored from outside, 3 x Ø4 pins
    x_revolve(d, 'OUTPUT_BOSS', [(RS02_X['output'], 0), (ox[0] + 0.5, 0), (ox[0] + 0.5, 21.0), (RS02_X['output'], 21.0)])
    x_holes(d, 'OUTPUT_SCREWS', [P(r, a) for r, a in OUT_HOLES], 2.2, RS02_X['output'] - 0.1, ox[1] + 1)
    x_holes(d, 'OUTPUT_CBORES', [P(r, a) for r, a in OUT_HOLES], 3.75, 206.0, ox[1] + 1)
    # outboard cap: a Ø70 ring in a 1.5 mm recess with a snap groove; the M4 heads show through its middle
    x_revolve(d, 'OUT_CAP_SEAT', [(ox[1] - 1.5, 0), (ox[1] + 1, 0), (ox[1] + 1, 35.1), (ox[1] - 1.5, 35.1)], cut=True)
    x_revolve(d, 'OUT_CAP_GROOVE', [(ox[1] - 3.5, 32.4), (ox[1] - 1.4, 32.4), (ox[1] - 1.4, 33.6), (ox[1] - 3.5, 33.6)], cut=True)
    x_holes(d, 'OUTPUT_PINS', [P(r, a) for r, a in OUT_PINS], 2.025, RS02_X['output'] - 0.1, RS02_X['output'] + 6.0)
    # inboard cheek: 6808 bore with a shoulder at X 134, cable pocket under the cap, channel down into the forearm
    x_revolve(d, 'BEARING_BORE', [(STUB['x0'], 0), (ix[1] + 1, 0), (ix[1] + 1, 26.025), (STUB['x0'], 26.025)], cut=True)
    x_revolve(d, 'CAP_SEAT', [(ix[0] - 1, 0), (ix[0] + CAP['recess'], 0), (ix[0] + CAP['recess'], CAP['r'] + 0.1), (ix[0] - 1, CAP['r'] + 0.1)], cut=True)
    x_revolve(d, 'POCKET', [(ix[0] + 1.0, 0), (ix[0] + CAP['recess'] + CAP['pocket'], 0), (ix[0] + CAP['recess'] + CAP['pocket'], CAP['r'] - 1.0), (ix[0] + 1.0, CAP['r'] - 1.0)], cut=True)
    # break the recess lip where it meets the cheek's R6 rim round (a sharp 66 deg edge otherwise)
    lip = edges_where(d, lambda p: abs(math.hypot(p[1] - CY, p[2] - CZ) - CAP['r'] - 0.1) < 0.3 and ix[0] - 0.2 < p[0] < ix[0] + 1.2)
    print('  cap lip edges', len(lip), flush=True)
    fillet_edges(d, lip, (0.8, 0.6, 0.4), 'CAP_LIP_ROUND')
    # open the shoulder layer's centre (keep r 21.5-28 for the 6808 outer race): the stub ends free and the harness passes from its bore into the pocket
    x_revolve(d, 'STUB_PASS', [(ix[0] + 4.5, 0), (STUB['x0'] + 0.6, 0), (STUB['x0'] + 0.6, 21.5), (ix[0] + 4.5, 21.5)], cut=True)
    with Sk(d, plane(d, 'Z', CZ, 'POCKET_DROP_P'), 'POCKET_DROP') as s:     # flush with the pocket floor: no step for a sliver
        s.poly([(ix[0] + 1.5, CY - 36.0, CZ), (ix[0] + CAP['recess'] + CAP['pocket'], CY - 36.0, CZ), (ix[0] + CAP['recess'] + CAP['pocket'], 150.0, CZ), (ix[0] + 1.5, 150.0, CZ)])
    feat(d, s.feat, 'POCKET_DROP', 10.0, True, mode=MID)
    if STOP_KIND == 'lug':
        # stop slot: the lug's path over 0-124 deg plus its span (forearm frame: a drum point at phi sits at phi - flex)
        lo = STOP['lug_phi'] - STOP['travel'] - STOP['lug_span'] / 2
        hi = STOP['lug_phi'] + STOP['lug_span'] / 2
        arc_band(d, 'STOP_SLOT', STOP['r0'] - 0.5, STOP['r1'] + 0.5, lo, hi, ix[1] - STOP['depth'] - 0.5, ix[1] + 0.5, cut=True)
        # relief at the slot mouth for the lug's R2 root fillets: 2.2 mm wider over the last 2.6 mm
        d_ = math.degrees(1.1 / STOP['r0'])
        arc_band(d, 'SLOT_MOUTH', STOP['r0'] - 1.6, STOP['r1'] + 0.5,   # inner edge r 27.9, 1.9 mm off the 6808 bore
                 lo - d_, hi + d_, ix[1] - 2.1, ix[1] + 0.5, cut=True)   # relief 2.6 deep: worst-case axial stack (+-0.3) keeps contact off the R2 root
        d2 = math.degrees(2.2 / STOP['r0'])                   # the slot ends get the full 2.2 mm for the R2 fillets on the lug's end edges
        arc_band(d, 'SLOT_END_LO', STOP['r0'] - 1.6, STOP['r1'] + 0.5, lo - d2, lo + 2.0, ix[1] - 2.1, ix[1] + 0.5, cut=True)
        arc_band(d, 'SLOT_END_HI', STOP['r0'] - 1.6, STOP['r1'] + 0.5, hi - 2.0, hi + d2, ix[1] - 2.1, ix[1] + 0.5, cut=True)
    else:
        # slot for the dowel: its path over 0-124 deg, with R4.1 ends where it stops (forearm frame: drum phi sits at phi - flex)
        lo, hi = PIN['phi'] - STOP['travel'], PIN['phi']
        w = PIN['d'] / 2 + 0.1
        arc_band(d, 'STOP_SLOT', PIN['r'] - w, PIN['r'] + w, lo, hi, ix[1] - PIN['proud'] - 0.5, ix[1] + 0.5, cut=True)
        with Sk(d, plane(d, 'X', ix[1] - PIN['proud'] / 2, 'SLOT_ENDS_P'), 'SLOT_ENDS') as s_:
            for a_ in (lo, hi):
                y_, z_ = P(PIN['r'], a_)
                s_.circle((ix[1] - PIN['proud'] / 2, y_, z_), w)
        feat(d, s_.feat, 'SLOT_ENDS', PIN['proud'] + 1.0, True, mode=MID, lo=0.01)


def yaw_interface(d):
    """The belly's bottom rim (layout A2): a rim band under the Ø72 skin at Y 98.3, the Ø58.2 bore the RS00 goes up through,
    six M3 x 5.7 inserts on r 32.6 for the stub ring's screws, and the low cable channel at the back. The front of the belly
    near the elbow is 1.5 mm fuller (Y 148) so the RS00, 8 mm higher than in draft 4, clears it."""
    y_revolve(d, 'RIM_BAND', [(29.1, 98.3), (34.5, 98.3), (34.5, 105.5), (31.5, 107.5), (29.1, 107.5)])   # just past the 7 mm inserts
    with Sk(d, plane(d, 'Y', 98.3, 'SLEEVE_INSERTS_P'), 'SLEEVE_INSERTS') as s:
        for a in range(0, 360, 60):
            t = math.radians(a)
            s.circle((HX + 32.6 * math.cos(t), 98.3, CZ + 32.6 * math.sin(t)), 2.0)
    feat(d, s.feat, 'SLEEVE_INSERTS', 7.0, True, want=(1, 1, 98.3))
    with Sk(d, plane(d, 'Y', 98.3, 'CABLE_CHANNEL_LOW_P'), 'CABLE_CHANNEL_LOW') as s:
        s.poly([(HX - 6.0, 98.3, CZ - 23.0), (HX + 6.0, 98.3, CZ - 23.0), (HX + 6.0, 98.3, CZ - 32.0), (HX - 6.0, 98.3, CZ - 32.0)])   # 12 x 9: 1 mm+ off the 2.4 mm skin
    feat(d, s.feat, 'CABLE_CHANNEL_LOW', 13.0, True, want=(1, 1, 98.3))   # through the rim band; above it the cable runs behind the RS00


def upper():
    d = new_part(OUT['upper'])
    secs = [spline_section(d, section(*row), f'UA_SKIN_{i}') for i, row in enumerate(UPPER)]
    loft(d, secs, 'UA_SKIN', start=1)                          # start normal to the hub section: meets the hub square
    e = DRUM['edge']
    x_revolve(d, 'DRUM', [(DRUM['x0'], 0), (DRUM['x1'], 0), (DRUM['x1'], DRUM['r']), (DRUM['x0'], DRUM['r'])])
    drum_rims = edges_where(d, lambda p: (abs(p[0] - DRUM['x0']) < 0.01 or abs(p[0] - DRUM['x1']) < 0.01)
                            and abs(math.hypot(p[1] - CY, p[2] - CZ) - DRUM['r']) < 0.05)
    fillet_edges(d, drum_rims, (e, 6, 5), 'DRUM_EDGES')
    # skin into the drum: the intersection curve lies on the drum's cylinder, between its end planes
    blend = edges_where(d, lambda p: abs(math.hypot(p[1] - CY, p[2] - CZ) - DRUM['r']) < 0.3 and DRUM['x0'] + 1 < p[0] < DRUM['x1'] - 1)
    fillet_edges(d, blend, (12, 10, 8, 6, 4), 'SKIN_DRUM_BLEND')
    shell(d, [(HX, HUB_JOINT, CZ + 20)], SHELL_T, 'SHELL')
    upper_details(d)
    save(d, 'upper')


def cheek_profile(y_t=165.0, n=180):
    """Side outline of a cheek (Y, Z): the r 42 circle about the elbow axis, with tangent lines down to the belly's front
    and back at Y y_t, closed below inside the belly."""
    ys = [r[0] for r in FORE]
    zf = CZ + float(np.interp(y_t, ys, [r[3] for r in FORE]))
    zb = CZ - float(np.interp(y_t, ys, [r[4] for r in FORE]))

    def tangent(py, pz, sgn):
        dy, dz = py - CY, pz - CZ
        dist = math.hypot(dy, dz)
        base = math.atan2(dz, dy)
        off = math.acos(CHEEK_R / dist)
        return base + sgn * off
    a_f = tangent(y_t, zf, -1)        # front tangent point angle
    a_b = tangent(y_t, zb, 1)         # back tangent point angle
    # arc from the front tangent point over the top to the back tangent point
    a0, a1 = a_f, a_b                 # over the top (through +Y): decreasing angle from front to back
    if a1 > a0:
        a1 -= 2 * math.pi
    arc = [(CY + CHEEK_R * math.cos(t), CZ + CHEEK_R * math.sin(t)) for t in np.linspace(a0, a1, n)]
    return [(y_t - 0.5, zf), (y_t, zf)] + arc + [(y_t, zb), (y_t - 0.5, zb)]       # sits on the belly's top footprint


def cheek_outline(y_t=165.0, rho=20.0):
    """Side outline of a cheek plate (Y, Z) as sketch segments: from the belly top it rises vertically (G1 with the belly),
    turns through a concave arc of radius rho into the r 42 circle round the elbow axis, over the top, and down the same
    way at the back. Segments: ('line', p0, p1) and ('arc', start, end, a point on the arc)."""
    ys = [r[0] for r in FORE]
    zf = CZ + float(np.interp(y_t, ys, [r[3] for r in FORE]))
    zb = CZ - float(np.interp(y_t, ys, [r[4] for r in FORE]))

    def blend(z_line, side):
        dz = abs(z_line - CZ) + rho
        yc = CY - math.sqrt((CHEEK_R + rho) ** 2 - dz ** 2)
        zc = z_line + side * rho
        t_line = (yc, z_line)
        u = np.array([yc - CY, zc - CZ]) / (CHEEK_R + rho)
        t_circ = (CY + CHEEK_R * u[0], CZ + CHEEK_R * u[1])
        a0 = math.atan2(t_line[1] - zc, t_line[0] - yc)
        a1 = math.atan2(t_circ[1] - zc, t_circ[0] - yc)
        if a1 - a0 > math.pi:
            a1 -= 2 * math.pi
        if a0 - a1 > math.pi:
            a1 += 2 * math.pi
        am = (a0 + a1) / 2
        return t_line, t_circ, (yc + rho * math.cos(am), zc + rho * math.sin(am))
    lf, cf, mf = blend(zf, 1)
    lb, cb, mb = blend(zb, -1)
    top = (CY + CHEEK_R, CZ)               # a point on the big arc, over the top
    bot = (y_t - 0.5, zf), (y_t - 0.5, zb)
    return [('line', bot[0], (y_t, zf)), ('line', (y_t, zf), lf), ('arc', lf, cf, mf), ('arc', cf, cb, top),
            ('arc', cb, lb, mb), ('line', lb, (y_t, zb)), ('line', (y_t, zb), bot[1]), ('line', bot[1], bot[0])]


def fore():
    d = new_part(OUT['fore'])
    secs = [spline_section(d, section(*row), f'FA_SKIN_{i}') for i, row in enumerate(FORE)]
    loft(d, secs, 'FA_SKIN', end=1)                           # sides arrive vertical under the cheek plates
    segs = cheek_outline()
    y_plate_bottom = 164.5
    for i, (x0, x1) in enumerate(CHEEKS):
        xm = (x0 + x1) / 2
        with Sk(d, plane(d, 'X', xm, f'CHEEK{i}_P'), f'CHEEK{i}') as s_:
            sm_ = d.SketchManager
            for sg in segs:
                if sg[0] == 'line':
                    a_, b_ = s_.p((xm, *sg[1])), s_.p((xm, *sg[2]))
                    sm_.CreateLine(a_[0], a_[1], 0, b_[0], b_[1], 0)
                else:
                    a_, b_, c_ = s_.p((xm, *sg[1])), s_.p((xm, *sg[2])), s_.p((xm, *sg[3]))
                    sm_.Create3PointArc(a_[0], a_[1], 0, b_[0], b_[1], 0, c_[0], c_[1], 0)
        # a separate body, rounded all round while free, then combined with the belly
        d.ClearSelection2(True); s_.feat.Select2(False, 0)
        f_ = d.FeatureManager.FeatureExtrusion3(True, False, False, MID, 0, (x1 - x0) * m, (x1 - x0) * m, False, False, False, False, 0, 0,
                                                False, False, False, False, False, False, True, 0, 0, False)
        if f_ is None:
            raise SystemExit(f'CHEEK{i} extrude failed')
        f_.Name = f'CHEEK{i}'
        d.ForceRebuild3(False)
        plate = [b_ for b_ in d.GetBodies2(0, True) if abs(b_.GetBodyBox()[0] * 1000 - x0) < 0.2 and abs(b_.GetBodyBox()[3] * 1000 - x1) < 0.2][0]
        es = plate.GetEdges
        es = es() if callable(es) else es
        rim = []
        for e in es:
            cp = e.GetCurveParams3
            if abs(cp.StartPoint[0] * 1000 - cp.EndPoint[0] * 1000) < 0.01 and cp.StartPoint[1] * 1000 > y_plate_bottom + 0.2:
                rim.append(e)
        fillet_edges(d, rim, (6, 5, 4, 3), f'CHEEK{i}_ROUND')
    # combine the plates with the belly
    bs = list(d.GetBodies2(0, True))
    main = max(bs, key=lambda b_: b_.GetMassProperties(1190)[3])
    tools = [b_ for b_ in bs if b_ is not main]
    # combine: every body selected with mark 2, then an empty typed tool array (the call that works from Python)
    d.ClearSelection2(True)
    sd = d.SelectionManager.CreateSelectData
    sd.Mark = 2
    for b_ in bs:
        b_.Select2(True, sd)
    f_ = d.FeatureManager.InsertCombineFeature(15903, NUL, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, []))
    d.ForceRebuild3(False)
    print('  combine', f_ is not None, 'bodies', len(list(d.GetBodies2(0, True))), flush=True)
    if len(list(d.GetBodies2(0, True))) != 1:
        raise SystemExit('combine failed')
    x_revolve(d, 'DRUM_CLEAR', [(CHEEKS[0][1], 0), (CHEEKS[1][0], 0), (CHEEKS[1][0], CLEAR_R), (CHEEKS[0][1], CLEAR_R)], cut=True)
    # round the saddle the clearance cuts into the belly top (front and back), then blend the cheeks into the belly
    saddle = edges_where(d, lambda p: abs(math.hypot(p[1] - CY, p[2] - CZ) - CLEAR_R) < 1.0 and CHEEKS[0][1] - 0.5 < p[0] < CHEEKS[1][0] + 0.5)
    print('  saddle edges', len(saddle), flush=True)
    fillet_edges(d, saddle, (6, 5, 4, 3, 2), 'SADDLE_EDGE')
    # cavity: an inner loft 3 mm inside the skin, open at the bottom, closed 3 mm under the drum clearance (Y 158.9)
    ys = [r[0] for r in FORE]
    inner = []
    for y in (FORE[0][0] - 1.0, 108.0, 128.0, 148.0, 160.0):
        row = [float(np.interp(y, ys, [r[i] for r in FORE])) for i in range(1, 6)]
        inner.append(section(y, *[v - FORE_T for v in row[:4]], row[4]))
    sk = [spline_section(d, p, f'FA_CAV_{i}') for i, p in enumerate(inner)]
    v0 = vol(d)
    d.ClearSelection2(True)
    for k in sk:
        k.Select2(True, 1)
    f = d.FeatureManager.InsertCutBlend(False, True, False, 1.0, 0, 0, False, 0, 0, 0, True, True)
    if f is None:
        raise SystemExit('cavity failed')
    f.Name = 'CAVITY'
    d.ForceRebuild3(False)
    print(f'  CAVITY: cut {v0 - vol(d):.0f} mm3', flush=True)
    fore_details(d)
    yaw_interface(d)
    save(d, 'fore')


if __name__ == '__main__':
    for k in sys.argv[1:] or ('upper', 'fore'):
        print('==', k, flush=True)
        globals()[k]()
