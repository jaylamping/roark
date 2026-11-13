"""Join the per-task fragments into results.json, adding the verdicts and notes that were decided after reading the numbers."""
import json

from common import HERE


def load(n):
    return json.loads((HERE / f'{n}.json').read_text())


t1, t2, t3, t3b, t4, t5, t6p = (load(n) for n in ('T1', 'T2', 'T3', 'T3B', 'T4', 'T5', 'T6_post'))

# ---- T3 ----
b = t3b['rows'][-1]
t3['support_cross_check'] = t3b['rows']
t3['notes'] = (
    'Fixed: the four base hole walls. Load: 150 N +X as a rigid remote load on the bore at its centre. Peak von Mises is on the '
    'inside fillet (compression side); the layer stress is sz tension on the back face X 0 just above the base. Scored nodes: '
    'at least two global elements from the fixed hole walls and 1.5 mm from the bore wall; the playbook mask (two elements from '
    f'both) gives {t3["convergence_rows"][-1]["peak_vm_playbook_mask"]} and {t3["convergence_rows"][-1]["layer_playbook_mask"]} MPa. '
    f'Excluded: {t3["convergence_rows"][-1]["vm_max_unmasked"]} MPa at the edge of a fixed hole wall, rising with the mesh (a '
    'fixture singularity). Cross-check with the screws modelled as bonded steel washers fixed on top and the hole walls free '
    f'(t3b.py): fillet {b["fillet_peak_vm_mpa"]}, back-face layer stress {b["back_face_sz_mpa"]}, hole walls below the washers and '
    f'underside {b["low_peak_vm_mpa"]} MPa; bearing stress under the screw heads is not resolved by either model. '
    'Hand: root bending 11.0 MPa (FEA plain section at Z 12: 8.07 against 8.00 by hand), displacement 1.98 mm by hand against '
    f'{t3["max_disp_mm"]}. The finest mesh has 143,635 nodes, closer to the 150,000 ceiling than intended. Margin on the layers '
    'is 10 %. Interlayer shear (not in the requirement) is 7.2 MPa at the fillet against the playbook\'s 13 MPa: 1.8.')

# ---- T4 ----
rows = t4['convergence_rows']
r05 = t4['r05_rows'][-1]
layer = rows[-2]['layer_stress_mpa']          # back face, converged over the first three rows; the fourth row's is the corner itself
t4_out = dict(
    convergence_rows=[dict(el_mm=r['el_mm'], corner_edge_local_mm=r['corner_edge_local_mm'], nodes=r['nodes'],
                           corner_peak_vm_mpa=r['corner_peak_vm_mpa'], corner_peak_at_mm=r['corner_peak_at_mm'],
                           corner_peak_sz_mpa=r['corner_peak_sz_mpa'], corner_avg_vm_r05_r1_r2=r['corner_avg_vm'],
                           back_face_layer_stress_mpa=r['layer_stress_mpa'] if r['layer_at_mm'][0] < 0.01 else None,
                           max_disp_mm=r['max_disp_mm']) for r in rows],
    converged=False,
    reported_stress_mpa=r05['peak_vm_mpa'],
    section_stress_mpa=t4['hand_root_stress_mpa'],
    r05_stand_in_rows=t4['r05_rows'], r05_converged=t4['r05_converged'],
    back_face_layer_stress_mpa=layer, sf_layer=round(22.5 / layer, 2), sf_yield_at_corner=round(45 / r05['peak_vm_mpa'], 2),
    how_judged=(
        'The sharp corner has no stress to report: its peak rose 19.8, 26.5, 40.4, 54.7 MPa as the edge mesh halved '
        '(1.0 to 0.125 mm), a singularity, so it was judged three ways: the section carries 11.0 MPa by hand (node averages '
        'within 2 mm of the corner 9 to 16 MPa, compressive); the same part with a 0.5 mm radius, standing in for what a '
        f'printer leaves in a sharp corner, converges at {r05["peak_vm_mpa"]} MPa von Mises (compressive, {r05["peak_sz_mpa"]} MPa '
        f'across layers), a factor of {round(45 / r05["peak_vm_mpa"], 2)} on yield; and away from the corner the tension across '
        f'layers on the back face converges at {layer} MPa, a factor of {round(22.5 / layer, 2)}.'),
    verdict='fail', status='done',
    notes=('reported_stress_mpa is the converged peak of the 0.5 mm-radius stand-in (bracket_r05.SLDPRT), not a number from the '
           'sharp model; the true as-printed radius is not known, and a smaller one gives more. The fail does not rest on that '
           'alone: without the fillet the back-face layer tension is 11.46 MPa (10.2 with it), 1.96 against the 2.0 required, a '
           'converged number away from any corner, fixture or load. In the finest sharp row the largest sz tension moved to a node '
           '0.12 mm from the corner (13.2 MPa): part of the singular field, not used. Result.average() is a mean over nodes, so it '
           'rises as the mesh is refined toward the corner (9.0, 10.3, 12.0, 15.6 within 2 mm): it is not mesh-independent. '
           'Checks on every row: reaction -150 N in X exactly, plain section at Z 12 within 2 % of 8.00 MPa.'),
    seconds=t4['seconds'])

