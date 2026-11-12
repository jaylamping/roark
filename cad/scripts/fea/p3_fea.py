"""Linear static FEA of arm parts in SolidWorks Simulation, in this session's own instance (tools/solidworks/RULES.md).

    python cad/scripts/fea/p3_fea.py <case> [...]      # cases from CASES below
    python cad/scripts/fea/p3_fea.py faces <part> x0 x1 r0 r1

Other scripts import it and add their own PARTS and CASES (ua_fea.py, ua_fea_contact.py). Each case meshes, solves and
reports the peak von Mises away from fixtures (bulk SF) and the peak normal stress across each print layer direction (layer
SF, against half the bulk strength), plus optional regions. The row is appended to RUNS and the nodal stresses are saved as
<case>.npz next to the model, for fea_parts.py. Set ARM_SW_DIR to keep an FEA instance apart from the modelling one.

The first cases are the original one-piece upper arm and forearm studies (rev C); their models are not in the repo.
"""
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'arm'))
from sk import *        # noqa: E402,F403  pythoncom, VARIANT, L, NUL, app, session, W

CAD = Path(__file__).resolve().parents[2]
F = Path(os.environ.get('ARM_FEA_DIR', CAD / '_sim' / 'upper-arm'))      # models, .npz and the run log (gitignored)
RUNS = F / 'fea_runs.json'
PARTS = {'arm': F / 'UA2_ARM.SLDPRT', 'carrier': F / 'UA2_CARRIER.SLDPRT', 'fork': F / 'marengo_forearm_left.SLDPRT', 'fork_stop': F / 'fork_stop.SLDPRT', 'carrier_v1': F / 'carrier_v1.SLDPRT', 'carrier_v5': F / 'carrier_v5.SLDPRT', 'carrier_v6': F / 'carrier_v6.SLDPRT', 'carrier_v2': F / 'carrier_v2.SLDPRT', 'carrier_v3': F / 'carrier_v3.SLDPRT', 'fork_stop2': F / 'fork_stop2.SLDPRT', 'carrier_v4': F / 'carrier_v4.SLDPRT', 'distal': F / 'marengo_forearm_distal_left.SLDPRT'}
I = lambda v=0: VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)
CY, CZ = 209.860668, 5.985875
EX, NU, YIELD, LAYER, RHO = 1.9e9, 0.38, 45.0, 0.5, 1190.0
GOLD = (170.49, 209.861, 5.986)


def cyl(r, box):
    return ('cyl', r, box)


def pl(point, area=None):
    return ('plane', point, area)


ARM_FIX = [('fixed', cyl(3.0, [150, 290, -30, 195, 321, 40]))]
ARM_HOLES = cyl(2.5, [151, 170, -50, 166, 250, 60])
FK_FIX = [('fixed', cyl(2.25, [194, 195, -12, 207, 225, 24])), ('hinge', cyl(20.0, [141, 180, -25, 151, 240, 36]))]
FK_END = cyl(1.7, [140, 62, -20, 200, 67, 32])
FK_END_PT = (170.49, 20.0, 5.986)
arm = lambda f, m: dict(part='arm', fix=ARM_FIX, remote=(ARM_HOLES, GOLD, f, m))
fork = lambda f, m: dict(part='fork', fix=FK_FIX, remote=(FK_END, FK_END_PT, f, m))
CASES = {
    'LC1A': arm((0, 0, 300), (-17, 0, 0)),
    'LC1B': arm((0, 0, -300), (17, 0, 0)),
    'LC1C': arm((300, 0, 0), (-17, 0, 0)),
    'LC2': arm((0, 0, 0), (0, 17, 0)),
    'LC1A_fine': dict(arm((0, 0, 300), (-17, 0, 0)), el=2.0, ctrl=[(ARM_HOLES, 0.8), (ARM_FIX[0][1], 0.8)]),
    'fore': fork((0, 0, 100), (0, 0, 0)),
    'twist': fork((100, 0, 0), (0, 14, 0)),
    'twist_fine': dict(fork((100, 0, 0), (0, 14, 0)), el=2.0, ctrl=[(FK_END, 0.8), (FK_FIX[0][1], 0.8)]),
}
# stop load: 34 N.m at r 38.25, 889 N. Everything is linear, so 17 N.m is half of each stress.
SLEEVES = cyl(2.5, [139, 165, -45, 152, 255, 55])
FINGER = {'finger_root': [139, 165, 10, 146, 200, 50]}


