"""Running clearances of the left shoulder CAD (first pass), at the brief's poses and over each joint's travel.

    python check_clearance.py [quick]

Reads the STL/STEP exports of the SolidWorks parts (cad/_wip/shoulder-pass1/{stl,step}), the vendor motors placed as in
build_asm.py, the torso corner and the frozen upper arm. Surfaces are sampled at about 0.7 mm (frame and arm 1.0 mm) and
compared with KD-trees (distances good to about +-0.4 mm), as in the measurement study. Motor rotors are split off their
stators, so a part bolted to an output is not reported as touching it.
Writes cad/_wip/shoulder-pass1/clearance.json.
"""
import json
import os
import sys
import time

import cadquery as cq
import numpy as np
import trimesh
from scipy.spatial import cKDTree

from build_asm import T_ROLL_RS03, T_RS02, pose_matrix
from dims import *
from swk import CAD, VENDOR, WIP

QUICK = len(sys.argv) > 1 and sys.argv[1] == 'quick'
STL = WIP / os.environ.get('CLEAR_STL', 'stl')   # CLEAR_STL: another STL set (e.g. a before / after pair)
UA = CAD / 'reference' / 'shoulder'


def mesh_step(path, M=None, tol=0.15):
    s = cq.importers.importStep(str(path))
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
    doc = TDocStd_Document(TCollection_ExtendedString('d'))
    r = STEPCAFControl_Reader(); r.SetNameMode(True); r.ReadFile(path); r.Transfer(doc)
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


FRAME_STEP = os.environ.get('FRAME_STEP', r'J:/code/_transfer/shoulder/torso_frame.step')


def frame_samples(path=None, sp=1.0):
    """Rev A frame (its own coordinates) moved -38 in X; pitch motor envelope and shell parts left out."""
    from build_asm import FRAME_SHIFT
    out = []
    for nm, sh in named_solids(path or FRAME_STEP):
        bb = sh.BoundingBox()
        if bb.xmax < 60 or bb.ymax < 250 or nm.split('__')[0] in ('actuator', 'shellpart') or nm.startswith('fastener__c1_'):
            continue
        m = tess(sh)
        if m.area > 0:
            out.append(samp(m, sp))
    return np.vstack(out) - np.array([FRAME_SHIFT, 0, 0])


def load():
    t0 = time.time()
    P = {}
    for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'hub', 'cover', 'port_cap'):   # fork cap dropped (look option a)
        P[k] = samp(trimesh.load((WIP / os.environ['PART_STL_DIR'] if k in os.environ.get('PART_STL_PARTS', '').split(',') else STL) / f'{k}.stl'), 0.7)
    for k in ('cover_ring',):      # optional parts: swept when their STL exists
        f_ = (WIP / os.environ['PART_STL_DIR'] if k in os.environ.get('PART_STL_PARTS', '').split(',') else STL) / f'{k}.stl'
        if f_.exists():
            P[k] = samp(trimesh.load(f_), 0.7)
    P['roll_rs03'] = samp(mesh_step(VENDOR / 'vendor_robstride_rs03.stp', T_ROLL_RS03), 0.7)
    P['rs02'] = samp(mesh_step(VENDOR / 'vendor_robstride_rs02.step', T_RS02), 0.7)
    pm = samp(mesh_step(UA / 'torso_pitch_rs03_left.step', tol=0.3), 0.7)
    r = np.hypot(pm[:, 1] - RY, pm[:, 2] - PZ)
    pm = pm[~((r < 23.8) & (np.abs(pm[:, 0] - PITCH_OUT) < 4.5))]      # rotor bolted to the drum pad
    # rev A frame (moved into the old-frame coordinates of the parts) and the pitch motor
    P['torso'] = np.vstack([frame_samples(), pm])
    ua = [samp(mesh_step(UA / f'upper_arm_organic_{n}_left.step', tol=0.3), 1.0) for n in ('front', 'back', 'rs02_ring')]
    P['upper_arm'] = np.vstack(ua)
    p = P['roll_rs03']; r = np.hypot(p[:, 0] - RX, p[:, 1] - RY)
    P['roll_rs03'] = p[~((r < 23.8) & (np.abs(p[:, 2] - ROLL_OUT) < 4.5))]
    p = P['rs02']; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
    P['rs02'] = p[~((r < 21.8) & (p[:, 1] < 323.5))]
    # stop lugs apart from the rest of the cap: behind the plate (Z < -39.4), r 43.5-57.5 about the roll axis
    c = P['cap']; r = np.hypot(c[:, 0] - RX, c[:, 1] - RY)
    st = (c[:, 2] < CAP_Z1 - 0.1) & (r > 43.5) & (r < 60)
    P['stops'] = c[st]; P['cap'] = c[~st]
    print('loaded', {k: len(v) for k, v in P.items()}, round(time.time() - t0), 's', flush=True)
    return P


