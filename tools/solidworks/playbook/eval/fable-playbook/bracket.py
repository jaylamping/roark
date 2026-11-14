"""The T1 bracket as a function, so T4 (no inside fillet) builds the same part from the same numbers."""
import math

from common import (BASE_HOLES, BORE, D_BASE, D_BORE, D_UP, R_IN, R_OUT, UP_HOLES, hand_volume)
from swkit import (MID, Sk, bbox, bodies, edges_where, expect, extrude, feature_errors, fillet, log, new_part, plane, save,
                   single_body, volume, Failed)

Q = 1 - math.pi / 4


def near(a, b, tol=0.01):
    return abs(a - b) < tol


def build(sw, path, inside_fillet=R_IN):
    d = new_part(sw, path)
    with Sk(d, plane(d, 'Z', 3.0, 'BASE_P'), 'BASE') as s:
        s.rect((0, 0, 3.0), (80, 50, 3.0))
    extrude(d, s.feat, 'BASE', 6.0, mode=MID, expect_dv=80 * 50 * 6)
    with Sk(d, plane(d, 'X', 3.0, 'UPRIGHT_P'), 'UPRIGHT') as s:
        s.rect((3.0, 0, 6), (3.0, 50, 46))
    extrude(d, s.feat, 'UPRIGHT', 6.0, mode=MID, expect_dv=6 * 50 * 40)
    expect('bodies after the upright', len(bodies(d)), 1, 0)
    save(d)

    if inside_fillet:
        e = edges_where(d, lambda p: near(p[0], 6) and near(p[2], 6))
        expect('inside-corner edges', len(e), 1, 0)
        v0 = volume(d)
        if fillet(d, e, (inside_fillet,), 'INSIDE_FILLET') is None:
            raise Failed('inside fillet did not build')
        expect('inside fillet adds', volume(d) - v0, Q * inside_fillet ** 2 * 50, 0.01)
        save(d)

    e = edges_where(d, lambda p: near(p[0], 80) and (near(p[1], 0) or near(p[1], 50)))
    expect('base corner edges at X 80', len(e), 2, 0)
    v0 = volume(d)
    if fillet(d, e, (R_OUT,), 'BASE_CORNERS') is None:
        raise Failed('base corner rounds did not build')
    expect('base corners remove', v0 - volume(d), 2 * Q * R_OUT ** 2 * 6, 0.01)
    e = edges_where(d, lambda p: near(p[2], 46) and (near(p[1], 0) or near(p[1], 50)))
    expect('upright top corner edges', len(e), 2, 0)
    v0 = volume(d)
    if fillet(d, e, (R_OUT,), 'UPRIGHT_CORNERS') is None:
        raise Failed('upright corner rounds did not build')
    expect('upright corners remove', v0 - volume(d), 2 * Q * R_OUT ** 2 * 6, 0.01)
    save(d)

    # cutting tools overshoot 1 mm each side into empty space (03-modelling.md): the volume removed is unchanged
    with Sk(d, plane(d, 'Z', 3.0, 'BASE_HOLES_P'), 'BASE_HOLES') as s:
        for x, y in BASE_HOLES:
            s.circle((x, y, 3.0), D_BASE / 2)
    extrude(d, s.feat, 'BASE_HOLES', 8.0, cut=True, mode=MID, expect_dv=4 * math.pi * (D_BASE / 2) ** 2 * 6)
    with Sk(d, plane(d, 'X', 3.0, 'BORE_P'), 'BORE') as s:
        s.circle((3.0, BORE[0], BORE[1]), D_BORE / 2)
    extrude(d, s.feat, 'BORE', 8.0, cut=True, mode=MID, expect_dv=math.pi * (D_BORE / 2) ** 2 * 6)
    with Sk(d, plane(d, 'X', 3.0, 'MOTOR_HOLES_P'), 'MOTOR_HOLES') as s:
        for y, z in UP_HOLES:
            s.circle((3.0, y, z), D_UP / 2)
    extrude(d, s.feat, 'MOTOR_HOLES', 8.0, cut=True, mode=MID, expect_dv=4 * math.pi * (D_UP / 2) ** 2 * 6)
    save(d)

    expect('volume against the hand value', volume(d), hand_volume(inside_fillet), 0.001)
    b = bbox(d)
    for k, want in enumerate((0, 0, 0, 80, 50, 46)):
        expect(f'box[{k}]', b[k], want, 0.01)
    errs = feature_errors(d)
    if errs:
        raise Failed(f'rebuild errors {errs}')
    single_body(d)
    save(d)
    log('built', path, 'volume', round(volume(d), 2))
    return d
