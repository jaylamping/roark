"""C2 study: 60 N at the wrist pin in +X, -X and +Y, elbow mounting face held. python c2_fea.py [el]

Two solves (+X, +Y) at the working mesh; -X is the +X result with every stress reversed (linear study, and the part
and its support are mirror images about X 0), so von Mises and layer shear are the same and only the sign of the
tension across layers changes. Then the governing case again on a coarser mesh and with the support a second way
(the six screw-hole walls instead of the face). Four studies, one instance (05-fea.md: at most four).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
from swfea import PETG, static          # noqa: E402
from swkit import *                     # noqa: E402,F403

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-c'
HERE = Path(__file__).resolve().parent
EL = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5
STEM = sys.argv[2] if len(sys.argv) > 2 else 'link_organic'
F = 60.0
PIN = (0.0, 0.0, -200.0)
DIRS = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}
ALLOW = dict(vm=45.0, layer=22.5, shear=13.0)

# predictions, written before the solve (07-done.md)
PRED = {'nodes': 125000,
        'XP': dict(disp_mm=3.5, peak='neck edges at x = +-a, Z -35 to -50, about 5 to 6 MPa'),
        'YP': dict(disp_mm=5.0, peak='neck +-Y skin at Z -28 to -36 just outside the mount, about 12 to 18 MPa')}
log('PREDICTED', PRED)


def read(r, flip=False):
    """The three measures for each print direction, outside 1, 2, 3 and 5 mm from the fixture and load faces."""
    if flip:
        r.s = r.s.copy()
        r.s[:, 1:10] *= -1          # all stress components and principals reverse; von Mises (col 10) does not
    out = dict(nodes=r.nodes, el=r.el, max_disp_mm=round(r.max_disp(), 3), reaction=[round(float(v), 2) for v in r.reaction],
               vm_all=round(float(r.vm.max()), 2))
    for dist in (1.0, 2.0, 3.0, 5.0):
        m = r.away(dist=dist)
        vm, at = r.peak(m)
        row = dict(vm=[round(vm, 2), at])
        for k, n in DIRS.items():
            a, b = r.layer_stress(n, m), r.layer_shear(n, m)
            row['layer_' + k] = [round(a[0], 2), a[1]]
            row['shear_' + k] = [round(b[0], 2), b[1]]
        out[f'away_{dist:g}mm'] = row
    # the plain section, against the hand value: shaft skin at Z -110
    out['shaft_z-110_vm_mean'] = [round(float(r.vm[(np.abs(r.pos[:, 2] + 110) < 2)].max()), 2)]
    return out


def picks(d):
    face = pick(d, kind='plane', at=(0, -4, 20))
    pins = pick(d, kind='cyl', r=4.0, inside=[-5, -25, -205, 5, 25, -195])
    bolts = pick(d, kind='cyl', r=1.7, inside=[-28, -5, -28, 28, 5, 28])
    log('picks: mount face', len(face), 'pin faces', len(pins), 'bolt walls', len(bolts))
    if len(face) != 1 or len(pins) != 2 or len(bolts) != 6:
        list_faces(d)
        raise Failed('a pick has the wrong count')
    return face, pins, bolts


res = {'predicted': PRED, 'el': EL}
with job() as j:
    j.simulation()
    if 'build' in sys.argv:          # build the round-2 link in this same instance: launches are scarce today
        import subprocess
        import c2_build
        ok = {}
        for stem, neck in ((STEM, True), (STEM + 'n', False)):       # with the neck blend, and without it as a fallback
            d = new_part(j.sw, OUT / f'{stem}.SLDPRT')
            c2_build.LAST.clear()
            c2_build.bone(d, True, neck=neck, rows=c2_build.BONE2)
            res['build_' + stem] = c2_build.finish(j, d, stem)
            res['build_' + stem]['neck_blend'] = c2_build.LAST.get('neck_blend')
            export(j.sw, d, OUT / f'{stem}.step')
            close(j.sw, d)
            subprocess.run([sys.executable, str(ROOT / 'tools' / 'pc' / 'capped.py'), '--mb', '4096', '--', sys.executable,
                            str(HERE / 'c2_check.py'), stem], cwd=str(HERE), capture_output=True)
            chk = json.loads((HERE / f'c2_check_{stem}.json').read_text())
            ok[stem] = chk['fixed_items_ok'] and (not neck or bool(res['build_' + stem]['neck_blend']))
            log(stem, 'fixed items ok:', chk['fixed_items_ok'], chk['failed'], 'neck blend', res['build_' + stem]['neck_blend'])
        if not ok[STEM]:
            log('the blended link is not usable: the study runs on the unblended one')
            STEM = STEM + 'n'
        res['studied'] = STEM
    d = open_doc(j.sw, OUT / f'{STEM}.SLDPRT')
    d.ForceRebuild3(False)

    def run(name, force, el, support='face'):
        face, pins, bolts = picks(d)
        r = static(j, d, name, PETG, fixtures=[('fixed', face if support == 'face' else bolts)],
                   loads=[('remote', pins, PIN, force, (0, 0, 0))], el=el, ctrl=[(pins, 1.0)], loose_ok=True,
                   max_nodes=199000)
        log(r.summary())
        np.savez_compressed(OUT / f'fea_{STEM}_{name}.npz', pos=r.pos, s=r.s, disp=r.disp, fixed=r.fixed_pts, loaded=r.loaded_pts)
        return r

    r = run('XP', (F, 0, 0), EL)
    res['XP'] = read(r)
    res['XN'] = read(r, flip=True)
    res['XN']['note'] = '+X result reversed'
    (HERE / f'c2_fea_{STEM}.json').write_text(json.dumps(res, indent=1))
    r = run('YP', (0, F, 0), EL)
    res['YP'] = read(r)
    (HERE / f'c2_fea_{STEM}.json').write_text(json.dumps(res, indent=1))
    r = run('YP_coarse', (0, F, 0), EL * 1.6)
    res['YP_coarse'] = read(r)
    (HERE / f'c2_fea_{STEM}.json').write_text(json.dumps(res, indent=1))
    r = run('YP_holes', (0, F, 0), EL, support='holes')
    res['YP_holes'] = read(r)
    (HERE / f'c2_fea_{STEM}.json').write_text(json.dumps(res, indent=1))
    close(j.sw, d)
print(json.dumps(res)[:3000])
