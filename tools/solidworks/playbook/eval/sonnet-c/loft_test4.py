import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
import trimesh
f = PchipInterpolator(-np.array([k[0] for k in KEYS_A], float), np.array([k[1:] for k in KEYS_A], float))
def mk(zs): return [(z,) + tuple(float(v) for v in f(-z)) for z in zs]
def lofts(j, name, groups):
    d = new_part(j.sw, WIP / f'{name}.SLDPRT')
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 33.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID)
    n = 0
    for g, secs in enumerate(groups):
        sks = []
        for (z, a, y0, y1, nn) in secs:
            with Sk(d, plane(d, 'Z', z, f'P{n}'), f'S{n}') as s:
                s.spline(sect(a, y0, y1, nn, z))
            sks.append(s.feat); n += 1
        loft(d, sks, f'L{g}')
    export(j.sw, d, WIP / f'{name}.stl'); save(d); close(j.sw, d)
    m = trimesh.load(WIP / f'{name}.stl')
    out = []
    for z in range(-30, -212, -8):
        s = m.section(plane_origin=[0, 0, z + 0.3], plane_normal=[0, 0, 1])
        out.append((z, None if s is None else round(float(np.ptp(s.vertices[:, 0])), 1)))
    print(name, 'vol', round(m.volume), out, flush=True)
with job() as j:
    lofts(j, 'v1', [mk([-17, -25, -37, -52, -75, -105]), mk([-105, -132, -155, -176, -200, -213])])
