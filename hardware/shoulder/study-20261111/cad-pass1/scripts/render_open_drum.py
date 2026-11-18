"""Today's shoulder beside a "motor showing" idea (checks/size_audit/MOTOR_SHOWING.png): the drum opened so the roll motor
shows as a dark band, as the organic arm shows its motors. A quick picture, not CAD: today's drum mesh with the triangles
of its outer skin left out between the two rims (Z -21 to +27), except on the body side where the spine to the pitch
motor stays. Plastic opaque white, motors dark, outer shell solid.

    python render_open_drum.py        (under capped.py)
"""
import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
import render_shoulder_with_shell as S

ARM_RENDER = H.HERE.parents[1] / 'D6_shoulder_vs_arm_render.png'


def open_drum():
    d = R.P['drum'].copy()
    c = d.triangles_center
    r = np.hypot(c[:, 0] - RX, c[:, 1] - RY)
    band = (c[:, 2] > -21.0) & (c[:, 2] < 27.0) & (r > 49.0) & (c[:, 0] > RX - 28.0)
    return trimesh.Trimesh(d.vertices, d.faces[~band], process=False)


def main():
    sh = S.outer_shell()
    F = np.array([70.0, 350.0, 0.0])
    views = [('Front three-quarter', F + np.array([560.0, 200.0, 780.0]), F), ('Back three-quarter', F + np.array([540.0, 180.0, -760.0]), F),
             ('Straight from the front', F + np.array([0.0, 0.0, 1000.0]), F), ('Straight from the left side', F + np.array([1000.0, 0.0, 0.0]), F)]
    rows = []
    for tag, title, drum in (('today', 'TODAY: the roll motor is inside a closed white drum', R.P['drum']),
                             ('open', 'MOTOR SHOWING: the drum opened between its two rims, the motor seen as a dark band (as the arm shows its motors)', open_drum())):
        ims = []
        for i, (name, eye, foc) in enumerate(views):
            it = [(m if k != 'drum' else drum, H.PARTC, 1.0) for k, m in R.P.items()] + [(m, H.MOTORC, 1.0) for m in R.M.values()]
            it += [(m, H.ARMC if n != 'rs02_ring' else H.MOTORC, 1.0) for n, m in R.UA.items()] + [(sh, S.SHELL_COL, 1.0)]
            im = H.shot(it, f'open_{tag}_{i}', eye, foc, size=(760, 760), angle=28)
            H.label(im, (12, 10), name, 24)
            ims.append(im)
        rows.append(H.column([H.heading(title, 4 * 760 + 3 * 16, 32), H.row(ims)], gap=6))
    arm = Image.open(ARM_RENDER).convert('RGB')
    arm = arm.crop((arm.width // 2 + 150, 0, arm.width, arm.height))
    arm = arm.resize((int(arm.width * 1560 / arm.height), 1560), Image.LANCZOS)
    arm = H.column([H.heading('For comparison: the organic arm', arm.width, 32), H.caption(arm, 'The upper arm and elbow from the arm thread\'s own render, under the shoulder built today. Its motors show as dark bands.', 26)], gap=6)
    body = H.row([H.column(rows, gap=10), arm], gap=20)
    head = H.heading('Shoulder look: closed drum today, or the motor showing', body.width, 46,
                     'A quick picture to judge by eye, not CAD: same motors, joints, bearings and reach. Opening the drum needs a strength check and a new place for the wires that run under its skin today.')
    sheet = H.column([head, body], gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(S.OUT / 'MOTOR_SHOWING.png', optimize=True)
    print('saved', S.OUT / 'MOTOR_SHOWING.png', sheet.size)


if __name__ == '__main__':
    main()
