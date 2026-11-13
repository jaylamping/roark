"""Linear static studies in SolidWorks Simulation from a script, with the checks that make a result worth reporting.

    from swkit import *
    from swfea import *

    with job() as j:
        d = open_doc(j.sw, model)
        r = static(j, d, 'TIP_100N', PETG,
                   fixtures=[('fixed', pick(d, kind='plane', normal=(-1, 0, 0)))],
                   loads=[('remote', pick(d, kind='plane', normal=(1, 0, 0)), (100, 5, 5), (0, 0, -100), (0, 0, 0))],
                   el=2.0)
        print(r.summary())            # nodes, peak von Mises away from the fixture, peak displacement, reaction check

How to choose the inputs and how to judge the output: playbook/05-fea.md. Units: mm, N, N.m, MPa; material properties
in SI (Pa, kg/m3) because that is what the Simulation material takes.

The calls are those of cad/scripts/fea/p3_fea.py and hub_seat.py on branch left-arm-organic-r1, proven on SolidWorks
2026. Needs numpy and scipy.
"""
import os
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from swkit import NUL, Failed, L, call, dispatch_array, free_gb, log, solid_bodies

# Printed PETG as the arm studies use it: modulus and yield from the left-arm test coupons, and across layers half the
# in-plane strength (cad/scripts/fea/p3_fea.py). Steel and brass for bolts and inserts in contact models.
PETG = dict(name='PETG printed', EX=1.9e9, NUXY=0.38, DENS=1190.0, SIGYLD=45e6, SIGXT=50e6)
STEEL = dict(name='Steel', EX=2.1e11, NUXY=0.28, DENS=7850.0, SIGYLD=640e6, SIGXT=800e6)
BRASS = dict(name='Brass', EX=1.0e11, NUXY=0.33, DENS=8500.0, SIGYLD=240e6, SIGXT=340e6)
LAYER_FACTOR = 0.5            # allowable across print layers, as a share of yield
NO_PENETRATION, BONDED = 0, 1         # CreateContactSet types
SOLVER_DIRECT = 1             # swsSolverType_e: 0 automatic, 1 direct sparse, 2 FFEPlus (iterative), 7 Intel direct sparse
MAX_NODES = 450_000           # above this a direct-sparse solve does not fit holly-pc's memory (05-fea.md, memory)


def _arr(q, cols):
    """A COM result as an (n, cols) array; late binding sometimes wraps it in a (data, error) tuple."""
    q = q[0] if isinstance(q, tuple) and len(q) == 2 and not np.isscalar(q[0]) else q
    return np.array(q, float).reshape(-1, cols)


def _material(body, mat):
    mt = body.GetDefaultMaterial
    mt.MaterialUnits = 0                       # SI
    mt.MaterialName = mat['name']
    for k in ('EX', 'NUXY', 'DENS', 'SIGYLD', 'SIGXT'):
        mt.SetPropertyByName2(k, mat[k], False)
    mt.SetPropertyByName2('GXY', mat['EX'] / (2 * (1 + mat['NUXY'])), False)
    rc = body.SetSolidBodyMaterial(mt)
    if rc:
        raise Failed(f'material not set ({rc})')


