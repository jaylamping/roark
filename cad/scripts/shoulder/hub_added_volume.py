"""Added (and removed) material between two hub meshes, by Y-plane sections one at a time (light: 2D polygon differences).
python hub_added_volume.py NEW.STL OLD.STL [y0 y1 step]. Prints, per band, the r / theta / X / Z / Y ranges and the area-sum volume."""
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

RX, YZ = 170.49, 5.99


def section(m, y):
    s = m.section(plane_origin=(0, y, 0), plane_normal=(0, 1, 0))
    if s is None:
        return None
    polys = []
    for path in s.discrete:          # closed loops in 3D: take (x, z)
        pts = np.asarray(path)[:, [0, 2]]
        if len(pts) >= 3:
            polys.append(Polygon(pts).buffer(0))
    if not polys:
        return None
    # even-odd fill: symmetric difference of all loops
    u = polys[0]
    for p in polys[1:]:
        u = u.symmetric_difference(p)
    return u


new, old = trimesh.load(sys.argv[1]), trimesh.load(sys.argv[2])
y0, y1, dy = (float(v) for v in sys.argv[3:6]) if len(sys.argv) > 5 else (286.0, 314.0, 0.2)
bands = {}
for y in np.arange(y0 + dy / 2, y1, dy):
    a, b = section(new, y), section(old, y)
    if a is None:
        continue
    for sign, diff in (('added', a.difference(b) if b is not None else a), ('removed', b.difference(a) if b is not None else None)):
        if diff is None or diff.is_empty or diff.area < 0.02:
            continue
        geoms = getattr(diff, 'geoms', [diff])
        for g in geoms:
            if g.area < 0.02:
                continue
            xs, zs = np.asarray(g.exterior.coords).T
            r = np.hypot(xs - RX, zs - YZ)
            th = np.degrees(np.arctan2(zs - YZ, xs - RX)) % 360
            key = (sign, 'below Y 296' if y < 296 else 'above Y 296', '-X side' if np.mean(xs) < RX else '+X side')
            b_ = bands.setdefault(key, dict(vol=0.0, r=[1e9, -1e9], th=[], x=[1e9, -1e9], z=[1e9, -1e9], y=[1e9, -1e9]))
            b_['vol'] += g.area * dy
            b_['r'] = [min(b_['r'][0], r.min()), max(b_['r'][1], r.max())]
            b_['th'] += [th.min(), th.max()]
            b_['x'] = [min(b_['x'][0], xs.min()), max(b_['x'][1], xs.max())]
            b_['z'] = [min(b_['z'][0], zs.min()), max(b_['z'][1], zs.max())]
            b_['y'] = [min(b_['y'][0], y - dy / 2), max(b_['y'][1], y + dy / 2)]
for k, b_ in sorted(bands.items()):
    th = np.array(b_['th'])
    print(f"{' / '.join(k):34s} vol {b_['vol']:7.0f} mm3  r {b_['r'][0]:.2f}..{b_['r'][1]:.2f}  theta {th.min():.1f}..{th.max():.1f}"
          f"  Y {b_['y'][0]:.1f}..{b_['y'][1]:.1f}  X {b_['x'][0]:.2f}..{b_['x'][1]:.2f}  Z {b_['z'][0]:.2f}..{b_['z'][1]:.2f}"
          f" (Z-YZ {b_['z'][0] - YZ:+.2f}..{b_['z'][1] - YZ:+.2f})")
