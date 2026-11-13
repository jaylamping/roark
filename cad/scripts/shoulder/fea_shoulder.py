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
PARTS = {'hub': F / os.environ.get('HUB_FEA_FILE', 'hub_fea.SLDPRT')}   # a second solve stream uses its own copy
PARTS['fork'] = F / os.environ.get('FORK_FEA_FILE', 'fork_fea.SLDPRT')
PARTS['fork1'] = F / 'fork1_fea.SLDPRT'
PARTS['stop_fr'] = F / 'stop_fork_rear.SLDPRT'   # stop rev 2 checks
PARTS['stop_cap'] = F / 'stop_cap.SLDPRT'
PARTS['stop_fr_leg2'] = F / 'stop_fork_rear_leg2.SLDPRT'
PARTS['stop_fr_G'] = F / 'stop_fork_rear_G.SLDPRT'
PARTS['stop_fr_N'] = F / 'stop_fork_rear_N.SLDPRT'
PARTS['stop_fr_N2'] = F / 'stop_fork_rear_N2.SLDPRT'      # fork front alone (debug of the two-body model)   # fork front + fork rear, two bodies (fork_fea_part.py)


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
    elif s.IsTorus:
        t = 'tor'
        tp = s.TorusParams
        r = (tp[6] * 1000, tp[7] * 1000)      # major, minor
    return t, r, n, box, f.GetArea * 1e6 if not callable(f.GetArea) else f.GetArea() * 1e6


def _safe(f, default=None):
    try:
        return f()
    except Exception:
        return default


