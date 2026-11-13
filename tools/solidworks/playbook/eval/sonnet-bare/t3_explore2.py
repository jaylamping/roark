import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    cw = inst.load_simulation()
    doc = open_part(sw, os.path.join(WIP, "bracket_fea_probe.SLDPRT"))
    bore = faces_where(doc, lambda i: i["kind"]=="cyl" and i["r"]==11.0)[0][0]
    holes = [f for f,i in faces_where(doc, lambda i: i["kind"]=="cyl" and i["r"]==2.75)]
    cwdoc, sm, study = new_static_study(cw, "probe2")
    rc, body = set_material(study)
    lr = study.LoadsAndRestraintsManager
    feat = doc.FeatureByName("Right Plane"); spec = feat.GetSpecificFeature2
    for label, arr in (("dispatch_array", dispatch_array), ("tuple", lambda x: tuple(x)), ("list", lambda x: list(x))):
        for rlabel, ref in (("feature", feat), ("specific", spec), ("none", NOTHING)):
            err = byref_long()
            try:
                r = lr.AddRestraint(0, arr(holes), NOTHING, err)
                print("restraint", label, r is not None, err.value)
                if r is not None: lr.DeleteLoadsAndRestraints(r.Name if hasattr(r,'Name') else "")
            except Exception as e:
                print("restraint", label, "EXC", e)
            err = byref_long()
            try:
                fo = lr.AddForce2(0, 0, arr([bore]), ref, err)
                print("force", label, rlabel, fo is not None, err.value)
            except Exception as e:
                print("force", label, rlabel, "EXC", e)
