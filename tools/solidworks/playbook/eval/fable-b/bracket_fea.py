"""The wall-bracket load case for B2 and B3: 60 N down on the top patch X 55 to 65, screwed to the wall at X 0.

Two supports, because a fixed hole wall has a singular edge (05-fea.md):
  'holes': the two dia 4.5 hole walls fixed. Nothing stops the plate moving into the wall, so it is the soft bound.
  'wall':  the whole wall face X 0 fixed (as if glued to the wall). The stiff bound.
The numbers the two agree on are the result. Peaks are read outside a FIXED distance DFIX from the fixture nodes at every
mesh size (a mask in element sizes shrinks with the mesh). The load patch is at the low-stress end of the arm; its own
nodes are left out the same way.
"""
import numpy as np
from scipy.spatial import cKDTree

from common import ROOT
from swfea import PETG, static
from swkit import Failed, expect, log, pick

F = 60.0
HOLE_R = 2.25
DFIX = 2.0            # mm from fixture nodes left out of every peak
SIM = ROOT / 'cad' / '_sim' / 'sw-eval' / 'fable-b'
SIM.mkdir(parents=True, exist_ok=True)
ALLOW = dict(vm=45.0, tension=22.5, shear=13.0)
NORMALS = dict(X=(1, 0, 0), Y=(0, 1, 0), Z=(0, 0, 1))


def solve(j, d, tag, support, el, ctrl=None, predict=None):
    """One solve. ctrl(d) -> [(faces, size)]. predict = dict(nodes, disp, peak) written to the log BEFORE the solve."""
    d.ForceRebuild3(False)
    holes = pick(d, kind='cyl', r=HOLE_R, inside=[-0.1, 15, 5, 5.1, 25, 55])
    expect(tag + ' hole faces', len(holes), 2, 0)
    wall = pick(d, kind='plane', normal=(-1, 0, 0), inside=[-0.01, -1e3, -1e3, 0.01, 1e3, 1e3])
    expect(tag + ' wall faces', len(wall), 1, 0)
    patch = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
    expect(tag + ' load patch faces', len(patch), 1, 0)
    fix = holes if support == 'holes' else wall
    c = ctrl(d) if ctrl else []
    for fs, size in c:
        if not fs:
            raise Failed(tag + ': empty mesh-control pick')
    if predict:
        log(f'{tag}: PREDICT nodes ~{predict["nodes"]}, max disp ~{predict["disp"]} mm, peak {predict["peak"]}')
    r = static(j, d, tag, PETG, fixtures=[('fixed', fix)], loads=[('normal', patch, F)], el=el, ctrl=c, loose_ok=True)
    np.savez_compressed(SIM / f'{tag}.npz', pos=r.pos, s=r.s, disp=r.disp, fixed=r.fixed_pts, loaded=r.loaded_pts,
                        reaction=np.array(r.reaction))
    return r


def mask(r, dfix=DFIX):
    keep = np.ones(len(r.pos), bool)
    for pts in (r.fixed_pts, r.loaded_pts):
        if pts is None or not len(pts):
            raise Failed(r.name + ': fixture or load nodes were not read, so no peak can be cleared of them')
        keep &= cKDTree(pts).query(r.pos)[0] >= dfix
    return keep


def measures(r, keep=None):
    """vm, and for each print direction the tension across layers and the shear between them: value, place, factor."""
    keep = mask(r) if keep is None else keep
    vm, at = r.peak(keep)
    out = dict(vm=(round(vm, 2), at, round(ALLOW['vm'] / vm, 2)))
    for k, n in NORMALS.items():
        t, ta = r.layer_stress(n, keep)
        s, sa = r.layer_shear(n, keep)
        out[k] = dict(tension=(round(t, 2), ta, round(ALLOW['tension'] / t, 2) if t > 0 else None),
                      shear=(round(s, 2), sa, round(ALLOW['shear'] / s, 2)))
    return out


def factors(m, direction):
    """(sf_yield, sf_layer, sf_shear, min) for one print direction."""
    a = (m['vm'][2], m[direction]['tension'][2], m[direction]['shear'][2])
    return a + (min(a),)


def checks(r, x=35.0, c=6.0, inertia=1440.0, ztop=52.0, tag=''):
    """Reaction against the load, and bending stress on the top face of the plain arm at X = x against M c / I."""
    top = (np.abs(r.pos[:, 0] - x) < 1.5) & (r.pos[:, 2] > ztop - 0.01) & (np.abs(r.pos[:, 1] - 20) < 3)
    sx = float(r.s[top, 1].mean()) if top.any() else float('nan')
    hand = F * (60.0 - x) * c / inertia
    out = dict(reaction=r.reaction, reaction_err_pct=round(100 * abs(r.reaction[3] - F) / F, 3),
               reaction_fz=r.reaction[2], sx_top=round(sx, 3), sx_hand=round(hand, 3), sx_nodes=int(top.sum()),
               sx_err_pct=round(100 * abs(sx - hand) / hand, 2), max_disp=round(r.max_disp(), 4),
               vm_all=round(float(r.vm.max()), 2), vm_all_at=r.pos[int(np.argmax(r.vm))].round(2).tolist(),
               nodes=r.nodes, excessive_prompt=bool(r.excessive))
    log(tag, 'checks', out)
    return out
