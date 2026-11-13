"""T2: open saved bracket.SLDPRT, add 4 counterbores + a slot, save as bracket_b.SLDPRT."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *
import math
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    sk = doc.SketchManager; fm = doc.FeatureManager
    sk.AddToDB = True   # no sketch inference/snapping: the first build had hole centres and radii moved by inference
    v0 = doc.Extension.CreateMassProperty2.Volume*1e9
    # counterbores: sketch on the top face of the base (Z=6), cut 3 mm blind down
    doc.ClearSelection2(True)
    ok = doc.Extension.SelectByID2("", "FACE", 45e-3, 40e-3, 6e-3, False, 0, NOTHING, 0); assert ok, "top face"
    sk.InsertSketch(True)
    for x, y in [(25,10),(25,40),(65,10),(65,40)]:
        sk.CreateCircleByRadius(x*MM, y*MM, 0, 5*MM)
    sk.InsertSketch(True)
    f = cut(fm, through=False, depth_mm=3); assert f, "counterbore"
    v1 = doc.Extension.CreateMassProperty2.Volume*1e9
    stamp(f"cbores removed {v0-v1:.3f} (hand {4*math.pi*(25-2.75**2)*3:.3f})")
    # slot through the base (Front plane): two lines + two semicircular arcs, 20 long x 6 wide overall.
    # (With sketch inference on, this contour would not cut; with AddToDB it does.)
    select_plane(doc, "Front Plane")
    sk.InsertSketch(True)
    L = lambda x1,y1,x2,y2: sk.CreateLine(x1*MM,y1*MM,0,x2*MM,y2*MM,0)
    A = lambda cx,cy,x1,y1,x2,y2: sk.CreateArc(cx*MM,cy*MM,0,x1*MM,y1*MM,0,x2*MM,y2*MM,0,1)
    L(38,22,52,22); A(52,25,52,22,52,28); L(52,28,38,28); A(38,25,38,28,38,22)
    sk.InsertSketch(True)
    f = cut(fm, both=True); assert f, "slot"
    v2 = doc.Extension.CreateMassProperty2.Volume*1e9
    stamp(f"slot removed {v1-v2:.3f} (hand {(14*6+math.pi*9)*6:.3f})")
    # floor of the counterbore: planar faces with zmin==zmax between 0 and 6
    body = doc.GetBodies2(0, False)[0]
    floors = set()
    for face in g(body, "GetFaces"):
        s = g(face, "GetSurface")
        if g(s, "IsPlane"):
            b = g(face, "GetBox")
            if abs(b[2]-b[5]) < 1e-9 and 1e-4 < b[2] < 5.99e-3: floors.add(round(b[2]/MM, 4))
    stamp(f"internal horizontal planar faces at z (mm): {sorted(floors)}")
    path = os.path.join(WIP, "bracket_b.SLDPRT")
    stamp(f"save {save_as(doc, path)}")
    hand = 32974.02416773478 - 4*math.pi*(25-2.75**2)*3 - (14*6+math.pi*9)*6
    stl_n = doc.GetBodyCount if hasattr(doc,'GetBodyCount') else None
    record("T2", volume_mm3=round(v2,2), hand_volume_mm3=round(hand,2), counterbore_floor_z_mm=sorted(floors)[0] if floors else None,
           bodies=len(doc.GetBodies2(0, False)), status="done")
    stamp(str(json.load(open(RESULTS))["T2"]))
