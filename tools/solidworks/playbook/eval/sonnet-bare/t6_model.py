"""T6 model: PETG block with a dia 10.2 cross hole along Y, steel dia 10 x 50 pin as a second body (multibody part)."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *

def build_pin_block(sw, path):
    doc = new_part(sw)
    sk = doc.SketchManager; fm = doc.FeatureManager
    sk.AddToDB = True
    # block: Front plane (XY), X -20..20, Y -15..15, extrude +Z 20
    select_plane(doc, "Front Plane"); sk.InsertSketch(True)
    for p in ((-20,-15,20,-15),(20,-15,20,15),(20,15,-20,15),(-20,15,-20,-15)):
        sk.CreateLine(p[0]*MM,p[1]*MM,0,p[2]*MM,p[3]*MM,0)
    sk.InsertSketch(True); assert ext(fm, 20), "block"
    # hole along Y: Top plane sketch (x = X, y = -Z), centre X0 Z10, dia 10.2, through both ways
    select_plane(doc, "Top Plane"); sk.InsertSketch(True)
    sk.CreateCircleByRadius(0, -10*MM, 0, 5.1*MM); sk.InsertSketch(True)
    assert cut(fm, both=True), "hole"
    # pin: dia 10, Y -25..25, separate body
    select_plane(doc, "Top Plane"); sk.InsertSketch(True)
    sk.CreateCircleByRadius(0, -10*MM, 0, 5.0*MM); sk.InsertSketch(True)
    assert ext(fm, 25, merge=False, both=True), "pin"
    ok, e, w = save_as(doc, path)
    return doc

if __name__ == "__main__":
    write_mat()
    with launch() as inst:
        sw = inst.sw; prep(sw)
        doc = build_pin_block(sw, os.path.join(WIP, "pin_block.SLDPRT"))
        bodies = doc.GetBodies2(0, False)
        print("bodies", len(bodies))
        for b in bodies:
            print(" body", b.Name, "box mm", [round(x/MM,3) for x in b.GetBodyBox()])
        for f, i in faces_where(doc, lambda i: i["kind"] == "cyl"): print(i)
        for f, i in faces_where(doc, lambda i: i["kind"] == "plane" and abs(i["normal"][2]) > .99 and i["origin"][2] == 0): print("plane z0", i["area"], i["box"])
