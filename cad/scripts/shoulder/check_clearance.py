"""Running clearances of the left shoulder CAD (first pass), at the brief's poses and over each joint's travel.

    python check_clearance.py [quick]

Reads the STL/STEP exports of the SolidWorks parts (cad/_wip/shoulder-pass1/{stl,step}), the vendor motors placed as in
build_asm.py, the torso corner and the frozen upper arm. Surfaces are sampled at about 0.7 mm (frame and arm 1.0 mm) and
compared with KD-trees (distances good to about +-0.4 mm), as in the measurement study. Motor rotors are split off their
stators, so a part bolted to an output is not reported as touching it.
Writes cad/_wip/shoulder-pass1/clearance.json (CLEAR_JSON: another name).

The roll stop is the fork rear's tooth in the rear cap's arc slot (dims.STOP_SLOT). The tooth and the slot's two end faces
are split off their parts as 'stop_tooth' and 'stop_ends': their contact is the stop and is reported on its own, so a rub
between the rear cap and the fork rear anywhere else shows in the list. Poses beyond the stops are evaluated for the stop
section only and never count toward the minimum over travel.

How it runs: the poses are spread over a process pool (cores minus 2; CLEAR_WORKERS: another count). A pair's distance
depends only on the joints between its two groups (pitch-to-roll parts on roll alone, and so on), so each pair is evaluated
once per distinct set of those angles. The smaller cloud of a pair is queried into the larger one's tree, every sample of
it. Sampling is seeded, so a repeat run on the same files gives the same numbers. Sampled STEP parts are cached in
cad/_wip/shoulder-pass1/clearance_cache by file hash (CLEAR_NO_CACHE=1: off).
Inputs: FRAME_STEP, the rev A frame (torso_frame.step); a missing input stops the run with its path.
"""
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

import clearance_worker as CW

QUICK = len(sys.argv) > 1 and sys.argv[1] == 'quick'
if mp.current_process().name == 'MainProcess':
    # not in a pool worker: on Windows a worker imports this file again, and needs none of the CAD libraries (about 250 MB
    # and some seconds each)
    import cadquery as cq
    import trimesh

    from build_asm import T_ROLL_RS03, T_RS02, pose_matrix
    from dims import *
    from swk import CAD, VENDOR, WIP

    STL = WIP / os.environ.get('CLEAR_STL', 'stl')   # CLEAR_STL: another STL set (e.g. a before / after pair)
    UA = CAD / 'reference' / 'shoulder'
    CACHE = WIP / 'clearance_cache'
BOUND = CW.BOUND
INPUTS = {}      # name -> (path, sha256) of every file read, for the result file


def need(path, what):
    """The input file, or a stop that names it."""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f'check_clearance: file not found: {p}  ({what})')
    return p


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def note_input(name, path):
    INPUTS[name] = dict(path=str(path), sha256=sha(path))
    return INPUTS[name]['sha256']


def cached(name, path, params, make):
    """make() -> point array, kept in CACHE under the file's hash and the parameters."""
    h = note_input(name, path)
    if os.environ.get('CLEAR_NO_CACHE'):
        return make()
    key = hashlib.sha256((h + repr(params)).encode()).hexdigest()[:20]
    f = CACHE / f'{name}_{key}.npy'
    if f.exists():
        return np.load(f)
    pts = make()
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(f, pts)
    return pts


def mesh_step(path, M=None, tol=0.15):
    s = cq.importers.importStep(str(need(path, 'STEP part')))
    vs, fs, o = [], [], 0
    for so in s.solids().vals():
        v, f = so.tessellate(tol, 0.3)
        v = np.array([(p.x, p.y, p.z) for p in v])
        vs.append(v); fs.append(np.array(f) + o); o += len(v)
    m = trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False)
    if M is not None:
        m.apply_transform(M)
    return m


def samp(m, sp):
    n = max(200, int(m.area / sp ** 2))
    p, _ = trimesh.sample.sample_surface_even(m, n, seed=1)
    return np.asarray(p)