def solver_macro(j, d, study, solver, folder):
    """Set a study's solver from inside SolidWorks with a generated Basic macro; returns the macro's own log text.

    Writing StaticStudyOptions from python fails ("can not be set" / "server threw an exception") and reading it back
    after a write faults inside SolidWorks, so neither is done here. The study must be saved in the model first.
    The saves here do not rebuild: a rebuild makes every face object the caller still holds stale, and reading results
    for those faces then fails with "Memory is locked" (measured 2026-11-12).
    Measured on SolidWorks 2026 SP0: asking for 1 (direct sparse) reads back as 7 (Intel direct sparse), and the
    benchmark log beside the model then names "Intel Direct Sparse".
    """
    _save_as_is(d)
    folder = Path(folder)
    mlog, mac = folder / f'solver_{study}.log', folder / f'solver_{study}.swb'
    mac.write_text('\n'.join([
        'Dim swApp As Object', 'Sub main()', 'On Error Resume Next', 'Set swApp = Application.SldWorks',
        f'Open "{mlog}" For Output As #1',
        'Set cwa = swApp.GetAddInObject("SldWorks.Simulation")', 'Set cw = cwa.CosmosWorks',
        'Set sm = cw.ActiveDoc.StudyManager',
        'For i = 0 To sm.StudyCount - 1', 'Set s = sm.GetStudy(i)', f'If s.Name = "{study}" Then',
        'Set so = s.StaticStudyOptions', 'Print #1, "before "; so.SolverType', 'Err.Clear',
        f'so.SolverType = {int(solver)}', 'Print #1, "set err "; Err.Number; " "; Err.Description',
        'Print #1, "after "; s.StaticStudyOptions.SolverType', 'End If', 'Next i', 'Close #1', 'End Sub', '']), encoding='ascii')
    e = L()
    j.sw.RunMacro2(str(mac), '', 'main', 1, e)
    text = mlog.read_text(errors='ignore') if mlog.exists() else ''
    if 'set err  0' not in text and 'set err 0' not in text:
        raise Failed(f'solver macro did not set the solver: {text!r} (RunMacro2 error {e.value})')
    _save_as_is(d)
    return text


def _save_as_is(d):
    """Save without rebuilding, so face and edge objects stay valid."""
    e, w = L(), L()
    if not d.Save3(1, e, w):
        raise Failed(f'save failed: {d.GetPathName} errors {e.value} warnings {w.value}')


class Result:
    """Nodal results of one solved study, in the model frame.

    pos (n, 3) mm. s (n, 12) MPa: node, sx sy sz, txy txz tyz, p1 p2 p3, von Mises, stress intensity (p1 - p3).
    disp (n, 5) mm: node, UX UY UZ, resultant. reaction [Fx, Fy, Fz, resultant] N: what the fixtures push back with,
    summed over every restrained node, so it is equal and opposite to the applied load. applied: the size of the
    applied load in N (the sum of the sizes when there are several loads: compare by hand when they are not parallel).
    Columns and units measured on SolidWorks 2026 SP0, 2026-11-12 (selftest.py beam, rod, steps).
    """

    def __init__(self, name, el, pos, s, fixed_pts, loaded_pts, disp, reaction, nodes, elements, seconds, applied):
        self.name, self.el, self.pos, self.s = name, el, pos, s
        self.fixed_pts, self.loaded_pts = fixed_pts, loaded_pts
        self.disp, self.reaction = disp, reaction
        self.nodes, self.elements, self.seconds, self.applied = nodes, elements, seconds, applied
        self.vm = s[:, 10]

    def away(self, k=2.0):
        """Mask of nodes at least k element sizes from every fixture and load face.

        Stress on a restrained or loaded face is an artefact of the idealisation, and at a sharp restrained edge it grows
        without limit as the mesh shrinks. Report the peak away from them, and say that you did.
        """
        keep = np.ones(len(self.pos), bool)
        for pts in (self.fixed_pts, self.loaded_pts):
            if pts is not None and len(pts):
                keep &= cKDTree(pts).query(self.pos)[0] >= k * self.el
        return keep

    def peak(self, mask=None):
        """(von Mises MPa, [x, y, z] mm) of the worst node in mask (default: away from fixtures and loads)."""
        mask = self.away() if mask is None else mask
        if not mask.any():
            raise Failed(f'{self.name}: no nodes left in the mask')
        i = np.flatnonzero(mask)[np.argmax(self.vm[mask])]
        return float(self.vm[i]), self.pos[i].round(2).tolist()

    def layer_stress(self, normal, mask=None):
        """(MPa, where) of the largest tensile stress across print layers whose normal is the given direction."""
        n = np.array(normal, float)
        n /= np.linalg.norm(n)
        S = self.s
        sn = (n[0] ** 2 * S[:, 1] + n[1] ** 2 * S[:, 2] + n[2] ** 2 * S[:, 3]
              + 2 * (n[0] * n[1] * S[:, 4] + n[0] * n[2] * S[:, 5] + n[1] * n[2] * S[:, 6]))
        mask = self.away() if mask is None else mask
        i = np.flatnonzero(mask)[np.argmax(sn[mask])]
        return float(sn[i]), self.pos[i].round(2).tolist()

    def in_box(self, box):
        return np.all((self.pos >= np.array(box[:3])) & (self.pos <= np.array(box[3:])), axis=1)

    def average(self, at, radius):
        """Mean von Mises over the nodes within radius mm of a point, and how many nodes that was.

        A peak that falls back to the surrounding level within about 1 mm, on a handful of nodes, is a corner effect;
        one that holds over 2 mm is the section. Report the average with its node count beside any peak that governs.
        """
        idx = cKDTree(self.pos).query_ball_point(at, radius)
        return float(self.vm[idx].mean()), len(idx)

    def max_disp(self):
        """Largest resultant displacement in mm, or None if displacements could not be read."""
        return None if self.disp is None else float(np.abs(self.disp[:, 4]).max())

    def summary(self, yield_mpa=45.0):
        vm, at = self.peak()
        out = dict(study=self.name, el_mm=self.el, nodes=self.nodes, elements=self.elements, solve_s=round(self.seconds),
                   peak_vm_all=round(float(self.vm.max()), 2), peak_vm_away=round(vm, 2), at=at,
                   sf_yield=round(yield_mpa / vm, 2) if vm > 0 else None, max_disp_mm=self.max_disp(),
                   reaction_N=self.reaction, applied_N=self.applied)
        return out


