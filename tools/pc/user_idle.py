"""Is anyone using this PC right now? conventions/cad-workstation.md section 5.

    python tools/pc/user_idle.py [--watch SECONDS]     # default 180

Prints one line and exits 0 if the PC is free for a job, 1 if someone is using it, 2 if it could not tell. A thread asks
this of Joey-PC before it moves a waiting job there. Windows only; stdlib only.

It watches the keyboard and mouse for SECONDS, one look a second. A person at the PC makes input for many seconds on
end (bursts of 19 to 36 s were logged on Joey-PC, 2026-11-13). Joey-PC also runs a keep-alive script for remote sessions:
once nobody has touched the PC for five minutes, it sweeps the mouse across the monitors every two minutes, about 1.2 s
each time, and Windows counts that as input, so "time since the last input" never grows there. The check therefore reads
the PC as in use when any burst of input lasts longer than a sweep can, or when there is more input in total than a few
sweeps make. A fullscreen window in front (a game, a film) counts as in use whatever the input.

It must run in the logged-in desktop session, which a Remote Control session does. From a service the input time is
meaningless, and it exits 2.
"""

from __future__ import annotations

import sys

SWEEP_S = 3  # the longest run of seconds one keep-alive sweep can fill (1.2 s of input, sampled each second)
SWEEPS_S = 8  # the most seconds of input the sweeps can make in one watch (two a watch, plus its window clicks)


def free_to_use(total_s: int | None, longest_s: int, fullscreen: bool, watch_s: float) -> tuple[int, str]:
    """(exit code, reason) from the seconds with input seen during the watch and the longest unbroken run of them. A
    fullscreen window counts as in use however quiet the input: a film or a game on a controller sends no input."""
    if total_s is None:
        return 2, "could not read the input time (not in the desktop session?)"
    if fullscreen:
        return 1, "in use: a fullscreen window is in front"
    if longest_s > SWEEP_S or total_s > SWEEPS_S:
        return 1, f"in use: input in {total_s} of {watch_s:.0f} s, {longest_s} s on end"
    return 0, f"free: input in {total_s} of {watch_s:.0f} s (keep-alive sweeps at most) and nothing fullscreen"


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


def bursts(seen: list[bool]) -> tuple[int, int]:
    """(seconds with input, longest unbroken run of them) from one flag per one-second look."""
    total = longest = run = 0
    for hit in seen:
        run = run + 1 if hit else 0
        total += hit
        longest = max(longest, run)
    return total, longest


def watch_input(watch_s: float) -> tuple[int | None, int]:
    """bursts() over `watch_s` seconds of looking. Stops early once it is clearly a person."""
    import time

    last = last_input_tick()
    if last is None:
        return None, 0
    seen: list[bool] = []
    end = time.monotonic() + watch_s
    while time.monotonic() < end:
        time.sleep(1.0)
        now = last_input_tick()
        if now is None:
            return None, 0
        seen.append(now != last)
        last = now
        total, longest = bursts(seen)
        if longest > SWEEP_S or total > SWEEPS_S:
            break
    return bursts(seen)


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
        code, why = free_to_use(0, 0, True, watch_s)
    else:
        total, longest = watch_input(watch_s)
        code, why = free_to_use(total, longest, fullscreen_in_front(), watch_s)
    print(why)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
