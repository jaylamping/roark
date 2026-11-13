from study import *
out = []
with job() as j:
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    for el in (3.0, 2.0, 1.5):
        r = run_case(j, d, f'T5A_EL{el}'.replace('.', 'p'), el, ctrl_faces=lambda dd: pick(dd, kind='cyl', r=4.0))
        m4 = r.away(4.0 / el)       # fixed 4 mm clearance from fixtures and loads
        row = dict(el=el, nodes=r.nodes, vm_away4=r.peak(m4), vm_away_2el=r.peak(),
                   layerZ=r.layer_stress((0, 0, 1), m4), layerX=r.layer_stress((1, 0, 0), m4), layerY=r.layer_stress((0, 1, 0), m4),
                   layerZ_all=r.layer_stress((0, 0, 1), np.ones(len(r.pos), bool))[0],
                   sx_max=float(r.s[m4, 1].max()), tension_xx_where=r.pos[m4][np.argmax(r.s[m4,1])].round(2).tolist())
        out.append(row); print('T5A', row, flush=True)
    close(j.sw, d)
(R / 't5a_result.json').write_text(json.dumps(out, indent=1, default=str))
