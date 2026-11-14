"""Shared by the fable-d benchmark scripts: paths, STL helpers for stand-ins and merged pictures, STL checks."""
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
WIP = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-d'
PICS = HERE / 'pictures'
WIP.mkdir(parents=True, exist_ok=True)
PICS.mkdir(parents=True, exist_ok=True)


def box_tris(lo, hi):
    """12 triangles of an axis-aligned box, normals outward."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (2, 3, 7), (2, 7, 6), (1, 2, 6), (1, 6, 5), (3, 0, 4), (3, 4, 7)]
    return v[np.array(f)]


def write_stl(path, tris):
    tris = np.asarray(tris, float)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-300)[:, None]
    rec = np.zeros(len(tris), np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    rec['n'], rec['v'] = n, tris
    Path(path).write_bytes(b'\0' * 80 + struct.pack('<I', len(tris)) + rec.tobytes())


def merge_stl(out, *parts):
    """One STL from several STL paths or triangle arrays (for a picture of an assembly; the shells stay separate)."""
    import sheet
    arrs = [sheet.read_stl(p) if isinstance(p, (str, Path)) else np.asarray(p, float) for p in parts]
    write_stl(out, np.concatenate(arrs))


def stl_check(path, want_volume, want_box, tol=0.005):
    """Watertight, one shell, volume and box against the part (04-export.md). Returns a dict; raises nothing."""
    import trimesh
    mesh = trimesh.load(str(path))
    b = mesh.bounds
    return dict(watertight=bool(mesh.is_watertight), shells=len(mesh.split()), volume=round(float(mesh.volume), 2),
                volume_ok=bool(abs(mesh.volume - want_volume) <= tol * want_volume),
                box=[round(float(v), 3) for v in list(b[0]) + list(b[1])],
                box_ok=bool(np.allclose(list(b[0]) + list(b[1]), want_box, atol=0.02)))
