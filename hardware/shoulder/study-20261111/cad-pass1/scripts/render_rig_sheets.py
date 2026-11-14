"""All-sides sheet for each cable crossing rig (offscreen VTK): one row per part, as it lies on the print bed; columns are
three-quarter from above, three-quarter from below, straight down on the top, straight up at the underside, and one side.

    python render_rig_sheets.py [roll yaw pitch]        -> checks/cable_rigs/SHEET_<rig>.png
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'cad' / 'scripts' / 'shoulder'))
import view  # noqa: E402

FX = ROOT / 'cad' / 'exports' / 'fixtures'
OUT = ROOT / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'cable_rigs'
RIGS = {
    'roll': [('deck tray', 'roll_deck_tray'), ('deck lid', 'roll_deck_lid'), ('axis base', 'roll_axis_base'), ('axis top', 'roll_axis_top')],
    'yaw': [('hub', 'yaw2_hub'), ('fork part, 5.5', 'yaw2_fork'), ('fork part, 7.0', 'yaw2_fork_7'), ('boss, 5.5', 'yaw2_boss'), ('boss, 7.0', 'yaw2_boss_7'),
            ('cap', 'yaw2_cap')],
    'pitch': [('tray', 'pitch_tray'), ('lid', 'pitch_lid')],
}
VIEWS = [('from above', 30, 35), ('from below', 30, -35), ('top', 0, 89.9), ('underside', 0, -89.9), ('side', 0, 0)]
W, H = 620, 520
ZUP = trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0))      # the bed's Z becomes the renderer's up (Y)

tmp = Path(tempfile.mkdtemp())
try:
    f1, f2 = ImageFont.truetype('arial.ttf', 22), ImageFont.truetype('arial.ttf', 32)
except OSError:
    f1 = f2 = ImageFont.load_default()
for rig in sys.argv[1:] or list(RIGS):
    parts = RIGS[rig]
    sheet = Image.new('RGB', (len(VIEWS) * W, len(parts) * H + 64), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((16, 12), f'Cable rig: {rig}. Each part as it lies on the bed', fill='black', font=f2)
    for r, (label, stem) in enumerate(parts):
        m = trimesh.load(FX / f'fixtures_cable_rig_{stem}.STL')
        ext = m.extents
        m.apply_transform(ZUP)
        p = tmp / f'{stem}.stl'
        m.export(p)
        for c, (nm, az, el) in enumerate(VIEWS):
            q = tmp / f'{stem}_{c}.png'
            view.render([str(p)], str(q), az, el, size=(W, H), zoom=1.2)
            sheet.paste(Image.open(q).convert('RGB'), (c * W, 64 + r * H))
            d.text((c * W + 10, 64 + r * H + 8), f'{label}: {nm}' + (f'  ({ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm)' if c == 0 else ''), fill='black', font=f1)
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / f'SHEET_{rig}.png')
    print('saved', OUT / f'SHEET_{rig}.png')
