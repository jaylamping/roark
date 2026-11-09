"""Print projects for the arm parts. Each mesh goes into the P2 seed project (p2_seed.json: the reviewed P2 L04B project with
its mesh removed), so every setting is the P2 process, then Bambu Studio slices it offline. Library for ua_slice.py."""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CAD = HERE.parents[1]
OUT = CAD / '_wip' / 'arm-slices'          # scratch (gitignored)


class Seed:
    """The seed project's files, read like the zip they came from."""
    def __init__(self):
        import json as _j
        self.files = _j.loads((HERE / 'p2_seed.json').read_text(encoding='utf-8'))['files']

    def infolist(self):
        return [type('I', (), {'filename': n}) for n in self.files]

    def read(self, n):
        return self.files[n].encode()
EXE = 'C:/Program Files/Bambu Studio/bambu-studio.exe'
BED = 256.0
UP_X = lambda v: v[:, [1, 2, 0]]  # +X up, cyclic, keeps handedness
DOWN_X = lambda v: np.c_[v[:, 2], v[:, 1], -v[:, 0]]  # -X up, outboard face on the bed


def read_stl(p):
    b = Path(p).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    t = np.frombuffer(b, np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')]), n, 84)['v'].reshape(-1, 3).astype(float)
    return t * 1000 if np.ptp(t, axis=0).max() < 5 else t


JOBS = {}   # jobs are added by the part scripts (ua_slice.py)


# settings that differ from the P2 project, on purpose
BRIM = {'brim_type': 'outer_only', 'brim_width': '5', 'curr_bed_type': 'Supertack Plate', 'support_type': 'tree(auto)', 'support_style': 'tree_hybrid'}
EXTRA = {}
# support blockers: keep support out of the bearing seat, r 28 about the elbow axis, carrier inboard face down
BLOCK = {'carrier': lambda lo, hi: disc((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 28.0, lo[2] - 1, hi[2] + 1)}



PLA = 'Bambu PLA Basic @BBL P2S'
FDIR = Path(os.environ.get('APPDATA', '')) / 'BambuStudio/system/BBL/filament'
SKIP = {'name', 'from', 'inherits', 'type', 'instantiation', 'setting_id', 'include', 'compatible_printers', 'filament_extruder_variant'}


def filament(n):
    """A Bambu system filament profile with its inherits chain resolved."""
    p = FDIR / f'{n}.json'
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding='utf8'))
    b = filament(d['inherits']) if 'inherits' in d else {}
    b.update(d)
    return b


def to_pla(ps):
    """Swap the project's PETG for Bambu PLA Basic, keeping the process (walls, infill, supports) as it is."""
    f = filament(PLA)
    if not f:
        raise SystemExit(f'no {PLA} profile in {FDIR}')
    for k, v in f.items():
        if k in SKIP or k not in ps:
            continue
        cur = ps[k]
        if isinstance(cur, list) and isinstance(v, list) and len(v) != len(cur):
            v = (v * len(cur))[:len(cur)] if len(v) == 1 else v[:len(cur)] if len(v) > len(cur) else v + [v[-1]] * (len(cur) - len(v))
        ps[k] = v
    ps['filament_settings_id'] = [PLA]
    if 'filament_ids' in ps:
        ps['filament_ids'] = [f.get('filament_id', '')]
    return ps


PLA_JOBS = ()  # internal parts that carry no load, or rig fixtures


def box_mesh(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    c = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return c[np.array(f)].reshape(-1, 3)


MOD = {}


SYS = Path(os.environ.get('APPDATA', '')) / 'BambuStudio/system/BBL'


def system_preset(kind, n):
    """A Bambu system preset with its inherits chain resolved."""
    p = SYS / kind / f'{n}.json'
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding='utf8'))
    b = system_preset(kind, d['inherits']) if 'inherits' in d else {}
    b.update(d)
    return b


