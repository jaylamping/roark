"""Assemble results.json from the per-task result files. python make_results.py <final B3 step name>

Every number is read from a file a script wrote; the sentences are the second session's.
"""
import json
import sys

from common import HERE

FINAL = sys.argv[1]
J = lambda n: json.loads((HERE / n).read_text())      # noqa: E731

# ---- B1 -----------------------------------------------------------------------------------------------------------------
b1 = J('b1.json')
B1 = {k: b1[k] for k in ('volume_mm3', 'hand_volume_mm3', 'mass_g', 'bbox_mm', 'bodies', 'stl_watertight')}
B1['spec_questions'] = [
    f'The set-screw hole (axis Z 22.6, dia 4) leaves {b1["measured"]["wall_above_setscrew_mm"]:.1f} mm of boss above it, under the '
    '0.6 mm minimum wall; one diameter of edge distance puts the axis at Z 19 or lower. Is 22.6 a typing error?',
    'The dia 5.5 dowel holes on a dia 30 circle span radius 12.25 to 17.75 and the boss radius is 13: each hole is blind over a '
    f'0.75 mm lune ({b1["measured"]["dowel_lunes_under_boss"][0]["area"]} mm2) under the boss, so a dowel cannot pass through. '
    'The circle needs dia 31.5 or more, or the holes must continue through the boss edge.',
    'The keyway is on +X and the set screw on +Y, 90 degrees apart: a set screw that holds a key normally sits over it. Intended?',
    'Dia 4 for a set screw is neither an M4 tap size (3.3) nor a size for a heat-set insert or a printed thread. Which is meant?',
]
B1.update(status='done', stl_shells=b1['stl_shells'], stl_volume_mm3=b1['stl_volume_mm3'], step_mm=b1['step_mm'], sha256=b1['sha256'],
          notes='First session, kept. Every specified dimension measured on the solid (b1.json measured, b1.log). Built as written; '
                'the four questions are what I would ask before printing.')

# ---- B2 -----------------------------------------------------------------------------------------------------------------
st, var, edges, mod = J('b2_study.json'), J('b2_variant.json'), J('b2_edges.json'), J('b2_model.json')
fine = {r['support']: r for r in st['runs'] if r['el'] == 1.25}
vfine = {r['support']: r for r in var['rows'] if r['el'] == 1.25}
w, h = fine['wall'], fine['holes']
B2 = dict(
    hand_root_stress_mpa=round(st['hand']['root'], 2),
    print_orientation='on its side: layers stacked along Y, the X-Z profile flat on the bed, no supports',
    nodes=w['checks']['nodes'],
    peak_vm_mpa=w['measures']['vm'][0],
    layer_stress_mpa=w['measures']['Y']['tension'][0],
    layer_shear_mpa=h['measures']['Y']['shear'][0],
    sf_yield=w['measures']['vm'][2],
    sf_layer=w['measures']['Y']['tension'][2],
    sf_shear=h['measures']['Y']['shear'][2],
    max_disp_mm=h['checks']['max_disp'],
    reaction_n=h['checks']['reaction'],
    converged=False,
    verdict='fail',
    status='done',
    by_support={k: dict(peak_vm_mpa=r['measures']['vm'][0], peak_vm_at=r['measures']['vm'][1], sf_yield=r['measures']['vm'][2],
                        max_disp_mm=r['checks']['max_disp'], reaction_n=r['checks']['reaction'],
                        sx_plain_section_mpa=r['checks']['sx_top'], sx_hand_mpa=r['checks']['sx_hand'],
                        excluded_within_2mm_of_fixture_and_load=r['excluded_within_dfix'],
                        per_print_direction={d: dict(tension=r['measures'][d]['tension'], shear=r['measures'][d]['shear']) for d in 'XYZ'})
                for k, r in fine.items()},
    convergence_vm={s: [(r['el'], r['checks']['nodes'], r['measures']['vm'][0]) for r in st['runs'] if r['support'] == s] for s in ('holes', 'wall')},
    sharp_side_edges={r['tag']: dict(edge_el=r['edge_el'], tension=r['edges']['tension']['peak'], tension_avg_1mm=r['edges']['tension']['avg_1.0'][0],
                                     shear=r['edges']['shear']['peak'], vm=r['vm'][0]) for r in edges},
    all_round_fillet_variant={k: dict(nodes=r['nodes'], peak_vm_mpa=r['measures']['vm'][0], at=r['measures']['vm'][1], factors_Y=r['factors_Y'])
                              for k, r in vfine.items()},
    mass_g=round(mod['mass_g'], 3), sha256=mod['sha256'],
    notes='First session ran every solve; verdict by the second. The values above are the worse of the two supports at the finest mesh '
          '(vm and layer tension: wall face fixed; layer shear, displacement: holes fixed). converged is false because the two layer '
          'measures peak on the sharp edges where the arm sides meet the plate and double each time the element there halves '
          '(sharp_side_edges); von Mises in the root fillet did converge (1 %). With those edges given the same R3 the corner of the '
          'root carries 21.6 to 23.9 MPa, a factor of 1.88 (wall fixed) to 2.08 (holes fixed) against 2.0 '
          '(all_round_fillet_variant). Printed with layers along X the factor on tension across layers is 1.12; along Z the factor '
          'on shear between layers is 1.75 to 1.95. So no print direction shows 2.0 on all three.')

