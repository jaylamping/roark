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
HUB_SRC = CAD / '_wip' / 'hub_ref' / 'upper_arm_hub_left.SLDPRT'      # today's hub, copied from the left-arm worktree (PR #28) 2026-11-12
HUB_SRC_SHA = '7b857f61855fb2a65fd4e6d73981605c4b9f12747af1e5abcfd2a75bc5ddcb0b'   # the native part its STEP/STL exports were recorded from
HUB = F / (os.environ.get('HS_HUB_FILE', 'HUB_GROOVE.SLDPRT') if os.environ.get('HS_GROOVE') == '1' else 'HUB_TODAY.SLDPRT')
R1C = os.environ.get('ARM_R1C') == '1'
R1D = os.environ.get('ARM_R1D') == '1'
ARM_MODEL = os.environ.get('ARM_FEA_NAME', 'UA_ORGANIC_BONDED_v32.SLDPRT') if R1D else 'UA_ORGANIC_BONDED_v31.SLDPRT' if R1C else 'UA_ORGANIC_BONDED_v28.SLDPRT'
GROOVE = os.environ.get('HS_GROOVE') == '1'      # option (d): groove in the hub spigot
BOLTED = os.environ.get('HS_BOLTED') == '1'     # lugs in frictionless contact, steel M3 bodies bonded in the post bores, no preload
MODEL = F / os.environ.get('HS_MODEL', ('UA_HUBSEAT_v31' if R1C else 'UA_HUBSEAT_v28') + ('_bolted' if BOLTED else '') + '.SLDPRT')
BOLTS = F / 'HS_BOLTS.SLDPRT'
# HS_INSERT_MODEL (2026-11-12, coordinator "M"): the lug bolt joint as built. Front post: the Ruthex M3 x 5.7 insert (Dia 4.0
# hole, so the insert is a Dia 4.0 x 5.7 brass sleeve; its knurl crests sit in the PETG) bonded in the post from the lug face, the
# bolt bonded inside it, the rest of the 6.5 insert hole and the Dia 3.2 pilot left open. Back post: Dia 3.4 clearance hole and the
# Dia 6.0 counterbore 7 below the lug face (R1d); the M3 x 25 DIN 912 bolt (head Dia 5.5 x 3) in no-penetration contact there,
# head underside on its seat, shank in the clearance hole, and in the hub lug hole (Dia 3.4) as before. No preload.
INSERTS_ON = os.environ.get('HS_INSERT_MODEL') == '1'
if INSERTS_ON:
    BOLTS = F / 'HS_BOLTS_INS.SLDPRT'
INSERTS = F / 'HS_INSERTS.SLDPRT'
# HS_SHIM (2026-11-12, R1e): the printed PETG shim ring as its own body, r 36.2-38.4 x t, between the arm's lowered end face
# (ARM_END_DROP = t) and the hub disc (Y 302). Held on the disc by the touching-face bond (friction keeps it there); no-penetration
# contact against the arm's end face, so it carries compression only.
SHIM_T = float(os.environ.get('HS_SHIM', '0'))
SHIM = F / 'HS_SHIM.SLDPRT'
HUB_JOINT_Y = 302.0
_SLOT_CL = float(os.environ.get('ARM_SLOT_CL', '0.1'))      # R1f (D3): 0.5 per side for the lug plates
LUG_FACE_F = 5.985875 + 5.0 + _SLOT_CL      # front / back post faces at the lug (HUB_LUG_HZ 5.0 + the printed clearance)
LUG_FACE_B = 5.985875 - 5.0 - _SLOT_CL
BOLT_SEAT = LUG_FACE_B - 7.0
PADS_ON = os.environ.get('HS_PADS') == '1'      # R1d gap cases: four soft bonded pads stabilise the arm (soft springs crash SolidWorks here)
PADS = F / 'HS_PADS.SLDPRT'
PAD_PTS = [(147.5, 15.0), (193.5, 15.0), (147.5, -15.0), (193.5, -15.0)]      # X, Z - CZ: post-top strips under the hub fill (theta 147 / 33 / 213 / 327)
PAD_E = float(os.environ.get('HS_PAD_E', '0.05'))      # MPa: 4 pads Dia 1.8 x 0.3 give ~1.7 N/mm axially
HX, CY, CZ = 170.49, 209.860668, 5.985875
HUB_TOP = 319.86


