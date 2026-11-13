"""Tests for the "is anyone using this PC" check (pytest; run by scripts/check.sh). Rules: conventions/cad-workstation.md section 5."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import user_idle


def test_a_pc_counts_as_free_only_when_nobody_types_and_nothing_is_fullscreen() -> None:
    """Guards: bug - SolidWorks launched by sessions took focus from Joey's fullscreen game on Joey-PC (2026-11-07), so a
    job may only move there when he is away. His keep-alive script nudges the mouse every ten minutes, which must not
    read as him being there; a game on a controller or a film sends no input, which must not read as him being away."""
    free = user_idle.free_to_use
    assert free(0, False, 180)[0] == 0
    assert free(user_idle.NUDGE_S, False, 180)[0] == 0  # one keep-alive nudge
    assert free(user_idle.NUDGE_S + 1, False, 180)[0] == 1  # a person
    assert free(0, True, 180)[0] == 1  # no input but fullscreen: in use
    assert free(None, False, 180)[0] == 2  # could not tell is never "free"
