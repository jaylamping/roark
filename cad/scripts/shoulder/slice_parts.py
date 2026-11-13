"""Slice the shoulder parts with the Bambu Studio CLI to read print time, mass with support, and warnings.

    python slice_parts.py [part ...]        (under capped.py; results in cad/_wip/shoulder-pass1/slice/<part>/result.json)

Uses the arm thread's slicing helper and seed project read-only (left-arm-organic cad/scripts/arm/organic_print.py: the
accepted upper-arm PETG project: 0.20 mm, 6 walls, tree supports on, brim 5), so the numbers are comparable with the arm's.
Orientations are the ones in PRINT_NOTES.md. A first look only: no print file is kept as a release.
"""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, r'J:/code/roark-wt/left-arm-organic/cad/scripts/arm')
import organic_print as P  # noqa: E402  (read-only use)

from swk import WIP  # noqa: E402

OUT = WIP / 'slice'
RIG = WIP.parent / 'yaw-loop-rig'
X90 = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)      # Y up -> Z up
ORIENT = {      # rotation taking the robot's frame to the bed's (rows = bed x, y, z)
    'drum': np.diag([1.0, -1.0, -1.0]),                 # front lip (+Z) down
    'cap': np.diag([1.0, -1.0, -1.0]),                  # front face down
    'ring': np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float),   # flat: X along the bed's normal
    'fork_front': np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),    # upright, Y up
    'fork_rear': np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),
    'hub': np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float),    # RS02 face (high Y) down
    'cover': np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float),  # back wall (low X) down
}
FILES = {k: WIP / 'stl' / f'{k}.STL' for k in ORIENT}
FILES['fork_front'] = WIP / 'stl' / 'fork_front.stl'
for k in ('fork', 'hub', 'boss', 'cap'):
    FILES[f'rig_{k}'] = RIG / f'fixtures_yaw_loop_rig_{k}.stl'


def run(name):
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    m = trimesh.load(FILES[name])
    if name in ORIENT:
        m = trimesh.Trimesh(m.vertices @ ORIENT[name].T, m.faces, process=False)
    m.apply_translation((0, 0, -m.bounds[0, 2]))
    src, size = P.project(name, m, [], {}, out)
    final = f'{name}.3mf'
    args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3000, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(name=name, exit=r.returncode, size_mm=[round(float(v), 1) for v in size], volume_g_petg=round(float(m.volume) * 1.27e-3, 1))
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        g = [n for n in z.namelist() if n.endswith('.gcode')]
        if g:
            txt = z.read(g[0]).decode(errors='replace')
            feat = {}
            for mt in re.finditer(r'^; FEATURE: (.+)$', txt, re.M):
                feat[mt.group(1).strip()] = feat.get(mt.group(1).strip(), 0) + 1
            res['feature_blocks'] = feat
            for key in ('total filament weight', 'total filament length', 'model printing time', 'total estimated time'):
                mt = re.search(rf'^; {key}[^:\n]*: (.+)$', txt, re.M)
                if mt:
                    res[key] = mt.group(1).strip()
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:900], flush=True)


if __name__ == '__main__':
    for n in sys.argv[1:] or list(FILES):
        try:
            run(n)
        except Exception as e:      # one failed part must not stop the rest
            print(name := n, 'FAILED', repr(e)[:300], flush=True)
