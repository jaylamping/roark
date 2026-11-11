"""Concept A upper arm: Bambu Studio print projects for the P2S, from the STL exports.

Each part goes into the last accepted upper-arm project (marengo hardware/designs/left-arm/prints/upper-arm/upper_arm.3mf,
released 2026-11-07), so every setting is that print's: P2S, 0.4 mm High Flow nozzle, Generic PETG, 0.20 mm layers, 6 walls,
50% zig-zag sparse infill with a 100% modifier, Cool Plate SuperTack (no glue, plate 70 C), tree supports (Tree Hybrid), outer
brim 5 mm. Only the meshes, the modifier meshes and the infill of the ring and the coupon change. The 100% modifier covers the
loaded zones: the drum's inboard end (stop lug and its backing, the 6808 stub, the RS02 rib and its key seats), the seam posts,
and the hub band with its lug posts. The ring prints 100% throughout. Every setting that differs from the system presets is
listed in different_settings_to_system, so Bambu Studio keeps it.
Then Bambu Studio slices each project offline (--slice 0 --export-3mf), and the sliced 3MF (with its G-code) is checked:
height, time, grams, settings against the seed, and where the support lands.

    python cad/scripts/arm/organic_print.py [ring back front stub_coupon]

Writes cad/_wip/organic-arm/print/<job>/ (input project, sliced 3MF, result.json, log).
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

CY, CZ = 209.860668, 5.985875
REPO = Path(__file__).resolve().parents[3]
E = REPO / 'cad' / 'exports' / 'upper-arm'
OUT = REPO / 'cad' / '_wip' / 'organic-arm' / 'print'
SEED = HOLD = Path('J:/code/marengo/hardware/designs/left-arm/prints/upper-arm/upper_arm.3mf')
EXE = 'C:/Program Files/Bambu Studio/bambu-studio.exe'
BED = 256.0
SYS = Path.home() / 'AppData/Roaming/BambuStudio/system/BBL'
if not SYS.is_dir():      # before Bambu Studio's GUI has run once, use the presets shipped with the install
    SYS = Path(EXE).parent / 'resources/profiles/BBL'

# settings that differ from the seed project, on purpose
COMMON = {}       # all already in the seed: brim outer 5, SuperTack, tree hybrid, support on, 6 walls
HALF = {'sparse_infill_density': '50%'}
SOLID = {'sparse_infill_density': '100%'}
RING = {'sparse_infill_density': '100%', 'brim_type': 'no_brim'}     # no brim: it would flash the key-slot flanks (review 2026-11-11)
FIT = {'wall_loops': '3', 'sparse_infill_density': '15%'}      # fit coupons only check a fit (as test pass 1)


# ---- orientations: CAD (arm frame) -> plate, proper rotations only
def ring_down(v):        # RS02 face (X 165.7) on the bed: -X up
    return np.c_[v[:, 2], v[:, 1], -v[:, 0]]


def front_down(v):       # front half (Z > CZ): its seam face Z = CZ on the bed, outside up
    return v.copy()


def back_down(v):        # back half (Z < CZ): turned over about Y, seam face on the bed
    return np.c_[-v[:, 0], v[:, 1], -v[:, 2]]


def load(name):
    return trimesh.load(E / f'upper_arm_organic_{name}_left.STL')


def cyl_z(x, y, r, z0, z1):
    c = trimesh.creation.cylinder(radius=r, height=z1 - z0, sections=48)
    c.apply_translation((x, y, (z0 + z1) / 2))
    return c


def box(lo, hi):
    b = trimesh.creation.box(extents=np.subtract(hi, lo))
    b.apply_translation(np.add(lo, hi) / 2)
    return b


def loaded_zones():
    """100% infill zones in CAD coordinates (the same for both halves; each half only meets its own side)."""
    z = [box((128.0, 150.0, -50.0), (171.0, 262.0, 62.0)),            # drum inboard end: lug + backing, stub, rib, the four keys to their tips and the wall tapers past them
         box((128.0, 283.0, -50.0), (214.0, 312.0, 62.0))]            # hub band: seat, lug posts
    for x, y in [(151.0, 272.0), (190.0, 272.0)]:                       # seam posts (organic_parts.UA_POSTS)
        z.append(cyl_z(x, y, 7.0, -50.0, 62.0))
    return z


def stub_coupon():
    """The two half-stubs as printed (each half seam face down), cut from the halves at X 130.5-142.5, inside r 24: the Ø40
    seat for the 6808 inner race and a slice of the end wall to hold it. Laid side by side."""
    keep = trimesh.creation.cylinder(radius=24.0, height=12.0, sections=96)
    keep.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    keep.apply_translation((136.5, CY, CZ))
    a = load('front').intersection(keep)
    b = load('back').intersection(keep)
    va, vb = front_down(a.vertices), back_down(b.vertices)
    a = trimesh.Trimesh(va, a.faces)
    b = trimesh.Trimesh(vb, b.faces)
    b.apply_translation((a.bounds[1, 0] - b.bounds[0, 0] + 12.0, a.bounds[0, 1] - b.bounds[0, 1], a.bounds[0, 2] - b.bounds[0, 2]))
    return trimesh.util.concatenate([a, b]), [], FIT


def key_coupon():
    """Ring-and-key torque coupon: the back half's main key (phi 80) with its rib and a patch of drum wall, cut from the back
    half and printed the same way up (seam face down), for a break test against a second ring. Box X 143-166.5,
    dy -10..21, dz -47..-27 about the elbow axis."""
    keep = box((143.0, CY - 10.0, CZ - 47.0), (166.5, CY + 21.0, CZ - 27.0))
    c = load('back').intersection(keep)
    return trimesh.Trimesh(back_down(c.vertices), c.faces), [], SOLID


JOBS = {
    'ring': lambda: (trimesh.Trimesh(ring_down(load('rs02_ring').vertices), load('rs02_ring').faces), [], RING),
    'back': lambda: (trimesh.Trimesh(back_down(load('back').vertices), load('back').faces),
                     [trimesh.Trimesh(back_down(z.vertices), z.faces) for z in loaded_zones()], HALF),
    'front': lambda: (trimesh.Trimesh(front_down(load('front').vertices), load('front').faces),
                      [trimesh.Trimesh(front_down(z.vertices), z.faces) for z in loaded_zones()], HALF),
    'stub_coupon': stub_coupon,
    'key_coupon': key_coupon,
}


def system_preset(kind, n):
    p = SYS / kind / f'{n}.json'
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding='utf8'))
    b = system_preset(kind, d['inherits']) if 'inherits' in d else {}
    b.update(d)
    return b


def mark_overrides(ps, ours=()):
    """List every key that differs from the system presets, so Bambu Studio keeps our values instead of reloading the preset's."""
    meta = {'name', 'from', 'inherits', 'type', 'instantiation', 'setting_id', 'include', 'compatible_printers',
            'compatible_printers_condition', 'version', 'print_settings_id', 'filament_settings_id', 'printer_settings_id'}
    fil = ps.get('filament_settings_id') or ['']
    seed = list(ps.get('different_settings_to_system') or [])     # keep everything the accepted project already kept
    out = []
    for kind, n in [('process', ps.get('print_settings_id', ''))] + [('filament', f) for f in fil] + [('machine', ps.get('printer_settings_id', ''))]:
        ref = system_preset(kind, n)
        keys = sorted(k for k, v in ref.items() if k not in meta and k in ps and ps[k] != v
                      and not (isinstance(v, list) and isinstance(ps[k], list) and len(v) == 1 and all(x == v[0] for x in ps[k])))
        out.append(';'.join(keys))
    extra = [k for k in ours if k in ps and k != 'curr_bed_type' and k not in out[0].split(';')]
    out[0] = ';'.join(sorted([k for k in out[0].split(';') if k] + extra))
    for i, old in enumerate(seed[:len(out)]):
        out[i] = ';'.join(sorted(set(k for k in out[i].split(';') if k) | set(k for k in old.split(';') if k)))
    ps['different_settings_to_system'] = out
    return ps


