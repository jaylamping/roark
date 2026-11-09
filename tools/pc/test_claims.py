"""Tests for the Joey-PC claims (pytest; run by scripts/check.sh). Rules: conventions/joey-pc.md section 2."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claims


def test_a_live_claim_blocks_its_worktree_and_solidworks_until_it_goes_quiet(tmp_path: Path) -> None:
    """Guards: bug - two threads drove one SolidWorks instance and one checkout on Joey-PC and crashed it (2026-11-06)."""
    wt = str(tmp_path / "wt-a")
    claims.claim(tmp_path, "arm", wt, 4242, "fea", t=0)
    with pytest.raises(SystemExit):
        claims.claim(tmp_path, "shell", wt, None, "", t=60)
    with pytest.raises(SystemExit):
        claims.claim(tmp_path, "shell", str(tmp_path / "wt-b"), 4242, "", t=60)
    claims.claim(tmp_path, "shell", str(tmp_path / "wt-b"), 5151, "", t=60)  # different worktree and PID: fine
    stale_t = (claims.STALE_MIN + 1) * 60
    claims.claim(tmp_path, "power", wt, None, "", t=stale_t)  # arm went quiet: its claim no longer blocks
    assert [c["session"] for c in claims.who(tmp_path, "5151")] == ["shell"]


def test_heartbeat_keeps_a_session_fresh_and_list_flags_silence(tmp_path: Path) -> None:
    """Guards: bug - the Remote Control session dropped overnight and nobody noticed until morning (2026-11-08)."""
    claims.claim(tmp_path, "arm", str(tmp_path / "wt"), None, "solving", t=0)
    claims.beat(tmp_path, "arm", "case 3 of 7", None, t=10 * 60)
    assert claims.table(tmp_path, 20 * 60, claims.STALE_MIN)[0].startswith("ok")
    assert claims.table(tmp_path, 30 * 60, claims.STALE_MIN)[0].startswith("STALE")
    claims.release(tmp_path, "arm")
    assert claims.table(tmp_path, 30 * 60, claims.STALE_MIN) == ["no claims"]
