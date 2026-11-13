#!/usr/bin/env python3
"""One CAD writer at a time in the shared checkout (the CAD workstation, J:\\code\\roark on holly-pc).

Many sessions share one working tree. Before a session opens SolidWorks to change files in
cad/, or stages cad/ files, it takes the writer lock; it releases it after its commit.
The lock is the gitignored file cad/.cad-writer.lock. The pre-commit hook refuses a commit
touching CAD unless $CAD_WRITER holds the lock. Also hold it while switching branches,
resetting or pulling in the shared checkout.

Usage:
    python3 tools/cad/cad_lock.py acquire NAME [--note TEXT] [--take-stale]   take the lock
    python3 tools/cad/cad_lock.py refresh [WRITER]           keep it alive during long work
    python3 tools/cad/cad_lock.py release [WRITER]           give it back
    python3 tools/cad/cad_lock.py status                     who holds it
    python3 tools/cad/cad_lock.py check [WRITER]             exit 0 if WRITER holds the lock
WRITER defaults to $CAD_WRITER. acquire prints the WRITER value for this session
(NAME:token, unique per acquire), so two sessions with the same NAME never share the lock.
NAME says what the session works on, e.g. "left-arm". A lock not refreshed for 4 hours is
stale, even if SolidWorks is still open: refresh during long work. After making sure the
holding session stopped and closed its SolidWorks, take a stale lock over with
acquire --take-stale. An unreadable lock file is never stale; inspect and delete it by hand.
Exit code 0 = ok, 1 = held by someone else / not yours, 2 = bad usage.

Every change to the lock (acquire, refresh, release, takeover) runs inside a short mutex
(cad/.cad-writer.lock.mutex, created exclusively), so a read and the write that depends on it
can't interleave with another session's.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "cad" / ".cad-writer.lock"
STALE_SECONDS = 4 * 3600
MUTEX_WAIT_SECONDS = 5.0


class Unreadable(dict):
    """A lock file that exists but isn't a valid record: treated as HELD (never stale) until removed by hand."""


class Busy(Exception):
    """The mutex is held: another lock operation is running, or one crashed and left it."""


def read(path: Path = LOCK_PATH) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
        lock = json.loads(text)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        lock = None
    valid = (
        isinstance(lock, dict)
        and isinstance(lock.get("writer"), str)
        and isinstance(lock.get("updated"), (int, float))
    )
    if valid:
        return lock
    try:
        since = path.stat().st_mtime
    except OSError:
        since = None
    return Unreadable(
        writer="(unreadable lock file; check it and delete it by hand)", since=since
    )


def is_stale(lock: dict, now: float | None = None) -> bool:
    if isinstance(lock, Unreadable):
        return False
    now = time.time() if now is None else now
    return now - float(lock["updated"]) > STALE_SECONDS


def describe(lock: dict) -> str:
    if isinstance(lock, Unreadable):
        since = lock.get("since")
        age = f", written {(time.time() - since) / 60:.0f} min ago" if since else ""
        return f"{lock['writer']}{age}"
    age = (time.time() - float(lock["updated"])) / 60
    note = f", {lock['note']}" if lock.get("note") else ""
    return f"{lock['writer']} on {lock.get('host', '?')}, refreshed {age:.0f} min ago{note}"


