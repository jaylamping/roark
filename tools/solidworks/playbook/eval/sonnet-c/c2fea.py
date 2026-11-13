"""(support variant: SUPPORT=holes fixes the six screw-hole walls instead of the ring)
C2 FEA: 60 N at the wrist pin in +X, -X, +Y, elbow ring fixed. Usage: c2fea.py <model_name> <el_mm> [cases]"""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
import swfea
from swfea import PETG, static

def main(name, el, cases):
    out = {}
    with job() as j:
        j.simulation()
        d = open_doc(j.sw, WIP / f'{name}.SLDPRT')
        d.ForceRebuild3(False)
        ring = [f for f in pick(d, kind='plane', normal=(0, -1, 0)) if abs(face_info(f)['box'][1] + 4.0) < 0.02]
        pin = pick(d, kind='cyl', r=4.0, inside=[-5, -30, -204.1, 5, 30, -195.9])
        log('ring faces', len(ring), [face_info(f)['area'] for f in ring], 'pin faces', len(pin), [face_info(f)['box'] for f in pin])
        assert len(ring) >= 1 and len(pin) == 2
        for cname, F in cases:
            log(f'PREDICT {cname}: nodes about 60000, disp about 2-6 mm, peak at the neck near the disc')
            ring = [f for f in pick(d, kind='plane', normal=(0, -1, 0)) if abs(face_info(f)['box'][1] + 4.0) < 0.02]
            pin = pick(d, kind='cyl', r=4.0, inside=[-5, -30, -204.1, 5, 30, -195.9])
            holes = pick(d, kind='cyl', r=1.7)
            r = static(j, d, cname, PETG, fixtures=[('fixed', holes if os.environ.get('SUPPORT') == 'holes' else ring)],
                       loads=[('remote', pin, (0.0, 0.0, -200.0), F, (0, 0, 0))], el=el,
                       ctrl=[(pin, 1.2)], loose_ok=True)
            s = r.summary()
            row = dict(summary=s, reaction=r.reaction, applied=r.applied)
            for nm, nrm in (('layers_Y', (0, 1, 0)), ('layers_X', (1, 0, 0)), ('layers_Z', (0, 0, 1))):
                ts, tsat = r.layer_stress(nrm)
                sh, shat = r.layer_shear(nrm)
                row[nm] = dict(tension_MPa=round(ts, 2), tension_at=tsat, shear_MPa=round(sh, 2), shear_at=shat,
                               sf_tension=round(22.5 / max(ts, 1e-9), 2), sf_shear=round(13.0 / max(sh, 1e-9), 2))
            row['peak_all'] = float(r.vm.max()); row['peak_all_at'] = r.pos[int(r.vm.argmax())].round(1).tolist()
            for dist in (1, 2, 3, 5):
                m_ = r.away(dist=dist * el)
                row[f'peak_away_{dist}el'] = r.peak(m_)
            np.savez_compressed(ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-c' / f'{name}_{cname}.npz', pos=r.pos, s=r.s, disp=r.disp)
            out[cname] = row
            log(json.dumps(row, default=str))
            d.ForceRebuild3(False)
        close(j.sw, d)
    json.dump(out, open(EV / f'fea_{name}_{el}{os.environ.get("SUPPORT", "")}.json', 'w'), indent=1, default=str)

if __name__ == '__main__':
    name, el = sys.argv[1], float(sys.argv[2])
    cases = [('PX', (60.0, 0, 0)), ('MX', (-60.0, 0, 0)), ('PY', (0, 60.0, 0))]
    if len(sys.argv) > 3:
        cases = [c for c in cases if c[0] in sys.argv[3].split(',')]
    main(name, el, cases)
