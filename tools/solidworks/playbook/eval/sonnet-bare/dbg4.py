import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    sk = doc.SketchManager; fm = doc.FeatureManager
    vol=lambda: doc.Extension.CreateMassProperty2.Volume*1e9
    L = lambda x1,y1,x2,y2: sk.CreateLine(x1*MM,y1*MM,0,x2*MM,y2*MM,0)
    A = lambda cx,cy,x1,y1,x2,y2: sk.CreateArc(cx*MM,cy*MM,0,x1*MM,y1*MM,0,x2*MM,y2*MM,0,1)
    v0=vol()
    select_plane(doc, "Front Plane"); sk.InsertSketch(True)
    L(38,22,52,22); A(52,25,52,22,55,25); A(52,25,55,25,52,28); L(52,28,38,28); A(38,25,38,28,35,25); A(38,25,35,25,38,22)
    sk.InsertSketch(True)
    f = cut(fm, both=True); print("quarters", bool(f), v0-vol(), (14*6+math.pi*9)*6)
