"""Who is using what on Joey-PC, and whether they are still alive. conventions/joey-pc.md section 2.

Each session (a thread's Remote Control session, the FEA runner) keeps one small JSON file in the claims folder: its
worktree, its SolidWorks PID, what it is doing and when it last said so. One file per session, so sessions never write the
same file. Stdlib only.

    python tools/pc/claims.py claim <session> --worktree J:\\code\\roark-wt\\<session> [--sw-pid N] [--status TEXT]
    python tools/pc/claims.py beat <session> [--status TEXT] [--sw-pid N]   # every few minutes during long work
    python tools/pc/claims.py release <session>
    python tools/pc/claims.py list [--stale MINUTES]                        # default 15
    python tools/pc/claims.py who <worktree path or SolidWorks PID>

The folder is C:\\Temp\\roark-claims on Windows, ~/.roark-claims elsewhere, or ROARK_CLAIMS_DIR.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

STALE_MIN = 15.0
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def claims_dir() -> Path:
    env = os.environ.get("ROARK_CLAIMS_DIR")
    if env:
        return Path(env)
    return Path(r"C:\Temp\roark-claims") if os.name == "nt" else Path.home() / ".roark-claims"


def now() -> float:
    return time.time()


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).rstrip("\\/")


def load_all(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            out.append({"session": f.stem, "broken": True, "beat": 0})
    return out


def write(d: Path, c: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{c['session']}.json.tmp"
    tmp.write_text(json.dumps(c, indent=1), encoding="utf-8")
    os.replace(tmp, d / f"{c['session']}.json")  # atomic: a reader never sees half a file


def age_min(c: dict, t: float) -> float:
    return (t - float(c.get("beat", 0))) / 60.0


def claim(d: Path, session: str, worktree: str, sw_pid: int | None, status: str, t: float, stale: float = STALE_MIN) -> dict:
    if not NAME.fullmatch(session):
        raise SystemExit(f"session name {session!r}: lower case letters, digits and '-' only")
    wt = norm(worktree)
    for c in load_all(d):
        if c.get("session") == session or age_min(c, t) > stale:
            continue
        if c.get("worktree") == wt:
            raise SystemExit(f"{wt} is claimed by {c['session']} (last beat {age_min(c, t):.0f} min ago)")
        if sw_pid and c.get("sw_pid") == sw_pid:
            raise SystemExit(f"SolidWorks PID {sw_pid} is claimed by {c['session']}")
    c = {"session": session, "worktree": wt, "sw_pid": sw_pid, "status": status, "started": t, "beat": t}
    write(d, c)
    return c


def beat(d: Path, session: str, status: str | None, sw_pid: int | None, t: float) -> dict:
    f = d / f"{session}.json"
    if not f.is_file():
        raise SystemExit(f"{session} has no claim; run claim first")
    c = json.loads(f.read_text(encoding="utf-8"))
    c["beat"] = t
    if status is not None:
        c["status"] = status
    if sw_pid is not None:
        c["sw_pid"] = sw_pid
    write(d, c)
    return c


def release(d: Path, session: str) -> None:
    (d / f"{session}.json").unlink(missing_ok=True)


def who(d: Path, what: str) -> list[dict]:
    pid = int(what) if what.isdigit() else None
    key = norm(what) if pid is None else None
    return [c for c in load_all(d) if (pid and c.get("sw_pid") == pid) or (key and c.get("worktree") == key)]


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
        beat(d, pos[1], opts.get("--status"), pid, now())
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
