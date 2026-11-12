"""SolidWorks helpers for the shoulder scripts, in model (torso frame) coordinates, mm.

One SolidWorks instance per working session, reused across scripts through sw_instance.session() (tools/solidworks/RULES.md).
Sketch points are mapped through each sketch's ModelToSketchTransform, so a plane's orientation never matters.
"""
import inspect
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pythoncom
from win32com.client import VARIANT

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tools' / 'solidworks'))
from sw_instance import session, end_session  # noqa: E402

CAD = REPO / 'cad'
LOOK = os.environ.get('LOOK', '')          # look-option variants build into _wip/look/<x>, never over the real parts
OUT = CAD / '_wip' / 'look' / LOOK if LOOK else CAD / 'shoulder' / 'left'
OUT.mkdir(parents=True, exist_ok=True)
VENDOR = CAD / 'vendor' / 'robstride'
WIP = CAD / '_wip' / 'shoulder-pass1'
WIP.mkdir(parents=True, exist_ok=True)
STATE = WIP / os.environ.get('SW_STATE_NAME', '.sw_instance_pid')   # a second stream runs its own instance
TPL_PART = r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
TPL_ASM = r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\assembly 0250mm and smaller.asmdot'
NUL = VARIANT(pythoncom.VT_DISPATCH, None)
m = 1e-3
BASE = {'X': 'Right Plane', 'Y': 'Top Plane', 'Z': 'Front Plane'}
BLIND, THRU_ALL, MID = 0, 1, 6


def log(*a):
    s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
    print(s, flush=True)
    with open(WIP / os.environ.get('SW_LOG_NAME', 'build_log.txt'), 'a', encoding='utf8') as f:
        f.write(s + '\n')


def L(v=0):
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)


_APP = []


def app():
    if not _APP:
        _APP.append(session(STATE, visible=True).sw)
    return _APP[0]


def finish():
    end_session(STATE)


def vol(d):
    return sum(b.GetMassProperties(1190)[3] for b in (d.GetBodies2(0, True) or [])) * 1e9


def vol_com(d):
    """Total volume (mm3) and first moment (mm4 vector) of all solid bodies."""
    V, M = 0.0, np.zeros(3)
    for b in (d.GetBodies2(0, True) or []):
        mp = b.GetMassProperties(1190)
        v = mp[3] * 1e9
        V += v
        M += np.array(mp[:3]) * 1e3 * v
    return V, M


def bodies(d):
    return [(b.Name, round(b.GetMassProperties(1190)[3] * 1e9, 0), [round(v * 1e3, 1) for v in b.GetBodyBox()]) for b in (d.GetBodies2(0, True) or [])]


def new_part(path, tpl=TPL_PART):
    sw = app()
    sw.CloseAllDocuments(True)     # this session's own instance only: a failed build leaves its part open
    d = sw.NewDocument(tpl, 0, 0, 0)
    if d is None:
        raise SystemExit('NewDocument failed: ' + tpl)
    d.SetUserPreferenceIntegerValue(194, 0) if False else None
    e, w = L(), L()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ok = d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    log('new', Path(path).name, 'saved', ok, e.value)
    return d


def save(d):
    d.ForceRebuild3(False)
    e, w = L(), L()
    ok = d.Save3(1, e, w)
    log('  save', d.GetTitle, ok, e.value, w.value)
    return ok


def export(d, path, stl_fine=True):
    sw = app()
    old = sw.GetUserPreferenceIntegerValue(78)
    od2, od3 = sw.GetUserPreferenceDoubleValue(2), sw.GetUserPreferenceDoubleValue(3)
    if stl_fine:
        # custom: 0.01 mm deviation, 3 deg angle (the 'fine' preset left sliver triangles at face boundaries, which the
        # pictures' 40 deg feature-edge pass drew as lines across smooth blends)
        sw.SetUserPreferenceIntegerValue(78, 3)
        sw.SetUserPreferenceDoubleValue(2, 1e-5)
        sw.SetUserPreferenceDoubleValue(3, 0.0524)
    try:
        e, w = L(), L()
        ok = d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    finally:
        sw.SetUserPreferenceIntegerValue(78, old)
        sw.SetUserPreferenceDoubleValue(2, od2)
        sw.SetUserPreferenceDoubleValue(3, od3)
    log('  export', Path(path).name, ok, e.value)
    return ok


