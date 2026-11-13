"""Lug plate ligament check (review A5, 2026-11-13): the strip of plate above the bolt hole, against the extrusion width.
Reads the plate geometry constants used by lug_shim_print.py and, if given, the sliced plate STL, and reports the ligament
above and below the hole and how many perimeters fit.
    python plate_ligament_check.py [PLATE_STL]      (under capped.py)"""
import os
import sys

LINE_W = 0.42        # Bambu P2S 0.4 nozzle default outer wall line width
BOLT_Y = 292.0
HOLE_R = float(os.environ.get('LUG_PLATE_HOLE_R', '1.9'))      # r1g4 Dia 3.8 (was 4.4)
PLATE_Y0, PLATE_Y1 = 288.2, float(os.environ.get('LUG_PLATE_TOP', '294.6'))
ROOT_TANGENT_Y = 294.8   # hub R1.2 Z-root tangent

for nm, lig in (('above the hole', PLATE_Y1 - (BOLT_Y + HOLE_R)), ('below the hole', (BOLT_Y - HOLE_R) - PLATE_Y0)):
    print(f'ligament {nm}: {lig:.2f} mm = {lig / LINE_W:.2f} line widths ({int(lig // LINE_W)} whole perimeters)')
print(f'plate top to the R1.2 root tangent: {ROOT_TANGENT_Y - PLATE_Y1:.2f} mm')
if len(sys.argv) > 1:
    import numpy as np
    import trimesh
    m = trimesh.load(sys.argv[1])
    z = float(m.bounds[1, 2]) / 2
    sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    print('mid-height section loops:', 0 if sec is None else len(sec.discrete))
