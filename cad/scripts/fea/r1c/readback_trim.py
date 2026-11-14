"""Read-back trim test (2026-11-14, coordinator): one solved study's stresses read two ways, timed.
    python readback_trim.py MODEL.SLDPRT STUDY_NAME OUT_DIR
A: all nodes at once, CWResults.GetStress(0, 1, NUL, 3) (what p3_fea.py does), node id + 11 values per node.
B: per solid body, CWResults.GetStressForEntities3(True, component, 1, NUL, (body,), 3, 0, 0, False) for components 0-10, one
   body at a time (never faces), merged by node id into the same 12-column layout.
Writes OUT_DIR/A.npz and OUT_DIR/B.npz (pos from the mesh, s in node-id order like p3_fea), and prints the seconds and the largest
difference. The study must already be solved; nothing is meshed or solved here."""
import os
import sys
import time

import numpy as np
import pythoncom
from win32com.client import VARIANT

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'tools', 'solidworks'))
import sw_instance as S  # noqa: E402

NUL = VARIANT(pythoncom.VT_DISPATCH, None)
model, study, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)


def I():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


with S.launch() as inst:
    sw = inst.sw
    cw = inst.load_simulation()
    e, w = I(), I()
    t = time.time()
    d = sw.OpenDoc6(model, 1, 1, '', e, w)
    print('open', d is not None, e.value, w.value, round(time.time() - t, 1), 's', flush=True)
    doc = cw.ActiveDoc
    sm = doc.StudyManager
    names = [sm.GetStudy(k).Name for k in range(sm.StudyCount)]
    k = names.index(study)
    sm.ActiveStudy = k
    st = sm.GetStudy(k)
    t = time.time()
    res = st.Results
    print('results object', res is not None, round(time.time() - t, 1), 's (loading the result file)', flush=True)
    if res is None:
        raise SystemExit('no results for ' + study)
    mesh = st.Mesh
    raw = mesh.GetNodes
    raw = np.array(raw[0] if isinstance(raw, tuple) and len(raw) == 2 else raw, float).reshape(-1, 4)
    xyz = dict(zip(raw[:, 0].astype(int), raw[:, 1:] * 1000))
    # A: all nodes
    t = time.time()
    err = I()
    a = res.GetStress(0, 1, NUL, 3, err)
    a = np.array(a[0] if isinstance(a, tuple) and len(a) == 2 else a, float).reshape(-1, 12)
    ta = time.time() - t
    print(f'A all-node GetStress: {ta:.1f} s, {a.shape[0]} nodes, err {err.value}', flush=True)
    np.savez(os.path.join(out, 'A.npz'), pos=np.array([xyz[int(i)] for i in a[:, 0]]), s=a)
    # B: per solid body
    bodies = list(d.GetBodies2(0, True) or [])      # solid bodies only
    print('solid bodies', len(bodies), flush=True)
    t = time.time()
    cols = {}
    per = []
    for bi, b in enumerate(bodies):
        tb = time.time()
        n = 0
        for comp in range(11):
            err = I()
            q = res.GetStressForEntities3(True, comp, 1, NUL, (b,), 3, 0, 0, False, err)
            q = np.array(q[0] if isinstance(q, tuple) and len(q) == 2 and not isinstance(q[1], float) else q, float).reshape(-1, 2)
            if err.value:
                print(f'  body {bi} comp {comp}: err {err.value}', flush=True)
            for nid, v in q:
                cols.setdefault(int(nid), [np.nan] * 11)[comp] = v
            n = len(q)
        per.append((bi, n, time.time() - tb))
    tbt = time.time() - t
    ids = np.array(sorted(cols))
    bmat = np.c_[ids, np.array([cols[i] for i in ids])]
    print(f'B per-body GetStressForEntities3: {tbt:.1f} s, {len(ids)} nodes from {len(bodies)} bodies', flush=True)
    for bi, n, tt in per:
        print(f'  body {bi}: {n} node values per component, {tt:.1f} s', flush=True)
    order = {int(i): r for r, i in enumerate(a[:, 0])}
    b2 = np.full_like(a, np.nan)
    for row in bmat:
        r = order.get(int(row[0]))
        if r is not None:
            b2[r] = row
    missing = int(np.isnan(b2[:, 0]).sum())
    extra = len(set(cols) - set(order))
    print(f'nodes in A not in B: {missing}; in B not in A: {extra}', flush=True)
    b2[np.isnan(b2[:, 0]), 0] = a[np.isnan(b2[:, 0]), 0]
    np.savez(os.path.join(out, 'B.npz'), pos=np.array([xyz[int(i)] for i in b2[:, 0]]), s=b2)
    dmax = np.nanmax(np.abs(b2[:, 1:] - a[:, 1:]), axis=0)
    print('largest |B - A| per column (MPa):', np.round(dmax, 6).tolist(), flush=True)
    print(f'SECONDS A {ta:.1f} B {tbt:.1f}', flush=True)
    sw.CloseDoc(d.GetTitle)