def wall(th):
    return pl((142.5, CY - 38.25 * math.cos(math.radians(th)), CZ + 38.25 * math.sin(math.radians(th))), 30.0)


def patch(th):
    return pl((142.25, CY - 38.25 * math.cos(math.radians(th)), CZ + 38.25 * math.sin(math.radians(th))), 22.75)


def box_at(th):
    y, z = CY - 38.25 * math.cos(math.radians(th)), CZ + 38.25 * math.sin(math.radians(th))
    return [139, y - 11, z - 11, 146, y + 11, z + 11]


for name, th in (('carrier_stop_0', 23.0), ('carrier_stop_133', 196.0)):
    CASES[name] = dict(part='carrier', fix=[('fixed', SLEEVES)], forces=[(wall(th), 889.0, None)], el=2.0, ctrl=[(wall(th), 0.8), (SLEEVES, 0.8)], regions={'wall': box_at(th)})
# hand load that gives 34 N.m at the elbow: 120 N, 283 mm from the axis
HAND = (170.49, -73.1, 5.986)
for name, th, fz in (('fork_stop_0', 23.0, -120.0), ('fork_stop_133', 63.0, 120.0)):
    CASES[name] = dict(part='fork_stop', fix=[('fixed', patch(th)), ('hinge', FK_FIX[1][1])], remote=(FK_END, HAND, (0, 0, fz), (0, 0, 0)), el=2.0, ctrl=[(patch(th), 0.8)], regions=FINGER)
    CASES['finger_' + name[5:]] = dict(part='fork_stop', fix=FK_FIX, forces=[(patch(th), 889.0, None)], el=2.0, ctrl=[(patch(th), 0.8)], regions=FINGER)
for v in ('v1', 'v2', 'v3'):
    for th, tag in ((23.0, '0'), (196.0, '133')):
        CASES[f'carrier_{v}_{tag}'] = dict(part='carrier_' + v, fix=[('fixed', SLEEVES)], forces=[(pl(wall(th)[1], 41.0 if v != 'v1' else 26.0), 889.0, None)], el=2.0, ctrl=[(pl(wall(th)[1], 41.0 if v != 'v1' else 26.0), 0.6), (SLEEVES, 0.8)], regions={'wall': box_at(th)})
        CASES[f'carrier_{v}_{tag}_fine'] = dict(CASES[f'carrier_{v}_{tag}'], el=1.5, ctrl=[(pl(wall(th)[1], 41.0 if v != 'v1' else 26.0), 0.4), (SLEEVES, 0.6)])
def patch2(th):
    return pl((143.25, CY - 38.25 * math.cos(math.radians(th)), CZ + 38.25 * math.sin(math.radians(th))), 36.0)


for th, tag, fz in ((23.0, '0', -120.0), (63.0, '133', 120.0)):
    CASES['finger2_' + tag] = dict(part='fork_stop2', fix=FK_FIX, forces=[(patch2(th), 889.0, None)], el=2.0, ctrl=[(patch2(th), 0.6)], regions=FINGER)
    CASES['fork2_' + tag] = dict(part='fork_stop2', fix=[('fixed', patch2(th)), ('hinge', FK_FIX[1][1])], remote=(FK_END, HAND, (0, 0, fz), (0, 0, 0)), el=2.0, ctrl=[(patch2(th), 0.6)], regions=FINGER)