def named_solids(path):
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.TDF import TDF_LabelSequence, TDF_Label
    from OCP.TDataStd import TDataStd_Name
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TopLoc import TopLoc_Location
    import cadquery as cq
    need(path, 'STEP assembly')
    doc = TDocStd_Document(TCollection_ExtendedString('d'))
    r = STEPCAFControl_Reader(); r.SetNameMode(True); r.ReadFile(str(path)); r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(l):
        a = TDataStd_Name()
        return a.Get().ToExtString() if l.FindAttribute(TDataStd_Name.GetID_s(), a) else '?'
    out = []

    def walk(lab, loc, nm):
        if st.IsAssembly_s(lab):
            seq = TDF_LabelSequence(); st.GetComponents_s(lab, seq)
            for i in range(1, seq.Length() + 1):
                c = seq.Value(i); ref = TDF_Label(); st.GetReferredShape_s(c, ref)
                walk(ref, loc.Multiplied(st.GetLocation_s(c)), name(c) if name(c) != '?' else name(ref))
            return
        out.append((nm if nm != '?' else name(lab), cq.Shape.cast(st.GetShape_s(lab).Moved(loc))))
    roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), name(roots.Value(i)))
    return out


def tess(shape, tol=0.3):
    v, f = shape.tessellate(tol, 0.3)
    return trimesh.Trimesh(np.array([(p.x, p.y, p.z) for p in v]), np.array(f), process=False)


FRAME_STEP = os.environ.get('FRAME_STEP', r'J:/code/_transfer/shoulder/torso_frame.step')   # holly-pc's path; set FRAME_STEP elsewhere


def frame_samples(path=None, sp=1.0):
    """Rev A frame (its own coordinates) moved -38 in X; pitch motor envelope and shell parts left out."""
    from build_asm import FRAME_SHIFT
    path = need(path or FRAME_STEP, 'rev A frame, torso_frame.step: set FRAME_STEP')
    out = []
    for nm, sh in named_solids(path):
        bb = sh.BoundingBox()
        if bb.xmax < 60 or bb.ymax < 250 or nm.split('__')[0] in ('actuator', 'shellpart') or nm.startswith('fastener__c1_'):
            continue
        m = tess(sh)
        if m.area > 0:
            out.append(samp(m, sp))
    if not out:
        raise SystemExit(f'check_clearance: no frame solid was read from {path}')
    return np.vstack(out) - np.array([FRAME_SHIFT, 0, 0])


def _ang(p):
    return np.degrees(np.arctan2(p[:, 1] - RY, p[:, 0] - RX)) % 360.0


def _adiff(a, b):
    return np.abs((a - b + 180.0) % 360.0 - 180.0)


def split_stop(P):
    """The stop's two halves off their parts: the fork rear's tooth, and the two end faces of the rear cap's arc slot."""
    ss = STOP_SLOT
    f = P['fork_rear']
    r = np.hypot(f[:, 0] - RX, f[:, 1] - RY)
    tooth = ((f[:, 2] > HOUSE_Z0 + 0.05) & (r > ss['tooth_r'][0] - 0.5) & (r < ss['tooth_r'][1] + 0.5)
             & (_adiff(_ang(f), ss['tooth_angle']) < ss['tooth_half'] + 1.5))
    P['stop_tooth'], P['fork_rear'] = f[tooth], f[~tooth]
    c = P['cap']
    r = np.hypot(c[:, 0] - RX, c[:, 1] - RY)
    a = _ang(c)
    a_in = ss['tooth_angle'] - ss['tooth_half'] + ROLL_STOP_IN          # the slot's end the tooth meets at the inward stop
    a_out = ss['tooth_angle'] + ss['tooth_half'] + ROLL_STOP_OUT        # and at the outward stop
    # the end faces themselves (within 0.75 deg of each end), and the rim of the rear face beside each end (6 deg): the tooth
    # passes through the plate there, so that rim lies against the tooth's flank at the stop as the end face does
    near = np.minimum(_adiff(a, a_in), _adiff(a, a_out))
    ends = ((c[:, 2] > CAP_Z1 - 0.05) & (c[:, 2] < ss['z_floor'] - 0.05) & (r > ss['r'][0] - 0.3) & (r < ss['r'][1] + 0.3)
            & ((near < 0.75) | ((c[:, 2] < CAP_Z1 + 0.06) & (near < 6.0))))
    P['stop_ends'], P['cap'] = c[ends], c[~ends]


