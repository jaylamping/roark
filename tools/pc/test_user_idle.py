"""Tests for the "is anyone using this PC" check (pytest; run by scripts/check.sh). Rules: conventions/cad-workstation.md section 5."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import user_idle


def test_a_pc_counts_as_free_only_when_input_is_quiet_and_nothing_is_fullscreen() -> None:
    """Guards: bug - SolidWorks launched by sessions took focus from Joey's fullscreen game on Joey-PC (2026-11-07), so a
    job may only move there when he is away; a game on a controller or a film sends no keyboard or mouse input."""
    free = user_idle.free_to_use
    assert free(20 * 60, False, 15 * 60)[0] == 0
    assert free(5 * 60, False, 15 * 60)[0] == 1
    assert free(3 * 3600, True, 15 * 60)[0] == 1  # quiet for hours but fullscreen: in use
    assert free(None, False, 15 * 60)[0] == 2  # could not tell is never "free"
