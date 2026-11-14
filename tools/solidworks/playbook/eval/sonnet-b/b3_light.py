"""B3: lighten the B2 bracket. Run: python b3_light.py [step names...]  (default: all)"""
import json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
from swfea import PETG, static

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
F = 60.0
RHO = 1.19e-3          # g/mm3

BASE = dict(py0=0, py1=40, pz0=0, pz1=60, tp=5.0, h_root=12.0, h_tip=12.0, r_fil=3.0)
STEPS = {
    'S0_baseline': dict(BASE),
    'S1_plate_trim': dict(BASE, py0=8, py1=32, pz0=5, pz1=56),
    'S2_taper_arm': dict(BASE, py0=8, py1=32, pz0=5, pz1=56, h_root=13.0, h_tip=4.0),
    'S3_thin_plate': dict(BASE, py0=8, py1=32, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0),
    'S4_plate_strip': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0),
    'S7_web_slot': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0, slot=(12.0, 44.0, 0.28, 0.72)),
    'S8_long_slot': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0, slot=(11.0, 48.0, 0.30, 0.70)),
    'S9_pointed_slot': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0, slot=(13.0, 39.0, 0.28, 0.72, 5.0)),
    'S10_plate_window': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=13.0, h_tip=4.0, tp=4.0, slot=(13.0, 39.0, 0.28, 0.72, 5.0), win=(16.0, 24.0, 18.0, 34.0)),
    'S11_narrow_tip3': dict(BASE, py0=14, py1=26, pz0=5, pz1=55, h_root=13.0, h_tip=3.0, tp=4.0, slot=(13.0, 39.0, 0.28, 0.72, 5.0), win=(16.5, 23.5, 17.0, 35.5)),
    'S12_h12': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=12.0, h_tip=4.0, tp=4.0, slot=(13.0, 39.0, 0.28, 0.72, 5.0), win=(16.0, 24.0, 18.0, 34.0)),
    'S5_big_fillet': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=11.0, h_tip=4.0, tp=4.0, r_fil=5.0),
    'S6_plate3': dict(BASE, py0=13, py1=27, pz0=5, pz1=56, h_root=11.0, h_tip=4.0, tp=3.0, r_fil=5.0),
}


def zb(p, x):
    """bottom z of the arm at x"""
    h = p['h_root'] + (p['h_tip'] - p['h_root']) * (x - 5.0) / 60.0
    return 52.0 - h


def build_main(d, p, arm_end):
    tp = p['tp']
    with Sk(d, plane(d, 'X', tp / 2, 'PLATE_P'), 'PLATE') as s:
        s.rect((tp / 2, p['py0'], p['pz0']), (tp / 2, p['py1'], p['pz1']))
    extrude(d, s.feat, 'PLATE', tp, mode=MID, expect_dv=tp * (p['py1'] - p['py0']) * (p['pz1'] - p['pz0']))
    z_root, z_end = zb(p, tp), zb(p, arm_end)
    # arm profile in x-z, extruded 10 wide in y about y = 20; starts at the plate face x = tp (the plate is tp thick)
    pts = [(tp, 20, 52.0), (arm_end, 20, 52.0), (arm_end, 20, z_end), (tp, 20, zb(p, tp))]
    with Sk(d, plane(d, 'Y', 20.0, 'ARM_P'), 'ARM') as s:
        s.poly(pts)
    area = 0.5 * ((52 - z_root) + (52 - z_end)) * (arm_end - tp)
    extrude(d, s.feat, 'ARM', 10.0, mode=MID, expect_dv=area * 10)
    zr = zb(p, tp)
    edges = edges_where(d, lambda q: abs(q[0] - tp) < 0.01 and min(abs(q[2] - 52), abs(q[2] - zr)) < 0.01 and 15 - 0.01 <= q[1] <= 25 + 0.01)
    expect('fillet edges found', len(edges), 2, 0)
    if fillet(d, edges, (p['r_fil'],), 'ROOT_FILLETS') is None:
        raise SystemExit('FAIL fillet')
    if p.get('slot'):
        x0, x1, f0, f1 = p['slot'][:4]      # slot between fractions f0 and f1 of the local arm depth, below the top
        hh = lambda x: 52.0 - zb(p, x)
        tl = p['slot'][4] if len(p['slot']) > 4 else 0.0     # pointed ends: taper length (mm) at each end, tips on the mid-depth line
        fm = (f0 + f1) / 2
        if tl:
            sp = [(x0, 20, 52 - fm * hh(x0)), (x0 + tl, 20, 52 - f0 * hh(x0 + tl)), (x1 - tl, 20, 52 - f0 * hh(x1 - tl)), (x1, 20, 52 - fm * hh(x1)),
                  (x1 - tl, 20, 52 - f1 * hh(x1 - tl)), (x0 + tl, 20, 52 - f1 * hh(x0 + tl))]
        else:
            sp = [(x0, 20, 52 - f0 * hh(x0)), (x1, 20, 52 - f0 * hh(x1)), (x1, 20, 52 - f1 * hh(x1)), (x0, 20, 52 - f1 * hh(x0))]
        with Sk(d, plane(d, 'Y', 20.0, 'WEB_P'), 'WEBSLOT') as s:
            s.poly(sp)
        if tl:
            sa = (f1 - f0) * (hh(x0 + tl) + hh(x1 - tl)) / 2 * (x1 - x0 - 2 * tl) + 0.5 * tl * (f1 - f0) * hh(x0 + tl) + 0.5 * tl * (f1 - f0) * hh(x1 - tl)
        else:
            sa = (f1 - f0) * (hh(x0) + hh(x1)) / 2 * (x1 - x0)
        extrude(d, s.feat, 'WEBSLOT', 12.0, cut=True, mode=MID, expect_dv=sa * 10.0)
    if p.get('win'):
        wy0, wy1, wz0, wz1 = p['win']
        with Sk(d, plane(d, 'X', tp / 2, 'WIN_P'), 'WINDOW') as s:
            s.rect((tp / 2, wy0, wz0), (tp / 2, wy1, wz1))
        extrude(d, s.feat, 'WINDOW', tp, cut=True, mode=MID, expect_dv=tp * (wy1 - wy0) * (wz1 - wz0))
    with Sk(d, plane(d, 'X', tp / 2, 'SCREW_P'), 'SCREWS') as s:
        s.circle((tp / 2, 20, 12), 2.25)
        s.circle((tp / 2, 20, 48), 2.25)
    extrude(d, s.feat, 'SCREWS', tp, cut=True, mode=MID, expect_dv=2 * math.pi * 2.25 ** 2 * tp)
    save(d)


