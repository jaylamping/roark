"""D1 after the SolidWorks job: stand-ins, picture sheets, clearance and open-area checks, and the 9 N case in ANY direction.

Numpy only (run under tools/pc/capped.py). Reads the STLs and the nodal results d1_build.py left in cad/_wip.
"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from common import HERE, PICS, WIP, box_tris, merge_stl, write_stl
import sheet

BOARD_Z, BT = 8.0, 1.6
HOLES = [(sx * 39.0, sy * 26.5) for sx in (1, -1) for sy in (1, -1)]
out = {}

# ---- stand-ins ---------------------------------------------------------------------------------------------------------
board = [box_tris((-42.5, -30, BOARD_Z), (42.5, 30, BOARD_Z + BT)),
         box_tris((-25, -12, BOARD_Z + BT), (-3, 10, BOARD_Z + BT + 14)),        # inductor, the 14 mm part
         box_tris((2, -20, BOARD_Z + BT), (14, -8, BOARD_Z + BT + 12)),          # capacitor
         box_tris((2, 6, BOARD_Z + BT), (14, 18, BOARD_Z + BT + 12)),
         box_tris((30, -24, BOARD_Z + BT), (41.5, -6, BOARD_Z + BT + 10)),       # the two wire terminals on the +X edge
         box_tris((30, 6, BOARD_Z + BT), (41.5, 24, BOARD_Z + BT + 10)),
         box_tris((-30, -22, BOARD_Z - 3), (20, 20, BOARD_Z))]                   # solder side, the 3 mm keep-out
board = np.concatenate(board)
rail = np.concatenate([box_tris((-75, -10, -20), (75, 10, -6)), box_tris((-75, -10, -6), (75, -3, 0)),
                       box_tris((-75, 3, -6), (75, 10, 0))])
write_stl(WIP / 'board_standin.stl', board)
write_stl(WIP / 'rail_standin.stl', rail)
merge_stl(WIP / 'd1_assembly.stl', WIP / 'buck_mount.stl', board, rail)
merge_stl(WIP / 'd1_board_out.stl', WIP / 'buck_mount.stl', board + np.array([0, 0, 25.0]), rail)
merge_stl(WIP / 'd1_mount_on_rail.stl', WIP / 'buck_mount.stl', rail)
merge_stl(WIP / 'd1_idea_b.stl', WIP / 'idea_b_snap.stl', board, rail)
for name, src in (('d1_buck_mount', 'buck_mount'), ('d1_assembly_idea_a', 'd1_assembly'), ('d1_board_out', 'd1_board_out'),
                  ('d1_mount_on_rail', 'd1_mount_on_rail'), ('d1_idea_b_snap', 'd1_idea_b')):
    st = sheet.sheet([str(WIP / f'{src}.stl')], str(PICS / f'{name}.png'), px=360)
    if name == 'd1_buck_mount':
        out['shape'] = st

# ---- clearance: is the space the board, its parts, the rail and the tools need really empty? ---------------------------
mount = sheet.read_stl(WIP / 'buck_mount.stl')


def grid(lo, hi, step):
    ax = [np.arange(lo[k] + step / 2, hi[k], step) for k in range(3)]
    return np.stack(np.meshgrid(*ax, indexing='ij'), -1).reshape(-1, 3)


def share_inside(pts):
    return float(sheet.inside(mount, pts).mean()), len(pts)


def cyl_pts(c, r, z0, z1, n=400, seed=1):
    rng = np.random.default_rng(seed)
    rr, a = r * np.sqrt(rng.random(n)), 2 * np.pi * rng.random(n)
    return np.c_[c[0] + rr * np.cos(a), c[1] + rr * np.sin(a), z0 + (z1 - z0) * rng.random(n)]


clear = {}
clear['board_and_14mm_above'] = share_inside(grid((-42.5, -30, BOARD_Z + 0.01), (42.5, 30, BOARD_Z + BT + 14), 1.5))
low = grid((-42.5, -30, BOARD_Z - 3), (42.5, 30, BOARD_Z - 0.01), 1.0)
land = np.min([np.hypot(low[:, 0] - x, low[:, 1] - y) for x, y in HOLES], axis=0) <= 3.5
clear['3mm_below_outside_dia7_lands'] = share_inside(low[~land])
clear['rail_volume'] = share_inside(grid((-58.5, -10, -20), (58.5, 10, -0.01), 2.0))
clear['slot_for_T_nuts'] = share_inside(grid((-58.5, -3, -6), (58.5, 3, -0.01), 1.0))
clear['M3_tool_path_dia6_to_Z45'] = max(share_inside(cyl_pts(c, 3.0, BOARD_Z + 0.01, 45))[0] for c in HOLES)
clear['M3_insert_holes_dia3.8'] = max(share_inside(cyl_pts(c, 1.9, 2.1, 7.99))[0] for c in HOLES)
clear['M5_tool_path_dia9.5_to_Z45'] = max(share_inside(cyl_pts((sx * 50.5, 0), 4.75, 3.51, 45))[0] for sx in (1, -1))
clear['M5_holes_dia5.3'] = max(share_inside(cyl_pts((sx * 50.5, 0), 2.65, 0.01, 3.49))[0] for sx in (1, -1))
solid = {}
ring = np.array([[x + 2.75 * np.cos(a), y + 2.75 * np.sin(a), z] for x, y in HOLES for a in np.linspace(0, 6.28, 24, endpoint=False)
                 for z in (4.5, 6.0, 7.9)])
solid['post_walls_r2.75'] = share_inside(ring)
solid['under_M5_head_r4'] = share_inside(np.array([[sx * 50.5 + 4 * np.cos(a), 4 * np.sin(a), z] for sx in (1, -1)
                                                   for a in np.linspace(0, 6.28, 24, endpoint=False) for z in (0.5, 3.4)]))
out['must_be_empty_share_inside_mount'] = {k: (v if isinstance(v, float) else list(v)) for k, v in clear.items()}
out['must_be_solid_share_inside_mount'] = {k: list(v) for k, v in solid.items()}
# the M5 head against the board edge and the M3 heads against the envelope
out['m5_head_edge_to_board_edge_mm'] = round(50.5 - 4.75 - 42.5, 2)
pts = mount.reshape(-1, 3)
out['mount_extent'] = dict(lo=pts.min(0).round(3).tolist(), hi=pts.max(0).round(3).tolist())
out['envelope'] = dict(limit='Y -25 to 25, Z up to 45', mount_y=[float(pts[:, 1].min()), float(pts[:, 1].max())],
                       board_y=[-30.0, 30.0], top_of_board_parts_z=BOARD_Z + BT + 14, mount_top_z=float(pts[:, 2].max()),
                       over_y_each_side_mm=5.0, z_ok=True, ok=False)

# ---- open area: how much of each board face is not covered, in plan, by the mount -------------------------------------
g = np.stack(np.meshgrid(np.arange(-42.5 + 0.125, 42.5, 0.25), np.arange(-30 + 0.125, 30, 0.25), indexing='ij'), -1).reshape(-1, 2)
under = np.zeros(len(g), bool)
for z in (2.0, 6.0):                      # the base (Z 0 to 4) and the posts (Z 4 to 8): everything under the board
    under |= sheet.inside(mount, np.c_[g, np.full(len(g), z)])
heads = np.min([np.hypot(g[:, 0] - x, g[:, 1] - y) for x, y in HOLES], axis=0) <= 2.75      # M3 cap heads, dia 5.5
railshadow = np.abs(g[:, 1]) <= 10
out['open_area'] = dict(bottom_face_open=round(1 - float(under.mean()), 3), top_face_open=round(1 - float(heads.mean()), 3),
                        bottom_open_counting_the_rail_8mm_below=round(1 - float((under | railshadow).mean()), 3),
                        hand_bottom=round(1 - (85 * 12 + 4 * (7 * 20.5 + np.pi * 3.5 ** 2 / 2)) / (85 * 60), 3))

# ---- the studies -------------------------------------------------------------------------------------------------------
A = np.zeros((6, 6))
A[:3, :3] = [[1, -.5, -.5], [-.5, 1, -.5], [-.5, -.5, 1]]
A[3:, 3:] = 3 * np.eye(3)
ALLOW = dict(vm=45.0, layer=22.5, shear=13.0)


def load(name):
    z = np.load(WIP / f'd1_{name}.npz', allow_pickle=True)
    return {k: z[k] for k in z.files}


def away(c, dist):
    keep = np.ones(len(c['pos']), bool)
    for k in ('fixed', 'loaded'):
        if c[k].dtype != object:
            keep &= cKDTree(c[k]).query(c['pos'])[0] >= dist
    return keep


def measures(S, n, mask, pos):
    """von Mises, tension across layers stacked along n, shear between them: (value, where) each, over mask."""
    n = np.array(n, float)
    vm = np.sqrt(np.einsum('ni,ij,nj->n', S, A, S))
    sn = n[0] ** 2 * S[:, 0] + n[1] ** 2 * S[:, 1] + n[2] ** 2 * S[:, 2] + 2 * (n[0] * n[1] * S[:, 3] + n[0] * n[2] * S[:, 4] + n[1] * n[2] * S[:, 5])
    t = np.c_[S[:, 0] * n[0] + S[:, 3] * n[1] + S[:, 4] * n[2], S[:, 3] * n[0] + S[:, 1] * n[1] + S[:, 5] * n[2],
              S[:, 4] * n[0] + S[:, 5] * n[1] + S[:, 2] * n[2]]
    tau = np.linalg.norm(t - np.outer(t @ n, n), axis=1)
    res = {}
    for key, v in (('vm', vm), ('layer', sn), ('shear', tau)):
        i = np.flatnonzero(mask)[np.argmax(v[mask])]
        res[key] = dict(mpa=round(float(v[i]), 3), at=pos[i].round(2).tolist(), sf=round(ALLOW[key] / max(float(v[i]), 1e-9), 1))
    return res


cases = {k: load(k) for k in ('Z_remote', 'X_remote', 'Y_remote', 'Z_even')}
dist = 2 * 1.2
st = {}
for k, c in cases.items():
    m = away(c, dist)
    S = c['s'][:, 1:7]
    row = dict(nodes=len(c['pos']), reaction=c['reaction'].round(3).tolist(), max_disp_mm=round(float(np.abs(c['disp'][:, 4]).max()), 4),
               peak_vm_all_nodes=round(float(c['s'][:, 10].max()), 3), excluded_within_mm=dist)
    for label, n in (('layers_Z', (0, 0, 1)), ('layers_X', (1, 0, 0)), ('layers_Y', (0, 1, 0))):
        row[label] = measures(S, n, m, c['pos'])
    # the plain section: an arm half way between spine and post, top surface (hand: M c / I with M = 2.25 N x distance to the post)
    mid = [i for i in cKDTree(c['pos']).query_ball_point((39.0, 16.25, 4.0), 1.5)]
    row['arm_mid_top_sy_mpa'] = [round(float(c['s'][mid, 2].mean()), 3), len(mid)]
    st[k] = row
same = all(cases[k]['pos'].shape == cases['Z_remote']['pos'].shape and np.allclose(cases[k]['pos'], cases['Z_remote']['pos'])
           for k in ('X_remote', 'Y_remote'))
out['studies'] = st
out['hand'] = dict(arm_mid_top_sy_mpa=round(2.25 * 10.25 * 2 / (7 * 4 ** 3 / 12), 3), arm_root_mpa=round(2.25 * 20.5 * 2 / (7 * 4 ** 3 / 12), 3),
                   note='arm as a cantilever from the spine edge (Y 6) to the post centre (Y 26.5), 7 x 4 section, 9 N / 4 per post')
if same:
    # 9 N in ANY direction n: the stress is nx Sx + ny Sy + nz Sz. Each measure is maximised over n per node:
    # von Mises^2 = n' Q n with Q[k][l] = Sk' A Sl, so the worst is sqrt(largest eigenvalue); likewise for the shear;
    # tension across layers is linear in n, so the worst is the length of the vector of the three cases.
    U = np.stack([cases['X_remote']['s'][:, 1:7], cases['Y_remote']['s'][:, 1:7], -cases['Z_remote']['s'][:, 1:7]], 1)   # (n, 3, 6)
    m = away(cases['Z_remote'], dist)
    pos = cases['Z_remote']['pos']
    Q = np.einsum('nki,ij,nlj->nkl', U, A, U)
    vm = np.sqrt(np.linalg.eigvalsh(Q)[:, -1])
    anyd = {}
    for label, ln in (('layers_Z', 2), ('layers_X', 0), ('layers_Y', 1)):
        col = {0: 0, 1: 1, 2: 2}[ln]
        sn = np.linalg.norm(U[:, :, col], axis=1)
        sh = {2: (4, 5), 0: (3, 4), 1: (3, 5)}[ln]            # the two shear components on the layer plane
        B = U[:, :, list(sh)]                                    # (n, 3, 2)
        tau = np.sqrt(np.linalg.eigvalsh(np.einsum('nki,nli->nkl', B, B))[:, -1])
        res = {}
        for key, v in (('vm', vm), ('layer', sn), ('shear', tau)):
            i = np.flatnonzero(m)[np.argmax(v[m])]
            res[key] = dict(mpa=round(float(v[i]), 3), at=pos[i].round(2).tolist(), sf=round(ALLOW[key] / float(v[i]), 1))
        anyd[label] = res
    i = np.flatnonzero(m)[np.argmax(vm[m])]
    w, vec = np.linalg.eigh(Q[i])
    anyd['worst_direction_for_vm'] = (vec[:, -1] * np.sign(vec[2, -1] or 1)).round(3).tolist()
    out['any_direction_9N'] = anyd
else:
    out['any_direction_9N'] = 'NOT COMBINED: the three meshes differ'
(HERE / 'd1_post.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