def pick(d, sel):
    out = []
    for f in faces_of(d):
        t, r, n, b, a = info(f)
        lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
        if sel[0] == 'cyl' and t == 'cyl' and abs(r - sel[1]) < 0.02:
            q = sel[2]
            if all(lo[i] >= q[i] - .01 and hi[i] <= q[i + 3] + .01 for i in range(3)):
                out.append(f)
        if sel[0] == 'tor' and t == 'tor' and abs(r[1] - sel[1]) < 0.02 and sel[2][0] <= r[0] <= sel[2][1]:   # minor radius, major range
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
    el = float(os.environ.get('FEA_EL', c.get('el', 3.0)))
    sw.CloseAllDocuments(True)        # a failed case leaves its model open, and a second copy by the same name won't open
    e, w = L(), L()
    d = sw.OpenDoc6(str(PARTS[c['part']]), 1, 1, '', e, w)
    sw.ActivateDoc3(d.GetTitle, False, 0, L())
    if c.get('dummy'):
        # a stiff dummy of the RS02 output: an aluminium disc seated on the hub's step face, a separate body bonded to it
        # (the six preloaded M4 on PCD 24 keep the joint closed: about 0.6 kN of bolt load change at 23 N.m against about
        # 3 kN of preload each), so the load reaches the hub through the seat and the bolt pattern, not through hub faces
        from swk import Sk, plane, extrude
        dm_ = c['dummy']
        with Sk(d, plane(d, 'Y', dm_['y0'], 'P_DUMMY'), 'DUMMY') as s_:
            s_.circle((RX, dm_['y0'], YZ), dm_['r'])
        extrude(d, s_.feat, 'DUMMY', dm_['t'], (0, 1, 0), merge=False)
        if dm_.get('bolts'):
            # tapped M4 holes in the dummy (thread faces for the bolt connectors), on the hub's six screw axes
            cen_ = hole_centres(d)
            print(' hub hole centres', [tuple(round(v, 3) for v in c_) for c_ in cen_], flush=True)
            with Sk(d, plane(d, 'Y', dm_['y0'], 'P_DUMMY_T'), 'DUMMY_TAPS') as s_:
                for cx_, cz_ in cen_:
                    s_.circle((cx_, dm_['y0'], cz_), 1.65)
            extrude(d, s_.feat, 'DUMMY_TAPS', 8.0, (0, 1, 0), cut=True)
        d.ForceRebuild3(False)
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
    mats = []
    for k in range(comp.SolidBodyCount):
        cb = comp.GetSolidBodyAt(k, I())
        is_dummy = False
        if c.get('dummy'):
            nm_ = ''
            for a_ in ('SolidBodyName', 'Name'):
                try:
                    nm_ = str(getattr(cb, a_)); break
                except Exception:
                    pass
            # the dummy is the body made by the DUMMY feature (created last); by name if the name is readable
            is_dummy = ('DUMMY' in nm_.upper()) if nm_ else (k == comp.SolidBodyCount - 1)
            print(' body', k, repr(nm_), 'dummy' if is_dummy else 'hub', flush=True)
        if is_dummy:
            ma = cb.GetDefaultMaterial
            ma.MaterialUnits = 0
            ma.MaterialName = 'AL'
            for k_, v_ in (('EX', 69e9), ('NUXY', 0.33), ('GXY', 26e9), ('DENS', 2700.0), ('SIGYLD', 250e6), ('SIGXT', 300e6)):
                ma.SetPropertyByName2(k_, v_, False)
            mats.append(('dummy', cb.SetSolidBodyMaterial(ma)))
        else:
            mats.append(('petg', cb.SetSolidBodyMaterial(m)))
    print(' material', mats, flush=True)
    lbc = st.LoadsAndRestraintsManager
    fixed = []
    for kind, sel in c['fix']:
        fs = pick(d, sel)
        if kind.endswith('?'):          # optional: only where the part has these faces
            if not fs:
                continue
            kind = kind[:-1]
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
    rems = ([c['remote'] + (c.get('coupling', 0),)] if 'remote' in c else []) + [tuple(x) for x in c.get('remotes', [])]
    for sel, at, f, mm_, cpl in rems:
        fs, seen_ = [], set()
        for x in [x for s_ in (sel if isinstance(sel, list) else [sel]) for x in pick(d, s_)]:
            k_ = tuple(round(v, 3) for v in info(x)[3])
            if k_ not in seen_:
                seen_.add(k_)
                fs.append(x)
        loaded += fs
        err = I()
        r = lbc.AddRemoteLoad(1, fs, 0, at[0], at[1], at[2], err)
        print(' remote', len(fs), 'err', err.value, flush=True)
        call(r, 'RemoteLoadBeginEdit')
        r.ConnectionType = cpl                         # 0 rigid, 1 distributed
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
    if c.get('stabilise'):
        # contact models: soft springs hold the dummy against rigid-body motion until contact closes; Intel direct sparse
        so_ = st.StaticStudyOptions
        try:
            so_.UseSoftSpring = 1
            so_.SolverType = int(os.environ.get('FEA_SOLVER', '7'))   # 7 Intel direct sparse; 2 FFEPlus (iterative) if direct runs out of memory
        except Exception as e_:
            print(' study options failed', e_, flush=True)
    if os.environ.get('FEA_SOLVER') and not c.get('stabilise'):
        for try_ in range(3):      # set and read back on one options object; a fresh COM handle sometimes fails to read
            try:
                so_ = st.StaticStudyOptions
                so_.SolverType = int(os.environ['FEA_SOLVER'])   # 2 FFEPlus (iterative)
                got_ = so_.SolverType
                print(' solver set', got_, flush=True)
                if got_ == int(os.environ['FEA_SOLVER']):
                    break
            except Exception as e_:
                print(' solver override failed', try_, e_, flush=True)
                time.sleep(2)
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
        if not fs and c.get('ctrl_optional'):      # like-for-like runs on variants: a face set one geometry lacks is skipped
            print(' control', sel[0], 'no faces: skipped', flush=True)
            continue
        q = mesh.ApplyMeshControl(fs, I())
        q = q[0] if isinstance(q, tuple) else q
        call(q, 'MeshControlBeginEdit')
        q.Units = 0
        q.ElementSize = size
        q.Ratio = 1.5
        print(' control', len(fs), size, call(q, 'MeshControlEndEdit'), flush=True)
    rc = st.CreateMesh(0, el, el * 0.05)
    print(' mesh', rc, 'nodes', mesh.NodeCount, 'elements', mesh.ElementCount, flush=True)
    # fallbacks when the curvature mesher fails (rev C run-out lofts leave narrow faces): blended curvature, then finer
    for mt, k in ((1, 1.0), (1, 0.8), (0, 0.8)):
        if not rc:
            break
        try:
            mesh.MesherType = mt
        except Exception as e_:
            print(' mesher type set failed', e_, flush=True)
        rc = st.CreateMesh(0, el * k, el * k * 0.05)
        print(' mesh retry', mt, el * k, rc, 'nodes', mesh.NodeCount, 'elements', mesh.ElementCount, flush=True)
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
    extra = {}
    if c.get('react') or c.get('disp'):
        try:
            err = I()
            u = res.GetDisplacement(0, 1, NUL, 0, err)
            u = np.array(u[0] if isinstance(u, tuple) and len(u) == 2 else u, float).reshape(-1, 5)
            upos = np.array([xyz[int(i)] for i in u[:, 0]])
            extra['u_max'] = round(float(u[:, 4].max()), 4)
            for k_, box in c.get('disp', {}).items():         # mean displacement (as the solver reports it) of the nodes in a box
                mk = np.all((upos >= np.array(box[:3])) & (upos <= np.array(box[3:])), axis=1)
                extra['u_' + k_] = [round(float(v), 4) for v in u[mk, 1:5].mean(axis=0)] + [int(mk.sum())]
            np.savez(str(F / (name + '_u.npz')), pos=upos, u=u)
        except Exception as ex:
            extra['u_err'] = str(ex)[:120]
        for k_, sels in c.get('react', {}).items():
            try:
                fs_ = [x for s_ in sels for x in pick(d, s_)]
                err = I()
                r_ = res.GetReactionForcesAndMoments(1, NUL, fs_, 0, err)
                r_ = r_[0] if isinstance(r_, tuple) and len(r_) == 2 else r_
                extra['R_' + k_] = [round(float(v), 2) for v in list(r_)[:8]] + [len(fs_), err.value]
            except Exception as ex:
                extra['R_' + k_ + '_err'] = str(ex)[:120]
        print(' extra', extra, flush=True)
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
    if c.get('dummy'):
        keep_ = pos[:, 1] <= c['dummy']['y0'] + 0.01      # hub nodes only (the dummy sits above the seat)
        pos, s, away = pos[keep_], s[keep_], away[keep_]
    vm = s[:, 10]
    np.savez(str(F / (name + '.npz')), pos=pos, s=s)
    i = np.flatnonzero(away)[np.argmax(vm[away])]
    out = dict(extra, case=name, part=c['part'], el=el, nodes=int(len(pos)), elements=int(_safe(lambda: mesh.ElementCount, -1)), peak_vm=round(float(vm.max()), 2), vm=round(float(vm[i]), 2), at=pos[i].round(1).tolist(), sf=round(YIELD / float(vm[i]), 2))
    for label, n in (('x', (1, 0, 0)), ('y', (0, 1, 0)), ('z', (0, 0, 1))):
        ln = layer(pos, s[:, 1:7], None, n, None)
        j = np.flatnonzero(away)[np.argmax(ln[away])]
        out['layer_' + label] = dict(mpa=round(float(ln[j]), 2), at=pos[j].round(1).tolist(), sf=round(YIELD * LAYER / max(float(ln[j]), 1e-9), 2))
    for k, box in c.get('regions', {}).items():
        mk = np.all((pos >= np.array(box[:3])) & (pos <= np.array(box[3:])), axis=1)
        if mk.any():
            k_ = np.flatnonzero(mk)[np.argmax(vm[mk])]
            out['region_' + k] = dict(vm=round(float(vm[k_]), 2), at=pos[k_].round(1).tolist(), sf=round(YIELD / float(vm[k_]), 2), p1=round(float(s[mk, 7].max()), 2), p3=round(float(s[mk, 9].min()), 2), layer_x=round(float(layer(pos[mk], s[mk, 1:7], None, (1, 0, 0), None).max()), 2), layer_y=round(float(layer(pos[mk], s[mk, 1:7], None, (0, 1, 0), None).max()), 2), sf_layer_y=round(YIELD * LAYER / max(float(layer(pos[mk], s[mk, 1:7], None, (0, 1, 0), None).max()), 1e-9), 2))
            # 1 mm averages: mean over the nodes within 1 mm of the region's bulk peak and of its layer (sigma_y) peak
            ly_all = layer(pos, s[:, 1:7], None, (0, 1, 0), None)
            kl = np.flatnonzero(mk)[np.argmax(ly_all[mk])]
            near_v = np.linalg.norm(pos - pos[k_], axis=1) <= 1.0
            near_l = np.linalg.norm(pos - pos[kl], axis=1) <= 1.0
            n5_v = np.linalg.norm(pos - pos[k_], axis=1) <= 0.5
            n5_l = np.linalg.norm(pos - pos[kl], axis=1) <= 0.5
            out['region_' + k].update(layer_at=pos[kl].round(1).tolist(), sf_avg1=round(YIELD / float(vm[near_v].mean()), 2),
                                      sf_layer_y_avg1=round(YIELD * LAYER / max(float(ly_all[near_l].mean()), 1e-9), 2), n_avg1=int(near_l.sum()),
                                      sf_avg05=round(YIELD / float(vm[n5_v].mean()), 2),
                                      sf_layer_y_avg05=round(YIELD * LAYER / max(float(ly_all[n5_l].mean()), 1e-9), 2), n_avg05=int(n5_l.sum()))
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
HUB_FIX = [('fixed', cyl(2.15, [150, 297, -20, 192, 321, 30])), ('fixed', pl((RX + 21.5, RS02_OUT, YZ))),
           ('fixed?', cyl(1.9, [150, 297, -20, 192, 321, 30]))]   # ?: the two Ø3.8 locating holes, where the hub has them
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
RS02_SIDE = [cyl(2.15, [150, 297, -20, 192, 321, 30]), pl((RX + 21.5, RS02_OUT, YZ)), cyl(1.9, [150, 297, -20, 192, 321, 30])]   # + the Ø3.8 locating holes where present
GROOVE_FIX = [('radial', cyl(35.8, [130, 295.5, -35, 212, 302.5, 47])), ('axialY', ('cone', [130, 296.8, -35, 212, 298.0, 47])),
              ('fixed', LUG_HOLES[0]), ('fixed', LUG_HOLES[1])]
