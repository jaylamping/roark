"""T1: L-shaped motor bracket. Usage: python t1_bracket.py [sharp]  (sharp = no inside fillet, for T4)"""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *

def build(sw, name, inside_fillet=True, fillet_r=4, base_holes=True, upright=True):
    doc = new_part(sw)
    sk = doc.SketchManager; fm = doc.FeatureManager
    sk.AddToDB = True   # no sketch inference/snapping: the first build had hole centres and radii moved by inference
    # ---- base: Front plane (XY), extrude +Z 6
    select_plane(doc, "Front Plane")
    sk.InsertSketch(True)
    L = lambda x1,y1,x2,y2: sk.CreateLine(x1*MM,y1*MM,0,x2*MM,y2*MM,0)
    A = lambda cx,cy,x1,y1,x2,y2,d: sk.CreateArc(cx*MM,cy*MM,0,x1*MM,y1*MM,0,x2*MM,y2*MM,0,d)
    L(0,0,75,0); A(75,5,75,0,80,5,1); L(80,5,80,45); A(75,45,80,45,75,50,1); L(75,50,0,50); L(0,50,0,0)
    sk.InsertSketch(True)
    f = ext(fm, 6); assert f, "base extrude"
    stamp("base done vol %.3f (hand 24000-64.380=%.3f)" % (doc.Extension.CreateMassProperty2.Volume*1e9, 24000-64.380))
    # ---- upright: Right plane, sketch x = -Z, y = Y.  Z 0..46 (overlaps base), Y 0..50, extrude +X 6
    select_plane(doc, "Right Plane")
    sk.InsertSketch(True)
    M = lambda z,y: (-z*MM, y*MM)
    def Lm(z1,y1,z2,y2):
        a=M(z1,y1); b=M(z2,y2); sk.CreateLine(a[0],a[1],0,b[0],b[1],0)
    def Am(cz,cy,z1,y1,z2,y2):  # CCW in (Z,Y) becomes CW (-1) in sketch coords
        c=M(cz,cy); a=M(z1,y1); b=M(z2,y2); sk.CreateArc(c[0],c[1],0,a[0],a[1],0,b[0],b[1],0,1)
    Lm(0,0,0,50); Lm(0,50,41,50); Am(41,45,41,50,46,45); Lm(46,45,46,5); Am(41,5,46,5,41,0); Lm(41,0,0,0)
    sk.InsertSketch(True)
    f = ext(fm, 6); assert f, "upright extrude"
    stamp("upright done vol %.3f (hand %.3f)" % (doc.Extension.CreateMassProperty2.Volume*1e9, 24000-64.380+12000-64.380))
    # ---- inside fillet, edge along Y at X6 Z6
    if inside_fillet:
        doc.ClearSelection2(True)
        sel_edge(doc, 6, 25, 6, append=False)
        f = fillet(fm, fillet_r); assert f, "fillet"
        stamp("fillet done vol %.3f (hand %.3f)" % (doc.Extension.CreateMassProperty2.Volume*1e9, 24000-64.380+12000-64.380+171.68))
    # ---- base holes (through, both directions), Front plane
    select_plane(doc, "Front Plane")
    sk.InsertSketch(True)
    for x,y in [(25,10),(25,40),(65,10),(65,40)]:
        sk.CreateCircleByRadius(x*MM, y*MM, 0, 2.75*MM)
    sk.InsertSketch(True)
    f = cut(fm, both=True); assert f, "base holes"
    stamp("base holes vol %.3f (hand %.3f)" % (doc.Extension.CreateMassProperty2.Volume*1e9, 24000-64.380+12000-64.380+171.68-570.20))
    # ---- bore + 4 holes on Right plane (sketch x=-Z, y=Y)
    select_plane(doc, "Right Plane")
    sk.InsertSketch(True)
    zc, yc = 28, 25
    sk.CreateCircleByRadius(-zc*MM, yc*MM, 0, 11*MM)
    for ang in (45,135,225,315):
        z = zc + 15.5*math.cos(math.radians(ang)); y = yc + 15.5*math.sin(math.radians(ang))
        sk.CreateCircleByRadius(-z*MM, y*MM, 0, 1.7*MM)
    sk.InsertSketch(True)
    f = cut(fm, both=True); assert f, "bore"
    # NOTE: through-all both ways from X=0 would also cut anything behind; nothing else on that axis.
    doc.ShowNamedView2("*Isometric", 7)
    return doc

if __name__ == "__main__":
    sharp = len(sys.argv) > 1 and sys.argv[1] == "sharp"
    variant_c = len(sys.argv) > 1 and sys.argv[1] == "c"   # T5: inside fillet R6
    write_mat()
    with launch() as inst:
        sw = inst.sw
        prep(sw)
        stamp(f"launched pid {inst.pid}")
        name = "bracket_sharp" if sharp else ("bracket_c" if variant_c else "bracket")
        doc = build(sw, name, inside_fillet=not sharp, fillet_r=6 if variant_c else 4)
        mp = doc.Extension.CreateMassProperty2
        d0 = mp.Density
        doc.SetMaterialPropertyName2("", SLDMAT, "PETG printed")
        mp = doc.Extension.CreateMassProperty2
        stamp(f"density before {d0:.1f} after material {mp.Density:.1f}")
        vol = mp.Volume/MM**3
        stamp(f"vol {vol:.3f} mm3 SW mass {mp.Mass*1000:.3f} g; at 1190 kg/m3: {vol*1190e-9*1000:.3f} g")
        path = os.path.join(WIP, name + ".SLDPRT")
        e = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0); w = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        ok = doc.Extension.SaveAs3(path, 0, 1, NOTHING, NOTHING, e, w)
        stamp(f"saved {ok} err {e.value} warn {w.value}")
        sw.CloseDoc(doc.GetTitle)
        doc = open_part(sw, path)     # export from the saved file (an export straight after the build was not watertight)
        for ext_ in ("step", "stl"):
            p = os.path.join(WIP, name + "." + ext_)
            r = save_as(doc, p)
            stamp(f"export {ext_} {r} size {os.path.getsize(p) if os.path.exists(p) else None}")
        stamp("stl check " + str(stl_check(os.path.join(WIP, name + ".stl"))))
