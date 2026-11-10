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

from p3_fea import CASES, F, GOLD, PARTS, CY, CZ, I, cyl, pl, run, VARIANT, pythoncom

PARTS['organic'] = F / os.environ.get('ORG_MODEL', 'UA_ORGANIC_BONDED_v14.SLDPRT')   # v4: ring chamfer as printed; v3: ring joined only through its dogs, lug root fillets
FG, MG = 62.0, 17.2
SEAT = cyl(35.9, [129, 295, -35, 212, 304, 47])
RS02 = cyl(32.75, [156, 170, -30, 163.5, 250, 42])      # ring bore only: no rigid tie to the drum
P = lambda r, a: (CY + r * math.cos(math.radians(a)), CZ - r * math.sin(math.radians(a)))
REGIONS = {'ring_zone_excluded': [151.5, 165.8, -45, 165.8, 255, 52], 'neck_blend': [130, 215, -45, 211, 262, 52], 'drum_wall': [144, 165, -45, 196, 255, 52],
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
RING_ZONE = [155.8, 140.0, -50.0, 165.8, 280.0, 60.0]   # merged ring and its corners into rib and wall: bond artefact, keys by hand
for k, (f, m) in LOADS.items():
    base = dict(part='organic', fix=[('fixed', SEAT)], remote=(RS02, GOLD, f, m), regions=REGIONS, exclude=[RING_ZONE])
    CASES[k] = dict(base, el=3.0)
    CASES[k + '_fine'] = dict(base, el=2.0, ctrl=[(SEAT, 1.2)])
    CASES[k + '_xfine'] = dict(base, el=1.5, ctrl=[(SEAT, 1.0)])
for tag, a in (('0', 59.6), ('124', 120.4)):          # contact pads on the 60 deg lug's end faces
    face = ('plane', (137.55,) + P(33.0, a), None, 'on')     # the pad face only
    CASES['STOP_' + tag] = dict(part='organic', fix=[('fixed', SEAT)], forces=[(face, 889.0, None)], regions=REGIONS, el=2.5, ctrl=[(face, 0.8)], exclude=[RING_ZONE])
    CASES['STOP_' + tag + '_fine'] = dict(CASES['STOP_' + tag], el=1.8, ctrl=[(face, 0.5)])
    CASES['STOP_' + tag + '_xfine'] = dict(CASES['STOP_' + tag], el=1.3, ctrl=[(face, 0.35)])

# forearm side of the elbow (bonded shells and discs). Fixed on the RS02 output (6 M4 holes, 3 pin holes) and the 6808 bore
# (hinge); loads at the hand point through the six rim inserts. Layers across X (shells print on the seam, discs flat).
PARTS['fore'] = F / 'FA_ORGANIC_BONDED_v10.SLDPRT'
HAND = (170.49, -73.1, CZ)
OUT_FIX = [('fixed', cyl(2.2, [196, 190, -15, 214, 230, 27])), ('fixed', cyl(2.025, [196, 190, -15, 204, 230, 27])), ('hinge', cyl(26.025, [133, 180, -25, 143, 240, 37]))]
RIM = cyl(2.0, [125, 97, -35, 215, 107, 47])
FREG = {'cheek_in_web': [126, 165, -40, 142, 255, 52], 'cheek_out': [196, 165, -40, 214, 255, 52], 'saddle': [126, 150, -45, 214, 175, 52],
        'belly': [126, 95, -45, 214, 150, 52]}
for k, f, m in (('FP90', (0, 0, -55.0), (0, 0, 0)), ('FLAT', (55.0, 0, 0), (0, 0, 0)), ('FTW', (0, 0, 0), (0, 14.0, 0))):
    CASES[k] = dict(part='fore', fix=OUT_FIX, remote=(RIM, HAND, f, m), regions=FREG, el=3.0)
    CASES[k + '_fine'] = dict(CASES[k], el=2.0, ctrl=[(RIM, 1.0)])
# back-driven onto the stops: 120 N at the hand (34 N.m at the elbow), held by the slot end face and the bearing
for tag, a, fz in (('0', 119.6, -120.0), ('124', -63.6, 120.0)):   # contact pads on the slot ends for the 60 deg lug
    face = ('plane', (137.55,) + P(33.0, a), None, 'on')
    CASES['FSTOP_' + tag] = dict(part='fore', fix=[('fixed', face), OUT_FIX[2]], remote=(RIM, HAND, (0, 0, fz), (0, 0, 0)), regions=FREG, el=2.5, ctrl=[(face, 0.8)])
    CASES['FSTOP_' + tag + '_fine'] = dict(CASES['FSTOP_' + tag], el=1.8, ctrl=[(face, 0.5)])

# contact model: the ring is its own body (0.2 radial, 0.1 axial, dogs 0.4 per side in the notches); the housing load goes in
# through the ring bore only, so the torque has to pass the dogs
PARTS['contact'] = F / 'UA_ORGANIC_CONTACT_v7.SLDPRT'
CREG = dict(REGIONS, dogs_back=[150, 160, -40, 165, 225, -20], dogs_front=[150, 160, 30, 165, 225, 52])


def contact(st, d, lbc):
    """No-penetration contact between every ring face and every drum face near the ring (the ring is the smaller body)."""
    bs = list(d.GetBodies2(0, True))
    if len(bs) != 2:
        raise SystemExit('expected 2 bodies')
    ring = min(bs, key=lambda b: b.GetMassProperties(1190)[3])
    drum = [b for b in bs if b is not ring][0]
    rf = list(ring.GetFaces())
    df = []
    for f in drum.GetFaces():
        bx = [v * 1000 for v in f.GetBox]
        if bx[3] > 151.0 and bx[0] < 164.0 and min(bx[1], bx[4]) < CY + 42 and max(bx[1], bx[4]) > CY - 42:
            df.append(f)
    cm = st.ContactManager
    err = I()
    cs = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, rf), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, df), err)
    print(' contact set', cs is not None, 'faces', len(rf), len(df), 'err', err.value, 'sets', cm.ContactSetCount, flush=True)
    if err.value or cm.ContactSetCount == 0:
        raise SystemExit('contact failed')
    try:
        st.StaticStudyOptions.UseSoftSpring = 1
    except Exception as ex:
        print(' soft springs not set', str(ex)[:80], flush=True)
    return None