GREG = {'load_flank_90': [150, 296.5, 25, 192, 298.2, 47], 'load_flank_270': [150, 296.5, -35, 192, 298.2, -13],
        'land_below': [130, 295.9, -35, 212, 297.05, 47], 'spigot_ring': [130, 295.9, -35, 212, 302.1, 47],
        'lug_A': [143, 286, -2, 158, 297, 14], 'lug_B': [183, 286, -2, 198, 297, 14], 'hub_top': [130, 311.5, -35, 212, 320, 47]}
for k_, f_, m_ in (('A', (0.0, -372.0, 0.0), (22.9, 17.0, 0.0)), ('B', (0.0, -62.0, 0.0), (7.0, 8.6, 14.7))):
    CASES['HUBG_' + k_] = dict(part='hub', fix=GROOVE_FIX, remote=(RS02_SIDE, AT, tuple(-v for v in f_), tuple(-v for v in m_)), el=1.5,
                               ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (('cone', [130, 296.8, -35, 212, 298.0, 47]), 0.4)], regions=GREG)

# REV C: groove Y 298-302, cones of the load flank in Y 297.9-299.0; distributed coupling at the RS02 side; optional
# end-face contact on the disc face at Y 302 (bilateral axial support: the optimistic bound of a compression-only contact)
CONE_C = ('cone', [130, 297.8, -35, 212, 299.0, 47])
FACE_302 = pl((RX, 302.0, YZ - 37.5))
GREG_C = dict(GREG, load_flank_90=[150, 297.5, 25, 192, 299.2, 47], load_flank_270=[150, 297.5, -35, 192, 299.2, -13],
              land_below=[130, 295.9, -35, 212, 298.05, 47], window_band=[130, 302.2, -35, 212, 312.8, 47],
              groove_bottom=[130, 298.6, -35, 212, 300.8, 47], spigot_edge=[130, 295.4, -35, 212, 296.8, 47], disc_corner=[130, 301.4, -35, 212, 303.0, 47],
              corner45_t135=[139.0, 299.9, 24.0, 151.5, 301.2, 37.5], corner45_t315=[189.5, 299.9, -25.5, 202.0, 301.2, -12.0])
