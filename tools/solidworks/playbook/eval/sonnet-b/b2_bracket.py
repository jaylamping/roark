"""B2: wall bracket build + static studies. Run: python b2_bracket.py"""
import json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
from swfea import PETG, converge, static

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
OUT.mkdir(parents=True, exist_ok=True)
F = 60.0
NORMALS = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}

# hand values
L_ARM = 60.0 - 5.0                      # load acts at x = 60 (centre of X55..65), root at x = 5
M = F * L_ARM                           # N.mm
I = 10 * 12 ** 3 / 12                   # mm4, arm section 10 wide x 12 deep
HAND_SIGMA = M * 6 / I                  # nominal MPa at the arm root
HAND_DISP = F * L_ARM ** 3 / (3 * PETG['EX'] / 1e6 * I)   # N/mm2 for E; mm


def build_main(d, arm_end):
    """plate + arm to arm_end + 3 mm fillets + screw holes. Returns the volume expected."""
    with Sk(d, plane(d, 'X', 2.5, 'PLATE_P'), 'PLATE') as s:
        s.rect((2.5, 0, 0), (2.5, 40, 60))
    extrude(d, s.feat, 'PLATE', 5.0, mode=MID, expect_dv=12000)
    xm = (5 + arm_end) / 2
    with Sk(d, plane(d, 'X', xm, 'ARM_P'), 'ARM') as s:
        s.rect((xm, 15, 40), (xm, 25, 52))
    extrude(d, s.feat, 'ARM', arm_end - 5.0, mode=MID, expect_dv=(arm_end - 5) * 120)
    edges = edges_where(d, lambda p: abs(p[0] - 5) < 0.01 and min(abs(p[2] - 52), abs(p[2] - 40)) < 0.01 and 15 - 0.01 <= p[1] <= 25 + 0.01)
    expect('fillet edges found', len(edges), 2, 0)
    v0 = volume(d)
    r = fillet(d, edges, (3.0,), 'ROOT_FILLETS')
    if r != 3.0:
        raise SystemExit('FAIL fillet')
    expect('fillet volume added', volume(d) - v0, 2 * (1 - math.pi / 4) * 9 * 10, 0.02)
    with Sk(d, plane(d, 'X', 2.5, 'SCREW_P'), 'SCREWS') as s:
        s.circle((2.5, 20, 12), 2.25)
        s.circle((2.5, 20, 48), 2.25)
    extrude(d, s.feat, 'SCREWS', 5.0, cut=True, mode=MID, expect_dv=2 * math.pi * 2.25 ** 2 * 5)
    save(d)


if __name__ == '__main__':
    t0 = time.time()
    res = {'hand_root_stress_mpa_nominal': round(HAND_SIGMA, 2), 'hand_disp_mm': round(HAND_DISP, 3)}
    print('hand nominal sigma', HAND_SIGMA, 'hand tip disp', HAND_DISP, flush=True)
    with job() as j:
        # 1. the deliverable: one body, arm to 65
        d = new_part(j.sw, OUT / 'wall_bracket.SLDPRT')
        build_main(d, 65.0)
        single_body(d)
        v_full = volume(d)
        hv = 12000 + 7200 - 2 * math.pi * 2.25 ** 2 * 5 + 2 * (1 - math.pi / 4) * 90
        expect('bracket volume', v_full, hv, 0.002)
        log('wall_bracket volume', v_full, 'hand', hv, 'bbox', bbox(d), 'errors', feature_errors(d), 'bodies', len(bodies(d)))
        # measured features
        list_faces(d)
        res['volume_mm3'] = round(v_full, 2)
        res['mass_g'] = round(v_full * 1.19e-3, 3)
        save(d)
        close(j.sw, d)
        # 2. the study copy: arm to 55, pad body X55..65 bonded to it so the 10 mm load patch is its own face
        d = new_part(j.sw, OUT / 'wall_bracket_pad.SLDPRT')
        with Sk(d, plane(d, 'X', 60.0, 'PADX_P'), 'PAD') as s:
            s.rect((60.0, 15, 40), (60.0, 25, 52))
        extrude(d, s.feat, 'PAD', 10.0, mode=MID, expect_dv=1200)
        save(d)
        close(j.sw, d)
        d = new_part(j.sw, OUT / 'wall_bracket_fea.SLDPRT')
        build_main(d, 55.0)
        insert_body(d, OUT / 'wall_bracket_pad.SLDPRT')
        expect('fea volume equals deliverable', volume(d), v_full, 0.0005)
        log('bodies', bodies(d))
        save(d)
        close(j.sw, d)
        cw = j.simulation()
        d = open_doc(j.sw, OUT / 'wall_bracket_fea.SLDPRT')
        d.ForceRebuild3(False)
        wall = pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 20, 30))
        screws = pick(d, kind='cyl', r=2.25)
        top = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
        fil = pick(d, kind='cyl', r=3.0)
        log('picks wall', len(wall), 'screws', len(screws), 'top', len(top), 'fillets', len(fil))
        expect('wall', len(wall), 1, 0); expect('screws', len(screws), 2, 0); expect('top', len(top), 1, 0); expect('fillets', len(fil), 2, 0)
        for f in top:
            log('load face', face_info(f))
        log('PREDICT: nodes 15k-45k at el 2, disp ~1.2-1.6 mm, peak vm at arm root top fillet near (5..8, 15..25, 52)')

        def run(support):
            fx = [('fixed', wall)] if support == 'wall' else [('fixed', screws)]
            def go(el):
                return static(j, d, f'B2_{support}_' + str(el).replace('.', 'p'), PETG, fixtures=fx, loads=[('normal', top, F)], el=el,
                              ctrl=[(fil, el / 2)], max_nodes=200000)
            return go
        out = {}
        for support in ('wall', 'screws'):
            go = run(support)
            rows, ok = converge(go, (3.0, 2.0, 1.5), layers=(0, 1, 0))
            log('CONVERGE', support, rows, ok)
            out[support] = dict(rows=rows, converged=ok)
            if not ok:
                rows2, ok2 = converge(go, (2.0, 1.5, 1.0), layers=(0, 1, 0))
                log('CONVERGE-2', support, rows2, ok2)
                out[support]['rows2'] = rows2
                out[support]['converged2'] = ok2
        # finest results kept for each support at 1.5
        for support in ('wall', 'screws'):
            r = run(support)(1.5)
            keep = r.away(dist=3.0)
            info = dict(nodes=r.nodes, reaction=r.reaction, applied=r.applied, max_disp=r.max_disp(),
                        peak_all=float(r.vm.max()), peak_all_at=r.pos[int(np.argmax(r.vm))].round(2).tolist())
            info['peak_away'] = r.peak(keep)
            for name, n in NORMALS.items():
                info['layer_' + name] = (r.layer_stress(n, keep), r.layer_shear(n, keep))
            info['avg_plain_arm'] = r.average((30, 20, 52), 2.0)
            info['sx_plain_arm_top'] = float(r.s[(abs(r.pos[:, 0] - 30) < 2) & (r.pos[:, 2] > 51.0), 1].mean())
            out[support]['final'] = info
            np.savez(OUT / f'b2_{support}.npz', pos=r.pos, s=r.s, disp=r.disp)
            log('FINAL', support, info)
        res['studies'] = out
        res['seconds'] = round(time.time() - t0)
        (OUT / 'b2_measured.json').write_text(json.dumps(res, indent=1, default=str))
        close(j.sw, d)
