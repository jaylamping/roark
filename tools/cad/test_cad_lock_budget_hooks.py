"""Tests for the CAD writer lock, the LFS budget and the hook installer (pytest; run by scripts/check.sh).

Rules: conventions/cad.md section 6.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "hooks"))
import cad_lock
import gitlfs
import install_hooks
import lfs_budget
import pre_commit
import pre_push

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
    manifests = {
        f"cad/manifests/{m.name}": m.read_text(encoding="utf-8")
        for m in (Path(__file__).resolve().parents[2] / "cad" / "manifests").glob("*.json")
    }
    commit(
        tmp_path,
        {"cad/shoulder/shoulder_a.SLDPRT": pointer(5_000_000, "1" * 64), **manifests},
        "base",
    )
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def writer(lock: Path) -> str:
    return json.loads(lock.read_text())["writer"]


def make_stale(lock: Path) -> dict:
    data = json.loads(lock.read_text())
    data["updated"] = data["updated"] - cad_lock.STALE_SECONDS - 1
    lock.write_text(json.dumps(data))
    return data


def test_only_the_lock_holder_may_commit_cad(tmp_path: Path) -> None:
    """Guards: safety - one CAD writer at a time; committing CAD needs the lock (conventions/cad.md section 6)."""
    lock = tmp_path / ".cad-writer.lock"
    assert cad_lock.check("anyone", lock)[0] is False
    ok, msg = cad_lock.acquire("shoulder", path=lock)
    shoulder = writer(lock)
    assert (ok, msg) == (True, f"lock taken. In this shell: export CAD_WRITER={shoulder}")
    assert shoulder.startswith("shoulder:")
    assert cad_lock.acquire("torso", path=lock)[0] is False
    assert cad_lock.check(shoulder, lock)[0] is True
    assert cad_lock.check("shoulder", lock)[0] is False  # the name alone is not the writer
    assert cad_lock.check(None, lock)[0] is False
    assert cad_lock.refresh("torso:x", lock)[0] is False
    assert cad_lock.release("torso:x", lock)[0] is False
    assert cad_lock.refresh(shoulder, lock) == (True, f"{shoulder} refreshed the lock")
    assert cad_lock.release(shoulder, lock) == (True, f"released by {shoulder}")
    assert list(tmp_path.iterdir()) == []  # no temp or mutex files left behind


def test_two_sessions_with_one_name_never_share_the_lock(tmp_path: Path) -> None:
    """Guards: bug - two sessions that both called themselves "joey" both held the lock (PR 16 review, 2026-11-09)."""
    lock = tmp_path / ".cad-writer.lock"
    assert cad_lock.acquire("joey", path=lock)[0] is True
    first = writer(lock)
    assert cad_lock.acquire("joey", path=lock)[0] is False
    make_stale(lock)
    assert cad_lock.acquire("joey", path=lock)[0] is False  # stale, even under one's own name, needs --take-stale
    assert cad_lock.acquire("joey", path=lock, take_stale=True)[0] is True
    second = writer(lock)
    assert second != first
    assert cad_lock.check(first, lock)[0] is False
    assert cad_lock.refresh(first, lock)[0] is False
    assert cad_lock.release(first, lock)[0] is False
    assert writer(lock) == second


def test_lock_changes_wait_for_the_mutex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards: bug - a refresh or release between a takeover's read and its write left two writers (PR 16 review, 2026-11-09)."""
    lock = tmp_path / ".cad-writer.lock"
    assert cad_lock.acquire("shoulder", path=lock)[0] is True
    holder = writer(lock)
    make_stale(lock)
    mutex = lock.with_name(lock.name + ".mutex")
    mutex.write_text(json.dumps({"token": "another session mid-change"}))
    monkeypatch.setattr(cad_lock, "MUTEX_WAIT_SECONDS", 0.0)
    for change in (
        lambda: cad_lock.acquire("torso", path=lock, take_stale=True),
        lambda: cad_lock.refresh(holder, lock),
        lambda: cad_lock.release(holder, lock),
    ):
        with pytest.raises(cad_lock.Busy):
            change()
    assert mutex.exists()  # only its creator removes a mutex
    assert writer(lock) == holder
    mutex.unlink()
    assert cad_lock.refresh(holder, lock)[0] is True  # the owner refreshed first: no longer stale
    assert cad_lock.acquire("torso", path=lock, take_stale=True)[0] is False


