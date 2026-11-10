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

from swg import *

sw = sw_app()
sw.CloseAllDocuments(True)
CAD = Path(__file__).resolve().parents[2]
CY, CZ, HX = 209.860668, 5.985875, 170.49
HUB_Y = 319.86
N = 40
SHELL_T = 3.0
OUT = {'upper': CAD / 'upper-arm' / 'upper_arm_organic_master_left.SLDPRT',
       'fore': CAD / 'forearm' / 'forearm_organic_master_left.SLDPRT'}
WIP = CAD / '_wip' / 'organic-arm' / 'cad'

# (y, x+ half-width, x- half-width, z front, z back, superellipse n); concept A after the flex sweep
HUB_JOINT = 302.0                      # today's hub disc (Y 302-319.86) stays: the skin starts under it
UPPER = [(HUB_JOINT, 39.0, 39.0, 39.0, 39.0, 2.0), (294, 38.3, 38.3, 37.5, 39, 2.2), (284, 35, 35, 29, 38, 2.5),
         (266, 29, 29, 17.5, 34, 2.4), (250, 26, 26, 13.5, 30, 2.3), (232, 26, 26, 13.5, 28, 2.2)]
FORE = [(90.3, 36.0, 36.0, 36.0, 36.0, 2.0), (108, 35, 35, 34, 36.0, 2.0), (128, 38.5, 38.5, 33, 36.5, 2.2),
        (148, 42.0, 43.0, 30, 38.5, 3.2), (165, 42.51, 43.49, 27, 39, 10.0)]
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


# ---- elbow internals (RobStride RS02 drawing: body Ø78.5 x 28, 41.5 overall; output Ø43, 3.5 proud, 6 x M4 x 7 and
# 3 x Ø4 pins on Ø24; housing 9 x M3 x 8 on Ø73 on the shoulder behind the body; back Ø65)
RS02_X = dict(back=151.8, shoulder=162.8, front=193.7, output=197.2)
BULKHEAD = (156.8, 162.8)              # RS02 mounting ring (a separate part, organic_parts.py): screwed to the RS02 on the bench,
RIB = (152.4, 156.8)                   # then dropped into the halves behind this rib, keyed by two dogs in its notches
RIB_R0, DOG_PHI, DOG_SPAN = 33.5, (90.0, 270.0), 9.0       # notches straight back and front, so the ring drops in square;
# each dog bears on 7.7 x 4.2 mm: 17 N.m of RS02 reaction is 6.5 MPa on the dog sides (2 dogs at r 37.5)
STUB = dict(x0=134.0, r_out=20.0, r_in=16.0)        # hollow inboard stub; 6808 (Ø40 / Ø52 x 7) on X 134-141
STOP = dict(r0=28.0, r1=36.5, lug_phi=90.0, lug_span=30.0, travel=124.0, depth=4.5)   # 5 mm rim outside the slot
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
    x_revolve(d, 'RS02_RIB', [(RIB[0], RIB_R0), (RIB[1], RIB_R0), (RIB[1], DRUM['r'] - 1.0), (RIB[0], DRUM['r'] - 1.0)])
    for k, ph in enumerate(DOG_PHI):
        arc_band(d, f'RIB_NOTCH{k}', RIB_R0 - 0.1, DRUM['r'] - 2.9, ph - DOG_SPAN / 2, ph + DOG_SPAN / 2, RIB[0] - 0.1, RIB[1] + 0.1, cut=True)
    # outboard end wall thickened to X 193.9: the RS02 housing face (r 22.5-39) stops on it, 0.2 mm axial play to the ring
    x_revolve(d, 'RS02_STOP', [(RS02_X['front'] + 0.2, 22.5), (DRUM['x1'] - 2.0, 22.5), (DRUM['x1'] - 2.0, DRUM['r'] - 1.0), (RS02_X['front'] + 0.2, DRUM['r'] - 1.0)])
    # hard stop: a lug on the drum's inboard end, running in a slot in the inboard cheek
    arc_band(d, 'STOP_LUG', STOP['r0'], STOP['r1'], STOP['lug_phi'] - STOP['lug_span'] / 2, STOP['lug_phi'] + STOP['lug_span'] / 2,
             DRUM['x0'] - STOP['depth'], DRUM['x0'] + 1.5, cut=False)
    # backing behind the lug: the 3 mm end wall alone bends under the 889 N stop load (FEA SF 0.55); 4.6 mm more wall over
    # the lug's sector, inside the bay (the harness enters the stub from the top, away from it)
    arc_band(d, 'LUG_BACKING', STUB['r_out'], DRUM['r'] - SHELL_T + 0.05, STOP['lug_phi'] - 40.0, STOP['lug_phi'] + 40.0,
             DRUM['x0'] + SHELL_T - 0.1, DRUM['x0'] + SHELL_T + 4.6, cut=False)


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
    # stop slot: the lug's path over 0-124 deg plus its span (forearm frame: a drum point at phi sits at phi - flex)
    lo = STOP['lug_phi'] - STOP['travel'] - STOP['lug_span'] / 2
    hi = STOP['lug_phi'] + STOP['lug_span'] / 2
    arc_band(d, 'STOP_SLOT', STOP['r0'] - 0.5, STOP['r1'] + 0.5, lo, hi, ix[1] - STOP['depth'] - 0.5, ix[1] + 0.5, cut=True)


def yaw_interface(d):
    """The PR #28 yaw stage bolts on unchanged: a rim band under the Ø72 skin at Y 90.3, the Ø58.2 bore the RS00 goes up
    through, six M3 x 5.7 inserts on r 32.6 for the sleeve flange (through the RS00 ring), and the low cable channel at the back."""
    y_revolve(d, 'RIM_BAND', [(29.1, 90.3), (34.5, 90.3), (34.5, 97.0), (31.5, 103.0), (29.1, 103.0)])
    with Sk(d, plane(d, 'Y', 90.3, 'SLEEVE_INSERTS_P'), 'SLEEVE_INSERTS') as s:
        for a in range(0, 360, 60):
            t = math.radians(a)
            s.circle((HX + 32.6 * math.cos(t), 90.3, CZ + 32.6 * math.sin(t)), 2.0)
    feat(d, s.feat, 'SLEEVE_INSERTS', 7.0, True, want=(1, 1, 90.3))
    with Sk(d, plane(d, 'Y', 90.3, 'CABLE_CHANNEL_LOW_P'), 'CABLE_CHANNEL_LOW') as s:
        s.poly([(HX - 6.0, 90.3, CZ - 23.0), (HX + 6.0, 90.3, CZ - 23.0), (HX + 6.0, 90.3, CZ - 33.0), (HX - 6.0, 90.3, CZ - 33.0)])
    feat(d, s.feat, 'CABLE_CHANNEL_LOW', 13.0, True, want=(1, 1, 90.3))   # through the rim band; above it the cable runs behind the RS00


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
        inner.append(section(y, *[v - SHELL_T for v in row[:4]], row[4]))
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
