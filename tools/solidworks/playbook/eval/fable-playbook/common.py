"""Shared by the benchmark scripts of run fable-playbook: paths, the bracket's numbers, results.json fragments."""
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[4]                                   # the worktree root
sys.path.insert(0, str(WT / 'tools' / 'solidworks'))
OUT = WT / 'cad' / '_wip' / 'sw-eval' / 'fable-playbook'
OUT.mkdir(parents=True, exist_ok=True)

PETG_G_CM3 = 1.19                                      # 03-modelling.md, "Before you call a part done"

# ---- the T1 bracket, from TASKS.md (mm) ----
BASE = (0, 0, 0, 80, 50, 6)                            # x0 y0 z0 x1 y1 z1
UP = (0, 0, 6, 6, 50, 46)
R_IN = 4.0                                             # inside-corner fillet, edge along Y at X 6, Z 6
BASE_HOLES = [(25, 10), (25, 40), (65, 10), (65, 40)]  # (X, Y), dia 5.5
D_BASE = 5.5
BORE = (25.0, 28.0)                                    # (Y, Z), axis along X
D_BORE = 22.0
PCD, D_UP = 31.0, 3.4
UP_HOLES = [(BORE[0] + PCD / 2 * math.cos(math.radians(a)), BORE[1] + PCD / 2 * math.sin(math.radians(a)))
            for a in (45, 135, 225, 315)]              # (Y, Z)
R_OUT = 5.0                                            # base corners at X 80, upright top corners
T = 6.0                                                # plate thickness, both legs
F_MOTOR = 150.0                                        # N, +X, on the bore (T3)


def hand_volume(inside_fillet=R_IN):
    q = 1 - math.pi / 4                                # area of a unit square minus its quarter circle
    return (80 * 50 * 6 + 6 * 50 * 40
            + q * inside_fillet ** 2 * 50              # inside fillet adds
            - 4 * math.pi * (D_BASE / 2) ** 2 * T
            - math.pi * (D_BORE / 2) ** 2 * T
            - 4 * math.pi * (D_UP / 2) ** 2 * T
            - 2 * q * R_OUT ** 2 * T                   # base corners
            - 2 * q * R_OUT ** 2 * T)                  # upright top corners


def put(task, data, seconds=None):
    """Write one task's results fragment; merge.py joins them into results.json."""
    if seconds is not None:
        data['seconds'] = round(seconds)
    (HERE / f'{task}.json').write_text(json.dumps(data, indent=2))
    print('RESULT', task, json.dumps(data), flush=True)


def beat(status, pid=None):
    cmd = [sys.executable, str(WT / 'tools' / 'pc' / 'claims.py'), 'beat', 'sw-eval-fable', '--status', status]
    if pid:
        cmd += ['--sw-pid', str(pid)]
    subprocess.run(cmd, capture_output=True)


class Clock:
    def __init__(self):
        self.t = time.time()

    def s(self):
        return time.time() - self.t
