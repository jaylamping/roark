from t6 import *
with job() as j:
    d = open_doc(j.sw, OUT / 'ct6.SLDPRT')
    r = solve(j, d, 'T6_NOCONTACT', 3.0, 0.8, contact=False, loose_ok=True)
    rad = np.hypot(r.pos[:, 0], r.pos[:, 2] - 10)
    pin = (rad < 5.05)
    pa = pin & (rad < 1.0) & (np.abs(r.pos[:, 1]) < 14)
    out = dict(nodes=r.nodes, excessive=r.excessive, pin_rise_mm=float(r.disp[pa, 3].mean()), max_disp=r.max_disp(), reaction=r.reaction)
    print(out)
    (R / 't6_proof.json').write_text(json.dumps(out, indent=1))
    close(j.sw, d)
