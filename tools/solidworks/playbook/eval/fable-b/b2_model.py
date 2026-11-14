"""B2: the wall bracket of TASKS_B.md, one solid body, with the load patch (top face, X 55 to 65) split off as its own face."""
import math

from common import DENS, WIP, cyl, put, sha
from swkit import *

# ---- the specification -----------------------------------------------------------------------------------------------
PL = (0, 0, 0, 5, 40, 60)                      # wall plate box
HOLE_R, HOLES = 2.25, ((20, 12), (20, 48))     # dia 4.5 along X at (Y, Z)
ARM = (5, 15, 40, 65, 25, 52)                  # arm box
FIL = 3.0                                      # root fillets, arm top and bottom
PATCH_X = 55.0                                 # load patch: top face from here to X 65

v_plate = 5 * 40 * 60
v_holes = 2 * math.pi * HOLE_R ** 2 * 5
v_arm = 60 * 10 * 12
v_fil = 2 * (1 - math.pi / 4) * FIL ** 2 * 10
HAND = v_plate - v_holes + v_arm + v_fil


def split_face(d, name, pl, a, b, face_at):
    """Split the face through face_at with a sketched line a-b projected onto it (so a load can take part of a face).

    Not in swkit: InsertSplitLineProject with the sketch selected under mark 4 and the face under mark 1. The caller
    checks the two faces it expects afterwards.
    """
    with Sk(d, pl, name) as s:
        s.poly([a, b], closed=False)
    fs = pick(d, kind='plane', at=face_at)
    expect(name + ' face to split', len(fs), 1, 0)
    d.ClearSelection2(True)
    sd = d.SelectionManager.CreateSelectData
    sd.Mark = 4
    if not s.feat.Select2(False, 4):
        raise Failed(name + ': sketch not selected')
    sd = d.SelectionManager.CreateSelectData
    sd.Mark = 1
    if not fs[0].Select4(True, sd):
        raise Failed(name + ': face not selected')
    n0 = len(faces(d))
    d.InsertSplitLineProject(False, False)
    d.ForceRebuild3(False)
    if len(faces(d)) != n0 + 1:
        raise Failed(f'{name}: split line did not add a face ({n0} -> {len(faces(d))})')
    d.FeatureByPositionReverse(0).Name = name


def build(j, path):
    d = new_part(j.sw, path)
    with Sk(d, plane(d, 'X', 2.5, 'PLATE_P'), 'PLATE') as s:
        s.rect((2.5, 0, 0), (2.5, 40, 60))
    extrude(d, s.feat, 'PLATE', 5.0, mode=MID, expect_dv=v_plate)
    with Sk(d, plane(d, 'X', 2.5, 'HOLES_P'), 'SCREW_HOLES') as s:
        for y, z in HOLES:
            s.circle((2.5, y, z), HOLE_R)
    extrude(d, s.feat, 'SCREW_HOLES', 5.0, cut=True, mode=MID, expect_dv=v_holes)
    with Sk(d, plane(d, 'X', 35.0, 'ARM_P'), 'ARM') as s:
        s.rect((35.0, 15, 40), (35.0, 25, 52))
    extrude(d, s.feat, 'ARM', 60.0, mode=MID, expect_dv=v_arm)
    save(d)
    root = edges_where(d, lambda p: abs(p[0] - 5) < 0.01 and min(abs(p[2] - 52), abs(p[2] - 40)) < 0.01 and 14.99 < p[1] < 25.01)
    expect('root edges', len(root), 2, 0)
    v0 = volume(d)
    if fillet(d, root, (FIL,), 'ROOT_R3') != FIL:
        raise Failed('root fillet did not build')
    expect('fillet volume', volume(d) - v0, v_fil, 0.01)
    save(d)
    V = volume(d)
    expect('bracket volume', V, HAND, 0.001)
    split_face(d, 'LOAD_PATCH', plane(d, 'Z', 52.0, 'PATCH_P'), (PATCH_X, 14, 52), (PATCH_X, 26, 52), (40, 20, 52))
    expect('volume unchanged by the split', volume(d), V, 1e-6)
    save(d)
    return d, V


if __name__ == '__main__':
    P = WIP / 'wall_bracket.SLDPRT'
    with job() as j:
        d, V = build(j, P)
        b = bbox(d)
        for k, want in enumerate((0, 0, 0, 65, 40, 60)):
            expect(f'box[{k}]', b[k], want, 0.01)
        expect('rebuild errors', len(feature_errors(d)), 0, 0)
        single_body(d)
        meas = {}
        hs = pick(d, kind='cyl', r=HOLE_R)
        expect('hole faces', len(hs), 2, 0)
        got = sorted((round(cyl(f)[0][1], 4), round(cyl(f)[0][2], 4), round(cyl(f)[2], 4), abs(round(cyl(f)[1][0], 4)),
                      round(face_info(f)['box'][0], 3), round(face_info(f)['box'][3], 3)) for f in hs)
        meas['holes_y_z_r_axisx_x0_x1'] = got
        for g, (y, z) in zip(got, HOLES):
            expect('hole y', g[0], y, 0.001); expect('hole z', g[1], z, 0.001); expect('hole axis along X', g[3], 1, 0.001)
            expect('hole x0', g[4], 0, 0.001); expect('hole x1', g[5], 5, 0.001)
        fl = pick(d, kind='cyl', r=FIL)
        expect('fillet faces', len(fl), 2, 0)
        meas['fillets_axis_x_z'] = sorted((round(cyl(f)[0][0], 3), round(cyl(f)[0][2], 3), round(cyl(f)[2], 3)) for f in fl)
        expect('lower fillet axis z', meas['fillets_axis_x_z'][0][1], 37, 0.001)
        expect('upper fillet axis z', meas['fillets_axis_x_z'][1][1], 55, 0.001)
        expect('fillet axis x', meas['fillets_axis_x_z'][0][0], 8, 0.001)
        patch = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
        expect('load patch faces', len(patch), 1, 0)
        i = face_info(patch[0])
        meas['load_patch'] = dict(area=i['area'], box=i['box'])
        expect('load patch area', i['area'], 100, 0.001)
        expect('load patch x0', i['box'][0], 55, 0.001); expect('load patch x1', i['box'][3], 65, 0.001)
        wall = pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 5, 5))
        expect('wall face', len(wall), 1, 0)
        expect('wall face area', face_info(wall[0])['area'], 2400 - 2 * math.pi * HOLE_R ** 2, 0.001)
        tipf = pick(d, kind='plane', normal=(1, 0, 0), at=(65, 20, 46))
        expect('arm end face', len(tipf), 1, 0)
        expect('arm end face area', face_info(tipf[0])['area'], 120, 0.001)
        ib = face_info(tipf[0])['box']
        meas['arm_end_box'] = ib
        for k, want in enumerate((65, 15, 40, 65, 25, 52)):
            expect(f'arm end box[{k}]', ib[k], want, 0.001)
        save(d)
        close(j.sw, d)
    put('b2_model', dict(volume_mm3=V, hand_volume_mm3=HAND, mass_g=V * DENS, bbox_mm=b, measured=meas, sha256=sha(P)))
    print('B2 MODEL DONE')
