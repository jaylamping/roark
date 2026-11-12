"""Hub-end fit coupon (2026-11-12): the part of each printed half above a Y plane (the hub end), capped flat, written with the
halves' file names into OUT_DIR so organic_print.py / print_check.py slice and gate it exactly like the halves (same orientation,
settings, 100% zones, crown support blocker).
    python coupon_cut.py EXPORTS_DIR OUT_DIR Y0      (run under capped.py)"""
import json
import sys
from pathlib import Path

import trimesh

src, out, y0 = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
res = {}
for half in ('front', 'back'):
    m = trimesh.load(src / f'upper_arm_organic_{half}_left.STL')
    c = trimesh.intersections.slice_mesh_plane(m, [0, 1, 0], [0, y0, 0], cap=True)
    c.export(out / f'upper_arm_organic_{half}_left.STL')
    res[half] = dict(cut_Y=y0, volume_mm3=round(c.volume, 0), watertight=bool(c.is_watertight), bounds=c.bounds.round(2).tolist())
for f in ('upper_arm_organic_rs02_ring_left.STL',):
    if (src / f).exists():
        (out / f).write_bytes((src / f).read_bytes())
print(json.dumps(res, indent=1))