for k_, f_, m_ in (('A', (0.0, -372.0, 0.0), (22.9, 17.0, 0.0)), ('B', (0.0, -62.0, 0.0), (7.0, 8.6, 14.7))):
    base = dict(part='hub', remote=(RS02_SIDE, AT, tuple(-v for v in f_), tuple(-v for v in m_)), coupling=1, el=1.5,
                ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (CONE_C, float(os.environ.get('CONE_EL', '0.7')))], regions=GREG_C)
    # (SolidWorks gives the r 35.8 faces loose boxes, Y 294.3-304.4: the box is wide; only r 35.8 cylinders are taken)
    fx = [('radial', cyl(35.8, [130, 294.0, -35, 212, 305.0, 47])), ('axialY', CONE_C), ('fixed', LUG_HOLES[0]), ('fixed', LUG_HOLES[1])]
    CASES['HUBC_' + k_] = dict(base, fix=fx)
    CASES['HUBCF_' + k_] = dict(base, fix=fx + [('axialY', FACE_302)])

# REV C, interim lug case (arm thread's earlier bolted run, no ridge; rough, +-20%): each lug about 230 N along -Y plus
# about 170 N of opposed X shear (pulling the lugs apart), as a distributed remote load on each seam-bolt hole about the
# hole centre; hub held at the RS02 side (hub screws and step-ring face fixed). An upper bound for the lug roots.
CASES['HUBL_I'] = dict(part='hub', fix=HUB_FIX, el=1.5, ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5)], regions=GREG_C,
                       remotes=[(LUG_HOLES[0], (147.5, 292.0, YZ), (-170.0, -230.0, 0.0), (0.0, 0.0, 0.0), 1),
                                (LUG_HOLES[1], (193.5, 292.0, YZ), (170.0, -230.0, 0.0), (0.0, 0.0, 0.0), 1)])

# REV D2 comparison (2026-11-12): the arm's grown stop loads (its STOP_124 nominal: -X lug Fz 228 N, Fx 40, 56 N axial;
# +X lug Fz -134 N), same mesh on rev D, D2 and D2b: 0.4 mm on the lug-root R1.2 fillets, the groove bottom (r 34.3 and its
# bottom rounds) and the bore faces of the inward fill (r 23 on rev D; r 20 / 21 and the 45 deg cone on D2)
CASES['HUBL_STOP2'] = dict(part='hub', fix=HUB_FIX, el=1.5, ctrl_optional=1, regions=dict(GREG_C, lug_A=[143, 286, -2, 158, 297, 14], lug_B=[183, 286, -2, 198, 297, 14]),
    ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (cyl(1.2, [137, 294.5, -1.5, 205, 296.2, 13.5]), 0.4),
          (cyl(34.3, [130, 297.5, -35, 212, 302.0, 47]), 0.4), (('tor', 0.4, (34.0, 35.0)), 0.4), (('tor', 1.0, (34.0, 35.6)), 0.4),
          # the bore faces: SolidWorks gives large faces loose boxes, so a wide box; the radius alone picks them
          (cyl(23.0, [110, 285, -50, 231, 320, 62]), 0.4), (cyl(20.0, [110, 285, -50, 231, 320, 62]), 0.4), (cyl(21.0, [110, 285, -50, 231, 320, 62]), 0.4),
          (('cone', [130, 295.9, -35, 212, 313.5, 47]), 0.4)],
    remotes=[(LUG_HOLES[0], (147.5, 292.0, YZ), (40.0, -56.0, 228.0), (0.0, 0.0, 0.0), 1),
             (LUG_HOLES[1], (193.5, 292.0, YZ), (0.0, 0.0, -134.0), (0.0, 0.0, 0.0), 1)])

