"""B4: a tongue standing in a slot with 0.1 mm clearance, pushed sideways with 80 N. python b4_contact.py [ctrl size]

Block X -20..20, Y -10..10, Z 0..20, slot X -4.1..4.1, Z 8..20 through Y. Tongue X -4..4, Y -10..10, Z 8.1..40.
The block's bottom is fixed; 80 N in +X on the tongue's -X face between Z 30 and 40.

Hand, before SolidWorks: the tongue tilts until it bears on the +X wall at the slot mouth (Z 20) and on the -X wall at
its own foot (Z 8.1). With point contacts there: R_top * (20 - 8.1) = 80 * (35 - 8.1), so R_top = 180.8 N on the +X
wall and R_foot = R_top - 80 = 100.8 N on the -X wall. Real contact patches have depth, which shortens the lever, so
the results should be somewhat ABOVE these (about 190 to 215 and 110 to 135), and differ by exactly 80.
Tilt to close both gaps: 0.2 / 11.9 = 0.0168 rad about Z 14.05, so the tip (Z 40) moves 0.1 + 0.0168 * 20 = 0.44 mm
rigidly, plus bending of the 8 x 20 tongue above the slot mouth: 80 * 15^2 * (3 * 20 - 15) / (6 E I), I = 853 mm4,
0.08 mm. Tip about 0.5 to 0.6 mm.

The tongue is held by nothing until it touches, so it gets two soft pads (2 x 2 x 2, E 0.5 MPa), one on each Y face at
Z 13..15: on the tilt axis, where the tongue hardly moves, clear of the block (the slot is open there) and of every
contact face. Their outer faces are fixed.
"""
import json
import sys

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from common import DENS, HERE, ROOT, WIP, put, sha
from swkit import *
from swfea import NO_PENETRATION, PETG, SOLVER_DIRECT, static
import b2_model as M

F = 80.0
PAD = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
HAND_TOP = F * (35 - 8.1) / (20 - 8.1)
HAND_FOOT = HAND_TOP - F
SIM = ROOT / 'cad' / '_sim' / 'sw-eval' / 'fable-b'
SIM.mkdir(parents=True, exist_ok=True)
P = WIP / 'tongue_slot.SLDPRT'


def box_part(j, name, lo, hi):
    d = new_part(j.sw, WIP / f'{name}.SLDPRT')
    zc = (lo[2] + hi[2]) / 2
    with Sk(d, plane(d, 'Z', zc, name.upper() + '_P'), name.upper()) as s:
        s.rect((lo[0], lo[1], zc), (hi[0], hi[1], zc))
    extrude(d, s.feat, name.upper(), hi[2] - lo[2], mode=MID, expect_dv=(hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]))
    return d


def build(j):
    for name, lo, hi in (('b4_tongue', (-4, -10, 8.1), (4, 10, 40)), ('b4_pad_a', (-1, 10, 13), (1, 12, 15)),
                         ('b4_pad_b', (-1, -12, 13), (1, -10, 15))):
        d = box_part(j, name, lo, hi)
        save(d)
        close(j.sw, d)
    d = box_part(j, 'tongue_slot', (-20, -10, 0), (20, 10, 20))
    with Sk(d, plane(d, 'Y', 0.0, 'SLOT_P'), 'SLOT') as s:
        s.rect((-4.1, 0, 8.0), (4.1, 0, 20.5))                    # the tool overshoots the top face
    extrude(d, s.feat, 'SLOT', 20.0, cut=True, mode=MID, expect_dv=8.2 * 12 * 20)
    save(d)
    for name in ('b4_tongue', 'b4_pad_a', 'b4_pad_b'):
        insert_body(d, WIP / f'{name}.SLDPRT')
    bs = bodies(d)
    expect('bodies', len(bs), 4, 0)
    vols = sorted(b[1] for b in bs)
    for got, want in zip(vols, (8.0, 8.0, 8 * 20 * 31.9, 40 * 20 * 20 - 8.2 * 12 * 20)):
        expect('body volume', got, want, 0.001)
    # the load patch: the tongue's -X face above Z 30
    M.split_face(d, 'LOAD_PATCH', plane(d, 'X', -4.0, 'PATCH_P'), (-4.0, -11, 30.0), (-4.0, 11, 30.0), (-4.0, 0, 35.0))
    expect('bodies after the split', len(bodies(d)), 4, 0)
    save(d)
    close(j.sw, d)


