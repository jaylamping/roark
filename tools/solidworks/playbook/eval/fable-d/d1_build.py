"""D1: buck board mount on the top front rail. One job: chosen design (idea A), crude idea B, exports, four studies.

    python d1_build.py            # everything
    python d1_build.py nostudy    # models and exports only

Frame: X along the rail, Y across (front -Y), Z up, rail top face at Z 0, rail centred on Y 0. mm.
"""
import json
import math
import sys
import time

import numpy as np

from common import HERE, WIP, stl_check
from swfea import PETG, static
from swkit import (MID, Sk, bbox, bodies, close, edges_where, expect, export, extrude, face_info, feature_errors, fillet, job,
                   log, new_part, open_doc, pick, plane, save, single_body, volume)

# ---- the numbers that define the part, with their source ---------------------------------------------------------------
BOARD_L, BOARD_W, BOARD_T = 85.0, 60.0, 1.6     # task
HOLE_IN = 3.5                                   # task: hole centres this far in from each edge
BELOW, ABOVE = 3.0, 14.0                        # task: keep-outs under and over the board
RAIL_W = 20.0                                   # task
BOARD_Y0 = 0.0                                  # my choice: board centred on the rail (restate.md, question 1)
T = 4.0                                         # base thickness: M5 clamp length and arm depth
BOARD_Z = 8.0                                   # underside of the board: T + BELOW + 1 mm spare
SPINE_HW = 6.0                                  # half width of the spine along the rail (open area under the board)
ARM_W = 7.0                                     # arm width = post diameter: dia 4.0 insert hole + 1.5 mm wall
INS_D, INS_DEPTH = 4.0, 6.0                     # M3 heat-set insert hole (same as the D2 housing)
M5_D, SPOT_D, SPOT_DEPTH = 5.5, 10.5, 0.5       # M5 clearance; shallow spot face for the head or washer
TAB_L = 16.0                                    # tab beyond each end of the board for the M5 screw
ROOT_R = 2.0                                    # round in the corners where arms and tabs meet the spine

HX, HY = BOARD_L / 2 - HOLE_IN, BOARD_W / 2 - HOLE_IN       # 39.0, 26.5
XE = BOARD_L / 2                                              # 42.5: end of the spine, start of the tab
M5_X = XE + TAB_L / 2                                         # 50.5
POSTS = [(sx * HX, BOARD_Y0 + sy * HY) for sx in (1, -1) for sy in (1, -1)]

HAND = dict(
    spine=2 * XE * 2 * SPINE_HW * T,
    tabs=2 * TAB_L * RAIL_W * T,
    arms=sum(ARM_W * (abs(py) - SPINE_HW) * T for _, py in POSTS),
    posts=4 * (math.pi * (ARM_W / 2) ** 2 * BOARD_Z - math.pi * (ARM_W / 2) ** 2 / 2 * T),
    inserts=-4 * math.pi * (INS_D / 2) ** 2 * INS_DEPTH,
    m5=-2 * math.pi * (M5_D / 2) ** 2 * T,
    spot=-2 * math.pi * ((SPOT_D / 2) ** 2 - (M5_D / 2) ** 2) * SPOT_DEPTH,
    rounds=8 * ROOT_R ** 2 * (1 - math.pi / 4) * T)
HAND_V = sum(HAND.values())


def box(d, name, lo, hi, cut=False):
    zc = (lo[2] + hi[2]) / 2
    with Sk(d, plane(d, 'Z', zc, name + '_P'), name) as s:
        s.rect((lo[0], lo[1], zc), (hi[0], hi[1], zc))
    return extrude(d, s.feat, name, hi[2] - lo[2], cut=cut, mode=MID,
                   expect_dv=(hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]))


def cyls(d, name, centres, r, z0, z1, cut=False, expect_dv=None):
    zc = (z0 + z1) / 2
    with Sk(d, plane(d, 'Z', zc, name + '_P'), name) as s:
        for c in centres:
            s.circle((c[0], c[1], zc), r)
    return extrude(d, s.feat, name, z1 - z0, cut=cut, mode=MID, expect_dv=expect_dv)


def base(d):
    """Spine on the rail, a tab at each end, four arms out to the board holes. Shared by both ideas."""
    box(d, 'SPINE', (-XE, -SPINE_HW, 0), (XE, SPINE_HW, T))
    box(d, 'TAB_PX', (XE, -RAIL_W / 2, 0), (XE + TAB_L, RAIL_W / 2, T))
    box(d, 'TAB_NX', (-XE - TAB_L, -RAIL_W / 2, 0), (-XE, RAIL_W / 2, T))
    for k, (px, py) in enumerate(POSTS):
        y0, y1 = sorted((math.copysign(SPINE_HW, py), py))
        box(d, f'ARM{k}', (px - ARM_W / 2, y0, 0), (px + ARM_W / 2, y1, T))
    save(d)