def load():
    t0 = time.time()
    P = {}
    for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'hub', 'cover', 'port_cap'):   # fork cap dropped (look option a)
        f_ = need((WIP / os.environ['PART_STL_DIR'] if k in os.environ.get('PART_STL_PARTS', '').split(',') else STL) / f'{k}.stl', f'part STL "{k}"')
        note_input(k, f_)
        P[k] = samp(trimesh.load(f_), 0.7)
    for k in ('cover_ring',):      # optional parts: swept when their STL exists
        f_ = (WIP / os.environ['PART_STL_DIR'] if k in os.environ.get('PART_STL_PARTS', '').split(',') else STL) / f'{k}.stl'
        if f_.exists():
            note_input(k, f_)
            P[k] = samp(trimesh.load(f_), 0.7)
    f_ = need(VENDOR / 'vendor_robstride_rs03.stp', 'roll RS03')
    P['roll_rs03'] = cached('roll_rs03', f_, ('mesh_step', 0.15, 0.7, np.round(T_ROLL_RS03, 9).tolist()), lambda: samp(mesh_step(f_, T_ROLL_RS03), 0.7))
    f_ = need(VENDOR / 'vendor_robstride_rs02.step', 'yaw RS02')
    P['rs02'] = cached('rs02', f_, ('mesh_step', 0.15, 0.7, np.round(T_RS02, 9).tolist()), lambda: samp(mesh_step(f_, T_RS02), 0.7))
    f_ = need(UA / 'torso_pitch_rs03_left.step', 'pitch RS03')
    pm = cached('pitch_rs03', f_, ('mesh_step', 0.3, 0.7), lambda: samp(mesh_step(f_, tol=0.3), 0.7))
    r = np.hypot(pm[:, 1] - RY, pm[:, 2] - PZ)
    pm = pm[~((r < 23.8) & (np.abs(pm[:, 0] - PITCH_OUT) < 4.5))]      # rotor bolted to the drum pad
    # rev A frame (moved into the old-frame coordinates of the parts) and the pitch motor
    from build_asm import FRAME_SHIFT
    f_ = need(FRAME_STEP, 'rev A frame, torso_frame.step: set FRAME_STEP')
    P['torso'] = np.vstack([cached('frame', f_, ('frame_samples', 1.0, FRAME_SHIFT), lambda: frame_samples(f_)), pm])
    ua = []
    for n in ('front', 'back', 'rs02_ring'):
        f_ = need(UA / f'upper_arm_organic_{n}_left.step', 'upper arm')
        ua.append(cached(f'upper_arm_{n}', f_, ('mesh_step', 0.3, 1.0), lambda f_=f_: samp(mesh_step(f_, tol=0.3), 1.0)))
    P['upper_arm'] = np.vstack(ua)
    # the arm's exports are in their pre-E1 coordinates: with hub rev E1 the arm sits HUB_ARM_DROP lower on the yaw axis.
    # UA_SHIFT_Y overrides it (negative = down; 0 = the arm as exported, for a hub before rev E1)
    _dy = float(os.environ['UA_SHIFT_Y']) if os.environ.get('UA_SHIFT_Y') else -HUB_ARM_DROP
    if _dy:
        P['upper_arm'] = P['upper_arm'] + np.array((0.0, _dy, 0.0))
    p = P['roll_rs03']; r = np.hypot(p[:, 0] - RX, p[:, 1] - RY)
    P['roll_rs03'] = p[~((r < 23.8) & (np.abs(p[:, 2] - ROLL_OUT) < 4.5))]
    p = P['rs02']; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
    P['rs02'] = p[~((r < 21.8) & (p[:, 1] < 323.5))]
    split_stop(P)
    empty = [k for k, v in P.items() if len(v) == 0]
    if empty:
        raise SystemExit(f'check_clearance: no samples for {", ".join(empty)}: the part is missing, or the rule that picks it out no longer matches the geometry')
    print('loaded', {k: len(v) for k, v in P.items()}, round(time.time() - t0), 's', flush=True)
    return P