# ---- T5 ----
side = t5['orientation_options']['Y (on its side)']
t5.update(
    change=('None was required: the T3 bracket already meets the requirement as printed base-down (yield 2.85, layers 2.21). '
            'bracket_c is the T1 geometry unchanged, printed on its side (the Y 0 face on the bed, layers stacked along Y), which '
            'takes the bending out of the layer direction at no mass.'),
    sf_layer=side['sf_layer'], print_orientation='on its side: the Y 0 face on the bed, layers stacked along Y',
    notes=('Conditional task: T3 passed, so this is an optional margin improvement, not a fix. Shown with the T3 study itself '
           '(same geometry, same linear solve, T3_1.npz re-read for layers along Y): tension across layers 4.89 MPa (factor 4.6) '
           'instead of 10.2 (2.21), interlayer shear 4.67 MPa (2.78) instead of 7.24 (1.8, not part of the stated requirement), '
           'von Mises unchanged at 15.78 MPa (2.85). Base-down remains acceptable against the requirement as written. A print '
           'orientation is a design decision the playbook says to hand up: printability on the side (horizontal dia 5.5 and '
           'dia 3.4 holes, a 50 mm tall L section, the bore axis horizontal in both orientations) was not checked in a slicer.'))

# ---- T6 ----
runs = t6p['runs']
fin = runs[-1]
h = t6p['hand']
lift = t6p.get('lift', {})
valid = bool(abs(fin['reaction_n'][2] + 500) < 5 and abs(fin['pressure_integral_fz_n'] - 500) < 25
             and abs(fin['ligament_fz_n'] - 500) < 25 and fin.get('pad_share_pct', 99) < 1.0
             and lift.get('pin_rise_mm', 0) > 1e-3 and 0.1 < fin['pin_rise_mm'] < 0.2
             and (len(runs) < 2 or abs(runs[-1]['peak_contact_pressure_mpa'] - runs[-2]['peak_contact_pressure_mpa'])
                  <= 0.05 * runs[-2]['peak_contact_pressure_mpa']))
