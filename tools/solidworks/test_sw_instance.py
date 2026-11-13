"""Tests for the parts of sw_instance that need no SolidWorks (pytest). Windows only: the module imports pywin32."""

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("win32gui", reason="sw_instance is Windows only")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_instance


def test_only_a_half_closed_or_undriven_instance_is_unhealthy():
    """A launch must go ahead beside a solve or a long call, and must still refuse for the instance that stalls it for ever."""
    c = sw_instance.classify
    assert c(True, 93, False, False) == "idle"
    assert c(False, 93, True, False) == "solving"  # star.exe under it, client blocked or gone
    assert c(False, 93, False, True) == "busy"  # meshing or rebuilding: no solver, client alive in the call
    assert c(False, 93, False, False) == "orphan"  # client killed mid-call
    # Half-closed wins over everything: its killed-off solver and a client hung in ExitApp must not make it look healthy.
    assert c(False, 0, True, True) == "zombie"


def test_startup_limit_stops_while_a_healthy_instance_is_busy_and_a_zombie_ends_it(monkeypatch):
    """The 300 s refusal behind a long solve must not come back as a 300 s startup timeout at the splash screen."""
    now = [1000.0]
    others = [[(7, "solving")]]
    monkeypatch.setattr(sw_instance.time, "time", lambda: now[0])
    monkeypatch.setattr(sw_instance, "_others", lambda own_pid=None: others[0])
    clock = sw_instance._StartClock(1, timeout=300, busy_wait=7200)
    now[0] += 3000  # a 50 minute solve in the instance the splash screen waits for
    assert clock.running()
    others[0] = []
    now[0] += 200  # it answered: the ordinary limit runs again
    assert clock.running()
    now[0] += 200
    assert not clock.running()

    clock = sw_instance._StartClock(1, timeout=300, busy_wait=7200)
    others[0] = [(7, "busy")]
    now[0] += 7600  # busy_wait is the cap
    assert not clock.running()

    clock = sw_instance._StartClock(1, timeout=300, busy_wait=7200)
    others[0] = [(8, "zombie")]
    now[0] += 20
    with pytest.raises(RuntimeError, match="half-closed"):
        clock.running()


def test_big_solve_takes_over_a_dead_holders_lock_and_waits_for_a_live_one(tmp_path):
    lock = str(tmp_path / "solve.lock")
    Path(lock).write_text("gone thread\n999999999\n1.0\n")  # no such process
    with sw_instance.big_solve("a", path=lock, timeout=5, poll=0.1):
        text = Path(lock).read_text()
        assert text.splitlines()[:2] == ["a", str(os.getpid())]
        # This process holds it and is alive, so a second taker waits and then gives up; the lock is left alone.
        with pytest.raises(TimeoutError), sw_instance.big_solve("b", path=lock, timeout=0.3, poll=0.1):
            pass
        assert Path(lock).read_text() == text
    assert not os.path.exists(lock)
