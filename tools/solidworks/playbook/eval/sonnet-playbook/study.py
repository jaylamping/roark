import json, math, sys
from pathlib import Path
WT = r"J:\code\roark-wt\sw-eval-sonnet"
sys.path.insert(0, WT + r"\tools\solidworks")
import numpy as np
from swkit import *
from swfea import *
from t1 import OUT, R
BORE_C = (3.0, 25.0, 28.0)

def run_case(j, d, tag, el, fx=150.0, ctrl_faces=None, ctrl_ratio=0.5):
    fixed = pick(d, kind='cyl', r=2.75)
    expect(tag + ' base hole faces', len(fixed), 4, 0)
    bore = pick(d, kind='cyl', r=11.0)
    expect(tag + ' bore faces', len(bore), 1, 0)
    ctrl = []
    cf = ctrl_faces(d) if ctrl_faces else []
    if cf:
        ctrl.append((cf, max(0.4, el * ctrl_ratio)))
    return static(j, d, tag, PETG, fixtures=[('fixed', fixed)],
                  loads=[('remote', bore, BORE_C, (fx, 0, 0), (0, 0, 0))], el=el, ctrl=ctrl)

def report(r, label):
    vm, at = r.peak()
    lay, lat = r.layer_stress((0, 0, 1))
    return dict(el_mm=r.el, nodes=r.nodes, peak_vm_mpa=vm, peak_at_mm=at, layer_stress_mpa=lay, layer_at=lat,
                max_disp_mm=r.max_disp(), reaction_n=r.reaction, applied=r.applied, all_nodes_max_vm=float(r.vm.max()))
