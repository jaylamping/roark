"""In-between look options (checks/size_audit/IN_BETWEEN_OPTIONS.png): today's shoulder in the top row, then the fork front
opened three ways (LOOK=ibA, ibB, ibC: real CAD cuts, look builds in cad/_wip/shoulder-pass1/stl_look_ib*). Drum closed.
Plastic opaque white, motors dark, the real outer shell solid, the organic upper arm below the hub.

    python render_in_between.py        (under capped.py)
"""
import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
import render_shoulder_with_shell as S

WIP = H.REPO / 'cad' / '_wip' / 'shoulder-pass1'
ROWS = [('today', 'TODAY: the fork front covers the roll motor\'s whole face', None),
        ('ibA', 'A  SPOKES: three windows between spokes; the rim stays and covers the drum\'s eight front screws', 'stl_look_ibA'),
        ('ibC', 'B  BAND: one arc window over the top, no spokes; the rim stays, joined to the hub only through the lower cheek', 'stl_look_ibC'),
        ('ibB', 'C  YOKE: everything above the hub removed, rim and all; the drum\'s front lip and its eight screws show', 'stl_look_ibB')]


def main():
    sh = S.outer_shell()
    F = np.array([70.0, 350.0, 0.0])
    Fc = np.array([RX, RY - 12.0, 30.0])
    views = [('Front three-quarter', F + np.array([560.0, 200.0, 780.0]), F, 28, (760, 760)),
             ('Back three-quarter', F + np.array([540.0, 180.0, -760.0]), F, 28, (760, 760)),
             ('Straight from the front', F + np.array([0.0, 0.0, 1000.0]), F, 28, (760, 760)),
             ('Straight from the left side', F + np.array([1000.0, 0.0, 0.0]), F, 28, (760, 760)),
             ('Close, from the front', Fc + np.array([120.0, 60.0, 430.0]), Fc, 26, (900, 760))]
    rows, masses = [], {}
    for tag, title, folder in ROWS:
        ff = R.P['fork_front'] if folder is None else trimesh.load(WIP / folder / 'fork_front.stl')
        masses[tag] = abs(ff.volume) * 1.27e-3
        ims = []
        for i, (name, eye, foc, ang, size) in enumerate(views):
            it = [(m if k != 'fork_front' else ff, H.PARTC, 1.0) for k, m in R.P.items()] + [(m, H.MOTORC, 1.0) for m in R.M.values()]
            it += [(m, H.ARMC if n != 'rs02_ring' else H.MOTORC, 1.0) for n, m in R.UA.items()] + [(sh, S.SHELL_COL, 1.0)]
            im = H.shot(it, f'ib_{tag}_{i}', eye, foc, size=size, angle=ang)
            H.label(im, (12, 10), name, 24)
            ims.append(im)
        r = H.row(ims)
        sub = f'fork front {masses[tag]:.0f} g' + ('' if tag == 'today' else f' ({masses[tag] - masses["today"]:+.0f} g against today)')
        rows.append(H.column([H.heading(title, r.width, 32, sub), r], gap=6))
        print(tag, 'fork front %.1f g, bounds' % masses[tag], ff.bounds.round(1).tolist(), flush=True)
    head = H.heading('Shoulder look, "in between": drum closed, fork front opened', rows[0].width, 46,
                     'Look mock-ups in CAD (real cuts on the fork front; nothing checked for strength yet). Same motors, joints, bearings, reach and depth. '
                     'Outer body shell of 2026-11-06 with the r 80 opening drawn in; organic upper arm below the hub.')
    sheet = H.column([head] + rows, gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(S.OUT / 'IN_BETWEEN_OPTIONS.png', optimize=True)
    print('saved', S.OUT / 'IN_BETWEEN_OPTIONS.png', sheet.size)


if __name__ == '__main__':
    main()
