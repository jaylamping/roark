"""Is anyone using this PC right now? conventions/cad-workstation.md section 5.

    python tools/pc/user_idle.py [--min MINUTES]     # default 15

Prints one line and exits 0 if the PC is free for a job (nobody has touched the keyboard or mouse for MINUTES and no
fullscreen window, such as a game or a film, is in front), 1 if someone is using it, 2 if it could not tell. A thread asks
this of Joey-PC before it moves a waiting job there. Windows only; stdlib only.

It must run in the logged-in desktop session, which a Remote Control session does. From a service the idle time is
meaningless, and it exits 2.
"""

from __future__ import annotations

import sys


def free_to_use(idle_s: float | None, fullscreen: bool, min_idle_s: float) -> tuple[int, str]:
    """(exit code, reason). A fullscreen window counts as in use however long the input has been quiet: a film or a game
    played on a controller sends no keyboard or mouse input."""
    if idle_s is None:
        return 2, "could not read the idle time (not in the desktop session?)"
    if fullscreen:
        return 1, f"in use: a fullscreen window is in front (input idle {idle_s / 60:.0f} min)"
    if idle_s < min_idle_s:
        return 1, f"in use: last input {idle_s / 60:.1f} min ago, under {min_idle_s / 60:.0f} min"
    return 0, f"free: no input for {idle_s / 60:.0f} min and nothing fullscreen"


def idle_seconds() -> float | None:
    import ctypes
    import ctypes.wintypes as wt

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)) or info.dwTime == 0:
        return None
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


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
    minutes = float(argv[argv.index("--min") + 1]) if "--min" in argv else 15.0
    code, why = free_to_use(idle_seconds(), fullscreen_in_front(), minutes * 60)
    print(why)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