GROUP = dict(cover='fixed', torso='fixed', port_cap='pitch', drum='pitch', ring='pitch', cap='pitch', stops='pitch', roll_rs03='pitch', cover_ring='pitch',
             fork_front='roll', fork_rear='roll', fork_cap='roll', rs02='roll', hub='yaw', upper_arm='yaw')
ORDER = ['fixed', 'pitch', 'roll', 'yaw']
# pairs that are bolted or seated together (static fits), not running clearances
STATIC = {frozenset(p) for p in [('drum', 'ring'), ('drum', 'cap'), ('drum', 'roll_rs03'), ('cap', 'roll_rs03'), ('ring', 'cap'),
                                  ('fork_front', 'fork_rear'), ('fork_front', 'rs02'), ('fork_rear', 'rs02'), ('fork_front', 'fork_cap'),
                                  ('fork_rear', 'fork_cap'), ('hub', 'upper_arm'), ('stops', 'cap'), ('stops', 'drum'),
                                  ('stops', 'roll_rs03'), ('stops', 'ring'), ('cover', 'torso'), ('fork_cap', 'rs02'), ('port_cap', 'drum')]}


def xf(p, M):
    return p @ M[:3, :3].T + M[:3, 3]


def run():
    P = load()
    TREE = {k: cKDTree(v) for k, v in P.items()}
    keys = list(P)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if GROUP[a] != GROUP[b] and frozenset((a, b)) not in STATIC]
    res, at_pose = {}, []

    def upd(key, d, pose):
        if key not in res or d < res[key][0]:
            res[key] = (round(float(d), 2), pose)

    def eval_pose(p_, r_, y_, record=False):
        out = {}
        for a, b in pairs:
            # move a into b's frame: only the relative motion matters
            Ma = pose_matrix(GROUP[a], p_, r_, y_)
            Mb = pose_matrix(GROUP[b], p_, r_, y_)
            pa = xf(P[a][::2], np.linalg.inv(Mb) @ Ma)
            dd, _ = TREE[b].query(pa, distance_upper_bound=40, workers=2)
            d = float(dd.min()) if np.isfinite(dd.min()) else 40.0
            out[f'{a}|{b}'] = round(d, 2)
            upd(f'{a}|{b}', d, (p_, r_, y_))
        if record:
            at_pose.append(dict(pitch=p_, roll=r_, yaw=y_, min={k: v for k, v in sorted(out.items(), key=lambda kv: kv[1])[:8]}))
        return out

    t0 = time.time()
    brief = [(p, r, y) for r in (0.0, ROLL_STOP_IN, 45.0, ROLL_STOP_OUT) for p in (-30.0, 0.0, 90.0) for y in (-90.0, 0.0, 90.0)]
    for ps in brief:
        eval_pose(*ps, record=True)
    print('brief poses', len(brief), round(time.time() - t0), 's', flush=True)
    step = 10 if QUICK else 3
    sweep = [(0.0, float(r), y) for r in list(range(int(ROLL_STOP_IN), int(ROLL_STOP_OUT) + 1, step)) + [ROLL_STOP_OUT] for y in (-90.0, 0.0, 90.0)]
    sweep += [(float(p), r, 0.0) for p in range(-90, 181, step) for r in (ROLL_STOP_IN, 0.0, ROLL_STOP_OUT)]
    sweep += [(0.0, r, float(y)) for y in range(-90, 91, 2 * step) for r in (ROLL_STOP_IN, 0.0, ROLL_STOP_OUT)]
    for ps in sweep:
        eval_pose(*ps)
    print('sweeps', len(sweep), round(time.time() - t0), 's', flush=True)
    # stop lugs: first contact must be the fork rear arm at each end of travel
    lug = {}
    for r_ in (ROLL_STOP_IN + 3, ROLL_STOP_IN + 1, ROLL_STOP_IN, ROLL_STOP_IN - 1, ROLL_STOP_OUT - 2, ROLL_STOP_OUT, ROLL_STOP_OUT + 1):
        o = eval_pose(0.0, float(r_), 0.0)
        others = {k: v for k, v in o.items() if 'stops' not in k and 'upper_arm' not in k}
        lug[str(r_)] = dict(arm_to_lug=o.get('stops|fork_rear', o.get('fork_rear|stops')), closest_other=min(others.items(), key=lambda kv: kv[1]))
    out = dict(method='surface samples 0.7 mm (frame/arm 1.0), KD-tree, +-0.4 mm; rotors split off',
               min_over_all=dict(sorted(res.items(), key=lambda kv: kv[1][0])), brief_poses=at_pose, stops=lug)
    (WIP / os.environ.get('CLEAR_JSON', 'clearance.json')).write_text(json.dumps(out, indent=1))
    for k, v in list(out['min_over_all'].items())[:25]:
        print(f'{k:28s} {v[0]:7.2f}  at {v[1]}')
    print('stops', json.dumps(lug, indent=0))


if __name__ == '__main__':
    run()
