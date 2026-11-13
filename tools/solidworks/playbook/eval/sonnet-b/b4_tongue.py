"""B4: tongue in a slot, contact study. Run: python b4_tongue.py [quick]"""
import json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from scipy.spatial import Delaunay
from swkit import *
from swfea import BONDED, NO_PENETRATION, PETG, SOLVER_DIRECT, static, _arr

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
OUT.mkdir(parents=True, exist_ok=True)
PAD = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
F = 80.0
# hand: rigid tongue, contacts at the top edge of the +X wall (z 20) and the bottom edge of the tongue on the -X wall (z 8.1)
Z_LOAD, Z_TOP, Z_BOT = 35.0, 20.0, 8.1
F_TOP = F * (Z_LOAD - Z_BOT) / (Z_TOP - Z_BOT)       # on the +X wall
F_BOT = F_TOP - F                                    # on the -X wall
THETA = 0.2 / (Z_TOP - Z_BOT)
TIP_HAND = -0.1 + THETA * (40.0 - Z_BOT)             # rigid-body x displacement of the top, mm
print('hand wall forces', F_TOP, F_BOT, 'rigid tip disp', TIP_HAND, flush=True)


def part_box(j, name, x0, x1, y0, y1, z0, z1, feat):
    d = new_part(j.sw, OUT / f'{name}.SLDPRT')
    zc = (z0 + z1) / 2
    with Sk(d, plane(d, 'Z', zc, feat + '_P'), feat) as s:
        s.rect((x0, y0, zc), (x1, y1, zc))
    extrude(d, s.feat, feat, z1 - z0, mode=MID, expect_dv=(x1 - x0) * (y1 - y0) * (z1 - z0))
    return d


def wall_force(r, xwall):
    """Contact force on a slot wall from nodal sigma_x on the wall face, integrated with triangle-share areas (N)."""
    sel = (np.abs(r.pos[:, 0] - xwall) < 1e-3) & (np.abs(r.pos[:, 1]) <= 10 + 1e-3) & (r.pos[:, 2] >= 8 - 1e-3) & (r.pos[:, 2] <= 20 + 1e-3)
    p = r.pos[sel][:, 1:3]
    sx = r.s[sel, 1]
    tri = Delaunay(p)
    a = np.zeros(len(p))
    for t in tri.simplices:
        q = p[t]
        ar = 0.5 * abs((q[1, 0] - q[0, 0]) * (q[2, 1] - q[0, 1]) - (q[2, 0] - q[0, 0]) * (q[1, 1] - q[0, 1]))
        a[t] += ar / 3
    zc = float((-sx * a * r.pos[sel][:, 2]).sum() / max((-sx * a).sum(), 1e-12))
    return float(-(sx * a).sum()), zc, float(a.sum())


def section_force(r, z0, half=0.35):
    """Shear force in X through the tongue at height z0: integral of txz over the section (nodes within +-half mm of z0, area shares from a Delaunay triangulation in x-y)."""
    x, y, z = r.pos.T
    sel = (np.abs(z - z0) <= half) & (np.abs(x) <= 4 + 1e-3) & (np.abs(y) <= 10 + 1e-3)
    p = r.pos[sel][:, :2]
    tri = Delaunay(p)
    a = np.zeros(len(p))
    for t in tri.simplices:
        q = p[t]
        a[t] += 0.5 * abs((q[1, 0] - q[0, 0]) * (q[2, 1] - q[0, 1]) - (q[2, 0] - q[0, 0]) * (q[1, 1] - q[0, 1])) / 3
    return float((r.s[sel, 5] * a).sum()), float(a.sum()), int(sel.sum())


def split(r):
    x, y, z = r.pos.T
    pad = np.abs(y) > 10 + 1e-3
    tongue = (np.abs(x) <= 4 + 1e-3) & (np.abs(y) <= 10 + 1e-3) & (z >= 8.1 - 1e-3) & ~pad
    block = ~pad & ~tongue
    return block, tongue, pad


def pad_reaction(st, res):
    """Reaction force summed over pad outer faces (|y| > 11) and over everything else restrained."""
    gn = st.Mesh.GetNodes
    raw = _arr(gn() if callable(gn) else gn, 4)
    xyz = dict(zip(raw[:, 0].astype(int), raw[:, 1:] * 1000))
    q = _arr(res.GetReactionForcesAndMoments(0, NUL, 0, L()), 9)
    py = np.array([abs(xyz[int(i)][1]) for i in q[:, 0]])
    padf = q[py > 11.0, 1:4].sum(axis=0)
    return dict(pad_sum=padf.tolist(), pad_abs=float(np.abs(q[py > 11.0, 1:4]).sum()), other=q[py <= 11.0, 1:4].sum(axis=0).tolist())


