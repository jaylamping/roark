"""Picture sheet of an STL from all sides, and numbers for how boxy its surface is. Needs numpy only.

    python tools/solidworks/sheet.py part.stl                 # writes part.sheet.png, prints the shape numbers
    python tools/solidworks/sheet.py a.stl b.stl -o both.png  # one row per part, same scale: before and after

A model that cannot see its part cannot judge it. Run this after every step that changes the shape, open the PNG and look
at it; the report then shows what the reader would see. Eight views per part: front (from -Y), back, left (from -X),
right, top, bottom and two three-quarter views, all at one scale, lit the same way, with outline and crease lines.

The shape numbers (also `shape_stats(tris)`):
    flat_share      share of the surface area lying on planes larger than 1 % of the total area
    largest_flat    the largest such plane, as a share of the area
    sharp_mm        length of edges where the surface turns by more than 30 degrees
    sharp_per_area  sharp_mm divided by the square root of the area (does not grow with the part's size)
They say how much of a part is plates and corners. They do not say whether it looks good: that takes the picture.
A smoothed flat strap and a round bone can score alike, and faces the task requires to be flat count too.

`inside(tris, points)` says which points lie in the solid: the way to check that a clearance is clear and a boss is
solid. `--crop x0,y0,z0,x1,y1,z1` draws only the triangles inside a box, to look closely at one junction.

Run it under the cap for big meshes: python tools/pc/capped.py --mb 2048 -- python tools/solidworks/sheet.py part.stl
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

VIEWS = [  # name, direction the camera looks along, up
    ('front', (0, 1, 0), (0, 0, 1)), ('back', (0, -1, 0), (0, 0, 1)),
    ('left', (1, 0, 0), (0, 0, 1)), ('right', (-1, 0, 0), (0, 0, 1)),
    ('top', (0, 0, -1), (0, 1, 0)), ('bottom', (0, 0, 1), (0, 1, 0)),
    ('three-quarter', (0.62, 0.62, -0.48), (0, 0, 1)), ('three-quarter back', (-0.62, -0.62, -0.48), (0, 0, 1)),
]
LIGHTS = [((-0.45, -0.55, 0.70), 0.75), ((0.6, 0.2, 0.3), 0.25)]     # in camera axes: right, up, toward the camera
BG, INK = 250, 40


def read_stl(path):
    """(n, 3, 3) float array of triangle corners in the file's units. Binary or ASCII."""
    raw = Path(path).read_bytes()
    if len(raw) >= 84:
        n = struct.unpack('<I', raw[80:84])[0]
        if len(raw) == 84 + 50 * n:
            rec = np.frombuffer(raw, np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), n, 84)
            return rec['v'].astype(float)
    pts = [ln.split()[1:4] for ln in raw.decode('ascii', 'ignore').splitlines() if ln.strip().startswith('vertex')]
    if not pts or len(pts) % 3:
        raise SystemExit(f'{path}: not an STL this reader understands')
    return np.array(pts, float).reshape(-1, 3, 3)


