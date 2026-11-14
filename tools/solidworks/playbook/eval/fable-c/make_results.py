"""Collect results.json from what the other scripts wrote. python make_results.py <stem studied> <print axis> <mm from mount>"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
from sheet import read_stl, shape_stats          # noqa: E402

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-c'
STEM, AX, DIST = sys.argv[1], sys.argv[2], sys.argv[3]
ALLOW = dict(vm=45.0, layer=22.5, shear=13.0)
c1 = json.loads((HERE / 'c1_results.json').read_text())
fea = json.loads((HERE / f'c2_fea_{STEM}.json').read_text())
chk = json.loads((HERE / 'c2_check_link_organic.json').read_text())
build = fea.get('build_' + STEM, {})


def sf(case, dist):
    row = fea[case][f'away_{dist}mm']
    return dict(sf_yield=round(ALLOW['vm'] / row['vm'][0], 2), sf_layer=round(ALLOW['layer'] / max(row['layer_' + AX][0], 1e-9), 2),
                sf_shear=round(ALLOW['shear'] / row['shear_' + AX][0], 2), vm=row['vm'], layer=row['layer_' + AX],
                shear=row['shear_' + AX])


cases = {k: sf(k, DIST) for k in ('XP', 'XN', 'YP')}
low = {m: min((cases[k][m], k) for k in cases) for m in ('sf_yield', 'sf_layer', 'sf_shear')}
gov = min((v[0], m, v[1]) for m, v in low.items())
table = {}
for ax in 'XYZ':
    for k in ('XP', 'XN', 'YP'):
        row = fea[k][f'away_{DIST}mm']
        table[f'{k} layers along {ax}'] = dict(sf_yield=round(45 / row['vm'][0], 2), sf_layer=round(22.5 / row['layer_' + ax][0], 2),
                                               sf_shear=round(13 / row['shear_' + ax][0], 2))
res = {
    'C1': dict(volume_mm3=c1['volume_mm3'], hand_volume_mm3=c1['hand_volume_mm3'], mass_g=c1['mass_g'], bodies=c1['bodies'],
               shape=shape_stats(read_stl(OUT / 'link_boxy.stl'))),
    'C2': dict(mass_before_g=c1['mass_g'], mass_after_g=chk['mass_g_from_stl'],
               shape_before=shape_stats(read_stl(OUT / 'link_boxy.stl')),
               shape_after=shape_stats(read_stl(OUT / 'link_organic.stl')),
               print_orientation=f'lying flat, layers stacked along {AX}',
               sf_yield=low['sf_yield'][0], sf_layer=low['sf_layer'][0], sf_shear=low['sf_shear'][0],
               governing=f'{gov[1]} in case {gov[2]} ({gov[0]})', judged_outside_mm_of_mount_and_pin=float(DIST),
               cases=cases, all_print_directions=table,
               fixed_items_ok=chk['fixed_items_ok'], fixed_items=chk,
               ideas_tried=['A bone: one shaft whose section changes all the way (chosen)',
                            'B wishbone: two blades that part from the disc, open between'],
               checkpoints=json.loads((HERE / 'checkpoints.json').read_text()),
               minutes=json.loads((HERE / 'minutes.json').read_text()),
               study=dict(nodes=fea['YP']['nodes'], el_mm=fea['YP']['el'], predicted=fea['predicted'],
                          max_disp_mm={k: fea[k]['max_disp_mm'] for k in ('XP', 'YP')},
                          reaction={k: fea[k]['reaction'] for k in ('XP', 'YP')},
                          coarse=fea.get('YP_coarse'), holes=fea.get('YP_holes'), full=fea),
               model_sha256={f: hashlib.sha256((OUT / f).read_bytes()).hexdigest()
                             for f in ('link_organic.SLDPRT', 'link_organic.step', 'link_organic.stl', 'link_boxy.SLDPRT')},
               build=build,
               repeat_on_unblended_twin=json.loads((HERE / 'c2_fea_link_r3n.json').read_text())['YP']['away_2mm'],
               round1_failed=json.loads((HERE / 'c2_fea_round1.json').read_text())['YP']['away_2mm']),
}
(HERE / 'results.json').write_text(json.dumps(res, indent=1))
print(json.dumps({k: res['C2'][k] for k in ('mass_after_g', 'sf_yield', 'sf_layer', 'sf_shear', 'governing')}, indent=1))
print(json.dumps(table, indent=1))