def _tmp_with(path: Path, data: dict) -> Path:
    """Write the full record to a unique temp file beside the lock (never a half-written lock)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    return tmp


def _create(path: Path, data: dict) -> bool:
    """Atomically create the file with its full content; False if it already exists.

    os.link fails if the target exists, so the file appears complete or not at all. On a
    filesystem without hard links, fall back to an exclusive create (a reader that catches
    it half-written sees an unreadable lock, which counts as held).
    """
    tmp = _tmp_with(path, data)
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    except OSError:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data))
        return True
    finally:
        tmp.unlink(missing_ok=True)


def _rewrite(path: Path, data: dict) -> None:
    os.replace(_tmp_with(path, data), path)  # atomic: readers see the old or new record


@contextmanager
def _mutex(path: Path) -> Iterator[None]:
    guard = path.with_name(path.name + ".mutex")
    token = {"pid": os.getpid(), "host": socket.gethostname(), "token": secrets.token_hex(8)}
    deadline = time.monotonic() + MUTEX_WAIT_SECONDS
    while not _create(guard, token):
        if time.monotonic() >= deadline:
            raise Busy(
                f"{guard.name} is present: another lock command is running, or one crashed. "
                "If none is running, delete it by hand and retry."
            )
        time.sleep(0.05)
    try:
        yield
    finally:
        try:
            mine = json.loads(guard.read_text(encoding="utf-8")) == token
        except (OSError, ValueError):
            mine = False
        if mine:  # only ever remove our own mutex
            guard.unlink(missing_ok=True)


def acquire(
    name: str, note: str = "", path: Path = LOCK_PATH, take_stale: bool = False
) -> tuple[bool, str]:
    """Take the lock as a new writer NAME:token. Never refreshes: an existing lock is someone's."""
    with _mutex(path):
        now = time.time()
        writer = f"{name}:{secrets.token_hex(4)}"
        data = {
            "writer": writer,
            "host": socket.gethostname(),
            "started": now,
            "updated": now,
            "note": note,
        }
        lock = read(path)
        if lock is not None:
            if not is_stale(lock, now):
                return False, f"CAD writer lock held by {describe(lock)}"
            if not take_stale:
                return False, (
                    f"stale lock (no refresh for 4 h) held by {describe(lock)}. Make sure that session has "
                    "stopped and its SolidWorks is closed, then acquire again with --take-stale."
                )
            path.unlink()
        if not _create(path, data):
            return False, "another session took the lock first"
        took = f"took over a stale lock from {describe(lock)}; " if lock else ""
        return True, f"{took}lock taken. In this shell: export CAD_WRITER={writer}"


def refresh(writer: str | None, path: Path = LOCK_PATH) -> tuple[bool, str]:
    """Keep WRITER's lock alive. A stale lock of one's own may be refreshed until someone takes it over."""
    with _mutex(path):
        lock = read(path)
        if not writer or not lock or isinstance(lock, Unreadable) or lock["writer"] != writer:
            return False, _not_held(writer, lock)
        lock["updated"] = time.time()
        _rewrite(path, lock)
        return True, f"{writer} refreshed the lock"


def release(writer: str | None, path: Path = LOCK_PATH) -> tuple[bool, str]:
    with _mutex(path):
        lock = read(path)
        if not lock:
            return True, "no lock held"
        if not writer or isinstance(lock, Unreadable) or lock["writer"] != writer:
            return False, _not_held(writer, lock)
        path.unlink()
        return True, f"released by {writer}"


def check(writer: str | None, path: Path = LOCK_PATH) -> tuple[bool, str]:
    """Does WRITER hold the lock right now? (Read only; the pre-commit hook uses refresh.)"""
    lock = read(path)
    if writer and lock and not isinstance(lock, Unreadable) and lock["writer"] == writer:
        return True, f"{writer} holds the lock"
    return False, _not_held(writer, lock)


def _not_held(writer: str | None, lock: dict | None) -> str:
    if not lock:
        return (
            "no CAD writer lock held. Take it before changing or committing CAD: "
            "python3 tools/cad/cad_lock.py acquire <name>, then export the CAD_WRITER it prints."
        )
    if not writer:
        return f"CAD_WRITER is not set; the lock is held by {describe(lock)}."
    stale = " (stale)" if is_stale(lock) else ""
    return (
        f"{writer} does not hold the lock; it is held by {describe(lock)}{stale}. Wait for it, "
        "or ask that session to release it."
    )


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    note = ""
    take_stale = "--take-stale" in rest
    rest = [r for r in rest if r != "--take-stale"]
    if "--note" in rest:
        i = rest.index("--note")
        note = " ".join(rest[i + 1 :])
        rest = rest[:i]
    env_writer = os.environ.get("CAD_WRITER")
    try:
        if cmd == "status" and not rest:
            lock = read()
            stale = " (stale)" if lock and is_stale(lock) else ""
            print(f"held by {describe(lock)}{stale}" if lock else "no lock held")
            return 0
        if cmd == "acquire" and len(rest) == 1:
            ok, msg = acquire(rest[0], note, take_stale=take_stale)
        elif cmd in {"check", "refresh", "release"} and len(rest) <= 1:
            fn = {"check": check, "refresh": refresh, "release": release}[cmd]
            ok, msg = fn(rest[0] if rest else env_writer)
        else:
            print(__doc__)
            return 2
    except Busy as err:
        print(err)
        return 1
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
