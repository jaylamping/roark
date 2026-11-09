"""Tests for the CAD writer lock, the LFS budget and the hook installer (pytest; run by scripts/check.sh).

Rules: conventions/cad.md section 6.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cad_lock
import gitlfs
import install_hooks
import lfs_budget

NO_LIMITS = {
    "pushMaxBytes": 10**12,
    "monthMaxBytes": 10**12,
    "storageWarnBytes": 10**12,
    "storageMaxBytes": 10**12,
}


def pointer(size: int, oid: str) -> str:
    return (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {size}\n"
    )


def git(root: Path, *args: str) -> str:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def commit(root: Path, files: dict[str, str], msg: str) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "commit.gpgsign", "false")
    commit(
        tmp_path,
        {"cad/shoulder/shoulder_a.SLDPRT": pointer(5_000_000, "1" * 64)},
        "base",
    )
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def make_stale(lock: Path) -> dict:
    data = json.loads(lock.read_text())
    data["updated"] = time.time() - cad_lock.STALE_SECONDS - 1
    lock.write_text(json.dumps(data))
    return data


def test_only_the_lock_holder_may_commit_cad(tmp_path: Path) -> None:
    """Guards: number - one CAD writer at a time; committing CAD needs the lock (conventions/cad.md section 6)."""
    lock = tmp_path / ".cad-writer.lock"
    assert not cad_lock.check("anyone", lock)[0]
    assert cad_lock.acquire("shoulder", path=lock)[0]
    assert not cad_lock.acquire("torso", path=lock)[0]
    assert cad_lock.check("shoulder", lock)[0]
    assert not cad_lock.check("torso", lock)[0]
    assert not cad_lock.check(None, lock)[0]
    assert not cad_lock.release("torso", lock)[0]
    assert cad_lock.release("shoulder", lock)[0]
    assert list(tmp_path.iterdir()) == []  # no temp files left behind


def test_stale_lock_takeover_is_explicit_and_fails_closed(tmp_path: Path) -> None:
    """Guards: bug - two sessions recovering one stale lock could both end up holding it (CAD process review, 2026-11-08)."""
    lock = tmp_path / ".cad-writer.lock"
    assert cad_lock.acquire("shoulder", path=lock)[0]
    stale = make_stale(lock)
    ok, msg = cad_lock.acquire("torso", path=lock)
    assert not ok and "--take-stale" in msg
    guard = lock.with_name(lock.name + ".recover")
    guard.write_text(json.dumps({"token": "another recoverer"}))
    ok, msg = cad_lock.acquire("torso", path=lock, take_stale=True)
    assert not ok and "recovery guard" in msg
    assert guard.exists()  # only its creator removes a guard
    guard.unlink()
    lock.write_text(
        json.dumps(dict(stale, owner="shell", updated=time.time()))
    )  # changed hands after the stale read
    assert not cad_lock._take_stale(
        lock, stale, {"owner": "torso", "updated": time.time()}
    )[0]
    assert json.loads(lock.read_text())["owner"] == "shell"
    make_stale(lock)
    assert cad_lock.acquire("torso", path=lock, take_stale=True)[0]
    assert json.loads(lock.read_text())["owner"] == "torso"


def test_unreadable_lock_is_held_not_stale(tmp_path: Path) -> None:
    """Guards: bug - an empty, half-written lock file once read as stale and let a second writer in (CAD process review, 2026-11-08)."""
    lock = tmp_path / ".cad-writer.lock"
    lock.write_text("")
    assert not cad_lock.acquire("torso", path=lock, take_stale=True)[0]
    assert not cad_lock.check("torso", lock)[0]
    assert lock.exists()


def test_budget_counts_only_objects_the_target_remote_lacks(repo: Path) -> None:
    """Guards: number - pushMaxBytes in cad/manifests/lfs-budget.json, counted against the remote pushed to."""
    budget = dict(NO_LIMITS, pushMaxBytes=50_000_000)
    commit(
        repo,
        {
            "cad/shoulder/copy.SLDPRT": pointer(
                5_000_000, "1" * 64
            ),  # already on origin
            "cad/shoulder/shoulder_new.SLDPRT": pointer(60_000_000, "3" * 64),
        },
        "new",
    )
    git(repo, "update-ref", "refs/remotes/fork/main", "HEAD")
    ok, msgs = lfs_budget.check_push(
        ["HEAD", "--not", "--remotes=origin"], repo, budget, remote="origin"
    )
    assert not ok and "adds 60.0 MB in 1 new object" in msgs[0]
    assert (
        "adds 0.0 MB"
        in lfs_budget.check_push(
            ["HEAD", "--not", "--remotes=fork"], repo, budget, remote="fork"
        )[1][0]
    )
    os.environ["CAD_BUDGET_OK"] = "1"
    try:
        assert lfs_budget.check_push(
            ["HEAD", "--not", "--remotes=origin"], repo, budget
        )[0]
    finally:
        del os.environ["CAD_BUDGET_OK"]


def test_all_refs_of_one_push_are_checked_together() -> None:
    """Guards: bug - each ref was budgeted on its own, so two 250 MB branches passed a 300 MB limit (CAD process review, 2026-11-08)."""
    z = gitlfs.ZERO
    stdin = f"refs/heads/a {'1' * 40} refs/heads/a {'2' * 40}\nrefs/heads/b {'3' * 40} refs/heads/b {z}\nrefs/heads/c {z} refs/heads/c {'4' * 40}\n"
    assert gitlfs.pre_push_rev_args(stdin, "origin") == [
        "1" * 40,
        "3" * 40,
        f"^{'2' * 40}",
        "--not",
        "--remotes=origin",
    ]
    assert (
        gitlfs.pre_push_rev_args(
            f"refs/heads/c {z} refs/heads/c {'4' * 40}\n", "origin"
        )
        == []
    )


def test_hook_install_keeps_other_hooks_and_runs_lfs_itself(repo: Path) -> None:
    """Guards: bug - a chained local pre-push hook skipped the Git LFS upload (CAD process review, 2026-11-08)."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-push").write_text('#!/bin/sh\ngit lfs pre-push "$@"\n')
    (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n")
    lines = "\n".join(install_hooks.install(repo))
    assert "replaced Git LFS's pre-push hook" in lines
    assert "kept the existing pre-commit hook as pre-commit.local" in lines
    assert install_hooks.is_current(repo)
    install_hooks.install(repo)  # idempotent: does not wrap itself
    assert "echo mine" in (hooks / "pre-commit.local").read_text()
    assert "git lfs pre-push" in (hooks / "pre-push").read_text()


def test_worktree_without_the_cad_tools_still_commits_and_pushes(
    tmp_path: Path,
) -> None:
    """Guards: bug - hooks installed from one worktree failed every commit in worktrees whose branch had no tools/cad/hooks (Joey-PC, 2026-11-09)."""
    main, remote, wt = tmp_path / "main", tmp_path / "remote", tmp_path / "board"
    main.mkdir()
    remote.mkdir()
    git(main, "init", "-q", "-b", "main")
    git(main, "config", "commit.gpgsign", "false")
    commit(main, {"README.md": "x\n"}, "base")  # a branch from before tools/cad
    install_hooks.install(main)
    git(remote, "init", "-q", "--bare")
    git(main, "remote", "add", "up", str(remote))
    git(main, "worktree", "add", "-q", "-b", "board", str(wt))
    (wt / "board.txt").write_text("net list\n")
    git(wt, "add", "-A")
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    for args in (["commit", "-qm", "board"], ["push", "-q", "up", "board"]):
        done = subprocess.run(
            ["git", "-C", str(wt), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        assert "CAD checks skipped" in done.stderr
