"""Concept A upper arm FEA on the bonded model (cad/_sim/upper-arm/UA_ORGANIC_BONDED.SLDPRT, organic_parts.py fea_upper):
halves as one body, the RS02 ring merged into the drum. Run it in its own SolidWorks instance (ARM_SW_DIR).

    python cad/scripts/fea/organic_fea.py G90 G90_fine ...

Fixed: the hub seat bore (today's hub spigot). Elbow loads (from ua_fea.py): 62 N along gravity and 17.2 N.m at the elbow
centre, through the ring bore and the RS02 housing stop face as one rigid connector. E34: 34 N.m elbow torque on the housing
with the arm horizontal. STOP_0 / STOP_124: 889 N on a stop-lug end face (34 N.m at r 38.25).
"""
import math
import os
import sys

from p3_fea import CASES, F, GOLD, PARTS, CY, CZ, cyl, pl, run

PARTS['organic'] = F / os.environ.get('ORG_MODEL', 'UA_ORGANIC_BONDED_v2.SLDPRT')   # v2: lug backing
FG, MG = 62.0, 17.2
SEAT = cyl(35.9, [129, 295, -35, 212, 304, 47])
RS02 = [cyl(32.75, [156, 170, -30, 163.5, 250, 42]), pl((193.9, CY + 30.0, CZ))]
P = lambda r, a: (CY + r * math.cos(math.radians(a)), CZ - r * math.sin(math.radians(a)))
REGIONS = {'neck_blend': [130, 215, -45, 211, 262, 52], 'drum_wall': [144, 165, -45, 196, 255, 52],
           'rib': [151, 165, -45, 158, 255, 52], 'lug': [135, 165, -45, 145, 255, 52], 'neck': [130, 262, -45, 211, 296, 52]}
LOADS = {}
for th in (0, 45, 90, 135, 180):
    g = (0.0, -math.cos(math.radians(th)), -math.sin(math.radians(th)))
    LOADS[f'G{th}'] = (tuple(round(FG * v, 2) for v in g), (round(MG * math.sin(math.radians(th)), 2), 0.0, 0.0))
for tag, sx in (('Lp', 1.0), ('Lm', -1.0)):
    LOADS['G' + tag] = ((FG * sx, 0.0, 0.0), (0.0, 0.0, MG * sx))
LOADS['LC2'] = ((0, 0, 0), (0, 17, 0))
LOADS['E34'] = ((0.0, 0.0, -FG), (34.0, 0.0, 0.0))
LOADS['E17'] = ((0.0, 0.0, -FG), (17.0, 0.0, 0.0))          # the RS02's own peak on its housing
for k, (f, m) in LOADS.items():
    base = dict(part='organic', fix=[('fixed', SEAT)], remote=(RS02, GOLD, f, m), regions=REGIONS)
    CASES[k] = dict(base, el=3.0)
    CASES[k + '_fine'] = dict(base, el=2.0, ctrl=[(SEAT, 1.2)])
    CASES[k + '_xfine'] = dict(base, el=1.5, ctrl=[(SEAT, 1.0)])
for tag, a in (('0', 75.0), ('124', 105.0)):
    face = pl((139.5,) + P(32.25, a))
    CASES['STOP_' + tag] = dict(part='organic', fix=[('fixed', SEAT)], forces=[(face, 889.0, None)], regions=REGIONS, el=2.5, ctrl=[(face, 0.8)])
    CASES['STOP_' + tag + '_fine'] = dict(CASES['STOP_' + tag], el=1.8, ctrl=[(face, 0.5)])

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run('org2_' + n if 'v2' in str(PARTS['organic']) else 'org_' + n, CASES[n])
