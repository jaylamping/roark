"""Read (and with --press <label>, answer) a hidden dialog in MY OWN SolidWorks instance: python read_dialog.py <pid> [--press OK]"""
import ctypes
import sys

import psutil
import win32con
import win32gui
import win32process

pid = int(sys.argv[1])
press = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '--press' else None
pids = {pid} | {c.pid for c in psutil.Process(pid).children(recursive=True)}


def text_of(c):
    buf, res = ctypes.create_unicode_buffer(4000), ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(c, win32con.WM_GETTEXT, 4000, buf, 2, 1000, ctypes.byref(res))
    return buf.value


def each(h, _):
    if win32process.GetWindowThreadProcessId(h)[1] in pids and win32gui.GetClassName(h) == '#32770':
        kids = []
        win32gui.EnumChildWindows(h, lambda c, k: k.append(c) or True, kids)
        print('DIALOG', repr(win32gui.GetWindowText(h)), 'visible', win32gui.IsWindowVisible(h), 'enabled', win32gui.IsWindowEnabled(h))
        for c in kids:
            cls, t = win32gui.GetClassName(c), text_of(c)
            if t:
                print('   ', cls, repr(t[:600]))
            if press and cls == 'Button' and t.replace('&', '').strip() == press:
                win32gui.PostMessage(c, win32con.BM_CLICK, 0, 0)
                print('    pressed', press)
    return True


win32gui.EnumWindows(each, None)
