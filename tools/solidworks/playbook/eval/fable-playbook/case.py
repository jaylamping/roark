"""The T3 load case, shared by T3, T4 and T5: four base hole walls fixed, 150 N along +X on the bore.

Support: the bracket is screwed down through its four base holes, so the four hole walls are fixed (05-fea.md's own
example for a screwed part). The base underside is left free: a mounting surface under it would only add support.
Load: the motor sits in the bore and pulls +X, so a remote force of 150 N at the bore centre (3, 25, 28), carried rigidly
to the bore wall (the motor body is stiff next to PETG).
"""
import numpy as np

from common import BORE, D_BASE, D_BORE, D_UP, F_MOTOR, OUT
from swfea import PETG, static
from swkit import expect, log, pick


def faces_of(d, base_hole_r=D_BASE / 2):
    holes = pick(d, kind='cyl', r=base_hole_r, inside=[15, 0, -0.1, 75, 50, 6.1])
    bore = pick(d, kind='cyl', r=D_BORE / 2)
    motor = pick(d, kind='cyl', r=D_UP / 2)
    expect('fixed hole walls', len(holes), 4, 0)
    expect('bore faces', len(bore), 1, 0)
    expect('motor hole walls', len(motor), 4, 0)
    return holes, bore, motor


def run(j, d, name, el, local, extra_ctrl=(), layer=(0, 0, 1)):
    """One solve. local: element size on the hole walls, the bore and extra_ctrl faces [(faces, size)]."""
    holes, bore, motor = faces_of(d)
    ctrl = [(holes, local), (bore, local), (motor, local)] + [(fs, s) for fs, s in extra_ctrl if fs]
    r = static(j, d, name, PETG, fixtures=[('fixed', holes)],
               loads=[('remote', bore, (3.0, BORE[0], BORE[1]), (F_MOTOR, 0, 0), (0, 0, 0))], el=el, ctrl=ctrl)
    log(r.summary())
    np.savez_compressed(OUT.parent.parent.parent / '_sim' / 'sw-eval' / f'{name}.npz', pos=r.pos, s=r.s, disp=r.disp,
                        reaction=r.reaction, fixed=r.fixed_pts, loaded=r.loaded_pts)
    return r


def checks(r, tag=''):
    """Checks 1 to 4 of 05-fea.md on one result; returns the numbers."""
    out = {}
    # 1 reaction equals load: fixtures push back -150 N in X
    expect(tag + 'reaction Fx N', r.reaction[0], -F_MOTOR, 0.01)
    expect(tag + 'reaction resultant against applied N', r.reaction[3], r.applied, 0.01)
    assert abs(r.reaction[1]) < 1.5 and abs(r.reaction[2]) < 1.5, r.reaction
    out['reaction_n'] = r.reaction
    # 3 plain section: the upright at Z 12 (between the fillet top at Z 10 and the lowest hole edge at Z 15.3),
    # bending stress on its two faces, M c / I with M = 150 N x (28 - 12) mm, I = 50 x 6^3 / 12, c = 3
    hand = F_MOTOR * (BORE[1] - 12.0) * 3 / (50 * 6 ** 3 / 12)
    strip = np.abs(r.pos[:, 2] - 12.0) < 1.0
    back = strip & (r.pos[:, 0] < 0.01)
    front = strip & (r.pos[:, 0] > 5.99) & (r.pos[:, 0] < 6.01)
    sb, sf = float(r.s[back, 3].mean()), float(r.s[front, 3].mean())
    log(f'{tag}plain section Z 12: sz back face {sb:.2f} MPa on {back.sum()} nodes, inner face {sf:.2f} on {front.sum()} '
        f'nodes, hand +/-{hand:.2f}')
    out['section_back_sz'], out['section_front_sz'], out['section_hand'] = round(sb, 2), round(sf, 2), round(hand, 2)
    return out
