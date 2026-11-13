"""T6 post-processing from the saved nodal results (no SolidWorks): split by body with geometry, contact pressure,
pin rise, pad share, load path. Run under tools/pc/capped.py.

    python t6_post.py T6_MAIN0 [T6_MAIN1 ...] [--lift T6_LIFT]
"""
import json
import math
import sys

import numpy as np

from common import HERE, OUT

SIM = OUT.parent.parent.parent / '_sim' / 'sw-eval'
R_PIN, R_HOLE, AZ, HY = 5.0, 5.1, 10.0, 15.0
E_PETG, NU_PETG, E_ST, NU_ST = 1900.0, 0.38, 210000.0, 0.28


def hand():
    F, L, d = 500.0, 30.0, 10.0
    mean = F / (d * L)                                           # projected-area bearing stress
    Rr = R_PIN * R_HOLE / (R_HOLE - R_PIN)                       # relative radius of a pin in a slightly larger hole
    Es = 1 / ((1 - NU_PETG ** 2) / E_PETG + (1 - NU_ST ** 2) / E_ST)
    w = F / L                                                    # N/mm, if the pin loaded the hole evenly along Y
    b = math.sqrt(4 * w * Rr / (math.pi * Es))                   # Hertz half-width, line contact
    p0 = 2 * w / (math.pi * b)
    return dict(mean_projected_mpa=round(mean, 3), hertz_peak_pressure_mpa=round(p0, 2), hertz_half_width_mm=round(b, 2),
                hertz_peak_vm_mpa_approx=round(0.56 * p0, 2), relative_radius_mm=Rr, e_star_mpa=round(Es, 1))


def split(pos):
    """Label nodes by the solid they lie in, from the undeformed coordinates, with a guard at the interfaces."""
    x, y, z = pos.T
    rho = np.hypot(x, z - AZ)
    pin = rho <= R_PIN + 0.02
    in_block_box = (np.abs(x) <= 20.001) & (np.abs(y) <= HY + 0.001) & (z >= -0.001) & (z <= 20.001)
    block = in_block_box & (rho >= R_HOLE - 0.02)
    pad = (np.abs(y) > HY + 0.001) & (rho > R_PIN + 0.02)
    # interface nodes that two bodies could share: the pad's footprint on the block side, and the pad top on the pin
    pad_touch_block = block & (np.abs(y) > HY - 0.001) & (np.abs(x) <= 1.6) & (z <= 5.3)
    pad_touch_pin = pin & (np.abs(y) >= HY - 0.001) & (np.abs(y) <= HY + 2.001) & (np.abs(x) <= 1.6) & (z < AZ) & (rho > R_PIN - 0.02)
    # a pin node at |y| > 15 with rho <= 5.02 lying where the pad also is counts as pin; the pad keeps rho > 5.02
    assert not (pin & block).any(), 'a node is in both the pin and the block'
    assert not (pad & block).any() and not (pad & pin).any()
    left = ~(pin | block | pad)
    return pin, block, pad, pad_touch_block, pad_touch_pin, left, rho