def face_force(pos, s, sel, comp=1):
    """Integral of a stress component over a planar face from its nodes: Delaunay in (y, z), mean of each triangle's nodes."""
    pts, v = pos[sel][:, 1:3], s[sel, comp]
    tri = Delaunay(pts)
    a = pts[tri.simplices]
    u, w = a[:, 1] - a[:, 0], a[:, 2] - a[:, 0]
    area = 0.5 * np.abs(u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0])
    return float((area * v[tri.simplices].mean(axis=1)).sum()), float(area.sum())


def section(p, S, body, zc, x0, x1, n=(121, 161)):
    """Force and moment carried across the horizontal plane Z = zc through a body, X x0..x1, Y -10..10.

    The stresses are interpolated from the body's nodes within 2.5 mm of the plane onto a regular grid and summed.
    Returns (shear force in X = integral of txz, axial force = integral of sz, moment about Y = integral of sz * x).
    """
    from scipy.interpolate import LinearNDInterpolator
    sel = body & (np.abs(p[:, 2] - zc) < 2.5)
    f = LinearNDInterpolator(p[sel], S[sel][:, [5, 3]])
    xs = np.linspace(x0, x1, n[0] + 1)
    ys = np.linspace(-10, 10, n[1] + 1)
    xm, ym = (xs[1:] + xs[:-1]) / 2, (ys[1:] + ys[:-1]) / 2
    X, Y = np.meshgrid(xm, ym, indexing='ij')
    v = f(np.c_[X.ravel(), Y.ravel(), np.full(X.size, zc)])
    if np.isnan(v).any():
        raise Failed(f'section at Z {zc}: {int(np.isnan(v).any(axis=1).sum())} sample points fell outside the nodes')
    da = (xs[1] - xs[0]) * (ys[1] - ys[0])
    return float(v[:, 0].sum() * da), float(v[:, 1].sum() * da), float((v[:, 1] * X.ravel()).sum() * da)


