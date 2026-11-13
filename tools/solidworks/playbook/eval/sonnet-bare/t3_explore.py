import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    cw = inst.load_simulation()
    doc = open_part(sw, os.path.join(WIP, "bracket_fea_probe.SLDPRT"))
    bore = faces_where(doc, lambda i: i["kind"]=="cyl" and i["r"]==11.0)[0][0]
    holes = [f for f,i in faces_where(doc, lambda i: i["kind"]=="cyl" and i["r"]==2.75)]
    cwdoc, sm, study = new_static_study(cw, "probe")
    rc, body = set_material(study); print("material", rc)
    lr = study.LoadsAndRestraintsManager
    feat = doc.FeatureByName("Right Plane")
    err = byref_long(); r = lr.AddRestraint(0, tuple(holes), NOTHING, err); print("restraint", r.Name, err.value)
    err = byref_long(); fo = lr.AddForce2(0, 0, (bore,), feat, err); print("force", fo.Name, err.value)
    print("begin", g(fo, "ForceBeginEdit"))
    fo.Unit = 0
    print("set comps", fo.SetForceComponentValues2(False, False, True, 0.0, 0.0, 150.0))
    print("end", g(fo, "ForceEndEdit"))
    m = study.Mesh
    print("mesh quality", m.Quality, "jac", m.JacobianPoints, "mesher", m.MesherType)
    rc = study.CreateMesh(0, 4.0, 0.2); print("CreateMesh rc", rc)
    print("nodes", m.NodeCount, "elems", m.ElementCount, "state", m.MeshState, "aspect", m.MaxAspectRatio)
    t=time.time(); rc = study.RunAnalysis; print("run rc", rc, time.time()-t)
    res = study.Results
    e = byref_long(); print("minmax stress", res.GetMinMaxStress(9, 0, 1, NOTHING, 3, e), e.value)
    e = byref_long(); print("minmax disp", res.GetMinMaxDisplacement(3, 1, NOTHING, 3, e), e.value)
    import numpy as np
    nd = m.GetNodes; print("nodes type", type(nd), len(nd), nd[:12])
    faces = body_faces(doc)
    e = byref_long()
    st = res.GetStressForEntities2(True, 9, 1, NOTHING, tuple(faces), 3, e); print("stress ent", e.value, type(st), len(st), st[:10])
    e = byref_long()
    st2 = res.GetStressForEntities2(True, 2, 1, NOTHING, tuple(faces), 3, e); print("SZ", e.value, len(st2), st2[:10])
    e = byref_long()
    un = res.GetDisplacementForEntities(3, 1, NOTHING, tuple(faces[:1]), 3, e); print("disp ent", e.value, len(un), un[:10])