for th, tag in ((23.0, '0'), (187.0, '124')):
    sel = pl((143.25, CY - 38.25 * math.cos(math.radians(th)), CZ + 38.25 * math.sin(math.radians(th))), 41.0)
    CASES['stop4_' + tag] = dict(part='carrier_v4', fix=[('fixed', cyl(3.2, [139, 165, -45, 152, 255, 55]))], forces=[(sel, 889.0, None)], el=1.5, ctrl=[(sel, 0.4), (cyl(3.2, [139, 165, -45, 152, 255, 55]), 0.6)], regions={'wall': box_at(th)})
    # carrier as built: pilot in the ring takes radial load, three steel washers in Ø6.05 walls take the torque, all six or the nearest two
    PIL = ('hinge', cyl(32.9, [149, 165, -45, 152, 255, 55]))
    HOLES = {63.9: None, 103.9: None, 143.9: None, 223.9: None, 263.9: None, 303.9: None}
    def hole(a_):
        y_, z_ = CY - 36.5 * math.cos(math.radians(a_)), CZ + 36.5 * math.sin(math.radians(a_))
        return cyl(3.025, [147, y_ - 3.3, z_ - 3.3, 151, y_ + 3.3, z_ + 3.3])
    def land(a_):
        y_, z_ = CY - 36.5 * math.cos(math.radians(a_)), CZ + 36.5 * math.sin(math.radians(a_))
        return cyl(3.525, [147, y_ - 3.8, z_ - 3.8, 151, y_ + 3.8, z_ + 3.8])
    near_ = (63.9, 303.9) if th < 100 else (143.9, 223.9)
    CASES['stop6_' + tag + '_six'] = dict(part='carrier_v6', fix=[('fixed', cyl(3.025, [147, 165, -45, 151, 255, 55])), ('fixed', cyl(3.525, [147, 165, -45, 151, 255, 55])), PIL], forces=[(sel, 444.4, None)], el=1.0, ctrl=[(sel, 0.25), (cyl(3.025, [147, 165, -45, 151, 255, 55]), 0.4)], regions={'wall': box_at(th)})
    CASES['stop6_' + tag + '_two'] = dict(part='carrier_v6', fix=[('fixed', hole(a_)) for a_ in near_] + [('fixed', land(a_)) for a_ in near_] + [PIL], forces=[(sel, 444.4, None)], el=1.0, ctrl=[(sel, 0.25), (cyl(3.025, [147, 165, -45, 151, 255, 55]), 0.4)], regions={'wall': box_at(th)})
    for lab, el_, c0, c1 in (('', 1.5, 0.4, 0.6), ('_f', 1.0, 0.25, 0.4)):
        CASES['stop5_' + tag + lab] = dict(part='carrier_v5', fix=[('fixed', cyl(3.2, [139, 165, -45, 152, 255, 55]))], forces=[(sel, 444.4, None)], el=el_, ctrl=[(sel, c0), (cyl(3.2, [139, 165, -45, 152, 255, 55]), c1)], regions={'slot': [147, 225, -5, 152, 245, 17]})
