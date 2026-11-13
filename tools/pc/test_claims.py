"""Tests for the CAD workstation claims (pytest; run by scripts/check.sh). Rules: conventions/cad-workstation.md section 2."""

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


def test_a_stale_session_that_resumes_cannot_beat_over_a_new_owner(tmp_path: Path) -> None:
    """Guards: bug - beat skipped the checks claim makes, so a session back from silence held a worktree or PID that another
    session had claimed meanwhile (found 2026-11-10)."""
    wt_a, wt_b = str(tmp_path / "wt-a"), str(tmp_path / "wt-b")
    claims.claim(tmp_path, "arm", wt_a, 4242, "", t=0)
    stale_t = (claims.STALE_MIN + 1) * 60
    claims.claim(tmp_path, "power", wt_a, None, "", t=stale_t)  # arm went quiet; power takes its worktree
    with pytest.raises(SystemExit) as e:
        claims.beat(tmp_path, "arm", "back", None, t=stale_t + 60)
    assert str(e.value) == f"{claims.norm(wt_a)} is claimed by power (last beat 1 min ago)"
    claims.claim(tmp_path, "shell", wt_b, 5151, "", t=stale_t)
    claims.release(tmp_path, "power")
    with pytest.raises(SystemExit) as e:
        claims.beat(tmp_path, "arm", None, 5151, t=stale_t + 60)  # someone else's SolidWorks
    assert str(e.value) == "SolidWorks PID 5151 is claimed by shell"
    assert claims.beat(tmp_path, "arm", "back", None, t=stale_t + 60)["beat"] == stale_t + 60


def test_an_unreadable_claim_file_blocks_claims_until_removed_by_hand(tmp_path: Path) -> None:
    """Guards: bug - an unreadable claim counted as infinitely stale, so its worktree and SolidWorks were handed out again
    (found 2026-11-10)."""
    claims.claim(tmp_path, "arm", str(tmp_path / "wt-a"), None, "", t=0)
    (tmp_path / "power.json").write_text("{not json")
    msg = (f"claim file {tmp_path / 'power.json'} can't be read; it may be a live session's. "
           "Check it and delete it by hand.")
    with pytest.raises(SystemExit) as e:
        claims.claim(tmp_path, "shell", str(tmp_path / "wt-b"), None, "", t=60)
    assert str(e.value) == msg
    with pytest.raises(SystemExit) as e:
        claims.beat(tmp_path, "arm", None, None, t=60)
    assert str(e.value) == msg
    assert claims.table(tmp_path, 60, claims.STALE_MIN)[1].split()[0:2] == ["BROKEN", "power"]


def test_a_threads_fea_instance_shares_its_worktree_but_not_its_pid(tmp_path: Path) -> None:
    """Guards: number - a thread runs up to two SolidWorks instances, the second claimed as `<session>-fea` in the same
    worktree (conventions/cad-workstation.md section 1)."""
    wt = str(tmp_path / "wt-a")
    claims.claim(tmp_path, "arm", wt, 4242, "", t=0)
    assert claims.claim(tmp_path, "arm-fea", wt, 4343, "", t=0)["worktree"] == claims.norm(wt)
    with pytest.raises(SystemExit) as e:
        claims.claim(tmp_path, "power-fea", wt, 4444, "", t=0)
    assert str(e.value) == f"{claims.norm(wt)} is claimed by arm-fea (last beat 0 min ago)"  # files are read in name order
    with pytest.raises(SystemExit) as e:
        claims.beat(tmp_path, "arm-fea", None, 4242, t=60)
    assert str(e.value) == "SolidWorks PID 4242 is claimed by arm"


def test_a_session_name_cannot_reach_outside_the_claims_folder(tmp_path: Path) -> None:
    """Guards: safety - cad-workstation.md section 4: deleting files outside the thread's own worktree needs Joey, and claims.py
    runs without a prompt, so release and beat must not touch a file a session name points elsewhere."""
    d = tmp_path / "claims"
    outside = tmp_path / "x.json"
    outside.write_text('{"beat": 0}')
    for call in (lambda s: claims.release(d, s), lambda s: claims.beat(d, s, "x", None, t=0),
                 lambda s: claims.claim(d, s, str(tmp_path), None, "", t=0)):
        for bad in ("../x", "Arm", "arm/x", ""):
            with pytest.raises(SystemExit) as e:
                call(bad)
            assert str(e.value) == f"session name {bad!r}: lower case letters, digits and '-' only"
    assert outside.read_text() == '{"beat": 0}'
    assert not d.exists()


def test_who_names_the_launcher_of_an_instance_nobody_claimed(tmp_path: Path) -> None:
    """Guards: bug - the shoulder FEA ran SolidWorks all day without a claim, so `who <pid>` said nobody while its
    instances held up every other launch (holly-pc, 2026-11-13)."""
    assert claims.who(tmp_path, "4242") == []
    claims.note_instance(tmp_path, 4242, 111.5, str(tmp_path / "wt"), 77, "python fea_shoulder.py HUBL", t=5)
    (got,) = claims.who(tmp_path, "4242")
    assert got["unclaimed"] and got["client_pid"] == 77 and got["worktree"] == claims.norm(str(tmp_path / "wt"))
    assert claims.table(tmp_path, 10, claims.STALE_MIN) == ["no claims"]  # a note is not a claim and blocks nothing
    assert claims.instance_note(tmp_path, 4242, sw_started=999.0) is None  # the PID was reused by another process
    claims.claim(tmp_path, "shoulder", str(tmp_path / "wt"), 4242, "", t=10)
    assert [c["session"] for c in claims.who(tmp_path, "4242")] == ["shoulder"]  # a real claim wins
    claims.drop_instance(tmp_path, 4242)
    assert claims.instance_note(tmp_path, 4242) is None
