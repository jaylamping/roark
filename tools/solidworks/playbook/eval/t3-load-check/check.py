"""T3 load model check: the same bracket and mesh, three ways of putting 150 N along +X into it.

    python check.py [a] [b] [c]          # all three when none is named

  a  rigid remote load at the bore centre, carried rigidly to the bore wall (what fable-playbook/t3.py does)
  b  150 N in total along +X as an even traction on the bore wall (what sonnet-bare/t3_study.py does)
  c  150 N in total along +X shared over the four dia 3.4 hole walls, bore free (where the motor screws put it)

Each at global 3 mm with a mesh control on the four dia 3.4 hole walls at 0.8, 0.4 and 0.25 mm, nothing else refined,
so the three cases differ in the load only. Four base hole walls fixed. Writes rows.json beside this file and the nodal
results to cad/_sim/sw-eval/check/.
"""
import hashlib
import json
import math
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
WT = HERE.parents[4]
sys.path.insert(0, str(WT / 'tools' / 'solidworks'))
from swfea import (MAX_NODES, PETG, SOLVER_DIRECT, Result, _arr, _material, _save_as_is, _solver_dialogs,  # noqa: E402
                   solver_macro)
from swkit import NUL, Failed, L, call, close, expect, free_gb, job, log, open_doc, pick, volume  # noqa: E402

OUT = WT / 'cad' / '_wip' / 'sw-eval' / 'check'
SIM = WT / 'cad' / '_sim' / 'sw-eval' / 'check'
SRC = Path(r'J:\code\roark-wt\sw-eval-fable\cad\_wip\sw-eval\fable-playbook\bracket.SLDPRT')
F = 150.0
BORE = (25.0, 28.0)                                    # (Y, Z)
HOLES = [(BORE[0] + 15.5 * math.cos(math.radians(a)), BORE[1] + 15.5 * math.sin(math.radians(a))) for a in (45, 135, 225, 315)]
R_HOLE, RIM = 1.7, 1.2                                 # dia 3.4 walls; "at the hole" is within 1.2 mm of the wall
EXCL = 6.0                                             # mm from the fixed hole walls, the same at every mesh
GLOBAL, LOCALS = 3.0, (0.8, 0.4, 0.25)


def beat(status, pid=None):
    cmd = [sys.executable, str(WT / 'tools' / 'pc' / 'claims.py'), 'beat', 'sw-eval-check', '--status', status]
    subprocess.run(cmd + (['--sw-pid', str(pid)] if pid else []), capture_output=True)


