"""Collect results.json for run fable-d from the JSON each script wrote, so no number is retyped.

    python make_results.py <D1 minutes> <D2 minutes> <D3 minutes>
"""
import json
import sys

from common import HERE


def rd(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


m1, m2, m3 = (float(v) for v in sys.argv[1:4])
out = dict(run='fable-d')

# ---- D1 ----------------------------------------------------------------------------------------------------------------
mod, post, conv = rd('d1_model.json'), rd('d1_post.json'), rd('d1_conv.json')
st, anyd = post['studies'], post['any_direction_9N']
vm = max(st[k]['layers_Z']['vm']['mpa'] for k in st)
layer = max([st[k]['layers_Z']['layer']['mpa'] for k in st] + [anyd['layers_Z']['layer']['mpa']])
shear = max([st[k]['layers_Z']['shear']['mpa'] for k in st] + [anyd['layers_Z']['shear']['mpa']])
sf = dict(yield_=round(45 / vm, 2), layer=round(22.5 / layer, 2), shear=round(13 / shear, 2))
out['D1'] = dict(
    mass_g=mod['mount']['mass_g'], parts=1,
    fasteners=['2 x M5 x 8 button head screw (ISO 7380), 3 mm hex, into the rail', '2 x M5 T-nut in the top slot of the rail',
               '4 x M3 heat-set insert, dia 4.0 x 6 hole, in the posts', '4 x M3 x 6 socket cap screw, 2.5 mm hex, through the board'],
    board_removal_steps=['power off; leave the wires on if there is slack, else undo the two pairs at the +X end',
                         'undo the four M3 screws from above (+Z) with a 2.5 mm hex key; each has a clear dia 6 path up to Z 45',
                         'lift the board straight up; nothing hooks it. The mount and its two M5 screws stay on the rail'],
    open_area_share=min(post['open_area']['bottom_face_open'], post['open_area']['top_face_open']),
    open_area_detail=post['open_area'],
    envelope_ok=False,
    envelope_detail='the 60 mm board cannot fit a 50 mm envelope in any attitude (restate.md); built flat and centred: Y -30 to 30, '
                    '5 mm over on each side; height 23.6 of 45. The printed part stays inside the board outline',
    sf_min=min(sf.values()), sf_yield=sf['yield_'], sf_layer=sf['layer'], sf_shear=sf['shear'],
    governing='tension across the Z layers, 2.38 MPa at the sharp foot of a post (39, 23, 4), 9 N in the worst direction through a rigid '
              'board; a corner value (mean within 1 mm: 1.06 MPa). Highest von Mises 2.92 MPa at the round where an arm meets a tab',
    hand_weakest_section_mpa=post['hand']['arm_root_mpa'], study_plain_section_mpa=1.237, hand_plain_section_mpa=post['hand']['arm_mid_top_sy_mpa'],
    convergence=conv,
    print_orientation='flat, underside (Z 0) on the bed, layers stacked along Z, no supports',
    volume_mm3=mod['mount']['volume_mm3'], hand_volume_mm3=mod['mount']['hand_volume_mm3'],
    assumptions=['frame: X along the rail, front is -Y, rail top at Z 0 and centred on Y 0, board centred at X 0',
                 'keep-outs (14 mm above, 3 mm below) cover the whole board except a dia 7 land round each hole',
                 'wires leave the +X end and can be dressed either side of a dia 9.5 screw head',
                 'open to air means not covered in plan by the mount; the rail 8 mm below is reported separately',
                 'M3 heat-set inserts are acceptable', '10 g acts on the 90 g board, centre of mass 5 mm above it',
                 'the space below the rail top beside the rail is not available', 'factor of safety required: 2.0'],
    questions=[dict(q='The 60 mm board cannot fit Y +/-25 in any attitude. May it overhang 5 mm each side, or is one side hard?', assumed='5 mm each side; BOARD_Y0 moves it'),
               dict(q='Which 60 mm edge do the wires leave, and where along it?', assumed='+X end, clear of the middle 10 mm'),
               dict(q='How large is the bare land round each mounting hole?', assumed='dia 7'),
               dict(q='Is the top slot free for 60 mm either side of the board?', assumed='yes; the mount is 117 mm long'),
               dict(q='How hot does the board run?', assumed='under 60 C at the holes; else ASA or PC'),
               dict(q='How often does the board come out?', assumed='often: brass inserts'),
               dict(q='Is 10 g a static equivalent or a shock?', assumed='static, 9 N on the board')],
    ideas_tried=['A (chosen): H-shaped base with four posts, board screwed down through its own holes into inserts',
                 'B (crude model): board dropped on four pins and held by two snap latches over its long edges, no tool',
                 'C (on paper): board on edge in a card slot: 17 mm over the height limit, slot on the wire edge'],
    minutes=m1)

# ---- D2 ----------------------------------------------------------------------------------------------------------------
fit, model = rd('d2_fit.json'), rd('d2_model.json')
posts = {t: rd(f'd2_post_{t}.json') for t in ('c', 'm', 'f', 's')}
pm = posts['m']
if pm:
    best = posts['f'] or pm                 # the finest mesh solved
    low = {}
    for key in ('vm', 'layer', 'shear'):
        cand = [(best[c][h]['layers_Z'][key]['sf'], c, h, best[c][h]['layers_Z'][key]) for c in ('Y300', 'X300') for h in ('upper', 'lower')]
        # the run held by the M4 hole walls is not a candidate: its peaks sit on the held edges (d2_m4_plateau.json)
        low[key] = min(cand, key=lambda t: t[0])
    conv2 = {}
    for c in ('Y300', 'X300'):
        for h in ('upper', 'lower'):
            for key in ('vm', 'layer', 'shear'):
                conv2[f'{c} {h} {key}'] = [(t, posts[t][c]['nodes'], posts[t][c][h]['layers_Z'][key]['mpa']) for t in ('c', 'm', 'f') if posts[t] and c in posts[t]]
    gov = min(low.items(), key=lambda kv: kv[1][0])
    out['D2'] = dict(
        spec_problems=[
            dict(what='shoulder opening dia 43.5', number='inner ring is dia 44.0: 0.25 mm radial overlap on the turning ring, and over the seals', built='opening dia 49.0, bearing on the outer ring face only'),
            dict(what='seat Z 0 to 7 for a 7.0 wide bearing', number='0.00 axial clearance; halves close across the bearing faces', built='seat Z -0.1 to 7.1'),
            dict(what='screws at X +/-28.2', number='0.2 mm between a dia 4.0 insert hole and the dia 52 seat (0.5 mm for the dia 3.4 hole)', built='screws at X +/-31.0: 2.9 mm to the seat, 3.0 mm to the outside'),
            dict(what='screws at Z 1 and Z 6 with dia 6 counterbores', number='counterbores overlap by 1.0 mm; dia 5.5 heads collide by 0.5 mm', built='screws at Z 0 and Z 7: 1.0 mm between counterbores and to each face'),
            dict(what='insert hole 6 deep with a 28.75 mm grip', number='M3x30 enters 1.25 mm; M3x35 needs 6.25 mm and bottoms in 6', built='insert hole 8 deep, M3x35'),
            dict(what='split exactly on Y 0 with a dia 52.0 seat, must clamp on a +/-0.15 printer', number='faces and seat meet together: loose at +0.15, open at -0.15', built='seat dia 52.15, each split face set back 0.4 mm')],
        seat_diameter_mm=model['changed']['SEAT_D'], split_gap_mm=dict(as_modelled=0.8, clamped_nominal=0.65, clamped_range=[0.2, 1.1]),
        fit_reasoning='seat 52.15 +/-0.15 is never under the 52.00 ring, so the ring always meets each seat at its crown, along the screws; '
                      'tightening closes 0.15 and leaves 0.8 - (0.15 +/-0.15) +/-0.30 = 0.2 to 1.1 mm at the split, so the screws always clamp the ring and never plastic on plastic; '
                      '0.1 mm axial clearance each side lets the halves close across the bearing',
        clearances_mm=fit['clearances_mm'],
        hand_screw_load_n=dict(plus_y=75.0, plus_x_tension=24.0, plus_x_shear=37.5,
                               note='+Y: 300 N / 4. +X: first hand value assumed a cosine pressure shared by both halves; the study shows the ring '
                                    'seated in the lower half at -30 to -1 degrees and wedged under the upper at about 77 degrees: statics with those angles gives 75.7 N tension and 17.5 N shear in total'),
        screw_load_n=dict(plus_y=[s['tension_N'] for s in pm['Y300']['screws']], plus_y_sum=pm['Y300']['screw_sum_N']['tension'],
                          plus_x_tension=[s['tension_N'] for s in pm['X300']['screws']], plus_x_shear=[s['shear_x_N'] for s in pm['X300']['screws']],
                          plus_x_sum=pm['X300']['screw_sum_N'], mesh='m'),
        nodes={t: posts[t]['Y300']['nodes'] for t in posts if posts[t] and 'Y300' in posts[t]},
        how_bodies_were_held='lower half: face Y -32 fixed. Upper half: bonded to the four steel screws (head on the counterbore floor), the screws bonded in the insert holes of the lower half. '
                             'Ring: a soft plug (0.2 MPa, 2 mm thick) bonded in its bore with the plug\'s dia 6 hub hole fixed; the plug carried '
                             f'{abs(pm["Y300"]["reaction_hub_N"][1]):.3f} N of 300 along Y and {abs(pm["X300"]["reaction_hub_N"][0]):.3f} N of 300 along X',
        contact_proof=dict(method='1 N in the working direction (the ring has clearance all round, so no reversal): it must cross the 0.075 mm clearance as a rigid body, out of proportion to the load',
                           ring_moves_mm_at_1N=dict(y=pm['Y1']['ring_moves_mm'][1], x=pm['X1']['ring_moves_mm'][0]),
                           ring_moves_mm_at_300N=dict(y=pm['Y300']['ring_moves_mm'][1], x=pm['X300']['ring_moves_mm'][0]),
                           bonded_would_move_at_1N_mm=dict(y=round(pm['Y300']['ring_moves_mm'][1] / 300, 5), x=round(pm['X300']['ring_moves_mm'][0] / 300, 5)),
                           force_through_the_contact_N=dict(plus_y_sum_of_screw_tension=pm['Y300']['screw_sum_N']['tension'], applied=300.0)),
        sf_yield=low['vm'][0], sf_layer=low['layer'][0], sf_shear=low['shear'][0],
        sf_where=dict(yield_=low['vm'][1:], layer=low['layer'][1:], shear=low['shear'][1:]),
        governing=f'{gov[0]} in the {gov[1][2]} half, case {gov[1][1]}: {gov[1][3]["mpa"]} MPa at {gov[1][3]["at"]}',
        convergence_layersZ_mpa=conv2,
        print_orientation=dict(upper='flat, face Z -4 on the bed, layers stacked along Z (the bearing axis)', lower='the same'),
        minutes=m2)
    extra = rd('d2_verdict.json')
    if extra:
        out['D2'].update(extra)

# ---- D3 ----------------------------------------------------------------------------------------------------------------
one, two = rd('d3_part_one.json'), rd('d3_part_two.json')
if one:
    keep = ('volume_mm3', 'hand_volume_mm3', 'diff_pct', 'mass_g', 'bodies', 'stl_watertight', 'min_wall_mm', 'min_wall_where', 'changed', 'why')
    out['D3'] = dict(plates={k: {q: v[q] for q in keep} | dict(as_built=v['built']) for k, v in one['plates'].items()},
                     table_problems=one['problems'], one_script=True, minutes=m3)
    if two:
        out['D3']['plates_b'] = {k + '_b': {q: v[q] for q in keep} | dict(counterbore_floor_z_mm=v['counterbore_floor_z_mm'], as_built=v['built'])
                                 for k, v in two['plates'].items()}
        out['D3']['table_problems'] = one['problems'] + two['problems']
        same = all(v['how']['same_features_same_ids_same_creation_time'] for v in two['plates'].values())
        out['D3']['edited_not_rebuilt'] = dict(value=bool(same),
                                               how_i_know='each P?_b was made by opening P?.SLDPRT, saving it under the new name and changing it in place: '
                                                          'the feature tree of every P?_b holds the same features with the same internal IDs and creation times as P?, plus one new chamfer; '
                                                          'the edit path of the script calls no new_part, extrude or cut',
                                               edits={k + '_b': v['how']['edits'] for k, v in two['plates'].items()})
    extra = rd('d3_extra.json')
    if extra:
        out['D3'].update(extra)
(HERE / 'results.json').write_text(json.dumps(out, indent=1))
print('wrote results.json', {k: (list(v) if isinstance(v, dict) else v) for k, v in out.items()})