def post(name):
    z = np.load(SIM / f'{name}.npz', allow_pickle=True)
    pos, s, disp = z['pos'], z['s'], z['disp']
    total = float(z['total_n'])
    pin, block, pad, ptb, ptp, left, rho = split(pos)
    out = dict(study=name, nodes=int(z['nodes']), hole_local_mm=float(z['hole_local']), total_n=total,
               reaction_n=[float(v) for v in z['reaction']], solve_s=round(float(z['seconds'])),
               node_split=dict(pin=int(pin.sum()), block=int(block.sum()), pad=int(pad.sum()), unassigned=int(left.sum())))
    assert left.sum() == 0, f'{left.sum()} nodes belong to no body: {pos[left][:5]}'
    assert np.array_equal(disp[:, 0], s[:, 0]), 'displacement and stress rows are not in the same node order'
    uz = disp[:, 3]
    # pin rise: its nodes inside the block length, and at the ends
    out['pin_rise_mm'] = round(float(uz[pin & (np.abs(pos[:, 1]) < 1.0)].mean()), 5)
    out['pin_rise_end_mm'] = round(float(uz[pin & (np.abs(pos[:, 1]) > 24.9)].mean()), 5)
    out['pin_uz_range_mm'] = [round(float(uz[pin].min()), 5), round(float(uz[pin].max()), 5)]
    out['pin_ux_uy_abs_max_mm'] = [round(float(np.abs(disp[pin, 1]).max()), 5), round(float(np.abs(disp[pin, 2]).max()), 5)]
    out['block_max_disp_mm'] = round(float(disp[block, 4].max()), 5)
    out['max_disp_mm'] = round(float(disp[:, 4].max()), 5)
    out['max_disp_body'] = ['pin', 'block', 'pad'][int(np.argmax([disp[m, 4].max() for m in (pin, block, pad)]))]
    # block stress: everything in the block except the fixed bottom layer (2 elements of 3 mm) and the pad footprints
    score = block & ~ptb & (pos[:, 2] > 6.0)
    vm = s[:, 10]
    i = np.flatnonzero(score)[np.argmax(vm[score])]
    out['peak_contact_vm_mpa'] = round(float(vm[i]), 3)
    out['block_peak_at_mm'] = pos[i].round(2).tolist()
    out['block_peak_rho_mm'] = round(float(rho[i]), 3)
    # contact pressure: the radial normal stress on the hole wall, n = (x, 0, z - 10) / rho; pressure is its negative
    wall = block & (np.abs(rho - R_HOLE) < 0.02)
    nx, nz = pos[:, 0] / np.maximum(rho, 1e-9), (pos[:, 2] - AZ) / np.maximum(rho, 1e-9)
    srr = nx ** 2 * s[:, 1] + nz ** 2 * s[:, 3] + 2 * nx * nz * s[:, 5]
    th = np.degrees(np.arctan2(pos[:, 0], pos[:, 2] - AZ))        # 0 at the top of the hole, where the pin bears
    bearing = wall & (np.abs(th) < 45)
    k = np.flatnonzero(bearing)[np.argmin(srr[bearing])]
    # the pads' own mark on the block: each pad bridges the 0.1 mm gap at the bottom end of the hole, and what little it
    # carries enters the block through that sliver. At the unloaded side; reported, not scored
    pz = block & (np.abs(pos[:, 1]) > 13.5) & (np.abs(pos[:, 0]) < 2.5) & (pos[:, 2] < 6.0) & (pos[:, 2] > 1.0)
    ia = np.flatnonzero(pz)[np.argmax(vm[pz])]
    out['pad_attachment_artefact'] = dict(vm_mpa=round(float(vm[ia]), 2), at_mm=pos[ia].round(2).tolist(),
                                          radial_stress_mpa=round(float(srr[ia]), 2))
    out['peak_contact_pressure_mpa'] = round(float(-srr[k]), 3)
    out['peak_pressure_at_mm'] = pos[k].round(2).tolist()
    # the same away from the two hole ends (the pin bends, and its load comes in outside the block: the ends carry more)
    mid = wall & (np.abs(pos[:, 1]) < 5.0)
    km = np.flatnonzero(mid)[np.argmin(srr[mid])]
    out['mid_length_peak_pressure_mpa'] = round(float(-srr[km]), 3)
    out['mid_length_peak_at_mm'] = pos[km].round(2).tolist()
    vm_mid = block & (np.abs(pos[:, 1]) < 5.0)
    out['mid_length_peak_vm_mpa'] = round(float(vm[vm_mid].max()), 3)
    # contact arc: wall nodes carrying more than 5 % of the peak pressure, as an angle from the top of the hole
    inner = wall & (np.abs(pos[:, 1]) < 12.0)                     # clear of the hole's end edges
    loaded = inner & (-srr > 0.05 * -srr[k])
    out['contact_half_angle_deg'] = round(float(np.abs(th[loaded]).max()), 1)
    out['contact_half_width_mm'] = round(float(np.abs(pos[loaded, 0]).max()), 2)
    # the wall away from the contact is a free surface: its radial stress must be about zero
    free = inner & (np.abs(th) > 45)
    out['free_wall_radial_stress_abs_max_mpa'] = round(float(np.abs(srr[free]).max()), 4)
    # integrate the contact pressure over the hole wall: sum of p * nz * dA must give the load. Nodes are binned on a
    # grid in (angle, y), the mean pressure of each bin times its area, so mesh density does not weight the answer
    nb_t, nb_y = 90, 30
    tb = np.clip(((th[wall] + 180) / 360 * nb_t).astype(int), 0, nb_t - 1)
    yb = np.clip(((pos[wall, 1] + HY) / (2 * HY) * nb_y).astype(int), 0, nb_y - 1)
    sums = np.zeros((nb_t, nb_y)); cnt = np.zeros((nb_t, nb_y))
    np.add.at(sums, (tb, yb), (-srr[wall]) * nz[wall]); np.add.at(cnt, (tb, yb), 1)
    dA = (2 * math.pi * R_HOLE / nb_t) * (2 * HY / nb_y)
    filled = cnt > 0
    out['pressure_integral_fz_n'] = round(float((sums[filled] / cnt[filled]).sum() * dA), 1)
    out['pressure_grid_empty_bins'] = int((~filled).sum())
    # pressure along the hole: mean of the top-of-hole pressure in 5 bands of y
    top = wall & (np.abs(th) < 6)
    out['top_pressure_by_y'] = {f'{a:+.0f}..{a + 6:+.0f}': round(float(-srr[top & (pos[:, 1] >= a) & (pos[:, 1] < a + 6.001)].mean()), 2)
                                for a in (-15, -9, -3, 3, 9)}
    # load path: the block above the hole hangs on the two ligaments beside it. sz over the plane Z 10, binned in x so
    # that mesh density does not weight it, times the area, must equal the load
    slab = block & (np.abs(pos[:, 2] - AZ) < 0.75)
    edges = np.linspace(R_HOLE, 20.0, 16)
    fz = 0.0
    for a, b in zip(edges[:-1], edges[1:]):
        m = slab & (np.abs(pos[:, 0]) >= a) & (np.abs(pos[:, 0]) < b + 1e-9)
        fz += float(s[m, 3].mean()) * (b - a) * 2 * (2 * HY)
    out['ligament_fz_n'] = round(fz, 1)
    out['ligament_mean_sz_mpa'] = round(fz / (2 * (20 - R_HOLE) * 2 * HY), 3)
    # the pads: how much load they carry. Stress in the pad times its section (3 x 2 mm, cut at mid height)
    pm = pad & (np.abs(pos[:, 2] - 3.6) < 0.5)
    out['pad_mean_sz_mpa'] = round(float(s[pm, 3].mean()), 5)
    out['pad_force_n_from_stress'] = round(float(s[pm, 3].mean()) * 3.0 * 2.0 * 2, 4)
    out['pad_peak_vm_mpa'] = round(float(vm[pad].max()), 4)
    out['pin_peak_vm_mpa'] = round(float(vm[pin & ~ptp & (np.abs(pos[:, 1]) < 24.0)].max()), 2)
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    lift = None
    if '--lift' in args:
        lift = args[args.index('--lift') + 1]
        args = args[:args.index('--lift')]
    res = dict(hand=hand(), runs=[post(n) for n in args])
    if lift:
        z = np.load(SIM / f'{lift}.npz', allow_pickle=True)
        pin = split(z['pos'])[0]
        up = float(z['disp'][pin, 3].mean())
        k = float(z['total_n']) / up
        res['lift'] = dict(total_n=float(z['total_n']), pin_rise_mm=round(up, 6), pad_stiffness_n_per_mm=round(k, 4),
                           reaction_n=[float(v) for v in z['reaction']], block_max_disp_mm=float(z['disp'][split(z['pos'])[1], 4].max()))
        for r in res['runs']:
            r['pad_force_n_from_stiffness'] = round(k * r['pin_rise_mm'], 3)
            r['pad_share_pct'] = round(100 * k * r['pin_rise_mm'] / r['total_n'], 3)
    (HERE / 'T6_post.json').write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