def build():
    sys.path.insert(0, str(ARM))
    os.chdir(ARM)
    import organic_parts as OP
    from organic_master import L, NUL, sw, bodies
    REUSE = os.environ.get('HS_REUSE_HUB') == '1' and HUB.exists()      # keep the grooved hub other runs' models reference
    if not REUSE:
        import hashlib
        if hashlib.sha256(HUB_SRC.read_bytes()).hexdigest() != HUB_SRC_SHA:
            raise SystemExit(f'{HUB_SRC} is not the hub this model was built from (SHA-256 differs)')
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
        GFULL = os.environ.get('HS_GROOVE_FULL') == '1'      # 2026-11-12: full-ring groove for the ring ridge
        if GFULL:
            groove('SPIGOT_GROOVE_RING', 1, 1.5, 360.0)
        for sgn, tag in ((1, 'F'), (-1, 'B')):
            if not GFULL:
                groove(f'SPIGOT_GROOVE{tag}', sgn, 1.5, span)
            for k in (range(1, 11) if not GFULL else ()):
                dk = float(np.interp(k - 0.5 if REVCP else k, [a for a, _ in ro], [b for _, b in ro]))
                if dk > 0.02:
                    groove(f'GROOVE_RUNOUT{tag}{k}', sgn, dk, span + 2.0 * k)
            if REVCP and os.environ.get('HS_FILL', '1') == '1' and not (GFULL and sgn < 0):      # spigot inside filled r 28 -> 25 over the groove arcs (wall under the groove 9.25); full ring: once, 360 deg
                with M.Sk(h, M.plane(h, 'X', HX, f'SPIGOT_FILL{tag}_P'), f'SPIGOT_FILL{tag}') as sk_:
                    fr0 = float(os.environ.get('HS_FILL_R0', '25.0'))      # shoulder hub fd0cef8: r 23 (their 1.2 rounded fill ends not modelled)
                    sk_.poly([(HX, y_, CZ + sgn * r_) for r_, y_ in [(fr0, 296.0), (28.3, 296.0), (28.3, 302.3), (fr0, 302.3)]])
                    centerline_(sk_, (HX, 250.0, CZ), (HX, 340.0, CZ))
                revolve_(h, sk_.feat, f'SPIGOT_FILL{tag}', None, False, angle=360.0 if GFULL else 130.0, mid=True, lo=0.01)
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
            OP.post_z(d, f'HUB_POST{i}{"F" if sg > 0 else "B"}', (q[0], OP.HUB_POST_Y), sg, z0=CZ + sg * (OP.HUB_LUG_HZ + (OP.SLOT_CL if R1D else 0.0)))      # R1d: the printed 0.1 clearance to the lug
    if R1C:
        for sg in (1, -1):
            OP.r1c_fins(d, sg, CZ + sg * (OP.HUB_LUG_HZ + (OP.SLOT_CL if R1D else 0.0)))
        OP.r1d_post_trim(d)
        for sg in (1, -1):
            OP.r1d_slot_break(d, sg, CZ + sg * (OP.HUB_LUG_HZ + (OP.SLOT_CL if R1D else 0.0)))      # ARM_SLOT_BREAK only
        if OP.r1f_on():      # R1f (D3 extended lugs): post-to-wall webs, the seam pocket and the root relief, as in the printed halves
            for sg in (1, -1):
                zl_ = CZ + sg * (OP.HUB_LUG_HZ + OP.SLOT_CL)
                OP.r1f_lug_web(d, sg, zl_)
                OP.r1f_lug_pocket(d, sg, zl_)
                OP.r1f_plate_lump(d, sg, zl_)      # ARM_PLATE_LUMP: the plates inside their outline only (FEA)
    if BOLTED and INSERTS_ON:      # the holes as in the printed halves (organic_parts.upper_half)
        OP.z_cyl(d, 'HS_BACK_HOLES', OP.HUB_COLS, 1.7, CZ - 60.0, LUG_FACE_B + 0.5, True)
        OP.z_cyl(d, 'HS_BACK_CBORES', OP.HUB_COLS, 3.0, CZ - 60.0, BOLT_SEAT, True)
        OP.z_cyl(d, 'HS_INSERT_HOLES', OP.HUB_COLS, 2.0, LUG_FACE_F - 0.01, LUG_FACE_F + 6.5, True)
        OP.z_cyl(d, 'HS_PILOTS', OP.HUB_COLS, 1.6, LUG_FACE_F + 6.4, LUG_FACE_F + 10.0, True)
        d.ForceRebuild3(False)
        d.Save3(1, e, w)
        import organic_master as M
        b = M.new_part(BOLTS)
        for i, q in enumerate(OP.HUB_COLS):
            with M.Sk(b, M.plane(b, 'Z', BOLT_SEAT - 1.5, f'HEAD{i}_P'), f'HEAD{i}') as s_:
                s_.circle((q[0], q[1], BOLT_SEAT - 1.5), 2.75)
            M.feat(b, s_.feat, f'HEAD{i}', 3.0, False, mode=M.MID, lo=0.01)
            with M.Sk(b, M.plane(b, 'Z', BOLT_SEAT + 12.5, f'BOLT{i}_P'), f'BOLT{i}') as s_:
                s_.circle((q[0], q[1], BOLT_SEAT + 12.5), 1.5)
            M.feat(b, s_.feat, f'BOLT{i}', 25.0, False, mode=M.MID, lo=0.01)
        e2, w2 = L(), L()
        b.Save3(1, e2, w2)
        print('  bolt bodies', len(bodies(b)), flush=True)
        sw.CloseDoc(b.GetTitle)
        n = M.new_part(INSERTS)
        for i, q in enumerate(OP.HUB_COLS):
            zm = LUG_FACE_F + 2.85
            with M.Sk(n, M.plane(n, 'Z', zm, f'INSERT{i}_P'), f'INSERT{i}') as s_:
                s_.circle((q[0], q[1], zm), 2.0)
                s_.circle((q[0], q[1], zm), 1.5)
            M.feat(n, s_.feat, f'INSERT{i}', 5.7, False, mode=M.MID, lo=0.01)
        e2, w2 = L(), L()
        n.Save3(1, e2, w2)
        print('  insert bodies', len(bodies(n)), flush=True)
        sw.CloseDoc(n.GetTitle)
        e, w = L(), L()
        d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
    elif BOLTED:      # M3 bores through both posts at each lug (the real holes are 3.4 / inserts; here the bolt fills its bore)
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
        if INSERTS_ON:
            fi = d.InsertPart3(str(INSERTS), 1, '')
            d.ForceRebuild3(False)
            print('  inserts', fi is not None, bodies(d), flush=True)
    if SHIM_T > 0:
        d.Save3(1, e, w)
        import organic_master as M
        sdoc = M.new_part(SHIM)
        ym = HUB_JOINT_Y - SHIM_T / 2
        with M.Sk(sdoc, M.plane(sdoc, 'Y', ym, 'SHIM_P'), 'SHIM') as s_:
            s_.circle((HX, ym, CZ), 38.4)
            s_.circle((HX, ym, CZ), 36.2)
        M.feat(sdoc, s_.feat, 'SHIM', SHIM_T, False, mode=M.MID, lo=0.01)
        e2, w2 = L(), L()
        sdoc.Save3(1, e2, w2)
        sw.CloseDoc(sdoc.GetTitle)
        e, w = L(), L()
        d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
        fs_ = d.InsertPart3(str(SHIM), 1, '')
        d.ForceRebuild3(False)
        print('  shim', fs_ is not None, SHIM_T, bodies(d), flush=True)
    if PADS_ON:      # pads from the trimmed post tops (Y 295.7) to the hub fill's underside (Y 296.0)
        d.Save3(1, e, w)
        import organic_master as M
        pdoc = M.new_part(PADS)
        for i, (x_, dz) in enumerate(PAD_PTS):
            with M.Sk(pdoc, M.plane(pdoc, 'Y', 295.85, f'PAD{i}_P'), f'PAD{i}') as s_:
                s_.circle((x_, 295.85, CZ + dz), 0.9)
            M.feat(pdoc, s_.feat, f'PAD{i}', 0.3, False, mode=M.MID, lo=0.01)
        e2, w2 = L(), L()
        pdoc.Save3(1, e2, w2)
        sw.CloseDoc(pdoc.GetTitle)
        e, w = L(), L()
        d = sw.OpenDoc6(str(MODEL), 1, 1, '', e, w)
        fp = d.InsertPart3(str(PADS), 1, '')
        d.ForceRebuild3(False)
        print('  pads', fp is not None, bodies(d), flush=True)
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
        if os.environ.get('FEA_EXISTING_STUDY'):      # saved study: its contacts and materials are already in it
            return post
        bs = sorted(d.GetBodies2(0, True), key=lambda b: b.GetMassProperties(1190)[3])
        n_pads = sum('HS_PADS' in b.Name.upper() for b in bs)      # pads are found by name, whatever HS_PADS says
        n_ins = sum('HS_INSERTS' in b.Name.upper() for b in bs)
        n_shim = sum('HS_SHIM' in b.Name.upper() for b in bs)
        want = (4 if BOLTED else 2) + n_pads + n_ins + n_shim
        if len(bs) != want:
            raise SystemExit(f'expected {want} bodies, got {len(bs)}')
        hub, arm = bs[-2], bs[-1]
        bolts = [b for b in bs[:-2] if 'HS_BOLTS' in b.Name.upper()] if (n_pads or n_ins) else bs[:-2]
        inserts = [b for b in bs[:-2] if 'HS_INSERTS' in b.Name.upper()]
        shims = [b for b in bs[:-2] if 'HS_SHIM' in b.Name.upper()]
        print(' bodies', [b.Name for b in bs], 'bolts', len(bolts), flush=True)
        if BOLTED:      # the two smallest bodies are the bolts: steel
            comp = st.SolidManager.GetComponentAt(0, I())
            for k in range(comp.SolidBodyCount):
                cb = comp.GetSolidBodyAt(k, I())
                try:
                    nm = cb.SolidBodyName
                except Exception:
                    nm = '?'
                if 'HS_PADS' in str(nm).upper():      # soft stabilising pads
                    m = cb.GetDefaultMaterial
                    m.MaterialUnits = 0
                    m.MaterialName = 'soft pad'
                    for kk, v in (('EX', PAD_E * 1e6), ('NUXY', 0.3), ('GXY', PAD_E * 1e6 / 2.6), ('DENS', 100.0), ('SIGYLD', 1.0e6)):
                        m.SetPropertyByName2(kk, v, False)
                    print(' pad material', nm, cb.SetSolidBodyMaterial(m), flush=True)
                if 'HS_INSERTS' in str(nm).upper():      # brass inserts
                    m = cb.GetDefaultMaterial
                    m.MaterialUnits = 0
                    m.MaterialName = 'brass'
                    for kk, v in (('EX', 1.0e11), ('NUXY', 0.34), ('GXY', 3.7e10), ('DENS', 8500.0), ('SIGYLD', 2.4e8)):
                        m.SetPropertyByName2(kk, v, False)
                    print(' insert material', nm, cb.SetSolidBodyMaterial(m), flush=True)
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

        D3_ = os.environ.get('HS_D3') == '1'      # 2026-11-12: hub rev D3 lugs (to Y 297.6, X offset 36.35) in the lug set, not the seat set

        def lugzone(b):
            lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
            return hi[1] > 287.5 and lo[1] < (297.9 if D3_ else 294.2) and abs((lo[2] + hi[2]) / 2 - CZ) < 12.0 and (hi[0] < 153.0 or lo[0] > 188.0)

        hf = [f for f in faces(hub) if near_seat(box(f)) and not (D3_ and lugzone(box(f)))]
        af = [f for f in faces(arm) if near_seat(box(f)) and not (D3_ and lugzone(box(f)))]
        cm = st.ContactManager
        err = I()
        cs = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, hf), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, af), err)
        print(' seat contact set', cs is not None, 'faces hub', len(hf), 'arm', len(af), 'err', err.value, flush=True)
        if BOLTED:      # lug faces and lug holes against the posts and the bolts: no penetration, no bond
            near_lugs = lugzone
            lf = [f for f in faces(hub) if near_lugs(box(f))]
            def ins_mouth(b):      # the insert's end face at the lug face: the only insert face the hub lug can reach
                return abs(b[2] - LUG_FACE_F) < 0.02 and abs(b[5] - LUG_FACE_F) < 0.02
            pf = [f for f in faces(arm) if near_lugs(box(f))] + [f for bb in bolts for f in faces(bb)] + [f for bb in inserts for f in faces(bb) if ins_mouth(box(f))]
            err = I()
            cs2 = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, lf), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, pf), err)
            print(' lug contact set', cs2 is not None, 'faces hub', len(lf), 'arm+bolts', len(pf), 'err', err.value, flush=True)
        if BOLTED and inserts:      # explicit bonds (2026-11-12: with the global bond alone an insert came loose, 5e6 mm displacement):
            # insert outside to the arm's insert hole, insert bore to the bolt shank. Contact set type 1 = bonded (type 0 = no
            # penetration; swsContactSetTypeStaticNonLinear_e)
            def wid(b):
                return max(abs(b[3] - b[0]), abs(b[4] - b[1]))
            def in_ins_zone(b):
                return min(b[2], b[5]) > LUG_FACE_F - 0.05 and max(b[2], b[5]) < LUG_FACE_F + 6.55 and any(abs((b[0] + b[3]) / 2 - x0) < 0.5 for x0 in (147.5, 193.5)) and abs((b[1] + b[4]) / 2 - 292.0) < 0.5
            ins_out = [f for bb in inserts for f in faces(bb) if abs(wid(box(f)) - 4.0) < 0.3 and abs(box(f)[5] - box(f)[2]) > 1.0]
            ins_in = [f for bb in inserts for f in faces(bb) if abs(wid(box(f)) - 3.0) < 0.3 and abs(box(f)[5] - box(f)[2]) > 1.0]
            hole = [f for f in faces(arm) if in_ins_zone(box(f)) and abs(wid(box(f)) - 4.0) < 0.3 and abs(box(f)[5] - box(f)[2]) > 1.0]
            shank = [f for bb in bolts for f in faces(bb) if abs(wid(box(f)) - 3.0) < 0.3 and abs(box(f)[5] - box(f)[2]) > 5.0]
            for nm_, a_, b_ in (('insert to arm hole', ins_out, hole), ('bolt shank to insert bore', shank, ins_in)):
                err = I()
                cb_ = cm.CreateContactSet(1, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, a_), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, b_), err)
                try:
                    ty_ = cb_.ContactSetType
                except Exception:
                    ty_ = '?'
                print(' bonded set', nm_, cb_ is not None, 'faces', len(a_), len(b_), 'err', err.value, 'type', ty_, flush=True)
                if cb_ is None or err.value or not a_ or not b_:
                    raise SystemExit(f'bonded set failed: {nm_}')
        if shims:      # the shim's underside against the arm's lowered end face: no penetration (compression only)
            sb_ = [f for bb in shims for f in faces(bb) if abs(box(f)[1] - box(f)[4]) < 0.01 and min(box(f)[1], box(f)[4]) < HUB_JOINT_Y - 0.05]
            # every flat arm face at the shim's underside level (2026-11-12: the end face is split at the seam into one face per
            # half; matching only one left the other half globally bonded to the shim, which then carried the stop's twist)
            yb_ = min(min(box(g)[1], box(g)[4]) for g in sb_) if sb_ else None
            ae_ = [f for f in faces(arm) if abs(box(f)[1] - box(f)[4]) < 0.02 and abs((box(f)[1] + box(f)[4]) / 2 - yb_) < 0.05] if sb_ else []
            for f in ae_:
                print('  arm end face for the shim set: box', [round(v, 2) for v in box(f)], flush=True)
            err = I()
            cs4 = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, sb_), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, ae_), err)
            print(' shim contact set', cs4 is not None, 'faces shim', len(sb_), 'arm end face', len(ae_), 'err', err.value, flush=True)
            if cs4 is None or not sb_ or not ae_ or err.value:
                raise SystemExit('shim contact failed')
            # 2026-11-12: the shim-body STOP_0 showed the shim / end-face contact sticking tangentially (about 10 N.m of the stop's
            # twist through the shim, lugs unloaded). Log every contact set's friction settings
            for k_ in range(cm.ContactSetCount):
                c_ = cm.GetContactSetAt(k_)
                fr_ = {}
                for nm_ in ('IncludeFriction', 'FrictionCoefficient', 'Friction', 'UseFriction'):
                    try:
                        fr_[nm_] = getattr(c_, nm_)
                    except Exception:
                        pass
                print(' contact set', k_, 'friction', fr_, flush=True)
            # (read only: property puts from our out-of-process scripts have faulted SolidWorks before)
        for k_ in range(cm.ContactSetCount):
            try:
                cs_ = cm.GetContactSetAt(k_)
                print(' contact set', k_, cs_.ContactName, 'type', cs_.ContactSetType, flush=True)
            except Exception as ex:
                print(' contact set', k_, 'not read', str(ex)[:60], flush=True)
        if BOLTED and inserts:      # bolt head on its seat and shank in the back clearance hole: no penetration, no bond
            def near_back_hole(b):
                lo, hi = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])), (max(b[0], b[3]), max(b[1], b[4]), max(b[2], b[5]))
                return (hi[2] < LUG_FACE_B + 0.6 and any(lo[0] > x0 - 3.1 and hi[0] < x0 + 3.1 for x0 in (147.5, 193.5))
                        and lo[1] > 292.0 - 3.1 and hi[1] < 292.0 + 3.1)
            hf3 = [f for f in faces(arm) if near_back_hole(box(f))]
            bf3 = [f for bb in bolts for f in faces(bb)]
            err = I()
            cs3 = cm.CreateContactSet(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, bf3), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, hf3), err)
            print(' bolt seat contact set', cs3 is not None, 'faces bolts', len(bf3), 'arm (back hole, counterbore)', len(hf3), 'err', err.value, flush=True)
            if not hf3:
                raise SystemExit('no back-hole faces found')
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

        return post

    for k in ('STOP_0', 'STOP_124', 'G90', 'LC2', 'LC2M', 'G90Y'):      # LC2 / LC2M (2026-11-12): YAW_17, the RS02's 17 N.m peak about the hub axis, + / -
        for sfx in ('', '_fine'):
            if k + sfx in CASES:
                c = dict(CASES[k + sfx])
                c.update(part='hubseat', fix=[('fixed', ('plane', (HX, HUB_TOP, CZ), None))], pre_mesh=pre)   # hub top face
                ms = float(os.environ.get('HS_SEAT_MESH', '0.35' if R1D else '0'))
                if ms > 0:      # R1d (review 2026-11-12): mesh control on the ridge, groove, collar foot and bore faces (any face meeting the seat
                    # box, up to 400 mm2 so the large skin and spigot faces are left at the global size)
                    c['ctrl'] = list(c.get('ctrl', [])) + [(('touch', [128.0, 297.5, -40.0, 213.0, 302.05, 50.0], float(os.environ.get('HS_SEAT_MESH_AMAX', '150'))), ms)]      # 2026-11-12: ridge and groove faces only (the wider box gave 2.4 M nodes)
                pm = float(os.environ.get('HS_POST_MESH', '0'))
                if pm > 0:      # 2026-11-12: the hub lugs and roots, the arm posts they bear on and the fins where they meet the posts (Y 268-297.5, |Z - CZ| < 12), both sides
                    for x0, x1 in ((128.0, 153.5), (187.5, 213.0)):
                        c['ctrl'] = list(c.get('ctrl', [])) + [(('touch', [x0, 268.0, CZ - 12.0, x1, 297.5, CZ + 12.0], float(os.environ.get('HS_POST_MESH_AMAX', '150'))), pm)]
                lfm = float(os.environ.get('HS_LUGFACE_MESH', '0') or 0)
                if lfm > 0:      # 2026-11-12 (D3): the lug bearing faces themselves, both bodies, whatever their area: flat faces in the planes
                    # Z = CZ +- 5.0 (lug faces; ours line-to-line with the plates lumped) over the lug zones. The merged post / web faces are
                    # too big for the post control's area limit, and letting big faces into that control blew the mesh up (640-720 k nodes)
                    for zf in (CZ + 5.0, CZ - 5.0):
                        for x0, x1 in ((HX - 37.0, HX - 17.0), (HX + 17.0, HX + 37.0)):
                            c['ctrl'] = list(c.get('ctrl', [])) + [(('zflat', zf, 0.15, [x0, 286.0, x1, 298.0]), lfm)]
                # 2026-11-12: lug-root refinement (coordinator: the settled repeat case). HS_ROOT_MESH, or a flag file
                # cad/_wip/hs_root_mesh/<run folder>.txt holding the size, puts that size on every face meeting each lug-root box:
                # the R1.2 Z-root fillets, the lug faces next to them, and any small adjoining face (under HS_ROOT_MESH_AMAX mm2;
                # the large spigot underside face stays at its own size)
                flag = CAD / '_wip' / 'hs_root_mesh' / (Path(os.environ.get('ARM_FEA_DIR', 'x')).name + '.txt')
                rm = os.environ.get('HS_ROOT_MESH') or (flag.read_text().strip() if flag.exists() else '')
                ram = os.environ.get('HS_ROOT_MESH_AMAX', '150')
                gel = None
                if ',' in rm:      # "size,max face area[,global size]" (2026-11-12: at 150 mm2 the lug faces came in too, 1.18 M nodes; 20 keeps the
                    # R1.2 fillets; 0.3 on the fillets at global 4.0 still gave 458 k nodes, over the solver memory limit, so the refined runs
                    # coarsen the global size, which is far from the joint)
                    parts_ = rm.split(',')
                    rm, ram = parts_[0], parts_[1]
                    gel = float(parts_[2]) if len(parts_) > 2 else None
                if rm:
                    for x0, x1 in ((139.5, 149.0), (192.0, 201.5)):
                        # FIRST in the list: a face already under a control keeps it (a later control on the same face had no effect,
                        # case r1d11_g01_stop_rep meshed to the same node count as without it)
                        c['ctrl'] = [(('touch', [x0, 292.5, CZ - 8.5, x1, 296.6, CZ + 8.5], float(ram)), float(rm))] + list(c.get('ctrl', []))
                # 2026-11-12: groove-region refinement (coordinator, the settled 0.2 gap run): HS_GROOVE_MESH or a flag file
                # cad/_wip/hs_groove_mesh/<run folder>.txt. The joint faces are full rings, so this refines every face meeting the
                # groove band (Y 298.7-302.05, both bodies), not only the θ of the peak
                gflag = CAD / '_wip' / 'hs_groove_mesh' / (Path(os.environ.get('ARM_FEA_DIR', 'x')).name + '.txt')
                gm = os.environ.get('HS_GROOVE_MESH') or (gflag.read_text().strip() if gflag.exists() else '')
                if gm:
                    c['ctrl'] = [(('touch', [128.0, 298.7, -40.0, 213.0, 302.05, 50.0], 2000.0), float(gm))] + list(c.get('ctrl', []))      # first: see the root control
                # 2026-11-12: the arm bore (r 35.9) and the hub spigot (r 35.85) are 0.05 apart radially. Their cylinder faces are too
                # large for the seat control, so they meshed at the global size; at 5.0 the facets sag about 0.09 (L^2 / 8r) and the
                # bodies overlapped (STOP_124 at 5.0: 8.8 GPa at the bore, θ 182). HS_BORE_MESH (default 1.5 whenever the global size
                # is over 4.5): that size on every cylinder face of r 34.5-37.0 in the joint band not already controlled
                bm = float(os.environ.get('HS_BORE_MESH', '0') or 0)
                gsz = gel if (rm and gel) else float(os.environ.get('HS_GLOBAL_EL', '0') or 0)
                if bm <= 0 and gsz > 4.5:      # (at 4.0 the bore / spigot nodes were checked: no overlap, arm r >= 35.900, hub r <= 35.793)
                    bm = 1.5
                if bm > 0:
                    c['ctrl'] = list(c.get('ctrl', [])) + [(('cylr', 34.5, 37.0, [128.0, 288.0, -40.0, 213.0, 303.0, 50.0]), bm)]      # LAST: faces under the seat / root controls keep theirs
                if rm and gel:
                    c['el'] = gel
                elif os.environ.get('HS_GLOBAL_EL'):      # 2026-11-12: coarser away from the joint (direct sparse memory); the seat control stays
                    c['el'] = float(os.environ['HS_GLOBAL_EL'])
                CASES['HS_' + k + sfx] = c


