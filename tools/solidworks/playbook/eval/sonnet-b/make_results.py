"""Assemble results.json from the measured json files in cad/_wip/sw-eval/sonnet-b/ (copies in data/)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
O = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
b1 = json.load(open(O / 'b1_measured.json'))
b2 = json.load(open(O / 'b2_measured.json'))
b3 = json.load(open(O / 'b3_measured.json'))
b3fS10 = json.load(open(O / 'b3_final_S10_plate_window.json'))


def sf(i):
    return dict(yield_=45 / i['peak'][0], tens=22.5 / i['layer_Y'][0][0], shear=13 / i['layer_Y'][1][0])


desc = {
    'S0_baseline': 'B2 bracket as specified (plate 40x60x5, arm 10x12 constant)',
    'S1_plate_trim': 'plate trimmed to Y8..32, Z5..56',
    'S2_taper_arm': 'arm depth tapered 13 at the root to 4 at the tip (top flat at Z52)',
    'S3_thin_plate': 'plate 4 mm thick',
    'S4_plate_strip': 'plate narrowed to a 14 mm strip (Y13..27)',
    'S5_big_fillet': 'R5 root fillets, root depth 11 (rejected: yield factor 1.96)',
    'S7_web_slot': 'rectangular web slot through the arm (rejected: sharp slot ends 38 MPa)',
    'S9_pointed_slot': 'pointed-end web slot X13..39 through the arm',
    'S10_plate_window': 'window 8 x 16 cut in the plate between the screws (FINAL)',
    'S11_narrow_tip3': 'strip 12 wide, tip depth 3, plate to Z55, bigger window (lighter, but factors 2.01 and 1.98: not accepted)',
}
order = ['S1_plate_trim', 'S2_taper_arm', 'S3_thin_plate', 'S4_plate_strip', 'S5_big_fillet', 'S7_web_slot', 'S9_pointed_slot',
         'S10_plate_window', 'S11_narrow_tip3']
steps = [dict(step='S0_baseline', what=desc['S0_baseline'], mass_g=round(b2['mass_g'], 2), sf_yield=2.31, sf_layer=4.0, sf_shear=3.2,
              note='el 1.5 values; the finest local mesh gives layer 2.5 and shear 2.4')]
for k in order:
    v = b3.get(k)
    if not v:
        continue
    a, b = sf(v['wall']), sf(v['screws'])
    note = 'el 1.5, worst of wall-face and screw-hole supports, layers stacked along Y'
    if k == 'S11_narrow_tip3':
        note = 'finest mesh of the final convergence run: yield 2.01, shear 1.98 at a singular edge'
        steps.append(dict(step=k, what=desc[k], mass_g=round(v['mass_g'], 2), sf_yield=2.01, sf_layer=4.71, sf_shear=1.98, note=note))
        continue
    steps.append(dict(step=k, what=desc[k], mass_g=round(v['mass_g'], 2), sf_yield=round(min(a['yield_'], b['yield_']), 2),
                      sf_layer=round(min(a['tens'], b['tens']), 2), sf_shear=round(min(a['shear'], b['shear']), 2), note=note))
fin = b3['S10_plate_window']
rows = b3fS10['wall'] + b3fS10['screws']
sfy = min(45 / b3fS10['wall'][-1]['peak'][0], 45 / b3fS10['screws'][-1]['peak'][0])
sfl = 22.5 / max(r['Ytens'][0] for r in rows)
sfs = 13 / max(r['Yshear'][0] for r in rows)
steps[[s['step'] for s in steps].index('S10_plate_window')].update(sf_yield=round(sfy, 2), sf_layer=round(sfl, 2), sf_shear=round(sfs, 2),
                                                                    note='finest mesh of the final convergence run (48,842 nodes), both supports')
res = {
    'run': 'sonnet-b',
    'B1': dict(volume_mm3=b1['volume_mm3'], hand_volume_mm3=b1['hand_volume_mm3'], mass_g=b1['mass_g'], bbox_mm=b1['bbox_mm'], bodies=1,
               stl_watertight=b1['stl_watertight'], stl_volume_mm3=b1['stl_volume'],
               spec_questions=[
                   'The two dia 5.5 dowel holes on the dia 30 circle reach r = 12.25, 0.75 mm inside the dia 26 boss. Cut through the flange only (Z 0..5), each leaves a 1.79 mm2 crescent roof under the boss, so they are not full through holes. Move them out to a circle of dia 32 or more, or accept a blind sliver.',
                   'The dia 4 set-screw hole at Z 22.6 reaches Z 24.6, leaving 0.4 mm to the boss top at Z 25: under the 0.6 mm minimum wall and under one hole diameter. Lower it to Z 20 or less, or lengthen the boss.',
                   'The set-screw hole is a plain dia 4 on one side (+Y) with no thread or tap-drill size (an M4 tap drill is 3.3).',
                   'No fillet or chamfer is given at the flange/boss junction, a stress raiser in a printed part, and no print direction is given (with the axis along Z the layers run across the boss).'],
               status='done',
               notes='Every cylinder centre and radius, the keyway planes and the set-screw axis were read back from the finished solid (REPORT.md). STL 0.25 % below the solid volume (faceting), inside the 0.5 % limit.'),
    'B2': dict(hand_root_stress_mpa=13.75, hand_root_stress_with_kt_mpa=19.4,
               print_orientation='layers stacked along Y (arm and plate lying flat on the bed, printed on their side)', nodes=80572,
               peak_vm_mpa=19.5, layer_stress_mpa=8.92, layer_shear_mpa=5.32, sf_yield=2.31, sf_layer=2.52, sf_shear=2.44,
               max_disp_mm=1.51, reaction_n=60.0,
               converged='von Mises yes (19.43, 19.33, 19.48 over three local sizes); tension across layers and interlayer shear no: they rise at the sharp side edges where the arm meets the plate (singular), so they are reported at the finest mesh',
               verdict='PASS only in the Y-stacked orientation: factors 2.31 on yield, 2.5 on tension across layers and 2.4 on interlayer shear, all at the finest mesh. FAILS printed with layers along X (tension across layers 20.1 MPa, factor 1.12) or along Z (interlayer shear 7.3 MPa, factor 1.79). Thinnest margin 2.31; a 20 % higher load gives 1.93.',
               status='done',
               notes='Support tried two ways: whole X0 face fixed (governing, 19.5) and the two screw-hole walls fixed (18.4 outside 3 mm of the holes; 26 at the hole mouth is the fixture singularity). Load as 60 N even pressure on a bonded 10 mm end block so the patch is its own face; the twin model has the same volume as the one-body part.'),
    'B3': dict(mass_before_g=round(b2['mass_g'], 3), mass_after_g=round(fin['mass_g'], 3),
               saving_pct=round(100 * (1 - fin['mass_g'] / b2['mass_g']), 1), steps=steps,
               governing='von Mises against yield with the screw-hole walls fixed, at the top of the arm just outside the root fillet (6.5, 20, 52): factor 2.08. Interlayer shear is next at 2.47. The next step (S11, 6.95 g) read 2.01 on yield and 1.98 on shear at the finest mesh and was not accepted.',
               sf_yield=round(sfy, 2), sf_layer=round(sfl, 2), sf_shear=round(sfs, 2),
               print_orientation='layers stacked along Y (lying on its side); every cut is through Y so no supports', status='done',
               notes='Model saved as wall_bracket_light.SLDPRT (the S10 file). sf_yield from the screw-fixed case at the finest mesh; sf_layer and sf_shear are the worst over both supports and all four meshes.'),
    'B4': dict(hand_wall_forces_n=[180.8, 100.8], wall_forces_n=[183.3, 103.3], nodes=149727,
               how_tongue_was_stabilised='Four dia 1.8 x 3 mm soft pads (E 0.5 MPa) bonded to the tongue +-Y faces at x +-2, z 24, outer faces fixed; they carry 0.5 % of the load (sum of nodal reaction magnitudes 0.38 N of 80 N). The tongue is two bonded bodies split at Z 30 so the load patch is its own face. Two no-penetration contact sets (+X wall with +X face, -X wall with -X face). The floor was left out and shown not touched (15 to 20 micrometres of clearance left).',
               block_peak_vm_mpa=41.0, block_peak_at_mm=[4.1, -2.73, 20.0], tongue_tip_disp_mm=0.826, reaction_n=80.0,
               valid='yes for forces, displacement and equilibrium; no for the block peak stress as a design number',
               why='Reaction 80.0 N in X on three meshes (35.7k, 78.4k, 149.7k nodes). The shear force through the tongue is 80.0 N above the contacts (z 26 to 28) and 103.3 N between them, flat over z 10 to 18 and within 1.2 % across the meshes, which gives wall forces 183.3 and 103.3 N against the rigid-tongue hand 180.8 and 100.8 (1.4 % and 2.5 %). Contact is real: tongue and wall faces close to within 2 micrometres at the two contact lines and stay 0.1 to 0.28 mm apart elsewhere, and a reversed 0.001 N load moves the tongue 0.11 mm to the other wall. The block peak sits on the top edge of the +X wall, a sharp edge pressed by a flat face, and rises 35.0, 37.5, 41.0 MPa with refinement (singular); 3 mm below the edge the stress converges to 3.9 MPa and mid-wall to 2.5 MPa. A Hertz estimate with a 0.2 to 1 mm edge radius gives 57 to 127 MPa, so that edge will indent whatever the mesh says: chamfer or round it.',
               status='done',
               notes='Integrating nodal stress over the wall faces gave 170 and 80 N (sum 90, 11 % off equilibrium) and was not used. About 11 minutes of the 40.'),
    'B5': dict(problems_found=14, status='done', notes='Listed in REPORT.md under B5, most serious first.'),
}
json.dump(res, open(Path(__file__).resolve().parent / 'results.json', 'w'), indent=1)
print(json.dumps(res['B3']['steps'], indent=1))
