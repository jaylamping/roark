"""Who is using what on the CAD workstation, and whether they are still alive. conventions/cad-workstation.md section 2.

Each session (a thread's Remote Control session, the FEA runner) keeps one small JSON file in the claims folder: its
worktree, its SolidWorks PID, what it is doing and when it last said so. One file per session, so sessions never write the
same file. Stdlib only.

    python tools/pc/claims.py claim <session> --worktree J:\\code\\roark-wt\\<session> [--sw-pid N] [--status TEXT]
    python tools/pc/claims.py beat <session> [--status TEXT] [--sw-pid N]   # every few minutes during long work
    python tools/pc/claims.py release <session>
    python tools/pc/claims.py list [--stale MINUTES]                        # default 15
    python tools/pc/claims.py who <worktree path or SolidWorks PID>

`who <PID>` also answers for an instance nobody claimed: sw_instance.py leaves a note for every SolidWorks it starts or
attaches to (`instances/sw-<pid>.json` in the claims folder: worktree, client PID, command line), so a session that never
ran `claim` still shows as the owner of what it launched.

claim, beat and release run inside a short mutex (claims.mutex in the folder, created exclusively), so a check and the
write that depends on it can't interleave with another session's. claim and beat refuse a worktree or SolidWorks PID that
another live session holds; `<session>-fea`, a thread's second SolidWorks instance, may share its parent's worktree. A
claim file that can't be read blocks every claim and beat until it is checked and deleted by hand: it may be a live
session's. The folder is C:\\Temp\\roark-claims on Windows, ~/.roark-claims elsewhere, or ROARK_CLAIMS_DIR.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

STALE_MIN = 15.0
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FEA = "-fea"
MUTEX = "claims.mutex"
MUTEX_WAIT_S = 5.0
INSTANCES = "instances"


def claims_dir() -> Path:
    env = os.environ.get("ROARK_CLAIMS_DIR")
    if env:
        return Path(env)
    return Path(r"C:\Temp\roark-claims") if os.name == "nt" else Path.home() / ".roark-claims"


def now() -> float:
    return time.time()


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).rstrip("\\/")


def claim_file(d: Path, session: str) -> Path:
    """The session's file. The name is checked first, so no subcommand can reach a file outside the claims folder."""
    if not NAME.fullmatch(session):
        raise SystemExit(f"session name {session!r}: lower case letters, digits and '-' only")
    return d / f"{session}.json"