def static(j, d, name, material, fixtures, loads, el, ctrl=(), contacts=(), materials=None, solver=None, keep_study=False,
           post=None):
    """Build, mesh and solve one linear static study on the open part d, and read the nodal results back.

    material: the dict for every body, unless materials = {body name: dict} names some bodies individually.
    fixtures: [('fixed' | 'hinge', faces)]. loads: [('normal', faces, newtons)] presses on the faces along their own
    normals with that many newtons IN TOTAL, shared between the faces by area (one even pressure; positive pushes into
    the material). [('remote', faces, (x, y, z) mm, (Fx, Fy, Fz) N, (Mx, My, Mz) N.m)] applies a force and moment at a
    point in the model frame, carried to the faces rigidly.
    el: global element size mm. ctrl: [(faces, size mm)] local mesh controls.
    contacts: [(NO_PENETRATION | BONDED, faces_a, faces_b)] for multi-body parts; everything else touching is bonded.
    solver: None leaves Automatic; SOLVER_DIRECT sets direct sparse through a macro (needed for no-penetration contact).
    post: post(study, results) is called after the solve and before the study is deleted, for anything static() does
    not read itself; what it returns is kept as Result.extra.
    Every face list must be non-empty: an empty pick is the commonest way to solve the wrong problem.
    """
    t0 = time.time()
    cw = j.simulation()
    doc = cw.ActiveDoc
    if doc is None:
        raise Failed('Simulation sees no active document: open_doc() the model before static()')
    sm = doc.StudyManager
    err = L()
    tag = name[:24]
    st = sm.CreateNewStudy3(tag, 0, 0, err)            # 0 static, 0 solid mesh
    if st is None or err.value:
        raise Failed(f'study not created ({err.value}); a study of the same name already in the model?')
    comp = st.SolidManager.GetComponentAt(0, L())
    for k in range(comp.SolidBodyCount):
        b = comp.GetSolidBodyAt(k, L())
        _material(b, (materials or {}).get(str(call(b, 'SolidBodyName')).split('/')[-1], material) if materials else material)
    lbc = st.LoadsAndRestraintsManager
    fixed, loaded, applied = [], [], 0.0
    for kind, fs in fixtures:
        if not fs:
            raise Failed(f'{name}: a {kind} fixture has no faces')
        err = L()
        lbc.AddRestraint({'fixed': 0, 'hinge': 4}[kind], list(fs), NUL, err)
        if err.value:
            raise Failed(f'{name}: {kind} fixture failed ({err.value})')
        fixed += list(fs)
    for ld in loads:
        fs = list(ld[1])
        if not fs:
            raise Failed(f'{name}: a {ld[0]} load has no faces')
        loaded += fs
        err = L()
        if ld[0] == 'normal':
            # AddForce3 puts the value on EACH face it is given (two faces at 100 N reacted 200 N, 2026-11-12), so each
            # face gets its own call with its share by area
            areas = [call(f, 'GetArea') for f in fs]
            for f, a in zip(fs, areas):
                err = L()
                lbc.AddForce3(1, 0, -1, 0, 0, 0, NUL, NUL, False, False, 0, 0, 0, float(ld[2]) * a / sum(areas), [1.0] * 6,
                              False, False, [f], NUL, False, err)
                if err.value:
                    raise Failed(f'{name}: normal load failed ({err.value})')
            applied += abs(float(ld[2]))
        elif ld[0] == 'remote':
            at, f, mo = ld[2], ld[3], ld[4]
            r = lbc.AddRemoteLoad(1, fs, 0, at[0], at[1], at[2], err)
            call(r, 'RemoteLoadBeginEdit')
            r.ConnectionType = 0                   # rigid
            r.ForceUnit = 0                        # N
            r.MomentUnit = 0                       # N.m
            r.SetForceOrTranslationValues2(any(f), f[0] != 0, float(f[0]), f[1] != 0, float(f[1]), f[2] != 0, float(f[2]))
            r.SetMomentOrRotationValues2(any(mo), mo[0] != 0, float(mo[0]), mo[1] != 0, float(mo[1]), mo[2] != 0, float(mo[2]))
            rc = call(r, 'RemoteLoadEndEdit')
            if rc:
                raise Failed(f'{name}: remote load not accepted ({rc})')
            applied += float(np.linalg.norm(f))
        else:
            raise Failed(f'unknown load kind {ld[0]}')
        if err.value:
            raise Failed(f'{name}: {ld[0]} load failed ({err.value})')
    cm = st.ContactManager
    for kind, fa, fb in contacts:
        if not fa or not fb:
            raise Failed(f'{name}: a contact set has an empty side ({len(fa)}, {len(fb)} faces)')
        err = L()
        cs = cm.CreateContactSet(kind, dispatch_array(fa), dispatch_array(fb), err)
        if cs is None or err.value:
            raise Failed(f'{name}: contact set failed ({err.value})')
    mesh = st.Mesh
    mesh.Quality = 1                               # high: second-order tetrahedra
    for fs, size in ctrl:
        if not fs:
            raise Failed(f'{name}: a mesh control has no faces')
        q = mesh.ApplyMeshControl(list(fs), L())
        q = q[0] if isinstance(q, tuple) else q
        call(q, 'MeshControlBeginEdit')
        q.Units = 0                                # mm
        q.ElementSize = size
        q.Ratio = 1.5
        call(q, 'MeshControlEndEdit')
    rc = st.CreateMesh(0, el, el * 0.05)           # sizes in mm
    nodes, elements = int(mesh.NodeCount), int(mesh.ElementCount)
    log(f'{name}: mesh rc {rc}, {nodes} nodes, {elements} elements, free {free_gb():.1f} GB')
    if rc or not nodes:
        raise Failed(f'{name}: mesh failed ({rc}): sliver faces, or an element size larger than a thin wall?')
    if nodes > MAX_NODES:
        raise Failed(f'{name}: {nodes} nodes is over {MAX_NODES}: coarsen the global size and keep the local controls')
    if solver is not None:
        log(f'{name}: solver macro:', solver_macro(j, d, tag, solver, Path(d.GetPathName).parent).replace('\n', ' | '))
    rc = call(st, 'RunAnalysis')
    res = st.Results
    if rc or res is None:
        raise Failed(f'{name}: solve failed ({rc}). 24 is a singular model (a body free to move) or out of memory: '
                     'playbook/05-fea.md, "When the solve fails"')
    raw = _arr(call(mesh, 'GetNodes'), 4)
    xyz = dict(zip(raw[:, 0].astype(int), raw[:, 1:] * 1000))
    s = _arr(res.GetStress(0, 1, NUL, 3, L()), 12)       # 3 = N/mm2
    pos = np.array([xyz[int(i)] for i in s[:, 0]])

    def face_nodes(fs):
        try:
            q = _arr(res.GetStressForEntities2(True, 9, 1, NUL, fs, 3, L()), 2)
            return np.array([xyz[int(i)] for i in q[:, 0] if int(i) in xyz])
        except Exception as ex:      # noqa: BLE001 - has failed on contact models; the caller is told
            log(f'{name}: face nodes not read ({str(ex)[:80]}): peaks are NOT cleared of fixtures and loads')
            return None

    fixed_pts, loaded_pts = face_nodes(fixed), face_nodes(loaded)
    disp = reaction = None
    try:
        disp = _arr(res.GetTranslationalDisplacement(1, NUL, 0, L()), 5)       # last argument: 0 mm, 1 cm, 2 m, 3 inch
    except Exception as ex:      # noqa: BLE001
        log(f'{name}: displacements not read ({str(ex)[:80]})')
    try:
        # per node: id, Fx Fy Fz Fres, Mx My Mz Mres; zero except on restrained nodes. Last argument 0 = N (1 = lbf).
        # GetReactionForces2 does not exist on SolidWorks 2026.
        q = _arr(res.GetReactionForcesAndMoments(0, NUL, 0, L()), 9)
        f = q[:, 1:4].sum(axis=0)
        reaction = [round(float(v), 3) for v in f] + [round(float(np.linalg.norm(f)), 3)]
    except Exception as ex:      # noqa: BLE001
        log(f'{name}: reactions not read ({str(ex)[:80]})')
    extra = post(st, res) if post is not None else None
    if not keep_study and os.environ.get('SWFEA_KEEP') != '1':
        try:
            sm.DeleteStudy(tag)
        except Exception:      # noqa: BLE001 - the study staying in the model only costs file size
            pass
    r = Result(name, el, pos, s, fixed_pts, loaded_pts, disp, reaction, nodes, elements, time.time() - t0, applied)
    r.extra = extra
    return r


def converge(run, sizes, tol=0.05):
    """Solve at each element size in turn (coarse to fine) until the peak away from fixtures moves by under tol.

    run(el) -> Result. Returns the list of (el, nodes, peak) rows and whether it converged. A peak that keeps climbing as
    the mesh shrinks is a singularity (a sharp re-entrant corner or a fixture edge), not a stress: change the geometry
    (add the real fillet) or the mask, do not report the last number.
    """
    rows = []
    for el in sizes:
        r = run(el)
        rows.append((el, r.nodes, round(r.peak()[0], 2)))
        log('converge', rows[-1])
        if len(rows) > 1 and abs(rows[-1][2] - rows[-2][2]) <= tol * rows[-2][2]:
            return rows, True
    return rows, False


def body_named(d, part):
    """The solid body whose name contains part (bodies brought in by insert_body are named after their file)."""
    hit = [b for b in solid_bodies(d) if part.lower() in b.Name.lower()]
    if len(hit) != 1:
        raise Failed(f'{len(hit)} bodies match "{part}": {[b.Name for b in solid_bodies(d)]}')
    return hit[0]
