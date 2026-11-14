"""The left shoulder and upper arm on the torso with the real outer body shell (checks/size_audit/shoulder_with_shell.png).

Outer shell: marengo cad/exports/shell/marengo_shell_*.STL of 2026-11-06 (upper and lower front and back panels, hatches,
doors, grilles), brought into the shoulder's coordinates (X = lateral - 38, Y = height - 810.14, Z = forward). That shell
has the old r 53 socket hole and the collar. The r 80 opening of shoulder option A (hardware/shell/README.md) is not in
any model yet: here it is drawn in by leaving out the triangles inside r 80 round the left pitch axis, and the collar is
left out. Row 1: shell solid. Row 2: the same views with the shell see-through.

    python render_shoulder_with_shell.py        (under capped.py)
"""
import glob

import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
from dims import PZ

OUT = H.OUT.parent / 'size_audit'
OUT.mkdir(parents=True, exist_ok=True)
T = np.array([[0, 1, 0, -38.0], [0, 0, 1, -810.14], [1, 0, 0, 0], [0, 0, 0, 1.0]])
SHELL_COL = (0.36, 0.42, 0.52)


def outer_shell(open_r=80.0):
    ms = []
    for f in sorted(glob.glob('J:/code/marengo/cad/exports/shell/marengo_shell_*.STL')):
        n = f.split('marengo_shell_')[-1][:-4]
        if n.startswith(('bracket', 'coupon', 'screw', 'collar')):
            continue
        m = trimesh.load(f)
        m.apply_transform(T)
        ms.append(m)
    m = trimesh.util.concatenate(ms)
    v = m.vertices
    r = np.hypot(v[:, 1] - RY, v[:, 2] - PZ)
    inside = (r < open_r) & (v[:, 0] > 40.0)                    # the left socket's floor and inner cone
    keep = ~inside[m.faces].all(axis=1)
    return trimesh.Trimesh(v, m.faces[keep], process=False)


def scale_bar(p0, length=100.0, axis=(1, 0, 0)):
    a = np.array(axis, float)
    b = trimesh.creation.cylinder(radius=3.0, segment=np.array([np.array(p0, float), np.array(p0, float) + a * length]), sections=12)
    ends = [trimesh.creation.icosphere(subdivisions=1, radius=4.0) for _ in range(2)]
    ends[0].apply_translation(p0)
    ends[1].apply_translation(np.array(p0) + a * length)
    return trimesh.util.concatenate([b] + ends)


def main():
    sh = outer_shell()
    fr, _ = H.torso_meshes()
    F = np.array([40.0, 345.0, 0.0])
    views = [('Front three-quarter', F + np.array([650.0, 220.0, 900.0]), F, 30, None),
             ('Back three-quarter', F + np.array([620.0, 200.0, -880.0]), F, 30, None),
             ('Straight from the front', F + np.array([0.0, 0.0, 1150.0]), F, 30, ((-60.0, 175.0, 240.0), (1, 0, 0))),
             ('Straight from the left side', F + np.array([1150.0, 0.0, 0.0]), F, 30, ((330.0, 175.0, -50.0), (0, 0, 1))),
             ('Close-up: where the arm leaves the body', np.array([RX - 20.0, RY, 0.0]) + np.array([330.0, 150.0, 420.0]), np.array([RX - 45.0, RY - 20.0, 0.0]), 26, None)]
    rows = []
    for op, tag, cap in ((1.0, 'solid', 'Shell solid'), (0.32, 'ghost', 'Same views, shell see-through')):
        ims = []
        for i, (name, eye, foc, ang, bar) in enumerate(views):
            it = H.shoulder_scene() + [(sh, SHELL_COL, op)]
            if op < 1:
                it.append((fr, H.FRAMEC2, 1.0))
            if bar:
                it.append((scale_bar(bar[0], 100.0, bar[1]), (0.85, 0.1, 0.1), 1.0))
            im = H.shot(it, f'shell_{tag}_{i}', eye, foc, size=(960, 960), angle=ang)
            H.label(im, (14, 12), name, 30)
            if bar:
                H.label(im, (14, 900), 'red bar = 100 mm', 26, fill=(190, 30, 30))
            ims.append(im)
        rows.append(H.column([H.heading(cap, 5 * 960 + 4 * 16, 34), H.row(ims)], gap=6))
    head = H.heading('Left shoulder and upper arm with the outer body shell', rows[0].width, 46,
                     'Outer shell panels of 2026-11-06 (marengo), with the round r 80 shoulder opening of option A drawn in; the shell model itself has not been rebuilt for it. '
                     'Shoulder as built in CAD today, upper arm at its last frozen release. White: printed parts. Dark: motors.')
    sheet = H.column([head] + rows, gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(OUT / 'shoulder_with_shell.png', optimize=True)
    print('saved', OUT / 'shoulder_with_shell.png', sheet.size)


if __name__ == '__main__':
    main()