def xml(m, shift):
    v = m.vertices - shift
    vs = '\n'.join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{w:.5f}"/>' for x, y, w in v)
    ts = '\n'.join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
    return vs, ts


def obj_xml(i, uid, kind, vs, ts):
    nl = chr(10)
    return (f'<object id="{i}" p:UUID="{uid}-81cb-4c03-9d28-80fed5dfa1dc" type="{kind}">' + nl + '   <mesh>' + nl + '    <vertices>' + nl + vs + nl
            + '    </vertices>' + nl + '    <triangles>' + nl + ts + nl + '    </triangles>' + nl + '   </mesh>' + nl + '  </object>' + nl + '  ')


def project(name, part, mods, extra, out):
    lo, hi = part.bounds
    size = hi - lo
    if size[0] > BED - 12 or size[1] > BED - 12 or size[2] > BED:
        raise SystemExit(f'{name} does not fit {size}')
    center = (lo + hi) / 2
    center[2] = lo[2] + size[2] / 2
    h = size[2] / 2
    z = zipfile.ZipFile(SEED)
    obj = z.read('3D/Objects/object_1.model').decode()
    head, rest = obj[:obj.index('<object id="1"')], obj[obj.index('<object id="1"'):]
    tail = rest[rest.index('</resources>'):]
    vs, ts = xml(part, center)
    body = obj_xml(1, '00010000', 'model', vs, ts)
    mdl = z.read('3D/3dmodel.model').decode()
    cfg = z.read('Metadata/model_settings.config').decode()
    if mods:
        mm = trimesh.util.concatenate(mods)
        mvs, mts = xml(mm, center)
        body += obj_xml(2, '00010001', 'other', mvs, mts)
        mdl = re.sub(r'(objectid="2"[^>]*transform=")[^"]*"', r'\g<1>1 0 0 0 1 0 0 0 1 0 0 0"', mdl)
        cfg = re.sub(r'(<part id="2"[\s\S]*?key="matrix" value=")[^"]*"', rf'\g<1>1 0 0 0 0 1 0 0 0 0 1 {h:.5f} 0 0 0 1"', cfg)
        cfg = re.sub(r'(<part id="2"[\s\S]*?<mesh_stat face_count=")\d+', rf'\g<1>{len(mm.faces)}', cfg)
        cfg = cfg.replace('value="clamp_solid"', 'value="loaded_zones_100"')
    else:
        mdl = re.sub(r'\s*<component [^>]*objectid="2"[^>]*/>', '', mdl)
        cfg = re.sub(r'\s*<part id="2"[\s\S]*?</part>', '', cfg)
    obj = head + body + tail
    mdl = re.sub(r'(<item objectid="3"[^>]*transform=")[^"]*"', rf'\g<1>1 0 0 0 1 0 0 0 1 128 128 {h:.5f}"', mdl)
    cfg = cfg.replace('value="upper_arm"', f'value="upper_arm_organic_{name}"')
    cfg = re.sub(r'(<part id="1"[\s\S]*?key="matrix" value=")[^"]*"', rf'\g<1>1 0 0 0 0 1 0 0 0 0 1 {h:.5f} 0 0 0 1"', cfg)
    cfg = re.sub(r'(key="source_offset_z" value=")[^"]*"', rf'\g<1>{h:.5f}"', cfg)
    cfg = cfg.replace('face_count="48066"', f'face_count="{len(part.faces)}"')
    ps = json.loads(z.read('Metadata/project_settings.config'))
    ps.update(COMMON)
    ps.update(extra)
    mark_overrides(ps, set(COMMON) | set(extra))
    src = out / f'{name}_input.3mf'
    drop = ('Metadata/plate_1.gcode', 'Metadata/plate_1.gcode.md5', 'Metadata/slice_info.config', 'Metadata/plate_1.json')
    with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as o:
        for i in z.infolist():
            if i.filename in drop or i.filename.endswith('.png'):
                continue
            d = z.read(i.filename)
            if i.filename == '3D/Objects/object_1.model':
                d = obj.encode()
            elif i.filename == '3D/3dmodel.model':
                d = mdl.encode()
            elif i.filename == 'Metadata/model_settings.config':
                d = cfg.encode()
            elif i.filename == 'Metadata/project_settings.config':
                d = json.dumps(ps, indent=4).encode()
            o.writestr(i.filename, d)
    return src, size