def run(j, tag, load, cs, el=2.5, edge=0.0):
    d = open_doc(j.sw, P)
    d.ForceRebuild3(False)
    one = lambda what, fs, n=1: (expect(what, len(fs), n, 0), fs)[1]      # noqa: E731
    bottom = one('block bottom', pick(d, kind='plane', normal=(0, 0, -1), at=(0, 0, 0)))
    wall_p = one('slot wall +X', pick(d, kind='plane', normal=(-1, 0, 0), at=(4.1, 0, 14)))
    wall_m = one('slot wall -X', pick(d, kind='plane', normal=(1, 0, 0), at=(-4.1, 0, 14)))
    floor = one('slot floor', pick(d, kind='plane', normal=(0, 0, 1), at=(0, 0, 8.0)))
    t_p = one('tongue +X face', pick(d, kind='plane', normal=(1, 0, 0), at=(4.0, 0, 14)))
    t_m = one('tongue -X face below the patch', pick(d, kind='plane', normal=(-1, 0, 0), at=(-4.0, 0, 14)))
    t_b = one('tongue bottom', pick(d, kind='plane', normal=(0, 0, -1), at=(0, 0, 8.1)))
    patch = one('load patch', pick(d, kind='plane', normal=(-1, 0, 0), at=(-4.0, 0, 35)))
    expect('load patch area', face_info(patch[0])['area'], 200.0, 0.001)
    expect('patch z0', face_info(patch[0])['box'][2], 30.0, 0.001)
    pad_out = one('pad outer faces', pick(d, kind='plane', at=(0, 12, 14)) + pick(d, kind='plane', at=(0, -12, 14)), 2)
    log(f'{tag}: PREDICT nodes 60,000 to 200,000; tip displacement 0.5 to 0.6 mm at {load} N (0.44 rigid tilt + 0.08 bending); '
        f'wall forces a little above {HAND_TOP:.0f} and {HAND_FOOT:.0f} N; block peak on the slot-mouth edge X 4.1, Z 20')
    ctrl = [(wall_p + wall_m + t_p + t_m, cs)]
    if edge:      # the two lines the tongue bears on: the slot-mouth edge of the +X wall and the foot edge of the tongue
        ed = edges_where(d, lambda q: (abs(q[0] - 4.1) < 0.01 and abs(q[2] - 20) < 0.01) or (abs(q[0] + 4.0) < 0.01 and abs(q[2] - 8.1) < 0.01)
                         or (abs(q[0] - 4.0) < 0.01 and abs(q[2] - 8.1) < 0.01) or (abs(q[0] + 4.1) < 0.01 and abs(q[2] - 20) < 0.01)
                         or (abs(abs(q[0]) - 4.1) < 0.01 and abs(q[2] - 8.0) < 0.01))
        expect('contact edges for mesh control', len(ed), 6, 0)
        ctrl.append((ed, edge))
    r = static(j, d, tag, PETG, fixtures=[('fixed', bottom), ('fixed', pad_out)], loads=[('normal', patch, load)], el=el,
               ctrl=ctrl,
               contacts=[(NO_PENETRATION, wall_p, t_p), (NO_PENETRATION, wall_m, t_m), (NO_PENETRATION, floor, t_b)],
               materials={'pad': PAD}, solver=SOLVER_DIRECT, loose_ok=True)
    close(j.sw, d)
    np.savez_compressed(SIM / f'{tag}.npz', pos=r.pos, s=r.s, disp=r.disp, reaction=np.array(r.reaction))
    return analyse(tag, load, cs, el, r.pos, r.s, r.disp, r.reaction, r.nodes, bool(r.excessive), round(r.seconds))