def build_a(j):
    path = WIP / 'buck_mount.SLDPRT'
    d = new_part(j.sw, path)
    base(d)
    cyls(d, 'POSTS', POSTS, ARM_W / 2, 0, BOARD_Z, expect_dv=HAND['posts'])
    cyls(d, 'INSERT_HOLES', POSTS, INS_D / 2, BOARD_Z - INS_DEPTH, BOARD_Z, cut=True, expect_dv=-HAND['inserts'])
    cyls(d, 'M5_HOLES', [(M5_X, 0), (-M5_X, 0)], M5_D / 2, 0, T, cut=True, expect_dv=-HAND['m5'])
    with Sk(d, plane(d, 'Z', T - SPOT_DEPTH / 2, 'SPOT_P'), 'SPOT') as s:
        for sx in (1, -1):
            s.circle((sx * M5_X, 0, T - SPOT_DEPTH / 2), SPOT_D / 2)
    extrude(d, s.feat, 'SPOT', SPOT_DEPTH, cut=True, mode=MID, expect_dv=-HAND['spot'])
    save(d)

    def root(p):      # the eight upright inside corners: arm against spine, arm against tab
        ax, ay = abs(p[0]), abs(p[1])
        return ((abs(ax - (HX - ARM_W / 2)) < 0.01 and abs(ay - SPINE_HW) < 0.01)
                or (abs(ax - XE) < 0.01 and abs(ay - RAIL_W / 2) < 0.01))
    edges = edges_where(d, root)
    expect('root edges found', len(edges), 8, 0)
    v0 = volume(d)
    got = fillet(d, edges, (ROOT_R,), 'ROOT_ROUNDS')
    if got is None:
        raise SystemExit('root rounds did not build')
    expect('root rounds volume change', volume(d) - v0, HAND['rounds'], 0.02)
    single_body(d)
    save(d)

    # ---- the model is done when: volume, box, bodies, rebuild, and every dimension measured on the solid ----
    expect('mount volume', volume(d), HAND_V, 0.002)
    want_box = [-XE - TAB_L, BOARD_Y0 - HY - ARM_W / 2, 0, XE + TAB_L, BOARD_Y0 + HY + ARM_W / 2, BOARD_Z]
    for k, w in enumerate(want_box):
        expect(f'box[{k}]', bbox(d)[k], w, 0.01)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    meas = {}
    ins = [face_info(f) for f in pick(d, kind='cyl', r=INS_D / 2, inside=[-60, -40, BOARD_Z - INS_DEPTH - 0.1, 60, 40, BOARD_Z + 0.1])]
    expect('insert hole faces', len(ins), 4, 0)
    meas['insert_holes'] = sorted([[round((i['box'][0] + i['box'][3]) / 2, 3), round((i['box'][1] + i['box'][4]) / 2, 3),
                                    round(i['r'] * 2, 3), round(i['box'][2], 3), round(i['box'][5], 3)] for i in ins])
    for c in meas['insert_holes']:
        if min(math.dist(c[:2], p) for p in POSTS) > 0.01 or abs(c[3] - (BOARD_Z - INS_DEPTH)) > 0.01 or abs(c[4] - BOARD_Z) > 0.01:
            raise SystemExit(f'insert hole in the wrong place: {c}')
    m5 = [face_info(f) for f in pick(d, kind='cyl', r=M5_D / 2)]
    expect('M5 hole faces', len(m5), 2, 0)
    meas['m5_holes'] = sorted([[round((i['box'][0] + i['box'][3]) / 2, 3), round((i['box'][1] + i['box'][4]) / 2, 3),
                                round(i['r'] * 2, 3), round(i['box'][2], 3), round(i['box'][5], 3)] for i in m5])
    for c in meas['m5_holes']:
        if abs(abs(c[0]) - M5_X) > 0.01 or abs(c[1]) > 0.01:
            raise SystemExit(f'M5 hole in the wrong place: {c}')
    tops = [face_info(f) for px, py in POSTS for f in pick(d, kind='plane', at=(px + 2.75, py, BOARD_Z))]
    expect('post top faces', len(tops), 4, 0)
    meas['post_top_z'] = [round(i['box'][5], 3) for i in tops]
    meas['post_od'] = sorted(round(i['r'] * 2, 3) for i in (face_info(f) for f in pick(d, kind='cyl', r=ARM_W / 2)))
    log('measured', json.dumps(meas))
    v, bx = volume(d), bbox(d)
    export(j.sw, d, WIP / 'buck_mount.step')
    export(j.sw, d, WIP / 'buck_mount.stl')
    save(d)
    close(j.sw, d)
    chk = stl_check(WIP / 'buck_mount.stl', v, bx)
    log('STL check', chk)
    step_mm = any('.MILLI.' in ln for ln in (WIP / 'buck_mount.step').read_text(errors='ignore').splitlines() if 'SI_UNIT' in ln)
    log('STEP in mm', step_mm)
    return dict(volume_mm3=round(v, 2), hand_volume_mm3=round(HAND_V, 2), hand_terms={k: round(x, 2) for k, x in HAND.items()},
                mass_g=round(v * 1.19e-3, 2), bbox=bx, measured=meas, stl=chk, step_mm=step_mm)


