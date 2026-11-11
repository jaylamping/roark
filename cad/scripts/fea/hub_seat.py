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
HUB = F / ('HUB_GROOVE.SLDPRT' if os.environ.get('HS_GROOVE') == '1' else 'HUB_TODAY.SLDPRT')
R1C = os.environ.get('ARM_R1C') == '1'
ARM_MODEL = 'UA_ORGANIC_BONDED_v31.SLDPRT' if R1C else 'UA_ORGANIC_BONDED_v28.SLDPRT'
GROOVE = os.environ.get('HS_GROOVE') == '1'      # option (d): groove in the hub spigot
BOLTED = os.environ.get('HS_BOLTED') == '1'     # lugs in frictionless contact, steel M3 bodies bonded in the post bores, no preload
MODEL = F / os.environ.get('HS_MODEL', ('UA_HUBSEAT_v31' if R1C else 'UA_HUBSEAT_v28') + ('_bolted' if BOLTED else '') + '.SLDPRT')
BOLTS = F / 'HS_BOLTS.SLDPRT'
HX, CY, CZ = 170.49, 209.860668, 5.985875
HUB_TOP = 319.86


def build():
    sys.path.insert(0, str(ARM))
    os.chdir(ARM)
    import organic_parts as OP
    from organic_master import L, NUL, sw, bodies
    shutil.copy(HUB_SRC, HUB)          # (the STEP import hung behind a dialog in a hidden instance)
    if GROOVE:      # option (d): the groove in the hub spigot (profile with organic_master's ridge), on arcs theta 50-130 and 230-310
        import math as m_
        import numpy as np
        import organic_master as M
        e, w = L(), L()
        h = sw.OpenDoc6(str(HUB), 1, 1, '', e, w)
        t30 = m_.tan(m_.radians(30.0))
        y0 = 296.0 + M.RIDGE_LAND      # groove opening, load side
        from swg import revolve as revolve_, centerline as centerline_
        def groove(name, sgn, depth, angle):      # revolve-cut the profile, truncated at r 35.8 - depth, centred on theta 90 (sgn +1) / 270 (-1)
            rb = 35.8 - depth
            prof = [(36.5, y0 - 0.7 * t30), (rb, y0 + depth * t30), (rb, y0 + 2.5 + 1.5 - depth), (36.5, y0 + 4.7)] if depth < 1.5 else                    [(36.5, y0 - 0.7 * t30), (34.3, y0 + 1.5 * t30), (34.3, y0 + 2.5), (36.5, y0 + 4.7)]
            with M.Sk(h, M.plane(h, 'X', HX, name + '_P'), name) as sk_:
                sk_.poly([(HX, y_, CZ + sgn * r_) for r_, y_ in prof])
                centerline_(sk_, (HX, 250.0, CZ), (HX, 340.0, CZ))
            revolve_(h, sk_.feat, name, None, True, angle=angle, mid=True, lo=0.01)
        span = M.RIDGE_ARC[1] - M.RIDGE_ARC[0] + 10.0      # full depth 30-150 (ridge 35-145 plus 5 each end)
        for sgn, tag in ((1, 'F'), (-1, 'B')):
            groove(f'SPIGOT_GROOVE{tag}', sgn, 1.5, span)
            for k in range(1, 11):      # run-outs: 10 deg each end, depth stepping down 0.14 mm per degree pair
                groove(f'GROOVE_RUNOUT{tag}{k}', sgn, 1.5 * (1.0 - k / 11.0), span + 2.0 * k)
        h.ForceRebuild3(False)
        if os.environ.get('HS_ROUNDS', '1') == '1':      # 2026-11-11: hub rounds the shoulder thread is adding to the real hub
            rad = lambda p: m_.hypot(p[0] - HX, p[2] - CZ)
            sets = [('GROOVE_BOT_ROUND', 0.4, lambda p: abs(rad(p) - 34.3) < 0.03 and (abs(p[1] - (y0 + 1.5 * t30)) < 0.05 or abs(p[1] - (y0 + 2.5)) < 0.05)),
                    ('SPIGOT_BOT_ROUND', 0.4, lambda p: abs(rad(p) - 35.8) < 0.03 and abs(p[1] - 296.0) < 0.05)]
            lf = float(os.environ.get('HS_LUG_FILLET', '1.0'))      # lug-to-spigot root on the lugs' X-facing sides only: the arm's hub posts sit
            if lf > 0:                                                # 0.1 under the spigot beside the Z-facing sides, so a fillet there would clash
                lugx = (141.0, 151.75, 189.25, 200.0)
                sets.append(('LUG_ROOT_FILLET', lf, lambda p: abs(p[1] - 296.0) < 0.05 and min(abs(p[0] - x_) for x_ in lugx) < 0.05 and abs(p[2] - CZ) < 5.05))
            for nm, rr, test in sets:
                es = M.edges_where(h, test)
                if nm == 'LUG_ROOT_FILLET':      # only edges running along Z
                    es = [e for e in es if abs(e.GetCurveParams3.StartPoint[0] - e.GetCurveParams3.EndPoint[0]) * 1000 < 0.01]
                print(f'  {nm}: {len(es)} edges', flush=True)
                if M.fillet_edges(h, es, (rr,), nm) is None:
                    ok = sum(M.fillet_edges(h, [e], (rr,), f'{nm}{i}') is not None for i, e in enumerate(es))
                    print(f'  {nm}: {ok}/{len(es)} built edge by edge', flush=True)
            h.ForceRebuild3(False)
        from swg import bodies as bodies_
        print('  grooved hub bodies', bodies_(h), flush=True)
        if len(bodies_(h)) != 1:
            raise SystemExit('groove fills did not merge into the hub')
        h.Save3(1, e, w)
        for t_, v_ in ((69, True), (71, True)):
            sw.SetUserPreferenceToggle(t_, v_)
        h.Extension.SaveAs(str(HUB.with_suffix('.STL')), 0, 1, NUL, L(), L())      # for the assembly check
        sw.CloseDoc(h.GetTitle)
    shutil.copy(F / ARM_MODEL, MODEL)
    e, w = L(), L()
    d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
    if d is None:
        raise SystemExit('open ' + str(MODEL))
    for i, q in enumerate(OP.HUB_COLS):
        for sg in (1, -1):
            OP.post_z(d, f'HUB_POST{i}{"F" if sg > 0 else "B"}', (q[0], OP.HUB_POST_Y), sg, z0=CZ + sg * OP.HUB_LUG_HZ)
    if R1C:
        for sg in (1, -1):
            OP.r1c_fins(d, sg, CZ + sg * OP.HUB_LUG_HZ)
    if BOLTED:      # M3 bores through both posts at each lug (the real holes are 3.4 / inserts; here the bolt fills its bore)
        OP.z_cyl(d, 'HS_BOLT_BORES', OP.HUB_COLS, 1.5, CZ - 45.0, CZ + 50.0, True)
        d.ForceRebuild3(False)
        d.Save3(1, e, w)          # new_part below closes every open document
        import organic_master as M
        b = M.new_part(BOLTS)
        for i, q in enumerate(OP.HUB_COLS):
            with M.Sk(b, M.plane(b, 'Z', CZ + 4.0, f'BOLT{i}_P'), f'BOLT{i}') as s_:
                s_.circle((q[0], q[1], CZ + 4.0), 1.5)
            M.feat(b, s_.feat, f'BOLT{i}', 64.0, False, mode=M.MID, lo=0.01)
        e2, w2 = L(), L()
        b.Save3(1, e2, w2)
        sw.CloseDoc(b.GetTitle)
        e, w = L(), L()
        d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
    d.ForceRebuild3(False)
    n0 = len(bodies(d))
    f = d.InsertPart3(str(HUB), 1, '')        # swInsertPartImportSolids
    d.ForceRebuild3(False)
    bs = bodies(d)
    print('  bodies', n0, '->', bs, 'insert', f is not None, flush=True)
    if len(bs) != n0 + 1:
        raise SystemExit('hub not inserted as its own body')
    if BOLTED:
        fb = d.InsertPart3(str(BOLTS), 1, '')
        d.ForceRebuild3(False)
        print('  bolts', fb is not None, bodies(d), flush=True)
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
        bs = sorted(d.GetBodies2(0, True), key=lambda b: b.GetMassProperties(1190)[3])
        if len(bs) != (4 if BOLTED else 2):
            raise SystemExit(f'expected {4 if BOLTED else 2} bodies, got {len(bs)}')
        bolts, hub, arm = bs[:-2], bs[-2], bs[-1]
        if BOLTED:      # the two smallest bodies are the bolts: steel
            comp = st.SolidManager.GetComponentAt(0, I())
            for k in range(comp.SolidBodyCount):
                cb = comp.GetSolidBodyAt(k, I())
                try:
                    nm = cb.SolidBodyName
                except Exception:
                    nm = '?'
                if 'HS_BOLTS' in str(nm).upper():      # the inserted bolt bodies only (the arm body can carry its HS_BOLT_BORES feature's name)
                    m = cb.GetDefaultMaterial
                    m.MaterialUnits = 0
                    m.MaterialName = 'steel'
                    for kk, v in (('EX', 2.0e11), ('NUXY', 0.29), ('GXY', 7.8e10), ('DENS', 7850.0), ('SIGYLD', 6.4e8)):
                        m.SetPropertyByName2(kk, v, False)
                    print(' bolt material', nm, cb.SetSolidBodyMaterial(m), flush=True)
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
        if BOLTED:      # lug faces and lug holes against the posts and the bolts: no penetration, no bond
            def near_lugs(b):
                lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
                return hi[1] > 287.5 and lo[1] < 294.2 and abs((lo[2] + hi[2]) / 2 - CZ) < 12.0 and (hi[0] < 153.0 or lo[0] > 188.0)
            lf = [f for f in faces(hub) if near_lugs(box(f))]
            pf = [f for f in faces(arm) if near_lugs(box(f))] + [f for bb in bolts for f in faces(bb)]
            err = I()
            cs2 = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, lf), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, pf), err)
            print(' lug contact set', cs2 is not None, 'faces hub', len(lf), 'arm+bolts', len(pf), 'err', err.value, flush=True)
        if err.value or cm.ContactSetCount == 0:
            raise SystemExit('contact failed')
        # no soft springs: the bonded lugs already hold the arm (setting them crashed SolidWorks intermittently)

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
