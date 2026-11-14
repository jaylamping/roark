"""Print plate (Bambu Studio 3MF, sliced with the CLI) for the hub, for the P2S in PETG.

    python hub_plate.py [HUB.STL]        (under capped.py; default: the rev D3c7 candidate export)

Orientation: RS02 face (Y 319.86) on the bed, yaw axis vertical, spigot and lugs growing up. Layers are normal to the yaw
axis everywhere. The seed project (the arm's upper-arm plate: Generic PETG @BBL P2S, 0.20 mm, 6 walls, tree hybrid
supports, Supertack plate) is kept except for what EXTRA lists. Support blockers keep supports off the groove's flanks and
the lugs. Output: cad/_wip/shoulder-hub/plate/shoulder_hub_left_revD3c7.3mf, a result line, the plate picture, and a check
that every list in the project's settings has the seed's length (the fault that made Bambu Studio refuse the rig plates).

Uses the arm thread's slicing helper and seed project read-only (as rig_plates.py).
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

from dims import RX, YZ  # noqa: E402
from swk import CAD, WIP  # noqa: E402

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else CAD / 'exports' / 'shoulder' / 'shoulder_hub_left_revD3c7_candidate.STL'
OUT = WIP.parent / 'shoulder-hub' / 'plate'
NAME = 'shoulder_hub_left_revD3c7'
R = np.eye(4)
R[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]            # model Y (toward the RS02) becomes bed -Z: RS02 face down
# what differs from the seed project (each one is flagged in the 3MF and listed in PRINT_NOTES.md)
EXTRA = {'sparse_infill_density': '100%',      # the strength checks and the mass (80 g) are for solid PETG; the part is small
         'brim_type': 'no_brim'}               # the foot is a flat dia 50 ring face; a brim would have to be trimmed off the face the RS02 seats on


def groove_blocker():
    a = trimesh.creation.annulus(r_min=32.5, r_max=41.5, height=6.4, sections=96)      # round the groove, Y 296.4-302.8
    a.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))    # its axis along model Y
    a.apply_translation((RX, 299.6, YZ))
    return a


def lug_blockers():
    out = []
    for sg in (-1, 1):
        b = trimesh.creation.box(extents=(20.0, 10.5, 12.0))
        b.apply_translation((RX + sg * 27.0, 291.75, YZ))
        out.append(b)
    return out


def main():
    work = WIP / 'slice' / 'hub_plate'
    if work.exists():
        shutil.rmtree(work)
    (work / 'profile').mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    part = trimesh.load(SRC)
    part.apply_transform(R)
    z0 = part.bounds[0, 2]
    part.apply_translation((0, 0, -z0))
    blockers = [groove_blocker()] + lug_blockers()
    for b in blockers:
        b.apply_transform(R)
        b.apply_translation((0, 0, -z0))
    # a 100 % modifier over the clamped zones (the lugs, and the top with the six screw seats): the whole part is 100 % here,
    # so it changes nothing, but it stays in the project if someone lowers the general infill (and the helper needs one)
    top = trimesh.creation.cylinder(radius=26.0, height=9.0, sections=64)
    top.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
    top.apply_translation((RX, 315.4, YZ))
    mods = [top] + lug_blockers()
    for m_ in mods:
        m_.apply_transform(R)
        m_.apply_translation((0, 0, -z0))
    src, size = P.project(NAME, part, mods, EXTRA, work, blockers=blockers)
    final = f'{NAME}.3mf'
    args = [P.EXE, '--datadir', str(work / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(work), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3000, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (work / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(part=str(SRC.name), exit=r.returncode, size_mm=[round(float(v), 1) for v in size])
    f = work / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['filaments'] = re.findall(r'<filament [^>]*>', s)
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        cur = json.loads(z.read('Metadata/project_settings.config'))
        seed = json.loads(zipfile.ZipFile(P.SEED).read('Metadata/project_settings.config'))
        res['settings'] = {k: cur.get(k) for k in ('layer_height', 'wall_loops', 'sparse_infill_density', 'sparse_infill_pattern', 'enable_support', 'support_type', 'brim_type',
                                                   'filament_settings_id', 'filament_type', 'nozzle_temperature', 'supertack_plate_temp', 'printer_settings_id',
                                                   'print_settings_id', 'curr_bed_type', 'top_shell_layers', 'bottom_shell_layers')}
        res['differs_from_seed'] = sorted(k for k in set(cur) | set(seed) if cur.get(k) != seed.get(k) and k != 'different_settings_to_system')
        res['list_length_mismatches'] = sorted(k for k in seed if isinstance(seed[k], list) and k != 'different_settings_to_system'
                                               and (not isinstance(cur.get(k), list) or len(cur[k]) != len(seed[k])))
        res['flagged'] = cur.get('different_settings_to_system')
        res['gcode'] = any(n.endswith('.gcode') for n in z.namelist())
        for n in z.namelist():
            if n.endswith('plate_1.png'):
                (OUT / f'{NAME}_plate.png').write_bytes(z.read(n))
        shutil.copy(f, OUT / final)
    (OUT / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res), flush=True)


if __name__ == '__main__':
    main()
