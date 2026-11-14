"""T6 study: pin in hole, contact only. Usage: python t6_study.py <sizes comma> [stab]"""
import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from fea import *

def setup(cw, doc, stab="softspring", friction=0.0):
    cwdoc, sm, study = new_static_study(cw, "contact")
    sman = study.SolidManager
    comp = sman.GetComponentAt(0, byref_long())
    n = comp.SolidBodyCount
    mats = {}
    for i in range(n):
        b = comp.GetSolidBodyAt(i, byref_long())
        nm = b.SolidBodyName
        lib = "Steel pin" if "Boss-Extrude2" in nm else "PETG printed"
        assert b.SetLibraryMaterial2(SLDMAT, lib), lib
        mats[nm] = mat_report(b)
    faces = body_faces(doc)
    pin = [f for f, i in ((f, face_info(f)) for f in faces) if i["kind"] == "cyl" and abs(i["r"] - 5.0) < 1e-6][0]
    hole = [f for f, i in ((f, face_info(f)) for f in faces) if i["kind"] == "cyl" and abs(i["r"] - 5.1) < 1e-6][0]
    ends = [f for f, i in ((f, face_info(f)) for f in faces) if i["kind"] == "plane" and abs(abs(i["normal"][1]) - 1) < 1e-6 and abs(abs(i["origin"][1]) - 25) < 1e-6]
    bottom = [f for f, i in ((f, face_info(f)) for f in faces) if i["kind"] == "plane" and abs(abs(i["normal"][2]) - 1) < 1e-6 and abs(i["origin"][2]) < 1e-6]
    assert len(ends) == 2 and len(bottom) == 1, (len(ends), len(bottom))
    lr = study.LoadsAndRestraintsManager
    err = byref_long(); r = lr.AddRestraint(0, tuple(bottom), NOTHING, err); assert r is not None, ("restraint", err.value)
    feat = doc.FeatureByName("Front Plane")      # normal = +Z
    for e_ in ends:
        err = byref_long(); fo = lr.AddForce2(0, 0, (e_,), feat, err); assert fo is not None, ("force", err.value)
        g(fo, "ForceBeginEdit"); fo.Unit = 0
        fo.SetForceComponentValues2(False, False, True, 0.0, 0.0, 250.0)
        assert g(fo, "ForceEndEdit") == 0
    cm = study.ContactManager
    err = byref_long(); cs = cm.CreateContactSet2(0, 0, (pin,), (hole,), err); assert cs is not None, ("contact", err.value)
    opts = study.StaticStudyOptions
    info = dict(materials=mats, solver_default=opts.SolverType, contact_options=cs.Options, friction=cs.IncludeFriction)
    return study, dict(pin=pin, hole=hole, ends=ends, bottom=bottom, cs=cs, opts=opts), info

if __name__ == "__main__":
    sizes = [float(s) for s in sys.argv[1].split(",")]
    stab = sys.argv[2] if len(sys.argv) > 2 else "softspring"
    with launch() as inst:
        sw = inst.sw; prep(sw)
        cw = inst.load_simulation()
        doc = open_part(sw, os.path.join(WIP, "pin_block.SLDPRT"))
        stamp(save_as(doc, os.path.join(WIP, "pin_block_t6.SLDPRT")))
        study, h, info = setup(cw, doc)
        stamp(json.dumps(info, default=str))
        opts = h["opts"]
        if stab == "softspring":
            opts.UseSoftSpring2 = True
        stamp(f"stabilisation {stab}; SolverType {opts.SolverType}; UseSoftSpring {opts.UseSoftSpring2}")
        m = study.Mesh
        for s in sizes:
            t0 = time.time()
            rc = study.CreateMesh(0, s, s * 0.05); assert rc == 0, rc
            stamp(f"mesh {s}: nodes {m.NodeCount} elems {m.ElementCount} ({time.time()-t0:.1f}s)")
            if m.NodeCount > 150000: stamp("over node limit"); break
            t0 = time.time(); rc = study.RunAnalysis; stamp(f"solve rc {rc} in {time.time()-t0:.1f}s")
            res = study.Results
            ids, xyz = node_array(m)
            e = byref_long(); mm = res.GetMinMaxStress(9, 0, 1, NOTHING, 3, e); stamp(f"minmax VM {mm}")
            e = byref_long(); rx = np.array(res.GetReactionForcesAndMoments(1, NOTHING, 0, e), float).reshape(-1, 9)
            stamp(f"reaction sum {rx[:,1:4].sum(axis=0).round(3)}")
            for byel in (True, False):
                try:
                    e = byref_long(); pl = res.CreatePlot(2, 13, 3, byel, e)
                    stamp(f"CreatePlot CP byElem={byel}: {pl} err {e.value}")
                    if pl is not None:
                        e = byref_long(); stamp(f"  min/max {pl.GetMinMaxResultValues(e)} {e.value}")
                except Exception as ex: stamp(f"CreatePlot exc {ex}")
            # contact pressure from the nodal stress tensor on the hole face: p = -n.sigma.n, n radial from the hole axis (X0,Z10)
            comps = {}
            for c in (0, 2, 5):   # SX, SZ, TXZ
                cid, cv = surface_values(res, doc, c); comps[c] = dict(zip(cid, cv))
            hid = [int(k) for k in comps[0].keys()]
            P = xyz[np.array(hid) - 1]
            hole_nodes = [(n, p) for n, p in zip(hid, P) if abs(np.hypot(p[0], p[2]-10) - 5.1) < 0.02 and abs(p[1]) <= 15.0001]
            pr = []
            for n, p in hole_nodes:
                r = np.hypot(p[0], p[2]-10); nx, nz = p[0]/r, (p[2]-10)/r
                pr.append((-(comps[0][n]*nx*nx + comps[2][n]*nz*nz + 2*comps[5][n]*nx*nz), n, p))
            pr.sort(key=lambda t: -t[0]); stamp(f"nodal contact pressure on hole ({len(pr)} nodes): max {pr[0][0]:.3f} at {pr[0][2].round(2)}; mean top-10 {np.mean([t[0] for t in pr[:10]]):.3f}")
            try:
                e = byref_long(); cf = res.GetContactForcesAndFriction(1, NOTHING, (h["hole"],), 0, 0, e); stamp(f"contact forces {cf} err {e.value}")
            except Exception as ex: stamp(f"contact forces exc {ex}")
            break
