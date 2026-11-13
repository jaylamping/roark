"""Is anyone using this PC right now? conventions/cad-workstation.md section 5.

    python tools/pc/user_idle.py [--watch SECONDS]     # default 180

Prints one line and exits 0 if the PC is free for a job, 1 if someone is using it, 2 if it could not tell. A thread asks
this of Joey-PC before it moves a waiting job there. Windows only; stdlib only.

It watches the keyboard and mouse for SECONDS and counts the seconds in which any input arrived. A person at the PC
makes input in many of them. Joey-PC also runs a script that nudges the mouse about every ten minutes to keep remote
sessions alive, and Windows counts that as input, so "time since the last input" never passes ten minutes there: one
nudge is at most a few seconds of input in the window, which still reads as free. A fullscreen window in front (a game,
a film) counts as in use whatever the input.

It must run in the logged-in desktop session, which a Remote Control session does. From a service the input time is
meaningless, and it exits 2.
"""

from __future__ import annotations

import sys

NUDGE_S = 3  # seconds of input a keep-alive mouse nudge may make in one watch


def free_to_use(input_s: int | None, fullscreen: bool, watch_s: float) -> tuple[int, str]:
    """(exit code, reason) from the seconds with input seen during the watch. A fullscreen window counts as in use
    however quiet the input: a film or a game played on a controller sends no keyboard or mouse input."""
    if input_s is None:
        return 2, "could not read the input time (not in the desktop session?)"
    if fullscreen:
        return 1, "in use: a fullscreen window is in front"
    if input_s > NUDGE_S:
        return 1, f"in use: input in {input_s} of {watch_s:.0f} s"
    return 0, f"free: input in {input_s} of {watch_s:.0f} s (a keep-alive nudge at most) and nothing fullscreen"


def last_input_tick() -> int | None:
    import ctypes
    import ctypes.wintypes as wt

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)) or info.dwTime == 0:
        return None
    return info.dwTime


def input_seconds(watch_s: float) -> int | None:
    """How many one-second samples over `watch_s` saw new input. Stops early once it is clearly a person."""
    import time

    last = last_input_tick()
    if last is None:
        return None
    seen = 0
    end = time.monotonic() + watch_s
    while time.monotonic() < end and seen <= NUDGE_S:
        time.sleep(1.0)
        now = last_input_tick()
        if now is None:
            return None
        if now != last:
            seen, last = seen + 1, now
    return seen


def fullscreen_in_front() -> bool:
    import ctypes
    import ctypes.wintypes as wt

    user = ctypes.windll.user32
    h = user.GetForegroundWindow()
    if not h or h in (user.GetDesktopWindow(), user.GetShellWindow()):
        return False
    name = ctypes.create_unicode_buffer(64)
    user.GetClassNameW(h, name, 64)
    if name.value in ("Progman", "WorkerW"):  # the desktop itself
        return False

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

    win = wt.RECT()
    mon = MONITORINFO()
    mon.cbSize = ctypes.sizeof(mon)
    if not user.GetWindowRect(h, ctypes.byref(win)):
        return False
    if not user.GetMonitorInfoW(user.MonitorFromWindow(h, 2), ctypes.byref(mon)):
        return False
    m = mon.rcMonitor
    return win.left <= m.left and win.top <= m.top and win.right >= m.right and win.bottom >= m.bottom


def main(argv: list[str]) -> int:
    if sys.platform != "win32":
        print("user_idle.py is Windows only")
        return 2
    watch_s = float(argv[argv.index("--watch") + 1]) if "--watch" in argv else 180.0
    if fullscreen_in_front():
        code, why = free_to_use(0, True, watch_s)
    else:
        code, why = free_to_use(input_seconds(watch_s), fullscreen_in_front(), watch_s)
    print(why)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
