"""Test rings for the 6808's seat in the fork rear (D_6808_FITS.md): the housing bore with its flat-topped teardrop and
its lip, printed as in the fork rear (bore axis horizontal, the teardrop's flat on top), in three sizes on one plate.
cadquery, no SolidWorks.

    python brg_coupon.py            the three rings as STEP and STL in cad/exports/fixtures (as printed: Z up)
    python brg_coupon.py slice      the same, then the plate sliced with the CLI (under capped.py)

Each ring: the housing bore (dia 51.9, 52.0 or 52.1; depth 6.9 mm as in the fork rear), the 45 deg teardrop cut flat 0.4 mm
above the bore, the lip behind the bearing (dia 48.0, 2 mm thick), a 3.5 mm wall and a square foot. Notches on the top
tell them apart: 1 = dia 51.9, 2 = dia 52.0 (the fork rear as adopted), 3 = dia 52.1.
"""
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

from dims import BRG_LIP_R, BRG_LIP_Z, HOUSE_Z0

REPO = Path(__file__).resolve().parents[3]
FX = REPO / 'cad' / 'exports' / 'fixtures'
WIP = REPO / 'cad' / '_wip'
SIZES = ((51.9, 1), (52.0, 2), (52.1, 3))
DEPTH = (HOUSE_Z0 + 1.0) - BRG_LIP_Z      # 6.9: the housing from its mouth to the lip, as in build_fork_rear
LIP_T, WALL = 2.0, 3.5


def ring(dia, notches):
    R = dia / 2.0
    ro = R + WALL
    t = R / math.sqrt(2.0)
    f = R * math.sqrt(2.0) - (R + 0.4)
    body = (cq.Workplane('XY').circle(ro).extrude(DEPTH + LIP_T)
            .union(cq.Workplane('XY').center(0, -ro / 2.0).rect(2 * ro, ro).extrude(DEPTH + LIP_T)))      # the square foot, below the bore
    bore = (cq.Workplane('XY').circle(R).extrude(DEPTH)
            .union(cq.Workplane('XY').polyline([(-t, t), (-f, R + 0.4), (f, R + 0.4), (t, t), (0, 0)]).close().extrude(DEPTH)))
    body = body.cut(bore).cut(cq.Workplane('XY').circle(BRG_LIP_R).extrude(DEPTH + LIP_T))
    for i in range(notches):      # marks on the top: 1.2 wide, 1.0 deep, across the whole thickness
        x = (i - (notches - 1) / 2.0) * 4.0
        body = body.cut(cq.Workplane('XY').rect(1.2, 2.0).extrude(DEPTH + LIP_T).translate((x, ro, 0)))
    # as printed: the coupon's Y (up in the fork rear's print) becomes Z, foot on Z 0
    return body.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 0, ro))


def names():
    return [f'fixtures_brg_seat_coupon_d{int(round(d * 10))}' for d, _ in SIZES]


def build():
    FX.mkdir(parents=True, exist_ok=True)
    for (d, n), nm in zip(SIZES, names()):
        r = ring(d, n)
        cq.exporters.export(r, str(FX / f'{nm}.STL'), tolerance=0.005, angularTolerance=0.05)
        cq.exporters.export(r, str(FX / f'{nm}.STEP'))
        m = trimesh.load(str(FX / f'{nm}.STL'))
        print(f'{nm}: {m.volume:.0f} mm3, {m.volume * 1.27e-3:.1f} g PETG, size {m.extents.round(2).tolist()}, watertight {m.is_watertight}', flush=True)


def slice_plate():
    sys.path.insert(0, r'J:/code/roark-wt/left-arm-organic/cad/scripts/arm')
    import organic_print as P      # read-only use of the arm thread's slicing helper and seed project (Generic PETG, P2S)
    out = WIP / 'shoulder-pass1' / 'slice' / 'brg_coupon'
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    ms, x = [], 0.0
    for nm in names():
        m = trimesh.load(str(FX / f'{nm}.STL'))
        m.apply_translation(-m.bounds[0] + np.array([x, 0.0, 0.0]))
        ms.append(m)
        x += m.extents[0] + 8.0
    part = trimesh.util.concatenate(ms)
    extra = {'enable_support': '0', 'brim_type': 'outer_only', 'brim_width': '5', 'wall_loops': '4', 'sparse_infill_density': '25%'}
    src, size = P.project('brg_seat_coupon', part, [], extra, out)
    final = 'fixtures_brg_seat_coupon.3mf'
    args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3000, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(exit=r.returncode, size_mm=[round(float(v), 1) for v in size])
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        cur = json.loads(z.read('Metadata/project_settings.config'))
        res['settings'] = {k: cur.get(k) for k in ('layer_height', 'wall_loops', 'sparse_infill_density', 'enable_support', 'brim_type', 'brim_width', 'filament_settings_id',
                                                   'filament_type', 'printer_settings_id', 'print_settings_id', 'curr_bed_type')}
        g = [n_ for n_ in z.namelist() if n_.endswith('.gcode')]
        gc = z.read(g[0]).decode(errors='replace') if g else ''
        res['support_lines'] = len(re.findall(r'^; FEATURE: Support', gc, flags=re.M))
        d = WIP / 'prints' / 'shoulder' / 'fixtures'
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, d / final)
        res['out'] = str(d / final)
    print(json.dumps(res), flush=True)


if __name__ == '__main__':
    build()
    if 'slice' in sys.argv[1:]:
        slice_plate()