def zfillet(src, dst):
    """Rev D lug-root fillet on our FEA hub (2026-11-12, the shoulder thread's bc16e97 change, same selection as their
    build_parts.hub_lug_roots): R1.2 where the lugs' Z faces (|Z - CZ| = 5) meet the spigot underside at Y 296, r 18-31.5 from the
    hub axis, both lugs. Copies src to dst in F, fillets, saves, and writes dst's STL for the post-processing."""
    sys.path.insert(0, str(ARM))
    os.chdir(ARM)
    import math as m_
    from organic_master import L, sw, edges_where, fillet_edges, fine_stl
    shutil.copy(F / src, F / dst)
    e, w = L(), L()
    d = sw.OpenDoc6(str(F / dst), 1, 1, '', e, w)
    if d is None:
        raise SystemExit(f'open failed: {dst} {e.value} {w.value}')
    r_ = lambda q: m_.hypot(q[0] - HX, q[2] - CZ)
    roots = edges_where(d, lambda q: abs(q[1] - 296.0) < 0.05 and abs(abs(q[2] - CZ) - 5.0) < 0.1 and 18.0 < r_(q) < 31.5)
    print('  LUG_ZROOTS edges', len(roots), flush=True)
    if len(roots) < 4:
        raise SystemExit('expected at least 4 Z-root edges')
    n0 = d.FeatureManager.GetFeatureCount(True) if hasattr(d.FeatureManager, 'GetFeatureCount') else None
    fillet_edges(d, roots, [1.2], 'LUG_ZROOTS')
    ok = d.FeatureByName('LUG_ZROOTS') is not None
    print('  LUG_ZROOTS feature', ok, flush=True)
    if not ok:
        raise SystemExit('fillet failed')
    d.ForceRebuild3(False)
    e, w = L(), L()
    d.Save3(1, e, w)
    fine_stl(d, F / (Path(dst).stem + '.STL'))
    print('  saved', dst, 'and its STL', flush=True)
    sw.CloseDoc(d.GetTitle)


