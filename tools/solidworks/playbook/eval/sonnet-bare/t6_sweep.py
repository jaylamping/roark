"""T6: contact mesh sweep + stabilisation checks. python t6_sweep.py <stab: softspring|none> <global mm> <local sizes comma> [s2s]"""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from t6_study import *

def t6_rows(res, doc, study, h, ids, xyz, label):
    row = dict(mesh=label, nodes=int(study.Mesh.NodeCount), elements=int(study.Mesh.ElementCount))
    e = byref_long(); pl = res.CreatePlot(2, 13, 3, False, e); assert pl is not None, e.value
    e = byref_long(); mmr = pl.GetMinMaxResultValues(e); row["peak_contact_pressure"] = float(mmr[3]); row["peak_contact_pressure_node"] = int(mmr[2])
    row["peak_contact_pressure_at"] = xyz[int(mmr[2]) - 1].round(2).tolist()
    faces = body_faces(doc)
    infos = [(f, face_info(f)) for f in faces]
    # which body does a face belong to: block faces are those not on the pin (|y|<=25 with pin radius 5): use the body list
    bodies = list(doc.GetBodies2(0, False))
    pin_idx = [i for i, b in enumerate(bodies) if "Boss-Extrude2" in b.Name][0]
    pin_faces = list(g(bodies[pin_idx], "GetFaces")); blk_faces = [f for i, b in enumerate(bodies) if i != pin_idx for f in g(b, "GetFaces")]
    def vm_over(fs):
        e = byref_long(); st = np.array(res.GetStressForEntities2(True, 9, 1, NOTHING, tuple(fs), 3, e), float).reshape(-1, 2)
        k = int(np.argmax(st[:, 1])); return float(st[k, 1]), xyz[int(st[k, 0]) - 1].round(2).tolist()
    row["block_peak_vm"], row["block_peak_at"] = vm_over(blk_faces)
    row["pin_peak_vm"], row["pin_peak_at"] = vm_over(pin_faces)
    row["hole_face_peak_vm"], row["hole_face_peak_at"] = vm_over([h["hole"]])
    e = byref_long(); mm = res.GetMinMaxStress(9, 0, 1, NOTHING, 3, e); row["swminmax_vm"] = float(mm[3])
    e = byref_long(); rx = np.array(res.GetReactionForcesAndMoments(1, NOTHING, 0, e), float).reshape(-1, 9)
    row["reaction_sum_N"] = rx[:, 1:4].sum(axis=0).round(3).tolist(); row["reaction_n"] = float(np.linalg.norm(rx[:, 1:4].sum(axis=0)))
    e = byref_long(); cf = res.GetContactForcesAndFriction(1, NOTHING, (h["hole"],), 0, 0, e); row["contact_normal_force_hole"] = [round(float(x), 3) for x in cf]
    e = byref_long(); uz = np.array(res.GetDisplacementForEntities(2, 1, NOTHING, (h["pin"],), 0, e), float).reshape(-1, 2)
    p = xyz[uz[:, 0].astype(int) - 1]
    mid = np.abs(p[:, 1]) < 0.6
    row["pin_rise_mid_mm"] = float(uz[mid, 1].mean()); row["pin_uz_min_max_mm"] = [float(uz[:, 1].min()), float(uz[:, 1].max())]
    e = byref_long(); ub = np.array(res.GetDisplacementForEntities(2, 1, NOTHING, (h["hole"],), 0, e), float).reshape(-1, 2)
    pb = xyz[ub[:, 0].astype(int) - 1]; top = (np.abs(pb[:, 0]) < 0.8) & (pb[:, 2] > 14.5)
    row["hole_top_uz_mm"] = float(ub[top, 1].mean()) if top.any() else None
    e = byref_long(); d = res.GetMinMaxDisplacement(3, 1, NOTHING, 0, e); row["max_disp_mm"] = float(d[3])
    return row

if __name__ == "__main__":
    stab = sys.argv[1]; glob = float(sys.argv[2]); locs = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] else []
    s2s = len(sys.argv) > 4 and sys.argv[4] == "s2s"
    tag = f"{stab}{'_s2s' if s2s else ''}"
    with launch() as inst:
        sw = inst.sw; prep(sw)
        cw = inst.load_simulation()
        doc = open_part(sw, os.path.join(WIP, "pin_block.SLDPRT"))
        stamp(save_as(doc, os.path.join(WIP, f"pin_block_{tag}.SLDPRT")))
        study, h, info = setup(cw, doc)
        opts = h["opts"]
        if stab == "softspring": opts.UseSoftSpring2 = True
        if s2s:
            cs = h["cs"]; g(cs, "ContactSetBeginEdit"); cs.Options = 2; stamp(f"cs end {g(cs, 'ContactSetEndEdit')} options {cs.Options}")
        opts.SolverType = 1
        stamp(f"solver set {opts.SolverType}; soft spring {opts.UseSoftSpring2}; contact options {h['cs'].Options}")
        rows = []; m = study.Mesh; mc = None
        plan = [(glob, None)] + [(glob, l) for l in locs]
        for gsize, loc in plan:
            if loc is not None:
                mc = local_control(study, [h["pin"], h["hole"]], loc, mc)
            rc = study.CreateMesh(0, gsize, gsize * 0.05); assert rc == 0, rc
            n = m.NodeCount
            if n > 150000: stamp(f"{gsize}/{loc}: {n} nodes > 150000, not solved"); break
            t0 = time.time()
            try:
                rc = study.RunAnalysis
            except Exception as ex:
                stamp(f"solve exception {ex}"); break
            if rc != 0: stamp(f"solve rc {rc} at nodes {n}"); rows.append(dict(mesh=f"{gsize}/{loc}", nodes=int(n), solve_rc=int(rc))); break
            res = study.Results; ids, xyz = node_array(m)
            row = t6_rows(res, doc, study, h, ids, xyz, f"global {gsize} mm" + (f" + {loc} mm control on pin and hole faces" if loc else ""))
            row["solve_s"] = round(time.time() - t0, 1); rows.append(row)
            stamp(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k in ("mesh","nodes","peak_contact_pressure","peak_contact_pressure_at","block_peak_vm","block_peak_at","pin_rise_mid_mm","reaction_n","contact_normal_force_hole","solve_s")}))
            json.dump(dict(info=info, rows=rows), open(os.path.join(EV, f"t6_{tag}_rows.json"), "w"), indent=1, default=str)
        stamp("done")