# ------------------------------------------------------------------------------------------------------------ reference
def plane(d, axis, off, name):
    """Plane normal to model axis 'X'/'Y'/'Z' at coordinate off (mm)."""
    if abs(off) < 1e-9:
        return d.FeatureByName(BASE[axis])
    f = d.FeatureByName(name)
    if f is not None:
        return f
    d.ClearSelection2(True)
    d.FeatureByName(BASE[axis]).Select2(False, 0)
    p = d.FeatureManager.InsertRefPlane(8 + (256 if off < 0 else 0), abs(off) * m, 0, 0, 0, 0)
    if p is None:
        raise SystemExit('plane failed ' + name)
    p.Name = name
    return p


def ref_axis(d, p1, p2, name):
    d.ClearSelection2(True)
    p1.Select2(False, 0)
    p2.Select2(True, 0)
    ok = d.InsertAxis2(True)
    f = d.FeatureByPositionReverse(0)
    if not ok or f is None or f.GetTypeName2 != 'RefAxis':
        raise SystemExit('axis failed ' + name)
    f.Name = name
    return f


def plane_normal(pl):
    """Model unit normal of a reference plane feature."""
    t = pl.GetSpecificFeature2.Transform.ArrayData
    return np.array([t[6], t[7], t[8]])


def plane_axis_angle(d, axis_feat, ref_plane, deg, want_dir, name):
    """Plane through axis_feat at deg to ref_plane, chosen so that it contains the model direction want_dir.
    Returns (plane, sign): the plane's angle dimension D1 is 'deg' with that flip."""
    want = np.array(want_dir, float)
    want /= np.linalg.norm(want)
    for flip in (0, 256):
        d.ClearSelection2(True)
        axis_feat.Select2(False, 0)
        ref_plane.Select2(True, 1)
        p = d.FeatureManager.InsertRefPlane(4, 0, 16 + flip, math.radians(deg), 0, 0)
        if p is None:
            continue
        n = plane_normal(p)
        if abs(float(n @ want)) < 1e-4:
            p.Name = name
            return p, flip
        d.ClearSelection2(True)
        p.Select2(False, 0)
        d.EditDelete()
    raise SystemExit('angle plane failed ' + name)


def plane_offset_from(d, base, off, toward, name):
    """Plane parallel to base at distance off, on the side of model direction 'toward'."""
    n = plane_normal(base)
    flip = 256 if float(n @ np.array(toward, float)) < 0 else 0
    d.ClearSelection2(True)
    base.Select2(False, 0)
    p = d.FeatureManager.InsertRefPlane(8 + flip, off * m, 0, 0, 0, 0)
    if p is None:
        raise SystemExit('offset plane failed ' + name)
    p.Name = name
    return p


