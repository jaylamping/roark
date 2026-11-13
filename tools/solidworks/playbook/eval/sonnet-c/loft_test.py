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
    for z in range(-30, -212, -10):
        s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        out.append((z, None if s is None else round(float(np.ptp(s.vertices[:, 0])), 1)))
    print(name, 'vol', round(m.volume), out, flush=True)
if __name__ == '__main__':
    with job() as j:
        run(j, 't_dense', A)
