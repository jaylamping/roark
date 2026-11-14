"""A mesh series on one bracket file for the T3 load case, with the masks stated. Used by T3, T4 and T5."""
import hashlib

import numpy as np
from scipy.spatial import cKDTree

from case import checks, run
from swkit import close, log, open_doc, pick

BORE_CLEAR = 1.5        # mm: nodes nearer the rigidly loaded bore wall than this are not scored


def masks(r):
    """play: the playbook's mask (two global elements from fixture and load faces).
    mine: two global elements from the fixed hole walls, 1.5 mm from the bore wall. The bore carries a rigid remote load,
    whose artefact is at its two edges; the motor holes 2.8 mm away are real features and must be scored."""
    df = cKDTree(r.fixed_pts).query(r.pos)[0]
    dl = cKDTree(r.loaded_pts).query(r.pos)[0]
    return r.away(), (df >= 2 * r.el) & (dl >= BORE_CLEAR)


def score(r, layer):
    play, mine = masks(r)
    n = np.array(layer, float)
    vm, at = r.peak(mine)
    ls, lat = r.layer_stress(n, mine)
    row = dict(el_mm=r.el, nodes=r.nodes, peak_vm_mpa=round(vm, 2), peak_at_mm=at, layer_stress_mpa=round(ls, 2),
               layer_at_mm=lat, peak_vm_playbook_mask=round(r.peak(play)[0], 2),
               layer_playbook_mask=round(r.layer_stress(n, play)[0], 2), vm_max_unmasked=round(float(r.vm.max()), 2),
               vm_max_unmasked_at=r.pos[int(np.argmax(r.vm))].round(2).tolist(), max_disp_mm=round(r.max_disp(), 4))
    return row


def series(j, path, tag, steps, extra, layer=(0, 0, 1), tol=0.05):
    """steps: [(global el, local size)]. extra(d) -> faces that get the local size besides the holes and the bore.
    Stops when both the von Mises peak and the layer stress move under tol between two steps. Returns rows, converged,
    the last Result and its check numbers."""
    log(tag, 'model', path.name, 'sha256', hashlib.sha256(path.read_bytes()).hexdigest())
    rows, conv, r, chk = [], False, None, None
    for k, (el, local) in enumerate(steps):
        d = open_doc(j.sw, path)
        r = run(j, d, f'{tag}_{k}', el, local, [(extra(d), local)])
        chk = checks(r, f'{tag}_{k} ')
        close(j.sw, d)
        row = score(r, layer)
        row['local_mm'] = local
        rows.append(row)
        log('ROW', row)
        if len(rows) > 1:
            a, b = rows[-2], rows[-1]
            dv = abs(b['peak_vm_mpa'] - a['peak_vm_mpa']) / a['peak_vm_mpa']
            dl = abs(b['layer_stress_mpa'] - a['layer_stress_mpa']) / max(a['layer_stress_mpa'], 1e-9)
            log(f'{tag}: step moved the vm peak {100 * dv:.1f} %, the layer stress {100 * dl:.1f} %')
            if dv <= tol and dl <= tol:
                conv = True
                break
    return rows, conv, r, chk