# axial capture: 300 N along -X on the bearing seat, held by the six printed floors under the Ø7 washers and the pilot
POL = lambda r_, a_: (CY - r_ * math.cos(math.radians(a_)), CZ + r_ * math.sin(math.radians(a_)))
FLOORS = [pl((148.75,) + POL(36.5, a_), 10.3) for a_ in (63.9, 103.9, 143.9, 223.9, 263.9, 303.9)]
CASES['cap7_x'] = dict(part='carrier_v6', fix=[('fixed', f_) for f_ in FLOORS] + [('hinge', cyl(32.9, [149, 165, -45, 152, 255, 55]))], remote=(cyl(26.1, [141, 180, -25, 150.5, 240, 37]), GOLD, (-300, 0, 0), (0, 0, 0)), el=1.0, ctrl=[(f_, 0.3) for f_ in FLOORS])
# printed joint: no pilot, the carrier is held by its screws in Ø3.2 holes through the 2.65 web, all six or the nearest two
PJ = lambda a_: cyl(1.6, [148, POL(36.5, a_)[0] - 1.8, POL(36.5, a_)[1] - 1.8, 152, POL(36.5, a_)[0] + 1.8, POL(36.5, a_)[1] + 1.8])
for th_, tag_ in ((23.0, '0'), (187.0, '124')):
    sel_ = pl((143.25, CY - 38.25 * math.cos(math.radians(th_)), CZ + 38.25 * math.sin(math.radians(th_))), 41.0)
    near_ = (63.9, 303.9) if th_ < 100 else (143.9, 223.9)
    CASES[f'pj_{tag_}_six'] = dict(part='carrier_v6', fix=[('fixed', PJ(a_)) for a_ in (63.9, 103.9, 143.9, 223.9, 263.9, 303.9)], forces=[(sel_, 444.4, None)], el=1.0, ctrl=[(sel_, 0.25)], regions={'wall': box_at(th_)})
    CASES[f'pj_{tag_}_two'] = dict(part='carrier_v6', fix=[('fixed', PJ(a_)) for a_ in near_], forces=[(sel_, 444.4, None)], el=1.0, ctrl=[(sel_, 0.25)], regions={'wall': box_at(th_)})
# forearm at the 120 mm flange. Loads include the placeholder hand, pack and tube, 5.5 N. A placeholder estimate, not a design.
RIM = cyl(1.7, [140, 84, -20, 200, 92, 32])
HUB = cyl(1.7, [150, 84, -15, 190, 92, 25])
WR = cyl(1.7, [135, 14, -30, 205, 20, 42])
fk3 = lambda f, m_: dict(part='fork', fix=FK_FIX, remote=(RIM, FK_END_PT, f, m_))
CASES['fork3_fore'] = dict(fk3((0, 0, 105.5), (0, 0, 0)), el=2.0, ctrl=[(RIM, 0.8), (FK_FIX[0][1], 0.8)])
CASES['fork3_twist'] = dict(fk3((105.5, 0, 0), (0, 14, 0)), el=2.0, ctrl=[(RIM, 0.8), (FK_FIX[0][1], 0.8)])
for nm, f_, m_ in (('fore', (0, 0, 105.5), (0, 0, 0)), ('twist', (105.5, 0, 0), (0, 14, 0))):
    CASES['distal_' + nm] = dict(part='distal', fix=[('fixed', cyl(1.7, [150, 70, -15, 190, 90, 25]))], remote=(cyl(1.7, [135, 14, -30, 205, 20, 42]), FK_END_PT, f_, m_), el=2.0, ctrl=[(cyl(1.7, [150, 70, -15, 190, 90, 25]), 0.8)])
CASES['LC1C_fine'] = dict(CASES['LC1C'], el=2.0, ctrl=[(ARM_HOLES, 0.8), (ARM_FIX[0][1], 0.8)])
for k_ in ('LC1B', 'LC2'):
    CASES[k_ + '_fine'] = dict(CASES[k_], el=2.0, ctrl=[(ARM_HOLES, 0.8), (ARM_FIX[0][1], 0.8)])


def call(o, n, *a):
    v = getattr(o, n)
    return v(*a) if callable(v) else v


def faces_of(d):
    return [f for b in d.GetBodies2(0, True) for f in b.GetFaces()]


def info(f):
    s = f.GetSurface
    x = list(call(f, 'GetBox'))
    box = [x[i] * 1000 for i in range(6)]
    t = 'other'
    r = None
    n = None
    if s.IsCylinder:
        t = 'cyl'
        r = s.CylinderParams[6] * 1000
    elif s.IsPlane:
        t = 'plane'
        n = [round(v, 3) for v in f.Normal]
    return t, r, n, box, f.GetArea * 1e6 if not callable(f.GetArea) else f.GetArea() * 1e6