def build_pad(j, p, path):
    d = new_part(j.sw, path)
    z55, z65 = zb(p, 55.0), zb(p, 65.0)
    with Sk(d, plane(d, 'Y', 20.0, 'PAD_P'), 'PAD') as s:
        s.poly([(55, 20, 52.0), (65, 20, 52.0), (65, 20, z65), (55, 20, z55)])
    extrude(d, s.feat, 'PAD', 10.0, mode=MID, expect_dv=0.5 * ((52 - z55) + (52 - z65)) * 10 * 10)
    save(d)
    close(j.sw, d)


def study_step(j, name, p):
    t0 = time.time()
    path = OUT / f'b3_{name}.SLDPRT'
    d = new_part(j.sw, path)
    build_main(d, p, 65.0)
    single_body(d)
    vol = volume(d)
    log(name, 'volume', vol, 'mass', vol * RHO, 'errors', feature_errors(d), 'bbox', bbox(d))
    save(d)
    close(j.sw, d)
    build_pad(j, p, OUT / f'b3_{name}_pad.SLDPRT')
    fea = OUT / f'b3_{name}_fea.SLDPRT'
    d = new_part(j.sw, fea)
    build_main(d, p, 55.0)
    insert_body(d, OUT / f'b3_{name}_pad.SLDPRT')
    expect('fea volume equals deliverable', volume(d), vol, 0.0005)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, fea)
    d.ForceRebuild3(False)
    wall = pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 14, 30))
    screws = pick(d, kind='cyl', r=2.25)
    top = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
    fil = pick(d, kind='cyl', r=p['r_fil'])
    log('picks', len(wall), len(screws), len(top), len(fil))
    expect('wall', len(wall), 1, 0); expect('screws', len(screws), 2, 0); expect('top', len(top), 1, 0); expect('fillets', len(fil), 2, 0)
    res = dict(name=name, params=p, volume=vol, mass_g=vol * RHO)
    for support, fx in (('wall', wall), ('screws', screws)):
        r = static(j, d, f'{name[:2]}{support}', PETG, fixtures=[('fixed', fx)], loads=[('normal', top, F)], el=1.5,
                   ctrl=[(fil, 0.75)], max_nodes=250000)
        keep = r.away(dist=3.0)
        info = dict(nodes=r.nodes, reaction=r.reaction, applied=r.applied, max_disp=r.max_disp(), peak=r.peak(keep),
                    peak_all=float(r.vm.max()), peak_all_at=r.pos[int(np.argmax(r.vm))].round(2).tolist())
        for nm, n in (('X', (1, 0, 0)), ('Y', (0, 1, 0)), ('Z', (0, 0, 1))):
            info['layer_' + nm] = (r.layer_stress(n, keep), r.layer_shear(n, keep))
        res[support] = info
        np.savez(OUT / f'b3_{name}_{support}.npz', pos=r.pos, s=r.s, disp=r.disp)
        log('RESULT', name, support, info)
    close(j.sw, d)
    res['seconds'] = round(time.time() - t0)
    return res


if __name__ == '__main__':
    names = sys.argv[1:] or list(STEPS)
    allres = {}
    pf = OUT / 'b3_measured.json'
    if pf.exists():
        allres = json.loads(pf.read_text())
    for n in names:      # one fresh instance per step: the fifth study of one instance failed with error 24 on 2026-11-13
        with job() as j:
            allres[n] = study_step(j, n, STEPS[n])
            pf.write_text(json.dumps(allres, indent=1, default=str))
