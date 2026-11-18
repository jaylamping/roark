"""All-sides sheet of one part STL (offscreen VTK): front (+Z), back, +X side, -X side, from above (+Y), from below and
two three-quarter views. python render_part_sheet.py PART.STL OUT.png "title" """
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r'J:/code/roark-wt/shoulder-study/cad/scripts/shoulder')
import view  # noqa: E402

stl, out, title = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
VIEWS = [('front (+Z)', 0, 0), ('+X side (outboard)', 90, 0), ('back (-Z)', 180, 0), ('-X side (inboard)', 270, 0),
         ('from above (+Y)', 0, 89.9), ('from below (-Y)', 0, -89.9), ('back three-quarter, from above', 215, 35),
         ('back three-quarter, from below', 215, -35)]
W, H = 900, 760
tmp = Path(tempfile.mkdtemp())
tiles = []
for i, (nm, az, el) in enumerate(VIEWS):
    p = tmp / f'v{i}.png'
    view.render([stl], str(p), az, el, size=(W, H), zoom=1.25)
    tiles.append((nm, Image.open(p).convert('RGB')))
try:
    f1, f2 = ImageFont.truetype('arial.ttf', 26), ImageFont.truetype('arial.ttf', 34)
except OSError:
    f1 = f2 = ImageFont.load_default()
sheet = Image.new('RGB', (4 * W, 2 * H + 70), 'white')
d = ImageDraw.Draw(sheet)
d.text((20, 14), title, fill='black', font=f2)
for i, (nm, im) in enumerate(tiles):
    x, y = (i % 4) * W, 70 + (i // 4) * H
    sheet.paste(im, (x, y))
    d.text((x + 14, y + 10), nm, fill='black', font=f1)
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print('saved', out)
