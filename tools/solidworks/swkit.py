"""Modelling helpers for scripted SolidWorks work: one job, one instance, every step checked.

    import sys
    sys.path.insert(0, r"J:\\code\\roark-wt\\<session>\\tools\\solidworks")
    from swkit import *

    with job() as j:                                   # own instance (RULES.md), closed on the way out
        d = new_part(j.sw, r"...\\cad\\_wip\\demo\\block.SLDPRT")
        with Sk(d, plane(d, 'Z', 5.0, 'BLOCK_P'), 'BLOCK') as s:
            s.rect((0, 0, 5.0), (40, 20, 5.0))
        extrude(d, s.feat, 'BLOCK', 10.0, mode=MID)    # raises unless the volume grew
        save(d)
        export(j.sw, d, r"...\\block.step")

How to use it, and why each helper is shaped the way it is: playbook/README.md. Everything here takes and returns
millimetres and degrees in the model frame; SolidWorks itself works in metres and radians, and the helpers convert.

The feature calls are the ones the left-arm build scripts proved on SolidWorks 2026 (cad/scripts/arm/swg.py and
organic_master.py on branch left-arm-organic-r1). Windows only: needs pywin32, psutil and numpy.
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import psutil
import pythoncom
from win32com.client import VARIANT

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sw_instance import launch  # noqa: E402

m = 1e-3
NUL = VARIANT(pythoncom.VT_DISPATCH, None)       # "no object" for an optional COM argument; plain None is refused
BASE = {'X': 'Right Plane', 'Y': 'Top Plane', 'Z': 'Front Plane'}       # the default plane normal to each model axis
BLIND, THRU_ALL, UP_TO_NEXT, MID = 0, 1, 2, 6      # swEndConditions_e
PART, ASSEMBLY = 1, 2                              # swDocumentTypes_e
MIN_FREE_GB = 8.0                                  # holly-pc rule: leave this much free after a launch (cad-workstation.md)


class Failed(RuntimeError):
    """A SolidWorks step did not do what was asked. The message names the step; nothing after it has run."""


def L(v=0):
    """A by-reference long, for the error and warning out-arguments: e = L(); f(..., e); e.value."""
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)


def call(o, name, *a):
    """Read o.name whether late binding exposes it as a property or as a method (it differs between calls and builds)."""
    v = getattr(o, name)
    return v(*a) if callable(v) else v


def dispatch_array(items):
    """A COM array of objects (faces, edges), for the calls that refuse a Python list (CreateContactSet)."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(items))


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def free_gb():
    return psutil.virtual_memory().available / 2 ** 30


class job:
    """with job() as j: one SolidWorks instance for one script, closed on the way out whatever happens.

    Refuses to start when the machine has less than min_free_gb free. j.sw is the SldWorks object, j.inst the
    sw_instance.Instance (j.inst.pid for claims.py), j.simulation() loads the Simulation add-in.
    """

    def __init__(self, min_free_gb=MIN_FREE_GB, visible=False):
        self.min_free_gb, self.visible = min_free_gb, visible
        self.inst = self.sw = None

    def __enter__(self):
        if free_gb() < self.min_free_gb:
            raise Failed(f'only {free_gb():.1f} GB free, under the {self.min_free_gb} GB floor: wait, do not launch')
        self.inst = launch(visible=self.visible)
        self.sw = self.inst.sw
        pin_export_prefs(self.sw)
        log('SolidWorks pid', self.inst.pid, 'free GB', round(free_gb(), 1))
        return self

    def simulation(self):
        return self.inst.load_simulation()

    def __exit__(self, *exc):
        log('closing pid', self.inst.pid, 'committed MB', self._private())
        self.inst.close()

    def _private(self):
        try:
            return self.inst.private_mb()
        except psutil.Error:
            return '?'


# ---- documents ---------------------------------------------------------------------------------------------------------

def pin_export_prefs(sw):
    """STL and STEP options are per-machine settings, not part of a part: set them so every machine exports alike.

    Binary STL in mm, quality Fine, kept in the model frame (no shift to positive space), STEP AP203 (cad.md section 9).
    """
    sw.SetUserPreferenceToggle(69, True)           # swSTLBinaryFormat
    sw.SetUserPreferenceToggle(71, True)           # swSTLDontTranslateToPositive
    sw.SetUserPreferenceIntegerValue(211, 0)       # swExportStlUnits = mm
    sw.SetUserPreferenceIntegerValue(78, 2)        # swSTLQuality = Fine
    sw.SetUserPreferenceIntegerValue(75, 203)      # swStepAP = AP203


