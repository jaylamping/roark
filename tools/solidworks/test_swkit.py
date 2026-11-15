"""Tests for the parts of swkit that need no SolidWorks (pytest). Windows only: the module imports pywin32."""

import ctypes
import os
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("win32gui", reason="swkit is Windows only")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import swkit


def test_a_call_that_does_not_return_is_written_up_and_a_polling_loop_is_not(tmp_path, monkeypatch):
    """Guards: bug - a STEP import held by a hidden dialog never returned and the script said nothing, for as long as
    anyone let it (holly-pc, 2026-11-15). The watch must also stay quiet while the script is waiting in a loop of its
    own (a solve polled every few seconds) and while it computes, or every long solve and read would be reported."""
    monkeypatch.setenv("ROARK_CLAIMS_DIR", str(tmp_path))
    with swkit.stall_watch(os.getpid(), tmp_path, stall_s=1.0, poll=0.2) as w:  # this process stands in for an idle SolidWorks
        for _ in range(30):
            time.sleep(0.1)  # three seconds in a wait loop of the script's own
        end = time.time() + 2.0
        while time.time() < end:
            sum(range(1000))  # two seconds of computing
        threading.Event().wait(2.0)  # two seconds waiting on an event, as for a child process or a worker thread
        assert w.reports == []
        ctypes.windll.kernel32.SleepEx(6000, False)  # one call out of Python that does not come back, as a COM call
    assert len(w.reports) == 1
    text = Path(w.reports[0]).read_text(encoding="utf-8")
    assert "SleepEx(6000, False)" in text and "test_swkit.py" in text
    line = (tmp_path / "runs.log").read_text(encoding="utf-8").splitlines()[-1].split("\t")
    assert len(line) == 6 and line[4].startswith("STALLED at test_swkit.py")
