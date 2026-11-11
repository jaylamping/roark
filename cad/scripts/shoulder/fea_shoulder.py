"""Linear static FEA of the shoulder parts in SolidWorks Simulation, in this session's own instance.

    python fea_shoulder.py <case> [...]

Engine adapted from the arm thread's cad/scripts/fea/p3_fea.py (left-arm-organic), so the numbers compare: PETG E 1.9 GPa,
nu 0.38, yield 45 MPa, layer strength 0.5 x yield. Each case reports the peak von Mises away from the fixtures (bulk SF),
the peak normal stress across each layer direction (layer SF), and the same peaks with nothing excluded (sf_noexcl).
Models are copies in cad/_sim/shoulder (gitignored); rows go to cad/_sim/shoulder/fea_runs.json.
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

from swk import app, session, STATE, L, NUL, CAD, VARIANT, pythoncom
from dims import *

F = CAD / '_sim' / 'shoulder'
F.mkdir(parents=True, exist_ok=True)
RUNS = F / 'fea_runs.json'
I = lambda v=0: VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)
EX, NU, YIELD, LAYER, RHO = 1.9e9, 0.38, 45.0, 0.5, 1270.0
PARTS = {'hub': F / 'hub_fea.SLDPRT'}


def cyl(r, box):
    return ('cyl', r, box)


def pl(point, area=None):
    return ('plane', point, area, 'on')


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
        if sel[0] == 'cone' and f.GetSurface.IsCone:      # cones whose box lies inside the given box
            q = sel[1]
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
    sw.ActivateDoc3(d.GetTitle, False, 0, L())
    cw = session(STATE).load_simulation()
    doc = cw.ActiveDoc
    sm = doc.StudyManager
    err = I()
    tag = name[:20] + time.strftime('_%H%M%S')
    st = sm.CreateNewStudy3(tag, 0, 0, err)
    print(name, 'study', err.value, flush=True)
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
        err = I()
        if kind in ('radial', 'axialY'):
            # radial only on cylinders (type 7: radial, circumferential, axial), or only normal to the Top plane (type 5)
            ref = d.FeatureByName('Top Plane') if kind == 'axialY' else NUL
            r_ = lbc.AddRestraint(7 if kind == 'radial' else 5, fs, ref, err)
            call(r_, 'RestraintBeginEdit')
            r_.SetTranslationComponentsValues2(*((1, 0, 0) if kind == 'radial' else (0, 0, 1)), 0.0, 0.0, 0.0)
            print(' restraint edit', call(r_, 'RestraintEndEdit'), flush=True)
        else:
            lbc.AddRestraint({'fixed': 0, 'roller': 3, 'hinge': 4}[kind], fs, NUL, err)
        print(' fixture', kind, len(fs), 'err', err.value, flush=True)
        if not fs or err.value:
            raise SystemExit('fixture failed')
        fixed += fs
    loaded = []
    if 'remote' in c:
        sel, at, f, mm_ = c['remote']
        fs = [x for s_ in (sel if isinstance(sel, list) else [sel]) for x in pick(d, s_)]
        loaded += fs
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
        err = I()
        lbc.AddForce3(1, 0, -1, 0, 0, 0, NUL, NUL, False, False, 0, 0, 0, float(newton), [1.0] * 6, False, False, fs, NUL, False, err)
        print(' normal force', len(fs), newton, 'err', err.value, flush=True)
        if not fs or err.value:
            raise SystemExit('force failed')
    post = c['pre_mesh'](st, d, lbc) if 'pre_mesh' in c else None     # contacts, connectors: returns a result hook
    mesh = st.Mesh
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
    for sel, size in c.get('ctrl', []):
        fs = pick(d, sel)
        q = mesh.ApplyMeshControl(fs, I())
        q = q[0] if isinstance(q, tuple) else q
        call(q, 'MeshControlBeginEdit')
        q.Units = 0
        q.ElementSize = size
        q.Ratio = 1.5
        print(' control', len(fs), size, call(q, 'MeshControlEndEdit'), flush=True)
    rc = st.CreateMesh(0, el, el * 0.05)
    print(' mesh', rc, 'nodes', mesh.NodeCount, 'elements', mesh.ElementCount, flush=True)
    if rc:
        raise SystemExit('mesh failed')
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
            out['region_' + k] = dict(vm=round(float(vm[k_]), 2), at=pos[k_].round(1).tolist(), sf=round(YIELD / float(vm[k_]), 2), p1=round(float(s[mk, 7].max()), 2), p3=round(float(s[mk, 9].min()), 2), layer_x=round(float(layer(pos[mk], s[mk, 1:7], None, (1, 0, 0), None).max()), 2), layer_y=round(float(layer(pos[mk], s[mk, 1:7], None, (0, 1, 0), None).max()), 2), sf_layer_y=round(YIELD * LAYER / max(float(layer(pos[mk], s[mk, 1:7], None, (0, 1, 0), None).max()), 1e-9), 2))
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
    out['peak_layer_noexcl'] = {lb: round(float(layer(pos, s[:, 1:7], None, n_, None).max()), 2) for lb, n_ in (('x', (1, 0, 0)), ('y', (0, 1, 0)), ('z', (0, 0, 1)))}
    out['sf_noexcl'] = dict(bulk=round(YIELD / float(vm.max()), 2), **{'layer_' + lb: round(YIELD * LAYER / max(v, 1e-9), 2) for lb, v in out['peak_layer_noexcl'].items()})
    print(json.dumps(out), round(time.time() - t0), 's', flush=True)
    rows = json.loads(RUNS.read_text()) if RUNS.exists() else []
    RUNS.write_text(json.dumps(rows + [out], indent=0))
    sw.CloseDoc(d.GetTitle)



# ---- (a) hub lugs: seam-bolt holes (r 1.7 along Z at X 147.5 / 193.5, Y 292) carry the arm. Fixed at the six hub screws
# (r 2.15 on PCD 24) and the step ring face that bears on the RS02 output. All the arm load is put through the lugs (the
# spigot's bearing on the arm's hub seat is ignored): conservative for the lugs. Hub prints with the yaw axis vertical:
# layers normal to Y, so the layer stress is sigma_y.
HUB_FIX = [('fixed', cyl(2.15, [150, 297, -20, 192, 321, 30])), ('fixed', pl((RX + 21.5, RS02_OUT, YZ)))]
LUG_HOLES = [cyl(1.7, [144, 289, 0, 151, 295, 12]), cyl(1.7, [190, 289, 0, 197, 295, 12])]
AT = (RX, 292.0, YZ)
YAW_T = 17.0          # RS02 peak torque (the arm thread's rating, 17 N.m)
CASES = {}
for tag, mom in (('MX', (23.0, YAW_T, 0.0)), ('MZ', (0.0, YAW_T, 23.0)), ('MXn', (-23.0, -YAW_T, 0.0))):
    CASES['HUB_' + tag] = dict(part='hub', fix=HUB_FIX, remote=(LUG_HOLES, AT, (0.0, -2 * 155.0, 0.0), mom), el=1.5,
                               ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5)], regions={'lug_A': [143, 286, -2, 158, 297, 14], 'lug_B': [183, 286, -2, 198, 297, 14]})

# the other bound: the arm's hub seat clamps the spigot (r 35.8, Y 296-302) as well, so the load enters through lugs and spigot
SPIGOT = cyl(35.8, [130, 295, -35, 212, 303, 47])
for tag, mom in (('MX', (23.0, YAW_T, 0.0)), ('MZ', (0.0, YAW_T, 23.0))):
    CASES['HUBS_' + tag] = dict(CASES['HUB_' + tag], remote=(LUG_HOLES + [SPIGOT], AT, (0.0, -2 * 155.0, 0.0), mom))

# arm-thread load cases (2026-11-11), spigot held over Y 296-302 with the lugs (rigid remote on both):
# A: arm horizontal, 5 kg payload: 62 N shear + 310 N, 22.9 N.m about X, 17 N.m yaw.  B: elbow end stop at 515 N:
# 7.0 N.m about X, 8.6 about Y (yaw), 14.7 about Z (sideways), with the 62 N shear.
CASES['HUBS_A'] = dict(CASES['HUBS_MX'], remote=(LUG_HOLES + [SPIGOT], AT, (0.0, -372.0, 0.0), (22.9, 17.0, 0.0)))
CASES['HUBS_B'] = dict(CASES['HUBS_MX'], remote=(LUG_HOLES + [SPIGOT], AT, (0.0, -62.0, 0.0), (7.0, 8.6, 14.7)))

# ---- groove model (hub rev B + groove): spigot held radially only (roller on the r 35.8 cylinder), axially only on the
# groove's load flanks (roller on the 30 deg cones, low-Y side), lugs bolted (fixed holes). The arm loads go in as their
# reaction at the RS02 side (remote load on the hub screws and the step-ring face, -F and -M about the same point).
RS02_SIDE = [cyl(2.15, [150, 297, -20, 192, 321, 30]), pl((RX + 21.5, RS02_OUT, YZ))]
GROOVE_FIX = [('radial', cyl(35.8, [130, 295.5, -35, 212, 302.5, 47])), ('axialY', ('cone', [130, 296.8, -35, 212, 298.0, 47])),
              ('fixed', LUG_HOLES[0]), ('fixed', LUG_HOLES[1])]
GREG = {'load_flank_90': [150, 296.5, 25, 192, 298.2, 47], 'load_flank_270': [150, 296.5, -35, 192, 298.2, -13],
        'land_below': [130, 295.9, -35, 212, 297.05, 47], 'spigot_ring': [130, 295.9, -35, 212, 302.1, 47],
        'lug_A': [143, 286, -2, 158, 297, 14], 'lug_B': [183, 286, -2, 198, 297, 14], 'hub_top': [130, 311.5, -35, 212, 320, 47]}
for k_, f_, m_ in (('A', (0.0, -372.0, 0.0), (22.9, 17.0, 0.0)), ('B', (0.0, -62.0, 0.0), (7.0, 8.6, 14.7))):
    CASES['HUBG_' + k_] = dict(part='hub', fix=GROOVE_FIX, remote=(RS02_SIDE, AT, tuple(-v for v in f_), tuple(-v for v in m_)), el=1.5,
                               ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (('cone', [130, 296.8, -35, 212, 298.0, 47]), 0.4)], regions=GREG)

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run(n, CASES[n])
