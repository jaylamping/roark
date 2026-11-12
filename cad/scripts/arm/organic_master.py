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
# STL export options are SolidWorks system settings, not part of the template: pin them so every machine exports alike.
# Exports stay in the arm frame (no shift to positive space), binary, mm, quality Fine.
for _t, _v in ((69, True), (71, True)):      # swSTLBinaryFormat, swSTLDontTranslateToPositive
    sw.SetUserPreferenceToggle(_t, _v)
sw.SetUserPreferenceIntegerValue(211, 0)      # swExportStlUnits = swMM
sw.SetUserPreferenceIntegerValue(78, 2)       # swSTLQuality_Fine: reproduces the v26 exports' face counts (ring 3252)
sw.SetUserPreferenceIntegerValue(75, 203)     # swStepAP: AP203, as the v26 exports
print('  stl prefs: quality', sw.GetUserPreferenceIntegerValue(78), 'dev', sw.GetUserPreferenceDoubleValue(2),
      'angle', sw.GetUserPreferenceDoubleValue(3), 'no-translate', sw.GetUserPreferenceToggle(71),
      'step AP', sw.GetUserPreferenceIntegerValue(75), flush=True)
CAD = Path(__file__).resolve().parents[2]
CY, CZ, HX = 209.860668, 5.985875, 170.49
HUB_Y = 319.86
N = 40
SHELL_T = 3.0
FORE_T = 2.1              # forearm belly skin: belly FEA bulk SF 7.8 at 2.4 mm; 2.1 saves about 8 g more
OUT = {'upper': CAD / 'upper-arm' / 'upper_arm_organic_master_left.SLDPRT',
       'fore': CAD / 'forearm' / 'forearm_organic_master_left.SLDPRT'}
WIP = CAD / '_wip' / 'organic-arm' / 'cad'
# R2 (2026-11-11, trial): the neck opening narrowed to phi +-15 next to the rib, inside the drum only. ARM_R2=1 builds it into
# cad/_wip/r2 so R1's master and its STL stay as they are.
R2 = os.environ.get('ARM_R2') == '1'
R1B = os.environ.get('ARM_R1B') == '1'      # R1b: round the rib/opening-edge corners (see upper_details)
R1B_DONE = []
R1C = os.environ.get('ARM_R1C') == '1'      # R1c (2026-11-11): hub band: fins on the hub posts, bore 0.05 radial, lip round
SEAT_R = 35.9      # R1c keeps R1's 0.1 radial on the r 35.8 spigot (no interference risk; the fins carry the joint)
RIDGE_LAND = float(os.environ.get('ARM_RIDGE_LAND', '2.0'))      # option (d): spigot land below the groove, Y 296 to the groove opening (2026-11-11: 2 mm)
RIDGE_ARC = (35.0, 145.0)      # ridge arcs theta 35-145 and 215-325 (groove full depth 30-150 / 210-330, run-outs to 20 / 160)
# R1d (2026-11-12, after the R1c delta review): one axial datum (the end face on the hub disc at Y 302), the seat floor and post
# tops 0.3 below the spigot (Y 295.7), the load flank 0.1 off the groove's (ARM_FLANK_GAP) with crush ribs proud of it
# (ARM_RIB_PROUD: 0.25 to print, 0.1 = touching for the FEA, 0 = none), tip relieved to r 34.8, no floor corner ring, the collar
# foot chamfered into the arm's inside. Implies R1C. ARM_WIP_TAG keeps FEA variants apart.
R1D = os.environ.get('ARM_R1D') == '1'
if R1D:
    R1C = True
FLOOR_Y = 295.7 if R1D else 296.0
if R1C:
    WIP = CAD / '_wip' / ('r1d' + os.environ.get('ARM_WIP_TAG', '') if R1D else 'r1c')
    OUT['upper'] = WIP / ('upper_arm_organic_master_left_r1d.SLDPRT' if R1D else 'upper_arm_organic_master_left_r1c.SLDPRT')
    WIP.mkdir(parents=True, exist_ok=True)
