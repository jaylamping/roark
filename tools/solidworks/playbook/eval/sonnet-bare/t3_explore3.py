import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    n0 = len(body_faces(doc))
    print(add_split_annuli(doc), n0, len(body_faces(doc)))
    f = doc.FirstFeature
    while f:
        print(f.Name, f.GetTypeName2, end=" | "); f = f.GetNextFeature
    print()
    doc.EditRebuild3
    print("faces", len(body_faces(doc)), "err", g(doc, "GetFeatureCount"))
