"""D2 fit check and pictures: does the pair go together, what touches, what clears and by how much. Numpy only.

The clamped state is checked: the ring (dia 52.00) sits in the lower seat (dia 52.15), so its centre is 0.075 below
the housing axis, and the upper half comes down 0.15 until its seat crown meets the ring.
"""
import json

import numpy as np

from common import HERE, PICS, WIP, merge_stl
import sheet

model = json.loads((HERE / 'd2_model.json').read_text())
up, lo, ring = (sheet.read_stl(WIP / f'{n}.stl') for n in ('housing_upper', 'housing_lower', 'ring'))
SEAT_D, OPEN_D, GAP0 = 52.15, 49.0, 0.8
close_y = SEAT_D - 52.0                       # how far the upper half comes down from its modelled place: 0.15
up_c = up + np.array([0, -close_y, 0])
ring_c = ring + np.array([0, -close_y / 2, 0])
merge_stl(WIP / 'd2_pair.stl', up_c, lo, ring_c)
st = {}
for name, src in (('d2_housing_upper', 'housing_upper'), ('d2_housing_lower', 'housing_lower'), ('d2_pair', 'd2_pair')):
    st[name] = sheet.sheet([str(WIP / f'{src}.stl')], str(PICS / f'{name}.png'), px=360)
merge_stl(WIP / 'd2_pair_open.stl', up + np.array([0, 14.0, 0]), lo, ring_c)
sheet.sheet([str(WIP / 'd2_pair_open.stl')], str(PICS / 'd2_pair_open.png'), px=360)


def annulus(r0, r1, z0, z1, cy=0.0, n=6000, seed=2):
    rng = np.random.default_rng(seed)
    r, a = np.sqrt(r0 ** 2 + (r1 ** 2 - r0 ** 2) * rng.random(n)), 2 * np.pi * rng.random(n)
    return np.c_[r * np.cos(a), cy + r * np.sin(a), z0 + (z1 - z0) * rng.random(n)]


def ycyl(x, z, r, y0, y1, n=1500, seed=3):
    rng = np.random.default_rng(seed)
    rr, a = r * np.sqrt(rng.random(n)), 2 * np.pi * rng.random(n)
    return np.c_[x + rr * np.cos(a), y0 + (y1 - y0) * rng.random(n), z + rr * np.sin(a)]


def hit(pts):
    return round(float((sheet.inside(up_c, pts) | sheet.inside(lo, pts)).mean()), 4)


