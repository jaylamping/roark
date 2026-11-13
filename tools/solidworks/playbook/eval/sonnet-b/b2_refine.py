"""B2 follow-up: convergence of the governing peak with one exclusion distance (3 mm) and the load tried a second way."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
from swfea import PETG, static

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
NORMALS = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}
res = {}
with job() as j:
    j.simulation()
    d = open_doc(j.sw, OUT / 'wall_bracket_fea.SLDPRT')
    d.ForceRebuild3(False)
    wall = pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 20, 30))
    screws = pick(d, kind='cyl', r=2.25)
    top = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
    fil = pick(d, kind='cyl', r=3.0)
    expect('picks', len(wall) + len(screws) + len(top) + len(fil), 6, 0)
    for support, fx in (('wall', wall), ('screws', screws)):
        rows = []
        for el, c in ((2.0, 0.75), (2.0, 0.5), (2.0, 0.35)):
            r = static(j, d, f'R_{support}_{str(c).replace(".", "p")}', PETG, fixtures=[('fixed', fx)], loads=[('normal', top, 60.0)], el=el,
                       ctrl=[(fil, c)], max_nodes=300000)
            keep = r.away(dist=3.0)
            row = dict(el=el, ctrl=c, nodes=r.nodes, peak=r.peak(keep), peak_unmasked=float(r.vm.max()),
                       avgY=r.layer_stress((0, 1, 0), keep)[0], shearY=r.layer_shear((0, 1, 0), keep)[0],
                       avg_at_peak=r.average(r.peak(keep)[1], 1.0), avg2=r.average(r.peak(keep)[1], 2.0), reaction=r.reaction)
            for nm, n in NORMALS.items():
                row['L_' + nm] = (r.layer_stress(n, keep)[0], r.layer_shear(n, keep)[0])
            rows.append(row)
            log('ROW', support, row)
        res[support] = rows
        (OUT / 'b2_refine.json').write_text(json.dumps(res, indent=1, default=str))
    close(j.sw, d)
