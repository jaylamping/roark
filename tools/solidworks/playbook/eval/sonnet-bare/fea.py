"""Helpers for SolidWorks Simulation static studies via COM (pywin32). Frame: mm. COM calls take SI where noted."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *

def byref_long():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

def dispatch_array(objs):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(objs))

def body_faces(doc, idx=None):
    """All faces of all solid bodies (or of body idx)."""
    bodies = list(doc.GetBodies2(0, False))
    if idx is not None: bodies = [bodies[idx]]
    return [f for b in bodies for f in g(b, "GetFaces")]

def face_info(face):
    s = g(face, "GetSurface")
    b = g(face, "GetBox")
    info = dict(box=[round(x/MM, 3) for x in b], area=g(face, "GetArea")/MM**2)
    if g(s, "IsCylinder"):
        p = g(s, "CylinderParams")  # origin xyz, axis xyz, radius
        info.update(kind="cyl", origin=[round(x/MM,3) for x in p[0:3]], axis=[round(x,3) for x in p[3:6]], r=round(p[6]/MM, 4))
    elif g(s, "IsPlane"):
        p = g(s, "PlaneParams")  # normal xyz, origin xyz
        info.update(kind="plane", normal=[round(x,3) for x in p[0:3]], origin=[round(x/MM,3) for x in p[3:6]])
    else:
        info.update(kind="other")
    return info

def faces_where(doc, pred):
    out = []
    for f in body_faces(doc):
        i = face_info(f)
        if pred(i): out.append((f, i))
    return out

def new_static_study(cw, name):
    cwdoc = cw.ActiveDoc
    sm = cwdoc.StudyManager
    err = byref_long()
    study = sm.CreateNewStudy3(name, 0, 0, err)
    assert study is not None, ("study", err.value)
    return cwdoc, sm, study

def set_material(study, lib=SLDMAT, name="PETG printed"):
    comp = study.SolidManager.GetComponentAt(0, byref_long())
    body = comp.GetSolidBodyAt(0, byref_long())
    rc = body.SetLibraryMaterial2(lib, name)
    return rc, body

def mat_report(body):
    m = body.GetSolidBodyMaterial
    out = {"name": m.MaterialName, "source": m.Source}
    for p in ("EX", "NUXY", "DENS", "SIGYLD", "SIGXT"):
        try: out[p] = m.GetPropertyByName2(0, p, VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False))
        except Exception as e: out[p] = f"err {e}"
    return out

def add_split_annuli(doc, d_mm=10.0, pts=((25,10),(25,40),(65,10),(65,40)), top_z=6.0):
    """Split-line the bottom face (Z=0) with circles so that each bolt gets a washer-sized face (geometry unchanged).
    The circles are sketched on the base top face and projected down onto the bottom face."""
    sk = doc.SketchManager; fm = doc.FeatureManager
    sk.AddToDB = True
    doc.ClearSelection2(True)
    ok = doc.Extension.SelectByID2("", "FACE", 45e-3, 25e-3, top_z*MM, False, 0, NOTHING, 0); assert ok, "top face"
    sk.InsertSketch(True)
    for x, y in pts:
        sk.CreateCircleByRadius(x*MM, y*MM, 0, d_mm/2*MM)
    sk.InsertSketch(True)
    f = doc.FirstFeature; names = []
    while f:
        if f.GetTypeName2 == "ProfileFeature": names.append(f.Name)
        f = f.GetNextFeature
    skname = names[-1]
    doc.ClearSelection2(True)
    ok1 = doc.Extension.SelectByID2(skname, "SKETCH", 0, 0, 0, False, 4, NOTHING, 0)
    ok2 = doc.Extension.SelectByID2("", "FACE", 45e-3, 25e-3, 0, True, 2, NOTHING, 0)   # bottom face
    ok3 = doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, True, 1, NOTHING, 0)  # projection direction
    feat = doc.InsertSplitLineProject(True, False)
    return skname, ok1, ok2, ok3, feat

# ---------------------------------------------------------------------------------------------------------------
import numpy as np

HOLE_XY = [(25,10),(25,40),(65,10),(65,40)]

def node_array(mesh):
    a = np.array(mesh.GetNodes, float).reshape(-1, 4)
    return a[:, 0].astype(int), a[:, 1:] / MM   # ids, xyz in mm

def surface_values(res, doc, comp, unit=3):
    e = byref_long()
    st = res.GetStressForEntities2(True, comp, 1, NOTHING, tuple(body_faces(doc)), unit, e)
    assert e.value == 0, e.value
    a = np.array(st, float).reshape(-1, 2)
    return a[:, 0].astype(int), a[:, 1]

def near_holes(xyz, r=8.0):
    d = np.min([np.hypot(xyz[:,0]-x, xyz[:,1]-y) for x, y in HOLE_XY], axis=0)
    return (d < r) & (xyz[:,2] < 7.0)

def study_rows(doc, study, size_mm, root_box=((0,14),(0,50),(3,14)), extra=None):
    """Mesh at size_mm, solve, return one dict of everything the checks need."""
    m = study.Mesh
    t0 = time.time()
    rc = study.CreateMesh(0, float(size_mm), float(size_mm) * 0.05)
    assert rc == 0, ("mesh", rc)
    row = dict(el_mm=size_mm, nodes=int(m.NodeCount), elements=int(m.ElementCount), max_aspect=float(m.MaxAspectRatio),
               mesh_s=round(time.time() - t0, 1))
    if row["nodes"] > 150000:
        row["skipped"] = "mesh over the 150,000-node limit, not solved"; return row
    t0 = time.time()
    rc = study.RunAnalysis
    assert rc == 0, ("solve", rc)
    row["solve_s"] = round(time.time() - t0, 1)
    res = study.Results
    ids, xyz = node_array(m)
    vid, vm = surface_values(res, doc, 9)
    zid, sz = surface_values(res, doc, 2)
    p = xyz[vid - 1]
    far = ~near_holes(p)
    k = int(np.argmax(vm)); row["peak_vm_all"] = float(vm[k]); row["peak_vm_all_at"] = p[k].round(2).tolist()
    kk = np.where(far)[0]; k2 = kk[int(np.argmax(vm[kk]))]
    row["peak_vm_away_from_bolts"] = float(vm[k2]); row["peak_vm_away_at"] = p[k2].round(2).tolist()
    (x0,x1),(y0,y1),(z0,z1) = root_box
    inr = (p[:,0]>=x0)&(p[:,0]<=x1)&(p[:,1]>=y0)&(p[:,1]<=y1)&(p[:,2]>=z0)&(p[:,2]<=z1)
    kr = np.where(inr)[0]; k3 = kr[int(np.argmax(vm[kr]))]
    row["peak_vm_root"] = float(vm[k3]); row["peak_vm_root_at"] = p[k3].round(2).tolist()
    ps = xyz[zid - 1]; farz = np.where(~near_holes(ps))[0]
    k4 = farz[int(np.argmax(sz[farz]))]; row["peak_sz_tension_away"] = float(sz[k4]); row["peak_sz_at"] = ps[k4].round(2).tolist()
    k5 = int(np.argmax(sz)); row["peak_sz_tension_all"] = float(sz[k5]); row["peak_sz_all_at"] = ps[k5].round(2).tolist()
    for comp, key in ((0, "peak_sx_tension_away"), (1, "peak_sy_tension_away")):
        cid, cv = surface_values(res, doc, comp); pc = xyz[cid - 1]; fc = np.where(~near_holes(pc))[0]; kc = fc[int(np.argmax(cv[fc]))]
        row[key] = float(cv[kc]); row[key + "_at"] = pc[kc].round(2).tolist()
    e = byref_long(); mm = res.GetMinMaxStress(9, 0, 1, NOTHING, 3, e); row["swminmax_vm"] = float(mm[3]); row["swminmax_vm_node"] = int(mm[2])
    e = byref_long(); d = res.GetMinMaxDisplacement(3, 1, NOTHING, 0, e); row["max_disp_mm"] = float(d[3])   # unit 0 = mm (3 would be inches)
    e = byref_long(); rx = np.array(res.GetReactionForcesAndMoments(1, NOTHING, 0, e), float).reshape(-1, 9)
    row["reaction_sum_N"] = rx[:, 1:4].sum(axis=0).round(4).tolist()
    row["reaction_n"] = float(np.linalg.norm(rx[:, 1:4].sum(axis=0)))
    # back-face nominal bending stress check, away from every hole: X=0 face, Z 7.5..8.5, |Y-25|<=10
    sel = np.where((ps[:,0] < 0.01) & (ps[:,2] > 7.5) & (ps[:,2] < 8.5) & (np.abs(ps[:,1]-25) <= 10))[0]
    row["backface_sz_Z8_mean"] = float(np.mean(sz[sel])) if len(sel) else None
    if extra: row.update(extra(res, doc, study, ids, xyz))
    return row


def local_control(study, faces, size_mm, mc=None):
    """Mesh control on faces; reuse mc to change its size (BeginEdit/EndEdit are needed for a change to take)."""
    if mc is None:
        err = byref_long()
        mc = study.Mesh.ApplyMeshControl(tuple(faces), err)
        assert mc is not None, ("meshcontrol", err.value)
    g(mc, "MeshControlBeginEdit")
    mc.Units = 0; mc.ElementSize = float(size_mm); mc.UseSameElementSize = True
    assert g(mc, "MeshControlEndEdit") == 0
    return mc
