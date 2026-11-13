"""Run a dedicated SolidWorks instance per session and talk to it by process ID.

    from sw_instance import launch

    with launch() as inst:      # hidden; a launch can still take focus briefly (RULES.md)
        sw = inst.sw
        ...

Read RULES.md first. launch() starts a new SLDWORKS.exe and attaches through the
Running Object Table entry for that PID, so it can never reach another session's
instance. Never use GetActiveObject or Dispatch('SldWorks.Application').
"""
import ctypes
import ctypes.wintypes as wt
import msvcrt
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

import psutil
import pythoncom
import win32com.client as wc
import win32con
import win32gui
import win32process

EXE = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"
SIM_DLL = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.dll"
SIM_DIR = os.path.normcase(os.path.dirname(SIM_DLL))
LOCK = os.path.join(tempfile.gettempdir(), "sw_instance_launch.lock")
SOLVERS = ("cwanalysisproc.exe", "star.exe")
SOLVE_LOCK = r"C:\joe\.fea_solve.lock"  # one large solve at a time on the CAD workstation (RULES.md, rule 6)


class _LaunchLock:
    """Two SolidWorks processes started together can hang at startup, so launches queue across sessions."""

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        self.f = open(LOCK, "a+b")
        start = time.time()
        while True:
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() - start > self.timeout:
                    self.f.close()
                    raise RuntimeError("timed out waiting for another SolidWorks launch to finish")
                time.sleep(1)

    def __exit__(self, *exc):
        self.f.seek(0)
        msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        self.f.close()


class NotAnswering(RuntimeError):
    """The instance is running but not answering: mid-solve, stuck behind a hidden dialog, or half-closed."""