cy = -close_y / 2
SCREWS = [(sx * 31.0, z) for sx in (1, -1) for z in (0.0, 7.0)]
empty = {
    'outer ring itself (r 24 to 25.99, Z 0 to 7)': hit(annulus(24.0, 25.99, 0.0, 7.0, cy)),
    'turning inner ring and its sweep through both shoulders (r 20 to 22, Z -4 to 11)': hit(annulus(20.0, 22.0, -4.0, 11.0, cy)),
    'seals and balls (r 22 to 24, Z -4 to 11)': hit(annulus(22.0, 24.0, -4.0, 11.0, cy)),
    'shaft (r 0 to 20, Z -4 to 11)': hit(annulus(0.0, 20.0, -4.0, 11.0, cy)),
    'screw shanks dia 3.0 and thread ends, Y -6.5 to 28.35': max(hit(ycyl(x, z, 1.5, -6.5, 28.35)) for x, z in SCREWS),
    'screw heads dia 5.5 and the driver above them, Y 28.36 to 60': max(hit(ycyl(x, z, 2.75, 28.36, 60.0)) for x, z in SCREWS),
    'M4 screws from the mounting face, dia 4.0, Y -40 to -24': max(hit(ycyl(sx * 24.0, 3.5, 2.0, -40.0, -24.05)) for sx in (1, -1)),
    'split gap, Y -0.39 to 0.24, outside the bore': hit(np.c_[np.random.default_rng(4).uniform(26.2, 36, 4000) * np.random.default_rng(5).choice([-1, 1], 4000),
                                                             np.random.default_rng(6).uniform(-0.39, 0.24, 4000),
                                                             np.random.default_rng(7).uniform(-4, 11, 4000)]),
}
solid = {
    'shoulders over the outer ring face (r 24.6 to 25.9, Z -3.9 to -0.2 and 7.2 to 10.9)':
        min(hit(annulus(24.6, 25.9, -3.9, -0.2, 0.0)), hit(annulus(24.6, 25.9, 7.2, 10.9, 0.0))),
    'wall between seat and insert holes (x 27 to 28.5, y -8 to -1)': hit(np.c_[np.random.default_rng(8).uniform(27, 28.5, 2000) * np.random.default_rng(9).choice([-1, 1], 2000),
                                                                             np.random.default_rng(10).uniform(-8, -1, 2000),
                                                                             np.random.default_rng(11).uniform(-3.5, 10.5, 2000)]),
}
tol = 0.15
clear = {
    'seat_to_ring_radial_nominal': round((SEAT_D - 52.0) / 2, 3),
    'seat_to_ring_radial_range': [0.0, round((SEAT_D + tol - 52.0) / 2, 3)],
    'ring_to_each_shoulder_axial': 0.1,
    'shoulder_opening_to_inner_ring_radial': round(OPEN_D / 2 - 22.0, 3),
    'shoulder_opening_to_inner_ring_as_specified_dia_43.5': round(43.5 / 2 - 22.0, 3),
    'shoulder_land_on_outer_ring_face_radial': round(26.0 - OPEN_D / 2, 3),
    'shoulder_opening_outside_the_seal_radial': round(OPEN_D / 2 - 24.0, 3),
    'split_gap_as_modelled': GAP0,
    'split_gap_clamped_nominal': round(GAP0 - close_y, 3),
    'split_gap_clamped_range': [round(GAP0 - 2 * tol - 2 * tol, 3), round(GAP0 + 2 * tol, 3)],
    'screw_shank_in_clearance_hole_radial': 0.2,
    'screw_head_in_counterbore_radial': 0.25,
    'insert_hole_wall_to_seat': round(31.0 - 2.0 - SEAT_D / 2, 3),
    'insert_hole_wall_to_seat_as_specified_x_28.2': round(28.2 - 2.0 - 26.0, 3),
    'insert_hole_wall_to_outside_x': 3.0,
    'counterbore_to_counterbore': 1.0,
    'counterbore_to_counterbore_as_specified_z_1_and_6': -1.0,
    'counterbore_to_faces_z': 1.0,
    'counterbore_to_outside_x': 2.0,
    'M3x35_tip_above_hole_bottom': round(8.0 - (35.0 - (28.5 - close_y + GAP0 / 2)), 3),
    'M3x35_thread_in_insert_hole': round(35.0 - (28.5 - close_y + GAP0 / 2), 3),
    'M3x30_thread_in_insert_hole': round(30.0 - (28.5 - close_y + GAP0 / 2), 3),
    'M4_hole_bottom_to_seat': round(24.0 - np.sqrt(26.075 ** 2 - 21.2 ** 2), 3),
}
pts = annulus(24.0, 25.99, 0.0, 7.0, cy)
bad = pts[sheet.inside(up_c, pts) | sheet.inside(lo, pts)]
rr = np.hypot(bad[:, 0], bad[:, 1] - cy) if len(bad) else np.zeros(1)
ang = np.degrees(np.abs(np.arctan2(bad[:, 0], np.abs(bad[:, 1] - cy)))) if len(bad) else np.zeros(1)
ring_note = dict(points_flagged=len(bad), of=len(pts), smallest_radius_flagged_mm=round(float(rr.min()), 4),
                 largest_angle_from_a_crown_deg=round(float(ang.max()), 1),
                 why='the ring touches both seat crowns in the clamped state; the STL facets of a concave seat cut a few '
                     'hundredths of a millimetre inside the true cylinder there')
out = dict(ring_points_note=ring_note, must_be_empty_share_inside_housing=empty, must_be_solid_share_inside_housing=solid, clearances_mm=clear,
           clamped_state=dict(upper_half_moves_y=-close_y, ring_centre_y=cy), shape=st)
(HERE / 'd2_fit.json').write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ('must_be_empty_share_inside_housing', 'must_be_solid_share_inside_housing', 'clearances_mm')}, indent=1))
