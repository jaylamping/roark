"""Per-process audio sessions through Windows Core Audio, with ctypes only, so the launcher needs no extra package.

The hider mutes the sessions of the instance it watches (see RULES.md, Sound). Run this file to list every session with its
mute state and peak meter.
"""
import ctypes
import ctypes.wintypes as wt
import uuid

ole = ctypes.OleDLL("ole32")
HR = ctypes.HRESULT


class GUID(ctypes.Structure):
    _fields_ = [("b", ctypes.c_byte * 16)]

    @classmethod
    def of(cls, s):
        g = cls()
        ctypes.memmove(g.b, uuid.UUID(s).bytes_le, 16)
        return g


CLSID_ENUM = GUID.of("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_ENUM = GUID.of("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_MGR2 = GUID.of("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F")
IID_CTL2 = GUID.of("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D")
IID_VOL = GUID.of("87CE5498-68D6-44E5-9215-6DA47EF883D8")
IID_METER = GUID.of("C02216F6-8C67-4B5B-9D00-D008E73E0064")


def _m(p, i, *argt):
    """Method i of the COM object at p."""
    vt = ctypes.cast(ctypes.cast(p, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    return ctypes.WINFUNCTYPE(HR, ctypes.c_void_p, *argt)(vt[i])


def _rel(p):
    if p:
        vt = ctypes.cast(ctypes.cast(p, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])(p)


def _qi(p, iid):
    out = ctypes.c_void_p()
    _m(p, 0, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(p, ctypes.byref(iid), ctypes.byref(out))
    return out


def sessions():
    """Yield (pid, is_system_sounds, ISimpleAudioVolume ptr, IAudioMeterInformation ptr) for every session on every
    active render device. The caller does not release; pointers are released after the generator moves on."""
    try:
        ole.CoInitializeEx(None, 2)
    except OSError:
        pass
    en = ctypes.c_void_p()
    ole.CoCreateInstance(ctypes.byref(CLSID_ENUM), None, 1, ctypes.byref(IID_ENUM), ctypes.byref(en))
    col = ctypes.c_void_p()
    _m(en, 3, ctypes.c_int, wt.DWORD, ctypes.POINTER(ctypes.c_void_p))(en, 0, 1, ctypes.byref(col))  # render, active
    n = wt.UINT()
    _m(col, 3, ctypes.POINTER(wt.UINT))(col, ctypes.byref(n))
    for i in range(n.value):
        dev = ctypes.c_void_p()
        _m(col, 4, wt.UINT, ctypes.POINTER(ctypes.c_void_p))(col, i, ctypes.byref(dev))
        mgr = ctypes.c_void_p()
        _m(dev, 3, ctypes.POINTER(GUID), wt.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            dev, ctypes.byref(IID_MGR2), 23, None, ctypes.byref(mgr))
        se = ctypes.c_void_p()
        _m(mgr, 5, ctypes.POINTER(ctypes.c_void_p))(mgr, ctypes.byref(se))
        k = ctypes.c_int()
        _m(se, 3, ctypes.POINTER(ctypes.c_int))(se, ctypes.byref(k))
        for j in range(k.value):
            ctl = ctypes.c_void_p()
            _m(se, 4, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(se, j, ctypes.byref(ctl))
            c2 = _qi(ctl, IID_CTL2)
            pid = wt.DWORD()
            try:
                _m(c2, 14, ctypes.POINTER(wt.DWORD))(c2, ctypes.byref(pid))
            except OSError:
                pass  # multi-process session
            system = _m(c2, 15)(c2) == 0  # IsSystemSoundsSession returns S_OK for the system sounds session
            vol, meter = _qi(ctl, IID_VOL), _qi(ctl, IID_METER)
            try:
                yield pid.value, system, vol, meter
            finally:
                for p in (vol, meter, c2, ctl):
                    _rel(p)
        for p in (se, mgr, dev):
            _rel(p)
    _rel(col)
    _rel(en)


def set_mute(vol, on):
    _m(vol, 5, wt.BOOL, ctypes.c_void_p)(vol, bool(on), None)


def get_mute(vol):
    b = wt.BOOL()
    _m(vol, 6, ctypes.POINTER(wt.BOOL))(vol, ctypes.byref(b))
    return bool(b.value)


def peak(meter):
    f = ctypes.c_float()
    _m(meter, 3, ctypes.POINTER(ctypes.c_float))(meter, ctypes.byref(f))
    return f.value


def mute_pids(pids, on=True):
    """Mute (or unmute) every session owned by one of these PIDs. Returns the PIDs whose mute changed."""
    hit = []
    for pid, system, vol, _ in sessions():
        if pid in pids and not system and get_mute(vol) != on:
            set_mute(vol, on)
            hit.append(pid)
    return hit


if __name__ == "__main__":
    import psutil
    for pid, system, vol, meter in sessions():
        try:
            name = psutil.Process(pid).name() if pid else "-"
        except psutil.Error:
            name = "?"
        print(pid, name, "system" if system else "", "muted" if get_mute(vol) else "", round(peak(meter), 4))
