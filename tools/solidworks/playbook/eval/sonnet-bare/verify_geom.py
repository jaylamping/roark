"""Print every cylindrical/planar-face fact of a part so hole positions/radii can be checked against the spec."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *
names = sys.argv[1:]
with launch() as inst:
    sw = inst.sw; prep(sw)
    for n in names:
        doc = open_part(sw, os.path.join(WIP, n + ".SLDPRT"))
        print("==", n, "volume", doc.Extension.CreateMassProperty2.Volume*1e9)
        for f, i in faces_where(doc, lambda i: i["kind"] == "cyl" and i["r"] not in (5.0, 4.0)):
            ax = i["axis"]; o = i["origin"]
            c = [o[k] if abs(ax[k]) < 0.5 else None for k in range(3)]
            print("  cyl r", i["r"], "axis", ax, "centre (X,Y,Z) with None = along axis", c)
        flo = sorted({round(i["origin"][2],3) for f,i in faces_where(doc, lambda i: i["kind"]=="plane" and abs(abs(i["normal"][2])-1)<1e-6)})
        print("  planar Z faces at Z:", flo)