def part_template(sw):
    """The part template: SolidWorks' default if one is set, else SW_PART_TEMPLATE, else the first installed .prtdot."""
    t = sw.GetUserPreferenceStringValue(8) or os.environ.get('SW_PART_TEMPLATE', '')      # 8 = swDefaultTemplatePart
    if t and os.path.exists(t):
        return t
    found = sorted(Path(r'C:\ProgramData\SOLIDWORKS').glob('SOLIDWORKS 20*/templates/**/*.prtdot'))
    if not found:
        raise Failed('no part template: set SW_PART_TEMPLATE to a .prtdot file')
    return str(found[-1])


def new_part(sw, path):
    """A new empty part in MMGS units, saved at path at once (an unsaved document is lost with the instance)."""
    sw.CloseAllDocuments(True)       # a failed earlier build leaves its part open, and NewDocument then throws
    d = sw.NewDocument(part_template(sw), 0, 0, 0)
    if d is None:
        raise Failed('NewDocument returned nothing')
    d.Extension.SetUserPreferenceInteger(263, 0, 5)      # swUnitSystem = MMGS, whatever the template says
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    save_as(d, path)
    return d


def open_doc(sw, path, kind=PART):
    """Open a part (or assembly) silently and make it the active document."""
    e, w = L(), L()
    d = sw.OpenDoc6(str(path), kind, 1, '', e, w)        # 1 = swOpenDocOptions_Silent
    if d is None:
        raise Failed(f'open failed: {path} errors {e.value} warnings {w.value}')
    sw.ActivateDoc3(d.GetTitle, False, 0, L())
    return d


def save(d):
    """Rebuild and save in place. Call it after every step that worked (RULES.md rule 5)."""
    d.ForceRebuild3(False)
    e, w = L(), L()
    if not d.Save3(1, e, w):                             # 1 = swSaveAsOptions_Silent
        raise Failed(f'save failed: {d.GetPathName} errors {e.value} warnings {w.value}')


def save_as(d, path):
    e, w = L(), L()
    ok = d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    if not ok or not os.path.exists(path) or os.path.getsize(path) == 0:
        raise Failed(f'save as failed: {path} errors {e.value} warnings {w.value}')


def export(sw, d, path):
    """Export the part to .step or .stl by its extension, with the pinned options, and check the file landed."""
    pin_export_prefs(sw)
    d.ForceRebuild3(False)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    save_as(d, path)
    log('exported', path, os.path.getsize(path), 'bytes')


def close(sw, d):
    sw.CloseDoc(d.GetTitle)


def import_step(sw, step, target):
    """Import a STEP file and save it as a native part or assembly at target (extension chosen by what came in)."""
    data = sw.GetImportFileData(str(step))
    e = L()
    d = sw.LoadFile4(str(step), 'r', data, e)
    if d is None:
        raise Failed(f'import failed: {step} error {e.value}')
    target = Path(target).with_suffix('.SLDASM' if d.GetType == ASSEMBLY else '.SLDPRT')
    save_as(d, target)
    return d, target


# ---- measuring: the check after every feature --------------------------------------------------------------------------

def solid_bodies(d):
    return list(d.GetBodies2(0, True) or [])             # 0 = swSolidBody, visible only


def volume(d):
    """Total solid volume in mm3."""
    return sum(b.GetMassProperties(1000.0)[3] for b in solid_bodies(d)) * 1e9


def bodies(d):
    """[(name, volume mm3, [x0, y0, z0, x1, y1, z1] mm)] for every solid body."""
    return [(b.Name, round(b.GetMassProperties(1000.0)[3] * 1e9, 2), [round(v * 1e3, 3) for v in b.GetBodyBox()])
            for b in solid_bodies(d)]


def bbox(d):
    """[x0, y0, z0, x1, y1, z1] in mm over all solid bodies."""
    bs = np.array([b[2] for b in bodies(d)])
    return [float(v) for v in bs[:, :3].min(axis=0)] + [float(v) for v in bs[:, 3:].max(axis=0)]