# HUBL_STOP2 loads with a light, identical mesh for every variant (coordinator, 21:58Z: under about 700k nodes): 0.35 mm on
# the -X lug's two R1.2 Z roots, 0.4 mm on the small faces round the -X lug's root (its Z faces, inner face, outer R1.0
# roots and any local backing; large faces such as the bore and underside rings are excluded by area), 0.5 mm in the lug
# holes, 1.5 mm elsewhere. The groove bottom and bore are single full-ring faces, so they are not refined (a face control
# cannot be limited to an arc)
CASES['HUBL_STOP3'] = dict(CASES['HUBL_STOP2'], ctrl_optional=1,
    ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (cyl(1.2, [137, 294.5, -1.5, 153.5, 296.2, 13.5]), 0.35),
          (('touch', [137, 293.5, -2.0, 154.0, 297.5, 14.0], 160.0), 0.4)])

# HUBL_STOP3 with the loads swapped onto the +X lug (the stop the other way; the +X lug sits in the cable sector and has no
# backing): +X lug Fz 228 N, Fx -40 N (mirrored), 56 N axial; -X lug Fz -134 N. The same light mesh, mirrored onto the +X lug
CASES['HUBL_STOP3X'] = dict(CASES['HUBL_STOP3'], ctrl_optional=1,
    ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (cyl(1.2, [187.5, 294.5, -1.5, 204, 296.2, 13.5]), 0.35),
          (('touch', [187.0, 293.5, -2.0, 204.0, 297.5, 14.0], 160.0), 0.4)],
    remotes=[(LUG_HOLES[0], (147.5, 292.0, YZ), (0.0, 0.0, -134.0), (0.0, 0.0, 0.0), 1),
             (LUG_HOLES[1], (193.5, 292.0, YZ), (-40.0, -56.0, 228.0), (0.0, 0.0, 0.0), 1)])

# Yaw torque (coordinator 23:59Z): the full-ring ridge carries no torque about the yaw axis, so the RS02's whole torque goes
# through the two lugs as a Z-force couple, F = T / 46.0 mm (lug bolt axes at X 147.5 and 193.5). At the 17 N.m peak (RS02
# manual 260713 4.1.2) 370 N per lug; linear, so one solve gives both directions (the other is -sigma); rated 6 N.m = x 6/17.
# Light mesh on both lugs: 0.35 mm on all four R1.2 Z roots, 0.4 mm on the small faces round both roots, 0.5 mm in the holes
YAW_F = 17.0 / 0.046
CASES['HUBL_YAW'] = dict(part='hub', fix=HUB_FIX, el=1.5, ctrl_optional=1, regions=dict(GREG_C, lug_A=[143, 286, -2, 158, 297, 14], lug_B=[183, 286, -2, 198, 297, 14]),
    ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (cyl(1.2, [137, 294.5, -1.5, 205, 296.2, 13.5]), 0.35),
          (('touch', [137, 293.5, -2.0, 154.0, 297.5, 14.0], 160.0), 0.4), (('touch', [187.0, 293.5, -2.0, 204.0, 297.5, 14.0], 160.0), 0.4)],
    remotes=[(LUG_HOLES[0], (147.5, 292.0, YZ), (0.0, 0.0, YAW_F), (0.0, 0.0, 0.0), 1),
             (LUG_HOLES[1], (193.5, 292.0, YZ), (0.0, 0.0, -YAW_F), (0.0, 0.0, 0.0), 1)])

# Rev D3 (the arm thread's extended-lug torque path, 45b2e71): the lugs and their extensions bear on the arm through flat
# printed shim plates on their Z faces (the planes Z 1.0 / 11.0, r 18.7-36.8 x Y 288-297.6 short of the fillets). The couple
# goes in as a distributed load on the pushing Z face of each lug (-X lug: Z 1.0 face, pushed +Z; +X lug: Z 11.0 face, pushed
# -Z; linear, so the other direction is -sigma).
#   HUBL_YAW3   17 N.m on the arm's mating face (r 18.5-35.3 x Y 288-294.3, centroid about r 28): 304 N per lug, at r 28,
#               Y 291.2. 370 N (the conservative bolt-lever figure) is the same result x 370/304 (linear, same distribution)
#   HUBL_STOP4  the stop-case lug loads (-X: Fz 228, Fx 40, 56 N along -Y; +X: Fz -134) on the same faces, at r 28
D3_FACE = lambda sg: ('plane', (RX + sg * 28.0, 290.0, 1.0 if sg < 0 else 11.0), None, 'on')   # a point on the flat face, 5.4 clear of the bolt hole (X offset 23, Y 292)
D3_AT = lambda sg, r_: (RX + sg * r_, 291.2, 1.0 if sg < 0 else 11.0)
D3_CTRL = [(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5), (cyl(1.2, [132, 294.5, -1.5, 209, 297.8, 13.5]), 0.35), (cyl(0.5, [132, 293.5, 0.5, 209, 295.1, 11.5]), 0.35),
           (('touch', [132.0, 292.5, -2.0, 154.0, 298.2, 14.0], 160.0), 0.4), (('touch', [187.0, 292.5, -2.0, 209.0, 298.2, 14.0], 160.0), 0.4)]
