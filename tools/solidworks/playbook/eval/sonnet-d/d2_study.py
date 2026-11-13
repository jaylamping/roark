"""D2 study: 300 N on the ring along +Y and +X, face Y -32 fixed, contact ring/seats and halves, pins as the screws.

    python d2_study.py Y|X|YB      YB is the +Y case with the contacts replaced by bonds (the proof that the sets do something)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
from swkit import *   # noqa
from swfea import *   # noqa
from scipy.spatial import cKDTree

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d2")
RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
H, XS = 0.3, 30.0
PAD_MAT = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
EL = float(sys.argv[2]) if len(sys.argv) > 2 else 3.5
PADS = [(25 * math.cos(math.radians(a)), 25 * math.sin(math.radians(a))) for a in (45, 135, 225, 315)]


def masks(r):
    p = r.pos
    rad = np.hypot(p[:, 0], p[:, 1])
    pin = np.zeros(len(p), bool)
    for sx in (-1, 1):
        for z in (1.0, 6.0):
            pin |= (np.hypot(p[:, 0] - sx * XS, p[:, 2] - z) < 2.05) & (p[:, 1] > -6.1) & (p[:, 1] < 31.6)
    near_pad = np.zeros(len(p), bool)
    for x, y in PADS:
        near_pad |= (np.hypot(p[:, 0] - x, p[:, 1] - y) < 2.0) & (p[:, 2] > 7.1) & (p[:, 2] < 7.7)
    ring = (rad < 25.99) & (rad >= 23.99) & (p[:, 2] > 0.19) & (p[:, 2] < 7.21)
    housing = ~pin & ~near_pad & ~ring
    return dict(pin=pin, ring=ring, pad=near_pad, upper=housing & (p[:, 1] > 0), lower=housing & (p[:, 1] < 0))


if __name__ == '__main__':
    case = sys.argv[1]
    f = {'Y': (0, 300.0, 0), 'X': (300.0, 0, 0), 'YB': (0, 300.0, 0)}[case]
    with job() as j:
        d = open_doc(j.sw, OUT / 'housing_pair.SLDPRT')
        j.simulation()
        d.ForceRebuild3(False)
        up_seat = pick(d, kind='cyl', r=26.0, inside=[-27, 0.2, -1, 27, 27, 8])
        lo_seat = pick(d, kind='cyl', r=26.0, inside=[-27, -27, -1, 27, -0.2, 8])
        ring_out = pick(d, kind='cyl', r=26.0, inside=[-26.1, -26.1, 0, 26.1, 26.1, 7.3])
        up_split = pick(d, kind='plane', normal=(0, -1, 0), at=(33, H, 4))
        lo_split = pick(d, kind='plane', normal=(0, 1, 0), at=(33, -H, 4))
        mount = pick(d, kind='plane', normal=(0, -1, 0), at=(30, -32, 9))
        bore = pick(d, kind='cyl', r=24.0)
        pad_cyl = pick(d, kind='cyl', r=1.2)
        log('picks upper seat', len(up_seat), 'lower seat', len(lo_seat), 'ring outer', len(ring_out), 'splits', len(up_split), len(lo_split),
            'mount', len(mount), 'bore', len(bore), 'pad cyl', len(pad_cyl))
        for nm, fs, n in (('upper seat', up_seat, 1), ('lower seat', lo_seat, 1), ('ring outer', ring_out, 1), ('upper split', up_split, 1),
                          ('lower split', lo_split, 1), ('mount', mount, 1), ('bore', bore, 1), ('pad cyl', pad_cyl, 4)):
            expect(nm, len(fs), n, 0 if nm != 'ring outer' else 0)
        log('PREDICTION: nodes about 90,000 at 3.5 mm with 1.5 mm controls on the seat; displacement of the ring under 0.05 mm; '
            'screw tension 75 N each (+Y) or shear 37.5 N each (+X); peak on the seat arc next to the split face')
        kind = BONDED if case == 'YB' else NO_PENETRATION
        contacts = [(kind, ring_out, up_seat), (kind, ring_out, lo_seat), (kind, up_split, lo_split)]
        ctrl = [(list(up_seat) + list(lo_seat) + list(ring_out), 1.5), (pad_cyl, 0.2)]
        r = static(j, d, f'D2_{case}', PETG, fixtures=[('fixed', mount)],
                   loads=[('remote', bore, (0.0, 0.0, 3.7), f, (0, 0, 0))], el=EL, ctrl=ctrl, contacts=contacts,
                   materials={'ring': STEEL, 'pin_': STEEL, 'pad_': PAD_MAT}, solver=SOLVER_DIRECT, loose_ok=(case == 'YB'),
                   max_nodes=200_000)
        np.savez_compressed(OUT / f'D2_{case}.npz', pos=r.pos, s=r.s, disp=r.disp)
        log(json.dumps(r.summary()))
        M = masks(r)
        out = dict(case=case, nodes=r.nodes, el=EL, reaction=r.reaction, disp_max=r.max_disp())
        # screws: mean axial stress over the shank at three heights, times the section
        ten = {}
        for sx in (-1, 1):
            for z in (1.0, 6.0):
                sel = M['pin'] & (np.hypot(r.pos[:, 0] - sx * XS, r.pos[:, 2] - z) < 1.55)
                vals = []
                for y in (5.0, 14.0, 23.0):
                    w = sel & (np.abs(r.pos[:, 1] - y) < 1.5)
                    vals.append(round(float(r.s[w, 2].mean() * math.pi * 1.5 ** 2), 2) if w.any() else None)
                ten[f'x{sx * XS:g}_z{z:g}'] = vals
        out['pin_axial_force_N_at_y5_14_23'] = ten
        # shear in the pins (txy for +X): mean over the section
        sh = {}
        for sx in (-1, 1):
            for z in (1.0, 6.0):
                sel = M['pin'] & (np.hypot(r.pos[:, 0] - sx * XS, r.pos[:, 2] - z) < 1.55) & (np.abs(r.pos[:, 1] - 14.0) < 1.5)
                sh[f'x{sx * XS:g}_z{z:g}'] = [round(float(r.s[sel, 4].mean() * math.pi * 1.5 ** 2), 2) if sel.any() else None,
                                              round(float(r.s[sel, 11].max()), 1) if sel.any() else None]
        out['pin_shear_force_N_and_max_intensity'] = sh
        away = r.away()
        for half in ('upper', 'lower'):
            mk = M[half] & away
            vm, at = r.peak(mk)
            row = dict(vm=round(vm, 2), at=at, sf_yield=round(45.0 / vm, 2))
            for tag, n in (('Y', (0, 1, 0)), ('Z', (0, 0, 1)), ('X', (1, 0, 0))):
                row['layer_' + tag] = [round(v, 2) if isinstance(v, float) else v for v in r.layer_stress(n, mk)]
                row['shear_' + tag] = [round(v, 2) if isinstance(v, float) else v for v in r.layer_shear(n, mk)]
            out[half] = row
        # contact: gap of the ring pole against each seat after loading, from displacements
        dp = r.disp
        pos = r.pos
        tree = cKDTree(pos)
        for nm, at in (('ring top pole (0,26)', (0, 26.0, 3.7)), ('ring bottom pole (0,-26)', (0, -26.0, 3.7)), ('ring +X (26,0)', (26.0, 0, 3.7)), ('ring -X (-26,0)', (-26.0, 0, 3.7))):
            idx = tree.query_ball_point(at, 0.9)
            ringn = [i for i in idx if M['ring'][i] or abs(math.hypot(pos[i, 0], pos[i, 1]) - 26.0) < 0.02]
            out.setdefault('seat_nodes_disp', {})[nm] = [round(float(dp[i, 1:4][0]), 5) for i in idx[:0]]
            ds = dp[idx][:, 1:4]
            out['seat_nodes_disp'][nm] = [round(float(ds[:, 0].min()), 5), round(float(ds[:, 0].max()), 5), round(float(ds[:, 1].min()), 5), round(float(ds[:, 1].max()), 5)]
        # split gap: how far the facing faces moved apart (upper face minus lower face along Y) near x = 33
        up = (np.abs(pos[:, 1] - H) < 0.02) & (np.abs(pos[:, 0] - 33) < 2) & (pos[:, 2] > 8.2) & (pos[:, 2] < 10)
        lo = (np.abs(pos[:, 1] + H) < 0.02) & (np.abs(pos[:, 0] - 33) < 2) & (pos[:, 2] > 8.2) & (pos[:, 2] < 10)
        if up.any() and lo.any():
            out['split_gap_mm_at_x33'] = round(2 * H + float(dp[up, 2].mean() - dp[lo, 2].mean()), 5)
        out['pad_zone_peak_vm'] = round(float(r.vm[M['pad']].max()), 4) if M['pad'].any() else None
        (RES / f'd2_study_{case}.json').write_text(json.dumps(out, indent=1, default=float))
        print(json.dumps(out, indent=1, default=float))
        close(j.sw, d)
    print('STUDY DONE')
