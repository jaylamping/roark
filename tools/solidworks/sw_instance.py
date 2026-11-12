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
    main = [h for h in tops if win32gui.GetClassName(h).startswith("Afx:")] or tops
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


def _blockers(own_pid=None):
    """Other instances that will stall a launch at the splash screen: (pid, half_closed)."""
    out = []
    for pid, age, _threads, windows, _mb, ok in status():
        if pid != own_pid and not ok and age > 30:
            out.append((pid, windows == 0))
    return out


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


def launch(timeout=300, visible=False):
    """Start a new SolidWorks process and return an Instance attached to it by PID.

    Hidden by default, so it never stays on screen; a launch can still take focus briefly (RULES.md, Hidden by
    default). Pass visible=True only when someone needs to see it.
    """
    if not os.path.exists(EXE):
        raise RuntimeError(f"SolidWorks not found at {EXE}")
    pythoncom.CoInitialize()
    with _LaunchLock(2 * timeout):
        _wait_for_blockers(timeout)
        si = subprocess.STARTUPINFO()
        if not visible:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = win32con.SW_HIDE
        proc = subprocess.Popen([EXE], startupinfo=si)
        started = _started(proc.pid)
        try:
            return _finish_launch(proc, timeout, visible)
        except BaseException:
            kill_tree(proc.pid, started)  # never leave a hidden instance, or its sldProcMon, behind
            proc.kill()
            raise


def _wait_for_blockers(timeout):
    """A launch stalls at the splash screen while any other instance is not answering, so do not start one then.

    Waits for a solving instance to finish. A half-closed one never will, so that raises at once with its PID:
    its owner must end it (end_session), or Joey must (taskkill /PID <pid> /T /F).
    """
    start = time.time()
    while True:
        blockers = _blockers()
        dead = [pid for pid, half_closed in blockers if half_closed]
        if dead:
            raise RuntimeError(
                f"SolidWorks PID {dead} is half-closed (no windows, not answering) and stalls every launch. "
                f"Its owner must end_session() it, or run: taskkill /PID {dead[0]} /T /F"
            )
        if not blockers:
            return
        if time.time() - start > timeout:
            raise RuntimeError(
                f"SolidWorks PID {[pid for pid, _ in blockers]} did not answer for {timeout} s (solving, or stuck "
                "behind a hidden dialog), and a launch stalls at the splash screen until it does. Try again later."
            )
        time.sleep(5)


def _finish_launch(proc, timeout, visible):
    """Attach to the process launch() just started and wait for it to finish starting."""
    pid = proc.pid
    if not visible:
        _start_hider(pid)
    start = time.time()
    disp = None
    journal = False
    while time.time() - start < timeout:
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
        raise RuntimeError(f"SolidWorks PID {pid} never registered in the ROT")
    sw = wc.dynamic.Dispatch(disp)
    while time.time() - start < timeout:
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
        raise RuntimeError(f"SolidWorks PID {pid} did not finish starting")
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
    return Instance(pid, sw)


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
        os.remove(state)


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--hide-watch":
    _watch_hidden(int(sys.argv[2]))
elif __name__ == "__main__" and sys.argv[1:] == ["--status"]:
    print("    pid   age_s threads windows private_MB answers")
    for row in status():
        note = "" if row[5] else "  HALF-CLOSED: stalls every launch" if row[3] == 0 else "  busy: launches wait for it"
        print("{:7d} {:7d} {:7d} {:7d} {:10d} {!s:>7}".format(*row) + note)