def _normals(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    return n / np.maximum(2 * area, 1e-300)[:, None], area


def shape_stats(tris, sharp_deg=30.0, flat_min=0.01):
    """How much of the surface is flat plates and sharp edges. See the module docstring."""
    n, area = _normals(tris)
    ok = area > 1e-12
    tris, n, area = tris[ok], n[ok], area[ok]
    total = float(area.sum())
    # planes: same normal (to 0.5 degree) and same offset (to 0.02 mm)
    key = np.round(np.c_[n / 0.0087, np.einsum('ij,ij->i', n, tris[:, 0])[:, None] / 0.02]).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    plane_area = np.bincount(inv.ravel(), area)
    big = plane_area[plane_area >= flat_min * total]
    # edges shared by two triangles whose normals differ by more than sharp_deg
    v, vid = np.unique(np.round(tris.reshape(-1, 3), 4), axis=0, return_inverse=True)
    f = vid.reshape(-1, 3)
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    owner = np.tile(np.arange(len(f)), 3)
    order = np.lexsort((e[:, 1], e[:, 0]))
    e, owner = e[order], owner[order]
    pair = np.flatnonzero((e[1:] == e[:-1]).all(axis=1))
    cosang = np.einsum('ij,ij->i', n[owner[pair]], n[owner[pair + 1]])
    sharp = pair[cosang < np.cos(np.radians(sharp_deg))]
    sharp_mm = float(np.linalg.norm(v[e[sharp, 0]] - v[e[sharp, 1]], axis=1).sum())
    return dict(triangles=int(len(tris)), area_mm2=round(total, 1), flat_share=round(float(big.sum()) / total, 3),
                largest_flat=round(float(plane_area.max()) / total, 3), sharp_mm=round(sharp_mm, 1),
                sharp_per_area=round(sharp_mm / total ** 0.5, 2))


def inside(tris, points, chunk=200):
    """True for each point that lies in the solid the triangles enclose (a watertight STL). Needs numpy only.

    The check every clearance needs: is this cylinder, slot or passage really empty, is this boss really solid. Sample
    the region with points and ask. A ray goes up +Z from each point and counts the triangles it crosses; odd is inside.
    Points are nudged by a few nanometres so that a ray down an edge or through a vertex cannot be counted twice.
    Memory is chunk x triangles x 40 bytes: the default stays under 1 GB for 100,000 triangles. Do not use
    trimesh.contains on this machine: without an accelerator it breaks a 4 GB cap on 5,000 points (2026-11-13).
    """
    pts = np.asarray(points, float).reshape(-1, 3) + np.array([3.1e-6, 7.3e-6, 0.0])
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(det) > 1e-12                                   # triangles seen edge-on from above cannot be crossed
    a, b, c, det = a[ok], b[ok], c[ok], det[ok]
    lo, hi = np.minimum(np.minimum(a, b), c)[:, :2], np.maximum(np.maximum(a, b), c)[:, :2]
    out = np.zeros(len(pts), bool)
    for i in range(0, len(pts), chunk):
        q = pts[i:i + chunk]
        x, y = q[:, 0][:, None], q[:, 1][:, None]
        box = (x >= lo[:, 0]) & (x <= hi[:, 0]) & (y >= lo[:, 1]) & (y <= hi[:, 1])
        w0 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / det
        w1 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / det
        w2 = 1 - w0 - w1
        z = w0 * a[:, 2] + w1 * b[:, 2] + w2 * c[:, 2]
        hit = box & (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (z > q[:, 2][:, None])
        out[i:i + chunk] = hit.sum(axis=1) % 2 == 1
    return out


def _render(tris, look, up, px, scale, centre):
    """One orthographic view as a (px, px) uint8 image: depth buffer, two lights, outline and crease lines."""
    look = np.array(look, float) / np.linalg.norm(look)
    right = np.cross(look, up)
    right /= np.linalg.norm(right)
    upv = np.cross(right, look)
    rot = np.array([right, upv, -look])                        # camera axes: x right, y up, z toward the camera
    p = (tris - centre) @ rot.T
    n, _ = _normals(p)
    front = n[:, 2] > 1e-6
    p, n = p[front], n[front]
    shade = sum(w * np.clip(n @ (np.array(d) / np.linalg.norm(d)), 0, 1) for d, w in LIGHTS)
    shade = (70 + 165 * np.clip(0.15 + 0.85 * shade, 0, 1)).astype(np.uint8)
    xy = p[:, :, :2] * scale + px / 2
    xy[:, :, 1] = px - xy[:, :, 1]                             # image rows run downward
    img = np.full((px, px), BG, np.uint8)
    zbuf = np.full((px, px), -np.inf)
    nbuf = np.zeros((px, px, 3), np.float32)
    lo = np.clip(np.floor(xy.min(axis=1)).astype(int), 0, px - 1)
    hi = np.clip(np.ceil(xy.max(axis=1)).astype(int), 0, px - 1)
    for i in np.argsort(p[:, :, 2].mean(axis=1)):
        (x0, y0), (x1, y1) = lo[i], hi[i]
        a, b, c = xy[i]
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / det
        w1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / det
        w2 = 1 - w0 - w1
        z = w0 * p[i, 0, 2] + w1 * p[i, 1, 2] + w2 * p[i, 2, 2]
        zs = zbuf[y0:y1 + 1, x0:x1 + 1]
        hit = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9) & (z > zs)
        zs[hit] = z[hit]
        img[y0:y1 + 1, x0:x1 + 1][hit] = shade[i]
        nbuf[y0:y1 + 1, x0:x1 + 1][hit] = n[i]
    # lines: where the part ends, where depth jumps, where the surface turns sharply
    solid = np.isfinite(zbuf)
    z = np.where(solid, zbuf, 0.0)
    line = np.zeros_like(solid)
    for ax in (0, 1):
        s = solid != np.roll(solid, 1, ax)
        nz = np.maximum(np.minimum(nbuf[:, :, 2], np.roll(nbuf[:, :, 2], 1, ax)), 0.05)
        slope = np.sqrt(1 - nz ** 2) / nz                      # depth change per pixel the surface itself explains
        jump = (np.abs(z - np.roll(z, 1, ax)) * scale > 4 + 3 * slope) & solid & np.roll(solid, 1, ax)
        crease = (np.einsum('ijk,ijk->ij', nbuf, np.roll(nbuf, 1, ax)) < 0.87) & solid & np.roll(solid, 1, ax)
        line |= s | jump | crease
    line[0, :] = line[:, 0] = False
    img[line] = INK
    return img


FONT = {  # 3 x 5 dots, enough for labels
    'a': '010101111101101', 'b': '110101110101110', 'c': '011100100100011', 'e': '111100110100111',
    'f': '111100110100100', 'g': '011100101101011', 'h': '101101111101101', 'i': '111010010010111',
    'k': '101101110101101', 'l': '100100100100111', 'm': '101111101101101', 'n': '110101101101101',
    'o': '010101101101010', 'p': '110101110100100', 'q': '010101101011001', 'r': '110101110101101',
    't': '111010010010010', 'u': '101101101101111', '-': '000000111000000', ' ': '000000000000000',
}


def _label(img, text, x, y, k=3):
    for ch in text.lower():
        bits = FONT.get(ch, FONT['-'])
        for r in range(5):
            for c in range(3):
                if bits[r * 3 + c] == '1':
                    img[y + r * k:y + (r + 1) * k, x + c * k:x + (c + 1) * k] = INK
        x += 4 * k


def write_png(path, img):
    """Grey 8-bit PNG without any imaging library."""
    h, w = img.shape
    raw = b''.join(b'\x00' + img[r].tobytes() for r in range(h))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)

    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def sheet(paths, out, px=420, crop=None, together=False):
    """One row of eight views per STL, every tile at the same scale. Returns the shape numbers per file.

    together=True draws all the files as one scene (an assembly: each part exported in the model frame)."""
    parts = [read_stl(p) for p in paths]
    if together:
        parts, paths = [np.concatenate(parts)], ['+'.join(Path(p).stem for p in paths)]
    if crop is not None:
        lo, hi = np.array(crop[:3]), np.array(crop[3:])
        parts = [t[((t >= lo) & (t <= hi)).all(axis=(1, 2))] for t in parts]
    size = max(np.linalg.norm(t.reshape(-1, 3).max(0) - t.reshape(-1, 3).min(0)) for t in parts)
    scale = (px - 24) / size
    rows, stats = [], {}
    for path, tris in zip(paths, parts):
        pts = tris.reshape(-1, 3)
        centre = (pts.max(0) + pts.min(0)) / 2
        tiles = []
        for name, look, up in VIEWS:
            tile = _render(tris, look, up, px, scale, centre)
            _label(tile, name, 8, 8)
            tiles.append(tile)
        rows.append(np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:])]))
        stats[Path(path).name] = dict(shape_stats(tris), bbox_mm=np.round(pts.max(0) - pts.min(0), 2).tolist())
    img = np.vstack(rows)
    write_png(out, img)
    return stats


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('stl', nargs='+')
    ap.add_argument('-o', '--out')
    ap.add_argument('--px', type=int, default=420, help='tile size in pixels')
    ap.add_argument('--crop', help='x0,y0,z0,x1,y1,z1 in mm: draw only what lies inside this box')
    ap.add_argument('--together', action='store_true', help='draw all the files as one scene (an assembly)')
    a = ap.parse_args()
    out = a.out or str(Path(a.stl[0]).with_suffix('.sheet.png'))
    res = sheet(a.stl, out, a.px, [float(v) for v in a.crop.split(',')] if a.crop else None, a.together)
    print(json.dumps(res, indent=1))
    print('wrote', out, file=sys.stderr)
