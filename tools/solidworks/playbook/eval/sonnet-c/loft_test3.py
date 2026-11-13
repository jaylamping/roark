import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
import trimesh
def run(j, name, secs):
    d = base(j, WIP / f'{name}.SLDPRT', secs)
    export(j.sw, d, WIP / f'{name}.stl'); save(d); close(j.sw, d)
    m = trimesh.load(WIP / f'{name}.stl')
    out = []
    for z in range(-30, -212, -8):
        s = m.section(plane_origin=[0, 0, z + 0.3], plane_normal=[0, 0, 1])
        out.append((z, None if s is None else round(float(np.ptp(s.vertices[:, 0])), 1)))
    print(name, out, flush=True)
f = PchipInterpolator(-np.array([k[0] for k in KEYS_A], float), np.array([k[1:] for k in KEYS_A], float))
def mk(zs): return [(z,) + tuple(float(v) for v in f(-z)) for z in zs]
with job() as j:
    run(j, 'u1', mk([-17, -25, -37, -60, -100, -130, -150, -165, -182, -200, -212]))
    run(j, 'u2', mk([-17, -25, -37, -49, -61, -73, -85, -97, -109, -121, -133, -145, -157, -169, -181, -193, -205, -213]))