# ---- B3 -----------------------------------------------------------------------------------------------------------------
steps = J('b3_steps.json')


def step_row(s):
    pad = [min(r['pad_factors_Y'][k] for r in s['rows'] if 'pad_factors_Y' in r) for k in range(3)] if any('pad_factors_Y' in r for r in s['rows']) else None
    return dict(name=s['name'], changed=CHANGED[s['name']], mass_g=s['mass_g'], sf_yield=s['worst_Y'][0], sf_layer=s['worst_Y'][1],
                sf_shear=s['worst_Y'][2], pad_zone_factors=pad, buckling_factor_pinned=s['hand']['buckling_factor_pinned'],
                sizes_mm=sorted({r['el'] for r in s['rows']}, reverse=True), kept=KEPT[s['name']])


CHANGED = {
    's1_truss': 'cantilever replaced by an open triangle printed on its side: 5 mm wall strip, 3 mm chord, 4.5 mm strut, all 10 wide',
    's2_narrow': 'chord and strut narrowed to 5 mm along Y; chord 2.0, strut 5.2 deep',
    's3_chord': 'chord back up to 2.5 mm',
    's4_waist': 'wall strip thinned to 2 mm between the screws',
    's5_trim': 'strip foot and tip block trimmed 1 mm each; three mesh sizes from here on',
    's6_padr': 'R1.5 on the edges where the pad overhangs the narrowed members',
    's7_strap': 'chord and pad kept full width as one strap, only the strut narrowed',
    's8_full': 'back to full-width members, thinner: chord 2.0, strut 4.1',
    's9_thin': 'chord 1.2 (three perimeters), strut 3.6',
    's10_strip': 'wall strip 5 to 3.5 mm thick; strut 3.7 to hold the buckling floor',
}
KEPT = {
    's1_truss': 'yes', 's2_narrow': 'no: yield 1.88', 's3_chord': 'superseded', 's4_waist': 'superseded',
    's5_trim': 'no: see s6', 's6_padr': 'no: under the pad, inside the load mask, shear between layers gives 1.23 to 1.28',
    's7_strap': 'no: shear between layers 0.95 to 1.61 where the strut meets the strap', 's8_full': 'yes',
    's9_thin': 'yes', 's10_strip': 'yes',
}
by = {s['name']: s for s in steps}
fin = by[FINAL]
mass0 = round(mod['mass_g'], 3)
pad_fin = step_row(fin)['pad_zone_factors']
B3 = dict(
    mass_before_g=mass0, mass_after_g=fin['mass_g'], saving_pct=round(100 * (1 - fin['mass_g'] / mass0), 1),
    steps=[step_row(s) for s in steps if s['name'] in CHANGED],
    governing=None,       # filled below
    sf_yield=min(fin['worst_Y'][0], pad_fin[0]), sf_layer=min(fin['worst_Y'][1], pad_fin[1]), sf_shear=min(fin['worst_Y'][2], pad_fin[2]),
    print_orientation='on its side: layers stacked along Y, the X-Z profile flat on the bed, no supports',
    final_step=FINAL, params=fin['params'], fixed_measured=fin['fixed'], hand=fin['hand'], sha256=fin['sha256'],
    other_print_directions={d: [min(r['factors_' + d][k] for r in fin['rows']) for k in range(3)] for d in 'XZ'},
    status='done, over the 45 minute limit (first session 43 min of wall clock, about 20 of them stalled; second 6 min)',
)
B3['governing'] = (
    'None of the three required factors is at 2.0: the lowest is yield, 2.62, in the wall strip between the upper screw and the chord '
    '(hole walls fixed, read 2 mm from the hole). What stopped the thinning: (1) the strut, whose Euler load with pinned ends is '
    f'{fin["hand"]["buckling_factor_pinned"]} times its force, a floor of 2.0 that I set myself because the requirement names no buckling '
    'factor; (2) the chord at 1.2 mm, three 0.4 mm perimeters; (3) the strip, where stress goes with 1/t squared, so 3.0 mm gives 1.94 '
    'by hand and 3.2 mm would save 2 %.')
B3['notes'] = ('Steps s1 to s8 by the first session, s9 and s10 by the second. Factors are the worst of both supports and three mesh sizes, '
               'layers along Y, and include the pad zone inside the load mask (pad_zone_factors), which is what ruled out s5 to s7. '
               'Printed any other way it fails (other_print_directions: yield, layer, shear; layers along Z give 1.31 on tension across '
               'layers at the upper screw). Not modelled: the screw heads on a 3.5 mm strip (42.8 MPa on the fixed hole rim, a fixture '
               'edge, is excluded), creep, and the strut with its real end fixity or as printed.')