def pick(d, sel):
    out = []
    for f in faces_of(d):
        t, r, n, b, a = info(f)
        lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
        if sel[0] == 'cyl' and t == 'cyl' and abs(r - sel[1]) < 0.02:
            q = sel[2]
            if all(lo[i] >= q[i] - .01 and hi[i] <= q[i + 3] + .01 for i in range(3)):
                out.append(f)
        if sel[0] == 'touch':      # any face whose box meets the given box and whose area is under the limit (local mesh control)
            q, amax = sel[1], sel[2]
            if all(lo[i] <= q[i + 3] and hi[i] >= q[i] for i in range(3)) and a <= amax:
                out.append(f)
        if sel[0] == 'plane' and t == 'plane':
            p = sel[1]
            if all(lo[i] - .3 <= p[i] <= hi[i] + .3 for i in range(3)) and (sel[2] is None or abs(a - sel[2]) < sel[2] * .3):
                if len(sel) > 3 and sel[3] == 'on':       # the point must lie on the face itself (within 0.05 mm)
                    q = f.GetClosestPointOn(p[0] / 1000, p[1] / 1000, p[2] / 1000)
                    if q is None or math.dist([v * 1000 for v in list(q)[:3]], p) > 0.05:
                        continue
                out.append(f)
    return out


def layer(nodes, S, near, n, exclude):
    n = np.array(n, float)
    s = n[0] ** 2 * S[:, 0] + n[1] ** 2 * S[:, 1] + n[2] ** 2 * S[:, 2] + 2 * (n[0] * n[1] * S[:, 3] + n[0] * n[2] * S[:, 4] + n[1] * n[2] * S[:, 5])
    return s