if __name__ == '__main__':
    quick = len(sys.argv) > 1
    t0 = time.time()
    with job() as j:
        d = part_box(j, 'b4_block', -20, 20, -10, 10, 0, 20, 'BLOCK')
        with Sk(d, plane(d, 'Y', 0.0, 'SLOT_P'), 'SLOT') as s:
            s.rect((-4.1, 0, 8.0), (4.1, 0, 21.0))
        extrude(d, s.feat, 'SLOT', 22.0, cut=True, mode=MID, expect_dv=8.2 * 12 * 20)
        expect('block volume', volume(d), 40 * 20 * 20 - 8.2 * 12 * 20, 0.0005)
        save(d); close(j.sw, d)
        d = part_box(j, 'b4_tongue_low', -4, 4, -10, 10, 8.1, 30, 'TLOW'); save(d); close(j.sw, d)
        d = part_box(j, 'b4_tongue_up', -4, 4, -10, 10, 30, 40, 'TUP'); save(d); close(j.sw, d)
        for k, (px, sy) in enumerate(((2, 1), (-2, 1), (2, -1), (-2, -1))):
            d = new_part(j.sw, OUT / f'b4_softpad{k}.SLDPRT')
            yc = sy * 11.5
            with Sk(d, plane(d, 'Y', yc, f'SP{k}_P'), f'SOFTPAD{k}') as s:
                s.circle((px, yc, 24.0), 0.9)
            extrude(d, s.feat, f'SOFTPAD{k}', 3.0, mode=MID, expect_dv=math.pi * 0.81 * 3)
            save(d); close(j.sw, d)
        d = new_part(j.sw, OUT / 'b4_assembly.SLDPRT')
        with Sk(d, plane(d, 'Z', 10.0, 'BLK_P'), 'BLK') as s:
            s.rect((-20, -10, 10.0), (20, 10, 10.0))
        extrude(d, s.feat, 'BLK', 20.0, mode=MID, expect_dv=16000)
        with Sk(d, plane(d, 'Y', 0.0, 'SLOT_P'), 'SLOT') as s:
            s.rect((-4.1, 0, 8.0), (4.1, 0, 21.0))
        extrude(d, s.feat, 'SLOT', 22.0, cut=True, mode=MID, expect_dv=8.2 * 12 * 20)
        for nm in ('b4_tongue_low', 'b4_tongue_up', 'b4_softpad0', 'b4_softpad1', 'b4_softpad2', 'b4_softpad3'):
            insert_body(d, OUT / f'{nm}.SLDPRT')
        bd = bodies(d)
        for b in bd:
            log('body', b)
        expect('bodies', len(bd), 7, 0)
        want = 40 * 20 * 20 - 8.2 * 12 * 20 + 8 * 20 * 21.9 + 8 * 20 * 10 + 4 * math.pi * 0.81 * 3
        expect('assembly volume = sum of parts', volume(d), want, 0.0005)
        save(d); close(j.sw, d)

        cw = j.simulation()
        d = open_doc(j.sw, OUT / 'b4_assembly.SLDPRT')
        d.ForceRebuild3(False)
        bottom = pick(d, kind='plane', normal=(0, 0, -1), at=(0, 0, 0))
        wall_p = pick(d, kind='plane', normal=(-1, 0, 0), at=(4.1, 0, 14))
        wall_n = pick(d, kind='plane', normal=(1, 0, 0), at=(-4.1, 0, 14))
        tg_p = pick(d, kind='plane', normal=(1, 0, 0), at=(4.0, 0, 15))
        tg_n = pick(d, kind='plane', normal=(-1, 0, 0), at=(-4.0, 0, 15))
        load = pick(d, kind='plane', normal=(-1, 0, 0), at=(-4.0, 0, 35))
        padouts = [f for sx in (2, -2) for sy in (13, -13) for f in pick(d, kind='plane', normal=(0, 1 if sy > 0 else -1, 0), at=(sx, sy, 24.0))]
        for nm, v, n in (('bottom', bottom, 1), ('wall_p', wall_p, 1), ('wall_n', wall_n, 1), ('tg_p', tg_p, 1), ('tg_n', tg_n, 1), ('load', load, 1), ('padouts', padouts, 4)):
            log('pick', nm, len(v))
            expect(nm, len(v), n, 0)
        for nm, v in (('wall_p', wall_p), ('tg_p', tg_p), ('load', load)):
            log(nm, face_info(v[0]))
        log(f'PREDICT: tongue tip x-disp ~ +0.45..0.6 mm (rigid {TIP_HAND:.3f} + elastic), wall forces {F_TOP:.1f} (+X wall) / {F_BOT:.1f} (-X wall), nodes 20k-80k')

        def run(name, el, ctrl_size, load_n=F):
            ctrl = [(wall_p + wall_n + tg_p + tg_n, ctrl_size)]
            return static(j, d, name, PETG, fixtures=[('fixed', bottom), ('fixed', padouts)],
                          loads=[('normal', load, load_n)], el=el, ctrl=ctrl,
                          contacts=[(NO_PENETRATION, wall_p, tg_p), (NO_PENETRATION, wall_n, tg_n)],
                          materials={'softpad': PAD}, solver=SOLVER_DIRECT, post=pad_reaction, max_nodes=300000)

        out = {}
        sizes = [(3.0, 1.2)] if quick else [(3.0, 1.2), (2.5, 0.8), (2.0, 0.6)]
        rows = []
        for el, c in sizes:
            r = run('B4_' + str(c).replace('.', 'p'), el, c)
            blk, tg, pd = split(r)
            assert not (blk & tg).any() and (blk | tg | pd).all()
            fp, zp, ap = wall_force(r, 4.1)
            fn, zn, an = wall_force(r, -4.1)
            vmb = r.vm[blk]
            ib = np.flatnonzero(blk)[np.argmax(vmb)]
            top = tg & (np.abs(r.pos[:, 2] - 40) < 1e-3)
            sec = {str(z0): section_force(r, z0) for z0 in (10.0, 12.0, 14.0, 16.0, 18.0, 24.0, 26.0, 28.0)}
            near_edge = blk & (np.abs(r.pos[:, 0]) > 4.0) & (np.abs(r.pos[:, 0]) < 4.2) & (r.pos[:, 2] > 19.0)
            away_edge = blk & ~((r.pos[:, 2] > 18.0) & (np.abs(r.pos[:, 0]) < 6.0)) & ~((r.pos[:, 2] < 10.0) & (np.abs(r.pos[:, 0]) < 6.0))
            ia = np.flatnonzero(away_edge)[np.argmax(r.vm[away_edge])]
            row = dict(el=el, ctrl=c, section_shear=sec, block_peak_away_from_edges=(float(r.vm[ia]), r.pos[ia].round(2).tolist()),
                       block_vm_below_edge=[float(r.vm[blk & (np.abs(np.abs(r.pos[:, 0]) - 4.1) < 1e-3) & (np.abs(r.pos[:, 2] - zz) < 0.3)].max()) for zz in (19.0, 18.0, 17.0, 14.0, 9.0)],
                       tongue_min_uz_all=float(r.disp[tg, 3].min()), tongue_max_ux=float(r.disp[tg, 1].max()), nodes=r.nodes, reaction=r.reaction, applied=r.applied, F_plusX_wall=fp, z_plusX=zp, F_minusX_wall=fn, z_minusX=zn,
                       wall_area_check=(ap, an), block_peak_vm=float(vmb.max()), block_peak_at=r.pos[ib].round(2).tolist(),
                       tip_ux=float(r.disp[top, 1].mean()), tip_uy=float(r.disp[top, 2].mean()), tip_uz=float(r.disp[top, 3].mean()),
                       tongue_bottom_uz_min=float(r.disp[tg & (np.abs(r.pos[:, 2] - 8.1) < 1e-3), 3].min()),
                       tongue_peak_vm=float(r.vm[tg].max()), pads=r.extra, excessive=getattr(r, 'excessive', False),
                       max_disp=r.max_disp(), seconds=round(r.seconds))
            log('ROW', row)
            rows.append(row)
            np.savez(OUT / f'b4_{c}.npz', pos=r.pos, s=r.s, disp=r.disp)
            (OUT / 'b4_partial.json').write_text(json.dumps(rows, indent=1, default=str))
        out['rows'] = rows
        rr = run('B4_REV', 3.0, 1.2, load_n=-0.001)
        blk, tg, pd = split(rr)
        top = tg & (np.abs(rr.pos[:, 2] - 40) < 1e-3)
        out['reverse'] = dict(tip_ux=float(rr.disp[top, 1].mean()), reaction=rr.reaction, applied=rr.applied, pads=rr.extra, excessive=getattr(rr, 'excessive', False))
        log('REVERSE', out['reverse'])
        out['hand'] = dict(F_top=F_TOP, F_bot=F_BOT, tip_rigid=TIP_HAND)
        out['seconds'] = round(time.time() - t0)
        (OUT / 'b4_measured.json').write_text(json.dumps(out, indent=1, default=str))
        close(j.sw, d)
