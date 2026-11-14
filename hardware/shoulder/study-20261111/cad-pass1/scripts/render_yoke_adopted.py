"""The adopted shoulder (checks/size_audit/YOKE_ADOPTED.png): the real parts of 2026-11-14 as built (fork front as a yoke,
flange ring with rolled rim B, fork rear with the stiffer leg, cover band and ring in white), with and without the
optional dark cover ring. Real outer shell solid with the 160 mm opening drawn in; organic upper arm on the hub.

    python render_yoke_adopted.py        (under capped.py, with PYTHONPATH=.)
"""
import json

import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
import render_shoulder_with_shell as S
import render_yoke as Y

WIP = H.REPO / 'cad' / '_wip' / 'shoulder-pass1'
FIGS = WIP / 'yoke_adopted_figs.json'
DARK = (0.13, 0.13, 0.14)


def main():
    sh = S.outer_shell()
    ff = R.P['fork_front']
    cov = trimesh.load(WIP / 'stl' / 'cover_ring.stl')

    def it(roll=0.0, ring_on=True):
        x = Y.items(ff, sh, roll, None, True)
        return x + ([(cov, DARK, 1.0)] if ring_on else [])

    F = np.array([70.0, 350.0, 0.0])
    Ft = np.array([110.0, 345.0, 0.0])
    views = [('Front three-quarter', F + np.array([560.0, 200.0, 780.0]), F, 28, (760, 760), (0, 1, 0)),
             ('Back three-quarter', F + np.array([540.0, 180.0, -760.0]), F, 28, (760, 760), (0, 1, 0)),
             ('Straight from the front', F + np.array([0.0, 0.0, 1000.0]), F, 28, (760, 760), (0, 1, 0)),
             ('Straight from the left side', F + np.array([1000.0, 0.0, 0.0]), F, 28, (760, 760), (0, 1, 0)),
             ('Straight from above (front at the bottom)', Ft + np.array([0.0, 900.0, 0.0]), Ft, 26, (760, 760), (0, 0, -1))]
    ims = []
    for i, (name, eye, foc, ang, size, up) in enumerate(views):
        im = H.shot(it(), f'adopted_{i}', eye, foc, size=size, angle=ang, up=up)
        H.label(im, (12, 10), name, 24)
        ims.append(im)
    r1 = H.row(ims)
    rows = [H.column([H.heading('As adopted, with the dark cover ring', r1.width, 32, 'fork front %.0f g' % (abs(ff.volume) * 1.27e-3)), r1], gap=6)]
    Fz = np.array([RX, RY + 4.0, 36.0])
    ims = []
    for nm, on in (('close, with the cover ring', True), ('close, without it: the motor\'s turning face and the slot round it', False)):
        for j, eye in enumerate((Fz + np.array([70.0, 50.0, 300.0]), Fz + np.array([150.0, 150.0, 190.0]))):
            im = H.shot(it(0.0, on), f'adopted_close{len(ims)}', eye, Fz, size=(940, 760), angle=24)
            H.label(im, (12, 10), nm, 22)
            ims.append(im)
    rows.append(H.column([H.heading('The opened area: the cover ring is optional', r1.width, 32), H.row(ims)], gap=6))
    Fr = np.array([RX, RY - 30.0, 10.0])
    ims = []
    for roll, nm in ((90.0, 'roll +90: arm straight out'), (-11.0, 'roll -11: at the inward stop')):
        for j, (vn, eye) in enumerate((('front three-quarter', Fr + np.array([420.0, 190.0, 640.0])), ('straight from the front', Fr + np.array([0.0, 0.0, 800.0])))):
            im = H.shot(it(roll), f'adopted_roll{int(roll)}_{j}', eye, Fr, size=(940, 760), angle=30)
            H.label(im, (12, 10), f'{nm}, {vn}', 22)
            ims.append(im)
    rows.append(H.column([H.heading('Moving: the drum, its screws and the cover ring stay with the body; the yoke turns over them', r1.width, 32), H.row(ims)], gap=6))
    if FIGS.exists():
        lines = json.loads(FIGS.read_text(encoding='utf-8'))['lines']
        rows.append(H.column([H.heading('Figures of the adopted set', r1.width, 32), Y.text_block(lines, r1.width)], gap=6))
    head = H.heading('Shoulder as adopted 2026-11-14: yoke fork front, rolled rim, white cover band, stiffer rear leg', r1.width, 46,
                     'The real parts as built. Outer body shell of 2026-11-06 with the 160 mm opening drawn in; organic upper arm on the hub.')
    sheet = H.column([head] + rows, gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(S.OUT / 'YOKE_ADOPTED.png', optimize=True)
    print('saved', S.OUT / 'YOKE_ADOPTED.png', sheet.size)


if __name__ == '__main__':
    main()
