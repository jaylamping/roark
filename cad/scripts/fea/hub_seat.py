"""Upper-arm hub seat with the hub as its own body (2026-11-11). The usual FEA model fixes the arm's seat bore, and the layer
peak then sits on that fixed face (STOP_124 unexcluded layer SF 0.48-0.53 at Y 299). Here the arm is held the way it is built:

  - today's hub (left-arm upper_arm_hub_left.SLDPRT, as exported) is a second body, fixed at its top face (Y 319.86);
  - its spigot (r 35.8, Y 296-302) sits in the arm's seat bore (r 35.9) and its disc bears on the arm's end face (Y 302):
    no-penetration contact, so the seat only carries what it would by bearing;
  - its two lugs (Z CZ +-5) are clamped between the arm's hub posts by the seam bolts: the posts here run from the lug faces
    out to the skin (no clearance), and the touching faces are bonded, which stands in for the clamped joint under the bolts.

The arm is the R1 FEA model (UA_ORGANIC_BONDED_v28: master with the RS02 ring bonded in and the stop-lug pads).

    python cad/scripts/fea/hub_seat.py build                # once, in its own SolidWorks instance
    python cad/scripts/fea/organic_fea.py HS_STOP_0_fine    # cases are registered in organic_fea.py via register()
"""
import math
import os
import shutil
import sys
from pathlib import Path

ARM = Path(__file__).resolve().parents[1] / 'arm'
CAD = Path(__file__).resolve().parents[2]
F = Path(os.environ.get('ARM_FEA_DIR', CAD / '_sim' / 'ua2'))
HUB_SRC = Path(r'J:/code/roark-wt/left-arm/cad/upper-arm/upper_arm_hub_left.SLDPRT')   # the native part its STEP/STL exports were recorded from
HUB = F / 'HUB_TODAY.SLDPRT'
MODEL = F / 'UA_HUBSEAT_v28.SLDPRT'
HX, CY, CZ = 170.49, 209.860668, 5.985875
HUB_TOP = 319.86


def build():
    sys.path.insert(0, str(ARM))
    os.chdir(ARM)
    import organic_parts as OP
    from organic_master import L, NUL, sw, bodies
    shutil.copy(HUB_SRC, HUB)          # (the STEP import hung behind a dialog in a hidden instance)
    shutil.copy(F / 'UA_ORGANIC_BONDED_v28.SLDPRT', MODEL)
    e, w = L(), L()
    d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
    if d is None:
        raise SystemExit('open ' + str(MODEL))
    for i, q in enumerate(OP.HUB_COLS):
        for sg in (1, -1):
            OP.post_z(d, f'HUB_POST{i}{"F" if sg > 0 else "B"}', (q[0], OP.HUB_POST_Y), sg, z0=CZ + sg * OP.HUB_LUG_HZ)
    d.ForceRebuild3(False)
    n0 = len(bodies(d))
    f = d.InsertPart3(str(HUB), 1, '')        # swInsertPartImportSolids
    d.ForceRebuild3(False)
    bs = bodies(d)
    print('  bodies', n0, '->', bs, 'insert', f is not None, flush=True)
    if len(bs) != n0 + 1:
        raise SystemExit('hub not inserted as its own body')
    d.Save3(1, e, w)
    sw.CloseDoc(d.GetTitle)


def register(CASES, PARTS, pythoncom, VARIANT, I):
    """Add HS_<case> for STOP_0, STOP_124 and G90 (coarse and fine) on the hub-seat model."""
    PARTS['hubseat'] = MODEL

    def faces(b):
        fs = b.GetFaces
        return list((fs() if callable(fs) else fs) or [])

    def box(f):
        return [v * 1000 for v in f.GetBox]

    def pre(st, d, lbc):
        bs = list(d.GetBodies2(0, True))
        if len(bs) != 2:
            raise SystemExit(f'expected 2 bodies, got {len(bs)}')
        hub = min(bs, key=lambda b: b.GetMassProperties(1190)[3])
        arm = [b for b in bs if b is not hub][0]
        # contact at the seat: hub faces near the spigot and the disc's underside, arm faces of the bore and the end face

        def near_seat(b):
            lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
            r = max(math.hypot(x - HX, z - CZ) for x in (lo[0], hi[0]) for z in (lo[2], hi[2]))
            return hi[1] > 295.5 and lo[1] < 302.5 and r > 30.0

        hf = [f for f in faces(hub) if near_seat(box(f))]
        af = [f for f in faces(arm) if near_seat(box(f))]
        cm = st.ContactManager
        err = I()
        cs = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, hf), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, af), err)
        print(' seat contact set', cs is not None, 'faces hub', len(hf), 'arm', len(af), 'err', err.value, flush=True)
        if err.value or cm.ContactSetCount == 0:
            raise SystemExit('contact failed')
        try:
            st.StaticStudyOptions.UseSoftSpring = 1
        except Exception as ex:
            print(' soft springs not set', str(ex)[:80], flush=True)

        def post(st_, res):
            return dict(model='hub as its own body, seat by contact, lugs bonded to posts')
        return post

    for k in ('STOP_0', 'STOP_124', 'G90'):
        for sfx in ('', '_fine'):
            if k + sfx in CASES:
                c = dict(CASES[k + sfx])
                c.update(part='hubseat', fix=[('fixed', ('plane', (HX, HUB_TOP, CZ), None))], pre_mesh=pre)   # hub top face
                CASES['HS_' + k + sfx] = c


if __name__ == '__main__' and sys.argv[1:] == ['build']:
    build()
