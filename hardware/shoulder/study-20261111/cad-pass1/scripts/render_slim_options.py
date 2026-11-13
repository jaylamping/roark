"""Today's shoulder beside slimmer variants as quick ENVELOPE models (checks/size_audit/SLIM_OPTIONS.png).

The variants are not CAD: they are today's meshes with their skins pulled in by simple rules (below), to show what each
idea would look like on the torso. Motors are drawn solid and dark inside see-through plastic. Outer shell as in
render_shoulder_with_shell.py (panels of 2026-11-06 with the r 80 opening drawn in).

    python render_slim_options.py        (under capped.py)

  today        as built in CAD
  tight skin   drum's crowned sides and bell pulled in to 3 mm outside the rims (Z -31.5 / +39), drum wall 3 mm closer to the
               motor's lugs, fork front dome 7 mm lower, sleeve round the yaw motor 3.5 mm a side closer
  short back   tight skin, and the 12 mm of cable channel behind the motor taken out of the depth (rear face -60.8 -> -48.8)
  no rear      tight skin, and no rear bearing or rear fork leg at all (shown only to see what it buys; not recommended)
"""
import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
import render_shoulder_with_shell as S

OUT = S.OUT


def squeeze(v, axis, lim, k, above=True):
    """Pull coordinates beyond `lim` back toward it by factor k."""
    x = v[:, axis]
    m = x > lim if above else x < lim
    x[m] = lim + (x[m] - lim) * k


def radial(v, r0, k, ymax=None):
    """Pull points further than r0 from the roll axis in by factor k."""
    dx, dy = v[:, 0] - RX, v[:, 1] - RY
    r = np.hypot(dx, dy)
    m = r > r0
    if ymax is not None:
        m &= v[:, 1] < ymax
    s = np.ones(len(v))
    s[m] = (r0 + (r[m] - r0) * k) / r[m]
    v[:, 0], v[:, 1] = RX + dx * s, RY + dy * s


def variant(kind):
    P = {k: m.copy() for k, m in R.P.items()}
    M = {k: m.copy() for k, m in R.M.items()}
    if kind == 'today':
        return P, M
    d = P['drum'].vertices
    squeeze(d, 2, 39.0, 0.25, True)
    squeeze(d, 2, -31.5, 0.25, False)
    radial(d, 50.0, 0.67)
    squeeze(P['fork_front'].vertices, 2, 40.0, 0.3, True)
    for k in ('fork_front', 'fork_rear'):                   # the sleeve round the yaw motor, below the drum
        v = P[k].vertices
        low = v[:, 1] < 372.0
        for sg in (1, -1):
            m = low & (sg * (v[:, 0] - RX) > 41.5)
            v[m, 0] = RX + sg * (41.5 + (sg * (v[m, 0] - RX) - 41.5) * 0.4)
    if kind == 'short back':
        for k in ('fork_rear', 'cap'):
            squeeze(P[k].vertices, 2, -39.3, 0.442, False)
        squeeze(M['bearing'].vertices, 2, -39.3, 0.442, False)
        squeeze(P['fork_front'].vertices, 2, -39.3, 0.442, False)
    if kind == 'no rear':
        del P['fork_rear'], M['bearing']
        squeeze(P['cap'].vertices, 2, -39.3, 0.0, False)
        squeeze(P['fork_front'].vertices, 2, -39.3, 0.0, False)
    return P, M


def depth_of(P):
    z = np.concatenate([P[k].vertices[:, 2] for k in P if k in ('drum', 'cap', 'fork_front', 'fork_rear')])
    return z.min(), z.max()


def main():
    sh = S.outer_shell()
    F = np.array([60.0, 345.0, 0.0])
    views = [('Front three-quarter', F + np.array([650.0, 220.0, 900.0]), F, (0, 1, 0), None),
             ('Back three-quarter', F + np.array([620.0, 200.0, -880.0]), F, (0, 1, 0), None),
             ('Straight from the front', F + np.array([0.0, 0.0, 1150.0]), F, (0, 1, 0), ((-40.0, 175.0, 240.0), (1, 0, 0))),
             ('Straight from the left side', F + np.array([1150.0, 0.0, 0.0]), F, (0, 1, 0), ((330.0, 175.0, -50.0), (0, 0, 1))),
             ('Straight from above (front at the bottom)', np.array([110.0, 345.0, 0.0]) + np.array([0.0, 900.0, 0.0]), np.array([110.0, 345.0, 0.0]), (0, 0, -1), ((120.0, 520.0, 110.0), (1, 0, 0)))]
    notes = {'today': 'TODAY, as built in CAD',
             'tight skin': 'TIGHT SKIN: drum sides, bell and dome pulled in, thinner sleeve round the yaw motor. No function lost',
             'short back': 'TIGHT SKIN + SHORT BACK: the wires moved out from behind the motor, 12 mm less depth',
             'no rear': 'NO REAR SUPPORT: tight skin, no rear bearing and no rear fork leg. Shown to see what it buys; not recommended'}
    rows = []
    for kind in ('today', 'tight skin', 'short back', 'no rear'):
        P, M = variant(kind)
        z0, z1 = depth_of(P)
        ims = []
        for i, (name, eye, foc, up, bar) in enumerate(views):
            it = [(m, H.PARTC, 0.42) for k, m in P.items()] + [(m, H.MOTORC, 1.0) for m in M.values()]
            it += [(m, H.ARMC if n != 'rs02_ring' else H.MOTORC, 1.0) for n, m in R.UA.items()] + [(sh, S.SHELL_COL, 1.0)]
            if bar:
                it.append((S.scale_bar(bar[0], 100.0, bar[1]), (0.85, 0.1, 0.1), 1.0))
            im = H.shot(it, f'slim_{kind.replace(" ", "_")}_{i}', eye, foc, size=(760, 760), angle=30 if i < 4 else 26, up=up)
            H.label(im, (12, 10), name, 24)
            if bar:
                H.label(im, (12, 712), 'red bar = 100 mm', 22, fill=(190, 30, 30))
            ims.append(im)
        w = 5 * 760 + 4 * 16
        rows.append(H.column([H.heading(notes[kind], w, 34, f'depth front to back at the roll joint {z1 - z0:.0f} mm (the motor is 57)'), H.row(ims)], gap=6))
        print(kind, 'depth %.1f (%.1f to %.1f)' % (z1 - z0, z0, z1), flush=True)
    head = H.heading('Shoulder: today beside three slimmer ideas', rows[0].width, 46,
                     'Quick envelope models, not finished CAD: today\'s shapes with the skin pulled in by simple rules, to judge the look only. Plastic is drawn see-through; the dark shapes inside are the motors. '
                     'Outer body shell of 2026-11-06 with the r 80 opening drawn in.')
    sheet = H.column([head] + rows, gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(OUT / 'SLIM_OPTIONS.png', optimize=True)
    print('saved', OUT / 'SLIM_OPTIONS.png', sheet.size)


if __name__ == '__main__':
    main()
