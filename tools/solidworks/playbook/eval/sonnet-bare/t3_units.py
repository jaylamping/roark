import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from t3_study import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    cw = inst.load_simulation()
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    study, mr = setup_bracket_study(cw, doc)
    rc = study.CreateMesh(0, 3.0, 0.15); rc2 = study.RunAnalysis
    res = study.Results
    for u in (0, 1, 2, 3):
        e = byref_long(); d = res.GetMinMaxDisplacement(3, 1, NOTHING, u, e); print("disp unit", u, d, e.value)
    ids, xyz = node_array(study.Mesh)
    e = byref_long()
    # per-node URES on all faces: unit 0
    for u in (0, 3):
        e = byref_long(); un = np.array(res.GetDisplacementForEntities(3, 1, NOTHING, tuple(body_faces(doc)), u, e), float).reshape(-1, 2)
        k = int(np.argmax(un[:,1])); print("unit", u, "max", un[k,1], "at", xyz[int(un[k,0])-1].round(2))
    # displacement UX at bore top (Z=46) edge
    e = byref_long(); un = np.array(res.GetDisplacementForEntities(0, 1, NOTHING, tuple(body_faces(doc)), 0, e), float).reshape(-1, 2)
    p = xyz[un[:,0].astype(int)-1]; sel = (p[:,2]>45.9)&(p[:,0]<0.1); print("UX at top Z=46 X=0, unit0: mean", un[sel,1].mean(), "range", un[sel,1].min(), un[sel,1].max())
    sel = (np.abs(p[:,2]-6)<0.1)&(p[:,0]<0.1); print("UX at Z=6 X=0:", un[sel,1].mean())
