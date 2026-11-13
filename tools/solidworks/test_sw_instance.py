"""Tests for the parts of sw_instance that need no SolidWorks (pytest). Windows only: the module imports pywin32."""

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("win32gui", reason="sw_instance is Windows only")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_instance


def test_only_a_half_closed_or_undriven_instance_is_unhealthy():
    """Guards: bug - launch() refused for 300 s behind any instance that was solving or meshing, so sessions took turns
    (holly-pc, 2026-11-12, PR #70); and one half-closed instance stalled every launch at the splash screen (PR #66)."""
    c = sw_instance.classify
    assert c(True, 93, False, False) == "idle"
    assert c(False, 93, True, False) == "solving"  # star.exe under it, client blocked or gone
    assert c(False, 93, False, True) == "busy"  # meshing or rebuilding: no solver, client alive in the call
    assert c(False, 93, False, False) == "orphan"  # client killed mid-call
    # Half-closed wins over everything: its killed-off solver and a client hung in ExitApp must not make it look healthy.
    assert c(False, 0, True, True) == "zombie"


def test_startup_limit_stops_while_a_healthy_instance_is_busy_and_a_zombie_ends_it(monkeypatch):
    """Guards: bug - a start waits at the splash screen until the oldest instance answers (150 s and more, holly-pc,
    2026-11-13, PR #70), so a fixed 300 s startup limit would refuse behind a long solve just as the old guard did."""
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


def test_big_solve_takes_only_a_lock_whose_holder_has_gone(tmp_path):
    """Guards: bug - a 13 GB solve started beside another session's run and stopped it (holly-pc, 2026-11-13, PR #70).
    The lock only helps if a live holder is never displaced, including one that wrote the file by hand."""
    lock = tmp_path / "solve.lock"
    lock.write_text("gone thread\n999999999\n1.0\n")  # no such process
    with sw_instance.big_solve("a", path=str(lock), timeout=5, poll=0.1):
        text = lock.read_text()
        assert text.splitlines()[:2] == ["a", str(os.getpid())]
        # This process holds it and is alive, so a second taker waits and then gives up; the lock is left alone.
        with pytest.raises(TimeoutError), sw_instance.big_solve("b", path=str(lock), timeout=0.3, poll=0.1):
            pass
        assert lock.read_text() == text
    assert not lock.exists()

    for by_hand in (f"left arm thread, pid {os.getpid()}, started 2026-11-13T09:30", "left arm thread, back soon"):
        lock.write_text(by_hand)  # another layout: held unless every pid in it is gone
        with pytest.raises(TimeoutError), sw_instance.big_solve("b", path=str(lock), timeout=0.3, poll=0.1):
            pass
        assert lock.read_text() == by_hand
    lock.write_text("left arm thread, pid 999999999")
    with sw_instance.big_solve("b", path=str(lock), timeout=5, poll=0.1):
        pass