def analyse(tag, load, cs, el, p, S, U, reaction, nodes, excessive, seconds):
    """Everything read from the nodal results; also runs on a saved .npz (python b4_contact.py post ...)."""
    e = 1e-3
    pad = np.abs(p[:, 1]) > 10 + e
    tongue = (np.abs(p[:, 0]) <= 4.0 + e) & (p[:, 2] >= 8.1 - e) & ~pad
    block = ((np.abs(p[:, 0]) >= 4.1 - e) | (p[:, 2] <= 8.0 + e)) & ~pad
    stray = ~(pad | tongue | block)
    both = tongue & block
    if stray.any() or both.any():
        raise Failed(f'{tag}: {int(stray.sum())} nodes in no body and {int(both.sum())} in two: the split by geometry is wrong')
    out = dict(tag=tag, load=load, el=el, ctrl=cs, nodes=nodes, reaction=reaction, excessive_prompt=excessive,
               nodes_block=int(block.sum()), nodes_tongue=int(tongue.sum()), nodes_pad=int(pad.sum()), seconds=seconds)
    # wall forces: contact pressure on each slot wall is -sx there
    wp = block & (np.abs(p[:, 0] - 4.1) < e) & (p[:, 2] >= 8 - e)
    wm = block & (np.abs(p[:, 0] + 4.1) < e) & (p[:, 2] >= 8 - e)
    fp, ap = face_force(p, S, wp)
    fm, am = face_force(p, S, wm)
    expect(tag + ' wall face area', ap, 240.0, 0.01)
    out['wall_force_plus_x_wall_n'] = round(-fp, 2)          # the wall pushes the tongue towards -X with this
    out['wall_force_minus_x_wall_n'] = round(-fm, 2)         # the wall pushes the tongue towards +X with this
    # the same two forces from the tongue's own faces
    tp_ = tongue & (np.abs(p[:, 0] - 4.0) < e)
    tm_ = tongue & (np.abs(p[:, 0] + 4.0) < e) & (p[:, 2] < 30 - e)
    out['tongue_face_plus_n'] = round(-face_force(p, S, tp_)[0], 2)
    out['tongue_face_minus_n'] = round(-face_force(p, S, tm_)[0], 2)
    out['difference_n'] = round(out['wall_force_plus_x_wall_n'] - out['wall_force_minus_x_wall_n'], 2)
    # the wall forces by cutting free bodies (smooth interior stress, so far better than summing contact-edge stresses):
    #   tongue cut at Z 25, above the slot: must carry V = load and M = load * (35 - 25): the check on the method
    #   tongue cut at Z 14, between the two bearing lines: V = the foot force on the -X wall
    #   +X pillar of the block cut at Z 12 (X 4.1..20): V = the force on the +X wall; the -X pillar there carries none
    v25, n25, m25 = section(p, S, tongue, 25.0, -4, 4)
    v14, n14, m14 = section(p, S, tongue, 14.0, -4, 4)
    vp, _, mp_ = section(p, S, block, 12.0, 4.1, 20)
    vmn, _, _ = section(p, S, block, 12.0, -20, -4.1)
    out['section_check_tongue_z25'] = dict(shear_n=round(v25, 2), want=load, moment_nmm=round(m25, 1), want_moment=load * 10, axial_n=round(n25, 3))
    out['foot_force_from_tongue_cut_n'] = round(abs(v14), 2)
    out['tongue_cut_z14'] = dict(shear_n=round(v14, 2), moment_nmm=round(m14, 1), axial_n=round(n14, 3))
    out['top_force_from_pillar_cut_n'] = round(abs(vp), 2)
    out['pillar_cut_z12'] = dict(plus_shear_n=round(vp, 2), plus_moment_nmm=round(mp_, 1), minus_shear_n=round(vmn, 2))
    out['wall_forces_n'] = [out['top_force_from_pillar_cut_n'], out['foot_force_from_tongue_cut_n']]
    out['wall_forces_difference_n'] = round(abs(vp) - abs(v14), 2)
    # where the pressure sits: the centre of pressure in Z on each wall
    for name, sel in (('plus', wp), ('minus', wm)):
        pr = np.clip(-S[sel, 1], 0, None)
        out[f'pressure_centre_z_{name}'] = round(float((pr * p[sel, 2]).sum() / pr.sum()), 2) if pr.sum() > 0 else None
        out[f'pressure_peak_{name}_mpa'] = round(float(pr.max()), 2)
        out[f'bearing_depth_{name}_mm'] = [round(float(p[sel, 2][pr > 0.05 * pr.max()].min()), 2), round(float(p[sel, 2][pr > 0.05 * pr.max()].max()), 2)] if pr.max() > 0 else None
    # displacements: tip, and the gaps actually closed
    tip = tongue & (p[:, 2] > 40 - e)
    out['tongue_tip_disp_mm'] = round(float(U[tip, 4].max()), 4)
    out['tongue_tip_ux_mm'] = round(float(U[tip, 1].mean()), 4)
    top_c = tongue & (np.abs(p[:, 0] - 4.0) < e) & (np.abs(p[:, 2] - 20) < 0.6)
    foot_c = tongue & (np.abs(p[:, 0] + 4.0) < e) & (p[:, 2] < 8.1 + 0.4)
    out['tongue_ux_at_slot_mouth_mm'] = round(float(U[top_c, 1].mean()), 4) if top_c.any() else None
    out['tongue_ux_at_foot_mm'] = round(float(U[foot_c, 1].mean()), 4) if foot_c.any() else None
    out['tongue_uz_range_mm'] = [round(float(U[tongue, 3].min()), 4), round(float(U[tongue, 3].max()), 4)]
    out['tongue_uy_range_mm'] = [round(float(U[tongue, 2].min()), 4), round(float(U[tongue, 2].max()), 4)]
    # penetration left over: tongue face nodes beyond the wall, allowing for the wall's own movement
    kw = cKDTree(p[wp][:, 1:3])
    tn = np.flatnonzero(tongue & (np.abs(p[:, 0] - 4.0) < e) & (p[:, 2] <= 20))
    _, ix = kw.query(p[tn][:, 1:3])
    out['max_penetration_plus_wall_mm'] = round(float((U[tn, 1] - U[np.flatnonzero(wp)[ix], 1] - 0.1).max()), 4)
    kw = cKDTree(p[wm][:, 1:3])
    tn = np.flatnonzero(tongue & (np.abs(p[:, 0] + 4.0) < e) & (p[:, 2] <= 20))
    _, ix = kw.query(p[tn][:, 1:3])
    out['max_penetration_minus_wall_mm'] = round(float((U[np.flatnonzero(wm)[ix], 1] - U[tn, 1] - 0.1).max()), 4)
    # block stress: the peak, where, what it averages to, and the peak away from the contact edges
    vm = S[:, 10]
    ib = np.flatnonzero(block)
    k = ib[np.argmax(vm[ib])]
    out['block_peak_vm_mpa'] = round(float(vm[k]), 2)
    out['block_peak_at_mm'] = p[k].round(2).tolist()
    tree = cKDTree(p[ib])
    out['block_peak_averages'] = {str(rad): (round(float(vm[ib][tree.query_ball_point(p[k], rad)].mean()), 2),
                                             len(tree.query_ball_point(p[k], rad))) for rad in (0.5, 1.0, 2.0)}
    for name, c in (('slot_mouth_edge_plus', (4.1, 20.0)), ('slot_root_corner_plus', (4.1, 8.0)), ('slot_root_corner_minus', (-4.1, 8.0)),
                    ('slot_mouth_edge_minus', (-4.1, 20.0))):
        near = block & (np.hypot(p[:, 0] - c[0], p[:, 2] - c[1]) < 1.0)
        out['block_vm_near_' + name] = round(float(vm[near].max()), 2)
    far = block & (np.hypot(p[:, 0] - 4.1, p[:, 2] - 20) > 2.0) & (np.hypot(np.abs(p[:, 0]) - 4.1, p[:, 2] - 8) > 2.0) & (p[:, 2] > 1.5)
    kf = np.flatnonzero(far)[np.argmax(vm[far])]
    out['block_peak_vm_2mm_clear_of_edges_mpa'] = round(float(vm[kf]), 2)
    out['block_peak_2mm_clear_at_mm'] = p[kf].round(2).tolist()
    it = np.flatnonzero(tongue)
    kt = it[np.argmax(vm[it])]
    out['tongue_peak_vm_mpa'], out['tongue_peak_at_mm'] = round(float(vm[kt]), 2), p[kt].round(2).tolist()
    # the pads' share: their shear and direct stress times the bonded area (4 mm2 each)
    out['pad_peak_vm_mpa'] = round(float(vm[pad].max()), 5)
    out['pad_force_bound_n'] = round(float(vm[pad].max()) * 4.0 * 2, 4)
    log(tag, json.dumps(out))
    return out


if __name__ == '__main__':
    what = sys.argv[1]
    f = HERE / 'b4_runs.json'
    runs = json.loads(f.read_text()) if f.exists() else []
    if what == 'post':
        tag, load, cs = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
        z = np.load(SIM / f'{tag}.npz')
        runs.append(analyse(tag, load, cs, float(sys.argv[5]) if len(sys.argv) > 5 else 2.5, z['pos'], z['s'], z['disp'],
                            z['reaction'].tolist(), len(z['pos']), None, None))
        f.write_text(json.dumps(runs, indent=1, default=float))
        raise SystemExit('B4 POST DONE ' + tag)
    with job() as j:
        j.simulation()
        if what == 'build':
            build(j)
            print('B4 BUILD DONE', sha(P))
        else:
            tag, load, cs = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
            el = float(sys.argv[5]) if len(sys.argv) > 5 else 2.5
            runs.append(run(j, tag, load, cs, el, float(sys.argv[6]) if len(sys.argv) > 6 else 0.0))
            f.write_text(json.dumps(runs, indent=1, default=float))
            print('B4 RUN DONE', tag)
