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
R1D = os.environ.get('ARM_R1D') == '1'
ARM_MODEL = os.environ.get('ARM_FEA_NAME', 'UA_ORGANIC_BONDED_v32.SLDPRT') if R1D else 'UA_ORGANIC_BONDED_v31.SLDPRT' if R1C else 'UA_ORGANIC_BONDED_v28.SLDPRT'
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
    REUSE = os.environ.get('HS_REUSE_HUB') == '1' and HUB.exists()      # keep the grooved hub other runs' models reference
    if not REUSE:
        shutil.copy(HUB_SRC, HUB)          # (the STEP import hung behind a dialog in a hidden instance)
    if GROOVE and not REUSE:      # option (d): the groove in the hub spigot (profile with organic_master's ridge): full depth theta 30-150 / 210-330, run-outs beyond
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
            # the 45 deg flank stops at the disc face (r 35.8, Y y0 + 4 = 302): the cut must not undercut the disc (2026-11-11: running it
            # on to (36.5, 302.7) notched a wedge into the disc underside, a knife edge under the arm's end face, 1,447 MPa at STOP_0)
            # rev C+ (shoulder thread, 2026-11-11): the 45 deg flank reaches r 35.8 at Y 301.9 (bottom ends at Y 300.4), then 0.1 of cylinder
            # to the flat disc face at Y 302.0; set HS_REVCP=0 for the earlier profile (bottom to Y 300.5, flank to r 35.8 at Y 302.0)
            ytop = YTOP
            prof = [(36.5, y0 - 0.7 * t30), (rb, y0 + depth * t30), (rb, ytop - depth), (35.8, ytop), (36.5, ytop)]
            with M.Sk(h, M.plane(h, 'X', HX, name + '_P'), name) as sk_:
                sk_.poly([(HX, y_, CZ + sgn * r_) for r_, y_ in prof])
                centerline_(sk_, (HX, 250.0, CZ), (HX, 340.0, CZ))
            revolve_(h, sk_.feat, name, None, True, angle=angle, mid=True, lo=0.01)
        REVCP = os.environ.get('HS_REVCP', '1') == '1'
        YTOP = 301.9 if REVCP else y0 + 4.0
        span = M.RIDGE_ARC[1] - M.RIDGE_ARC[0] + 10.0      # full depth 30-150 (ridge 35-145 plus 5 each end)
        # run-out depth past the full-depth end (deg -> mm); rev C+ is a revolved taper, modelled as 1-deg steps at the mid-step depth
        ro = ([(0.0, 1.5), (1.3, 1.48), (3.9, 1.28), (6.5, 0.90), (8.9, 0.34), (10.0, 0.0)] if REVCP else [(0.0, 1.5), (11.0, 0.0)])
        for sgn, tag in ((1, 'F'), (-1, 'B')):
            groove(f'SPIGOT_GROOVE{tag}', sgn, 1.5, span)
            for k in range(1, 11):
                dk = float(np.interp(k - 0.5 if REVCP else k, [a for a, _ in ro], [b for _, b in ro]))
                if dk > 0.02:
                    groove(f'GROOVE_RUNOUT{tag}{k}', sgn, dk, span + 2.0 * k)
            if REVCP and os.environ.get('HS_FILL', '1') == '1':      # spigot inside filled r 28 -> 25 over the groove arcs (wall under the groove 9.25)
                with M.Sk(h, M.plane(h, 'X', HX, f'SPIGOT_FILL{tag}_P'), f'SPIGOT_FILL{tag}') as sk_:
                    fr0 = float(os.environ.get('HS_FILL_R0', '25.0'))      # shoulder hub fd0cef8: r 23 (their 1.2 rounded fill ends not modelled)
                    sk_.poly([(HX, y_, CZ + sgn * r_) for r_, y_ in [(fr0, 296.0), (28.3, 296.0), (28.3, 302.3), (fr0, 302.3)]])
                    centerline_(sk_, (HX, 250.0, CZ), (HX, 340.0, CZ))
                revolve_(h, sk_.feat, f'SPIGOT_FILL{tag}', None, False, angle=130.0, mid=True, lo=0.01)
        h.ForceRebuild3(False)
        if os.environ.get('HS_ROUNDS', '1') == '1':      # 2026-11-11: hub rounds the shoulder thread is adding to the real hub
            rad = lambda p: m_.hypot(p[0] - HX, p[2] - CZ)
            r45 = float(os.environ.get('HS_GROOVE_R45', '0.4'))      # 45 deg-side bottom corner; up to 1.0 clears the ridge's top tip corner
            sets = [('GROOVE_BOT_ROUND', 0.4, lambda p: abs(rad(p) - 34.3) < 0.03 and abs(p[1] - (y0 + 1.5 * t30)) < 0.05),
                    ('GROOVE_BOT_ROUND45', r45, lambda p: abs(rad(p) - 34.3) < 0.03 and abs(p[1] - (YTOP - 1.5)) < 0.05),      # Y 300.4 rev C+, 300.5 before
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
                if M.fillet_edges(h, es, (rr,), nm) is None:      # edge by edge, re-selecting each time (edge handles go stale after a fillet)
                    ok, n0 = 0, len(es)
                    for i in range(n0):
                        es = M.edges_where(h, test)
                        if nm == 'LUG_ROOT_FILLET':
                            es = [e for e in es if abs(e.GetCurveParams3.StartPoint[0] - e.GetCurveParams3.EndPoint[0]) * 1000 < 0.01]
                        if i - ok >= len(es):
                            break
                        try:
                            ok += M.fillet_edges(h, [es[i - ok]], (rr,), f'{nm}{i}') is not None
                        except Exception as ex:
                            print(f'  {nm}{i}: {str(ex)[:80]}', flush=True)
                    print(f'  {nm}: {ok}/{n0} built edge by edge', flush=True)
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
            OP.post_z(d, f'HUB_POST{i}{"F" if sg > 0 else "B"}', (q[0], OP.HUB_POST_Y), sg, z0=CZ + sg * (OP.HUB_LUG_HZ + (OP.CL if R1D else 0.0)))      # R1d: the printed 0.1 clearance to the lug
    if R1C:
        for sg in (1, -1):
            OP.r1c_fins(d, sg, CZ + sg * (OP.HUB_LUG_HZ + (OP.CL if R1D else 0.0)))
        OP.r1d_post_trim(d)
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
    NUL_ = VARIANT(pythoncom.VT_DISPATCH, None)
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
        # no soft springs by default (setting them crashed SolidWorks intermittently, 2026-11-11). R1d gap cases (2026-11-12): with
        # the load flank 0.1-0.2 off, nothing restrains the arm along -Y at the start, so the static solve fails (error 24);
        # HS_SOFT_SPRING=1 turns the stabilising soft springs on for those runs only
        if os.environ.get('HS_SOFT_SPRING') == '1':
            try:
                st.StaticStudyOptions.UseSoftSpring = 1
                print(' soft springs on', st.StaticStudyOptions.UseSoftSpring, flush=True)
            except Exception as ex:
                print(' soft springs not set', str(ex)[:80], flush=True)

        def post(st_, res):
            rx = {}
            for args in ((0, NUL_, 0), (1, NUL_, 0)):      # fixture reactions (2026-11-12: the soft-spring sanity check needs them)
                try:
                    e_ = I()
                    q_ = res.GetReactionForces2(*args, e_)
                    q_ = list(q_[0] if isinstance(q_, tuple) and len(q_) == 2 else q_)
                    rx = dict(args=list(args[::2]), raw=[round(float(v), 3) for v in q_[-8:]], err=e_.value)
                    print(' reaction forces (last values; total Fx Fy Fz Fres expected last 4)', rx, flush=True)
                    break
                except Exception as ex:
                    rx = dict(error=str(ex)[:120])
            dx = {}
            for comp in (3,):      # resultant displacement, min/max over the model (mm)
                try:
                    e_ = I()
                    q_ = res.GetMinMaxDisplacement(comp, NUL_, 0, None if False else NUL_, e_) if False else res.GetMinMaxDisplacement(comp, 0, NUL_, 0, e_)
                    q_ = list(q_[0] if isinstance(q_, tuple) and len(q_) == 2 else q_)
                    dx = dict(raw=[round(float(v), 5) for v in q_], err=e_.value)
                except Exception as ex:
                    dx = dict(error=str(ex)[:120])
            print(' displacement min/max', dx, flush=True)
            return dict(model='hub as its own body, seat by contact, ' + ('lugs in frictionless contact with the posts and steel bolts (no preload)' if BOLTED else 'lugs bonded to posts'),
                        soft_springs=os.environ.get('HS_SOFT_SPRING') == '1', reaction=rx, displacement=dx)
        return post

    for k in ('STOP_0', 'STOP_124', 'G90'):
        for sfx in ('', '_fine'):
            if k + sfx in CASES:
                c = dict(CASES[k + sfx])
                c.update(part='hubseat', fix=[('fixed', ('plane', (HX, HUB_TOP, CZ), None))], pre_mesh=pre)   # hub top face
                ms = float(os.environ.get('HS_SEAT_MESH', '0.35' if R1D else '0'))
                if ms > 0:      # R1d (review 2026-11-12): mesh control on the ridge, groove, collar foot and bore faces (any face meeting the seat
                    # box, up to 400 mm2 so the large skin and spigot faces are left at the global size)
                    c['ctrl'] = list(c.get('ctrl', [])) + [(('touch', [128.0, 297.5, -40.0, 213.0, 302.05, 50.0], float(os.environ.get('HS_SEAT_MESH_AMAX', '150'))), ms)]      # 2026-11-12: ridge and groove faces only (the wider box gave 2.4 M nodes)
                CASES['HS_' + k + sfx] = c


if __name__ == '__main__' and sys.argv[1:] == ['build']:
    build()