def study(j, d, name, case, local):
    """One solve, with the calls of swfea.static() plus a directional force (which static() does not have)."""
    t0 = time.time()
    doc = j.simulation().ActiveDoc
    sm = doc.StudyManager
    err = L()
    st = sm.CreateNewStudy3(name, 0, 0, err)
    if st is None or err.value:
        raise Failed(f'study not created ({err.value})')
    comp = st.SolidManager.GetComponentAt(0, L())
    for k in range(comp.SolidBodyCount):
        _material(comp.GetSolidBodyAt(k, L()), PETG)
    fixed = pick(d, kind='cyl', r=2.75, inside=[15, 0, -0.1, 75, 50, 6.1])
    bore = pick(d, kind='cyl', r=11.0)
    motor = pick(d, kind='cyl', r=R_HOLE)
    expect('fixed hole walls', len(fixed), 4, 0)
    expect('bore faces', len(bore), 1, 0)
    expect('motor hole walls', len(motor), 4, 0)
    lbc = st.LoadsAndRestraintsManager
    err = L()
    lbc.AddRestraint(0, list(fixed), NUL, err)
    if err.value:
        raise Failed(f'fixture failed ({err.value})')
    if case == 'a':
        loaded = bore
        err = L()
        r = lbc.AddRemoteLoad(1, list(bore), 0, 3.0, BORE[0], BORE[1], err)
        call(r, 'RemoteLoadBeginEdit')
        r.ConnectionType = 0                           # rigid
        r.ForceUnit = 0
        r.MomentUnit = 0
        r.SetForceOrTranslationValues2(True, True, F, False, 0.0, False, 0.0)
        r.SetMomentOrRotationValues2(False, False, 0.0, False, 0.0, False, 0.0)
        if call(r, 'RemoteLoadEndEdit') or err.value:
            raise Failed('remote load not accepted')
    else:
        loaded = bore if case == 'b' else motor
        ref = d.FeatureByName('Right Plane')           # normal along X
        if ref is None:
            raise Failed('no Right Plane')
        areas = [call(f, 'GetArea') for f in loaded]
        for f, a in zip(loaded, areas):                # one call per face with its share, so the total is certain
            err = L()
            fo = lbc.AddForce2(0, 0, [f], ref, err)
            if fo is None or err.value:
                raise Failed(f'force failed ({err.value})')
            call(fo, 'ForceBeginEdit')
            fo.Unit = 0
            fo.SetForceComponentValues2(False, False, True, 0.0, 0.0, F * a / sum(areas))
            if call(fo, 'ForceEndEdit'):
                raise Failed('force not accepted')
    mesh = st.Mesh
    mesh.Quality = 1
    q = mesh.ApplyMeshControl(list(motor), L())
    q = q[0] if isinstance(q, tuple) else q
    call(q, 'MeshControlBeginEdit')
    q.Units = 0
    q.ElementSize = local
    q.Ratio = 1.5
    call(q, 'MeshControlEndEdit')
    rc = st.CreateMesh(0, GLOBAL, GLOBAL * 0.05)
    nodes, elements = int(mesh.NodeCount), int(mesh.ElementCount)
    log(f'{name}: mesh rc {rc}, {nodes} nodes, free {free_gb():.1f} GB')
    if rc or not nodes or nodes > MAX_NODES:
        raise Failed(f'{name}: mesh rc {rc}, {nodes} nodes')
    # Direct sparse on every run, so the solver is the same at every mesh (Automatic changes to the iterative one as the
    # mesh grows). The solver asks "Excessive displacements detected" on the finer meshes with either solver (2.3 to
    # 2.8 mm on a 46 mm part): the watcher of swfea.static() answers No, which returns the linear result.
    log(f'{name}: solver macro:', solver_macro(j, d, name, SOLVER_DIRECT, OUT).split())
    stop, seen = threading.Event(), []
    watch = threading.Thread(target=_solver_dialogs, args=(j.inst.pid, stop, seen), daemon=True)
    watch.start()
    try:
        rc = call(st, 'RunAnalysis')
    finally:
        stop.set()
        watch.join(5)
    if any(k != 'excessive' for k, _ in seen):
        sm.DeleteStudy(name)
        raise Failed(f'{name}: the solver put up a dialog: {seen}')
    asked = bool(seen)       # "Excessive displacements", answered No: the linear result, checked below like any other
    res = st.Results
    if rc or res is None:
        raise Failed(f'{name}: solve failed ({rc})')
    raw = _arr(call(mesh, 'GetNodes'), 4)
    xyz = dict(zip(raw[:, 0].astype(int), raw[:, 1:] * 1000))
    s = _arr(res.GetStress(0, 1, NUL, 3, L()), 12)
    pos = np.array([xyz[int(i)] for i in s[:, 0]])

    def face_nodes(fs):
        qq = _arr(res.GetStressForEntities2(True, 9, 1, NUL, list(fs), 3, L()), 2)
        return np.array([xyz[int(i)] for i in qq[:, 0] if int(i) in xyz])

    fixed_pts, loaded_pts = face_nodes(fixed), face_nodes(loaded)
    for label, pts in (('fixture', fixed_pts), ('load', loaded_pts)):
        log(f'{name}: {label} nodes {len(pts)}, box {pts.min(axis=0).round(2).tolist()} to {pts.max(axis=0).round(2).tolist()}')
    disp = _arr(res.GetTranslationalDisplacement(1, NUL, 0, L()), 5)
    qq = _arr(res.GetReactionForcesAndMoments(0, NUL, 0, L()), 9)
    f = qq[:, 1:4].sum(axis=0)
    reaction = [round(float(v), 3) for v in f] + [round(float(np.linalg.norm(f)), 3)]
    sm.DeleteStudy(name)
    _save_as_is(d)
    r = Result(name, GLOBAL, pos, s, fixed_pts, loaded_pts, disp, reaction, nodes, elements, time.time() - t0, F)
    r.excessive = asked
    return r


def top(v, mask, pos):
    i = np.flatnonzero(mask)[np.argmax(v[mask])]
    return round(float(v[i]), 2), pos[i].round(2).tolist()


