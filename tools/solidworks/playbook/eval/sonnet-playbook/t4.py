from study import *
import t1
out = {}
with job() as j:
    # --- T3 addendum: the excluded peak on the hole wall
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    add = []
    for el in (2.0, 1.5, 1.0):
        r = run_case(j, d, f'T3B_EL{el}'.replace('.', 'p'), el, ctrl_faces=lambda dd: pick(dd, kind='cyl', r=4.0))
        i = int(np.argmax(r.vm)); at = r.pos[i]
        row = dict(el=el, nodes=r.nodes, vm_all=float(r.vm.max()), at=at.round(2).tolist(), away=r.peak()[0], layer=r.layer_stress((0,0,1))[0],
                   avg=[(rad,) + r.average(at, rad) for rad in (0.5, 1.0, 2.0)])
        # layer stress with no mask at all, and where
        row['layer_nomask'] = r.layer_stress((0, 0, 1), mask=np.ones(len(r.pos), bool))
        add.append(row); print('T3B', row, flush=True)
    close(j.sw, d)
    out['t3b'] = add
    # --- T4: sharp
    d = new_part(j.sw, OUT / 'bracket_sharp.SLDPRT')
    t1.build(d, sharp=True)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d); save(d)
    hv = t1.hand(sharp=True)
    expect('sharp volume vs hand', volume(d), hv, 0.005)
    out['sharp_volume'] = volume(d); out['sharp_hand'] = hv
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'bracket_sharp.SLDPRT')
    rows_full, rs = [], {}
    for el in (3.0, 2.0, 1.5, 1.0):
        r = run_case(j, d, f'T4_EL{el}'.replace('.', 'p'), el)
        rs[el] = r
        corner = (6.0, 25.0, 6.0)
        near = r.in_box([5.0, 0, 5.0, 7.0, 50, 7.0])
        # sy-line: peak vm among nodes within 1 mm of the corner line x=6,z=6
        dist = np.hypot(r.pos[:, 0] - 6, r.pos[:, 2] - 6)
        line = (dist < 0.75) & (r.pos[:, 1] > 8) & (r.pos[:, 1] < 42)
        row = report(r, el)
        row['corner_line_vm_max'] = float(r.vm[line].max()) if line.any() else None
        row['corner_avg_1mm'] = float(r.vm[(dist < 1.0) & (r.pos[:, 1] > 8) & (r.pos[:, 1] < 42)].mean())
        row['corner_avg_2mm'] = float(r.vm[(dist < 2.0) & (r.pos[:, 1] > 8) & (r.pos[:, 1] < 42)].mean())
        row['vm_all_nodes'] = float(r.vm.max()); row['vm_all_at'] = r.pos[np.argmax(r.vm)].round(2).tolist()
        row['sz_plain_x0_z12'] = float(r.s[(np.abs(r.pos[:,2]-12)<1)&(r.pos[:,0]<0.05)&(r.pos[:,1]>10)&(r.pos[:,1]<40),3].mean())
        rows_full.append(row); print('T4', row, flush=True)
    out['t4'] = rows_full
    close(j.sw, d)
(R / 't4_result.json').write_text(json.dumps(out, indent=1, default=str))