# --------------------------------------------------------------------------------------------------------------- sketch
class Sk:
    """with Sk(d, plane, name) as s: s.poly([...3D model points...]); s.circle(c3d, r)"""

    def __init__(self, d, pl, name):
        self.d, self.pl, self.name = d, pl, name

    def __enter__(self):
        d = self.d
        d.ClearSelection2(True)
        self.pl.Select2(False, 0)
        d.SketchManager.InsertSketch(True)
        sk = d.GetActiveSketch2
        self.T = sk.ModelToSketchTransform.ArrayData
        d.SketchManager.AddToDB = True
        return self

    def p(self, q):
        T = self.T
        x, y, z = q[0] * m, q[1] * m, q[2] * m
        return (x * T[0] + y * T[3] + z * T[6] + T[9], x * T[1] + y * T[4] + z * T[7] + T[10])

    def normal(self):
        T = self.T
        return np.array([T[2], T[5], T[8]])

    def line(self, a, b):
        a, b = self.p(a), self.p(b)
        return self.d.SketchManager.CreateLine(a[0], a[1], 0, b[0], b[1], 0)

    def cline(self, a, b):
        a, b = self.p(a), self.p(b)
        return self.d.SketchManager.CreateCenterLine(a[0], a[1], 0, b[0], b[1], 0)

    def poly(self, pts, closed=True):
        P = [self.p(q) for q in pts]
        for a, b in zip(P, (P[1:] + P[:1]) if closed else P[1:]):
            self.d.SketchManager.CreateLine(a[0], a[1], 0, b[0], b[1], 0)

    def circle(self, c, r):
        a = self.p(c)
        return self.d.SketchManager.CreateCircleByRadius(a[0], a[1], 0, r * m)

    def arc(self, c, p0, p1, direction):
        """direction +1 counter-clockwise in the SKETCH frame."""
        a, b, e = self.p(c), self.p(p0), self.p(p1)
        return self.d.SketchManager.CreateArc(a[0], a[1], 0, b[0], b[1], 0, e[0], e[1], 0, direction)

    def arc3(self, p0, pm, p1):
        """Arc through three model points."""
        a, b, c = self.p(p0), self.p(pm), self.p(p1)
        return self.d.SketchManager.Create3PointArc(a[0], a[1], 0, c[0], c[1], 0, b[0], b[1], 0)

    def spline(self, pts, closed=True):
        arr = []
        for q in list(pts) + ([pts[0]] if closed else []):
            u, v = self.p(q)
            arr += [u, v, 0.0]
        s = self.d.SketchManager.CreateSpline2(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, arr), True)
        if s is None:
            raise SystemExit('spline failed ' + self.name)
        return s

    def rpoly(self, pts, radii):
        """Closed polygon of model points with a tangent arc of radii[i] at each corner (0 = sharp). Points must lie in
        the sketch plane; arcs are built in sketch 2D."""
        P = [np.array(self.p(q)) for q in pts]
        n = len(P)
        R = [r * m for r in radii]
        ends = []
        for i in range(n):
            a, b, c = P[i - 1], P[i], P[(i + 1) % n]
            if R[i] <= 0:
                ends.append((b, b, None))
                continue
            u1 = (a - b) / np.linalg.norm(a - b)
            u2 = (c - b) / np.linalg.norm(c - b)
            ang = math.acos(max(-1.0, min(1.0, float(u1 @ u2))))
            t = R[i] / math.tan(ang / 2)
            p1, p2 = b + u1 * t, b + u2 * t
            bis = (u1 + u2) / np.linalg.norm(u1 + u2)
            cen = b + bis * (R[i] / math.sin(ang / 2))
            ends.append((p1, p2, cen))
        sm = self.d.SketchManager
        for i in range(n):
            p1, p2, cen = ends[i]
            if cen is not None:
                cr = (p1[0] - cen[0]) * (p2[1] - cen[1]) - (p1[1] - cen[1]) * (p2[0] - cen[0])
                sm.CreateArc(cen[0], cen[1], 0, p1[0], p1[1], 0, p2[0], p2[1], 0, 1 if cr > 0 else -1)
            q1 = ends[i][1]
            q2 = ends[(i + 1) % n][0]
            if np.linalg.norm(q2 - q1) > 1e-7:
                sm.CreateLine(q1[0], q1[1], 0, q2[0], q2[1], 0)

    def slot(self, a, b, w):
        """Stadium from model point a to b (centres of the end arcs), width w."""
        A, B = np.array(self.p(a)), np.array(self.p(b))
        dvec = (B - A) / np.linalg.norm(B - A)
        nv = np.array([-dvec[1], dvec[0]]) * (w / 2 * m)
        sm = self.d.SketchManager
        sm.CreateLine(*(A + nv), 0, *(B + nv), 0)
        sm.CreateLine(*(A - nv), 0, *(B - nv), 0)
        sm.CreateArc(B[0], B[1], 0, *(B + nv), 0, *(B - nv), 0, -1)
        sm.CreateArc(A[0], A[1], 0, *(A - nv), 0, *(A + nv), 0, -1)

    def __exit__(self, *a):
        self.d.SketchManager.AddToDB = False
        self.d.InsertSketch2(True)
        s = self.d.FeatureByPositionReverse(0)
        s.Name = self.name + '_SK'
        self.feat = s


