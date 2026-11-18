"""Picture sheet of one printed part for the pre-print gate (conventions/part-lifecycle.md: all sides including the bed
side). Eight views of the export: the bed side, the side opposite, four sides and two oblique views.

    python part_sheet.py <export.STL> <out.png> "<title>" <bed>      bed: +Y or -Y, the export direction that lies on the plate

Views are in the export's coordinates with the print's up direction drawn upward in the four side views.
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from view import render


def main(stl, out, title, bed):
    s = 1.0 if bed == '+Y' else -1.0      # the camera's elevation that looks at the bed side
    # view.py keeps +Y up on screen; for a part printed with +Y on the plate the side views are turned over afterwards
    views = [('Bed side (on the plate)', 0, 89.9 * s, False), ('Top as printed', 0, -89.9 * s, False),
             ('Side, from +Z', 0, 0, True), ('Side, from +X', 90, 0, True), ('Side, from -Z', 180, 0, True), ('Side, from -X', 270, 0, True),
             ('Oblique, bed side', 35, 30 * s, True), ('Oblique, top as printed', 215, -30 * s, True)]
    W, H, pad, head = 760, 620, 14, 86
    sheet = Image.new('RGB', (4 * W + 5 * pad, head + 2 * (H + 44) + 2 * pad), 'white')
    dr = ImageDraw.Draw(sheet)
    try:
        f1, f2 = ImageFont.truetype('arialbd.ttf', 34), ImageFont.truetype('arial.ttf', 26)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    dr.text((pad, 20), title, fill='black', font=f1)
    with tempfile.TemporaryDirectory() as td:
        for i, (name, az, el, turn) in enumerate(views):
            p = str(Path(td) / f'v{i}.png')
            render([stl], p, az=az, el=el, size=(W, H), zoom=1.25, colors=[(0.30, 0.31, 0.34)])
            im = Image.open(p).convert('RGB')
            if turn and bed == '+Y':
                im = im.rotate(180)
            x, y = pad + (i % 4) * (W + pad), head + (i // 4) * (H + 44 + pad)
            sheet.paste(im, (x, y + 40))
            dr.text((x + 4, y + 4), name, fill='black', font=f2)
    sheet.save(out, optimize=True)
    print(out, sheet.size, Path(out).stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main(*sys.argv[1:5])