def expect(what, got, want, tol):
    """Stop unless got is within tol (relative when 0 < tol < 1 and want != 0, else absolute) of want."""
    err = abs(got - want)
    lim = tol * abs(want) if 0 < tol < 1 and want else tol
    if err > lim:
        raise Failed(f'{what}: got {got:.4f}, expected {want:.4f} (off by {err:.4f}, allowed {lim:.4f})')
    log(f'ok {what}: {got:.4f} (expected {want:.4f})')


def feature_errors(d):
    """[(feature name, error code)] for features that failed to rebuild or carry a warning. Empty means a clean tree.

    GetErrorCode2 needs its by-reference "is a warning" flag: without it the call raises "Parameter not optional" for
    every feature, which an earlier version of this helper swallowed and so always reported a clean tree (2026-11-12).
    A cut whose sketch no longer meets the body reports 71.
    """
    out = []
    f = d.FirstFeature
    while f is not None:
        code = f.GetErrorCode2(VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False))
        code = code[0] if isinstance(code, tuple) else code
        if code:
            out.append((f.Name, int(code)))
        f = f.GetNextFeature
    return out


# ---- planes and sketches -----------------------------------------------------------------------------------------------

def plane(d, axis, off, name):
    """The plane normal to model axis 'X', 'Y' or 'Z' at that coordinate (mm). Offset 0 returns the base plane."""
    base = d.FeatureByName(BASE[axis])
    if base is None:
        raise Failed(f'no "{BASE[axis]}" in this part (a template in another language renames the base planes)')
    if abs(off) < 1e-9:
        return base
    d.ClearSelection2(True)
    base.Select2(False, 0)
    p = d.FeatureManager.InsertRefPlane(8 + (256 if off < 0 else 0), abs(off) * m, 0, 0, 0, 0)      # 8 distance, 256 flip
    if p is None:
        raise Failed('plane failed: ' + name)
    p.Name = name
    return p


class Sk:
    """with Sk(d, plane, name) as s: draw with 3D model points in mm; they are mapped into the sketch for you.

    The points go through the sketch's own ModelToSketchTransform, so it never matters which way a plane's sketch axes
    point or whether the plane was flipped. A point that does not lie on the sketch plane raises: that is the plane at
    the wrong offset, caught before it becomes a feature in the wrong place. s.feat is the finished sketch.
    """

    def __init__(self, d, pl, name):
        self.d, self.pl, self.name = d, pl, name

    def __enter__(self):
        d = self.d
        d.ClearSelection2(True)
        self.pl.Select2(False, 0)
        d.SketchManager.InsertSketch(True)
        sk = d.GetActiveSketch2
        if sk is None:
            raise Failed('sketch did not open: ' + self.name)
        self.T = sk.ModelToSketchTransform.ArrayData
        d.SketchManager.AddToDB = True       # straight to the database: no snapping or inferred relations to move points
        return self

    def p(self, q):
        T = self.T
        x, y, z = q[0] * m, q[1] * m, q[2] * m
        w = x * T[2] + y * T[5] + z * T[8] + T[11]
        if abs(w) > 1e-6:
            raise Failed(f'{self.name}: point {tuple(q)} is {abs(w) / m:.4f} mm off the sketch plane')
        return x * T[0] + y * T[3] + z * T[6] + T[9], x * T[1] + y * T[4] + z * T[7] + T[10]

    def poly(self, pts, closed=True):
        P = [self.p(q) for q in pts]
        for a, b in zip(P, (P[1:] + P[:1]) if closed else P[1:]):
            if self.d.SketchManager.CreateLine(a[0], a[1], 0, b[0], b[1], 0) is None:
                raise Failed(f'{self.name}: line not drawn (two points closer than 1e-5 mm?)')

    def rect(self, a, b):
        """Axis-aligned rectangle between opposite corners a and b, which must lie on the sketch plane."""
        k = [i for i in range(3) if abs(a[i] - b[i]) > 1e-9]
        if len(k) != 2:
            raise Failed(f'{self.name}: rect corners must differ in exactly two coordinates')
        c, e = list(a), list(a)
        c[k[0]], e[k[1]] = b[k[0]], b[k[1]]
        self.poly([a, c, b, e])

    def circle(self, c, r):
        a = self.p(c)
        if self.d.SketchManager.CreateCircleByRadius(a[0], a[1], 0, r * m) is None:
            raise Failed(f'{self.name}: circle not drawn')

    def arc(self, c, p0, p1, direction):
        """Arc about centre c from p0 to p1; direction +1 or -1 in the sketch's own sense: check the result's volume."""
        a, b, e = self.p(c), self.p(p0), self.p(p1)
        self.d.SketchManager.CreateArc(a[0], a[1], 0, b[0], b[1], 0, e[0], e[1], 0, direction)

    def spline(self, pts, closed=True):
        arr = []
        for q in list(pts) + (list(pts[:1]) if closed else []):
            u, v = self.p(q)
            arr += [u, v, 0.0]
        if self.d.SketchManager.CreateSpline2(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, arr), True) is None:
            raise Failed(f'{self.name}: spline not drawn')

    def centerline(self, a, b):
        """The axis for a revolve."""
        p, q = self.p(a), self.p(b)
        self.d.SketchManager.CreateCenterLine(p[0], p[1], 0, q[0], q[1], 0)

    def __exit__(self, et, ev, tb):
        self.d.SketchManager.AddToDB = False
        self.d.InsertSketch2(True)
        if et is None:
            self.feat = self.d.FeatureByPositionReverse(0)
            self.feat.Name = self.name + '_SK'