def build_b(j):
    """Idea B, crude: the same base, the board dropped on four pins and held by two snap latches. No tool, no screws."""
    d = new_part(j.sw, WIP / 'idea_b_snap.SLDPRT')
    base(d)
    cyls(d, 'POSTS', POSTS, ARM_W / 2, 0, BOARD_Z)
    cyls(d, 'PINS', POSTS, 1.5, BOARD_Z, BOARD_Z + 2.5, expect_dv=4 * math.pi * 1.5 ** 2 * 2.5)
    edge = BOARD_W / 2 + 0.3
    for k, sy in enumerate((1, -1)):
        lo, hi = sorted((sy * SPINE_HW, sy * (edge + 2.0)))
        box(d, f'LATCH_ARM{k}', (-5, lo, 0), (5, hi, T))
        lo, hi = sorted((sy * edge, sy * (edge + 2.0)))
        box(d, f'LATCH{k}', (-5, lo, T), (5, hi, BOARD_Z + BOARD_T + 3.0))
        lo, hi = sorted((sy * (edge - 1.3), sy * edge))
        box(d, f'HOOK{k}', (-5, lo, BOARD_Z + BOARD_T + 0.3), (5, hi, BOARD_Z + BOARD_T + 3.0))
    single_body(d)
    save(d)
    v, bx = volume(d), bbox(d)
    export(j.sw, d, WIP / 'idea_b_snap.stl')
    close(j.sw, d)
    return dict(volume_mm3=round(v, 2), mass_g=round(v * 1.19e-3, 2), bbox=bx)


def studies(j):
    """The 9 N case three ways (X, Y, Z through a rigid remote load at the board's centre of mass) and Z a second way
    (an even force on the four post tops). Held by the two spot faces under the M5 heads: no help from the rail."""
    j.simulation()
    d = open_doc(j.sw, WIP / 'buck_mount.SLDPRT')
    d.ForceRebuild3(False)
    tops = [f for px, py in POSTS for f in pick(d, kind='plane', at=(px + 2.75, py, BOARD_Z))]
    rings = [f for sx in (1, -1) for f in pick(d, kind='plane', at=(sx * (M5_X + 4.0), 0, T - SPOT_DEPTH))]
    expect('post top faces', len(tops), 4, 0)
    expect('spot faces', len(rings), 2, 0)
    cg = (0.0, BOARD_Y0, BOARD_Z + BOARD_T + 5.0)
    out = {}
    # ---- predictions, written before the solve (07-done.md) ----
    el = 1.2
    pred_nodes = int(1.45 * 8.5 * HAND_V / el ** 3)
    arm = HY - SPINE_HW
    inertia = ARM_W * T ** 3 / 12
    pred_sig = (9.0 / 4) * arm * (T / 2) / inertia
    pred_disp = (9.0 / 4) * arm ** 3 / (3 * PETG['EX'] / 1e6 * inertia)
    log(f'PREDICT el {el}: nodes {pred_nodes}; Z case: arm root bending {pred_sig:.2f} MPa nominal (x1.3 at the R{ROOT_R} round), '
        f'post deflection {pred_disp:.3f} mm from the arm alone (about twice that with the spine and tab); '
        'peak on the top or bottom face of an arm at its root round')
    out['predicted'] = dict(nodes=pred_nodes, arm_root_mpa=round(pred_sig, 2), disp_mm=round(pred_disp, 3))
    cases = [('Z_remote', ('remote', tops, cg, (0, 0, -9.0), (0, 0, 0))), ('X_remote', ('remote', tops, cg, (9.0, 0, 0), (0, 0, 0))),
             ('Y_remote', ('remote', tops, cg, (0, 9.0, 0), (0, 0, 0))), ('Z_even', ('normal', tops, 9.0))]
    for name, load in cases:
        t0 = time.time()
        r = static(j, d, 'D1_' + name, PETG, fixtures=[('fixed', rings)], loads=[load], el=el)
        s = r.summary()
        log(s)
        np.savez_compressed(WIP / f'd1_{name}.npz', pos=r.pos, s=r.s, disp=r.disp, fixed=r.fixed_pts, loaded=r.loaded_pts,
                            reaction=np.array(r.reaction), el=r.el)
        out[name] = dict(summary=s, seconds=round(time.time() - t0, 1))
    close(j.sw, d)
    return out


if __name__ == '__main__':
    res = {}
    with job() as j:
        res['mount'] = build_a(j)
        (HERE / 'd1_model.json').write_text(json.dumps(res, indent=1))
        res['idea_b'] = build_b(j)
        (HERE / 'd1_model.json').write_text(json.dumps(res, indent=1))
        if 'nostudy' not in sys.argv:
            res['studies'] = studies(j)
            (HERE / 'd1_model.json').write_text(json.dumps(res, indent=1, default=str))
    print('DONE d1_build', flush=True)
