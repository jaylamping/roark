"""R1e shim rings (2026-11-12): the printed PETG rings that go between the arm's lowered end face and the hub disc, picked by trial
at assembly. Ring r 36.2-38.4 (inside the rev D disc's flat, r 36.05-38.6; 0.6 inside our skin). Thickness marked by N notches
in the inner edge, N = (t - 0.25) / 0.05 (1 = 0.30 ... 17 = 1.10); notches 0.5 wide x 0.3 deep, 4 deg apart, from theta 0.
Rings of 0.35 and thinner get three break-off tabs to a skirt so peeling them off the plate doesn't stretch them.
Plates (each thickness = first layer + whole 0.10 layers):
  A: first layer 0.20 -> 0.30 0.40 ... 1.10 (9 rings)
  B: first layer 0.15 -> 0.35 0.45 ... 1.05 + a spare 0.65 (9 rings)
  C: first layer 0.20 -> spares 0.50 0.60 0.70 0.80 (4 rings)
Sliced with the arm halves' seed project (SuperTack, PETG), only the layer heights, 100 % infill, no support and no brim changed.
    python shim_print.py [A B C]        (from cad/scripts/arm; under capped.py)"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
import organic_print as P

R_IN, R_OUT = 36.2, 38.4
PLATES = {'A': (0.20, [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10]),
          'B': (0.15, [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.05, 0.65]),
          'C': (0.20, [0.50, 0.60, 0.70, 0.80])}
OUT = Path(os.environ.get('SHIM_OUT', P.REPO / 'cad' / '_wip' / 'r1e_shims'))


def ring_outline(t):
    ring = Point(0, 0).buffer(R_OUT, 256).difference(Point(0, 0).buffer(R_IN, 256))
    n = int(round((t - 0.25) / 0.05))
    for k in range(n):      # notches in the inner edge
        a = math.radians(4.0 * k)
        nb = box(R_IN - 0.1, -0.25, R_IN + 0.3, 0.25)
        ring = ring.difference(rotate(nb, math.degrees(a), origin=(0, 0)))
    if t <= 0.351:          # break-off tabs to a skirt (thin rings)
        skirt = Point(0, 0).buffer(39.6, 256).difference(Point(0, 0).buffer(39.0, 256))
        tabs = [rotate(box(R_OUT - 0.2, -0.4, 39.1, 0.4), a, origin=(0, 0)) for a in (90.0, 210.0, 330.0)]
        ring = unary_union([ring, skirt] + tabs)
    return ring, n


def plate_mesh(thicknesses):
    meshes, spots = [], []
    pitch = 80.0
    for i, t in enumerate(thicknesses):
        cx, cy = (i % 3 - 1) * pitch, (i // 3 - 1) * pitch
        poly, n = ring_outline(t)
        polys = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
        for pg in polys:
            m = trimesh.creation.extrude_polygon(pg, t)
            m.apply_translation((cx, cy, 0))
            meshes.append(m)
        spots.append(dict(t=t, notches=n, centre=[cx, cy]))
    return trimesh.util.concatenate(meshes), spots


def run(name):
    first, ts = PLATES[name]
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    part, spots = plate_mesh(ts)
    part.apply_translation((0, 0, -part.bounds[0, 2]))
    part.export(out / f'shims_{name}.stl')
    extra = {'layer_height': '0.1', 'initial_layer_print_height': f'{first:.2f}', 'sparse_infill_density': '100%',
             'enable_support': '0', 'brim_type': 'no_brim'}
    src, size = P.project(f'shims_{name}', part, [], extra, out)
    final = f'r1e_shims_{name}.3mf'
    args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(plate=name, first_layer=first, layer=0.10, rings=spots, exit=r.returncode, size_mm=[round(float(v), 1) for v in size])
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        cur = json.loads(z.read('Metadata/project_settings.config'))
        res['layer_settings'] = {k: cur.get(k) for k in ('layer_height', 'initial_layer_print_height', 'sparse_infill_density', 'enable_support', 'brim_type', 'curr_bed_type', 'elephant_foot_compensation')}
        g = [n for n in z.namelist() if n.endswith('.gcode')]
        if g:
            (out / f'r1e_shims_{name}.gcode').write_bytes(z.read(g[0]))
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:1200], flush=True)


if __name__ == '__main__':
    for n in sys.argv[1:] or PLATES:
        run(n)