# ---- features ----------------------------------------------------------------------------------------------------------

def extrude(d, sk, name, depth, cut=False, mode=BLIND, want=None, min_dv=1.0, expect_dv=None):
    """Extrude a sketch (cut=True removes material) and check what it did.

    mode MID extrudes depth in total, half each side of the sketch plane: nothing to get backwards, so put the sketch
    plane at the middle of the feature whenever you can. BLIND goes depth one way; THRU_ALL cuts through both sides.
    For BLIND and UP_TO_NEXT both directions are tried, and want = (axis index 0/1/2, sign, plane coordinate mm) keeps
    the one whose new faces lie on that side of the sketch plane.
    Raises unless the volume changed by more than min_dv mm3 the right way, and, when expect_dv is given, by that
    amount within 1 %.
    """
    fm = d.FeatureManager
    dep = abs(depth) * m
    for rev in ((False,) if mode == MID else (False, True)):
        v0 = volume(d)
        d.ClearSelection2(True)
        sk.Select2(False, 0)
        if cut:
            f = fm.FeatureCut4(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False, False, False,
                               False, False, False, True, False, False, False, 0, 0, False, False)
        else:
            f = fm.FeatureExtrusion3(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False, False,
                                     False, False, True, False, True, 0, 0, False)
            if f is None:      # auto-select merge fails on some multi-body states; feature scope without it works
                d.ClearSelection2(True)
                sk.Select2(False, 0)
                f = fm.FeatureExtrusion3(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False,
                                         False, False, False, True, True, False, 0, 0, False)
        if f is None:
            continue
        d.ForceRebuild3(False)
        dv = (v0 - volume(d)) if cut else (volume(d) - v0)
        ok = dv > min_dv
        if ok and want is not None:
            ax, sign, c0 = want
            vals = []
            for fc in (call(f, 'GetFaces') or []):
                b = call(fc, 'GetBox')
                vals += [b[ax] * 1e3, b[ax + 3] * 1e3]
            ok = bool(vals) and (sum(vals) / len(vals) - c0) * sign > 0
        if ok:
            if expect_dv is not None:
                expect(name + ' volume change', dv, expect_dv, 0.01)
            f.Name = name
            log(f'{name}: {"cut" if cut else "added"} {dv:.2f} mm3')
            return f
        d.EditUndo2(1)
    raise Failed(f'{name}: no {"cut" if cut else "extrude"} changed the volume the right way '
                 '(open sketch? sketch off the body? wrong side?)')


def revolve(d, sk, name, cut=False, angle=360.0, mid=False, min_dv=1.0, expect_dv=None):
    """Revolve a closed profile about the centreline drawn in the same sketch (Sk.centerline)."""
    v0 = volume(d)
    d.ClearSelection2(True)
    sk.Select2(False, 0)
    f = d.FeatureManager.FeatureRevolve2(True, True, False, cut, False, False, 6 if mid else 0, 0, math.radians(angle),
                                         0, False, False, 0, 0, 0, 0, 0, True, False, True)
    d.ForceRebuild3(False)
    dv = (v0 - volume(d)) if cut else (volume(d) - v0)
    if f is None or dv < min_dv:
        raise Failed(f'{name}: revolve failed (profile open, or crossing its centreline?)')
    if expect_dv is not None:
        expect(name + ' volume change', dv, expect_dv, 0.01)
    f.Name = name
    log(f'{name}: {"cut" if cut else "added"} {dv:.2f} mm3')
    return f