D3_REG = dict(GREG_C, lug_A=[130, 286, -2, 158, 298, 14], lug_B=[183, 286, -2, 211, 298, 14])
_d3 = lambda fa, fb, ra, rb: dict(part='hub', fix=HUB_FIX, el=1.5, ctrl_optional=1, ctrl=D3_CTRL, regions=D3_REG,
                                  remotes=[(D3_FACE(-1), D3_AT(-1, ra), fa, (0.0, 0.0, 0.0), 1), (D3_FACE(1), D3_AT(1, rb), fb, (0.0, 0.0, 0.0), 1)])
YAW3_F = 17000.0 / (2 * 28.0)
CASES['HUBL_YAW3'] = _d3((0.0, 0.0, YAW3_F), (0.0, 0.0, -YAW3_F), 28.0, 28.0)
CASES['HUBL_STOP4'] = _d3((40.0, -56.0, 228.0), (0.0, 0.0, -134.0), 28.0, 28.0)

# REV D, the arm thread's stop case on the full-ring joint (its fine-mesh repeat, roark 3c7114b): the full-ring ridge and groove
# are axisymmetric and frictionless, so they carry no torque about the hub axis; that part of the stop moment goes into the
# lugs as a Z-force pair. -X lug: Fz +169 N, Fx +40 N, 55 N axial (taken as a pull along -Y, like HUBL_I); +X lug: Fz -112 N.
CASES['HUBL_STOP'] = dict(part='hub', fix=HUB_FIX, el=1.5, ctrl=[(LUG_HOLES[0], 0.5), (LUG_HOLES[1], 0.5)], regions=dict(GREG_C, lug_A=[143, 286, -2, 158, 297, 14], lug_B=[183, 286, -2, 198, 297, 14]),
                          remotes=[(LUG_HOLES[0], (147.5, 292.0, YZ), (40.0, -55.0, 169.0), (0.0, 0.0, 0.0), 1),
                                   (LUG_HOLES[1], (193.5, 292.0, YZ), (0.0, 0.0, -112.0), (0.0, 0.0, 0.0), 1)])

SCREW_ANGLES = [-142.0, -82.0, -22.0, 38.0, 98.0, 158.0]     # hub screws on PCD 24 (measured on the hub)
HEAD_SEAT_Y = 298.06                                          # bottom face of each screw boss (tube r 2.15-4.4 in the lightening
                                                              # pocket, Y 298.06-319.86): the heads bear here, clamping 21.8 mm of boss
WASHER_OD, SHANK_D = 8.8, 4.0                                 # bearing limited by the boss OD 8.8 (washer Ø9): r 2.15-4.4, 46.3 mm2


def hole_centres(d):
    """Actual centres (X, Z) of the six hub screw holes, from the circle parameters of their edges (the imported holes sit a
    few hundredths off the nominal PCD 24 positions; the bolt connector needs head and thread concentric)."""
    import inspect
    out = []
    for a_ in SCREW_ANGLES:
        t_ = math.radians(a_)
        nx, nz = RX + 12.0 * math.cos(t_), YZ + 12.0 * math.sin(t_)
        found = None
        for b in d.GetBodies2(0, True):
            es = b.GetEdges
            for ed in (es() if inspect.ismethod(es) else es):
                cv = ed.GetCurve
                if not cv.IsCircle:
                    continue
                cp = cv.CircleParams
                cx_, cy_, cz_, r_ = cp[0] * 1e3, cp[1] * 1e3, cp[2] * 1e3, cp[6] * 1e3
                if (abs(r_ - 2.15) < 0.1 or abs(r_ - 1.9) < 0.1) and math.hypot(cx_ - nx, cz_ - nz) < 0.5:   # 1.9: the two locating holes (Ø3.8)
                    found = (cx_, cz_)
                    break
            if found:
                break
        out.append(found or (nx, nz))
    return out


