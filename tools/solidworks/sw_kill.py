"""End SolidWorks processes on the CAD workstation, with the checks a bare taskkill lacks. RULES.md, Ending instances.

    python tools/solidworks/sw_kill.py --list                 # every SolidWorks process and what --dead would end
    python tools/solidworks/sw_kill.py --dead                 # end what can never finish: see below
    python tools/solidworks/sw_kill.py <pid> [--force]        # end one instance and everything it started
    python tools/solidworks/sw_kill.py --all --force          # end every SolidWorks process, the keeper included

`--dead` ends only what nobody is waiting for: a half-closed instance, an instance that has not answered with no solver
and no live client driving it, and solver or helper processes whose SolidWorks has gone. Any session may run it. It
watches each one before ending it, as launch() does: 20 s for a half-closed instance, because a process starting or in an
ordinary exit looks the same for a moment, and 300 s for an abandoned one, because a client this module has no record of
may be driving it through a mesh. So `--dead` can take five minutes.

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


def may_end(state: str, is_keeper: bool, force: bool) -> tuple[bool, str]:
    """(allowed, reason) for ending one SolidWorks instance in this state."""
    if force:
        return True, "forced"
    if is_keeper:
        return False, "it is the keeper, which every session's launches rely on; --force to end it"
    if state in DEAD:
        return True, f"{state}: it can never finish"
    return False, f"{state}: a live session's instance; --force to end it"


WATCH_S = {"zombie": 20, "orphan": 300}
YOUNG_S = 30


def settled(state: str, age_s: float) -> str:
    """A process in its first 30 s has no windows yet and answers nothing: that is starting, not dead."""
    return "unsettled" if state in DEAD and age_s < YOUNG_S else state


def stays_dead(look, watch_s: float, poll_s: float = 5.0, sleep=time.sleep) -> bool:
    """True if `look()` returns the same dead state on every look for `watch_s` seconds. One look that shows the
    instance answering, solving, driven or gone ends the watch: it was not dead."""
    first = look()
    if first not in DEAD:
        return False
    waited = 0.0
    while waited < watch_s:
        sleep(poll_s)
        waited += poll_s
        if look() != first:
            return False
    return True


def _helpers_without_solidworks():
    """Solver and helper processes left behind when their SolidWorks was ended.

    A solver's helper parent can exit while the SolidWorks above it is alive and solving, which breaks the parent chain
    (RULES.md, 2026-11-09). So one counts as left behind only if no running SolidWorks started before it.
    """
    import psutil

    sw_starts = []
    helpers = []
    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info["name"] or "").lower()
            if name == "sldworks.exe":
                sw_starts.append(p.create_time())
            elif name in HELPERS:
                helpers.append(p)
        except psutil.Error:
            pass
    out = []
    for p in helpers:
        try:
            born = p.create_time()
            if (
                time.time() - born > 60
                and not any(a.name().lower() == "sldworks.exe" for a in p.parents())
                and not any(t <= born for t in sw_starts)
            ):
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

    def look(pid):
        """The instance's state now, or "gone"."""
        for row in sw.status():
            if row[0] == pid:
                return settled(sw.state(row), row[1])
        return "gone"

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
        started = sw._started(pid)
        st = look(pid)  # again, now: an earlier end in this run may have taken half a minute
        ok, why = may_end(st, is_keeper, force)
        if ok and not force:
            print(f"PID {pid} looks {st}; watching it for {WATCH_S[st]} s before ending it")
            if not stays_dead(lambda: look(pid), WATCH_S[st]):
                ok, why = False, f"it was {st} but changed while watched: not dead"
        if not ok:
            if what.isdigit():
                print(f"PID {pid} not ended: {why}")
                code = 1
            continue
        ended = sw.kill_tree(pid, started)
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