def loft(d, sketches, name):
    """Loft through closed section sketches, in order. Tries with and without merging into the existing body."""
    v0 = volume(d)
    for merge in (True, False):
        d.ClearSelection2(True)
        for k in sketches:
            k.Select2(True, 1)
        f = d.FeatureManager.InsertProtrusionBlend2(False, True, False, 1.0, 0, 0, 1.0, 1.0, True, True, False, 0, 0, 0,
                                                    True, merge, merge, 0)
        if f is not None:
            d.ForceRebuild3(False)
            f.Name = name
            log(f'{name}: added {volume(d) - v0:.2f} mm3 (merge {merge})')
            return f
    raise Failed(name + ': loft failed (sections must be closed, and their start points roughly in line)')


def shell(d, open_face_points, t, name):
    """Shell to wall thickness t mm, removing the faces at the given 3D points (each must lie on exactly one face).

    The faces are found by geometry and selected as objects: SelectByID2 by coordinates found nothing on a hidden
    instance (2026-11-12). With no points the part is hollowed with no opening.
    """
    hit = [pick(d, at=p) for p in open_face_points]
    if any(len(h) != 1 for h in hit):
        raise Failed(f'{name}: each point must lie on exactly one face; faces found {[len(h) for h in hit]} at '
                     f'{list(open_face_points)} (a point on an edge lies on two)')
    d.ClearSelection2(True)
    for h in hit:
        if not h[0].Select4(True, NUL):
            raise Failed(f'{name}: face not selected')
    v0 = volume(d)
    d.InsertFeatureShell(t * m, False)
    d.ForceRebuild3(False)
    f = d.FeatureByPositionReverse(0)
    if f is None or f.GetTypeName2 != 'Shell' or v0 - volume(d) < 1.0:
        raise Failed(f'{name}: shell failed (wall thicker than a local radius or a thin region?)')
    f.Name = name
    log(f'{name}: {t} mm wall, volume {volume(d):.1f} mm3')
    return f