GROUP = dict(cover='fixed', torso='fixed', port_cap='pitch', drum='pitch', ring='pitch', cap='pitch', stop_ends='pitch', roll_rs03='pitch', cover_ring='pitch',
             fork_front='roll', fork_rear='roll', fork_cap='roll', stop_tooth='roll', rs02='roll', hub='yaw', upper_arm='yaw')
ORDER = ['fixed', 'pitch', 'roll', 'yaw']
STOP_PAIR = 'stop_tooth|stop_ends'      # the stop's own contact: reported on its own
# pairs that are bolted or seated together (static fits), not running clearances
STATIC = {frozenset(p) for p in [('drum', 'ring'), ('drum', 'cap'), ('drum', 'roll_rs03'), ('cap', 'roll_rs03'), ('ring', 'cap'),
                                  ('fork_front', 'fork_rear'), ('fork_front', 'rs02'), ('fork_rear', 'rs02'), ('fork_front', 'fork_cap'),
                                  ('fork_rear', 'fork_cap'), ('hub', 'upper_arm'), ('cover', 'torso'), ('fork_cap', 'rs02'), ('port_cap', 'drum')]}
# which joint angles (pitch, roll, yaw) the relative position of two groups depends on: the joints between them
_JOINTS = {('fixed', 'pitch'): (1, 0, 0), ('fixed', 'roll'): (1, 1, 0), ('fixed', 'yaw'): (1, 1, 1),
           ('pitch', 'roll'): (0, 1, 0), ('pitch', 'yaw'): (0, 1, 1), ('roll', 'yaw'): (0, 0, 1)}


def xf(p, M):
    return p @ M[:3, :3].T + M[:3, 3]


def fmt(d):
    return f'over {BOUND:.0f}' if d >= BOUND else f'{d:7.2f}'


def script_version():
    here = Path(__file__).resolve().parent
    out = dict(check_clearance_sha256=sha(Path(__file__).resolve()), clearance_worker_sha256=sha(here / 'clearance_worker.py'))
    try:
        out['git_commit'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=here, capture_output=True, text=True, timeout=20).stdout.strip()
        out['git_modified'] = sorted(l[3:] for l in subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=here, capture_output=True, text=True,
                                                                    timeout=20).stdout.splitlines())
    except Exception as e:
        out['git_commit'] = f'not read: {e}'
    return out