def bolt_setup(preload):
    """pre_mesh hook: no-penetration contact between hub and dummy everywhere, and six bolt connectors (counterbore screw:
    head on the hub hole edge at the seat, thread in the dummy's tapped hole) with an axial preload."""
    def hook(st, d, lbc):
        cm = st.ContactManager
        try:
            r_ = cm.SetGlobalContact(2, 0)
        except Exception as e_:
            r_ = repr(e_)
        print(' global contact no-penetration', r_, flush=True)
        from swk import edges_where
        out = []
        for a_, (cx, cz) in zip(SCREW_ANGLES, hole_centres(d)):
            head = edges_where(d, lambda p, cx=cx, cz=cz: abs(p[1] - HEAD_SEAT_Y) < 0.08 and math.hypot(p[0] - cx, p[2] - cz) < 2.3,
                               pair=lambda p0, p1, cx=cx, cz=cz: all(min(abs(math.hypot(q[0] - cx, q[2] - cz) - 2.145), abs(math.hypot(q[0] - cx, q[2] - cz) - 1.9)) < 0.12 for q in (p0, p1)))   # Ø4.3 clearance or Ø3.8 locating
            thr = pick(d, cyl(1.65, [cx - 2, RS02_OUT - 0.1, cz - 2, cx + 2, RS02_OUT + 8.2, cz + 2]))
            err = I()
            b = lbc.AddBoltConnector(2, head[:1], thr, err)
            if b is None:
                print(' bolt', a_, 'head edges', len(head), 'thread faces', len(thr), 'err', err.value, flush=True)
                raise SystemExit('bolt failed')
            call(b, 'BoltConnectorBeginEdit')
            b.HeadDiameterUnit = 0
            b.HeadDiameterValue = WASHER_OD
            b.BoltShankDiameterUnit = 0
            b.BoltShankDiameterValue = SHANK_D
            b.MaterialSource = 1
            b.MaterialUnit = 0
            b.YoungModulus = 210e9
            b.PoissonsRatio = 0.28
            b.ThermalCoefficient = 1.2e-5
            b.PreLoadForceType = 0
            b.PreLoadForceValue = float(preload)
            rc = call(b, 'BoltConnectorEndEdit')
            out.append((a_, len(head), len(thr), rc))
        print(' bolts', out, flush=True)
        # local no-penetration contact on the seat (the solver refuses bolt connectors with no contact defined on them)
        dn, up = [], []
        for f in faces_of(d):
            t_, r_, n_, bx, a_ = info(f)
            if t_ == 'plane' and abs(bx[1] - RS02_OUT) < 0.02 and abs(bx[4] - RS02_OUT) < 0.02 and n_ is not None:
                (dn if n_[1] < -0.9 else up if n_[1] > 0.9 else []).append(f)
        err = I()
        cs = cm.CreateContactSet2(0, 0, dn, up, err)      # contact-set type 0 = no penetration (2 is shrink fit)
        print(' seat contact set: dummy faces', len(dn), 'hub faces', len(up), 'err', err.value, 'set', cs is not None, flush=True)
        if cs is None or err.value:
            raise SystemExit('contact set failed')
        return None
    return hook


# REV C+ honest top: the RS02 output as an aluminium dummy disc (r 23.4, 10 thick) on the step face (Y 319.86), bonded;
# the arm loads go in as their reaction on the dummy's top face about the arm's hub point. The spigot side as in HUBCF_*.
for k_ in ('A', 'B'):
    base_ = CASES['HUBCF_' + k_]
    CASES['HUBD_' + k_] = dict(base_, dummy=dict(r=23.4, y0=RS02_OUT, t=10.0),
                               remote=(pl((RX, RS02_OUT + 10.0, YZ)), AT, base_['remote'][2], base_['remote'][3]), coupling=0,
                               regions=dict(GREG_C, hub_top=[130, 311.5, -35, 212, RS02_OUT + 0.01, 47]))

# contact seat + six preloaded M4 (bearing 15 MPa on the boss end, 46.3 mm2 -> 0.69 kN; relaxed after creep: half)
for k_, pre_ in (('A', 690.0), ('B', 690.0), ('Ah', 345.0)):
    base_ = CASES['HUBD_' + k_[0]]
    CASES['HUBB_' + k_] = dict(base_, dummy=dict(base_['dummy'], bolts=True), pre_mesh=bolt_setup(pre_), stabilise=True)

# (c) roll joint load share and deflection. The fork front and fork rear as two bonded bodies (fork_fea_part.py). The
# arm load of check (a) (310 N down, 23 N.m bending, 17 N.m yaw torque at the hub point) goes in through the RS02 seat
# (seat face and the five screw holes, rigid). RS03 output: the boss face bolted to it, fixed (a rigid output bearing).
# 'free': no 6808 (all load to the RS03); 'brg': 6808 seat held radially (rigid stub, outer race floating axially), its
# reaction is the 6808's share. The truth sits between these two and the pinned-RS03 statics (written in checks/).
FK_BOSS = pl((RX + 9.0, RY + 15.59, ROLL_OUT))   # r 18 at 60 deg: clear of the screw holes (30/90) and the pin holes (0/120)
FK_SEAT6808 = cyl(BRG_SEAT_R, [RX - 27, RY - 27, BRG_LIP_Z - 0.1, RX + 27, RY + 27, HOUSE_Z0 + 1.1])   # follows the seat (r 26.1 since check (d))
_sa = [-150.0, -116.0, -76.0, 84.0, 130.0]
FK_RS02 = [pl((RX + 37.0 * math.cos(math.radians(a_)), SEAT_Y[0], YZ + 37.0 * math.sin(math.radians(a_)))) for a_ in _sa] +           [cyl(1.8, [RX - 45, SEAT_Y[0] - 6, YZ - 45, RX + 45, SEAT_Y[1] + 0.1, YZ + 45])]
FK_DISP = dict(seat6808=[RX - 27, RY - 27, -47.4, RX + 27, RY + 27, -40.7], rs02_seat=[RX - 45, SEAT_Y[0] - 0.2, YZ - 45, RX + 45, SEAT_Y[0] + 0.2, YZ + 45],
               cheek_top=[RX - 50, RY + 45, 38.0, RX + 50, RY + 60, 50.0], rear_top=[RX - 40, RY + 25, -57.0, RX + 40, RY + 40, -45.0])
