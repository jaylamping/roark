"""Tests for the "is anyone using this PC" check (pytest; run by scripts/check.sh). Rules: conventions/cad-workstation.md section 5."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import user_idle


def test_a_pc_counts_as_free_only_when_nobody_types_and_nothing_is_fullscreen() -> None:
    """Guards: bug - SolidWorks launched by sessions took focus from Joey's fullscreen game on Joey-PC (2026-11-07), so a
    job may start there unannounced only when he is away. His keep-alive script sweeps the mouse every two minutes once
    the PC is idle (about 1.2 s each), which must not read as him; he was logged in bursts of 19 to 36 s (2026-11-13);
    and a game on a controller or a film sends no input, which must not read as him being away."""
    free, bursts = user_idle.free_to_use, user_idle.bursts
    quiet = [False] * 180
    sweeps = quiet.copy()
    sweeps[10:12] = sweeps[130:132] = [True, True]  # two sweeps, two sampled seconds each
    joey = quiet.copy()
    joey[40:59] = [True] * 19
    assert free(*bursts(quiet), False, 180)[0] == 0
    assert bursts(sweeps) == (4, 2) and free(*bursts(sweeps), False, 180)[0] == 0
    assert bursts(joey) == (19, 19) and free(*bursts(joey), False, 180)[0] == 1
    assert free(9, 1, False, 180)[0] == 1  # scattered clicks: more than the sweeps can make
    assert free(0, 0, True, 180)[0] == 1  # no input but fullscreen: in use
    assert free(None, 0, False, 180)[0] == 2  # could not tell is never "free"
