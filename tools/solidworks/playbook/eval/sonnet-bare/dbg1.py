import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *
import t1_bracket as T
orig_stamp = T.stamp
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = T.build(sw, "dbg")
    fs = doc.FeatureManager
    f = doc.FirstFeature
    while f:
        print(f.Name, f.GetTypeName2)
        f = f.GetNextFeature
    bodies = doc.GetBodies2(0, False)
    b = bodies[0]
    print("nbodies", len(bodies), "bodybox", [round(x*1000,3) for x in b.GetBodyBox()])
    print("faces", b.GetFaceCount, "edges", b.GetEdgeCount)
    mp = doc.Extension.CreateMassProperty2
    print("vol", mp.Volume*1e9, "density", mp.Density)
    doc.SetMaterialPropertyName2("", SLDMAT, "PETG printed")
    print("mat", doc.MaterialIdName)
    doc.SetSaveFlag