def rect_pts(c, u, v, w, h):
    """Corners of a w (along u) x h (along v) rectangle centred at model point c."""
    c, u, v = np.array(c, float), np.array(u, float), np.array(v, float)
    u /= np.linalg.norm(u)
    v /= np.linalg.norm(v)
    return [tuple(c + su * u * w / 2 + sv * v * h / 2) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def seg_rect(p0, p1, v, h, ext0=0.0, ext1=0.0, off=0.0):
    """Rectangle from p0 to p1 (extended), thickness h along v (perpendicular to p1-p0, in the sketch plane), shifted off
    along v."""
    p0, p1, v = np.array(p0, float), np.array(p1, float), np.array(v, float)
    dvec = (p1 - p0) / np.linalg.norm(p1 - p0)
    v = v - dvec * (v @ dvec)
    v /= np.linalg.norm(v)
    a, b = p0 - dvec * ext0 + v * off, p1 + dvec * ext1 + v * off
    return [tuple(a - v * h / 2), tuple(b - v * h / 2), tuple(b + v * h / 2), tuple(a + v * h / 2)]


# ------------------------------------------------------------------------------------------------------------- features
def _facebox(f):
    lo = np.array([1e9] * 3)
    hi = -lo
    for fc in (f.GetFaces or []):
        b = fc.GetBox
        lo = np.minimum(lo, np.array(b[:3]) * 1e3)
        hi = np.maximum(hi, np.array(b[3:]) * 1e3)
    return lo, hi


def extrude(d, sk, name, depth, direction, cut=False, mode=BLIND, merge=True, lo=0.5, scope=None):
    """Extrude (or cut) sketch feature sk by depth (mm) toward model direction 'direction' (a 3-vector).
    mode MID: depth total, centred on the plane (direction ignored). THRU_ALL: through all on the 'direction' side."""
    fm = d.FeatureManager
    dirv = np.array(direction, float)
    if mode == MID:
        tries = (False,)
    else:
        T0 = sk.GetSpecificFeature2.ModelToSketchTransform.ArrayData
        nrm = np.array([T0[2], T0[5], T0[8]])
        first = bool(float(nrm @ dirv) < 0) != bool(cut)
        tries = (first, not first)
    for rev in tries:
        v0, m0 = vol_com(d)
        d.ClearSelection2(True)
        sk.Select2(False, 0)
        if cut:
            f = fm.FeatureCut4(True, False, rev, mode, 0, abs(depth) * m, abs(depth) * m, False, False, False, False, 0, 0,
                               False, False, False, False, False, False, True, False, False, False, 0, 0, False, False)
        else:
            f = fm.FeatureExtrusion3(True, False, rev, mode, 0, abs(depth) * m, abs(depth) * m, False, False, False, False, 0, 0,
                                     False, False, False, False, merge, False, True, 0, 0, False)
        if f is None:
            log(f'   {name} rev={rev}: no feature')
            continue
        d.ForceRebuild3(False)
        v1, m1 = vol_com(d)
        dv = (v0 - v1) if cut else (v1 - v0)
        ok = dv > lo or (not merge and not cut)
        if ok and mode != MID and abs(dv) > 1e-6:
            # centroid of the added or removed material must lie on the 'direction' side of the sketch plane
            cen = (m0 - m1) / (v0 - v1)
            T = sk.GetSpecificFeature2.ModelToSketchTransform.ArrayData
            R = np.array(T[:9]).reshape(3, 3)
            o = -np.array(T[9:12]) @ np.linalg.inv(R) * 1e3
            ok = float((cen - o) @ dirv) > 0
        if ok:
            f.Name = name
            log(f'  {name}: {"cut" if cut else "added"} {dv:.0f} mm3')
            return f
        d.EditUndo2(1)
        d.ForceRebuild3(False)
    raise SystemExit(name + ' failed')


def revolve(d, sk, name, cut=False, angle=360.0, lo=0.5):
    """Revolve a closed sketch that also holds one centreline (the axis)."""
    v0 = vol(d)
    d.ClearSelection2(True)
    sk.Select2(False, 0)
    f = d.FeatureManager.FeatureRevolve2(True, True, False, cut, False, False, 0, 0, math.radians(angle), 0, False, False,
                                         0, 0, 0, 0, 0, True, False, True)
    d.ForceRebuild3(False)
    dv = (v0 - vol(d)) if cut else (vol(d) - v0)
    if f is None or dv < lo:
        raise SystemExit(f'{name} revolve failed (dv {dv:.1f})')
    f.Name = name
    log(f'  {name}: {"cut" if cut else "added"} {dv:.0f} mm3')
    return f


def edges_where(d, test, pair=None):
    """Edges of all bodies whose start, end and mid points pass test(p) (model mm)."""
    out = []
    for b in (d.GetBodies2(0, True) or []):
        es = b.GetEdges
        for e in ((es() if inspect.ismethod(es) else es) or []):
            cp = e.GetCurveParams3
            cp = cp() if inspect.ismethod(cp) else cp
            p0 = np.array(cp.StartPoint[:3]) * 1e3
            p1 = np.array(cp.EndPoint[:3]) * 1e3
            pm = (p0 + p1) / 2 if np.linalg.norm(p1 - p0) > 1e-6 else p0
            if test(p0) and test(p1) and test(pm) and (pair is None or pair(p0, p1)):
                out.append(e)
    return out


def fillet(d, edges, radii, name):
    """Constant-radius fillet on edges; tries the radii in turn, keeps the first that builds."""
    if not edges:
        log(f'  {name}: no edges')
        return None
    for r in radii:
        d.ClearSelection2(True)
        for e in edges:
            e.Select4(True, NUL)
        f = d.FeatureManager.FeatureFillet3(195, r * m, 0, 0, 0, 0, 0, NUL, NUL, NUL, NUL, NUL, NUL, NUL)
        if f is not None:
            d.ForceRebuild3(False)
            f.Name = name
            log(f'  {name}: R{r} on {len(edges)} edges')
            return r
    log(f'  {name}: no fillet built on {len(edges)} edges')
    return None


def fillet_each(d, edges, radii, name):
    """Try the edges one at a time (a fillet that fails on one edge does not block the others)."""
    done = 0
    for i, e in enumerate(edges):
        for r in radii:
            d.ClearSelection2(True)
            e.Select4(False, NUL)
            f = d.FeatureManager.FeatureFillet3(195, r * m, 0, 0, 0, 0, 0, NUL, NUL, NUL, NUL, NUL, NUL, NUL)
            if f is not None:
                f.Name = f'{name}_{i}'
                done += 1
                break
    d.ForceRebuild3(False)
    log(f'  {name}: {done}/{len(edges)} edges filleted')
    return done


def add_global(d, name, value, unit=''):
    em = d.GetEquationMgr
    for i in range(em.GetCount):
        if em.Equation(i).startswith(f'"{name}"'):
            em.Equation(i, f'"{name}" = {value}{unit}')
            return i
    return em.Add2(-1, f'"{name}" = {value}{unit}', True)


def link_dim(d, dimname, expr):
    em = d.GetEquationMgr
    i = em.Add2(-1, f'"{dimname}" = {expr}', True)
    d.ForceRebuild3(False)
    return i


def set_material_petg(d):
    """Density for mass properties: solid PETG 1.27 g/cc (user-defined, no library material needed)."""
    ext = d.Extension
    mp = ext.CreateMassProperty
    return mp


def mass_g(d):
    return vol(d) * 1.27e-3


def stamp_props(d, props):
    cpm = d.Extension.CustomPropertyManager('')
    for k, v in props.items():
        cpm.Add3(k, 30, str(v), 2)


def sector(s, pt, ri, ro, a0, a1, rc=0.0):
    """Annular sector ri..ro, angles a0..a1 (deg), corners rounded rc; pt(r, a) gives the model point. ri = 0: a pie."""
    a0, a1 = min(a0, a1), max(a0, a1)
    am = (a0 + a1) / 2
    if rc <= 0 or ri <= 0:
        if ri > 0:
            s.arc3(pt(ro, a0), pt(ro, am), pt(ro, a1))
            s.arc3(pt(ri, a0), pt(ri, am), pt(ri, a1))
            s.line(pt(ri, a0), pt(ro, a0))
            s.line(pt(ri, a1), pt(ro, a1))
        else:
            s.arc3(pt(ro, a0), pt(ro, am), pt(ro, a1))
            s.line(pt(0, a0), pt(ro, a0))
            s.line(pt(0, a1), pt(ro, a1))
        return
    do = math.degrees(math.asin(rc / (ro - rc)))
    di = math.degrees(math.asin(rc / (ri + rc)))
    lo_o, lo_i = math.sqrt((ro - rc) ** 2 - rc ** 2), math.sqrt((ri + rc) ** 2 - rc ** 2)
    # outer arc between the corner tangent points
    s.arc3(pt(ro, a0 + do), pt(ro, am), pt(ro, a1 - do))
    s.arc3(pt(ri, a0 + di), pt(ri, am), pt(ri, a1 - di))
    for a, sg in ((a0, 1), (a1, -1)):
        s.line(pt(lo_i, a), pt(lo_o, a))
        # corner arcs: centre at radius ro-rc / ri+rc, angle a + sg*do / di
        co = pt(ro - rc, a + sg * do)
        ci = pt(ri + rc, a + sg * di)
        for c, rr, tp_arc, tp_line in ((co, ro - rc, pt(ro, a + sg * do), pt(lo_o, a)), (ci, ri + rc, pt(ri, a + sg * di), pt(lo_i, a))):
            # mid point of the corner arc: from the centre toward the corner
            c3, p1, p2 = np.array(c), np.array(tp_arc), np.array(tp_line)
            mvec = (p1 - c3) / np.linalg.norm(p1 - c3) + (p2 - c3) / np.linalg.norm(p2 - c3)
            mvec /= np.linalg.norm(mvec)
            s.arc3(tuple(p1), tuple(c3 + mvec * rc), tuple(p2))
