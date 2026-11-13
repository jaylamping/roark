"""Picture sheets for the R1g shim sets (2026-11-13): each build plate seen from above, every piece outlined from a section at its
mid-height and labelled with its thickness and notch code, plus a side scan (height along a line through each piece) to show the
printed thickness steps. Reads each set's result.json and plate STL.
    python shim_sheet.py SET_DIR OUT_PNG TITLE      (SET_DIR holds A/, B/, ... with result.json and the plate STL; under capped.py)"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

root, out, title = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
plates = sorted(p for p in root.iterdir() if (p / 'result.json').exists())
fig, axs = plt.subplots(2, len(plates), figsize=(6.5 * len(plates), 10), gridspec_kw=dict(height_ratios=[3, 1]), squeeze=False)
for k, pd in enumerate(plates):
    res = json.loads((pd / 'result.json').read_text())
    stl = next(pd.glob('*.stl'))
    m = trimesh.load(stl)
    ax, ax2 = axs[0][k], axs[1][k]
    zs = np.unique(np.round(m.vertices[:, 2], 3))
    sec = m.section(plane_origin=[0, 0, 0.1], plane_normal=[0, 0, 1])
    if sec is not None:
        for e in sec.discrete:
            ax.plot(e[:, 0], e[:, 1], color='#333333', lw=0.6)
    pieces = res.get('rings') or res.get('plates') or []
    info = res.get('info', {})
    ax.set_title(f'{pd.name}: first layer {res.get("first_layer")}, then 0.10 layers; {int(float(info.get("prediction", 0)) / 60)} min, {info.get("weight", "?")} g', fontsize=10)
    ax.set_aspect('equal')
    ax.grid(alpha=0.2)
    # scan: each piece's printed thickness measured on its own body (components standing on the plate; lips and tabs sit on top)
    comps = [c for c in m.split(only_watertight=False) if c.bounds[0, 2] < 0.01 and c.area > 20.0]
    nom = sorted([p_['t'] for p_ in pieces])
    meas = []
    for c in comps:
        t_ = round(float(c.bounds[1, 2]), 3)
        cx, cy = c.bounds[:, :2].mean(axis=0)
        ax.text(cx, cy, f'{t_:.2f}', ha='center', va='center', fontsize=8, color='#1f4e8c', fontweight='bold')
        meas.append(t_)
    meas = sorted(meas)
    ax2.plot(range(len(nom)), nom, 'o', ms=7, mfc='none', mec='#999999', label='nominal')
    ax2.plot(range(len(meas)), meas, 'x', ms=6, color='#2a7f2a', label='modelled (mesh body height)')
    ax2.set_ylabel('thickness (mm)')
    ax2.set_xlabel('pieces, sorted')
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)
    ax2.set_title('scan: each piece body height against its nominal thickness', fontsize=9)

fig.suptitle(title, fontsize=12)
fig.tight_layout()
fig.savefig(out, dpi=110)
print('saved', out)
