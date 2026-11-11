"""Masses, overall size against today, and the hub section cost of the dished top.

    python numbers_concept.py STUDY_WORK CONCEPT_OUT      -> CONCEPT_OUT/numbers.json

Size: bounding box of the shoulder (printed parts and the roll and yaw motors) in the torso frame; also without the pitch
flange ring (P1 inboard of X 104, which sits round the pitch motor) and with the fixed pitch loop cover. Hub: plane sections Y = const through the torque path (spigot to top); area and polar section
modulus about the yaw axis (J / r_max), today's hub against the dished one.
"""
import sys, os, json
import numpy as np, trimesh

W, C = sys.argv[1], sys.argv[2]
RX, RY, YZ = 170.49, 424.86, 5.99
ROLL_REAR = -25.96
info = json.load(open(os.path.join(C, 'parts.json')))
L = lambda p: trimesh.load(p)
today = {k: L(os.path.join(W, 'w', k + '.stl')) for k in ['P1', 'P2', 'SPACER', 'HUB', 'ROLL', 'YAW']}
NEW = ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished']
conc = {k: L(os.path.join(C, k + '.stl')) for k in NEW + ['BRG_6808', 'PITCH_cover']}
out = {}
TODAY_G = dict(P1=169.8, P2=178.3, spacer=24.9, hub=62.6)
out['mass_today_g'] = TODAY_G; out['mass_today_total'] = round(sum(TODAY_G.values()), 1)
out['mass_new_g'] = {k: info[k]['mass_petg_g'] for k in NEW}
out['mass_new_total'] = round(sum(out['mass_new_g'].values()), 1)
out['mass_pitch_cover_g'] = info['PITCH_cover']['mass_petg_g']


def bb(ms):
    return np.vstack([x.bounds for x in ms]).min(0), np.vstack([x.bounds for x in ms]).max(0)


def size(ms):
    lo, hi = bb(ms)
    return dict(X=[round(lo[0], 1), round(hi[0], 1)], width_X=round(hi[0] - lo[0], 1),
                Y=[round(lo[1], 1), round(hi[1], 1)], height_Y=round(hi[1] - lo[1], 1),
                Z=[round(lo[2], 1), round(hi[2], 1)], depth_Z=round(hi[2] - lo[2], 1),
                rear_reach_behind_roll_rear_face=round(ROLL_REAR - lo[2], 1))


out['size'] = dict(today=size([today[k] for k in ['P1', 'P2', 'SPACER', 'HUB', 'ROLL', 'YAW']]),
                   concept=size([conc[k] for k in NEW] + [today['ROLL'], today['YAW']]),
                   concept_body_outboard_of_X104=size([conc['P1_drum'].slice_plane([104, 0, 0], [1, 0, 0])] + [conc[k] for k in NEW[1:]]
                                                      + [today['ROLL'], today['YAW']]),
                   concept_with_pitch_cover=size([conc[k] for k in NEW + ['PITCH_cover']] + [today['ROLL'], today['YAW']]))


def sect_poly(mesh, y):
    s = mesh.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return None
    p2, T = s.to_planar(to_2D=np.array([[1, 0, 0, -RX], [0, 0, 1, -YZ], [0, 1, 0, -y], [0, 0, 0, 1]], float))
    from shapely.geometry.polygon import orient
    A = J = 0.0; rmax = 0.0
    for poly in p2.polygons_full:
        poly = orient(poly, 1.0)               # exterior counter-clockwise, holes clockwise: signed sums give the net section
        for ring in [poly.exterior] + list(poly.interiors):
            P = np.array(ring.coords); x0, y0 = P[:-1, 0], P[:-1, 1]; x1, y1 = P[1:, 0], P[1:, 1]
            cr = x0 * y1 - x1 * y0
            A += cr.sum() / 2
            J += (cr * (y0 ** 2 + y0 * y1 + y1 ** 2 + x0 ** 2 + x0 * x1 + x1 ** 2)).sum() / 12   # Ix + Iy about the yaw axis
        rmax = max(rmax, float(np.hypot(*np.array(poly.exterior.coords).T).max()))
    return dict(area=round(A, 0), J=round(J, 0), Zp=round(J / rmax, 0), rmax=round(rmax, 1), pieces=len(p2.polygons_full))


hub_old, hub_new = today['HUB'], conc['HUB_dished']
ys = np.round(np.arange(296.0, 319.6, 0.5), 2)
scan = {}
for nm, m in (('today', hub_old), ('dished', hub_new)):
    scan[nm] = {float(y): sect_poly(m, y) for y in ys}
weak = {}
for nm in scan:
    vals = {y: v for y, v in scan[nm].items() if v}
    ya = min(vals, key=lambda y: vals[y]['area']); yz = min(vals, key=lambda y: vals[y]['Zp'])
    weak[nm] = dict(min_area_at=ya, min_area=vals[ya], min_Zp_at=yz, min_Zp=vals[yz])
# the band the dish changes: Y 312.8-319.86 (today: plate Y 317-319.9)
band = {nm: {y: scan[nm][y] for y in (304.0, 308.0, 312.0, 313.0, 314.0, 315.0, 316.0, 317.0, 318.0, 319.0)} for nm in scan}
out['hub'] = dict(vol_old=round(hub_old.volume), vol_new=round(hub_new.volume), weakest=weak, band=band)
json.dump(out, open(os.path.join(C, 'numbers.json'), 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('mass_new_total', 'size')}, indent=1))
print(json.dumps(out['hub']['weakest'], indent=1))
for nm in band:
    print(nm, {y: (v['area'], v['Zp'], v['pieces']) if v else None for y, v in band[nm].items()})