def d3hub(src, dst):
    """Hub rev D3 lugs on our FEA hub (2026-11-12; shoulder thread 22ead5b, A_HUB_LUGS.md "Rev D3 as built"): each lug grown out
    from its outer face (X offset 29.5) to a straight face at X offset 34.4 over Y 288-294.5, stepped out to 36.35 over Y 294.5-297.6
    with a 45 deg chamfer from (36.35, Y 296.7) to the land (35.45, Y 297.6), at the lug's own thickness (|Z - CZ| <= 5); then the
    R1.2 Z roots along Y 296 from the bore out to the land (r up to 35.9) and R0.5 where the step underside (Y 294.5) meets the
    outer face (X offset 34.4). Built on the hub before its Z-root fillet (src), saved as dst with its STL."""
    sys.path.insert(0, str(ARM))
    os.chdir(ARM)
    import math as m_
    import organic_master as M
    from organic_master import L, sw, edges_where, fillet_edges, fine_stl
    shutil.copy(F / src, F / dst)
    e, w = L(), L()
    d = sw.OpenDoc6(str(F / dst), 1, 1, '', e, w)
    if d is None:
        raise SystemExit(f'open failed: {dst} {e.value} {w.value}')
    if os.environ.get('HS_D3_STEP') == '1':      # D3 candidate 22ead5b (step and column)
        prof = [(29.0, 288.0), (34.4, 288.0), (34.4, 294.5), (36.35, 294.5), (36.35, 296.7), (35.45, 297.6), (29.0, 297.6)]
    else:      # the adoption form (2026-11-13): one straight outer face at X offset 34.4 up to the spigot underside
        prof = [(29.0, 288.0), (34.4, 288.0), (34.4, 296.3), (29.0, 296.3)]
    for k, side in enumerate((-1, 1)):
        name = f'D3_LUGEXT{k}'
        with M.Sk(d, M.plane(d, 'Z', CZ, name + '_P'), name) as s_:
            s_.poly([(HX + side * o, y, CZ) for o, y in prof])
        M.feat(d, s_.feat, name, 10.0, False, mode=M.MID, lo=0.01)
    d.ForceRebuild3(False)
    from swg import bodies as bodies_
    print('  D3 hub bodies', len(bodies_(d)), flush=True)
    if len(bodies_(d)) != 1:
        raise SystemExit('lug extensions did not merge into the hub')
    r_ = lambda q: m_.hypot(q[0] - HX, q[2] - CZ)
    # src already carries the R1.2 Z roots out to r 31.5 (HUB_RING_ZF); fillet only the new stretch along the extension. One
    # selection of all 16 edges (from the unfilleted hub) built nothing (2026-11-12)
    roots = edges_where(d, lambda q: abs(q[1] - 296.0) < 0.05 and abs(abs(q[2] - CZ) - 5.0) < 0.1 and 31.0 < r_(q) < 35.0)
    print('  D3 Z-root edges (new stretch)', len(roots), flush=True)
    built = 0
    if roots:
        fillet_edges(d, roots, [1.2], 'D3_ZROOTS')
        built = d.FeatureByName('D3_ZROOTS') is not None
        if not built:
            for i_, e_ in enumerate(roots):
                fillet_edges(d, [e_], [1.2], f'D3_ZROOT{i_}')
                built += d.FeatureByName(f'D3_ZROOT{i_}') is not None
    print('  D3_ZROOTS built', built, 'of', len(roots), '(unfilleted stretches stay sharp: hub-root peaks there are a model edge)', flush=True)
    if os.environ.get('HS_D3_STEP') == '1':
        steps = edges_where(d, lambda q: abs(q[1] - 294.5) < 0.05 and abs(abs(q[0] - HX) - 34.4) < 0.05 and abs(q[2] - CZ) < 4.9)
        print('  D3 step-corner edges', len(steps), flush=True)
        if steps:
            fillet_edges(d, steps, [0.5], 'D3_STEPR05')
            print('  D3_STEPR05', d.FeatureByName('D3_STEPR05') is not None, flush=True)
    else:      # D3b (2026-11-13): R0.8 outward root where the lug's outer face (X offset 34.4) meets the spigot underside (Y 296)
        outr = edges_where(d, lambda q: abs(q[1] - 296.0) < 0.05 and abs(abs(q[0] - HX) - 34.4) < 0.05 and abs(q[2] - CZ) < 4.9)
        print('  D3b outward-root edges', len(outr), flush=True)
        if outr:
            fillet_edges(d, outr, [0.8], 'D3B_OUTR08')
            print('  D3B_OUTR08', d.FeatureByName('D3B_OUTR08') is not None, flush=True)
    d.ForceRebuild3(False)
    e, w = L(), L()
    d.Save3(1, e, w)
    fine_stl(d, F / (Path(dst).stem + '.STL'))
    print('  saved', dst, 'and its STL', flush=True)
    sw.CloseDoc(d.GetTitle)


if __name__ == '__main__' and sys.argv[1:2] == ['d3hub']:
    d3hub(sys.argv[2], sys.argv[3])
elif __name__ == '__main__' and sys.argv[1:] == ['build']:
    build()
elif __name__ == '__main__' and sys.argv[1:2] == ['zfillet']:
    zfillet(sys.argv[2], sys.argv[3])