def mark_overrides(ps, ours=()):
    """List every key that differs from the system presets, so Bambu Studio keeps our values instead of reloading the preset's."""
    meta = {'name', 'from', 'inherits', 'type', 'instantiation', 'setting_id', 'include', 'compatible_printers', 'compatible_printers_condition', 'version', 'print_settings_id', 'filament_settings_id', 'printer_settings_id'}
    fil = ps.get('filament_settings_id') or ['']
    out = []
    for kind, n in [('process', ps.get('print_settings_id', ''))] + [('filament', f) for f in fil] + [('machine', ps.get('printer_settings_id', ''))]:
        ref = system_preset(kind, n)
        keys = sorted(k for k, v in ref.items() if k not in meta and k in ps and ps[k] != v and not (isinstance(v, list) and isinstance(ps[k], list) and len(v) == 1 and all(x == v[0] for x in ps[k])))
        out.append(';'.join(keys))
    extra = [k for k in ours if k in ps and k != 'curr_bed_type' and k not in out[0].split(';')]
    out[0] = ';'.join(sorted([k for k in out[0].split(';') if k] + extra))
    ps['different_settings_to_system'] = out
    return ps

def disc(cx, cy, r, z0, z1, n=48):
    """Solid cylinder, as triangles, for a support blocker. Plate-up coordinates of the job."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    p = np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]
    v = []
    for i in range(n):
        j = (i + 1) % n
        A, B = p[i], p[j]
        v += [[cx, cy, z0], [B[0], B[1], z0], [A[0], A[1], z0]]
        v += [[cx, cy, z1], [A[0], A[1], z1], [B[0], B[1], z1]]
        v += [[A[0], A[1], z0], [B[0], B[1], z0], [B[0], B[1], z1]]
        v += [[A[0], A[1], z0], [B[0], B[1], z1], [A[0], A[1], z1]]
    return np.array(v, float)


def mesh_xml(tri, shift):
    key = np.round(tri, 4)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    uniq = uniq - shift
    vs = chr(10).join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{w:.5f}"/>' for x, y, w in uniq)
    ts = chr(10).join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    return vs, ts, len(faces)


def project(name, tri, out):
    key = np.round(tri, 4)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    lo, hi = uniq.min(0), uniq.max(0)
    size = hi - lo
    center = (lo + hi) / 2
    uniq = uniq - center
    if size[0] > BED - 12 or size[1] > BED - 12 or size[2] > BED:
        raise SystemExit(f'{name} does not fit {size}')
    h = size[2] / 2
    z = Seed()
    verts = '\n'.join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{w:.5f}"/>' for x, y, w in uniq)
    tris = '\n'.join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    obj = z.read('3D/Objects/object_1.model').decode()
    obj = obj[:obj.index('<vertices>')] + '<vertices>\n' + verts + '\n    </vertices>\n    <triangles>\n' + tris + '\n    </triangles>' + obj[obj.index('</triangles>') + len('</triangles>'):]
    blk = BLOCK.get(name)
    mdl = z.read('3D/3dmodel.model').decode()
    if name != 'p2':
        mdl = re.sub(r'(<item objectid="2"[^>]*transform=")[^"]*"', rf'\g<1>1 0 0 0 1 0 0 0 1 128 128 {h:.5f}"', mdl)
    cfg = z.read('Metadata/model_settings.config').decode()
    if blk:
        vs, ts, nb = mesh_xml(blk(lo, hi), center)
        obj = obj.replace('  </object>', '  </object>' + chr(10) + '  <object id="3" p:UUID="00030000-81cb-4c03-9d28-80fed5dfa1dc" type="model">' + chr(10) + '   <mesh>' + chr(10) + '    <vertices>' + chr(10) + vs + chr(10) + '    </vertices>' + chr(10) + '    <triangles>' + chr(10) + ts + chr(10) + '    </triangles>' + chr(10) + '   </mesh>' + chr(10) + '  </object>', 1)
        mdl = mdl.replace('</components>', ' <component p:path="/3D/Objects/object_1.model" objectid="3" p:UUID="00010001-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' + chr(10) + '   </components>', 1)
        cfg = cfg.replace('    </part>', '    </part>' + chr(10) + f'    <part id="3" subtype="support_blocker" uuid="51d17843-7a32-47a7-bb0b-71b78baf25d6">' + chr(10) + '      <metadata key="name" value="blocker" />' + chr(10) + f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 {h:.5f} 0 0 0 1" />' + chr(10) + f'      <mesh_stat face_count="{nb}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0" />' + chr(10) + '    </part>', 1)
    mod = MOD.get(name)
    if mod:
        vs, ts, nm_ = mesh_xml(mod[0](lo, hi), center)
        obj = obj.replace('  </object>', '  </object>' + chr(10) + '  <object id="4" p:UUID="00040000-81cb-4c03-9d28-80fed5dfa1dc" type="model">' + chr(10) + '   <mesh>' + chr(10) + '    <vertices>' + chr(10) + vs + chr(10) + '    </vertices>' + chr(10) + '    <triangles>' + chr(10) + ts + chr(10) + '    </triangles>' + chr(10) + '   </mesh>' + chr(10) + '  </object>', 1)
        mdl = mdl.replace('</components>', ' <component p:path="/3D/Objects/object_1.model" objectid="4" p:UUID="00010002-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' + chr(10) + '   </components>', 1)
        meta = ''.join(f'      <metadata key="{k}" value="{v}" />' + chr(10) for k, v in mod[1].items())
        cfg = cfg.replace('    </part>', '    </part>' + chr(10) + '    <part id="4" subtype="modifier_part" uuid="51d17843-7a32-47a7-bb0b-71b78baf25d7">' + chr(10) + '      <metadata key="name" value="clamp_solid" />' + chr(10) + f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 {h:.5f} 0 0 0 1" />' + chr(10) + meta + f'      <mesh_stat face_count="{nm_}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0" />' + chr(10) + '    </part>', 1)
    cfg = cfg.replace('P2_LEFT_L04B_04HF_100R_6W_DEVELOPMENT_HOLD', name)
    cfg = cfg.replace('174726', str(len(faces)))
    cfg = cfg.replace('value="1 0 0 0 0 1 0 0 0 0 1 51 0 0 0 1"', f'value="1 0 0 0 0 1 0 0 0 0 1 {h:.5f} 0 0 0 1"')
    cfg = cfg.replace('key="source_offset_z" value="51"', f'key="source_offset_z" value="{h:.5f}"')
    ps = json.loads(z.read('Metadata/project_settings.config'))
    ps.update(BRIM)
    ps.update(EXTRA.get(name, {}))
    if name in PLA_JOBS:
        to_pla(ps)
    mark_overrides(ps, set(BRIM) | set(EXTRA.get(name, {})))
    src = out / f'{name}_input.3mf'
    with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as o:
        for i in z.infolist():
            d = z.read(i.filename)
            if i.filename == '3D/Objects/object_1.model':
                d = obj.encode()
            elif i.filename == '3D/3dmodel.model':
                d = mdl.encode()
            elif i.filename == 'Metadata/model_settings.config':
                d = cfg.encode()
            elif i.filename == 'Metadata/project_settings.config':
                d = json.dumps(ps, indent=4).encode()
            elif i.filename == 'Metadata/plate_1.json' or i.filename.endswith('.png'):
                continue
            o.writestr(i.filename, d)
    return src, size, len(faces)


def mesh_gate(name, tri, out):
    """Fail the build before any 3MF is written if the part mesh has slivers, spikes or stray bodies."""
    sys.path[:0] = [str(mesh_check_dir()), str(whitelist_dir())]
    import mesh_check
    from mesh_whitelist import WHITELIST
    mesh_check.gate(name, tri, out, SRC.get(name), WHITELIST)


def mesh_check_dir():
    return HERE


def whitelist_dir():
    return HERE


SRC = {}  # source meshes in CAD coordinates, by job


def run(name):
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    (out / 'profile').mkdir(parents=True)
    tri = JOBS[name]()
    mesh_gate(name, tri, out)
    src, size, nf = project(name, tri, out)
    final = f'{name}.3mf'
    args = [EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (out / 'log.txt').write_text(r.stdout[-4000:] + r.stderr[-2000:], errors='replace')
    res = dict(name=name, exit=r.returncode, size_mm=[round(float(v), 1) for v in size], faces=int(nf))
    f = out / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = re.findall(r'key="(prediction|weight)" value="([^"]*)"', s)
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        p = json.loads(z.read('Metadata/plate_1.json'))
        res['bbox'] = [round(v, 1) for v in p.get('bbox_all', [])]
        cur = json.loads(z.read('Metadata/project_settings.config'))
        ref = json.loads(Seed().read('Metadata/project_settings.config'))
        res['settings_diff'] = {k: (str(cur.get(k))[:40], str(ref.get(k))[:40]) for k in ref if cur.get(k) != ref.get(k)}
    (out / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:900], flush=True)


if __name__ == '__main__':
    for n in (sys.argv[1:] or JOBS):
        run(n)
