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
import contextlib
import ctypes
import os
import re
import threading
import time
import warnings
from pathlib import Path

import numpy as np
import psutil
import win32con
import win32gui
import win32process
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from swkit import NUL, Failed, L, call, dispatch_array, free_gb, log, solid_bodies

# Printed PETG as the arm studies use it: modulus and yield from the left-arm test coupons, and across layers half the
# in-plane strength (cad/scripts/fea/p3_fea.py). Steel and brass for bolts and inserts in contact models.
PETG = dict(name='PETG printed', EX=1.9e9, NUXY=0.38, DENS=1190.0, SIGYLD=45e6, SIGXT=50e6)
STEEL = dict(name='Steel', EX=2.1e11, NUXY=0.28, DENS=7850.0, SIGYLD=640e6, SIGXT=800e6)
BRASS = dict(name='Brass', EX=1.0e11, NUXY=0.33, DENS=8500.0, SIGYLD=240e6, SIGXT=340e6)
LAYER_FACTOR = 0.5            # allowable across print layers, as a share of yield
NO_PENETRATION, BONDED = 0, 1         # CreateContactSet types
BEARING_X, BEARING_SINE, BEARING_PARABOLIC = 0, 0, 1      # ICWBearingLoad Direction and DistributionType (measured)
SOLVER_DIRECT = 1            # swsSolverType_e: 0 automatic, 1 direct sparse, 2 FFEPlus (iterative), 7 Intel direct sparse
MAX_NODES = 450_000           # above this a direct-sparse solve does not fit holly-pc's memory (05-fea.md, memory)
HEAVY_NODES = 200_000         # above this a solve needs over about 6 GB: one at a time machine-wide (heavy_solve_lock)
HEAVY_LOCK = Path(os.environ.get('FEA_SOLVE_LOCK', r'C:\joe\.fea_solve.lock'))


def _arr(q, cols):
    """A COM result as an (n, cols) array; late binding sometimes wraps it in a (data, error) tuple."""
    q = q[0] if isinstance(q, tuple) and len(q) == 2 and not np.isscalar(q[0]) else q
    return np.array(q, float).reshape(-1, cols)


_STRESS_COLS = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (9, 10))   # (component asked for, column in GetStress)