def test_unreadable_lock_is_held_not_stale(tmp_path: Path) -> None:
    """Guards: bug - an empty, half-written or wrong-shaped lock file once read as stale or crashed the hook (CAD process review, 2026-11-08; PR 16 review)."""
    lock = tmp_path / ".cad-writer.lock"
    for text in ["", "123", '{"writer": "a", "updated": "soon"}', "{}"]:
        lock.write_text(text)
        assert cad_lock.acquire("torso", path=lock, take_stale=True)[0] is False
        assert cad_lock.check("torso:x", lock)[0] is False
        assert cad_lock.release("a", lock)[0] is False
        assert lock.read_text() == text


def test_pre_commit_needs_the_lock_for_cad_only(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards: safety - a CAD commit without the lock is refused; a commit with no CAD is not checked (conventions/cad.md section 6)."""
    lock = repo / "cad" / ".cad-writer.lock"
    monkeypatch.setattr(cad_lock, "LOCK_PATH", lock)
    monkeypatch.setattr(cad_lock.refresh, "__defaults__", (lock,))
    monkeypatch.setattr(pre_commit, "REPO_ROOT", repo)
    monkeypatch.setattr(pre_commit, "git", lambda *a: gitlfs.git(*a, root=repo))
    monkeypatch.setattr(pre_commit, "run", lambda *a: 0)
    monkeypatch.delenv("CAD_WRITER", raising=False)
    (repo / "notes.txt").write_text("x")
    git(repo, "add", "notes.txt")
    assert pre_commit.main() == 0
    (repo / "cad" / "shoulder" / "shoulder_b.SLDPRT").write_text(pointer(1, "2" * 64))
    git(repo, "add", "-A")
    assert pre_commit.main() == 1
    assert cad_lock.acquire("shoulder", path=lock)[0] is True
    monkeypatch.setenv("CAD_WRITER", "shoulder:wrong")
    assert pre_commit.main() == 1
    monkeypatch.setenv("CAD_WRITER", writer(lock))
    assert pre_commit.main() == 0


def run_budget(repo: Path, budget: dict, remote: str = "origin") -> tuple[bool, list[str]]:
    return lfs_budget.check_push(["HEAD", "--not", f"--remotes={remote}"], repo, budget, remote=remote)


def test_budget_counts_only_objects_the_target_remote_lacks(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards: number - pushMaxBytes in cad/manifests/lfs-budget.json, counted against the remote pushed to."""
    monkeypatch.delenv("CAD_BUDGET_OK", raising=False)
    month = time.strftime("%Y-%m", time.gmtime())
    budget = dict(NO_LIMITS, pushMaxBytes=50_000_000)
    commit(
        repo,
        {
            "cad/shoulder/copy.SLDPRT": pointer(5_000_000, "1" * 64),  # already on origin
            "cad/shoulder/shoulder_new.SLDPRT": pointer(60_000_000, "3" * 64),
        },
        "new",
    )
    git(repo, "update-ref", "refs/remotes/fork/main", "HEAD")
    refuse = [
        f"LFS: this push adds 60.0 MB in 1 new object(s); {month} so far 5 MB; stored 0.01 GB",
        "over the per-push limit of 50 MB",
        (
            "Commit CAD at gates, not every save; squash interim saves before pushing. "
            "With Joey's OK, push again with CAD_BUDGET_OK=1."
        ),
    ]
    assert run_budget(repo, budget) == (False, refuse)
    assert run_budget(repo, budget, "fork") == (
        True,
        [f"LFS: this push adds 0.0 MB in 0 new object(s); {month} so far 65 MB; stored 0.07 GB"],
    )
    monkeypatch.setenv("CAD_BUDGET_OK", "1")
    assert run_budget(repo, budget) == (True, [*refuse[:2], "CAD_BUDGET_OK=1 set: pushing anyway"])


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        ({"monthMaxBytes": 10_000_000}, (False, ["takes {month} past 10 MB of new LFS data"])),
        ({"storageMaxBytes": 10_000_000}, (False, ["takes storage past 0 GB (GitHub Free quota is 10 GiB)"])),
        ({"storageWarnBytes": 10_000_000}, (True, ["warning: storage past 0 GB; plan a cleanup or paid data pack"])),
        ({"monthMaxBytes": 11_000_000, "storageMaxBytes": 11_000_000}, (True, [])),
    ],
)
def test_month_and_storage_limits(repo: Path, monkeypatch: pytest.MonkeyPatch, limits: dict, expected: tuple) -> None:
    """Guards: number - monthMaxBytes, storageMaxBytes and storageWarnBytes: 5 MB stored + 6 MB new against each limit."""
    monkeypatch.delenv("CAD_BUDGET_OK", raising=False)
    month = time.strftime("%Y-%m", time.gmtime())
    commit(repo, {"cad/shoulder/shoulder_c.SLDPRT": pointer(6_000_000, "5" * 64)}, "six")
    ok, msgs = run_budget(repo, dict(NO_LIMITS, **limits))
    want_ok, want_extra = expected
    assert ok is want_ok
    assert msgs[1 : 1 + len(want_extra)] == [m.format(month=month) for m in want_extra]


