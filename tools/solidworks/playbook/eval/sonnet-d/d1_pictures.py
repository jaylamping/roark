"""D1: stand-ins for the rail and the board, the assembly STL, the crude STL of idea B, and the checks that need numpy
only: envelope, fit of the stand-in board, open area, tool-access clearance. Run after d1_build.py."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
import sheet  # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d1")
PIC = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d\pictures")
TH = 41.0
C, S = math.cos(math.radians(TH)), math.sin(math.radians(TH))
Y0, ZC = -0.5, 22.8
T = np.eye(4)
T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = (1, 0, 0), (0, C, S), (0, -S, C), (0, Y0, ZC)     # board frame -> model frame


def bbox_in_board(x0, x1, u0, u1, n0, n1):
    m = trimesh.creation.box(extents=(x1 - x0, u1 - u0, n1 - n0))
    m.apply_translation(((x0 + x1) / 2, (u0 + u1) / 2, (n0 + n1) / 2))
    m.apply_transform(T)
    return m


def cyl_in_board(x, u, n0, n1, r):
    m = trimesh.creation.cylinder(radius=r, height=n1 - n0, sections=24)    # axis along local z = n
    m.apply_translation((x, u, (n0 + n1) / 2))
    m.apply_transform(T)
    return m


def stand_ins():
    board = bbox_in_board(-42.5, 42.5, -30, 30, 0, 1.6)
    tall = bbox_in_board(-20, 20, -12, 12, 1.6, 15.6)
    term = bbox_in_board(38, 46, -10, 10, 1.6, 9.0)
    under = bbox_in_board(-33, 33, -22, 22, -3, 0)
    screws = [cyl_in_board(sx * 39, su * 26.5, 1.6, 3.25, 2.85) for sx in (1, -1) for su in (1, -1)]
    rail = trimesh.creation.box(extents=(140, 20, 20))
    rail.apply_translation((0, 0, -10))
    return board, tall, term, under, screws, rail


def write(mesh, path):
    mesh.export(path)
    return path


if __name__ == '__main__':
    mount = trimesh.load(OUT / 'buck_mount.stl')
    board, tall, term, under, screws, rail = stand_ins()
    asm = trimesh.util.concatenate([mount, board, tall, term, under, rail] + screws)
    write(asm, OUT / 'buck_mount_assembly.stl')
    print('assembly', asm.bounds.round(1).tolist())

    res = {}
    # envelope: mount and stand-ins together
    allm = trimesh.util.concatenate([mount, board, tall, term, under] + screws)
    res['envelope_box'] = allm.bounds.round(2).tolist()
    res['envelope_mount_only'] = mount.bounds.round(2).tolist()
    res['envelope_ok'] = bool(allm.bounds[1][1] <= 25 and allm.bounds[0][1] >= -25 and allm.bounds[1][2] <= 45)

    tris = sheet.read_stl(OUT / 'buck_mount.stl')
    # fit: points inside the board slab, the tall-part block, the underside slab, the screws must not be inside the mount
    rng = np.random.default_rng(1)

    def sample(x0, x1, u0, u1, n0, n1, k=6000):
        p = np.c_[rng.uniform(x0, x1, k), rng.uniform(u0, u1, k), rng.uniform(n0, n1, k)]
        h = np.c_[p, np.ones(k)] @ T.T
        return h[:, :3], p

    chk = {}
    for name, box in (('board slab', (-42.5, 42.5, -30, 30, 0.05, 1.55)), ('underside parts slab', (-33, 33, -22, 22, -2.95, -0.05)),
                      ('tall parts block', (-20, 20, -12, 12, 1.65, 15.55)), ('terminal block', (38, 46, -10, 10, 1.65, 9.0))):
        pts, loc = sample(*box)
        if name == 'board slab':     # ignore the four hole discs: the standoffs have a pilot there, the board a hole
            keep = np.ones(len(loc), bool)
            for sx in (1, -1):
                for su in (1, -1):
                    keep &= np.hypot(loc[:, 0] - sx * 39, loc[:, 1] - su * 26.5) > 1.7
            pts = pts[keep]
        hit = int(sheet.inside(tris, pts).sum())
        chk[name] = dict(points=len(pts), inside_mount=hit)
    res['fit_points'] = chk

    # underside clearance to the rib top line (smallest distance from the underside slab bottom to mount): sample
    pts, loc = sample(-33, 33, -22, 22, -3.0, -3.0, 4000)
    from scipy.spatial import cKDTree
    tree = cKDTree(mount.sample(60000))
    res['underside_to_mount_min_mm'] = round(float(tree.query(pts)[0].min()), 2)
    # underside parts at the rib X positions? ribs sit at X 35.5..42.5, parts assumed within X +-33: the gap in X
    res['underside_parts_to_rib_x_gap_mm'] = 35.5 - 33

    # open area: grid on the board; a cell is covered when the mount (or the screw head disc) lies within 6 mm along
    # the board normal on that face
    g = 1.0
    xs = np.arange(-42.5 + g / 2, 42.5, g)
    us = np.arange(-30 + g / 2, 30, g)
    X, U = np.meshgrid(xs, us)
    X, U = X.ravel(), U.ravel()
    area = 85 * 60
    cover = {}
    for face, n_list in (('bottom (n < 0)', [-0.3, -1, -2, -3, -4, -5, -6, -7]), ('top (n > 1.6)', [1.9, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])):
        hit = np.zeros(len(X), bool)
        for n in n_list:
            p = np.c_[X, U, np.full(len(X), n)]
            h = np.c_[p, np.ones(len(p))] @ T.T
            hit |= sheet.inside(tris, h[:, :3])
        if face.startswith('top'):    # plus the four screw heads, diameter 5.7
            for sx in (1, -1):
                for su in (1, -1):
                    hit |= np.hypot(X - sx * 39, U - su * 26.5) < 3.5
        cover[face] = round(float(1 - hit.mean()), 3)
    res['open_area_share_by_face'] = cover
    res['open_area_share'] = min(cover.values())
    (OUT / 'd1_checks.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

    # idea B: slide-in cradle, crude (boxes only): two grooved rails along X under the long edges, end stops, latch
    base = trimesh.creation.box(extents=(100, 20, 4)); base.apply_translation((0, 0, 2))
    rails = [bbox_in_board(-44, 44, su * 30 - (4 if su > 0 else 0) + (0 if su > 0 else -0), su * 30 + (0 if su > 0 else 0) + (4 if su > 0 else 0), -4, 4)
             for su in (-1, 1)]
    rails = [bbox_in_board(-44, 44, -36, -28, -4, 4), bbox_in_board(-44, 44, 28, 36, -4, 4)]
    posts = [trimesh.creation.box(extents=(8, 6, 26)) for _ in range(2)]
    posts[0].apply_translation((-38, -14, 13)); posts[1].apply_translation((38, 14, 13))
    stop = bbox_in_board(-46, -43, -28, 28, -4, 8)
    latch = bbox_in_board(43, 45, -8, 8, -4, 12)
    ideaB = trimesh.util.concatenate([base] + rails + posts + [stop, latch, board, tall, term, rail])
    write(ideaB, OUT / 'ideaB_slide_in_cradle.stl')