def stress_table(components, node_ids=None):
    """The 12-column table GetStress returns (node id, sx sy sz txy txz tyz, p1 p2 p3, von Mises, intensity) built from
    one (n, 2) array of node id and value per component, as GetStressForEntities3 gives them. A node shared by two bodies
    is listed once per body with the same value and is kept once. The principals and the intensity are computed from the
    tensor. None if the components do not list the same nodes, or not exactly `node_ids` (the mesh's own)."""
    ids, cols = None, {}
    for col, q in components:
        q = np.asarray(q, float).reshape(-1, 2)
        i = q[:, 0].astype(np.int64)
        order = np.argsort(i, kind='stable')
        i, v = i[order], q[order, 1]
        keep = np.r_[True, i[1:] != i[:-1]]
        i, v = i[keep], v[keep]
        if ids is None:
            ids = i
        elif len(i) != len(ids) or (i != ids).any():
            return None
        cols[col] = v
    if ids is None or (node_ids is not None and (len(ids) != len(node_ids) or set(ids.tolist()) != set(node_ids))):
        return None
    s = np.zeros((len(ids), 12))
    s[:, 0] = ids
    for col, v in cols.items():
        s[:, col] = v
    t = np.empty((len(ids), 3, 3))
    t[:, 0, 0], t[:, 1, 1], t[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
    t[:, 0, 1] = t[:, 1, 0] = s[:, 4]
    t[:, 0, 2] = t[:, 2, 0] = s[:, 5]
    t[:, 1, 2] = t[:, 2, 1] = s[:, 6]
    w = np.linalg.eigvalsh(t)                      # ascending
    s[:, 7], s[:, 8], s[:, 9] = w[:, 2], w[:, 1], w[:, 0]
    s[:, 11] = w[:, 2] - w[:, 0]
    return s


def _stress_by_body(d, res, node_ids, name):
    """The nodal stresses read one component at a time over the solid bodies. GetStress for every node goes through COM
    one value at a time and took 734 s on a 745,656-node model; this took 7 x 19 s and gave the same value at every node
    (shoulder hub, 2026-11-13). Pass bodies, never faces: hundreds of faces ended the instance ("remote procedure call
    failed"). None if the read fails or does not cover exactly the mesh's nodes; the caller then reads the slow way."""
    if os.environ.get('SWFEA_SLOW_READ') == '1':
        return None
    t0 = time.time()
    try:
        bodies = solid_bodies(d)
        parts = [(col, _arr(res.GetStressForEntities3(True, comp, 1, NUL, bodies, 3, 0, 0, False, L()), 2))
                 for comp, col in _STRESS_COLS]
        s = stress_table(parts, node_ids)
    except Exception as ex:      # noqa: BLE001 - any failure here only costs time: the slow read follows
        log(f'{name}: stresses not read by body ({str(ex)[:80]}); reading every node instead')
        return None
    if s is None:
        log(f'{name}: the read by body did not cover the mesh\'s nodes; reading every node instead')
        return None
    log(f'{name}: stresses read by body, {len(s)} nodes in {time.time() - t0:.0f} s')
    return s


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


def _solver_dialogs(pid, stop, seen):
    """While a solve runs, answer the solver's "Excessive displacements detected" box with No, and record any other.

    It also answers OK to "Failure to achieve equilibrium" (a contact iteration that ran out; static() then raises).
    The solver (star.exe, a child of the instance) asks Yes / No / Cancel when a body moves a long way. On a hidden
    instance nobody sees it: the solve waits for ever, --status shows busy, and every other session's launch waits
    behind it (10 minutes on 2026-11-12 before it was found). No finishes the solve with the small-displacement
    result. Only dialogs titled "Simulation" in this instance's own process tree are read. Any other dialog is logged
    with its text and static() fails the run with it ("Fixture transfer failed" went unread on 2026-11-13 and the run
    was reported as if it had solved); one that offers only OK is dismissed first so the solve returns.
    """
    done = set()

    def text_of(c):
        buf, res = ctypes.create_unicode_buffer(4000), ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(c, win32con.WM_GETTEXT, 4000, buf, 2, 1000, ctypes.byref(res))
        return buf.value

    def each(h, pids):
        try:
            if (h in done or win32process.GetWindowThreadProcessId(h)[1] not in pids
                    or win32gui.GetClassName(h) != '#32770' or win32gui.GetWindowText(h) != 'Simulation'):
                return True
            kids = []
            win32gui.EnumChildWindows(h, lambda c, k: k.append(c) or True, kids)
            text = ' '.join(t for t in (text_of(c) for c in kids if win32gui.GetClassName(c) in ('Edit', 'Static')) if t)
            text = ' '.join(text.split())
            done.add(h)
            if 'Excessive displacements' in text:
                for c in kids:
                    if win32gui.GetClassName(c) == 'Button' and win32gui.GetWindowText(c).replace('&', '').strip() == 'No':
                        win32gui.PostMessage(c, win32con.BM_CLICK, 0, 0)
                        seen.append(('excessive', text))
                        log('solver asked about excessive displacements: answered No (finish with the small-displacement result)')
            elif 'Failure to achieve equilibrium' in text:
                for c in kids:
                    if win32gui.GetClassName(c) == 'Button' and win32gui.GetWindowText(c).replace('&', '').strip() == 'OK':
                        win32gui.PostMessage(c, win32con.BM_CLICK, 0, 0)
                        seen.append(('noconverge', text))
                        log('solver could not reach equilibrium: answered OK; the result is not valid')
            else:
                btns = [c for c in kids if win32gui.GetClassName(c) == 'Button']
                names = [win32gui.GetWindowText(c).replace('&', '').strip() for c in btns]
                if names == ['OK']:            # a notice with nothing to choose: dismiss it so the solve returns
                    win32gui.PostMessage(btns[0], win32con.BM_CLICK, 0, 0)
                    seen.append(('notice', text))
                    log('solver notice dismissed with OK, the run will be failed with its text:', text[:300])
                else:
                    seen.append(('unanswered', text))
                    log('solver dialog NOT answered, the solve may be waiting on it:', text[:300])
        except Exception:      # noqa: BLE001 - a window that closed while it was being read
            pass
        return True

    while not stop.wait(2.0):
        try:
            pids = {pid} | {c.pid for c in psutil.Process(pid).children(recursive=True)}
        except psutil.Error:
            return
        try:
            win32gui.EnumWindows(each, pids)
        except Exception:      # noqa: BLE001
            pass


class Result:
    """Nodal results of one solved study, in the model frame.

    pos (n, 3) mm. s (n, 12) MPa: node, sx sy sz, txy txz tyz, p1 p2 p3, von Mises, stress intensity (p1 - p3).
    disp (n, 5) mm: node, UX UY UZ, resultant. reaction [Fx, Fy, Fz, resultant] N: what the fixtures push back with,
    summed over every restrained node, so it is equal and opposite to the applied load. applied: the size of the
    applied load in N (the sum of the sizes when there are several loads: compare by hand when they are not parallel).
    excessive: True when the solver reported excessive displacements (only reachable with loose_ok=True).
    Columns and units measured on SolidWorks 2026 SP0, 2026-11-12 (selftest.py beam, rod, steps).
    """

    def __init__(self, name, el, pos, s, fixed_pts, loaded_pts, disp, reaction, nodes, elements, seconds, applied):
        self.name, self.el, self.pos, self.s = name, el, pos, s
        self.fixed_pts, self.loaded_pts = fixed_pts, loaded_pts
        self.disp, self.reaction = disp, reaction
        self.nodes, self.elements, self.seconds, self.applied = nodes, elements, seconds, applied
        self.vm = s[:, 10]

    def away(self, k=2.0, dist=None):
        """Mask of nodes at least dist mm (default k element sizes) from every fixture and load face.

        Stress on a restrained or loaded face is an artefact of the idealisation, and at a sharp restrained edge it grows
        without limit as the mesh shrinks. Report the peak away from them, and say that you did. Across a convergence
        series pass the same dist every time: a mask of k elements shrinks with the mesh and lets the edge back in.
        The mask also hides real features next to a load face (a screw hole beside a loaded bore): read those
        separately with in_box() and report them.
        """
        keep = np.ones(len(self.pos), bool)
        for pts in (self.fixed_pts, self.loaded_pts):
            if pts is not None and len(pts):
                keep &= cKDTree(pts).query(self.pos)[0] >= (k * self.el if dist is None else dist)
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

    def layer_shear(self, normal, mask=None):
        """(MPa, where) of the largest shear stress on the plane between print layers stacked along the given direction.

        Judge it against the interlayer shear allowable (13 MPa for printed PETG, 05-fea.md).
        """
        n = np.array(normal, float)
        n /= np.linalg.norm(n)
        S = self.s
        t = np.c_[S[:, 1] * n[0] + S[:, 4] * n[1] + S[:, 5] * n[2],       # traction on the layer plane
                  S[:, 4] * n[0] + S[:, 2] * n[1] + S[:, 6] * n[2],
                  S[:, 5] * n[0] + S[:, 6] * n[1] + S[:, 3] * n[2]]
        tau = np.linalg.norm(t - np.outer(t @ n, n), axis=1)
        mask = self.away() if mask is None else mask
        i = np.flatnonzero(mask)[np.argmax(tau[mask])]
        return float(tau[i]), self.pos[i].round(2).tolist()

    def in_box(self, box):
        return np.all((self.pos >= np.array(box[:3])) & (self.pos <= np.array(box[3:])), axis=1)

    def average(self, at, radius):
        """Mean von Mises over the nodes within radius mm of a point, and how many nodes that was.

        A peak that falls back to the surrounding level within about 1 mm, on a handful of nodes, is a corner effect;
        one that holds over 2 mm is the section. Report the average with its node count beside any peak that governs.
        """
        idx = cKDTree(self.pos).query_ball_point(at, radius)
        return float(self.vm[idx].mean()), len(idx)

    def near(self, pts, dist):
        """Mask of nodes within dist mm of any of the given points (n, 3). Use it with a face's nodes to read a surface
        only: on a part in bending average() takes in nodes below the surface and reads low (22 % on a 4 mm wall)."""
        return cKDTree(np.atleast_2d(pts)).query(self.pos)[0] <= dist

    def max_disp(self):
        """Largest resultant displacement in mm, or None if displacements could not be read."""
        return None if self.disp is None else float(np.abs(self.disp[:, 4]).max())

    def summary(self, yield_mpa=45.0, mask=None):
        """The numbers of one study. On a model of several bodies pass mask: without it the peak is taken over every
        body, so a steel screw or pin is judged against the plastic's yield. Split the nodes by geometry (in_box, a
        radius) and call summary once per printed body."""
        vm, at = self.peak(mask)
        out = dict(study=self.name, el_mm=self.el, nodes=self.nodes, elements=self.elements, solve_s=round(self.seconds),
                   peak_vm_all=round(float(self.vm.max()), 2), peak_vm_away=round(vm, 2), at=at,
                   sf_yield=round(yield_mpa / vm, 2) if vm > 0 else None, max_disp_mm=self.max_disp(),
                   reaction_N=self.reaction, applied_N=self.applied)
        if getattr(self, 'excessive', False):
            out['excessive_displacements'] = True
        return out


def _delete_feature(d, feat):
    d.ClearSelection2(True)
    if feat.Select2(False, 0):
        d.Extension.DeleteSelection2(0)
    d.ClearSelection2(True)


def _bearing_frame(fs, force, name):
    """(origin mm, unit force direction, unit axis) of a bearing load, or Failed: the faces must be cylinders about one
    axis and the force square to it."""
    force = np.array(force, float)
    axis = origin = None
    for f in fs:
        s = f.GetSurface
        if not s.IsCylinder:
            raise Failed(f'{name}: a bearing load takes cylindrical faces only')
        p = np.array(s.CylinderParams, float)
        o, a = p[:3] * 1e3, p[3:6] / np.linalg.norm(p[3:6])
        if axis is None:
            axis, origin = a, o
        elif abs(abs(a @ axis) - 1) > 1e-6 or np.linalg.norm(np.cross(o - origin, axis)) > 0.01:
            raise Failed(f'{name}: the faces of one bearing load must share one axis (give each bore its own load)')
    size = float(np.linalg.norm(force))
    if size == 0:
        raise Failed(f'{name}: a bearing load of zero')
    if abs(force @ axis) > 1e-3 * size:
        raise Failed(f'{name}: the force has {force @ axis:.3f} N along the bore axis, which a bearing load cannot carry: '
                     'give the axial part to another load')
    return origin, force / size, axis


def _bearing_csys(d, fs, force, name):
    """A coordinate system for a bearing load: Z along the faces' common axis, X along the force. Returns the feature.

    SolidWorks' bearing load takes its direction from a coordinate system whose Z is the bore axis. One is made here
    from numbers and read back, and static() deletes it with the study. Adding and deleting it leaves face objects
    valid (measured 2026-11-14). A feature of the same name left by a failed run is replaced.
    """
    origin, x, axis = _bearing_frame(fs, force, name)
    R = np.c_[x, np.cross(axis, x), axis]          # columns: the coordinate system's X, Y, Z in the model frame
    old = d.FeatureByName(name)
    if old is not None:
        _delete_feature(d, old)
    fm = d.FeatureManager
    fm._FlagAsMethod('CreateCoordinateSystemUsingNumericalValues')
    # the three angles are Euler angles whose order the documentation does not give: each order is tried and the
    # result read back, so a wrong guess can only fail, never point the load somewhere else
    for seq in ('xyz', 'XYZ', 'zyx', 'ZYX'):
        with warnings.catch_warnings():            # gimbal lock only means one of several equal answers is taken
            warnings.simplefilter('ignore')
            ang = dict(zip(seq.lower(), Rotation.from_matrix(R).as_euler(seq)))
        cs = fm.CreateCoordinateSystemUsingNumericalValues(True, origin[0] / 1e3, origin[1] / 1e3, origin[2] / 1e3, True,
                                                           float(ang['x']), float(ang['y']), float(ang['z']))
        if cs is None:
            continue
        T = np.array(d.Extension.GetCoordinateSystemTransformByName(cs.Name).ArrayData, float)
        if np.abs(T[0:3] - x).max() < 1e-6 and np.abs(T[6:9] - axis).max() < 1e-6:
            cs.Name = name
            return cs
        _delete_feature(d, cs)
    raise Failed(f'{name}: no coordinate system could be made with X along {x.round(4).tolist()} and Z along '
                 f'{axis.round(4).tolist()}')


@contextlib.contextmanager
def heavy_solve_lock(owner, wait_s=3600):
    """Hold the machine-wide lock for one heavy solve (over HEAVY_NODES). One such solve at a time on holly-pc.

    The lock is a file created exclusively, holding `owner=<thread> pid=<pid> start=<time>` (write it in this form in
    your own scripts too). A lock whose PID is dead, or that names no PID and is three hours old, is stale and is replaced; a live one is waited for (the other solve takes 7 to 11 minutes), up to wait_s, then Failed.
    static() takes it by itself; meshing, builds and post-processing need none.
    """
    t0 = time.time()
    while True:
        try:
            fd = os.open(HEAVY_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                text = HEAVY_LOCK.read_text()
                m = re.search(r'pid\W{0,3}(\d+)', text, re.I)
                pid = int(m.group(1)) if m else None
                old = time.time() - HEAVY_LOCK.stat().st_mtime > 3 * 3600
            except Exception:      # noqa: BLE001  being written, or gone again: treat as held
                text, pid, old = '?', None, False
            if pid is None and old:            # no PID to test and three hours old: no solve takes that long
                pid = -1
            if pid is not None and (pid < 0 or not psutil.pid_exists(pid)):
                log(f'heavy solve lock is stale ({text.strip()}): replacing it')
                try:
                    HEAVY_LOCK.unlink()
                except OSError:
                    pass
                continue
            if time.time() - t0 > wait_s:
                raise Failed(f'heavy solve lock held for over {wait_s} s by {text.strip()}') from None
            log(f'waiting for the heavy solve lock: {text.strip()}')
            time.sleep(20)
    try:
        os.write(fd, f'owner={owner} pid={os.getpid()} start={time.strftime("%Y-%m-%dT%H:%M:%S")}\n'.encode())
        os.close(fd)
        yield
    finally:
        try:
            HEAVY_LOCK.unlink()
        except OSError:
            pass


def static(j, d, name, material, fixtures, loads, el, ctrl=(), contacts=(), materials=None, solver=None, keep_study=False,
           post=None, loose_ok=False, max_nodes=MAX_NODES):
    """Build, mesh and solve one linear static study on the open part d, and read the nodal results back.

    material: the dict for every body, unless materials = {part of a body's name: dict} picks some bodies out. A key
    matches a body when the body's Simulation name contains it, whatever the case; that name is "SolidBody 3(PAD)" for
    a body made in the part and "SolidBody 2(<pad>-<PAD>)" for one brought in from pad.SLDPRT. A key that matches no
    body, or a body matched by two keys, raises, and each body's material is logged.
    [('bearing', faces, (Fx, Fy, Fz) N)] is a pin or shaft pressing on a bore: cylindrical faces about one axis, the
    force square to that axis. Only the half of the bore the force points at is loaded, heaviest where it points
    (peak 4 F / (pi d t)), and nothing holds the faces rigid. No contact, no clearance: playbook/05-fea.md.
    fixtures: [('fixed' | 'hinge', faces)]. loads: [('normal', faces, newtons)] presses on the faces along their own
    normals with that many newtons IN TOTAL, shared between the faces by area (one even pressure; positive pushes into
    the material). [('remote', faces, (x, y, z) mm, (Fx, Fy, Fz) N, (Mx, My, Mz) N.m)] applies a force and moment at a
    point in the model frame, carried to the faces rigidly.
    el: global element size mm. ctrl: [(faces, size mm)] local mesh controls.
    contacts: [(NO_PENETRATION | BONDED, faces_a, faces_b)] for multi-body parts; everything else touching is bonded.
    solver: None leaves Automatic; SOLVER_DIRECT sets direct sparse through a macro (needed for no-penetration contact).
    loose_ok: when the solver reports excessive displacements (a body free to move, or held only by something very
    soft) static() raises, unless loose_ok=True, which returns the result with Result.excessive set.
    post: post(study, results) is called after the solve and before the study is deleted, for anything static() does
    not read itself; what it returns is kept as Result.extra.
    Every face list must be non-empty: an empty pick is the commonest way to solve the wrong problem.
    """
    t0 = time.time()
    cw = j.simulation()
    doc = cw.ActiveDoc
    if doc is None:
        raise Failed('Simulation sees no active document: open_doc() the model before static()')
    for ld in loads:                                   # refused before a study exists, so nothing is left in the model
        if ld[0] == 'bearing' and ld[1]:
            _bearing_frame(ld[1], ld[2], name)
    sm = doc.StudyManager
    err = L()
    tag = re.sub(r'[^A-Za-z0-9_ -]', '_', name)[:24]     # a dot in a study name fails with error 2 (2026-11-13)
    st = sm.CreateNewStudy3(tag, 0, 0, err)            # 0 static, 0 solid mesh
    if st is None or err.value:
        raise Failed(f'study not created ({err.value}); a study of the same name already in the model?')
    comp = st.SolidManager.GetComponentAt(0, L())
    named = [(b, str(call(b, 'SolidBodyName'))) for b in (comp.GetSolidBodyAt(k, L()) for k in range(comp.SolidBodyCount))]
    hits = {bname: [key for key in (materials or {}) if key.lower() in bname.lower()] for _, bname in named}
    unused = sorted(set(materials or {}) - {key for hit in hits.values() for key in hit})
    twice = {bname: hit for bname, hit in hits.items() if len(hit) > 1}
    if unused or twice:
        sm.DeleteStudy(tag)                        # or the corrected call cannot make a study of this name
        if twice:
            raise Failed(f'{name}: a body matches more than one materials key: {twice}')
        raise Failed(f'{name}: materials keys {unused} match no body. The bodies are: {[bname for _, bname in named]}')
    for b, bname in named:
        mat = materials[hits[bname][0]] if hits[bname] else material
        _material(b, mat)
        if materials:
            log(f'{name}: body "{bname}" is {mat["name"]}')
    lbc = st.LoadsAndRestraintsManager
    fixed, loaded, applied, temps = [], [], 0.0, []
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
        elif ld[0] == 'bearing':
            f = np.array(ld[2], float)
            cs = _bearing_csys(d, fs, f, f'BEARING_{tag}_{len(temps)}'.replace(' ', '_'))
            temps.append(cs)
            b = lbc.AddBearingLoad(cs, fs, err)
            if b is None or err.value:
                raise Failed(f'{name}: bearing load failed ({err.value}): faces must be cylinders about one axis')
            call(b, 'BearingLoadBeginEdit')
            b.BearingLoadUnit = 0                  # N
            b.Direction = BEARING_X                # along the coordinate system's X, which _bearing_csys laid on the force
            b.XDirectionValue = float(np.linalg.norm(f))
            b.XDirectionReverse = False
            b.DistributionType = ld[3] if len(ld) > 3 else BEARING_SINE
            rc = call(b, 'BearingLoadEndEdit')
            if rc:
                raise Failed(f'{name}: bearing load not accepted ({rc})')
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
    if nodes > max_nodes:      # checked before the solve: pass a smaller max_nodes to hold a job to a budget
        raise Failed(f'{name}: {nodes} nodes is over {max_nodes}: coarsen the global size and keep the local controls')
    if solver is not None:
        log(f'{name}: solver macro:', solver_macro(j, d, tag, solver, Path(d.GetPathName).parent).replace('\n', ' | '))
    stop, seen = threading.Event(), []
    watch = threading.Thread(target=_solver_dialogs, args=(j.inst.pid, stop, seen), daemon=True)
    watch.start()
    lock = heavy_solve_lock(f'{Path(d.GetPathName).stem}/{name}') if nodes > HEAVY_NODES else contextlib.nullcontext()
    try:
        with lock:
            rc = call(st, 'RunAnalysis')
    finally:
        stop.set()
        watch.join(5)
    excessive = any(k == 'excessive' for k, _ in seen)
    if excessive and not loose_ok:
        try:
            sm.DeleteStudy(tag)                    # or the next run cannot make a study of this name
        except Exception as ex:      # noqa: BLE001
            log(f'{name}: study not deleted ({str(ex)[:80]})')
        raise Failed(f'{name}: the solver reported excessive displacements: a body is free to move, or held only by '
                     'something very soft. playbook/05-fea.md, "Contact between bodies"')
    if any(k == 'noconverge' for k, _ in seen):    # the solver still writes a result, with a clean reaction: never read it
        raise Failed(f'{name}: the contact iteration did not converge ("Failure to achieve equilibrium"): a body with '
                     'nothing to decide which way it goes. Move the pads, or load it the way that seats it. '
                     'playbook/05-fea.md, "Contact between bodies"')
    other = [t for k, t in seen if k in ('notice', 'unanswered')]
    if other:                                      # e.g. "Fixture transfer failed": whatever came back was not the model asked for
        raise Failed(f'{name}: the solver raised a dialog this helper does not know, so the result is not valid: '
                     f'{other[0][:300]}')
    res = st.Results
    if rc or res is None:
        raise Failed(f'{name}: solve failed ({rc}). 24 is a singular model (a body free to move) or out of memory: '
                     'playbook/05-fea.md, "When the solve fails"')
    raw = _arr(call(mesh, 'GetNodes'), 4)
    xyz = dict(zip(raw[:, 0].astype(int), raw[:, 1:] * 1000))
    s = _stress_by_body(d, res, set(xyz), name)
    if s is None:
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
    for label, pts in (('fixture', fixed_pts), ('load', loaded_pts)):      # a wrong face shows here before it shows anywhere
        if pts is not None and len(pts):
            log(f'{name}: {label} nodes {len(pts)}, box {pts.min(axis=0).round(2).tolist()} to {pts.max(axis=0).round(2).tolist()}')
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
        for cs in temps:                           # the bearing loads' coordinate systems go with the study
            _delete_feature(d, cs)
    # A document closed unsaved after a study and opened again in the same instance fails its next solve at once with
    # error 24, the solver stopping while it loads its input (selftest beam then loads, 2026-11-12). Saved, it does not.
    _save_as_is(d)
    r = Result(name, el, pos, s, fixed_pts, loaded_pts, disp, reaction, nodes, elements, time.time() - t0, applied)
    r.extra, r.excessive = extra, excessive
    return r


def converge(run, sizes, tol=0.05, layers=None, mask=None):
    """Solve at each element size in turn (coarse to fine) until the peak away from fixtures moves by under tol.

    run(el) -> Result. Returns the list of (el, nodes, peak) rows and whether it converged. With layers = the print
    layer normal, each row also carries the tension across layers and the shear between them, and both must settle
    too. mask(r) -> a node mask, to follow one body of several; it is combined with the exclusion distance. The peak is taken outside the
    same distance from fixtures and loads at every size (two of the coarsest elements), which can cover a real peak
    beside a fixture: read such a feature yourself with in_box() at each size. At least three sizes are always solved:
    two rows that agree can stop before a slow climb shows. A peak that keeps climbing as
    the mesh shrinks is a singularity (a sharp re-entrant corner or a fixture edge), not a stress: change the geometry
    (add the real fillet) or the mask, do not report the last number.
    """
    rows = []
    dist = 2.0 * max(sizes)       # one exclusion distance for the whole series, set by the coarsest mesh
    for el in sizes:
        r = run(el)
        keep = r.away(dist=dist)
        if mask is not None:
            keep &= mask(r)
        row = (el, r.nodes, round(r.peak(keep)[0], 2))
        rows.append(row if layers is None else row + (round(r.layer_stress(layers, keep)[0], 2),
                                                      round(r.layer_shear(layers, keep)[0], 2)))
        log('converge', rows[-1])
        if len(rows) > 2 and all(abs(a - b) <= tol * abs(b) for a, b in zip(rows[-1][2:], rows[-2][2:])):
            return rows, True
    return rows, False


def judge(series, limits, need=2.0, tol=0.05):
    """The verdict of a study series, worked out the same way every time. Returns a dict.

    series: {entry: [value at the coarsest mesh, ..., value at the finest]} in MPa, peak magnitudes (zero or more),
    one entry for every measure and, on a model of several bodies or load cases, for every body and case
    ('lower half, +X, layer shear'). Only cases the part must carry: a bonded twin run to prove a contact is not one.
    Only real stresses: a peak that climbs without end at a fixture edge or a sharp corner is not one (converge()).
    limits: {entry: allowable MPa} with the same keys. need: the factor required. tol: as in converge().

    For each entry: factor = limit / finest value; step = the last change as a share of the value before it, as
    converge() measures it. An entry is settled (converged) when it has at least three values and either that step is
    at or under tol, or the last change is at or under tol * limit / need in MPa: with the defaults, 5 % of the
    stress the part is allowed at the factor asked for (1.1 MPa of von Mises against 45, 0.56 of layer tension
    against 22.5, 0.33 of shear against 13). That floor is there so that a small stress which moves by a large share
    of itself (0.9 to 0.7 MPa is 21 %) does not hold up a verdict it cannot change. It is a rule for the verdict, not
    for how well a number is known: a value that has to be reported to 5 % is still checked against itself. The
    lowest factor is taken over every entry, so it cannot be read from the wrong row. verdict is the worst state of
    any entry:
      'fail'                    its factor is under need, settled or not
      'not shown'               it still moves and its step is growing, or the margin does not cover the movement
                                (below), or it has under three values
      'margin, not converged'   it still moves, its last step is no larger than the one before, and it would be at
                                or over need after two more refinements. Not a pass: the report says which entry
                                moves and by how much. Not a fail either
      'pass'                    settled and at or over need
    The margin: an entry that fell at every step is taken at its finest value. Any other is taken as rising by the
    last step twice more, last * (1 + step)^2, whichever way the last step went: a series that has gone both ways
    (contact pressure does) can come back up by as much as it moved. At a sharp corner, where each refinement adds
    about the same share, that is what two more refinements of the same ratio would read; a peak that is settling
    stays under it.
    A growing step: the last step is larger than the step before it, and the entry did not fall at every step. Two
    more steps of the last size is then not a fair reading, because the series itself says the next one will be
    larger, and three values give no rate to project with: 2.02, 2.43, 3.12 MPa against 13 reads 2.53 after two
    steps of the same size and 1.92 if the steps go on growing as they did. Such an entry is 'not shown' whatever
    its factor, its row has step_growing True, and the log line says where to look. It is the mark of a peak the
    mesh has only begun to see: a sharp edge, or the edge of a contact where another body's corner bears. A finer
    mesh does not settle it; give the edge its radius, or read the stress 1 mm away from it (07-done.md).
    """
    if not series or set(series) != set(limits):
        raise Failed(f'judge: series and limits must have the same keys, at least one: {sorted(set(series) ^ set(limits))}')
    rows, lowest = [], None

    def share(a, b):                     # the change from a to b as a share of a, as converge() measures it
        return abs(b - a) / a if a else (0.0 if b == 0 else float('inf'))

    def shown(f):                        # json has no infinity: an entry with no stress has no factor
        return None if f is None or f == float('inf') else round(f, 2)

    def pct(s):
        return None if s is None or s == float('inf') else round(100 * s, 1)

    for key, vals in series.items():
        vals, limit = [float(v) for v in vals], float(limits[key])
        if not vals or not all(v >= 0 for v in vals) or not limit > 0:     # written so that nan is refused too
            raise Failed(f'judge: "{key}" needs at least one value, none negative, and a limit over zero: {vals}, {limit}')
        last = vals[-1]
        step = share(vals[-2], last) if len(vals) > 1 else None
        before = share(vals[-3], vals[-2]) if len(vals) > 2 else None
        floor = tol * limit / need
        conv = len(vals) >= 3 and (step <= tol or abs(last - vals[-2]) <= floor)
        fell = all(b <= a for a, b in zip(vals, vals[1:]))
        growing = len(vals) >= 3 and not conv and not fell and step > before * (1 + 1e-9)
        projected = last if step is None or fell else last * (1 + step) ** 2
        factor = limit / last if last else float('inf')
        f_proj = limit / projected if projected else float('inf')
        if factor < need:
            state = 'fail'
        elif conv:
            state = 'pass'
        elif len(vals) >= 3 and not growing and f_proj >= need:
            state = 'margin, not converged'
        else:
            state = 'not shown'
        if lowest is None or factor < lowest[0]:
            lowest = (factor, key)
        rows.append(dict(entry=key, values=vals, limit=limit, factor=shown(factor), converged=conv,
                         last_step_pct=pct(step), step_before_pct=pct(before),
                         last_change_mpa=None if len(vals) < 2 else round(abs(last - vals[-2]), 3),
                         settled_under_mpa=round(floor, 3), step_growing=growing,
                         factor_after_two_more_steps=shown(f_proj), state=state))
    order = ['fail', 'not shown', 'margin, not converged', 'pass']
    verdict = min((r['state'] for r in rows), key=order.index)
    out = dict(verdict=verdict, need=need, lowest_factor=shown(lowest[0]), lowest_entry=lowest[1], rows=rows)
    log(f'judge: {verdict}; lowest factor {out["lowest_factor"]} at "{lowest[1]}"')
    for r in rows:
        if r['state'] == 'pass':
            continue
        if len(r['values']) < 3:
            why = f'only {len(r["values"])} of the three sizes'
        elif r['step_growing']:
            why = (f'last step {r["last_step_pct"]} % after {r["step_before_pct"]} %: the step is growing, the mark of a '
                   f'sharp edge or of a contact edge where the corner of another body bears. Find where the peak is, '
                   f'then round the edge or read 1 mm away from it; a finer mesh will not settle it')
        else:
            why = f'last step {r["last_step_pct"]} %, factor after two more {r["factor_after_two_more_steps"]}'
        log(f'judge:   {r["state"]}: "{r["entry"]}" factor {r["factor"]}, {why}')
    return out


def body_named(d, part):
    """The solid body whose name contains part (insert_body names a body "<file>-<its name in that file>")."""
    hit = [b for b in solid_bodies(d) if part.lower() in b.Name.lower()]
    if len(hit) != 1:
        raise Failed(f'{len(hit)} bodies match "{part}": {[b.Name for b in solid_bodies(d)]}')
    return hit[0]
