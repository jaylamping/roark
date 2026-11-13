"""B3: convergence of a chosen step with one 3 mm exclusion distance. Run: python b3_final.py S11_narrow_tip3"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from b3_light import *      # noqa: E402,F401,F403
from b3_light import STEPS, OUT  # noqa: E402

name = sys.argv[1]
p = STEPS[name]
res = {}
with job() as j:
    j.simulation()
    d = open_doc(j.sw, OUT / f'b3_{name}_fea.SLDPRT')
    d.ForceRebuild3(False)
    wall = pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 14, 30))
    screws = pick(d, kind='cyl', r=2.25)
    top = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
    fil = pick(d, kind='cyl', r=p['r_fil'])
    expect('picks', len(wall) + len(screws) + len(top) + len(fil), 6, 0)
    for support, fx in (('screws', screws), ('wall', wall)):
        rows = []
        for el, c in ((2.0, 0.75), (2.0, 0.5), (2.0, 0.35), (1.5, 0.35)):
            r = static(j, d, f'F_{support}_{str(el).replace(".", "p")}_{str(c).replace(".", "p")}', PETG, fixtures=[('fixed', fx)], loads=[('normal', top, 60.0)], el=el,
                       ctrl=[(fil, c)], max_nodes=300000)
            keep = r.away(dist=3.0)
            pk = r.peak(keep)
            row = dict(el=el, ctrl=c, nodes=r.nodes, peak=pk, reaction=r.reaction, avg1=r.average(pk[1], 1.0), avg2=r.average(pk[1], 2.0),
                       Ytens=r.layer_stress((0, 1, 0), keep), Yshear=r.layer_shear((0, 1, 0), keep), disp=r.max_disp(),
                       L_X=r.layer_stress((1, 0, 0), keep)[0], L_Z=(r.layer_stress((0, 0, 1), keep)[0], r.layer_shear((0, 0, 1), keep)[0]))
            rows.append(row)
            log('ROW', support, row)
        res[support] = rows
        (OUT / f'b3_final_{name}.json').write_text(json.dumps(res, indent=1, default=str))
    close(j.sw, d)