t6 = dict(
    hand_bearing_mpa=h['mean_projected_mpa'], hand_hertz_peak_pressure_mpa=h['hertz_peak_pressure_mpa'],
    hand_hertz_half_width_mm=h['hertz_half_width_mm'],
    nodes=fin['nodes'], solver='direct sparse (set 1 by macro, reads back 7 = Intel direct sparse)',
    how_pin_was_stabilised=('Real 0.1 mm radial gap modelled. Two soft pads (modulus 0.5 MPa, 3 x 2 mm section), one outside each '
                            'end of the hole and under the pin, each bonded to the block side face below the hole and to the '
                            'underside of the pin, with explicit bonded sets because the pin face is in the contact set.'),
    peak_contact_vm_mpa=fin['peak_contact_vm_mpa'], block_peak_at_mm=fin['block_peak_at_mm'],
    peak_contact_pressure_mpa=fin['peak_contact_pressure_mpa'], peak_pressure_at_mm=fin['peak_pressure_at_mm'],
    pin_rise_mm=fin['pin_rise_mm'], reaction_n=fin['reaction_n'], valid=valid,
    why=(f'Reaction {fin["reaction_n"][2]} N in Z for 500 N applied; the contact pressure integrated over the hole wall gives '
         f'{fin["pressure_integral_fz_n"]} N and the tension in the two ligaments beside the hole {fin["ligament_fz_n"]} N; the pin '
         f'rises {fin["pin_rise_mm"]} mm (0.1 mm gap, then deformation); the pads carry {fin.get("pad_share_pct")} % of the load '
         f'(stiffness {lift.get("pad_stiffness_n_per_mm")} N/mm from the lift run); with {lift.get("total_n")} N the pin floats '
         f'{lift.get("pin_rise_mm")} mm on the pads with the gap still open, so the set is contact, not a bond; the hole wall away '
         f'from the contact is stress-free to {fin["free_wall_radial_stress_abs_max_mpa"]} MPa; peak pressure {fin["peak_contact_pressure_mpa"]} '
         f'MPa against {h["hertz_peak_pressure_mpa"]} by Hertz line contact (peaks on the three meshes '
         f'{[r["peak_contact_pressure_mpa"] for r in runs]}), and it moved '
         + (f'{round(100 * abs(runs[-1]["peak_contact_pressure_mpa"] / runs[-2]["peak_contact_pressure_mpa"] - 1), 1)} % between the '
            f'last two meshes.' if len(runs) > 1 else 'on one mesh only.')),
    runs=runs, lift=lift, hand=h, status='done',
    notes=('The bearing stress asked for is the contact pressure (radial stress on the hole wall): peak_contact_pressure_mpa. '
           'peak_contact_vm_mpa is the largest von Mises in the block (bottom 6 mm above the fixture and the pad footprints '
           'left out), which sits just under the contact. hand_bearing_mpa is F / (d L), the mean over the projected area; the '
           'peak is compared with Hertz. Bodies split by geometry from undeformed coordinates, no node in two bodies. '
           'Known artefact of the stabilising pads: each pad bridges the 0.1 mm gap at the bottom end of the hole, and where its '
           'bond meets the hole edge the block shows a local spike: '
           f'{[r["pad_attachment_artefact"]["vm_mpa"] for r in runs]} MPa von Mises on the three meshes, the last at one node at '
           f'{fin["pad_attachment_artefact"]["at_mm"]} whose displacement is five times its neighbours, at one of the four pad '
           'corners only (the other three read 3 to 6 MPa). The pads carry 2.4 N in all, so this is a bond-constraint artefact, '
           'not load; I did not chase its cause further. It is at the unloaded side of the hole, 10 mm from the bearing zone, '
           'and is left out of both peaks; a pad bonded to the block clear of the hole edge would avoid it. '
           'The first try at a finer mesh (0.5 on the hole, '
           '0.625 on the pin) meshed 227,182 nodes and was stopped before solving by the 150,000 ceiling of this run.'))

res = dict(run='fable-playbook', T1=t1, T2=t2, T3=t3, T4=t4_out, T5=t5, T6=t6,
           T7=dict(status='done', notes='answers in REPORT.md'))
(HERE / 'results.json').write_text(json.dumps(res, indent=2))
print(json.dumps({k: (v.get('status'), v.get('verdict'), v.get('valid')) for k, v in res.items() if isinstance(v, dict)}))
