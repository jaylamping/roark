"""T4: same load case on bracket_sharp (no inside fillet). Convergence of the corner stress."""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from t3_study import *

def corner_edge(doc):
    body = doc.GetBodies2(0, False)[0]
    for e in g(body, "GetEdges"):
        try:
            a = g(g(e, "GetStartVertex"), "GetPoint"); b = g(g(e, "GetEndVertex"), "GetPoint")
        except Exception:
            continue
        pts = [[x/MM for x in a], [x/MM for x in b]]
        if all(abs(p[0]-6) < 1e-3 and abs(p[2]-6) < 1e-3 for p in pts) and abs(abs(pts[0][1]-pts[1][1]) - 50) < 1e-3:
            return e
    raise RuntimeError("corner edge not found")

def corner_extra(res, doc, study, ids, xyz):
    vid, vm = surface_values(res, doc, 9)
    p = xyz[vid - 1]
    sel = np.where((np.abs(p[:,0]-6) < 0.2) & (np.abs(p[:,2]-6) < 0.2) & (p[:,1] > 5) & (p[:,1] < 45))[0]
    out = {}
    if len(sel):
        k = sel[int(np.argmax(vm[sel]))]; out["corner_vm"] = float(vm[k]); out["corner_at"] = p[k].round(3).tolist(); out["corner_nodes"] = int(len(sel))
    return out

if __name__ == "__main__":
    with launch() as inst:
        sw = inst.sw; prep(sw)
        cw = inst.load_simulation()
        doc = open_part(sw, os.path.join(WIP, "bracket_sharp.SLDPRT"))
        stamp(save_as(doc, os.path.join(WIP, "bracket_sharp_t4.SLDPRT")))
        study, mr = setup_bracket_study(cw, doc)
        rows = []
        def show(row, label):
            row["mesh"] = label; rows.append(row)
            stamp(json.dumps({k: (round(v,3) if isinstance(v,float) else v) for k, v in row.items() if k in ("mesh","nodes","corner_vm","corner_at","peak_vm_away_from_bolts","peak_vm_away_at","peak_sz_tension_away","peak_sz_at","peak_vm_root","peak_vm_root_at","reaction_n","max_disp_mm","skipped")}))
            json.dump(dict(material=mr, rows=rows), open(os.path.join(EV, "t4_rows.json"), "w"), indent=1)
        for s in (3.0, 2.0, 1.5):
            show(study_rows(doc, study, s, extra=corner_extra), f"global {s} mm")
        edge = corner_edge(doc)
        mc = None
        for sz_ in (1.0, 0.5, 0.25, 0.12, 0.06):
            mc = local_control(study, [edge], sz_, mc)
            row = study_rows(doc, study, 3.0, extra=corner_extra); row["local_control_mm"] = sz_
            show(row, f"global 3.0 mm + {sz_} mm control on the corner edge")
            if row["nodes"] > 120000: break
        stamp("done")
