"""Sensitivity for T5: bracket_c with the whole bottom face fixed instead of the four bolt-hole walls."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from t3_study import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    cw = inst.load_simulation()
    doc = open_part(sw, os.path.join(WIP, "bracket_c.SLDPRT"))
    stamp(save_as(doc, os.path.join(WIP, "bracket_c_botfix.SLDPRT")))
    bottom = [f for f, i in faces_where(doc, lambda i: i["kind"] == "plane" and abs(abs(i["normal"][2]) - 1) < 1e-6 and abs(i["origin"][2]) < 1e-6 and i["area"] > 3000)]
    stamp(f"bottom faces: {len(bottom)} area {[round(face_info(f)['area']) for f in bottom]}")
    study, mr = setup_bracket_study(cw, doc, fixed_faces=bottom)
    rows = []
    for s in (3.0, 2.0):
        r = study_rows(doc, study, s); rows.append(r)
        stamp(json.dumps({k: (round(v,3) if isinstance(v,float) else v) for k, v in r.items() if k in ("el_mm","nodes","peak_vm_all","peak_vm_all_at","peak_vm_away_from_bolts","peak_sz_tension_away","peak_sx_tension_away","peak_sy_tension_away","max_disp_mm","reaction_n")}))
    small = [f for f, i in faces_where(doc, lambda i: i["kind"] == "cyl" and 1.6 < i["r"] < 1.8)]
    mc = None
    for sz_ in (0.5, 0.3):
        mc = local_control(study, small, sz_, mc)
        r = study_rows(doc, study, 3.0); r["local_control_mm"] = sz_; rows.append(r)
        stamp(json.dumps({k: (round(v,3) if isinstance(v,float) else v) for k, v in r.items() if k in ("local_control_mm","nodes","peak_vm_all","peak_vm_all_at","peak_vm_away_from_bolts","peak_sz_tension_away","peak_sx_tension_away","peak_sy_tension_away","max_disp_mm","reaction_n")}))
    json.dump(rows, open(os.path.join(EV, "t5_botfix_rows.json"), "w"), indent=1)