for k in ('E34', 'E17', 'G90'):
    f, m = LOADS[k]
    CASES['C' + k] = dict(part='contact', fix=[('fixed', SEAT)], remote=(RS02, GOLD, f, m), regions=CREG, el=2.5, pre_mesh=contact)
    CASES['C' + k + '_fine'] = dict(CASES['C' + k], el=1.8)

# A2 rotating lower forearm. 5 kg at the hand point plus the 500 g placeholder (200 g hand at 90 mm past the face, 300 g pack
# in the bay): 54 N at the combined point Y -68.8. ROT: the turning section held at its bearing seats; STUB: the static stub
# ring held at its top face, the load reaching it through the bearings on the stub.
from pathlib import Path as _P
SIMF = _P(__file__).resolve().parents[2] / '_sim' / 'forearm'
PARTS['rot'] = SIMF / 'ROT_A2_v2.SLDPRT'
PARTS['stub'] = SIMF / 'STUB_A2_v2.SLDPRT'
HP2 = (170.49, -68.8, CZ)
BORE = cyl(26.05, [135, 68, -30, 206, 92, 42])
FACE = pl((170.49 + 25.0, 14.9, CZ))
STUB_OD = cyl(20.0, [145, 69, -20, 196, 91, 32])
RING_TOP = pl((170.49 + 30.0, 98.3, CZ))
RREG = {'hub': [135, 64, -30, 206, 92, 42], 'shell': [133, 14, -32, 208, 84, 44], 'wrist': [135, 14, -30, 206, 23, 42]}
for k, f, m in (('ROT_P90', (0, 0, -54.0), (0, 0, 0)), ('ROT_LAT', (54.0, 0, 0), (0, 0, 0)), ('ROT_TW', (0, 0, 0), (0, 14.0, 0))):
    CASES[k] = dict(part='rot', fix=[('fixed', BORE)], remote=(FACE, HP2, f, m), regions=RREG, el=2.5)
    CASES[k + '_fine'] = dict(CASES[k], el=1.8)
CASES['STUB_P90'] = dict(part='stub', fix=[('fixed', RING_TOP)], remote=(STUB_OD, HP2, (0, 0, -54.0), (0, 0, 0)), el=1.5, regions={'stub': [148, 69, -20, 193, 93, 32]})
CASES['STUB_P90_fine'] = dict(CASES['STUB_P90'], el=1.0)
CASES['STUB_TW'] = dict(part='stub', fix=[('fixed', RING_TOP)], remote=(STUB_OD, HP2, (0, 0, 0), (0, 14.0, 0)), el=1.5, regions={'stub': [148, 69, -20, 193, 93, 32]})

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run(('a2_' if CASES[n]['part'] in ('rot', 'stub') else 'fa_' if CASES[n]['part'] == 'fore' else 'con_' if CASES[n]['part'] == 'contact' else 'org12_') + n, CASES[n])