# ---- B4 -----------------------------------------------------------------------------------------------------------------
runs = {r['tag']: r for r in J('b4_runs.json') if 'wall_forces_n' in r}
f, m, c, tiny, rev = (runs[k] for k in ('B4_80N_c0p5_e0p2', 'B4_80N_c0p8', 'B4_80N_c1p2', 'B4_0p08N_c0p8', 'B4_m0p08N_c0p8'))
B4 = dict(
    hand_wall_forces_n=[round(80 * 26.9 / 11.9, 1), round(80 * 26.9 / 11.9 - 80, 1)],
    wall_forces_n=f['wall_forces_n'],
    nodes=f['nodes'],
    how_tongue_was_stabilised='two 2 x 2 x 2 mm soft pads (E 0.5 MPa), one bonded to each Y face of the tongue at Z 13 to 15 (on the tilt '
                              'axis, clear of the block and of every contact face), outer faces fixed; they carry at most '
                              f'{f["pad_force_bound_n"]} N of 80',
    block_peak_vm_mpa=f['block_peak_vm_mpa'], block_peak_at_mm=f['block_peak_at_mm'],
    tongue_tip_disp_mm=f['tongue_tip_disp_mm'], reaction_n=f['reaction'],
    valid='forces, load path and displacement: yes. block_peak_vm_mpa: no',
    why='Contact, not a bond: at 0.08 N the tongue swings 0.444 mm through the clearance as a rigid body (0.01717 rad, hand 0.0168 to '
        '0.0176) and rests on the two predicted lines. Reaction -80.0 N. Wall forces from free-body cuts differ by 81.0 N against 80 '
        'applied, are 1.6 % above the hand values as predicted, and hold within 0.8 % over 43,133, 88,263 and 244,072 nodes; the cut '
        'method returns 80.0 N and 800 N.mm above the slot. Pads carry 0.06 %. The block peak is a line contact on the sharp '
        'slot-mouth edge: 35, 38, 53 MPa over the three meshes, above yield, so it is not a stress; 2 mm away the peak is 8.7 MPa and '
        'the 1 mm average 17 to 21 MPa. The reverse-load run did not converge and is INVALID, not used.',
    by_mesh={r['tag']: dict(nodes=r['nodes'], wall_forces_n=r['wall_forces_n'], difference_n=r['wall_forces_difference_n'],
                            tip_ux_mm=r['tongue_tip_ux_mm'], tip_disp_mm=r['tongue_tip_disp_mm'], block_peak_vm_mpa=r['block_peak_vm_mpa'],
                            block_peak_averages=r['block_peak_averages'], block_peak_2mm_clear_mpa=r['block_peak_vm_2mm_clear_of_edges_mpa'],
                            pad_force_bound_n=r['pad_force_bound_n'], seconds=r['seconds']) for r in (c, m, f)},
    tiny_load_0p08N=dict(tip_ux_mm=tiny['tongue_tip_ux_mm'], wall_forces_n=tiny['wall_forces_n'], ux_at_slot_mouth_mm=tiny['tongue_ux_at_slot_mouth_mm'],
                         ux_at_foot_mm=tiny['tongue_ux_at_foot_mm']),
    reverse_load_minus_0p08N=dict(status='INVALID', reason='100 contact iterations, solver reported failure to achieve equilibrium; the saved '
                                  'unconverged result shows wall forces of hundreds of newtons', wall_forces_n=rev['wall_forces_n']),
    status='done, over the 40 minute limit (first session 33 min, second 21 min of wall clock)',
    notes='nodes and the headline values are the 244,072-node solve the first session ran, which broke the 200,000-node memory rule; the '
          '88,263-node mesh gives 184.0 and 102.1 N and is the one to rerun. tongue_tip_disp_mm is the resultant; UX is 0.827.',
)

B5 = dict(problems_found=15, status='done', verdict='not approved',
          notes='REPORT.md, B5. The three that void it on their own: reaction 96 N for 120 N applied; the STL is in inches (1.02 in3 = '
                '16,700 mm3); tension across Z layers read from sigma-x against 45 MPa instead of sigma-z against 22.5.')

out = dict(run='fable-b', B1=B1, B2=B2, B3=B3, B4=B4, B5=B5)
(HERE / 'results.json').write_text(json.dumps(out, indent=1, default=float))
print(json.dumps({k: (v.get('status'), v.get('verdict')) for k, v in out.items() if isinstance(v, dict)}))
print('B3', B3['mass_before_g'], B3['mass_after_g'], B3['saving_pct'], B3['sf_yield'], B3['sf_layer'], B3['sf_shear'], B3['other_print_directions'])