def load_all(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(c, dict) or not isinstance(c.get("beat"), (int, float)):
                raise ValueError("not a claim")
            out.append(c)
        except (OSError, ValueError):
            out.append({"session": f.stem, "broken": True, "file": str(f), "beat": 0})
    return out


def write(d: Path, c: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{c['session']}.json.tmp"
    tmp.write_text(json.dumps(c, indent=1), encoding="utf-8")
    os.replace(tmp, d / f"{c['session']}.json")  # atomic: a reader never sees half a file


@contextmanager
def mutex(d: Path) -> Iterator[None]:
    """One claims change at a time. A mutex left by a crashed command is deleted by hand, as cad_lock.py's is."""
    d.mkdir(parents=True, exist_ok=True)
    guard, token = d / MUTEX, secrets.token_hex(8)
    deadline = time.monotonic() + MUTEX_WAIT_S
    while True:
        try:
            fd = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise SystemExit(f"{guard} is present: another claims command is running, or one crashed. "
                                 "If none is running, delete it by hand and retry.") from None
            time.sleep(0.05)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token)
    try:
        yield
    finally:
        try:
            mine = guard.read_text(encoding="utf-8") == token
        except OSError:
            mine = False
        if mine:  # only ever remove our own mutex
            guard.unlink(missing_ok=True)


def age_min(c: dict, t: float) -> float:
    return (t - float(c.get("beat", 0))) / 60.0


def siblings(a: str, b: str) -> bool:
    """A thread's FEA instance, `<session>-fea`, works in its parent's worktree (cad-workstation.md section 1)."""
    return a == b + FEA or b == a + FEA


def refuse_conflicts(d: Path, session: str, wt: str, sw_pid: int | None, t: float, stale: float) -> None:
    for c in load_all(d):
        if c.get("session") == session:
            continue
        if c.get("broken"):
            raise SystemExit(f"claim file {c['file']} can't be read; it may be a live session's. "
                             "Check it and delete it by hand.")
        if age_min(c, t) > stale:
            continue
        if c.get("worktree") == wt and not siblings(session, c["session"]):
            raise SystemExit(f"{wt} is claimed by {c['session']} (last beat {age_min(c, t):.0f} min ago)")
        if sw_pid and c.get("sw_pid") == sw_pid:
            raise SystemExit(f"SolidWorks PID {sw_pid} is claimed by {c['session']}")


def claim(d: Path, session: str, worktree: str, sw_pid: int | None, status: str, t: float, stale: float = STALE_MIN) -> dict:
    claim_file(d, session)
    wt = norm(worktree)
    with mutex(d):
        refuse_conflicts(d, session, wt, sw_pid, t, stale)
        c = {"session": session, "worktree": wt, "sw_pid": sw_pid, "status": status, "started": t, "beat": t}
        write(d, c)
    return c


def beat(d: Path, session: str, status: str | None, sw_pid: int | None, t: float, stale: float = STALE_MIN) -> dict:
    """Refreshes a claim. Refuses, as claim does, when another live session now holds its worktree or PID: a session that
    went stale and resumes doesn't take back what someone else claimed meanwhile."""
    f = claim_file(d, session)
    with mutex(d):
        if not f.is_file():
            raise SystemExit(f"{session} has no claim; run claim first")
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SystemExit(f"claim file {f} can't be read ({e}); check it and delete it by hand") from None
        pid = c.get("sw_pid") if sw_pid is None else sw_pid
        refuse_conflicts(d, session, c.get("worktree", ""), pid, t, stale)
        c["beat"] = t
        c["sw_pid"] = pid
        if status is not None:
            c["status"] = status
        write(d, c)
    return c


def release(d: Path, session: str) -> None:
    f = claim_file(d, session)
    with mutex(d):
        f.unlink(missing_ok=True)


def instance_file(d: Path, sw_pid: int) -> Path:
    return d / INSTANCES / f"sw-{int(sw_pid)}.json"


def note_instance(d: Path, sw_pid: int, sw_started: float, worktree: str, client_pid: int, command: str, t: float) -> dict:
    """Record who launched or attached to a SolidWorks instance. Written by sw_instance.py, not by hand; it needs no claim
    and never refuses, so it can't stop a launch. The subfolder keeps these out of load_all()."""
    n = {"sw_pid": int(sw_pid), "sw_started": sw_started, "worktree": norm(worktree), "client_pid": client_pid,
         "command": command[:300], "since": t}
    f = instance_file(d, sw_pid)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(n, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return n


def drop_instance(d: Path, sw_pid: int) -> None:
    instance_file(d, sw_pid).unlink(missing_ok=True)


def instance_note(d: Path, sw_pid: int, sw_started: float | None = None) -> dict | None:
    """The note for this PID, or None. Windows reuses PIDs: pass the process start time to reject another process's note."""
    try:
        n = json.loads(instance_file(d, sw_pid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(n, dict) or (sw_started is not None and n.get("sw_started") != sw_started):
        return None
    return n


def who(d: Path, what: str) -> list[dict]:
    pid = int(what) if what.isdigit() else None
    key = norm(what) if pid is None else None
    found = [c for c in load_all(d) if (pid and c.get("sw_pid") == pid) or (key and c.get("worktree") == key)]
    if pid and not found:
        n = instance_note(d, pid)
        if n:
            found.append({"session": None, "unclaimed": True, **n})
    return found


def table(d: Path, t: float, stale: float) -> list[str]:
    rows = []
    for c in load_all(d):
        a = age_min(c, t)
        flag = "BROKEN" if c.get("broken") else ("STALE" if a > stale else "ok")
        rows.append(f"{flag:6} {c['session']:24} beat {a:6.1f} min ago  sw {c.get('sw_pid') or '-':>6}  "
                    f"{c.get('worktree', '')}  {c.get('status', '')}")
    return rows or ["no claims"]


def main(argv: list[str]) -> int:
    d = claims_dir()
    opts: dict[str, str] = {}
    pos: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    cmd = pos[0] if pos else ""
    pid = int(opts["--sw-pid"]) if "--sw-pid" in opts else None
    stale = float(opts.get("--stale", STALE_MIN))
    if cmd == "claim" and len(pos) == 2 and "--worktree" in opts:
        print(json.dumps(claim(d, pos[1], opts["--worktree"], pid, opts.get("--status", ""), now(), stale)))
    elif cmd == "beat" and len(pos) == 2:
        beat(d, pos[1], opts.get("--status"), pid, now(), stale)
    elif cmd == "release" and len(pos) == 2:
        release(d, pos[1])
    elif cmd == "list" and len(pos) == 1:
        print("\n".join(table(d, now(), stale)))
    elif cmd == "who" and len(pos) == 2:
        print("\n".join(json.dumps(c) for c in who(d, pos[1])) or "nobody")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
