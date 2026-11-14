"""Print plates (Bambu Studio 3MF) for the cable crossing rigs: each rig's parts arranged on one P2S plate, supports off,
no brim, 3 walls, 15 % infill, sliced with the CLI. Writes cad/_wip/cable-rigs/plates/fixtures_cable_rig_<rig>.3mf (the sliced
project) and a result line with time and mass.

    python rig_plates.py [roll yaw pitch_tray pitch_lid]        (under capped.py)

Uses the arm thread's slicing helper and seed project read-only (as slice_parts.py); the seed's PETG filament is replaced
by the Bambu PLA Basic preset for the P2S. The plate type stays the seed's (Supertack): change it if another plate is on.
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

from swk import CAD, WIP  # noqa: E402

FX = CAD / 'exports' / 'fixtures'
OUTD = WIP.parent / 'cable-rigs' / 'plates'      # scratch: a 3MF under cad/prints/ needs a pre-print gate report (part-lifecycle.md)
WORK = WIP / 'slice' / 'plates'
PLATES = {
    'roll': ['fixtures_cable_rig_roll_deck_tray', 'fixtures_cable_rig_roll_deck_lid', 'fixtures_cable_rig_roll_axis_base', 'fixtures_cable_rig_roll_axis_top'],
    # placed by hand (name, x, y, quarter turns): the two fork parts turned a quarter, the hub, bosses and cap in a second row
    'yaw': [('fixtures_cable_rig_yaw2_fork', 0, 0, 1), ('fixtures_cable_rig_yaw2_fork_7', 106, 0, 1), ('fixtures_cable_rig_yaw2_hub', 0, 92, 0),
            ('fixtures_cable_rig_yaw2_boss', 85, 92, 0), ('fixtures_cable_rig_yaw2_boss_7', 138, 92, 0), ('fixtures_cable_rig_yaw2_cap', 191, 92, 0)],
    'pitch_tray': ['fixtures_cable_rig_pitch_tray'],
    'pitch_lid': ['fixtures_cable_rig_pitch_lid'],
    'pitch_tray_r75': ['fixtures_cable_rig_pitch_tray_r75'],
    'pitch_lid_r75': ['fixtures_cable_rig_pitch_lid_r75'],
}
EXTRA = {'enable_support': '0', 'brim_type': 'no_brim', 'wall_loops': '3', 'sparse_infill_density': '15%'}
PLA = 'Bambu PLA Basic @BBL P2S'


def pla_settings(ps):
    """The PLA preset's values for every filament key the seed project carries (the seed is PETG)."""
    pre = P.system_preset('filament', PLA)
    if not pre:
        raise SystemExit(f'filament preset {PLA} not found under {P.SYS}')
    meta = {'name', 'from', 'inherits', 'type', 'instantiation', 'setting_id', 'include', 'compatible_printers', 'compatible_printers_condition', 'version',
            'filament_settings_id', 'compatible_prints', 'compatible_prints_condition'}
    out = {}
    for k, v in pre.items():
        if k in meta or k not in ps or k == 'filament_extruder_variant':
            continue
        # Every list must keep the length the seed project has for that key (one entry per nozzle variant, or per filament):
        # the preset file carries 1 or 3 where the project carries 2, and the GUI then refuses the file ("Invalid
        # configuration file") although the command-line slicer accepts it.
        if isinstance(v, list) and isinstance(ps[k], list) and len(v) != len(ps[k]):
            v = (v + [v[-1]] * len(ps[k]))[:len(ps[k])]
        out[k] = v
    out['filament_settings_id'] = [PLA]
    return out
GAP = 6.0


def arrange(names):
    """Rows of parts, largest first, 6 mm apart, centred; every part sits on Z 0."""
    if names and isinstance(names[0], tuple):
        out = []
        for n, x, y, q in names:
            m = trimesh.load(FX / f'{n}.STL')
            if q:
                m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2 * q, (0, 0, 1)))
            m.apply_translation(-m.bounds[0] + np.array([x, y, 0.0]))
            out.append(m)
        return trimesh.util.concatenate(out)
    ms = []
    for n in names:
        m = trimesh.load(FX / f'{n}.STL')
        m.apply_translation(-np.r_[m.bounds[0, :2], m.bounds[0, 2]])
        ms.append(m)
    ms.sort(key=lambda m: -m.extents[1])
    x = y = row_h = 0.0
    placed = []
    for m in ms:
        w, h = m.extents[0], m.extents[1]
        if x > 0 and x + w > 236.0:
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        m.apply_translation((x, y, 0))
        placed.append(m)
        x += w + GAP
        row_h = max(row_h, h)
    return trimesh.util.concatenate(placed)


def run(name):
    out = WORK / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    part = arrange(PLATES[name])
    seed = json.loads(zipfile.ZipFile(P.SEED).read('Metadata/project_settings.config'))
    extra = dict(pla_settings(seed), **EXTRA)
    src, size = P.project(f'cable_rig_{name}', part, [], extra, out)
    final = f'fixtures_cable_rig_{name}.3mf'
    args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3000, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(plate=name, parts=[q if isinstance(q, str) else q[0] for q in PLATES[name]], exit=r.returncode, size_mm=[round(float(v), 1) for v in size])
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        cur = json.loads(z.read('Metadata/project_settings.config'))
        res['settings'] = {k: cur.get(k) for k in ('layer_height', 'wall_loops', 'sparse_infill_density', 'enable_support', 'brim_type', 'filament_settings_id', 'filament_type',
                                                   'nozzle_temperature', 'supertack_plate_temp', 'printer_settings_id', 'print_settings_id', 'curr_bed_type')}
        res['flagged'] = cur.get('different_settings_to_system')
        g = [n_ for n_ in z.namelist() if n_.endswith('.gcode')]
        res['gcode'] = bool(g)
        OUTD.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, OUTD / final)
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res), flush=True)


if __name__ == '__main__':
    for n in sys.argv[1:] or list(PLATES):
        run(n)
