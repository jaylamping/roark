"""Shared pieces for the cable rig how-to sheets (render_rig_howto_*.py): the shoulder on the torso frame with the shell,
cached meshes, 3D markers, and panel layout with PIL.

Models used: the shoulder's current build STLs (cad/_wip/shoulder-pass1/stl), the motors and the frozen upper arm from
cad/reference/shoulder, and the rev A torso frame with its shell parts and the inner shell
(J:/code/_transfer/shoulder/torso_frame.step and shell_inner.step, 2026-11-11, moved 38 mm in X into the shoulder's
coordinates, as in render_pass1.py and check_shell_trim.py).
"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve()
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO / 'cad' / 'scripts' / 'shoulder'))
import render_pass1 as R  # noqa: E402  (loads the shoulder, motors, arm and frame corner)
from check_clearance import named_solids, tess  # noqa: E402
from build_asm import FRAME_SHIFT  # noqa: E402
from dims import RX, RY  # noqa: E402

CACHE = REPO / 'cad' / '_wip' / 'cable-rigs' / 'howto_cache'
OUT = REPO / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'cable_rigs'
CACHE.mkdir(parents=True, exist_ok=True)

SHELLC, FRAMEC2, ARMC, PARTC, MOTORC = (0.80, 0.84, 0.90), (0.50, 0.52, 0.56), (0.93, 0.93, 0.91), (0.96, 0.96, 0.94), (0.25, 0.26, 0.28)
RED, BLACK, PAIR = (0.85, 0.10, 0.10), (0.08, 0.08, 0.08), (0.95, 0.75, 0.10)
HI = (1.0, 0.45, 0.0)          # highlight
C1, C2, C3, C4 = (0.20, 0.50, 0.85), (0.95, 0.60, 0.15), (0.30, 0.70, 0.40), (0.70, 0.35, 0.75)


def font(sz):
    try:
        return ImageFont.truetype('arial.ttf', sz)
    except OSError:
        return ImageFont.load_default(size=sz)


def fontb(sz):
    try:
        return ImageFont.truetype('arialbd.ttf', sz)
    except OSError:
        return font(sz)


def torso_meshes():
    """(frame, shell) meshes of the whole rev A torso in the shoulder's coordinates, cached as STL."""
    fp, sp = CACHE / 'torso_frame_all.stl', CACHE / 'torso_shell_all.stl'
    if not (fp.exists() and sp.exists()):
        import cadquery as cq
        fr, sh = [], []
        for nm, s in named_solids(r'J:/code/_transfer/shoulder/torso_frame.step'):
            if nm.startswith('actuator__rs03'):
                continue
            (sh if nm.startswith('shellpart') else fr).append(tess(s, 0.5))
        try:
            sh += [tess(f, 0.6) for f in cq.importers.importStep(r'J:/code/_transfer/shoulder/shell_inner.step').faces().vals()]
        except Exception as ex:
            print('inner shell not loaded:', ex)
        for lst, path in ((fr, fp), (sh, sp)):
            m = trimesh.util.concatenate(lst)
            m.apply_translation((-FRAME_SHIFT, 0, 0))
            m.export(path)
    return trimesh.load(fp), trimesh.load(sp)


def ring_marker(centre, normal, r, thick=3.0):
    """A torus-like ring (a thin annulus tube) to circle something in a 3D view."""
    t = np.linspace(0, 2 * np.pi, 72)
    n = np.array(normal, float) / np.linalg.norm(normal)
    a = np.cross(n, (0, 1, 0) if abs(n[1]) < 0.9 else (1, 0, 0))
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    pts = [np.array(centre) + r * (np.cos(x) * a + np.sin(x) * b) for x in t]
    return R.tube(pts, thick)


def arrow(p0, p1, r=2.5):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    ln = np.linalg.norm(d)
    d /= ln
    shaft = trimesh.creation.cylinder(radius=r, segment=np.array([p0, p1 - d * 5 * r]), sections=16)
    head = trimesh.creation.cone(radius=2.6 * r, height=5 * r, sections=20)
    z = np.array([0, 0, 1.0])
    v = np.cross(z, d)
    c = float(np.dot(z, d))
    if np.linalg.norm(v) < 1e-9:
        T = np.eye(4) if c > 0 else trimesh.transformations.rotation_matrix(np.pi, (1, 0, 0))
    else:
        T = trimesh.transformations.rotation_matrix(np.arccos(np.clip(c, -1, 1)), v)
    T[:3, 3] = p1 - d * 5 * r
    head.apply_transform(T)
    return trimesh.util.concatenate([shaft, head])


def shot(items, name, eye, focal, size=(1200, 1000), angle=28.0, up=(0, 1, 0)):
    p = CACHE / f'{name}.png'
    R.render(items, p, np.array(eye, float), np.array(focal, float), up=up, size=size, angle=angle)
    return Image.open(p).convert('RGB')


def caption(im, text, sz=30, pad=14, bold=False, fill=(20, 20, 20), bg=(255, 255, 255)):
    """The image with a caption strip under it (wrapped)."""
    f = fontb(sz) if bold else font(sz)
    d = ImageDraw.Draw(im)
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) > im.width - 2 * pad and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    h = len(lines) * int(sz * 1.3) + 2 * pad
    out = Image.new('RGB', (im.width, im.height + h), bg)
    out.paste(im, (0, 0))
    d = ImageDraw.Draw(out)
    for i, ln in enumerate(lines):
        d.text((pad, im.height + pad + i * int(sz * 1.3)), ln, fill=fill, font=f)
    return out


def label(im, xy, text, sz=28, fill=(20, 20, 20), bold=True, box=True):
    d = ImageDraw.Draw(im)
    f = fontb(sz) if bold else font(sz)
    if box:
        w = d.textlength(text, font=f)
        d.rectangle((xy[0] - 6, xy[1] - 4, xy[0] + w + 6, xy[1] + sz + 8), fill=(255, 255, 255), outline=(120, 120, 120))
    d.text(xy, text, fill=fill, font=f)
    return im


def row(ims, gap=16, bg=(255, 255, 255)):
    h = max(i.height for i in ims)
    out = Image.new('RGB', (sum(i.width for i in ims) + gap * (len(ims) - 1), h), bg)
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def column(ims, gap=18, bg=(255, 255, 255)):
    w = max(i.width for i in ims)
    out = Image.new('RGB', (w, sum(i.height for i in ims) + gap * (len(ims) - 1)), bg)
    y = 0
    for i in ims:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def heading(text, width, sz=44, sub=None):
    h = sz + 34 + (int(sz * 0.7) + 8 if sub else 0)
    im = Image.new('RGB', (width, h), (32, 60, 110))
    d = ImageDraw.Draw(im)
    d.text((18, 14), text, fill=(255, 255, 255), font=fontb(sz))
    if sub:
        d.text((18, 14 + sz + 8), sub, fill=(215, 225, 240), font=font(int(sz * 0.62)))
    return im


def shoulder_scene(part_op=1.0, with_cover=True):
    """Shoulder parts, motors and the arm as render items."""
    it = [(m, PARTC, part_op) for k, m in R.P.items() if with_cover or k != 'cover']
    it += [(m, MOTORC, 1.0) for m in R.M.values()]
    it += [(m, ARMC if n != 'rs02_ring' else MOTORC, 1.0) for n, m in R.UA.items()]
    return it