def _top_windows(pid):
    tops = []

    def find(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid:
            tops.append(h)
        return True

    win32gui.EnumWindows(find, None)
    return tops


def answers(pid, wait=3.0):
    """True if this PID's window thread answers a null message within `wait` seconds. Sends nothing else.

    A solving instance does not answer until the solve ends. A half-closed one has no windows left and never will.
    """
    tops = _top_windows(pid)
    try:
        # A window can be destroyed between the listing and the look, while its instance is closing.
        main = [h for h in tops if win32gui.GetClassName(h).startswith("Afx:")] or tops
    except win32gui.error:
        return False
    if not main:
        return False
    try:
        win32gui.SendMessageTimeout(main[0], win32con.WM_NULL, 0, 0, win32con.SMTO_ABORTIFHUNG, int(wait * 1000))
        return True
    except win32gui.error:
        return False


def _wait_answers(pid, seconds):
    end = time.time() + seconds
    while True:
        if answers(pid):
            return True
        if time.time() >= end or _started(pid) is None:
            return False
        time.sleep(2)


def kill_tree(pid, started):
    """Force-stop this process and everything it started (cwanalysisproc, star, sldProcMon, sldexitapp).

    Only the process with this exact start time, because Windows reuses pids. Returns the pids stopped.
    """
    if started is None or _started(pid) != started:
        return []
    try:
        root = psutil.Process(pid)
        procs = root.children(recursive=True) + [root]
    except psutil.Error:
        return []
    for p in reversed(procs):  # the instance first, so it cannot start anything new
        try:
            p.kill()
        except psutil.Error:
            pass
    _, left = psutil.wait_procs(procs, timeout=15)
    # A process already exiting refuses to be terminated (taskkill: "no running instance of the task") while its
    # last thread spins in user code for ever. Ending its threads lets the exit finish.
    for p in left:
        try:
            for t in p.threads():
                h = ctypes.windll.kernel32.OpenThread(0x0001, False, t.id)  # THREAD_TERMINATE
                if h:
                    ctypes.windll.kernel32.TerminateThread(h, 1)
                    ctypes.windll.kernel32.CloseHandle(h)
        except psutil.Error:
            pass
    psutil.wait_procs(left, timeout=15)
    return [p.pid for p in procs if not p.is_running()]


def _deadline(seconds, on_expire, fn):
    """Run one blocking COM call. If it has not returned after `seconds`, run on_expire() from another thread.

    COM gives an outgoing call no timeout of its own, so a hung instance holds its caller for ever.
    """
    done = threading.Event()

    def dog():
        if not done.wait(seconds):
            on_expire()

    threading.Thread(target=dog, daemon=True).start()
    try:
        return fn()
    finally:
        done.set()


def status():
    """Every SLDWORKS.exe on this machine: (pid, age s, threads, windows, private MB, answers). Looks, never touches."""
    rows = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() != "sldworks.exe":
            continue
        try:
            rows.append(
                (
                    p.pid,
                    round(time.time() - p.create_time()),
                    p.num_threads(),
                    len(_top_windows(p.pid)),
                    round(p.memory_info().private / 2**20),
                    answers(p.pid),
                )
            )
        except psutil.Error:
            pass
    return rows


def owner_file(pid):
    return os.path.join(tempfile.gettempdir(), f"sw_owner_{pid}.txt")


def _write_owner(pid, started):
    """Record this Python process as the client driving that instance: "sw_start client_pid client_start"."""
    try:
        with open(owner_file(pid), "w") as f:
            f.write(f"{started!r} {os.getpid()} {_started(os.getpid())!r}")
    except OSError:
        pass


def _drop_owner(pid):
    try:
        os.remove(owner_file(pid))
    except OSError:
        pass
    try:
        _claims().drop_instance(_claims().claims_dir(), pid)
    except Exception:
        pass


def _claims():
    """tools/pc/claims.py, which is stdlib only. Imported late so this module still loads if it is missing."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pc")
    if here not in sys.path:
        sys.path.insert(0, here)
    import claims

    return claims


def _note_instance(pid, started):
    """Leave a note saying which worktree and command drive this instance, so `--status` and `claims.py who <pid>` name
    an owner even when the session made no claim. Never raises: a note must not stop a launch."""
    try:
        c = _claims()
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        c.note_instance(c.claims_dir(), pid, started, repo, os.getpid(), " ".join(sys.argv) or sys.executable, time.time())
    except Exception:
        pass


def who(pid):
    """One line on who drives this instance: its claim if it has one, else the note its launcher left, else ''."""
    try:
        c = _claims()
        d = c.claims_dir()
        for claim in c.load_all(d):
            if claim.get("sw_pid") == pid and not claim.get("broken"):
                return f"claimed by {claim['session']}: {claim.get('status', '')}"
        n = c.instance_note(d, pid, _started(pid))
        if n:
            if pid == keeper_pid():
                return n["command"]
            return f"no claim; {n['worktree']} (client PID {n['client_pid']}): {n['command']}"
    except Exception:
        pass
    return ""


def _owner_alive(pid):
    """True if a client process is still driving this instance: the one in its owner file, or the one that started it.

    A client blocked in a long COM call (mesh, rebuild, reading a result back) is alive. One killed mid-call is not.
    """
    try:
        with open(owner_file(pid)) as f:
            sw_started, client, client_started = f.read().split()
        if sw_started == repr(_started(pid)) and repr(_started(int(client))) == client_started:
            return True
    except (OSError, ValueError):
        pass
    try:
        parent = psutil.Process(pid).parent()  # None once the launching process has gone, even if its pid was reused
        return parent is not None and parent.is_running()
    except psutil.Error:
        return False


def _solving(pid):
    """True if this instance has a Simulation solver running under it."""
    try:
        return any(c.name().lower() in SOLVERS for c in psutil.Process(pid).children(recursive=True))
    except psutil.Error:
        return False


def classify(answers_now, windows, solving, owner_alive):
    """What an instance is doing, from what can be seen without touching it.

    idle     answers.
    solving  not answering, a solver process runs under it. Healthy.
    busy     not answering, a live client is driving it (mesh, rebuild, reading a result back). Healthy.
    orphan   not answering, still has its windows, but no solver and no live client: finishing a call whose client
             was killed, or stuck. It may recover.
    zombie   not answering and no windows left: half-closed. It never recovers.
    """
    if answers_now:
        return "idle"
    if windows == 0:
        return "zombie"
    if solving:
        return "solving"
    if owner_alive:
        return "busy"
    return "orphan"


def state(row):
    """classify() for one row of status()."""
    pid, _age, _threads, windows, _mb, ok = row
    return classify(ok, windows, (not ok) and _solving(pid), (not ok) and _owner_alive(pid))


def _others(own_pid=None):
    """Other instances that are not answering, as (pid, state). The first 30 s of a process are its own startup."""
    return [(row[0], state(row)) for row in status() if row[0] != own_pid and not row[5] and row[1] > 30]


def _zombies(others, settle=20):
    """The pids among `others` that are half-closed, and stay so for `settle` seconds.

    An instance in an ordinary exit also has no windows and does not answer, for a few seconds. Only one that
    stays that way stalls launches, so a launch must not be refused, or stopped half way, for the first kind.
    """
    dead = [pid for pid, what in others if what == "zombie"]
    end = time.time() + settle
    while dead and time.time() < end:
        time.sleep(5)
        still = {pid for pid, what in _others() if what == "zombie"}
        dead = [pid for pid in dead if pid in still]
    return dead


def _zombie_error(pids):
    return RuntimeError(
        f"SolidWorks PID {pids} is half-closed (no windows, not answering) and stalls every launch. "
        f"Its owner must end_session() it, or run: taskkill /PID {pids[0]} /T /F"
    )


def _clear_journal_prompt(pid):
    """A third SolidWorks process stops at a modal 'journal file could not be created' prompt. Click OK on it.

    Only that exact prompt, only in this PID. That instance has no Auto Recover, so save after each step.
    """
    tops = []

    def find(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.GetClassName(h) == "#32770":
            tops.append(h)
        return True

    win32gui.EnumWindows(find, None)
    for h in tops:
        kids = []
        win32gui.EnumChildWindows(h, lambda c, _: kids.append(c) or True, None)  # noqa: B023 - called before the loop moves on
        texts = {win32gui.GetWindowText(c): c for c in kids}
        if any("journal file could not be created" in s for s in texts) and "OK" in texts:
            win32gui.PostMessage(texts["OK"], win32con.BM_CLICK, 0, 0)
            return True
    return False


def hide_windows(pid):
    """Hide every visible top-level window of this PID. Works while COM is blocked by a solve. Returns what it hid."""
    hid = []

    def find(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h):
            win32gui.ShowWindow(h, win32con.SW_HIDE)
            hid.append((win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        return True

    win32gui.EnumWindows(find, None)
    return hid


def minimize_windows(pid):
    """Fallback for anything that will not run hidden: minimize this PID's windows without taking focus."""
    hid = []

    def find(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h):
            win32gui.ShowWindow(h, win32con.SW_SHOWMINNOACTIVE)
            hid.append((win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        return True

    win32gui.EnumWindows(find, None)
    return hid


def hider_log(pid):
    return os.path.join(tempfile.gettempdir(), f"sw_hidden_{pid}.log")


def _watch_hidden(pid):
    """Hide windows of this PID and its child processes the moment they show, and hand focus back if one takes it.

    Runs on window events rather than polling, so a window has no time to paint. Child processes matter:
    sldexitapp.exe opens the SOLIDWORKS Error Report after an exit. Anything hidden is logged, because a hidden
    modal dialog blocks the instance.
    """
    user = ctypes.windll.user32
    ours = {pid: _started(pid)}  # pid to start time, because Windows reuses pids
    state = {"prev": None}
    seen = set()

    def live(p):
        return p in ours and ours[p] is not None and ours[p] == _started(p)

    foreign = {}  # pid to start time of processes already judged not ours: a process's ancestry never changes

    def is_ours(p):
        if live(p):
            return True
        try:
            q = psutil.Process(p)
            born = q.create_time()
            if foreign.get(p) == born:
                return False
            name = q.name().lower()
            crash = name == "sldexitapp.exe" and f"/SWPID={pid}" in " ".join(q.cmdline()).upper()
            if crash or _descends(q) or (name == "star.exe" and _our_solver(q)):
                ours[p] = born
                return True
            if name != "sldexitapp.exe":  # a crash report names its PID on the command line, not by ancestry
                foreign[p] = born
        except psutil.Error:
            pass
        return False

    def _descends(q):
        # Any ancestor, not only the direct parent: the solver (Simulation\star.exe) can sit below a helper process,
        # and a window shown in the first 2 s of a child's life would otherwise beat the sweep.
        try:
            return any(live(a.pid) for a in q.parents())
        except psutil.Error:
            return False

    def _our_solver(q):
        # star.exe whose parent chain is broken (helper already gone): ours if it started after this instance and no
        # other SolidWorks is an ancestor, so another session's solver window is never touched.
        try:
            if os.path.normcase(os.path.dirname(q.exe())) != SIM_DIR or q.create_time() < ours[pid]:
                return False
            return not any(a.name().lower() == "sldworks.exe" for a in q.parents())
        except (psutil.Error, KeyError, TypeError):
            return False

    def log(h, took):
        item = (win32gui.GetClassName(h), win32gui.GetWindowText(h))
        if item not in seen or took:
            seen.add(item)
            with open(hider_log(pid), "a", encoding="utf8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {item[0]} | {item[1]}{' | HAD FOCUS' if took else ''}\n")

    def event(_hook, ev, h, obj, child, _thread, _time):
        try:
            if obj != 0 or child != 0 or not h or user.GetAncestor(h, 2) != h:
                return
            p = win32process.GetWindowThreadProcessId(h)[1]
            if not is_ours(p):
                if ev == 3:
                    state["prev"] = h
                return
            if win32gui.IsWindowVisible(h):
                win32gui.ShowWindow(h, win32con.SW_HIDE)
            log(h, ev == 3)
            if ev == 3 and state["prev"] and win32gui.IsWindow(state["prev"]):
                user.SwitchToThisWindow(state["prev"], True)
        except Exception:  # noqa: BLE001, S110 - an exception must never escape a Windows event hook
            pass

    proc = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)(event)
    user.SetWinEventHook.restype = wt.HANDLE
    user.SetWinEventHook(0x8002, 0x8002, 0, proc, 0, 0, 0)  # EVENT_OBJECT_SHOW
    user.SetWinEventHook(3, 3, 0, proc, 0, 0, 0)  # EVENT_SYSTEM_FOREGROUND
    fore = win32gui.GetForegroundWindow()
    if fore and win32process.GetWindowThreadProcessId(fore)[1] not in ours:
        state["prev"] = fore
    msg = wt.MSG()
    sweep = 0
    gone = None
    muted = set()
    while True:
        user.MsgWaitForMultipleObjectsEx(0, None, 250, 0x04FF, 0)
        while user.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
            user.TranslateMessage(ctypes.byref(msg))
            user.DispatchMessageW(ctypes.byref(msg))
        # Sound: mute this instance's own audio sessions as they appear. Windows saves an app's mute by exe path, so
        # close() raises the unmute flag first and the sessions end unmuted; Joey's own SolidWorks never inherits it.
        if not os.path.exists(unmute_flag(pid)):
            hit = _mute([q for q in ours if live(q)], True)
            if hit:
                muted.update(hit)
                with open(hider_log(pid), "a", encoding="utf8") as f:
                    f.write(f"{time.strftime('%H:%M:%S')} MUTED audio of {sorted(set(hit))}\n")
        elif muted:
            _mute(list(muted), False)
            muted.clear()
        if time.time() - sweep > 2:
            sweep = time.time()
            alive = [q for q in ours if live(q)]
            for q in alive:
                try:
                    for c in psutil.Process(q).children(recursive=True):
                        ours.setdefault(c.pid, c.create_time())
                except psutil.Error:
                    pass
            for q in [q for q in ours if not live(q)]:
                del ours[q]
            alive = list(ours)
            # A crash report can appear after the instance has gone, so stay a minute longer.
            gone = (gone or time.time()) if not alive else None
            if gone and time.time() - gone > 60:
                try:
                    os.remove(unmute_flag(pid))
                except OSError:
                    pass
                return
            for q in alive:
                hide_windows(q)


def unmute_flag(pid):
    return os.path.join(tempfile.gettempdir(), f"sw_unmute_{pid}.flag")


def _mute(pids, on):
    """Mute or unmute the audio sessions of these PIDs only. Returns the PIDs changed; never raises."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import sw_audio  # noqa: PLC0415 - Windows Core Audio through ctypes, loaded only where it is used

        return sw_audio.mute_pids(set(pids), on)
    except Exception:  # noqa: BLE001 - sound is a nicety: a Core Audio failure must never stop the hider or a close
        return []


def _started(pid):
    try:
        return psutil.Process(pid).create_time()
    except psutil.Error:
        return None


def _start_hider(pid):
    """A separate process, so it keeps working while this one waits on a blocking COM call and after it exits."""
    exe = sys.executable
    w = exe.replace("python.exe", "pythonw.exe")
    subprocess.Popen(
        [w if os.path.exists(w) else exe, os.path.abspath(__file__), "--hide-watch", str(pid)],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )


def _attach_by_pid(pid):
    """Return the IDispatch registered in the ROT for this PID, or None."""
    rot = pythoncom.GetRunningObjectTable()
    ctx = pythoncom.CreateBindCtx(0)
    tag = f"SolidWorks_PID_{pid}".lower()
    for moniker in rot.EnumRunning():
        name = moniker.GetDisplayName(ctx, None).lower()
        if name.lstrip("!") == tag:
            return rot.GetObject(moniker).QueryInterface(pythoncom.IID_IDispatch)
    return None


class Instance:
    def __init__(self, pid, sw, owned=True):
        self.pid = pid
        self.sw = sw
        self.owned = owned
        self.no_auto_recover = False
        self.started = _started(pid)  # Windows reuses pids: only ever stop the process with this start time

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def hide(self):
        return hide_windows(self.pid)

    def minimize(self):
        return minimize_windows(self.pid)

    def rss_mb(self):
        return round(psutil.Process(self.pid).memory_info().rss / 1e6)

    def load_simulation(self):
        """Load the Simulation add-in in this instance. Returns its CosmosWorks object."""
        add = None
        for prog in ("SldWorks.Simulation", "CosmosWorks.CosmosWorks"):
            try:
                add = self.sw.GetAddInObject(prog)
            except Exception:  # noqa: BLE001 - any failure means try the next name, then LoadAddIn
                add = None
            if add is not None:
                break
        if add is None:
            rc = self.sw.LoadAddIn(SIM_DLL)
            if rc != 0:
                raise RuntimeError(f"Simulation add-in did not load, LoadAddIn returned {rc}; 7 means a license error")
            add = self.sw.GetAddInObject("SldWorks.Simulation")
        if add is None:
            raise RuntimeError("Simulation add-in object not available")
        return wc.dynamic.Dispatch(add.CosmosWorks._oleobj_)

    def private_mb(self):
        """Committed memory. Recycle the instance when this grows: the working set (rss_mb) hides it."""
        return round(psutil.Process(self.pid).memory_info().private / 2**20)

    def answers(self):
        return answers(self.pid)

    def close(self, timeout=60, busy_wait=30):
        """Close this instance's documents and exit it. Only ever touches self.pid and what it started.

        Always returns within about busy_wait + 4 * timeout seconds: an instance that does not answer for
        `busy_wait` seconds (still solving, or half-closed) is force-stopped with its solver, not asked to exit.
        """
        if not self.owned:
            raise RuntimeError("this session does not own that instance")
        # Unmute this instance's sessions before it exits, so Windows saves SLDWORKS.exe as unmuted (see the hider).
        try:
            with open(unmute_flag(self.pid), "w"):
                pass
            time.sleep(0.6)  # the hider checks the flag every 250 ms
            kids = psutil.Process(self.pid).children(recursive=True) if _started(self.pid) == self.started else []
            _mute([self.pid] + [k.pid for k in kids], False)
        except (OSError, psutil.Error):
            pass
        try:
            kids = psutil.Process(self.pid).children(recursive=True) if _started(self.pid) == self.started else []
        except psutil.Error:
            kids = []

        def stop():
            kill_tree(self.pid, self.started)

        if self.sw is not None:
            # An instance that is not answering would hold ExitApp for ever, so it is never asked: it is stopped.
            if _wait_answers(self.pid, busy_wait):
                try:
                    # If a call is still out after `timeout`, the instance is stopped, which makes the call return.
                    if int(_deadline(timeout, stop, lambda: self.sw.GetProcessID)) != self.pid:
                        raise RuntimeError("handle does not match this instance's PID")
                    _deadline(timeout, stop, lambda: self.sw.CloseAllDocuments(True))
                    _deadline(timeout, stop, lambda: self.sw.ExitApp())
                except pythoncom.com_error:
                    pass  # crashed, hung or stopped above: the process cleanup below still runs
            self.sw = None
        pythoncom.CoFreeUnusedLibraries()
        if self.started is not None and _started(self.pid) == self.started:
            try:
                psutil.Process(self.pid).wait(timeout)
            except psutil.TimeoutExpired:
                pass  # ExitApp can leave a half-closed process with no documents and no Simulation license.
            except psutil.NoSuchProcess:
                pass
            stop()
        # What the instance started must not outlive it: a solver (cwanalysisproc, star) keeps its cores and memory
        # with nothing left to read the result, and sldexitapp.exe opens a visible Error Report.
        for p in kids + [q for q in psutil.process_iter(["name", "ppid"]) if q.info["ppid"] == self.pid]:
            try:
                if p.name().lower() in ("cwanalysisproc.exe", "star.exe", "sldexitapp.exe", "sldprocmon.exe"):
                    p.kill()
            except psutil.Error:
                pass
        # Last, so that while a slow CloseAllDocuments holds the instance it still reads as driven, not orphaned.
        _drop_owner(self.pid)


def launch(timeout=300, visible=False, busy_wait=7200):
    """Start a new SolidWorks process and return an Instance attached to it by PID.

    Hidden by default, so it never stays on screen; a launch can still take focus briefly (RULES.md, Hidden by
    default). Pass visible=True only when someone needs to see it.

    Starts beside instances that are solving or busy. If the splash screen has to wait for one of them (RULES.md,
    Launching beside a busy instance), that wait is not counted against `timeout`, up to `busy_wait` seconds.
    Refuses only when another instance is half-closed, or has not answered for `timeout` seconds with nothing
    driving it.
    """
    if not os.path.exists(EXE):
        raise RuntimeError(f"SolidWorks not found at {EXE}")
    pythoncom.CoInitialize()
    with _LaunchLock(busy_wait + 2 * timeout):
        _retire_keeper()  # before the blocker check: a hung keeper would read as an orphan and refuse the launch
        _wait_for_blockers(timeout)
        _ensure_keeper(timeout, busy_wait)
        inst = _start(timeout, visible, busy_wait)
    _write_owner(inst.pid, inst.started)
    _note_instance(inst.pid, inst.started)
    return inst


class _WmiProc:
    """The two things _finish_launch asks of a Popen, for a process this one did not start as its child."""

    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self._started = _started(pid)

    def poll(self):
        if _started(self.pid) == self._started and self._started is not None:
            return None
        self.returncode = -1
        return self.returncode

    def kill(self):
        kill_tree(self.pid, self._started)


def _start_outside_job():
    """Start SolidWorks hidden through WMI, so it is not a child of this process, or None if that fails.

    A child started the usual way joins this process's job object. Under tools/pc/capped.py, or a tool that ends its
    whole process tree, that would end the keeper with the client that happened to start it.
    """
    try:
        wmi = wc.GetObject("winmgmts:")
        startup = wmi.Get("Win32_ProcessStartup").SpawnInstance_()
        startup.ShowWindow = win32con.SW_HIDE
        method = wmi.Get("Win32_Process")
        params = method.Methods_("Create").InParameters.SpawnInstance_()
        params.CommandLine = f'"{EXE}"'
        params.ProcessStartupInformation = startup
        out = method.ExecMethod_("Create", params)
        if int(out.ReturnValue) == 0 and out.ProcessId:
            return _WmiProc(int(out.ProcessId))
    except Exception:
        pass
    return None


def _start(timeout, visible, busy_wait, outside_job=False):
    """Start one SolidWorks process and wait for it. The caller holds the launch lock."""
    proc = _start_outside_job() if outside_job else None
    if proc is None:
        si = subprocess.STARTUPINFO()
        if not visible:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = win32con.SW_HIDE
        proc = subprocess.Popen([EXE], startupinfo=si)
    started = _started(proc.pid)
    try:
        return _finish_launch(proc, timeout, visible, busy_wait)
    except BaseException:
        kill_tree(proc.pid, started)  # never leave a hidden instance, or its sldProcMon, behind
        proc.kill()
        raise


KEEPER_MAX_MB = 1500
KEEPER_NOTE = "keeper: idle instance that takes other launches' startup call; leave it running"


def _keeper_paths():
    """(switch file, state file) in the claims folder, so every worktree's copy of this module agrees on them."""
    d = str(_claims().claims_dir())
    return os.path.join(d, "keeper.on"), os.path.join(d, "keeper.state")


def keeper_pid():
    """PID of the running keeper instance, or None."""
    try:
        return _session_pid(_keeper_paths()[1])
    except Exception:
        return None


def keeper_due(switched_on, pid, answers_now, private_mb):
    """What launch() does about the keeper: "none" (leave things as they are), "start", or "restart" (end it, start another).

    The keeper has no client, so nothing else would ever restart one that hangs or grows.
    """
    if not switched_on:
        return "none"
    if pid is None:
        return "start"
    if not answers_now or private_mb > KEEPER_MAX_MB:
        return "restart"
    return "none"


def _retire_keeper():
    """End a keeper that does not answer or has grown too large. Never raises."""
    try:
        switch, _state = _keeper_paths()
        pid = keeper_pid()
        if pid is None or not os.path.exists(switch):
            return
        mb = round(psutil.Process(pid).memory_info().private / 2**20)
        # 90 s, not the 30 s an attach allows: under heavy paging an idle instance can be slow, and nothing drives it
        if keeper_due(True, pid, _wait_answers(pid, 90), mb) == "restart":
            print(f"sw_instance: replacing the keeper, PID {pid} ({mb} MB)", file=sys.stderr)
            kill_tree(pid, _started(pid))
            _drop_owner(pid)
    except Exception as e:
        print(f"sw_instance: keeper not checked ({e})", file=sys.stderr)


def _note_keeper(pid):
    c = _claims()
    if c.instance_note(c.claims_dir(), pid, _started(pid)) is None:
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        c.note_instance(c.claims_dir(), pid, _started(pid), repo, 0, KEEPER_NOTE, time.time())


def _ensure_keeper(timeout=300, busy_wait=7200):
    """Keep one idle, hidden SolidWorks running where the workstation asks for it (RULES.md, The keeper).

    A new SolidWorks waits at the splash screen until the oldest running instance answers. An instance that only ever
    idles answers at once, so once the keeper is the oldest no launch waits behind another session's mesh or result
    read-back. Called with the launch lock held. Never raises: a launch must not fail because the keeper did.
    """
    try:
        switch, state = _keeper_paths()
        pid = keeper_pid()
        if pid is not None:
            _note_keeper(pid)  # one adopted from a state file has no note yet
        if keeper_due(os.path.exists(switch), pid, True, 0) != "start":
            return
        older = [row[0] for row in status()]
        inst = _start(timeout, False, busy_wait, outside_job=True)
        with open(state, "w") as f:
            f.write(f"{inst.pid} {inst.started!r}")
        _note_keeper(inst.pid)
        inst.sw = None  # let go of it without closing: it outlives this process
        if older:
            print(f"sw_instance: keeper started as PID {inst.pid}; it only helps once the older instances "
                  f"{older} have exited", file=sys.stderr)
    except Exception as e:
        print(f"sw_instance: keeper not started ({e})", file=sys.stderr)


def keeper(switch_on):
    """Turn the workstation's keeper on (and start it) or off (and end it). `python sw_instance.py --keeper on|off`."""
    switch, state = _keeper_paths()
    if switch_on:
        os.makedirs(os.path.dirname(switch), exist_ok=True)
        open(switch, "a").close()
        pythoncom.CoInitialize()
        with _LaunchLock(7200):
            _retire_keeper()
            _ensure_keeper()
        return keeper_pid()
    with _LaunchLock(7200):  # not while another process is in its startup call into the keeper
        if os.path.exists(switch):
            os.remove(switch)
        pid = keeper_pid()
        if pid is not None:
            kill_tree(pid, _started(pid))
            _drop_owner(pid)
        if os.path.exists(state):
            os.remove(state)
    return None


def _wait_for_blockers(timeout):
    """Do not start beside an instance that will hold the new one at the splash screen for ever.

    A half-closed instance never answers again, so that raises at once with its PID: its owner must end it
    (end_session), or Joey must (taskkill /PID <pid> /T /F). An orphan (not answering, no solver, no live client)
    may still be finishing a call, so it gets `timeout` seconds. A solving or busy instance is healthy: the launch
    goes ahead beside it.
    """
    start = time.time()
    while True:
        others = _others()
        dead = _zombies(others)
        if dead:
            raise _zombie_error(dead)
        orphans = [pid for pid, what in others if what == "orphan"]
        if not orphans:
            return
        if time.time() - start > timeout:
            raise RuntimeError(
                f"SolidWorks PID {orphans} has not answered for {timeout} s and nothing is driving it (no solver, "
                "no live client), so a launch could wait at the splash screen for ever. Read its sw_hidden_<pid>.log; "
                f"its owner must end_session() it, or run: taskkill /PID {orphans[0]} /T /F"
            )
        time.sleep(5)


class _StartClock:
    """The startup time limit. It stops while another instance is solving or busy, because the new process then
    waits at the splash screen for that instance to answer (RULES.md, Launching beside a busy instance)."""

    def __init__(self, own_pid, timeout, busy_wait):
        self.own_pid = own_pid
        self.left = timeout
        self.end = time.time() + timeout + busy_wait
        self.last = time.time()
        self.looked = 0.0
        self.held_by = []

    def running(self):
        now = time.time()
        if now - self.looked > 10:  # looking costs up to 3 s for each instance that is not answering
            others = _others(self.own_pid)
            dead = _zombies(others)
            if dead:
                raise _zombie_error(dead)
            self.held_by = [pid for pid, what in others if what in ("solving", "busy")]
            self.looked = now = time.time()
        if not self.held_by:
            self.left -= now - self.last
        self.last = now
        return self.left > 0 and now < self.end

    def why(self):
        return f"; PID {self.held_by} was busy and may have held it at the splash screen" if self.held_by else ""


def _finish_launch(proc, timeout, visible, busy_wait=0):
    """Attach to the process launch() just started and wait for it to finish starting."""
    pid = proc.pid
    if not visible:
        _start_hider(pid)
    clock = _StartClock(pid, timeout, busy_wait)
    disp = None
    journal = False
    while clock.running():
        if proc.poll() is not None:
            raise RuntimeError(f"SolidWorks exited during start, code {proc.returncode}")
        journal = _clear_journal_prompt(pid) or journal
        try:
            disp = _attach_by_pid(pid)
        except pythoncom.com_error:
            disp = None
        if disp is not None:
            break
        time.sleep(1)
    if disp is None:
        raise RuntimeError(f"SolidWorks PID {pid} never registered in the ROT{clock.why()}")
    sw = wc.dynamic.Dispatch(disp)
    while clock.running():
        if proc.poll() is not None:
            raise RuntimeError(f"SolidWorks exited during start, code {proc.returncode}")
        journal = _clear_journal_prompt(pid) or journal
        try:
            if sw.StartupProcessCompleted:
                break
        except pythoncom.com_error:
            pass
        time.sleep(1)
    else:
        raise RuntimeError(f"SolidWorks PID {pid} did not finish starting{clock.why()}")
    got = int(sw.GetProcessID)
    if got != pid:
        raise RuntimeError(f"attached to PID {got}, expected {pid}")
    sw.Visible = visible
    if not visible:
        sw.UserControl = False
    inst = Instance(pid, sw)
    inst.no_auto_recover = journal
    return inst


def attach(pid, busy_wait=30):
    """Attach to an instance this session already launched, for example from an earlier script run.

    Raises NotAnswering, without touching it, if the instance does not answer within `busy_wait` seconds.
    """
    pythoncom.CoInitialize()
    # The first call into an instance that is not answering never returns, so check before making it.
    if not _wait_answers(pid, busy_wait):
        raise NotAnswering(
            f"SolidWorks PID {pid} is not answering (still solving, stuck behind a hidden dialog, or half-closed). "
            "Wait for the solve, or end_session() to stop it."
        )
    disp = _attach_by_pid(pid)
    if disp is None:
        raise RuntimeError(f"no SolidWorks PID {pid} in the ROT")
    sw = wc.dynamic.Dispatch(disp)
    got = int(sw.GetProcessID)
    if got != pid:
        raise RuntimeError(f"attached to PID {got}, expected {pid}")
    inst = Instance(pid, sw)
    _write_owner(pid, inst.started)  # this process drives it now: other sessions' launches read it as busy, not orphaned
    _note_instance(pid, inst.started)
    return inst


def _session_pid(state):
    """The PID in the state file if that exact process (same start time) is still SolidWorks, else None.

    The file holds "pid start_time", because Windows reuses pids: a bare pid could name another session's instance.
    """
    try:
        with open(state) as fh:
            pid_text, started = fh.read().split()
        pid = int(pid_text)
        proc = psutil.Process(pid)
        if proc.name().lower() == "sldworks.exe" and repr(proc.create_time()) == started:
            return pid
    except (OSError, ValueError, psutil.Error):
        pass
    return None


def session(state_file, visible=False):
    """Reuse this session's instance across script runs, keyed by a state file the session owns.

    `visible` applies only when a new instance is launched; an existing one keeps how it was started.
    """
    state = str(state_file)
    pid = _session_pid(state) if os.path.exists(state) else None
    if pid is not None:
        return attach(pid)
    inst = launch(visible=visible)
    with open(state, "w") as f:
        f.write(f"{inst.pid} {inst.started!r}")
    return inst


def end_session(state_file, busy_wait=30):
    """Close this session's instance if it is running. Never starts one.

    Always ends it: an instance that does not answer within `busy_wait` seconds is force-stopped with its solver,
    and the state file is removed either way, so the next session() starts clean.
    """
    state = str(state_file)
    if os.path.exists(state):
        pid = _session_pid(state)
        if pid is not None:
            started = _started(pid)
            try:
                attach(pid, busy_wait).close()
            except (NotAnswering, RuntimeError, pythoncom.com_error):
                pass  # not answering, or gone from the ROT: it is still this session's, so stop it below
            kill_tree(pid, started)
            _drop_owner(pid)
        os.remove(state)


def _solve_lock_holder(path):
    """The lock file's text if its holder may still be running, else None. Lines: owner, pid, process start time, taken at.

    A lock is only ever taken over on proof that its holder has gone, because a session may have written the file
    by hand in another layout: big_solve's own layout with a dead or reused pid, or any text whose every number is
    not a running pid. An empty file is a holder between creating and writing it, unless it is a minute old.
    """
    try:
        with open(path) as f:
            text = f.read()
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return None
    lines = text.splitlines()
    try:
        pid, born = int(lines[1]), float(lines[2])
    except (IndexError, ValueError):
        if not text.strip():
            return None if age > 60 else "(being written)"
        pids = [int(n) for n in re.findall(r"\d+", text) if len(n) < 10]
        return text if not pids or any(_started(p) is not None for p in pids) else None
    return text if _started(pid) == born else None


class big_solve:  # noqa: N801 - reads as a verb at the call site: `with big_solve("shoulder"):`
    """Hold the workstation's one large-solve slot for the length of a `with` block (RULES.md, rule 6).

        with big_solve("shoulder hub yaw"):
            study.RunAnalysis

    For a Simulation solve expected to need more than about 6 GB. Waits while another session holds it. The lock
    is a file created exclusively and removed on the way out; one whose holder process has gone is taken over.
    Two sessions that find the same dead lock at the same instant can both take it; the window is a few
    milliseconds and the cost is two large solves at once, which is what happened without the lock.
    """

    def __init__(self, owner, path=SOLVE_LOCK, timeout=6 * 3600, poll=15):
        self.owner, self.path, self.timeout, self.poll = str(owner), path, timeout, poll

    def __enter__(self):
        mine = f"{self.owner}\n{os.getpid()}\n{_started(os.getpid())!r}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
        end = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                holder = _solve_lock_holder(self.path)
                if holder is None:
                    try:
                        os.remove(self.path)
                        continue
                    except FileNotFoundError:
                        continue
                    except OSError:
                        holder = "a lock left behind that cannot be removed"
                if time.time() > end:
                    raise TimeoutError(f"large-solve lock {self.path} still held after {self.timeout} s by: {holder}") from None
                time.sleep(self.poll)
                continue
            with os.fdopen(fd, "w") as f:
                f.write(mine)
            self.mine = mine
            return self

    def __exit__(self, *exc):
        try:
            with open(self.path) as f:
                ours = f.read() == self.mine
            if ours:
                os.remove(self.path)
        except OSError:
            pass


NOTES = {
    "idle": "",
    "solving": "  solving",
    "busy": "  busy: a live client is driving it",
    "orphan": "  ORPHAN: not answering, no solver, no live client; launches wait for it, then refuse",
    "zombie": "  HALF-CLOSED: stalls every launch",
}

if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--hide-watch":
    _watch_hidden(int(sys.argv[2]))
elif __name__ == "__main__" and sys.argv[1:] == ["--status"]:
    print("    pid   age_s threads windows private_MB answers")
    for row in status():
        print("{:7d} {:7d} {:7d} {:7d} {:10d} {!s:>7}".format(*row) + NOTES[state(row)])
        if who(row[0]):
            print("        " + who(row[0]))
elif __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--keeper" and sys.argv[2] in ("on", "off", "status"):
    if sys.argv[2] != "status":
        keeper(sys.argv[2] == "on")
    print(f"keeper switch {'on' if os.path.exists(_keeper_paths()[0]) else 'off'}, PID {keeper_pid()}")
