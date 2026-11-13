import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from t3_study import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    cw = inst.load_simulation()
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    study, mr = setup_bracket_study(cw, doc)
    m = study.Mesh
    small = [f for f, i in faces_where(doc, lambda i: i["kind"] == "cyl" and 1.6 < i["r"] < 1.8)]
    study.CreateMesh(0, 3.0, 0.15); print("no control nodes", m.NodeCount, "controls", m.MeshControlCount)
    err = byref_long(); mc = m.ApplyMeshControl(tuple(small), err); print("control", mc.Name, err.value, "count", m.MeshControlCount)
    print("defaults: size", mc.ElementSize, "units", mc.Units, "ratio", mc.Ratio, "layers", mc.Layers, "samesize", mc.UseSameElementSize, "entities", mc.EntityCount)
    for sz_ in (1.0, 0.5):
        g(mc, "MeshControlBeginEdit")
        mc.Units = 0; mc.ElementSize = sz_; mc.UseSameElementSize = True
        print("end edit", g(mc, "MeshControlEndEdit"))
        print("after: size", mc.ElementSize, "units", mc.Units, "ratio", mc.Ratio)
        study.CreateMesh(0, 3.0, 0.15); print(sz_, "nodes", m.NodeCount, "elems", m.ElementCount)
