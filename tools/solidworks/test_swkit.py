"""Tests for the parts of swkit that need no SolidWorks (pytest). Windows only: the module imports pywin32."""

import os
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("win32gui", reason="swkit is Windows only")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import swkit


def test_a_call_that_does_not_return_is_written_up_and_a_polling_loop_is_not(tmp_path, monkeypatch):
    """Guards: bug - a STEP import held by a hidden dialog never returned and the script said nothing, for as long as
    anyone let it (holly-pc, 2026-11-15). The watch must also stay quiet while the script is waiting in a loop of its
    own (a solve polled every few seconds), or every long solve would be reported."""
    monkeypatch.setenv("ROARK_CLAIMS_DIR", str(tmp_path))
    with swkit.stall_watch(os.getpid(), tmp_path, stall_s=1.0, poll=0.2) as w:  # this process stands in for an idle SolidWorks
        for _ in range(30):
            time.sleep(0.1)  # three seconds of short calls: progress
        assert w.reports == []
        time.sleep(4.0)  # one call that does not come back
    assert len(w.reports) == 1
    text = Path(w.reports[0]).read_text(encoding="utf-8")
    assert "time.sleep(4.0)" in text and "test_swkit.py" in text
    line = (tmp_path / "runs.log").read_text(encoding="utf-8").splitlines()[-1].split("\t")
    assert len(line) == 6 and line[4].startswith("STALLED at test_swkit.py")
    assert sys.getprofile() is None  # the watch leaves the thread as it found it
