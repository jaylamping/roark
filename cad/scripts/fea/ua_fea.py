"""Upper-arm clamshell FEA on the bonded one-body model (cad/_sim/upper-arm/UA_CLAM_BONDED.SLDPRT, built by
cad/scripts/arm/ua_parts.py fea): the halves, ring and hub as one body, seam tractions read from the saved nodal stresses.

    python cad/scripts/fea/ua_fea.py G0 G45 G90 G135 G180 GLp GLm LC2 [G90_fine ...]

Governing load (Joey): arm straight, 5 kg at the hand about 0.5 m from the shoulder pitch plus self-weight, reduced to the
elbow load point: 62 N along gravity and 17.2 N.m, which makes 24 N.m at the hub face (62 N x 0.110 m + 17.2). Arm frame: Y up
the arm, Z front (flexion side). Shoulder pitch th: gravity g = (0, -cos th, -sin th); lateral GLp/GLm: +-X. The hub face is
clamped on the yaw RS02 output; the load goes in through the ring's carrier-screw holes. A `_fine` case reruns at 2 mm with
1 mm controls on the ring and the step at the ring end, for the convergence check.
"""
import math
import sys

from p3_fea import CASES, F, GOLD, PARTS, cyl, pl, run

PARTS['clam'] = F / 'UA_CLAM_BONDED.SLDPRT'
FG, MG = 62.0, 17.2
SEAM = [130, 240, 3, 212, 300, 9]          # seam band, Z 3..9
HUB_BOX = [125, 296, -40, 215, 321, 50]
RING_BOX = [150, 165, -40, 167, 256, 50]
RING_HOLES = cyl(1.65, [151, 170, -50, 166, 250, 60])
HUB_FACE = pl((150.0, 319.86, 6.0))
REGIONS = {'seam_band': SEAM, 'columns_lo': [134, 255, -22, 208, 296, 6], 'columns_up': [134, 255, 6, 208, 296, 34],
           'hub': HUB_BOX, 'ring': RING_BOX, 'ring_end': [160, 232, -30, 175, 250, 42]}

LOADS = {}
for th in (0, 45, 90, 135, 180):
    g = (0.0, -math.cos(math.radians(th)), -math.sin(math.radians(th)))
    LOADS[f'G{th}'] = (tuple(round(FG * v, 2) for v in g), (round(MG * math.sin(math.radians(th)), 2), 0.0, 0.0))
for tag, sx in (('Lp', 1.0), ('Lm', -1.0)):
    LOADS['G' + tag] = ((FG * sx, 0.0, 0.0), (0.0, 0.0, MG * sx))
LOADS['LC2'] = ((0, 0, 0), (0, 17, 0))          # 17 N.m twist about the arm axis


def case(force, moment, fine=False, part='clam', regions=REGIONS, **kw):
    c = dict(part=part, fix=[('fixed', HUB_FACE)], remote=(RING_HOLES, GOLD, force, moment), regions=regions, **kw)
    if fine:
        c.update(el=2.0, ctrl=[(RING_HOLES, 1.0), (HUB_FACE, 1.5)])
    return c


for k, (f, m) in LOADS.items():
    CASES[k] = case(f, m)
    CASES[k + '_fine'] = case(f, m, fine=True)
    CASES[k + '_xfine'] = dict(case(f, m), el=1.5, ctrl=[(RING_HOLES, 0.8), (HUB_FACE, 1.2)])

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run('clam_' + n, CASES[n])
