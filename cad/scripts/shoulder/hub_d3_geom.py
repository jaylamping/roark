"""Rev D3 lug geometry report: fillet extents (from the STEP) and the flat shim area on each lug Z face (from the STL).
python hub_d3_geom.py STEP STL"""
import math
import re
import sys

import numpy as np
import trimesh

RX, YZ, IN = 170.49, 5.99, 25.4


def step_faces(path):
    s = open(path, encoding='latin1').read()
    ents = {int(k): v for k, v in re.findall(r'#(\d+)\s*=\s*(.*?)\s*;\s*(?=#\d+\s*=|ENDSEC)', s, re.S)}
    refs = lambda i: [int(x) for x in re.findall(r'#(\d+)', ents[i])]

    def coords(i):
        return [float(x) for x in re.search(r'\(\s*([-\d.E+]+\s*,\s*[-\d.E+]+\s*,\s*[-\d.E+]+)\s*\)', ents[i]).group(1).split(',')]

    def verts(face):
        out, st, seen = [], [face], set()
        while st:
            i = st.pop()
            if i in seen:
                continue
            seen.add(i)
            e = ents[i]
            if e.startswith('CARTESIAN_POINT') and i != face:
                out.append([c * IN for c in coords(i)])
                continue
            if e.startswith(('ADVANCED_FACE', 'FACE_OUTER_BOUND', 'FACE_BOUND', 'EDGE_LOOP', 'ORIENTED_EDGE', 'EDGE_CURVE', 'VERTEX_POINT')):
                r = refs(i)
                if e.startswith('ADVANCED_FACE'):
                    r = r[:-1]
                if e.startswith('EDGE_CURVE'):
                    r = r[:2]
                st += r
        return out
    for k, e in sorted(ents.items()):
        if not e.startswith('ADVANCED_FACE'):
            continue
        se = ents[refs(k)[-1]]
        m = re.match(r"(CYLINDRICAL_SURFACE|TOROIDAL_SURFACE)\s*\(\s*'[^']*'\s*,\s*#\d+\s*,\s*([-\d.E+]+)(?:\s*,\s*([-\d.E+]+))?", se)
        if not m:
            continue
        rad = float(m.group(3) or m.group(2)) * IN
        yield k, m.group(1)[:3], rad, verts(k)


step, stl = sys.argv[1], sys.argv[2]
print('fillets on the lugs (X offset from the yaw axis, Y, Z - YZ, r):')
for k, t, rad, P in step_faces(step):
    if not P or rad > 1.25:
        continue
    P = np.array(P)
    if P[:, 1].max() > 298.5 or P[:, 1].min() < 287.5 or np.abs(P[:, 2] - YZ).max() > 7.0:
        continue
    xo = np.abs(P[:, 0] - RX)
    if xo.min() < 18.0:
        continue
    r = np.hypot(P[:, 0] - RX, P[:, 2] - YZ)
    side = '-X' if P[:, 0].mean() < RX else '+X'
    print(f'  {side} {t} R{rad:.2f}: X offset {xo.min():.2f}..{xo.max():.2f}  Y {P[:,1].min():.2f}..{P[:,1].max():.2f}'
          f'  Z-YZ {(P[:,2]-YZ).min():+.2f}..{(P[:,2]-YZ).max():+.2f}  r {r.min():.2f}..{r.max():.2f}')

m = trimesh.load(stl)
c = m.triangles_center
n = m.face_normals
a = m.area_faces
print('flat Z faces of the lugs (plane Z 1.0 / 11.0):')
for side, sx in (('-X', -1), ('+X', 1)):
    for zp in (1.0, 11.0):
        k = (np.abs(c[:, 2] - zp) < 0.01) & (np.abs(np.abs(n[:, 2]) - 1) < 1e-4) & (np.sign(c[:, 0] - RX) == sx) & (np.abs(c[:, 0] - RX) > 17)
        v = m.triangles[k].reshape(-1, 3)
        xo = np.abs(v[:, 0] - RX)
        print(f'  {side} lug, Z {zp:4.1f} face: flat area {a[k].sum():6.1f} mm2  X offset {xo.min():.2f}..{xo.max():.2f}  Y {v[:,1].min():.2f}..{v[:,1].max():.2f}'
              f'  (below Y 294.8: {a[k & (c[:,1] < 294.8)].sum():.1f} mm2; above: {a[k & (c[:,1] >= 294.8)].sum():.1f})')