R2_NECK = dict(x0=145.0, x1=156.0, hi=(15.0, 48.0), lo=(-32.0, -15.0), runout=(3.0, 2.0, 1.5))
if R2:
    WIP = CAD / '_wip' / 'r2'
    OUT['upper'] = WIP / 'upper_arm_organic_master_left_r2.SLDPRT'
    WIP.mkdir(parents=True, exist_ok=True)

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
    tpl = sw.GetUserPreferenceStringValue(8) or os.environ.get('SW_PART_TEMPLATE', '')   # holly-pc has no default part template set
    if not tpl:
        raise SystemExit('no default part template: set one in SolidWorks or set SW_PART_TEMPLATE')
    d = sw.NewDocument(tpl, 0, 0, 0)
    d.Extension.SetUserPreferenceInteger(263, 0, 5)   # swUnitSystem = MMGS whatever the template (Joey-PC's was IPS: STEP came out in inches)
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
    y_revolve(d, 'HUB_SEAT', [(0.0, FLOOR_Y), (SEAT_R, FLOOR_Y), (SEAT_R, HUB_JOINT + 1), (0.0, HUB_JOINT + 1)], cut=True)
    if R1D:
        os.environ['ARM_RIDGE'] = '1'
    if R1C and os.environ.get('ARM_RIDGE') == '1':      # option (d), 2026-11-11: Y tie, a ridge in the bore into a groove in the hub spigot
        # profile (r, Y): load flank (low-Y side) 30 deg from the radial plane, line-to-line with the groove's; tip r 34.5 (0.2 off the
        # groove bottom r 34.3); other flank 45 deg with 0.3 axial clearance. Arcs RIDGE_ARC and mirror (groove 5 deg longer each end).
        t30 = math.tan(math.radians(30.0))
        y0 = 296.0 + RIDGE_LAND      # groove opening (load side) at r 35.8
        ly = lambda r_: y0 + (35.8 - r_) * t30
        ny = lambda r_: y0 + 2.2 + (r_ - 34.3)
        # seat collar (2026-11-11, ridge5): at theta ~20-60 / 110-160 the arm's hollow inside reached up to Y 299 with its surface at
        # r 36.2, so the ridge root met it in a ~0.06 mm knife edge (STOP_0 vm SF 0.95 at 0.5 mm). A full ring r 35.9-37.4 over Y 296-302
        # makes the seat wall solid all round (outer skin there is r >= 38.21; the ring was already >= 83 % solid in every 10 deg bin,
        # the rest is the 0.3 mm gap behind the bore). Full ring: no end faces, so no new overhang with the halves seam-face down.
        if os.environ.get('ARM_SEAT_COLLAR', '1') == '1':
            y_revolve(d, 'SEAT_COLLAR', [(SEAT_R, FLOOR_Y), (37.4, FLOOR_Y), (37.4, HUB_JOINT), (SEAT_R, HUB_JOINT)])
            if R1D:      # collar foot: a 45 deg chamfer from the bore edge down into the arm's inside wall (r ~36.2) instead of the
                # 0.3 ledge and its re-entrant corner (R1c STOP_0 layer 1.29 at 0.5 mm); the triangle's outer part lies in the skin
                y_revolve(d, 'SEAT_COLLAR_FOOT', [(SEAT_R, FLOOR_Y), (37.0, FLOOR_Y), (37.0, FLOOR_Y - 1.1)])
        if R1D:      # load flank 0.1 (ARM_FLANK_GAP) off the groove's, measured normal to the flank
            gap = float(os.environ.get('ARM_FLANK_GAP', '0.1'))
            ly = lambda r_: y0 + (35.8 - r_) * t30 + gap / math.cos(math.radians(30.0))
        tc = float(os.environ.get('ARM_RIDGE_TIP_CHAMFER', '0.2'))      # load-flank tip corner, clear of the groove's 0.4 bottom round (its tangent point is at r 34.5)
        tip = [(34.5 + tc * math.cos(math.radians(30.0)), ly(34.5 + tc * math.cos(math.radians(30.0)))), (34.5, ly(34.5) + tc)] if tc > 0 else [(34.5, ly(34.5))]
        top = [(34.5, ny(34.5))]
        if os.environ.get('ARM_RIDGE_REVCP', '1') == '1':      # hub rev C+ (2026-11-11): groove bottom ends Y 300.4 with an R1.0 round on that corner.
            # 45 deg flank moved 0.1 toward low Y (0.3 axial clearance kept); top tip chamfer (34.5, 299.85) -> (34.9, 300.70) clears the
            # R1.0 round by >= 0.26 (min over its arc); the load flank is unchanged
            ny = lambda r_: y0 + 2.1 + (r_ - 34.3)
            top = [(34.5, 299.85), (34.9, ny(34.9))]
        if R1D:      # tip relieved to r 34.8 (0.5 off the groove bottom; it prints on support at the crown); 0.15 chamfer on the
            # load side; top chamfer (34.8, 300.4) -> (35.0, 300.8) clears the hub's R1.0 round by >= 0.33
            c30 = math.cos(math.radians(30.0))
            tip = [(34.8 + 0.15 * c30, ly(34.8 + 0.15 * c30)), (34.8, ly(34.8) + 0.15)]
            top = [(34.8, 300.4), (35.0, ny(35.0))]
        prof = [(36.3, ly(36.3))] + tip + top + [(35.9, ny(35.9)), (36.3, ny(35.9))]      # stays inside Y 302 (the arm's end face)
        # two partial revolves, one per arc, centred on theta 90 / 270 (2026-11-11: a full revolve trimmed back to r 35.88 left a
        # 0.02 mm band proud of the bore all round, which broke the FEA mesh)
        RING = R1D and os.environ.get('ARM_RIDGE_RING') == '1'      # 2026-11-12: full-ring ridge (each half a full semicircle through the seam)
        if RING:
            y_revolve(d, 'SEAT_RIDGE_RING', prof)
        for sgn, tag in (() if RING else ((1, 'F'), (-1, 'B'))):
            with Sk(d, plane(d, 'X', HX, f'SEAT_RIDGE{tag}_P'), f'SEAT_RIDGE{tag}') as sk_:
                sk_.poly([(HX, y_, CZ + sgn * r_) for r_, y_ in prof])
                centerline(sk_, (HX, 150, CZ), (HX, 340, CZ))
            revolve(d, sk_.feat, f'SEAT_RIDGE{tag}', None, False, angle=RIDGE_ARC[1] - RIDGE_ARC[0], mid=True, lo=0.01)
        if R1D and os.environ.get('ARM_RIDGE_TAPER', '1') == '1' and os.environ.get('ARM_RIDGE_RING') != '1':      # 2026-11-12 (R1d baseline): the ridge ends governed at the stop
            # (abrupt full-depth ends). The tip radius ramps smoothly (half cosine: no kink where the full-height tip starts) from r 34.8
            # at theta 45 / 135 / 225 / 315 to the bore (r 35.9) at 35 / 145 / 215 / 325: no flat end faces. Cut by a Y-extrude of the
            # region r 33 .. r_tip(theta), over Y 297.9-301.7 only (the ridge's span), running 0.5 deg past the end at the bore radius.
            for k_, (t_end, t_full) in enumerate(((35.0, 45.0), (145.0, 135.0), (215.0, 225.0), (325.0, 315.0))):
                sgn_ = np.sign(t_full - t_end)
                # 5 segments per ramp (2 deg, ~1.2 mm each): 40 left ~0.15 mm strip faces that stalled the mesher (2026-11-12);
                # no overrun past the end along the bore (a coincident boundary)
                ths = np.linspace(t_end, t_full, int(os.environ.get('ARM_TAPER_SEGS', '5')) + 1)
                def rc(t, t_end=t_end, t_full=t_full):
                    s_ = min(max(abs(t - t_full) / abs(t_full - t_end), 0.0), 1.0)      # 0 at full height, 1 at the end
                    return 35.9 if abs(t - t_full) > abs(t_full - t_end) else 34.8 + (35.9 - 34.8) * (1.0 - math.cos(0.5 * math.pi * s_))
                pts = [(HX + rc(t) * math.cos(math.radians(t)), 299.8, CZ + rc(t) * math.sin(math.radians(t))) for t in ths]
                pts += [(HX + 33.0 * math.cos(math.radians(t)), 299.8, CZ + 33.0 * math.sin(math.radians(t))) for t in ths[::-1]]
                with Sk(d, plane(d, 'Y', 299.8, f'RIDGE_TAPER{k_}_P'), f'RIDGE_TAPER{k_}') as sk_:
                    sk_.poly(pts)
                feat(d, sk_.feat, f'RIDGE_TAPER{k_}', 3.8, True, mode=MID, lo=0.01)
        rp = float(os.environ.get('ARM_RIB_PROUD', '0.25')) if R1D else 0.0
        if rp > 0:      # R1d crush ribs on the load flank: 6 per arc, 1 wide (tangential), over r 34.95-35.75, rp proud of the flank
            # (0.25 to print: 0.15 interference on the 0.1 gap; 0.1 in the FEA = touching). Each lies in a plane through the hub axis,
            # which carries the front rib at theta and the back one at theta + 180.
            c30, s30 = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
            px_, pz_ = plane(d, 'X', HX, 'RIB_AX_PX'), plane(d, 'Z', CZ, 'RIB_AX_PZ')
            d.ClearSelection2(True); px_.Select2(False, 0); pz_.Select2(True, 0)
            d.InsertAxis2(True)
            ax_ = d.FeatureByPositionReverse(0); ax_.Name = 'HUB_AXIS_REF'
            def rib_pts(th):
                rA, rB = 34.95, 35.75
                A, B = (rA, ly(rA)), (rB, ly(rB))
                q = [(A[0] + 0.25 * s30, A[1] + 0.25 * c30), (B[0] + 0.25 * s30, B[1] + 0.25 * c30), (B[0] - rp * s30, B[1] - rp * c30), (A[0] - rp * s30, A[1] - rp * c30)]
                c_, s_ = math.cos(math.radians(th)), math.sin(math.radians(th))
                return [(HX + r_ * c_, y_, CZ + r_ * s_) for r_, y_ in q]
            rib_th = (15.0, 45.0, 75.0, 105.0, 135.0, 165.0) if os.environ.get('ARM_RIDGE_RING') == '1' else (49.0, 65.0, 81.0, 99.0, 115.0, 131.0) if os.environ.get('ARM_RIDGE_TAPER', '1') == '1' else (45.0, 63.0, 81.0, 99.0, 117.0, 135.0)      # ribs on the full-height part only
            for k_, th in enumerate(rib_th):
                a_ = th - 90.0
                pts_ = rib_pts(th) + rib_pts(th + 180.0)
                done = False
                for flip in (False, True):
                    d.ClearSelection2(True); px_.Select2(False, 0); ax_.Select2(True, 1)
                    neg = (a_ < 0) != flip
                    pl_ = d.FeatureManager.InsertRefPlane(16 + (256 if neg else 0), math.radians(abs(a_)), 4, 0, 0, 0) if abs(a_) > 1e-6 else px_
                    if pl_ is None:
                        continue
                    if pl_ is not px_:
                        pl_.Name = f'RIB{k_}_P{"f" if flip else ""}'
                    d.ClearSelection2(True); pl_.Select2(False, 0)
                    d.SketchManager.InsertSketch(True)
                    T = d.GetActiveSketch2.ModelToSketchTransform.ArrayData
                    zoff = max(abs(x * m * T[2] + y * m * T[5] + z * m * T[8] + T[11]) for x, y, z in pts_) / m      # mm off the sketch plane
                    d.InsertSketch2(True)
                    if zoff < 1e-3:
                        with Sk(d, pl_, f'SEAT_FLANK_RIB{k_}') as sk_:
                            sk_.poly(pts_[:4]); sk_.poly(pts_[4:])
                        feat(d, sk_.feat, f'SEAT_FLANK_RIB{k_}', 1.0, False, mode=MID, lo=0.01)
                        done = True
                        break
                    print(f'  rib plane {k_} at {a_:+.0f} deg off by {zoff:.3f} mm, flip', flush=True)
                if not done:
                    raise SystemExit(f'rib {k_} plane failed')
        ec = float(os.environ.get('ARM_END_CHAMFER', '0.5'))
        er = float(os.environ.get('ARM_END_ROUND', '0'))
        if er > 0:      # (2026-11-12, option) a round tangent to the bore wall and the end face instead of the chamfer, so the end-face
            # contact on the hub disc fades out instead of ending on an edge (G90 contact-corner value 0.81 at the chamfer's outer edge).
            # R0.8 clears the rev D spigot-foot fillet by 0.23 and leaves r 36.7-37.6 bearing. The ridge top is taken down to the round's
            # start (Y 302 - R) from where its 45 flank (Y = r + 265.8) reaches that height, so no step or knife edge is left.
            ec = 0.0
            yr = HUB_JOINT - er
            arc = [(SEAT_R + er - er * math.cos(a), yr + er * math.sin(a)) for a in np.linspace(0.0, math.pi / 2, 13)]
            y_revolve(d, 'SEAT_END_ROUND', [(yr - 265.8, yr)] + arc + [(SEAT_R + er, HUB_JOINT + 0.3), (yr - 265.8, HUB_JOINT + 0.3)], cut=True)
        # R1e (2026-11-12): ARM_END_DROP lowers the end face so a printed PETG shim ring (r 36.2-38.4, picked by trial at assembly)
        # sits between it and the hub disc: the play-free joint. Everything from the bore (r 35.9) out past the skin above the new end
        # face comes off; the 0.5 chamfer and the ridge-top flat follow the end face down.
        drop = float(os.environ.get('ARM_END_DROP', '0'))
        ye = HUB_JOINT - drop
        if drop > 0:
            y_revolve(d, 'END_DROP', [(SEAT_R, ye), (41.0, ye), (41.0, HUB_JOINT + 0.5), (SEAT_R, HUB_JOINT + 0.5)], cut=True)
        if ec > 0:      # bore-to-end-face edge (r 35.9, Y 302): 0.5 x 45 chamfer, inside only, for the hub's R0.3 spigot-to-disc corner (rev C+)
            y_revolve(d, 'SEAT_END_CHAMFER', [(SEAT_R, ye - ec), (SEAT_R + ec, ye), (SEAT_R + ec, ye + 0.3), (SEAT_R, ye + 0.3)], cut=True)
            if os.environ.get('ARM_RIDGE_REVCP', '1') == '1':      # the ridge's 45 flank (Y = r + 265.8) runs parallel to the chamfer 0.2 above it,
                # leaving a 0.2-tall wedge on the ridge top at the bore (mesh gate, 2026-11-11): flatten the ridge top at the chamfer's start
                # its outer boundary follows the chamfer exactly (r 35.91 left a 0.01 lip: a knife edge at the ridge ends)
                # (R1e: with the end face lowered, the flat starts where the 45 flank meets it, so no step is left)
                rf0 = 35.6 if drop <= 0 else min(35.6, (ye - ec) - 265.8)
                y_revolve(d, 'RIDGE_TOP_FLAT', [(rf0, ye - ec), (SEAT_R, ye - ec), (SEAT_R + ec, ye), (SEAT_R + ec, ye + 0.3), (rf0, ye + 0.3)], cut=True)
        li = os.environ.get('ARM_SEAM_LEADIN')      # "relief,length" (R1e: "0.1,2.0")
        if li and R1D:      # R1e lead-in: the load flank relieved 'relief' along its normal over the last 'length' mm of arc at each ridge end
            # (the seam faces, theta 0 and 180, both halves), so a zero-gap flank does not bind or scuff where the halves slide tangentially
            # on closing; prisms along Z through the seam plane, CZ +- length
            rl, ll = (float(t) for t in li.split(','))
            gap_ = float(os.environ.get('ARM_FLANK_GAP', '0.1'))
            lyr = lambda r_: y0 + (35.8 - r_) * t30 + gap_ / math.cos(math.radians(30.0))
            dn = rl / math.cos(math.radians(30.0))
            rs = list(np.linspace(34.4, SEAT_R, 9))      # to the bore radius exactly: not into the collar wall
            for k_, sgn in enumerate((1.0, -1.0)):
                pts = [(HX + sgn * r_, lyr(r_) - 0.05, CZ) for r_ in rs] + [(HX + sgn * r_, lyr(r_) + dn, CZ) for r_ in reversed(rs)]
                with Sk(d, plane(d, 'Z', CZ, f'SEAM_LEADIN{k_}_P'), f'SEAM_LEADIN{k_}') as sk_:
                    sk_.poly(pts)
                feat(d, sk_.feat, f'SEAM_LEADIN{k_}', 2.0 * ll, True, mode=MID, lo=0.01)
        rf = float(os.environ.get('ARM_FLOOR_FILLET', '0' if R1D else '0.25'))      # R1d: none (the floor has 0.3 clearance)
        if rf > 0:      # (b) bore-to-floor corner (r 35.9, Y 296), where the spigot's bottom edge bore (STOP_0 vm SF 0.94 at 0.5 mm).
            # 0.25 clears the hub spigot's 0.4 bottom round by ~0.06; it would touch a sharp-cornered spigot by ~0.1 (needs the rounded hub)
            # built as a revolved 45 deg corner ring (edge fillets here go stale after the first edge and fail); where there is no
            # floor it is a 0.25 lip at the foot of the collar, facing -Y (a vertical wall with the halves seam-face down)
            # only where the arm has a floor at Y 296 (theta 69.5-109.5, front half only, from the R1c export); elsewhere the hollow
            # inside reaches the collar's foot and a full ring left a free 0.25 wedge lip (mesh gate, 2026-11-11)
            with Sk(d, plane(d, 'X', HX, 'SEAT_FLOOR_CORNER_P'), 'SEAT_FLOOR_CORNER') as sk_:
                sk_.poly([(HX, y_, CZ + r_) for r_, y_ in [(SEAT_R - rf, 296.0), (SEAT_R + 0.3, 296.0), (SEAT_R + 0.3, 296.0 + rf + 0.3), (SEAT_R, 296.0 + rf)]])
                centerline(sk_, (HX, 150, CZ), (HX, 340, CZ))
            revolve(d, sk_.feat, 'SEAT_FLOOR_CORNER', None, False, angle=36.0, mid=True, lo=0.01)
    if R1C and os.environ.get('ARM_SEAT_RIBS', '0') == '1':      # default off (2026-11-12): R1c/R1d do not use the bore crush ribs      # seat crush ribs (2026-11-11): the seat must be gap-free, or the hub's lugs and bolts carry the moment.
        # Six axial ribs on the r 35.9 bore over Y 296-302 at theta 45/90/135 in each half (from +X toward +Z about the hub
        # axis), 1 wide at the tip, tip 0.15 proud of the r 35.8 spigot; the halves still close on the seam and the ribs crush.
        r_tip = float(os.environ.get('ARM_SEAT_RIB_TIP', '35.65'))      # 35.8 for the FEA model (crushed, line-to-line)
        for k_, th in enumerate((45.0, 90.0, 135.0, 225.0, 270.0, 315.0)):
            c_, s_t = math.cos(math.radians(th)), math.sin(math.radians(th))
            def pt(r_, w_):      # radius r_ along theta, offset w_ across
                return (HX + r_ * c_ - w_ * s_t, 299.0, CZ + r_ * s_t + w_ * c_)
            with Sk(d, plane(d, 'Y', 299.0, f'SEAT_RIB{k_}_P'), f'SEAT_RIB{k_}') as sk_:
                sk_.poly([pt(SEAT_R + 0.4, -1.0), pt(SEAT_R + 0.4, 1.0), pt(r_tip, 0.5), pt(r_tip, -0.5)])
            feat(d, sk_.feat, f'SEAT_RIB{k_}', 6.0, False, mode=MID, lo=0.01)
    if R1C and os.environ.get('ARM_R1C_LIP') == '1':      # skipped (2026-11-11: built 3 of 6 edges, then failed); round the bore's inner lip at Y 296 (the spigot's contact edge, sigma z 48 MPa in the hub-seat model)
        lip = edges_where(d, lambda p: abs(p[1] - 296.0) < 0.05 and abs(math.hypot(p[0] - HX, p[2] - CZ) - SEAT_R) < 0.1)
        print('  R1c bore lip edges', len(lip), flush=True)
        for i_, e_ in enumerate(lip):      # edge by edge; skipped where it won't build
            fillet_edges(d, [e_], (1.0, 0.75, 0.5), f'R1C_SEAT_LIP{i_}')
    # drum ends: the output passes the outboard end wall; the inboard end carries the hollow stub for the 6808
    x_revolve(d, 'OUTPUT_BORE', [(RS02_X['front'], 0), (DRUM['x1'] + 1, 0), (DRUM['x1'] + 1, 22.5), (RS02_X['front'], 22.5)], cut=True)
    x_revolve(d, 'STUB', [(STUB['x0'], STUB['r_in']), (DRUM['x0'] + 1.5, STUB['r_in']), (DRUM['x0'] + 1.5, STUB['r_out']), (STUB['x0'], STUB['r_out'])])
    x_revolve(d, 'STUB_BORE', [(STUB['x0'] - 1, 0), (DRUM['x0'] + 4, 0), (DRUM['x0'] + 4, STUB['r_in']), (STUB['x0'] - 1, STUB['r_in'])], cut=True)
    # RS02 seat: bulkhead ring at the shoulder, bore for the Ø65 back, 9 x M3 on Ø73
    x_revolve(d, 'RS02_RIB', [(RIB[0], RIB_R0), (RIB[1], RIB_R0), (RIB[1], DRUM['r'] - SHELL_T + 0.3), (RIB[0], DRUM['r'] - SHELL_T + 0.3)])   # just into the wall: under the neck opening it ends as a free edge, no lip
    # the harness passes the rib at the top, from the neck to the stub: the rib is open there (phi -15 to 15)
    arc_band(d, 'RIB_HARNESS_GAP', RIB_R0 - 0.5, DRUM['r'] - SHELL_T + 0.6, -15.0, 15.0, RIB[0] - 0.1, RIB[1] + 0.1, cut=True)
    if R2:
        # wall continued across the neck opening from phi 15 (and -15) out past its edges (phi -21..39 at mid-wall), X 145-156:
        # r 41.5-44.5 lies inside the drum cylinder, so the outside is unchanged. The harness keeps phi +-15 (22 mm at r 42) and
        # the RS02 plug (X 157-163.5) its old opening. The band's outboard end runs out in a round.
        n2 = R2_NECK
        for tag, (a0, a1) in (('HI', n2['hi']), ('LO', n2['lo'])):
            arc_band(d, f'R2_NECK_{tag}', DRUM['r'] - SHELL_T, DRUM['r'], a0, a1, n2['x0'], n2['x1'], cut=False)
        ro = []      # the band end face's radial edges (new and old opening edges), not its faceted arcs
        for bd in d.GetBodies2(0, True):
            es = bd.GetEdges
            for e in ((es() if callable(es) else es) or []):
                cp = e.GetCurveParams3
                a, c = np.array(cp.StartPoint[:3]) * 1000.0, np.array(cp.EndPoint[:3]) * 1000.0
                ra, rc = math.hypot(a[1] - CY, a[2] - CZ), math.hypot(c[1] - CY, c[2] - CZ)
                if abs(a[0] - n2['x1']) < 0.05 and abs(c[0] - n2['x1']) < 0.05 and abs(ra - rc) > 1.0 and min(ra, rc) > DRUM['r'] - SHELL_T - 0.2:
                    ro.append(e)
        print('  R2 run-out edges', len(ro), flush=True)
        for i, e in enumerate(ro):      # one at a time: a corner that won't take a round mustn't block the others
            fillet_edges(d, [e], n2['runout'] + (1.0, 0.5), f'R2_NECK_RUNOUT{i}')
        # iteration 1: the rib's inboard face now meets the band's wall in a sharp concave corner (E34 layer SF 1.06 there):
        # round it R2 like the ring side, over the band's angles
        def at_rib_back(p):
            r = math.hypot(p[1] - CY, p[2] - CZ)
            ph = math.degrees(math.atan2(-(p[2] - CZ), p[1] - CY))
            in_band = n2['hi'][0] - 0.5 <= ph <= n2['hi'][1] + 0.5 or n2['lo'][0] - 0.5 <= ph <= n2['lo'][1] + 0.5
            return abs(p[0] - RIB[0]) < 0.05 and abs(r - (DRUM['r'] - SHELL_T)) < 0.1 and in_band
        rb = edges_where(d, at_rib_back)
        print('  R2 rib inboard corner edges', len(rb), flush=True)
        if fillet_edges(d, rb, (2.0, 1.5, 1.0), 'R2_RIB_BACK') is None:
            for i, e in enumerate(rb):
                fillet_edges(d, [e], (2.0, 1.5, 1.0), f'R2_RIB_BACK{i}')
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
    if R1B:
        # R1b (2026-11-11): the R2 round ends at the neck opening's edges (phi 41 and -24), where the rib's top (r 41.8, 0.3 proud
        # of the wall) meets the opening's edge face in a sharp corner: the elbow-torque peak there does not converge (singular).
        # Round those edges, within 3.5 mm of each corner
        corners = [np.array((154.0, CY + 41.8 * math.cos(math.radians(a)), CZ - 41.8 * math.sin(math.radians(a)))) for a in (40.5, -24.0)]
        oc = []      # edges on the rib top / wall band (r 41.4-41.9 at start, middle and end) that pass within 3.5 mm of a corner
        for bd in d.GetBodies2(0, True):
            es = bd.GetEdges
            for e in ((es() if callable(es) else es) or []):
                cp = e.GetCurveParams3
                ev = list(e.GetCurve.Evaluate2((cp.UMinValue + cp.UMaxValue) / 2, 0))
                pts = [np.array(cp.StartPoint[:3]) * 1000.0, np.array(ev[:3]) * 1000.0, np.array(cp.EndPoint[:3]) * 1000.0]
                if all(41.4 < math.hypot(q[1] - CY, q[2] - CZ) < 41.9 for q in pts) and min(np.linalg.norm(q - c) for q in pts for c in corners) < 3.5:
                    oc.append(e)
        print('  R1b open-corner edges', len(oc), flush=True)
        # attempt 2 (attempt 1, all six at R1.5/1.0/0.75 together, built nothing): one edge at a time, smaller rounds, and a
        # 0.3 x 45 deg chamfer where no round builds (the rib top stands only 0.3 proud of the wall there)
        for i, e in enumerate(oc):
            r_ = fillet_edges(d, [e], (1.0, 0.6, 0.4), f'R1B_OPEN_CORNER{i}')
            if r_ is None:
                d.ClearSelection2(True)
                e.Select4(True, NUL)
                f = d.FeatureManager.InsertFeatureChamfer(0, 1, 0.3 * m, math.pi / 4, 0, 0, 0, 0)
                d.ForceRebuild3(False)
                r_ = 'C0.3' if f is not None else None
                print(f'  R1B_OPEN_CORNER{i}: chamfer', r_, flush=True)
            R1B_DONE.append(r_)
        print('  R1b corners:', R1B_DONE, flush=True)
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