def test_all_refs_of_one_push_are_budgeted_together(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards: bug - each ref was budgeted on its own, so two 250 MB branches passed a 300 MB limit (CAD process review, 2026-11-08)."""
    monkeypatch.delenv("CAD_BUDGET_OK", raising=False)
    monkeypatch.setattr(lfs_budget, "BUDGET_PATH", repo / ".git" / "budget.json")
    (repo / ".git" / "budget.json").write_text(json.dumps(dict(NO_LIMITS, pushMaxBytes=150_000_000)))
    base = git(repo, "rev-parse", "HEAD").strip()
    tips = {}
    for branch, oid in (("a", "6"), ("b", "7")):
        git(repo, "checkout", "-q", "-b", branch, base)
        commit(repo, {f"cad/shoulder/shoulder_{branch}.SLDPRT": pointer(90_000_000, oid * 64)}, branch)
        tips[branch] = git(repo, "rev-parse", "HEAD").strip()
    z = gitlfs.ZERO
    line = lambda b: f"refs/heads/{b} {tips[b]} refs/heads/{b} {z}\n"
    assert pre_push.main(["origin"], repo, line("a")) == 0
    assert pre_push.main(["origin"], repo, line("b")) == 0
    assert pre_push.main(["origin"], repo, line("a") + line("b")) == 1


def test_force_push_over_an_unfetched_tip_is_checked(repo: Path) -> None:
    """Guards: bug - a remote tip this clone never fetched crashed the pre-push hook with a bare traceback (PR 16 review, 2026-11-09)."""
    tip = git(repo, "rev-parse", "HEAD").strip()
    stdin = f"refs/heads/main {tip} refs/heads/main {'9' * 40}\n"
    assert pre_push.known_locally(gitlfs.pre_push_rev_args(stdin, "origin"), repo) == [
        tip,
        "--not",
        "--remotes=origin",
    ]


def test_pre_push_rev_args_cover_every_ref() -> None:
    """Guards: protocol - git's pre-push stdin: <local ref> <local sha> <remote ref> <remote sha>, zero sha for none (githooks(5))."""
    z = gitlfs.ZERO
    stdin = f"refs/heads/a {'1' * 40} refs/heads/a {'2' * 40}\nrefs/heads/b {'3' * 40} refs/heads/b {z}\nrefs/heads/c {z} refs/heads/c {'4' * 40}\n"
    assert gitlfs.pre_push_rev_args(stdin, "origin") == ["1" * 40, "3" * 40, f"^{'2' * 40}", "--not", "--remotes=origin"]
    assert gitlfs.pre_push_rev_args(f"refs/heads/c {z} refs/heads/c {'4' * 40}\n", "origin") == []


STOCK_LFS_PRE_PUSH = (
    "#!/bin/sh\n"
    "command -v git-lfs >/dev/null 2>&1 || { printf >&2 \"\\n%s\\n\\n\" \"This repository is configured for Git LFS "
    "but 'git-lfs' was not found on your path.\"; exit 2; }\n"
    'git lfs pre-push "$@"\n'
)


def test_hook_install_keeps_other_hooks(repo: Path) -> None:
    """Guards: bug - any short hook mentioning git lfs was taken for LFS's own and stopped running (PR 16 review, 2026-11-09)."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-push").write_text(STOCK_LFS_PRE_PUSH)
    (hooks / "pre-commit").write_text('#!/bin/sh\ngit lfs status\necho mine\n')
    assert install_hooks.install(repo) == [
        "kept the existing pre-commit hook as pre-commit.local",
        "installed pre-commit",
        "replaced Git LFS's pre-push hook (ours runs git lfs; copy in pre-push.lfs-orig)",
        "installed pre-push",
    ]
    assert install_hooks.is_current(repo) is True
    assert install_hooks.install(repo) == ["installed pre-commit", "installed pre-push"]  # does not wrap itself
    assert (hooks / "pre-commit.local").read_text() == '#!/bin/sh\ngit lfs status\necho mine\n'
    assert install_hooks.is_stock_lfs_hook("pre-push", '#!/bin/sh\ngit lfs pre-push "$@"\n./secret-scan.sh\n') is False


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_installed_pre_push_runs_checks_then_local_then_lfs(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Guards: bug - a chained local hook skipped the Git LFS upload, and LFS uploaded before a check refused the push (CAD process review, 2026-11-08; PR 16 review)."""
    install_hooks.install(repo)
    hooks = repo / ".git" / "hooks"
    bin_dir = tmp_path_factory.mktemp("bin")
    log = bin_dir / "log"
    (bin_dir / "git-lfs").write_text(f'#!/bin/sh\necho "lfs $* $(cat)" >> {log}\n')
    (bin_dir / "git-lfs").chmod(0o755)
    real_git = shutil.which("git")
    (bin_dir / "git").write_text(
        f'#!/bin/sh\nif [ "$1" = lfs ]; then shift; exec {bin_dir}/git-lfs "$@"; fi\nexec {real_git} "$@"\n'
    )
    (bin_dir / "git").chmod(0o755)
    (hooks / "pre-push.local").write_text(f'#!/bin/sh\necho "local $(cat)" >> {log}\nexit $LOCAL_EXIT\n')
    (hooks / "pre-push.local").chmod(0o755)
    shutil.copytree(Path(__file__).resolve().parents[1], repo / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    tip = git(repo, "rev-parse", "HEAD").strip()
    stdin = f"refs/heads/main {tip} refs/heads/main {gitlfs.ZERO}\n"

    def push(local_exit: int) -> int:
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", LOCAL_EXIT=str(local_exit))
        env.pop("CAD_BUDGET_OK", None)
        return subprocess.run(
            ["sh", str(hooks / "pre-push"), "origin", "url"], cwd=repo, input=stdin, text=True, env=env, check=False
        ).returncode

    assert push(0) == 0
    assert log.read_text().splitlines() == [f"local {stdin.strip()}", f"lfs pre-push origin url {stdin.strip()}"]
    log.write_text("")
    assert push(1) == 1
    assert log.read_text().splitlines() == [f"local {stdin.strip()}"]  # nothing uploaded for a refused push


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