for tag, f_, mom in (('MX', (0.0, -310.0, 0.0), (23.0, YAW_T, 0.0)), ('MZ', (0.0, -310.0, 0.0), (0.0, YAW_T, 23.0)),
                     ('G', (0.0, -100.0, 0.0), (0.0, 0.0, 0.0)), ('GZ', (0.0, 0.0, -100.0), (0.0, 0.0, 0.0)), ('GX', (-100.0, 0.0, 0.0), (0.0, 0.0, 0.0))):
    for sup in ('free', 'brg'):
        CASES[f'FORK_{tag}_{sup}'] = dict(part='fork', fix=[('fixed', FK_BOSS)] + ([('radial', FK_SEAT6808)] if sup == 'brg' else []),
                                          remote=(FK_RS02, AT, f_, mom), coupling=0, el=2.5, disp=FK_DISP,
                                          react=dict(boss=[FK_BOSS], **({'seat6808': [FK_SEAT6808]} if sup == 'brg' else {})))

# STOP REV 2 (A2) at the RS03 peak (60 N.m, manual 261013 s1.3): 1714 N on the contact flank at r 35 (60 / 0.035), as a
# normal force on the flank face. Tooth: fork rear held at its joint face to the fork front and its two joint screws (the
# torque goes fork rear -> joint -> fork front -> RS03). Cap: held at its three M3 screws and its front face on the drum.
_ss = STOP_SLOT
_ta, _th = _ss['tooth_angle'], _ss['tooth_half']
def _rp(r, a, z):
    return (RX + r * math.cos(math.radians(a)), RY + r * math.sin(math.radians(a)), z)
STOP_F = 60000.0 / 35.0
CASES['STOP_A2_TOOTH'] = dict(part='stop_fr', el=1.5,
                              fix=[('fixed', ('plane', (RX, 356.9, JZ0), None, 'on')), ('fixed', cyl(2.25, [RX - 25, 350, -70, RX + 25, 364, JZ0 + 1]))],
                              forces=[(('plane', _rp(35.0, _ta - _th, -37.0), None, 'on'), STOP_F, None)],
                              ctrl=[(('touch', [RX - 14, RY - 44, -46.5, RX + 14, RY - 27, -32.5], 400.0), 0.5)],
                              regions=dict(tooth=[RX - 14, RY - 44, -46.5, RX + 14, RY - 27, -32.5]))
# the realistic hold: the two joint screws (the torque goes down the leg to the fork front) and the 6808 seat held radially
CASES['STOP_A2_TOOTH_J'] = dict(CASES['STOP_A2_TOOTH'], fix=[('fixed', cyl(2.25, [RX - 33, 340, -70, RX + 33, 364, JZ0 + 1])),
                                                            ('radial', cyl(BRG_SEAT_R, [RX - 27, RY - 27, BRG_LIP_Z - 0.1, RX + 27, RY + 27, HOUSE_Z0 + 1.1]))])
CASES['STOP_A2_TOOTH_LEG2'] = dict(CASES['STOP_A2_TOOTH_J'], part='stop_fr_leg2')   # the outward-leg mock-up
CASES['STOP_A2_TOOTH_G'] = dict(CASES['STOP_A2_TOOTH_J'], part='stop_fr_G')   # rear_screws layout G
CASES['STOP_A2_TOOTH_N'] = dict(CASES['STOP_A2_TOOTH_J'], part='stop_fr_N')   # rear_screws layout N
CASES['STOP_A2_TOOTH_N2'] = dict(CASES['STOP_A2_TOOTH_J'], part='stop_fr_N2')
CASES['STOP_A2_CAP'] = dict(part='stop_cap', el=1.5,
                            fix=[('fixed', cyl(1.7, [RX - 60, RY - 60, CAP_Z1 - 2, RX + 60, RY + 60, DRUM_Z0 + 1])), ('fixed', ('plane', _rp(54.0, 225.0, DRUM_Z0), None, 'on'))],
                            forces=[(('plane', _rp(35.0, _ta - _th + ROLL_STOP_IN, -36.0), None, 'on'), STOP_F, None)],
                            ctrl=[(('touch', [RX - 30, RY - 46, -40.5, RX + 2, RY - 20, -28.0], 400.0), 0.5)],
                            regions=dict(slot_end=[RX - 30, RY - 46, -40.5, RX + 2, RY - 20, -28.0]))

CASES['FORK1_G_free'] = dict(CASES['FORK_G_free'], part='fork1')

if __name__ == '__main__':
    try:
        for n in sys.argv[1:]:
            run(n, CASES[n])
    finally:
        if not os.environ.get('SW_KEEP'):      # one instance per run: exit it when the run ends
            from sw_instance import end_session
            try:
                app().CloseAllDocuments(True)
            except Exception:
                pass
            try:
                end_session(STATE)
            except Exception as e_:      # a dropped COM handle (AttributeError) escapes end_session: stop our own instance
                import sw_instance as SI
                print(' end_session failed:', type(e_).__name__, e_, '- stopping our instance', flush=True)
                pid_ = SI._session_pid(str(STATE))
                if pid_ is not None:
                    SI.kill_tree(pid_, SI._started(pid_))
                if os.path.exists(str(STATE)):
                    os.remove(str(STATE))