def run(name, c):
    sw = app()
    t0 = time.time()
    el = c.get('el', 3.0)
    sw.CloseAllDocuments(True)        # a failed case leaves its model open, and a second copy by the same name won't open
    e, w = L(), L()
    d = sw.OpenDoc6(str(PARTS[c['part']]), 1, 1, '', e, w)
    if d is None:
        raise SystemExit(f'open failed: {PARTS[c["part"]]} errors {e.value} warnings {w.value}')
    sw.ActivateDoc3(d.GetTitle, False, 0, L())
    cw = session(W / '.sw_instance_pid').load_simulation()
    doc = cw.ActiveDoc
    sm = doc.StudyManager
    err = I()
    tag = os.environ.get('FEA_STUDY_NAME') or name[:20] + time.strftime('_%H%M%S')
    # FEA_EXISTING_STUDY (2026-11-12): solve a study saved in the model as it is, e.g. with the solver set by hand in the GUI
    # (StaticStudyOptions puts fail from these scripts). Its materials, fixtures, loads, contacts, controls and mesh are kept;
    # the fixture / load faces are only re-picked here for the post-processing.
    ex_name = os.environ.get('FEA_EXISTING_STUDY')
    if ex_name:
        names = [sm.GetStudy(k).Name for k in range(sm.StudyCount)]
        if ex_name not in names:
            raise SystemExit(f'study {ex_name} not in {PARTS[c["part"]]} (has {names})')
        sm.ActiveStudy = names.index(ex_name)
        st = sm.GetStudy(names.index(ex_name))
        print(name, 'existing study', ex_name, 'solver reads', st.StaticStudyOptions.SolverType, flush=True)
    else:
        st = sm.CreateNewStudy3(tag, 0, 0, err)
        print(name, 'study', tag, err.value, flush=True)
        sol = st.SolidManager
        comp = sol.GetComponentAt(0, I())
        b = comp.GetSolidBodyAt(0, I())
        m = b.GetDefaultMaterial
        m.MaterialUnits = 0
        m.MaterialName = 'T'
        for k, v in (('EX', EX), ('NUXY', NU), ('GXY', EX / (2 * (1 + NU))), ('DENS', RHO), ('SIGYLD', YIELD * 1e6), ('SIGXT', 50e6)):
            m.SetPropertyByName2(k, v, False)
        print(' material', [comp.GetSolidBodyAt(k, I()).SetSolidBodyMaterial(m) for k in range(comp.SolidBodyCount)], flush=True)
    lbc = st.LoadsAndRestraintsManager
    fixed = []
    for kind, sel in c['fix']:
        fs = pick(d, sel)
        if ex_name:
            fixed += fs
            continue
        err = I()
        lbc.AddRestraint({'fixed': 0, 'hinge': 4}[kind], fs, NUL, err)
        print(' fixture', kind, len(fs), 'err', err.value, flush=True)
        if not fs or err.value:
            raise SystemExit('fixture failed')
        fixed += fs
    loaded = []
    if 'remote' in c:
        sel, at, f, mm_ = c['remote']
        fs = [x for s_ in (sel if isinstance(sel, list) else [sel]) for x in pick(d, s_)]
        loaded += fs
    if 'remote' in c and not ex_name:
        err = I()
        r = lbc.AddRemoteLoad(1, fs, 0, at[0], at[1], at[2], err)
        print(' remote', len(fs), 'err', err.value, flush=True)
        call(r, 'RemoteLoadBeginEdit')
        r.ConnectionType = 0
        r.ForceUnit = 0
        r.MomentUnit = 0
        r.SetForceOrTranslationValues2(any(f), f[0] != 0, float(f[0]), f[1] != 0, float(f[1]), f[2] != 0, float(f[2]))
        r.SetMomentOrRotationValues2(any(mm_), mm_[0] != 0, float(mm_[0]), mm_[1] != 0, float(mm_[1]), mm_[2] != 0, float(mm_[2]))
        print(' remote end', call(r, 'RemoteLoadEndEdit'), flush=True)
    for sel, newton, ref in c.get('forces', []):
        fs = pick(d, sel)
        loaded += fs
        if ex_name:
            continue
        err = I()
        lbc.AddForce3(1, 0, -1, 0, 0, 0, NUL, NUL, False, False, 0, 0, 0, float(newton), [1.0] * 6, False, False, fs, NUL, False, err)
        print(' normal force', len(fs), newton, 'err', err.value, flush=True)
        if not fs or err.value:
            raise SystemExit('force failed')
    post = c['pre_mesh'](st, d, lbc) if 'pre_mesh' in c else None     # contacts, connectors: returns a result hook
    mesh = st.Mesh
    if not ex_name:
        mesh.Quality = 1
    opts = {}      # defaults this script does not set: logged so runs on different machines can be compared
    for k, o, a in (('solver', st, 'StaticStudyOptions.SolverType'), ('mesher', mesh, 'MesherType'), ('jacobian', mesh, 'JacobianPoints'),
                    ('auto_transition', mesh, 'AutomaticTransition'), ('jacobian_check', mesh, 'UseJacobianCheck')):
        try:
            for part in a.split('.'):
                o = getattr(o, part)
            opts[k] = o
        except Exception:
            opts[k] = '?'
    print(' options', opts, flush=True)
    if os.environ.get('FEA_SOLVER') and not ex_name:      # 2026-11-12: e.g. direct sparse for contact runs the iterative solver will not converge
        try:
            so = st.StaticStudyOptions
            so.SolverType = int(os.environ['FEA_SOLVER'])
            print(' solver set to', os.environ['FEA_SOLVER'], 'reads back', st.StaticStudyOptions.SolverType, flush=True)
        except Exception as ex:
            print(' solver not set:', str(ex)[:100], flush=True)
            try:   # late-bound dispatch can't reach the put; use the typed wrapper from cosworks.tlb (memid 1)
                import pythoncom
                from win32com.client import gencache
                la = pythoncom.LoadTypeLib(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.tlb").GetLibAttr()
                mod = gencache.EnsureModule(str(la[0]), la[1], la[3], la[4])
                tso = mod.ICWStaticStudyOptions(st.StaticStudyOptions)
                tso.SolverType = int(os.environ['FEA_SOLVER'])
                print(' solver set (typed) to', os.environ['FEA_SOLVER'], 'reads back', tso.SolverType, flush=True)
            except Exception as ex2:
                print(' solver not set (typed):', str(ex2)[:140], flush=True)
    for sel, size in ([] if ex_name else c.get('ctrl', [])):
        fs = pick(d, sel)
        q = mesh.ApplyMeshControl(fs, I())
        q = q[0] if isinstance(q, tuple) else q
        call(q, 'MeshControlBeginEdit')
        q.Units = 0
        q.ElementSize = size
        q.Ratio = 1.5
        print(' control', len(fs), size, call(q, 'MeshControlEndEdit'), flush=True)
    tm = time.time()
    if ex_name and mesh.NodeCount:
        rc = 0
        print(' mesh kept', 'nodes', mesh.NodeCount, 'elements', mesh.ElementCount, flush=True)
    else:
        rc = st.CreateMesh(0, el, el * 0.05)
        print(' mesh', rc, 'nodes', mesh.NodeCount, 'elements', mesh.ElementCount, round(time.time() - tm), 's', flush=True)
    if rc:
        raise SystemExit('mesh failed')
    if os.environ.get('FEA_SAVE_STUDY') == '1':      # keep the study (and its mesh) in the model file, for a hand edit and FEA_EXISTING_STUDY
        e2, w2 = L(), L()
        ok = d.Save3(1, e2, w2)
        print(' saved study', tag, 'in', d.GetPathName, 'ok', ok, 'errors', e2.value, 'warnings', w2.value, flush=True)
    if os.environ.get('FEA_MESH_ONLY') == '1':      # mesh-time diagnosis (2026-11-12): stop after meshing
        sw.CloseDoc(d.GetTitle)
        print(' mesh only: done', flush=True)
        return
    rc = call(st, 'RunAnalysis')
    print(' solve', rc, round(time.time() - t0), 's', flush=True)
    res = st.Results
    if rc or res is None:
        raise SystemExit('solve failed')
    raw = call(mesh, 'GetNodes')
    raw = np.array(raw[0] if isinstance(raw, tuple) and len(raw) == 2 else raw, float).reshape(-1, 4)
    ids = raw[:, 0].astype(int)
    xyz = dict(zip(ids, raw[:, 1:] * 1000))
    err = I()
    s = res.GetStress(0, 1, NUL, 3, err)
    s = np.array(s[0] if isinstance(s, tuple) and len(s) == 2 else s, float).reshape(-1, 12)
    pos = np.array([xyz[int(i)] for i in s[:, 0]])
    np.savez(str(F / (name + '.npz')), pos=pos, s=s)      # saved first: the fixture readback below has failed on contact models
    try:
        err = I()
        q = res.GetStressForEntities2(True, 9, 1, NUL, fixed, 3, err)
        q = q[0] if isinstance(q, tuple) and len(q) == 2 else q
        fid = np.array(q, float).reshape(-1, 2)[:, 0].astype(int)
        anchors = np.array([xyz[int(i)] for i in fid if int(i) in xyz])
        dist = cKDTree(anchors).query(pos)[0]
    except Exception as ex:      # no fixture exclusion then (said in the log)
        print(' fixture nodes not read:', str(ex)[:80], flush=True)
        dist = np.full(len(pos), 1e9)
    away = dist >= 2 * el
    for bx in c.get('exclude', []):          # judged elsewhere (listed with the results): not part of the bulk / layer peaks
        away &= ~np.all((pos >= np.array(bx[:3])) & (pos <= np.array(bx[3:])), axis=1)
    if c.get('exclude'):
        print(' excluded', c['exclude'], flush=True)
    vm = s[:, 10]
    np.savez(str(F / (name + '.npz')), pos=pos, s=s)
    i = np.flatnonzero(away)[np.argmax(vm[away])]
    out = dict(case=name, part=c['part'], el=el, nodes=int(mesh.NodeCount), elements=int(mesh.ElementCount), peak_vm=round(float(vm.max()), 2), vm=round(float(vm[i]), 2), at=pos[i].round(1).tolist(), sf=round(YIELD / float(vm[i]), 2))
    for label, n in (('x', (1, 0, 0)), ('y', (0, 1, 0)), ('z', (0, 0, 1))):
        ln = layer(pos, s[:, 1:7], None, n, None)
        j = np.flatnonzero(away)[np.argmax(ln[away])]
        out['layer_' + label] = dict(mpa=round(float(ln[j]), 2), at=pos[j].round(1).tolist(), sf=round(YIELD * LAYER / max(float(ln[j]), 1e-9), 2))
    for k, box in c.get('regions', {}).items():
        mk = np.all((pos >= np.array(box[:3])) & (pos <= np.array(box[3:])), axis=1)
        if mk.any():
            k_ = np.flatnonzero(mk)[np.argmax(vm[mk])]
            out['region_' + k] = dict(vm=round(float(vm[k_]), 2), at=pos[k_].round(1).tolist(), sf=round(YIELD / float(vm[k_]), 2), p1=round(float(s[mk, 7].max()), 2), p3=round(float(s[mk, 9].min()), 2), layer_x=round(float(layer(pos[mk], s[mk, 1:7], None, (1, 0, 0), None).max()), 2))
    if loaded:
        err = I()
        q = res.GetStressForEntities2(True, 9, 1, NUL, loaded, 3, err)
        q = q[0] if isinstance(q, tuple) and len(q) == 2 else q
        lid = np.array(q, float).reshape(-1, 2)[:, 0].astype(int)
        lpts = np.array([xyz[int(i)] for i in lid if int(i) in xyz])
        far = away & (cKDTree(lpts).query(pos)[0] >= 2 * el)
        i = np.flatnonzero(far)[np.argmax(vm[far])]
        out['clear'] = dict(vm=round(float(vm[i]), 2), at=pos[i].round(1).tolist(), sf=round(YIELD / float(vm[i]), 2))
        for label, n in (('x', (1, 0, 0)), ('z', (0, 0, 1))):
            ln = layer(pos, s[:, 1:7], None, n, None)
            j = np.flatnonzero(far)[np.argmax(ln[far])]
            out['clear']['layer_' + label] = dict(sf=round(YIELD * LAYER / max(float(ln[j]), 1e-9), 2), at=pos[j].round(1).tolist())
    if post:
        out.update(post(st, res))
    out['model_sha256'] = hashlib.sha256(Path(PARTS[c['part']]).read_bytes()).hexdigest()
    print(json.dumps(out), round(time.time() - t0), 's', flush=True)
    rows = json.loads(RUNS.read_text()) if RUNS.exists() else []
    RUNS.write_text(json.dumps(rows + [out], indent=0))
    sw.CloseDoc(d.GetTitle)


if __name__ == '__main__' and sys.argv[1] == 'faces':
    sw = app()
    e, w = L(), L()
    d = sw.OpenDoc6(str(PARTS[sys.argv[2]]), 1, 1, '', e, w)
    x0, x1, r0, r1 = (float(v) for v in sys.argv[3:7])
    for f in faces_of(d):
        t, r, n, b, a = info(f)
        cx, cy, cz = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2
        rr = math.hypot(cy - CY, cz - CZ)
        if x0 <= cx <= x1 and r0 <= rr <= r1:
            th = math.degrees(math.atan2(cz - CZ, -(cy - CY))) % 360
            print(t, 'R' if r is None else round(r, 2), n, 'area', round(a, 1), 'box', [round(v, 1) for v in b], 'r', round(rr, 1), 'th', round(th, 1))
    sw.CloseDoc(d.GetTitle)
elif __name__ == '__main__':
    for n in sys.argv[1:]:
        run(n, CASES[n])
