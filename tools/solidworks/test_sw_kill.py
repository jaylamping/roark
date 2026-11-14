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
    for healthy in ("idle", "solving", "busy", "unsettled", "gone"):
        assert not end(healthy, False, False)[0]
        assert end(healthy, False, True)[0]
    assert not end("zombie", True, False)[0]  # the keeper is replaced by launch(), not by a passing session
    assert end("idle", True, True)[0]


def test_a_dead_looking_instance_is_watched_before_it_is_ended():
    """Guards: bug - a process in its first second, or in an ordinary exit, has no windows and answers nothing, exactly
    like a half-closed one, and an instance driven by a client this module has no record of reads as abandoned while it
    meshes (found reviewing sw_kill.py on holly-pc, 2026-11-13). launch() watches 20 s and 300 s before it believes
    either; ending on one look would end another session's launch or its working instance."""
    assert sw_kill.settled("zombie", 1) == "unsettled" and sw_kill.settled("orphan", 20) == "unsettled"
    assert sw_kill.settled("zombie", 400) == "zombie"

    def nap(_s):
        return None

    looks = iter(["zombie", "zombie", "gone"])  # an ordinary exit finishing
    assert not sw_kill.stays_dead(lambda: next(looks), 20, sleep=nap)
    looks = iter(["orphan"] * 10 + ["busy"] + ["orphan"] * 60)  # a mesh that answered once
    assert not sw_kill.stays_dead(lambda: next(looks), 300, sleep=nap)
    assert sw_kill.stays_dead(lambda: "zombie", 20, sleep=nap)
    assert not sw_kill.stays_dead(lambda: "idle", 20, sleep=nap)
    # A mesh for an unrecorded client never answers (19 minutes seen), but it burns a core; a half-closed one does too.
    assert sw_kill.working("orphan", 290, 300) and not sw_kill.working("orphan", 3, 300)
    assert not sw_kill.working("zombie", 290, 300)
