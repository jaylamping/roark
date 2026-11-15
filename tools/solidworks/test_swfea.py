"""Tests for the parts of swfea that need no SolidWorks (pytest). Windows only: the module imports pywin32."""

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("win32gui", reason="swfea is Windows only")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import swfea


def test_the_fast_stress_read_is_used_only_when_it_covers_the_mesh():
    """Guards: bug - reading stresses over the bodies is 5 times faster than GetStress (shoulder hub, 2026-11-13) but
    lists a node on two bodies twice, and a read that missed a body would score a part on some of its nodes only."""
    ids = [5, 2, 9, 2]  # node 2 lies on two bodies
    value = {2: 1.0, 5: 2.0, 9: 3.0}
    parts = [(col, np.c_[ids, [value[i] * col for i in ids]]) for col in (1, 2, 3, 4, 5, 6, 10)]
    s = swfea.stress_table(parts, {2, 5, 9})
    assert s[:, 0].tolist() == [2, 5, 9]
    assert s[:, 10].tolist() == [10.0, 20.0, 30.0]
    t = np.array([[s[0, 1], s[0, 4], s[0, 5]], [s[0, 4], s[0, 2], s[0, 6]], [s[0, 5], s[0, 6], s[0, 3]]])
    assert np.allclose(np.linalg.eigvalsh(t)[::-1], s[0, 7:10])
    assert swfea.stress_table(parts, {2, 5, 9, 11}) is None  # the mesh has a node the read did not return
    assert swfea.stress_table(parts[:-1] + [(10, np.c_[[2, 5, 8], [1, 2, 3]])], None) is None  # components disagree
