"""R1f lug shim plates (2026-11-12, WIP for hub rev D3): flat printed PETG plates on the extended lugs' Z faces, picked by trial
at assembly after the ring (zero yaw play). One shape fits all four places: flipped over it serves the other face of a lug and
the other lug (both mirror images). Outline in the lug's own face (offset from the yaw axis, Y):
  - the flat face below the hub's R1.2 Z root (Y 288.2-294.6), offset 18.9 out to the lug's outer edge less 0.2
    (34.2), the main flat face only (no strip above Y 294.6), per the D3 hub as built;
  - a Dia 4.4 hole for the lug bolt (offset 23.0, Y 292.0); the 0.2 chamfer is left out (one or two layers on these plates);
  - a lip: a 0.8 wide x 1.2 high rib along the bottom edge (Y 287.2-288.0, on the printed top face) that hooks under the lug's
    free end (Y 288), so the plate stays put while the half closes.
Thickness t marked on the inner edge: narrow notch = 0.05, wide notch = 0.25, counted from t = 0.25 (0.25 has none).
Plates (thickness = first layer + whole 0.10 layers), two of each size:
  A: first layer 0.25 -> 0.25 0.35 0.45 0.55 0.65 0.75
  B: first layer 0.20 -> 0.30 0.40 0.50 0.60 0.70
Sliced with the arm halves' seed project; only the layer heights, 100 % infill, no support and no brim changed.
    python lug_shim_print.py [A B]        (from cad/scripts/arm; under capped.py). Re-run when the D3 hub geometry is final."""
import json
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
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
import organic_print as P

PLATES = {'A': (0.25, [0.25, 0.35, 0.45, 0.55, 0.65, 0.75] * 2), 'B': (0.20, [0.30, 0.40, 0.50, 0.60, 0.70] * 2)}
OUT = Path(os.environ.get('LUG_SHIM_OUT', P.REPO / 'cad' / '_wip' / 'r1f_lug_shims'))
Y0 = 288.0      # local origin: offset 0 at the yaw axis, Y at the lug's free end


def outline(t):
    # D3 (coordinator 01:35Z): flat face X 18.76-34.4 over Y 288-294.8 (R1.2 root above), the strip X 35.45-36.35 flat over
    # Y 294.5-296.7; 0.2 in from every edge
    main = box(18.96, 288.2, 34.2, 294.6)
    # (2026-11-13, coordinator: no strip; the plate covers the main flat face only, so the lug's step and column above Y 294.6
    # sit in the 0.5 gap and carry nothing, and no plate edge lands on our corner at the root relief)
    lip_strip = box(18.96, 287.2, 34.2, 288.2)
    p = unary_union([main, lip_strip]).difference(Point(23.0, 292.0).buffer(2.2, 64))      # Dia 4.4 (2026-11-13): the plate edge 0.5 off the hub lug's Dia 3.4 hole rim, 0.2 off our insert's Dia 4.0
    k = int(round((t - 0.25) / 0.05))
    wide, narrow = divmod(k, 5)
    y = 293.9
    for w in [1.4] * wide + [0.5] * narrow:      # notches in the inner edge (offset 18.9), top down
        p = p.difference(box(18.86, y - w, 19.26, y))
        y -= w + 0.6
    lip = box(19.5, 287.2, 33.7, 288.0)      # rib on the printed top face
    return p, lip, (wide, narrow)


def plate_mesh(ts):
    meshes, spots = [], []
    for i, t in enumerate(ts):
        cx, cy = (i % 4) * 22.0, (i // 4) * 15.0
        p, lip, code = outline(t)
        polys = list(p.geoms) if p.geom_type == 'MultiPolygon' else [p]
        for pg in polys:
            m = trimesh.creation.extrude_polygon(pg, t)
            m.apply_translation((cx - 18.9, cy - 287.2, 0))
            meshes.append(m)
        r = trimesh.creation.extrude_polygon(lip, 1.2)
        r.apply_translation((cx - 18.9, cy - 287.2, t))
        meshes.append(r)
        spots.append(dict(t=t, notches_wide_narrow=code, at=[cx, cy]))
    part = trimesh.util.concatenate(meshes)
    part.apply_translation(-np.r_[part.bounds[0, :2], 0.0] - np.r_[(part.bounds[1, :2] - part.bounds[0, :2]) / 2, 0.0])
    return part, spots


def run(name):
    first, ts = PLATES[name]
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    part, spots = plate_mesh(ts)
    part.apply_translation((0, 0, -part.bounds[0, 2]))
    part.export(out / f'lug_shims_{name}.stl')
    extra = {'layer_height': '0.1', 'initial_layer_print_height': f'{first:.2f}', 'sparse_infill_density': '100%',
             'enable_support': '0', 'brim_type': 'no_brim'}
    src, size = P.project(f'lug_shims_{name}', part, [], extra, out)
    final = f'r1f_lug_shims_{name}.3mf'
    args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(plate=name, first_layer=first, layer=0.10, plates=spots, exit=r.returncode, size_mm=[round(float(v), 1) for v in size])
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        g = [n for n in z.namelist() if n.endswith('.gcode')]
        if g:
            (out / f'r1f_lug_shims_{name}.gcode').write_bytes(z.read(g[0]))
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:900], flush=True)


if __name__ == '__main__':
    for n in sys.argv[1:] or PLATES:
        run(n)