def run(name):
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    part, mods, extra = JOBS[name]()
    z0 = part.bounds[0, 2]
    part.apply_translation((0, 0, -z0))
    for m in mods:
        m.apply_translation((0, 0, -z0))
    part.export(out / f'{name}_plate.stl')
    src, size = project(name, part, mods, extra, out)
    final = f'upper_arm_organic_{name}.3mf'
    args = [EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(name=name, exit=r.returncode, size_mm=[round(float(v), 1) for v in size], faces=int(len(part.faces)), watertight=bool(part.is_watertight))
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        p = json.loads(z.read('Metadata/plate_1.json'))
        res['bbox'] = [round(v, 1) for v in p.get('bbox_all', [])]
        cur = json.loads(z.read('Metadata/project_settings.config'))
        ref = json.loads(zipfile.ZipFile(HOLD).read('Metadata/project_settings.config'))
        res['settings_vs_seed'] = {k: (str(cur.get(k))[:40], str(ref.get(k))[:40]) for k in ref if cur.get(k) != ref.get(k)}
        res['kept_as_ours'] = cur.get('different_settings_to_system')
        g = [n for n in z.namelist() if n.endswith('.gcode')]
        if g:
            (out / f'upper_arm_organic_{name}.gcode').write_bytes(z.read(g[0]))
            res['gcode'] = g[0]
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:1500], flush=True)


if __name__ == '__main__':
    for n in sys.argv[1:] or JOBS:
        run(n)