def score(r, case, local):
    p, sz, vm = r.pos, r.s[:, 3], r.vm
    d_fix = cKDTree(r.fixed_pts).query(p)[0]
    d_load = cKDTree(r.loaded_pts).query(p)[0]
    d_hole = np.min([np.hypot(p[:, 1] - y, p[:, 2] - z) for y, z in HOLES], axis=0) - R_HOLE
    d_bore = np.hypot(p[:, 1] - BORE[0], p[:, 2] - BORE[1]) - 11.0
    upright = p[:, 0] <= 6.01
    keep = d_fix >= EXCL                                # the only exclusion used for "overall"
    rim = upright & (d_hole <= RIM)
    row = dict(case=case, local_mm=local, nodes=r.nodes, reaction_n=r.reaction, max_disp_mm=round(r.max_disp(), 3),
               solve_s=round(r.seconds), solver='direct sparse', asked_excessive=r.excessive)
    row['vm'], row['vm_at'] = top(vm, keep, p)
    row['sz'], row['sz_at'] = top(sz, keep, p)
    row['rim_sz'], row['rim_sz_at'] = top(sz, rim, p)
    row['rim_vm'], row['rim_vm_at'] = top(vm, rim, p)
    # the rim value on each face of the upright, and off the hole wall itself (in case c the wall is the loaded face)
    for nm, m in (('rim_sz_x0', rim & (p[:, 0] < 0.01)), ('rim_sz_x6', rim & (p[:, 0] > 5.99)),
                  ('rim_sz_off_wall', rim & (d_hole > 0.05))):
        row[nm], row[nm + '_at'] = top(sz, m, p)
    # what the earlier runs' masks leave: swfea Result.away() (two global elements from fixture AND load faces),
    # fable-playbook series.masks "mine" (two elements from the fixed walls, 1.5 mm from the bore wall)
    away = (d_fix >= 2 * GLOBAL) & (d_load >= 2 * GLOBAL)
    mine = (d_fix >= 2 * GLOBAL) & (d_bore >= 1.5)
    row['sz_mask_away'], row['sz_mask_away_at'] = top(sz, away, p)
    row['vm_mask_away'], row['vm_mask_away_at'] = top(vm, away, p)
    row['sz_mask_bore15'], row['sz_mask_bore15_at'] = top(sz, mine, p)
    row['vm_mask_bore15'], row['vm_mask_bore15_at'] = top(vm, mine, p)
    row['rim_nodes'] = int(rim.sum())
    row['rim_nodes_left_by_away'] = int((rim & away).sum())
    row['rim_nodes_left_by_bore15'] = int((rim & mine).sum())
    # away from holes: the back face of the upright between the fillet top and the lowest holes, and the plain section
    back = (p[:, 0] < 0.01) & (p[:, 2] >= 8) & (p[:, 2] <= 12)
    row['back_z8_12_sz'], row['back_z8_12_sz_at'] = top(sz, back, p)
    strip = np.abs(p[:, 2] - 12.0) < 1.0
    row['section_z12_back_sz'] = round(float(sz[strip & (p[:, 0] < 0.01)].mean()), 2)
    row['section_z12_hand'] = round(F * (BORE[1] - 12.0) * 3 / (50 * 6 ** 3 / 12), 2)
    row['bore_edge_sz'], row['bore_edge_sz_at'] = top(sz, upright & (d_bore <= 1.5), p)
    row['vm_unmasked'], row['vm_unmasked_at'] = top(vm, np.ones(len(p), bool), p)
    return row


def main():
    cases = [c for c in sys.argv[1:] if c in 'abc'] or ['a', 'b', 'c']
    OUT.mkdir(parents=True, exist_ok=True)
    SIM.mkdir(parents=True, exist_ok=True)
    part = OUT / 'bracket.SLDPRT'
    if not part.exists():
        shutil.copy2(SRC, part)                        # a copy: the original belongs to another session
    log('model', part, 'sha256', hashlib.sha256(part.read_bytes()).hexdigest())
    # predictions (07-done.md): 25,000 to 120,000 nodes (sonnet-bare's local series on the same faces), displacement
    # 2.0 mm by hand (2.4 to 2.7 in the earlier runs), peaks at a dia 3.4 hole rim or the inside fillet
    log('predict: nodes 25k to 120k, max displacement 2 to 3 mm, peak at a dia 3.4 rim or the fillet; reaction -150 N in X')
    rows_file = HERE / 'rows.json'
    rows = json.loads(rows_file.read_text()) if rows_file.exists() else []
    with job() as j:
        beat('T3 load check', j.inst.pid)
        j.simulation()
        for case in cases:
            for local in LOCALS:
                name = f'CHK_{case}_{int(local * 100):03d}'
                d = open_doc(j.sw, part)
                d.ForceRebuild3(False)
                if not rows:
                    expect('bracket volume', volume(d), 32974.0, 3.0 / 32974.0)
                r = study(j, d, name, case, local)
                close(j.sw, d)
                expect(f'{name} reaction Fx', r.reaction[0], -F, 0.01)
                if not 25_000 / 2 <= r.nodes <= 120_000 * 2 or not 2.0 / 3 <= r.max_disp() <= 3.0 * 3:
                    raise Failed(f'{name}: nodes {r.nodes} or displacement {r.max_disp()} far from the prediction')
                np.savez_compressed(SIM / f'{name}.npz', pos=r.pos, s=r.s, disp=r.disp, reaction=r.reaction,
                                    fixed=r.fixed_pts, loaded=r.loaded_pts)
                row = score(r, case, local)
                rows = [x for x in rows if (x['case'], x['local_mm']) != (case, local)] + [row]
                rows_file.write_text(json.dumps(rows, indent=1))
                log('ROW', json.dumps(row))
                beat(f'T3 load check {name} done', j.inst.pid)
    log('DONE')


if __name__ == '__main__':
    main()
