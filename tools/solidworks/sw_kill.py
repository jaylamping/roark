"""End SolidWorks processes on the CAD workstation, with the checks a bare taskkill lacks. RULES.md, Ending instances.

    python tools/solidworks/sw_kill.py --list                 # every SolidWorks process and what --dead would end
    python tools/solidworks/sw_kill.py --dead                 # end what can never finish: see below
    python tools/solidworks/sw_kill.py <pid> [--force]        # end one instance and everything it started
    python tools/solidworks/sw_kill.py --all --force          # end every SolidWorks process, the keeper included

`--dead` ends only what nobody is waiting for: a half-closed instance, an instance that has not answered with no solver
and no live client driving it, and solver or helper processes whose SolidWorks has gone. Any session may run it.

A PID is ended without `--force` only if it is one of those. An instance that is idle, solving or busy belongs to a live
session and may be minutes from a result, and the keeper serves every session, so those need `--force`, which is for
Joey's say-so or the session that owns the instance.

Every process ended is written to `kills.log` in the claims folder with the time, its state, who had launched it and the
command that ended it. Windows only.
"""

from __future__ import annotations

import os
import sys
import time

HELPERS = ("cwanalysisproc.exe", "star.exe", "sldprocmon.exe", "sldexitapp.exe")
DEAD = ("zombie", "orphan")
ORPHAN_AFTER_S = 300


def may_end(state: str, is_keeper: bool, force: bool) -> tuple[bool, str]:
    """(allowed, reason) for ending one SolidWorks instance in this state."""
    if force:
        return True, "forced"
    if is_keeper:
        return False, "it is the keeper, which every session's launches rely on; --force to end it"
    if state in DEAD:
        return True, f"{state}: it can never finish"
    return False, f"{state}: a live session's instance; --force to end it"


def settled(state: str, age_s: float) -> str:
    """An instance not answering with nothing driving it may be starting, or finishing a call its client just left:
    launch() gives it 300 s before it calls it an orphan, and so does this."""
    return "unsettled" if state == "orphan" and age_s < ORPHAN_AFTER_S else state


def _helpers_without_solidworks():
    """Solver and helper processes with no SolidWorks among their ancestors: left behind when one was ended."""
    import psutil

    out = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() not in HELPERS:
            continue
        try:
            if not any(a.name().lower() == "sldworks.exe" for a in p.parents()) and time.time() - p.create_time() > 60:
                out.append(p)
        except psutil.Error:
            pass
    return out


def _log(sw, line: str) -> None:
    try:
        d = str(sw._claims().claims_dir())
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "kills.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line} | by PID {os.getpid()}: {' '.join(sys.argv)}\n")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    if sys.platform != "win32":
        print("sw_kill.py is Windows only")
        return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import psutil

    import sw_instance as sw

    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    if len(args) != 1 or not (args[0] in ("--list", "--dead", "--all") or args[0].isdigit()):
        print(__doc__)
        return 2
    what = args[0]
    if what == "--all" and not force:
        print("--all ends every session's SolidWorks: it needs --force")
        return 2

    keeper = sw.keeper_pid()
    rows = [(row[0], settled(sw.state(row), row[1]), row[0] == keeper, sw.who(row[0])) for row in sw.status()]
    strays = _helpers_without_solidworks()
    code = 0

    if what == "--list":
        for pid, st, is_keeper, who in rows:
            ok, why = may_end(st, is_keeper, False)
            print(f"{pid:7d} {'would end' if ok else 'keeps':9} {why}  {who}")
        for p in strays:
            print(f"{p.pid:7d} would end  {p.name()} with no SolidWorks above it")
        return 0

    if what.isdigit() and int(what) not in [r[0] for r in rows]:
        print(f"PID {what} is not a running SolidWorks instance")
        return 1

    for pid, st, is_keeper, who in rows:
        if what.isdigit() and int(what) != pid:
            continue
        ok, why = may_end(st, is_keeper, force)
        if not ok:
            if what.isdigit():
                print(f"PID {pid} not ended: {why}")
                code = 1
            continue
        ended = sw.kill_tree(pid, sw._started(pid))
        sw._drop_owner(pid)
        print(f"ended PID {pid} ({why}) and {max(len(ended) - 1, 0)} processes under it")
        _log(sw, f"ended SLDWORKS {pid} state={st} reason={why} who={who!r}")

    if what in ("--dead", "--all"):
        for p in strays:
            try:
                name = p.name()
                p.kill()
                print(f"ended {name} PID {p.pid}: no SolidWorks above it")
                _log(sw, f"ended {name} {p.pid} with no SolidWorks above it")
            except psutil.Error as e:
                print(f"could not end PID {p.pid}: {e}")
                code = 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
