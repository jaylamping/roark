"""Tests for the rules sw_kill.py applies before it ends a SolidWorks instance (pytest). They need no SolidWorks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_kill


def test_only_a_dead_instance_is_ended_without_force():
    """Guards: bug - an instance 28 minutes into a real solve was taken for hung and killed, leaving its solver running
    with nothing to read the result (holly-pc, 2026-11-11, PR #66); and half-closed instances that nobody was allowed to
    end stalled every launch until Joey ran taskkill by hand."""
    end = sw_kill.may_end
    assert end("zombie", False, False)[0] and end("orphan", False, False)[0]
    for healthy in ("idle", "solving", "busy", "unsettled"):
        assert not end(healthy, False, False)[0]
        assert end(healthy, False, True)[0]
    assert not end("zombie", True, False)[0]  # the keeper is replaced by launch(), not by a passing session
    assert end("idle", True, True)[0]
    assert sw_kill.settled("orphan", 40) == "unsettled"  # its client may have just let go: launch() waits 300 s too
    assert sw_kill.settled("orphan", 400) == "orphan"