def edges_where(d, test):
    """Edges whose start, middle and end points (mm) all pass test(p). Select by where an edge IS, never by its name."""
    out = []
    for b in solid_bodies(d):
        for e in (call(b, 'GetEdges') or []):
            cp = e.GetCurveParams3
            mid = e.GetCurve.Evaluate2((cp.UMinValue + cp.UMaxValue) / 2, 0)
            pts = [np.array(cp.StartPoint[:3]) * 1e3, np.array(list(mid)[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3]
            if all(test(p) for p in pts):
                out.append(e)
    return out


def fillet(d, edges, radii, name):
    """Round the edges with the first radius in radii (mm) that builds; returns that radius, or None if none did.

    Edge objects go stale once any feature is added: find them (edges_where) straight before this call.
    """
    if not edges:
        raise Failed(name + ': no edges to round (the edge test matched nothing)')
    for r in radii:
        v0 = volume(d)
        d.ClearSelection2(True)
        for e in edges:
            e.Select4(True, NUL)
        f = d.FeatureManager.FeatureFillet3(3, r * m, 0, 0, 0, 0, 0, NUL, NUL, NUL, NUL, NUL, NUL, NUL)
        if f is not None:
            d.ForceRebuild3(False)
            f.Name = name
            log(f'{name}: R{r} on {len(edges)} edges, volume change {volume(d) - v0:+.2f} mm3')
            return r
    log(f'{name}: no round built on {len(edges)} edges at {tuple(radii)}')
    return None


def chamfer(d, edges, width, name, angle=45.0):
    if not edges:
        raise Failed(name + ': no edges to chamfer')
    d.ClearSelection2(True)
    for e in edges:
        e.Select4(True, NUL)
    f = d.FeatureManager.InsertFeatureChamfer(0, 1, width * m, math.radians(angle), 0, 0, 0, 0)
    d.ForceRebuild3(False)
    if f is None:
        raise Failed(name + ': chamfer failed')
    f.Name = name
    return f


def cut_half_space(d, axis, at, keep_sign, name, span=400.0):
    """Remove everything on the far side of the plane axis = at; keep_sign +1 keeps the side with larger coordinates."""
    c = at - keep_sign * span / 2
    i = 'XYZ'.index(axis)
    a, b = [-span] * 3, [span] * 3
    a[i] = b[i] = c
    with Sk(d, plane(d, axis, c, name + '_P'), name) as s:
        s.rect(a, b)
    return extrude(d, s.feat, name, span, cut=True, mode=MID)


def insert_body(d, part_path):
    """Bring another part's solid in as an extra body, at the same coordinates (multi-body models for contact FEA).

    The body stays separate even where it overlaps one already there (measured 2026-11-12), so nothing here tells you
    about an overlap: check for it yourself. The part must hold exactly one solid body.
    """
    n0 = len(solid_bodies(d))
    f = d.InsertPart3(str(part_path), 1, '')       # 1 = swInsertPartImportSolids
    d.ForceRebuild3(False)
    if f is None or len(solid_bodies(d)) != n0 + 1:
        raise Failed(f'{part_path} did not come in as its own body (bodies {bodies(d)})')
    return f


def delete_body(d, name):
    d.ClearSelection2(True)
    if not d.Extension.SelectByID2(name, 'SOLIDBODY', 0, 0, 0, False, 0, NUL, 0):
        raise Failed('no body ' + name)
    f = d.FeatureManager.InsertDeleteBody2(False)
    d.ForceRebuild3(False)
    return f


def single_body(d, crumb_mm3=0.2):
    """Delete crumbs under crumb_mm3 and stop unless exactly one solid body is left: the state every print part must be in."""
    for b in bodies(d):
        if b[1] < crumb_mm3:
            delete_body(d, b[0])
    if len(bodies(d)) != 1:
        raise Failed(f'expected one body, got {bodies(d)}')


# ---- faces: pick by geometry -------------------------------------------------------------------------------------------

def faces(d):
    return [f for b in solid_bodies(d) for f in (call(b, 'GetFaces') or [])]


def face_info(f):
    """dict(kind 'cyl' | 'plane' | 'other', r mm or None, normal or None, box [lo xyz, hi xyz] mm, area mm2)."""
    s = f.GetSurface
    x = [v * 1e3 for v in call(f, 'GetBox')]
    box = [min(x[i], x[i + 3]) for i in range(3)] + [max(x[i], x[i + 3]) for i in range(3)]
    kind, r, n = 'other', None, None
    if s.IsCylinder:
        kind, r = 'cyl', s.CylinderParams[6] * 1e3
    elif s.IsPlane:
        kind, n = 'plane', [round(v, 4) for v in f.Normal]
    return dict(kind=kind, r=r, normal=n, box=box, area=call(f, 'GetArea') * 1e6)


def pick(d, kind=None, r=None, inside=None, normal=None, at=None, area=None, tol=0.02):
    """Faces matching every given filter. Stop and print list_faces(d) if a pick returns the wrong count.

    kind 'cyl' or 'plane'; r: cylinder radius mm (within tol); inside: [x0, y0, z0, x1, y1, z1] the face's box must lie
    within; normal: (nx, ny, nz) of a planar face (within 0.01); at: a point (mm) that must lie on the face (0.05 mm);
    area: mm2, within 5 %.
    """
    out = []
    for f in faces(d):
        i = face_info(f)
        if kind and i['kind'] != kind:
            continue
        if r is not None and (i['r'] is None or abs(i['r'] - r) > tol):
            continue
        if inside is not None and not all(i['box'][k] >= inside[k] - tol and i['box'][k + 3] <= inside[k + 3] + tol for k in range(3)):
            continue
        if normal is not None and (i['normal'] is None or max(abs(a - b) for a, b in zip(i['normal'], normal)) > 0.01):
            continue
        if area is not None and abs(i['area'] - area) > 0.05 * area:
            continue
        if at is not None:
            q = f.GetClosestPointOn(at[0] * m, at[1] * m, at[2] * m)
            if q is None or math.dist([v * 1e3 for v in list(q)[:3]], at) > 0.05:
                continue
        out.append(f)
    return out


def list_faces(d, limit=200):
    """Print every face's kind, radius or normal, area and box: how to find out what a pick should ask for."""
    for k, f in enumerate(faces(d)[:limit]):
        i = face_info(f)
        print(k, i['kind'], 'r' if i['r'] is not None else 'n', round(i['r'], 3) if i['r'] is not None else i['normal'],
              'area', round(i['area'], 2), 'box', [round(v, 2) for v in i['box']], flush=True)