def run():
    t_start = time.time()
    P = load()
    t_load = time.time() - t_start
    keys = list(P)
    pairs = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if GROUP[a] == GROUP[b] or frozenset((a, b)) in STATIC:
                continue
            ga, gb = sorted((GROUP[a], GROUP[b]), key=ORDER.index)
            q, t = (a, b) if len(P[a]) <= len(P[b]) else (b, a)      # the smaller cloud is queried into the larger one's tree
            name = STOP_PAIR if {a, b} == {'stop_tooth', 'stop_ends'} else f'{a}|{b}'
            pairs.append(dict(name=name, q=q, t=t, joints=_JOINTS[(ga, gb)]))

    # poses: within travel (they count toward the minimum), and beyond the stops (the stop section only)
    brief = [(p, r, y) for r in (0.0, ROLL_STOP_IN, 45.0, ROLL_STOP_OUT) for p in (-30.0, 0.0, 90.0) for y in (-90.0, 0.0, 90.0)]
    step = 10 if QUICK else 3
    sweep = [(0.0, float(r), y) for r in list(range(int(ROLL_STOP_IN), int(ROLL_STOP_OUT) + 1, step)) + [ROLL_STOP_OUT] for y in (-90.0, 0.0, 90.0)]
    sweep += [(float(p), r, 0.0) for p in range(-90, 181, step) for r in (ROLL_STOP_IN, 0.0, ROLL_STOP_OUT)]
    sweep += [(0.0, r, float(y)) for y in range(-90, 91, 2 * step) for r in (ROLL_STOP_IN, 0.0, ROLL_STOP_OUT)]
    stop_rolls = [ROLL_STOP_IN + 3, ROLL_STOP_IN + 1, ROLL_STOP_IN, ROLL_STOP_IN - 1, ROLL_STOP_OUT - 2, ROLL_STOP_OUT, ROLL_STOP_OUT + 1]
    stop_poses = [(0.0, float(r_), 0.0) for r_ in stop_rolls]
    in_travel = lambda ps: ROLL_STOP_IN - 1e-9 <= ps[1] <= ROLL_STOP_OUT + 1e-9
    travel = list(dict.fromkeys(brief + sweep + [ps for ps in stop_poses if in_travel(ps)]))
    beyond = [ps for ps in stop_poses if not in_travel(ps)]
    assert all(in_travel(ps) for ps in brief + sweep)

    # one task per pair and distinct set of the joint angles that matter to it
    def tkey(k, ps):
        return (k,) + tuple(a if use else 0.0 for a, use in zip(ps, pairs[k]['joints']))
    tasks = {}
    for ps in travel + beyond:
        for k in range(len(pairs)):
            tasks.setdefault(tkey(k, ps), None)
    order = sorted(tasks, key=lambda key: (pairs[key[0]]['t'], key[0]))      # a worker meets the same tree in a run of tasks
    job = []
    for i, key in enumerate(order):
        pr = pairs[key[0]]
        M = np.linalg.inv(pose_matrix(GROUP[pr['t']], *key[1:])) @ pose_matrix(GROUP[pr['q']], *key[1:])
        job.append((i, pr['q'], pr['t'], M))
    n_work = int(os.environ.get('CLEAR_WORKERS') or max(1, (os.cpu_count() or 4) - 2))
    print(f'poses {len(travel)} within travel + {len(beyond)} beyond the stops, pairs {len(pairs)}: {len(travel + beyond) * len(pairs)} pair-poses, '
          f'{len(job)} distinct to evaluate, {n_work} workers', flush=True)
    t0 = time.time()
    fd, npz = tempfile.mkstemp(suffix='.npz', prefix='clearance_samples_')
    os.close(fd)
    np.savez(npz, **P)
    val = [None] * len(job)
    try:
        if n_work == 1:
            CW.init(npz)
            for tsk in job:
                i, d = CW.dist(tsk)
                val[i] = d
        else:
            # one maths thread per worker: left alone, each worker's BLAS reserves buffers for every core, and 14 workers
            # then commit over 6 GB before doing anything (the workers read the environment when they import numpy)
            for v_ in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
                os.environ[v_] = '1'
            with mp.Pool(n_work, initializer=CW.init, initargs=(npz,)) as pool:
                done = 0
                for i, d in pool.imap_unordered(CW.dist, job, chunksize=max(1, len(job) // (n_work * 40))):
                    val[i] = d
                    done += 1
                    if done % 2000 == 0:
                        print(f'  {done} of {len(job)}  {time.time() - t0:.0f} s', flush=True)
    finally:
        try:
            os.remove(npz)
        except OSError:
            pass
    t_eval = time.time() - t0
    for key, d in zip(order, val):
        tasks[key] = d
    print(f'evaluated {len(job)} in {t_eval:.0f} s', flush=True)

    def at(ps):
        return {pairs[k]['name']: round(tasks[tkey(k, ps)], 2) for k in range(len(pairs))}

    res = {}
    for ps in travel:
        for nm, d in at(ps).items():
            if nm not in res or d < res[nm][0]:
                res[nm] = (d, ps)
    stop_travel = res.pop(STOP_PAIR)
    at_pose = []
    for ps in brief:
        o = {k: v for k, v in at(ps).items() if k != STOP_PAIR}
        at_pose.append(dict(pitch=ps[0], roll=ps[1], yaw=ps[2], min={k: v for k, v in sorted(o.items(), key=lambda kv: kv[1])[:8]}))
    # the stop: at each end of travel the tooth must meet the slot's end before anything else touches
    stops, past = {}, []
    for ps in stop_poses:
        o = at(ps)
        others = {k: v for k, v in o.items() if k != STOP_PAIR and 'upper_arm' not in k}
        k_, v_ = min(others.items(), key=lambda kv: kv[1])
        stops[str(ps[1])] = dict(tooth_to_slot_end=o[STOP_PAIR], closest_other=[k_, v_], within_travel=in_travel(ps))
        if not in_travel(ps):
            past.append(dict(pitch=ps[0], roll=ps[1], yaw=ps[2], min={k: v for k, v in sorted(others.items(), key=lambda kv: kv[1])[:8]}))
    order_res = dict(sorted(res.items(), key=lambda kv: kv[1][0]))
    shell = Path(FRAME_STEP).with_name('shell_inner.step')
    out = dict(method=f'surface samples 0.7 mm (frame/arm 1.0), KD-tree, +-0.4 mm; rotors split off; the smaller cloud of a pair queried into the larger; '
                      f'seeded sampling; search bound {BOUND:.0f} mm',
               min_over_all={k: [v[0], list(v[1])] for k, v in order_res.items()},
               over_bound=[k for k, v in order_res.items() if v[0] >= BOUND],
               stop_contact=dict(pair=STOP_PAIR, min_within_travel=[stop_travel[0], list(stop_travel[1])],
                                 note='the fork rear tooth against the end faces of the rear cap slot: the stop itself, not in min_over_all'),
               brief_poses=at_pose, stops=stops, beyond_stops=past,
               inputs=dict(files=INPUTS, frame_step=str(FRAME_STEP),
                           shell_inner=(dict(path=str(shell), sha256=sha(shell), note='beside the frame; not read by this script') if shell.is_file() else None),
                           parts={k: len(v) for k, v in P.items()}, stl_set=str(STL), quick=QUICK, ua_shift_y=os.environ.get('UA_SHIFT_Y'),
                           part_stl_dir=os.environ.get('PART_STL_DIR'), part_stl_parts=os.environ.get('PART_STL_PARTS')),
               script=script_version(),
               run=dict(poses_within_travel=len(travel), poses_beyond_stops=len(beyond), pairs=len(pairs), evaluated=len(job), workers=n_work,
                        load_s=round(t_load, 1), evaluate_s=round(t_eval, 1), total_s=round(time.time() - t_start, 1),
                        finished=time.strftime('%Y-%m-%d %H:%M:%S')))
    (WIP / os.environ.get('CLEAR_JSON', 'clearance.json')).write_text(json.dumps(out, indent=1))
    print('minimum over travel (the stop contact apart):')
    for k, v in list(order_res.items())[:25]:
        print(f'{k:28s} {fmt(v[0]):>8s}  at {v[1]}')
    print(f'never within {BOUND:.0f} mm: {len(out["over_bound"])} pairs')
    print(f'stop contact {STOP_PAIR}: {stop_travel[0]:.2f} at {stop_travel[1]}')
    for r_, s_ in stops.items():
        print(f'  roll {float(r_):+7.1f}{"" if s_["within_travel"] else " (beyond the stop)"}: tooth to slot end {fmt(s_["tooth_to_slot_end"]).strip()}, '
              f'closest other {s_["closest_other"][0]} {fmt(s_["closest_other"][1]).strip()}')
    print(f'total {time.time() - t_start:.0f} s (load {t_load:.0f}, evaluate {t_eval:.0f})')


if __name__ == '__main__':
    run()
