"""Shared paths and small helpers for benchmark run fable-b."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]                                  # the worktree
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
WIP = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-b'
WIP.mkdir(parents=True, exist_ok=True)
DENS = 1.19e-3                                          # g/mm3, printed PETG (03-modelling.md)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(task, obj):
    """Write one task's result object to <task>.json beside the scripts (merged into results.json at the end)."""
    (HERE / f'{task}.json').write_text(json.dumps(obj, indent=1, default=float))


def cyl(f):
    """(axis point xyz mm, axis direction, radius mm) of a cylindrical face."""
    p = f.GetSurface.CylinderParams
    return [v * 1e3 for v in p[0:3]], list(p[3:6]), p[6] * 1e3
