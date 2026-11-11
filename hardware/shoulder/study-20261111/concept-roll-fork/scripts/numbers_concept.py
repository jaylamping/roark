"""Masses, overall size against today, and the hub section cost of the dished top.

    python numbers_concept.py STUDY_WORK CONCEPT_OUT      -> CONCEPT_OUT/numbers.json
"""
import sys, os, json
import numpy as np, trimesh

W, C = sys.argv[1], sys.argv[2]
RX, RY, YZ = 170.49, 424.86, 5.99
info = json.load(open(os.path.join(C, 'parts.json')))
L = lambda p: trimesh.load(p)
today = {k: L(os.path.join(W, 'w', k + '.stl')) for k in ['P1', 'P2', 'SPACER', 'HUB', 'ROLL', 'YAW']}
conc = {k: L(os.path.join(C, k + '.stl')) for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'BRG_6808', 'PITCH_cover']}
out = {}

TODAY_G = dict(P1=169.8, P2=178.3, spacer=24.9, hub=62.6)
new = {k: info[k]['mass_petg_g'] for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished']}
out['mass_today_g'] = TODAY_G; out['mass_today_total'] = round(sum(TODAY_G.values()), 1)
out['mass_new_g'] = new; out['mass_new_total'] = round(sum(new.values()), 1)
out['mass_pitch_cover_g'] = info['PITCH_cover']['mass_petg_g']
# P1 breakdown: pitch-side features (X < 106) against drum side
m = conc['P1_drum']; pts = trimesh.sample.volume_mesh(m, 400000) if False else None
p = np.random.default_rng(0).uniform(m.bounds[0], m.bounds[1], (600000, 3)); ins = m.contains(p)
vbox = np.prod(m.bounds[1] - m.bounds[0]); q = p[ins]
reg = {'pitch flange, skirt and pad (X < 106)': q[:, 0] < 106,
       'ducts outside the drum (r > 57.5 from the roll axis, X > 106)': (q[:, 0] >= 106) & (np.hypot(q[:, 0] - RX, q[:, 1] - RY) > 57.5),
       'front lip (Z > 28.3)': (q[:, 0] >= 106) & (np.hypot(q[:, 0] - RX, q[:, 1] - RY) <= 57.5) & (q[:, 2] > 28.3)}
rest = np.ones(len(q), bool)
for k, s in reg.items(): rest &= ~s
reg['drum wall, ribs, ears, neck'] = rest
out['P1_breakdown_g'] = {k: round(s.sum() / len(p) * vbox * 1.27e-3, 1) for k, s in reg.items()}


def bb(ms):
    return np.vstack([x.bounds for x in ms]).min(0), np.vstack([x.bounds for x in ms]).max(0)


lo_t, hi_t = bb([today[k] for k in ['P1', 'P2', 'SPACER', 'HUB', 'ROLL', 'YAW']])
lo_c, hi_c = bb([conc[k] for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished']] + [today['ROLL'], today['YAW']])
# the shoulder body without the pitch-loop flange/skirt (which sits round the pitch motor, inboard of X 106)
cut = conc['P1_drum'].slice_plane([106, 0, 0], [1, 0, 0])
lo_b, hi_b = bb([cut] + [conc[k] for k in ['P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished']] + [today['ROLL'], today['YAW']])
out['size'] = dict(
    today=dict(Z=[round(lo_t[2], 1), round(hi_t[2], 1)], depth=round(hi_t[2] - lo_t[2], 1), behind_roll_rear=round(-25.96 - lo_t[2], 1),
               X=[round(lo_t[0], 1), round(hi_t[0], 1)], width=round(hi_t[0] - lo_t[0], 1), Y=[round(lo_t[1], 1), round(hi_t[1], 1)]),
    concept_body=dict(Z=[round(lo_b[2], 1), round(hi_b[2], 1)], depth=round(hi_b[2] - lo_b[2], 1), behind_roll_rear=round(-25.96 - lo_b[2], 1),
                      X=[round(lo_b[0], 1), round(hi_b[0], 1)], width=round(hi_b[0] - lo_b[0], 1), Y=[round(lo_b[1], 1), round(hi_b[1], 1)]),
    concept_with_pitch_ring=dict(Z=[round(lo_c[2], 1), round(hi_c[2], 1)], X=[round(lo_c[0], 1), round(hi_c[0], 1)], Y=[round(lo_c[1], 1), round(hi_c[1], 1)]))


# hub: material crossing cylinders about the yaw axis (torque path from the RS02 clamp disc out to the wall)
def cyl_area(mesh, r, y0, y1, n_th=1440, dy=0.2):
    th = np.linspace(0, 2 * np.pi, n_th, endpoint=False); ys = np.arange(y0, y1, dy)
    T, Yg = np.meshgrid(th, ys); P = np.c_[RX + r * np.cos(T.ravel()), Yg.ravel(), YZ + r * np.sin(T.ravel())]
    f = mesh.contains(P).mean(); return round(f * 2 * np.pi * r * (y1 - y0), 0)


def plane_area(mesh, y):
    s = mesh.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None: return 0
    p2, _ = s.to_planar(); return round(p2.area, 0)


hub_old, hub_new = today['HUB'], conc['HUB_dished']
out['hub'] = dict(
    vol_old=round(hub_old.volume), vol_new=round(hub_new.volume),
    cyl_r22=[cyl_area(hub_old, 22.0, 296, 320), cyl_area(hub_new, 22.0, 296, 320)],
    cyl_r27=[cyl_area(hub_old, 27.0, 296, 320), cyl_area(hub_new, 27.0, 296, 320)],
    cyl_r33=[cyl_area(hub_old, 33.0, 296, 320), cyl_area(hub_new, 33.0, 296, 320)],
    plane={y: [plane_area(hub_old, y), plane_area(hub_new, y)] for y in (304.0, 310.0, 314.0, 318.5)})
json.dump(out, open(os.path.join(C, 'numbers.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
