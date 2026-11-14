"""T3: static study of bracket.SLDPRT, mesh sweep. Fixed on the four base-hole faces, 150 N +X on the bore, PETG."""

import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")

from fea import *



def setup_bracket_study(cw, doc, name="static", fixed_faces=None, load_n=150.0):

    cwdoc, sm, study = new_static_study(cw, name)

    rc, body = set_material(study)

    assert rc, "material"

    mr = mat_report(body)

    lr = study.LoadsAndRestraintsManager

    holes = [f for f, i in faces_where(doc, lambda i: i["kind"] == "cyl" and abs(i["r"] - 2.75) < 1e-6 and abs(i["axis"][2]) > 0.99)] if fixed_faces is None else fixed_faces

    assert fixed_faces is not None or len(holes) == 4, len(holes)

    err = byref_long(); r = lr.AddRestraint(0, tuple(holes), NOTHING, err); assert r is not None, ("restraint", err.value)

    bore = faces_where(doc, lambda i: i["kind"] == "cyl" and abs(i["r"] - 11.0) < 1e-6)[0][0]

    feat = doc.FeatureByName("Right Plane")

    err = byref_long(); fo = lr.AddForce2(0, 0, (bore,), feat, err); assert fo is not None, ("force", err.value)

    g(fo, "ForceBeginEdit"); fo.Unit = 0

    fo.SetForceComponentValues2(False, False, True, 0.0, 0.0, float(load_n))

    assert g(fo, "ForceEndEdit") == 0

    return study, mr



if __name__ == "__main__":

    part = sys.argv[1] if len(sys.argv) > 1 else "bracket"

    sizes = [float(s) for s in sys.argv[2].split(",")] if len(sys.argv) > 2 else [4, 3, 2, 1.5, 1.0]

    tag = sys.argv[3] if len(sys.argv) > 3 else "t3"

    with launch() as inst:

        sw = inst.sw; prep(sw)

        cw = inst.load_simulation()

        stamp("simulation loaded")

        doc = open_part(sw, os.path.join(WIP, part + ".SLDPRT"))

        stamp(save_as(doc, os.path.join(WIP, f"{part}_{tag}.SLDPRT")))

        study, mr = setup_bracket_study(cw, doc)

        stamp(f"material {mr}")

        rows = []

        for s in sizes:

            row = study_rows(doc, study, s)

            rows.append(row)

            if "skipped" in row: stamp(f"size {s}: {row['nodes']} nodes, not solved"); break

            stamp(json.dumps({k: row[k] for k in ("el_mm","nodes","peak_vm_all","peak_vm_all_at","peak_vm_away_from_bolts","peak_vm_away_at","peak_vm_root","peak_vm_root_at","peak_sz_tension_away","peak_sz_at","max_disp_mm","reaction_n","solve_s")}))

            json.dump(dict(material=mr, rows=rows), open(os.path.join(EV, f"{tag}_{part}_rows.json"), "w"), indent=1)

            if row["nodes"] > 120000: break

        if len(sys.argv) > 4 and sys.argv[4] == "local":

            # local refinement around the dia 3.4 holes where the peaks sit: global 3 mm + control on those four faces

            small = [f for f, i in faces_where(doc, lambda i: i["kind"] == "cyl" and 1.6 < i["r"] < 1.8)]

            stamp(f"small-hole faces: {len(small)}")

            mc = None
            for sz_ in (1.0, 0.7, 0.5, 0.35, 0.25):


                mc = local_control(study, small, sz_, mc)

                row = study_rows(doc, study, 3.0); row["local_control_mm"] = sz_; rows.append(row)

                stamp(json.dumps({k: row.get(k) for k in ("nodes","local_control_mm","peak_vm_away_from_bolts","peak_vm_away_at","peak_sz_tension_away","peak_sz_at","peak_vm_root","skipped")}))

                json.dump(dict(material=mr, rows=rows), open(os.path.join(EV, f"{tag}_{part}_rows.json"), "w"), indent=1)

        stamp("done")

