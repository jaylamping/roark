"""Modelling helpers for scripted SolidWorks work: one job, one instance, every step checked.

    import sys
    sys.path.insert(0, r"J:\\code\\roark-wt\\<session>\\tools\\solidworks")
    from swkit import *

    with job() as j:                                   # own instance (RULES.md), closed on the way out
        d = new_part(j.sw, r"...\\cad\\_wip\\demo\\block.SLDPRT")
        with Sk(d, plane(d, 'Z', 5.0, 'BLOCK_P'), 'BLOCK') as s:
            s.rect((0, 0, 5.0), (40, 20, 5.0))
        extrude(d, s.feat, 'BLOCK', 10.0, mode=MID)    # raises unless the volume grew
        save(d)
        export(j.sw, d, r"...\\block.step")

How to use it, and why each helper is shaped the way it is: playbook/README.md. Everything here takes and returns
millimetres and degrees in the model frame; SolidWorks itself works in metres and radians, and the helpers convert.

The feature calls are the ones the left-arm build scripts proved on SolidWorks 2026 (cad/scripts/arm/swg.py and
organic_master.py on branch left-arm-organic-r1). Windows only: needs pywin32, psutil and numpy.
"""
import contextlib
import math
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import psutil
import pythoncom
from win32com.client import VARIANT

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_instance  # noqa: E402
from sw_instance import close_welcome, launch  # noqa: E402

m = 1e-3
NUL = VARIANT(pythoncom.VT_DISPATCH, None)       # "no object" for an optional COM argument; plain None is refused
BASE = {'X': 'Right Plane', 'Y': 'Top Plane', 'Z': 'Front Plane'}       # the default plane normal to each model axis
BLIND, THRU_ALL, UP_TO_NEXT, MID = 0, 1, 2, 6      # swEndConditions_e
PART, ASSEMBLY = 1, 2                              # swDocumentTypes_e
STALL_S = 180                                      # a call out this long with SolidWorks idle is written up (stall_watch)
MIN_FREE_GB = 8.0                                  # holly-pc rule: leave this much free after a launch (cad-workstation.md)


class Failed(RuntimeError):
    """A SolidWorks step did not do what was asked. The message names the step; nothing after it has run.

    Failed(what, try_=..., stop=...) adds the two lines a reader needs next: what to change before running again, and
    when to give that up. They are printed with the message, and kept as .try_ and .stop.
    """

    def __init__(self, what, try_=None, stop=None):
        self.what, self.try_, self.stop = what, try_, stop
        super().__init__(what + (f'\n  try: {try_}' if try_ else '') + (f'\n  stop when: {stop}' if stop else ''))


def L(v=0):
    """A by-reference long, for the error and warning out-arguments: e = L(); f(..., e); e.value."""
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)


def call(o, name, *a):
    """Read o.name whether late binding exposes it as a property or as a method (it differs between calls and builds)."""
    v = getattr(o, name)
    if hasattr(v, '_oleobj_'):       # a COM object is callable too: it is the value, not a method (measured on
        return v                     # GetFirstDisplayDimension, 2026-11-13)
    return v(*a) if callable(v) else v


def dispatch_array(items):
    """A COM array of objects (faces, edges), for the calls that refuse a Python list (CreateContactSet)."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(items))


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def free_gb():
    return psutil.virtual_memory().available / 2 ** 30


class stall_watch:      # noqa: N801 - reads as a verb at the call site, like job
    """with stall_watch(pid, folder): write a report when this thread makes no progress while SolidWorks sits idle.

    A COM call has no timeout: when a hidden dialog holds the instance the script waits for ever and says nothing
    (the Welcome dialog under a first STEP import, 2026-11-15, found only by hand). The watch counts this thread's
    calls and returns; when the count has not moved for stall_s seconds, and the instance is neither solving nor using
    a core (a long mesh or rebuild does), it writes stall_<pid>_<time>.txt into folder: where the script stands, the
    instance's windows and dialog texts, and the end of its hidden-window log. One report per stall, one log line, and
    one line in the claims folder's runs.log (outcome "STALLED ..."), so that tools/pc/sw_watch.py finds it even when
    the job is later killed and never writes its own line. It stops nothing and changes nothing: ending a stuck instance
    stays with its owner (playbook/01-session.md). job() runs one for its instance; stall_s=0 turns it off.

    180 s: the hang it was written for never returns, the slowest call seen to sit idle and still come back is a
    launch behind a busy instance (150 s, before the job has an instance to watch), and every long call that is
    working (mesh, rebuild, solve, reading results) shows a solver process or a busy core and is passed over.
    """

    def __init__(self, pid, folder, stall_s=STALL_S, poll=5.0):
        self.pid, self.folder, self.stall_s, self.poll = pid, Path(folder), stall_s, poll
        self.n, self.reports, self._stop = 0, [], None

    def _tick(self, _frame, _event, _arg):
        self.n += 1

    def __enter__(self):
        if not self.stall_s or sys.getprofile() is not None:        # off, or the script runs its own profiler
            return self
        self.tid = threading.get_ident()
        self._stop = threading.Event()
        sys.setprofile(self._tick)
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def __exit__(self, *exc):
        if self._stop is not None:
            self._stop.set()
            if sys.getprofile() == self._tick:
                sys.setprofile(None)

    def _working(self):
        """True while the instance is solving or using more than a tenth of a core: slow, not stuck."""
        try:
            return sw_instance._solving(self.pid) or psutil.Process(self.pid).cpu_percent(interval=1.0) > 10.0
        except psutil.Error:
            return False

    def _run(self):
        seen, since, told = self.n, time.time(), False
        while not self._stop.wait(self.poll):
            try:
                if self.n != seen:
                    seen, since, told = self.n, time.time(), False
                    continue
                idle = time.time() - since
                if idle < self.stall_s or told or self._working():
                    continue
                told = True
                self._report(idle)
            except Exception as ex:      # noqa: BLE001 - the watch must never be what breaks a job
                log(f'stall watch: {str(ex)[:120]}')

    def _report(self, idle):
        frame = sys._current_frames().get(self.tid)
        stack = traceback.extract_stack(frame) if frame is not None else []
        own = [f for f in stack if 'win32com' not in f.filename and not f.filename.startswith('<')] or stack
        where = f'{Path(own[-1].filename).name}:{own[-1].lineno} {own[-1].line}' if own else '?'
        wins = sw_instance.windows(self.pid)
        try:
            with open(sw_instance.hider_log(self.pid), encoding='utf8') as f:
                hidden = f.read().splitlines()[-30:]
        except OSError:
            hidden = ['(no hidden-window log)']
        path = self.folder / f'stall_{self.pid}_{time.strftime("%Y%m%d_%H%M%S")}.txt'
        text = '\n'.join(
            [f'{time.strftime("%Y-%m-%d %H:%M:%S %z")}  no progress for {idle:.0f} s at {where}',
             f'script: {" ".join(sys.argv)}',
             f'SolidWorks pid {self.pid}: answers {sw_instance.answers(self.pid)}, not solving, under a tenth of a core',
             '', 'windows (class | title | visible | enabled | dialog texts):']
            + [f'  {c} | {t} | {v} | {e} | {k}' for c, t, v, e, k in wins]
            + ['', 'hidden-window log, newest last:'] + ['  ' + h for h in hidden]
            + ['', 'where the script stands:'] + [ln.rstrip() for ln in traceback.format_list(stack)])
        try:
            path.write_text(text + '\n', encoding='utf-8')
        except OSError as ex:
            path = f'(not written: {ex})'
        self.reports.append(str(path))
        try:                 # a job's five fields and the folder it ran in, where sw_instance.session() writes its runs
            claims = Path(sw_instance._claims().claims_dir())
            claims.mkdir(parents=True, exist_ok=True)
            with open(claims / 'runs.log', 'a', encoding='utf-8') as f:
                f.write('\t'.join([time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(time.time() - idle)), f'{idle:.0f} s',
                                   ' '.join(Path(a).name for a in sys.argv) or '-', f'pid {self.pid}',
                                   ' '.join(f'STALLED at {where}; report {path}'.split())[:300], os.getcwd()]) + '\n')
        except Exception:    # noqa: BLE001 - the report file is written; a log line must not be what fails
            pass
        dialogs = [(t, k) for c, t, _v, _e, k in wins if c == '#32770'] or 'none listed'
        disabled = any(not e for c, _t, _v, e, _k in wins if c.startswith('Afx:'))
        log(f'STALLED {idle:.0f} s at {where}; SolidWorks pid {self.pid} is idle'
            + (', its main window disabled (a modal dialog holds it)' if disabled else '')
            + f'; dialogs: {dialogs}; report: {path}')


class job:
    """with job() as j: one SolidWorks instance for one script, closed on the way out whatever happens.

    Refuses to start when the machine has less than min_free_gb free. With wait_s it keeps asking for that long first,
    both for memory and for a launch queued behind a busy instance. j.sw is the SldWorks object, j.inst the
    sw_instance.Instance (j.inst.pid for claims.py), j.simulation() loads the Simulation add-in.
    The job changes no SolidWorks setting: export() sets the export options and puts them back.
    A call that does not come back while SolidWorks sits idle is written up after stall_s seconds (stall_watch: a
    stall_<pid>_<time>.txt beside runs.log, and a "STALLED" line in the claims folder's runs.log). Nothing is stopped.
    Every job adds one line to runs.log beside the script (or in log_to): when it started, how long it ran, and
    whether it ended ok or with which error.
    """

    def __init__(self, min_free_gb=MIN_FREE_GB, visible=False, wait_s=0, log_to=None, stall_s=STALL_S):
        self.min_free_gb, self.visible, self.wait_s = min_free_gb, visible, wait_s
        self.stall_s, self.watch = stall_s, None
        self.inst = self.sw = None
        self.log_to = Path(log_to) if log_to else Path(sys.argv[0] or '.').resolve().parent
        self.t0 = time.time()

    def _record(self, outcome):
        """One line per job in <folder>/runs.log: start, seconds, script, pid, outcome. The count of failed runs before
        one worked comes from this file, not from memory. A folder that cannot be written is said and passed over."""
        try:
            with open(self.log_to / 'runs.log', 'a', encoding='utf-8') as f:
                f.write('\t'.join([time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(self.t0)),
                                   f'{time.time() - self.t0:.0f} s', ' '.join(Path(a).name for a in sys.argv) or '-',
                                   f'pid {self.inst.pid if self.inst else "-"}',
                                   ' '.join(str(outcome).split())[:300]]) + '\n')
        except OSError as ex:
            log(f'runs.log not written in {self.log_to}: {ex}')

    def __enter__(self):
        end = time.time() + self.wait_s
        while free_gb() < self.min_free_gb:      # other jobs finish and hand memory back: a short dip is a queue too
            if time.time() >= end:
                raise Failed(f'only {free_gb():.1f} GB free, under the {self.min_free_gb} GB floor: wait, do not '
                             'launch (job(wait_s=...) waits for you)')
            log(f'launch is waiting for memory: {free_gb():.1f} GB free, floor {self.min_free_gb} GB')
            time.sleep(min(20, max(0.0, end - time.time())))
        while True:
            try:
                self.inst = launch(visible=self.visible)
                break
            except RuntimeError as ex:
                # another instance is solving and cannot answer: that is a queue, not a fault. With wait_s the job
                # keeps asking until the time is up; without it the first refusal is raised as before.
                if 'did not answer' not in str(ex) or time.time() >= end:
                    raise
                log('launch is waiting behind a busy instance:', str(ex)[:120])
                time.sleep(20)
        self.sw = self.inst.sw
        log('SolidWorks pid', self.inst.pid, 'free GB', round(free_gb(), 1))
        self.watch = stall_watch(self.inst.pid, self.log_to, self.stall_s).__enter__()
        return self

    def simulation(self):
        return self.inst.load_simulation()

    def __exit__(self, et, ev, tb):
        if self.watch is not None:       # before the close: a slow exit is not a stall
            self.watch.__exit__(et, ev, tb)
        self._record('ok' if et is None else f'FAILED {et.__name__}: {ev}')
        log('closing pid', self.inst.pid, 'committed MB', self._private())
        self.inst.close()

    def _private(self):
        try:
            return self.inst.private_mb()
        except psutil.Error:
            return '?'


# ---- documents ---------------------------------------------------------------------------------------------------------

EXPORT_TOGGLES = {69: True, 71: True}               # swSTLBinaryFormat, swSTLDontTranslateToPositive
EXPORT_INTS = {211: 0, 78: 2, 75: 203}              # swExportStlUnits = mm, swSTLQuality = Fine, swStepAP = AP203


@contextlib.contextmanager
def export_prefs(sw):
    """Set the STL and STEP options for one export, then put back what the machine had.

    They are per-user SolidWorks settings, not part of a part, and SolidWorks writes them to the registry when it
    closes: left set, a script would change every later session on the PC, the person's own included. Binary STL in
    mm, quality Fine, kept in the model frame (no shift to positive space), STEP AP203 (cad.md section 9).
    """
    was_t = {k: sw.GetUserPreferenceToggle(k) for k in EXPORT_TOGGLES}
    was_i = {k: sw.GetUserPreferenceIntegerValue(k) for k in EXPORT_INTS}
    try:
        for k, v in EXPORT_TOGGLES.items():
            sw.SetUserPreferenceToggle(k, v)
        for k, v in EXPORT_INTS.items():
            sw.SetUserPreferenceIntegerValue(k, v)
        yield
    finally:
        for k, v in was_t.items():
            sw.SetUserPreferenceToggle(k, bool(v))
        for k, v in was_i.items():
            sw.SetUserPreferenceIntegerValue(k, int(v))


def part_template(sw):
    """The part template: SolidWorks' default if one is set, else SW_PART_TEMPLATE, else the first installed .prtdot."""
    t = sw.GetUserPreferenceStringValue(8) or os.environ.get('SW_PART_TEMPLATE', '')      # 8 = swDefaultTemplatePart
    if t and os.path.exists(t):
        return t
    found = sorted(Path(r'C:\ProgramData\SOLIDWORKS').glob('SOLIDWORKS 20*/templates/**/*.prtdot'))
    if not found:
        raise Failed('no part template: set SW_PART_TEMPLATE to a .prtdot file')
    return str(found[-1])


def new_part(sw, path):
    """A new empty part in MMGS units, saved at path at once (an unsaved document is lost with the instance)."""
    sw.CloseAllDocuments(True)       # a failed earlier build leaves its part open, and NewDocument then throws
    d = sw.NewDocument(part_template(sw), 0, 0, 0)
    if d is None:
        raise Failed('NewDocument returned nothing')
    d.Extension.SetUserPreferenceInteger(263, 0, 5)      # swUnitSystem = MMGS, whatever the template says
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    save_as(d, path)
    return d


def open_doc(sw, path, kind=PART):
    """Open a part (or assembly) silently and make it the active document."""
    e, w = L(), L()
    d = sw.OpenDoc6(str(path), kind, 1, '', e, w)        # 1 = swOpenDocOptions_Silent
    if d is None:
        raise Failed(f'open failed: {path} errors {e.value} warnings {w.value}')
    sw.ActivateDoc3(d.GetTitle, False, 0, L())
    return d


def save(d):
    """Rebuild and save in place. Call it after every step that worked (RULES.md rule 5)."""
    d.ForceRebuild3(False)
    e, w = L(), L()
    if not d.Save3(1, e, w):                             # 1 = swSaveAsOptions_Silent
        raise Failed(f'save failed: {d.GetPathName} errors {e.value} warnings {w.value}')


def save_as(d, path):
    e, w = L(), L()
    ok = d.Extension.SaveAs(str(path), 0, 1, NUL, e, w)
    if not ok or not os.path.exists(path) or os.path.getsize(path) == 0:
        raise Failed(f'save as failed: {path} errors {e.value} warnings {w.value}')


def export(sw, d, path):
    """Export the part to .step or .stl by its extension, with the house options (put back afterwards), and check the file landed."""
    d.ForceRebuild3(False)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    with export_prefs(sw):
        save_as(d, path)
    log('exported', path, os.path.getsize(path), 'bytes')


def close(sw, d):
    sw.CloseDoc(d.GetTitle)


def import_step(sw, step, target):
    """Import a STEP file and save it as a native part or assembly at target (extension chosen by what came in)."""
    if close_welcome(int(sw.GetProcessID)):         # still open, it holds LoadFile4 for ever (it can come up after launch)
        time.sleep(1)
    data = sw.GetImportFileData(str(step))
    e = L()
    d = sw.LoadFile4(str(step), 'r', data, e)
    if d is None:
        raise Failed(f'import failed: {step} error {e.value}')
    target = Path(target).with_suffix('.SLDASM' if d.GetType == ASSEMBLY else '.SLDPRT')
    save_as(d, target)
    return d, target


# ---- measuring: the check after every feature --------------------------------------------------------------------------

def solid_bodies(d):
    return list(d.GetBodies2(0, True) or [])             # 0 = swSolidBody, visible only


def volume(d):
    """Total solid volume in mm3."""
    return sum(b.GetMassProperties(1000.0)[3] for b in solid_bodies(d)) * 1e9


def bodies(d):
    """[(name, volume mm3, [x0, y0, z0, x1, y1, z1] mm)] for every solid body."""
    return [(b.Name, round(b.GetMassProperties(1000.0)[3] * 1e9, 2), [round(v * 1e3, 3) for v in b.GetBodyBox()])
            for b in solid_bodies(d)]


def bbox(d):
    """[x0, y0, z0, x1, y1, z1] in mm over all solid bodies."""
    bs = np.array([b[2] for b in bodies(d)])
    return [float(v) for v in bs[:, :3].min(axis=0)] + [float(v) for v in bs[:, 3:].max(axis=0)]


def state(d):
    """What the model is now: dict(volume_mm3, bodies, box [x0, y0, z0, x1, y1, z1] mm or None, errors).

    errors is feature_errors(d). Every feature helper logs this line after it has built and keeps it in swkit.last,
    so a script's log shows the measured part after each step whether or not the script asked."""
    bs = bodies(d)
    return dict(volume_mm3=round(sum(b[1] for b in bs), 2), bodies=len(bs),
                box=[round(v, 3) for v in bbox(d)] if bs else None, errors=feature_errors(d))


last = {}        # the state after the newest feature: dict(feature=name, **state(d))


def _after(d, name):
    """Log the measured part after a feature and keep it in swkit.last. Measuring never fails the feature."""
    global last
    try:
        st = state(d)
    except Exception as ex:      # noqa: BLE001 - the feature built; a measurement that cannot be read is said, not raised
        log(f'{name}: built, but the part could not be measured afterwards ({str(ex)[:100]})')
        return None
    last = dict(feature=name, **st)
    log(f'{name}: part is now {st["volume_mm3"]:.2f} mm3, box {st["box"]}, {st["bodies"]} '
        f'{"body" if st["bodies"] == 1 else "bodies"}' + (f', REBUILD ERRORS {st["errors"]}' if st['errors'] else ''))
    return st


def expect(what, got, want, tol, abs_tol=0.0):
    """Stop unless got is within tol of want: relative when 0 < tol < 1 and want is not zero, else absolute.

    A want that is zero to within 1e-9 counts as zero, so tol is then absolute (a coordinate that should be 0 comes
    back as 6e-17, and one per cent of that allows nothing). abs_tol is a floor under the allowance, for small
    targets: expect(..., want=0.02, tol=0.05, abs_tol=0.01) allows 0.01, not 0.001. A got that is not a number fails.
    """
    err = abs(got - want)
    lim = max(tol * abs(want), abs_tol) if 0 < tol < 1 and abs(want) > 1e-9 else max(tol, abs_tol)
    if not err <= lim:                                   # written this way round so that nan fails
        raise Failed(f'{what}: got {got:.4f}, expected {want:.4f} (off by {err:.4g}, allowed {lim:.4g})')
    log(f'ok {what}: {got:.4f} (expected {want:.4f})')


def stamp(folder, label):
    """Write the time and a label to <folder>/times.log and return the minutes since the first line in it.

    A job spread over several scripts has no clock of its own, and a session's sense of how long it has been is not
    one: four benchmark runs of twenty minutes reported up to eighty-four. Call it at the start and end of every
    task; quote times in a report from times.log, never from memory. The clock starts at the first call in that
    folder and runs on across scripts, so give each job a folder of its own: in a folder an earlier job used, it
    goes on counting from that job's start. A line is: seconds since 1970, local time, minutes since the first
    line, label, with tabs between.
    """
    path = Path(folder) / 'times.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    first = float(lines[0].split('\t')[0]) if lines else now
    mins = (now - first) / 60
    label = ' '.join(str(label).split())                 # one line each: no tab or line break from the label
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'{now:.3f}\t{time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(now))}\t'
                f'{mins:.1f} min\t{label}\n')
    log(f'clock: {label}: {mins:.1f} min since the job began')
    return mins


def set_dim(d, feat_name, old_mm, new_mm):
    """Change the one driving dimension of an existing feature that now reads old_mm to new_mm; rebuild afterwards.

    Tried by name first (D1@<feature>), then over the feature's display dimensions. The value it reads now must be
    old_mm, so a wrong dimension cannot be changed by mistake. Returns the dimension's full name.
    Measured on six plates, benchmark run fable-d, 2026-11-13."""
    f = d.FeatureByName(feat_name)
    if f is None:
        raise Failed(f'no feature {feat_name}')
    found, seen = [], []
    dim = d.Parameter(f'D1@{feat_name}')
    if dim is not None:
        found.append(dim)
    else:
        dd = call(f, 'GetFirstDisplayDimension')
        while dd is not None:
            found.append(dd.GetDimension2(0))
            dd = f.GetNextDisplayDimension(dd)
    for dim in found:
        val = dim.SystemValue * 1e3
        seen.append((dim.FullName, round(val, 4)))
        if abs(val - old_mm) < 1e-6:
            try:
                dim.SystemValue = new_mm / 1e3
            except Exception as ex:      # noqa: BLE001 - logged, and the other documented call is tried
                log(f'{feat_name}: SystemValue could not be set ({str(ex)[:80]}); trying SetSystemValue3')
                dim.SetSystemValue3(new_mm / 1e3, 2, NUL)        # 2 = all configurations
            if abs(dim.SystemValue * 1e3 - new_mm) > 1e-6:
                raise Failed(f'{feat_name}: dimension {dim.FullName} did not take {new_mm}')
            log(f'{feat_name}: {dim.FullName} {old_mm} -> {new_mm}')
            return dim.FullName
    raise Failed(f'{feat_name}: no dimension reads {old_mm}; it has {seen}')


def redraw_circles(d, sketch_name, pts, r):
    """Edit an existing sketch in place: delete what it holds and draw circles of radius r at pts (model mm, on the
    sketch plane). Rebuild afterwards, then check feature_errors() and the volume. Returns how many segments went."""
    d.ClearSelection2(True)
    sk = d.FeatureByName(sketch_name)
    if sk is None or not sk.Select2(False, 0):
        raise Failed(f'no sketch {sketch_name}')
    d.EditSketch()
    act = d.GetActiveSketch2
    T = act.ModelToSketchTransform.ArrayData
    segs = call(act, 'GetSketchSegments') or []
    d.ClearSelection2(True)
    for seg in segs:
        seg.Select4(True, NUL)
    d.EditDelete()
    d.SketchManager.AddToDB = True
    try:
        for x, y, z in pts:
            x, y, z = x / 1e3, y / 1e3, z / 1e3
            u, v = x * T[0] + y * T[3] + z * T[6] + T[9], x * T[1] + y * T[4] + z * T[7] + T[10]
            if abs(x * T[2] + y * T[5] + z * T[8] + T[11]) > 1e-9:
                raise Failed(f'{sketch_name}: point off the sketch plane')
            if d.SketchManager.CreateCircleByRadius(u, v, 0, r / 1e3) is None:
                raise Failed(f'{sketch_name}: circle not drawn')
    finally:
        d.SketchManager.AddToDB = False
        d.InsertSketch2(True)
    log(f'{sketch_name}: {len(segs)} segments deleted, {len(pts)} circles drawn')
    return len(segs)


def feature_errors(d):
    """[(feature name, error code)] for features that failed to rebuild or carry a warning. Empty means a clean tree.

    GetErrorCode2 needs its by-reference "is a warning" flag: without it the call raises "Parameter not optional" for
    every feature, which an earlier version of this helper swallowed and so always reported a clean tree (2026-11-12).
    A cut whose sketch no longer meets the body reports 71.
    """
    out = []
    f = d.FirstFeature
    while f is not None:
        code = f.GetErrorCode2(VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False))
        code = code[0] if isinstance(code, tuple) else code
        if code:
            out.append((f.Name, int(code)))
        f = f.GetNextFeature
    return out


# ---- planes and sketches -----------------------------------------------------------------------------------------------

def plane(d, axis, off, name):
    """The plane normal to model axis 'X', 'Y' or 'Z' at that coordinate (mm). Offset 0 returns the base plane."""
    base = d.FeatureByName(BASE[axis])
    if base is None:
        raise Failed(f'no "{BASE[axis]}" in this part (a template in another language renames the base planes)')
    if abs(off) < 1e-9:
        return base
    d.ClearSelection2(True)
    base.Select2(False, 0)
    p = d.FeatureManager.InsertRefPlane(8 + (256 if off < 0 else 0), abs(off) * m, 0, 0, 0, 0)      # 8 distance, 256 flip
    if p is None:
        raise Failed('plane failed: ' + name)
    p.Name = name
    return p


class Sk:
    """with Sk(d, plane, name) as s: draw with 3D model points in mm; they are mapped into the sketch for you.

    The points go through the sketch's own ModelToSketchTransform, so it never matters which way a plane's sketch axes
    point or whether the plane was flipped. A point that does not lie on the sketch plane raises: that is the plane at
    the wrong offset, caught before it becomes a feature in the wrong place. s.feat is the finished sketch.
    """

    def __init__(self, d, pl, name):
        self.d, self.pl, self.name = d, pl, name

    def __enter__(self):
        d = self.d
        d.ClearSelection2(True)
        self.pl.Select2(False, 0)
        d.SketchManager.InsertSketch(True)
        sk = d.GetActiveSketch2
        if sk is None:
            raise Failed('sketch did not open: ' + self.name)
        self.T = sk.ModelToSketchTransform.ArrayData
        d.SketchManager.AddToDB = True       # straight to the database: no snapping or inferred relations to move points
        return self

    def p(self, q):
        T = self.T
        x, y, z = q[0] * m, q[1] * m, q[2] * m
        w = x * T[2] + y * T[5] + z * T[8] + T[11]
        if abs(w) > 1e-6:
            raise Failed(f'{self.name}: point {tuple(q)} is {abs(w) / m:.4f} mm off the sketch plane')
        return x * T[0] + y * T[3] + z * T[6] + T[9], x * T[1] + y * T[4] + z * T[7] + T[10]

    def poly(self, pts, closed=True):
        P = [self.p(q) for q in pts]
        for a, b in zip(P, (P[1:] + P[:1]) if closed else P[1:]):
            if self.d.SketchManager.CreateLine(a[0], a[1], 0, b[0], b[1], 0) is None:
                raise Failed(f'{self.name}: line not drawn (two points closer than 1e-5 mm?)')

    def rect(self, a, b):
        """Axis-aligned rectangle between opposite corners a and b, which must lie on the sketch plane."""
        k = [i for i in range(3) if abs(a[i] - b[i]) > 1e-9]
        if len(k) != 2:
            raise Failed(f'{self.name}: rect corners must differ in exactly two coordinates')
        c, e = list(a), list(a)
        c[k[0]], e[k[1]] = b[k[0]], b[k[1]]
        self.poly([a, c, b, e])

    def circle(self, c, r):
        a = self.p(c)
        if self.d.SketchManager.CreateCircleByRadius(a[0], a[1], 0, r * m) is None:
            raise Failed(f'{self.name}: circle not drawn')

    def arc(self, c, p0, p1, direction):
        """Arc about centre c from p0 to p1. direction +1 is counter-clockwise seen in the sketch's own axes, which may be
        mirrored against the model's: give the feature its expect_dv, and flip the sign if the volume is wrong."""
        a, b, e = self.p(c), self.p(p0), self.p(p1)
        self.d.SketchManager.CreateArc(a[0], a[1], 0, b[0], b[1], 0, e[0], e[1], 0, direction)

    def spline(self, pts, closed=True):
        arr = []
        for q in list(pts) + (list(pts[:1]) if closed else []):
            u, v = self.p(q)
            arr += [u, v, 0.0]
        if self.d.SketchManager.CreateSpline2(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, arr), True) is None:
            raise Failed(f'{self.name}: spline not drawn')

    def centerline(self, a, b):
        """The axis for a revolve."""
        p, q = self.p(a), self.p(b)
        self.d.SketchManager.CreateCenterLine(p[0], p[1], 0, q[0], q[1], 0)

    def __exit__(self, et, ev, tb):
        self.d.SketchManager.AddToDB = False
        self.d.InsertSketch2(True)
        if et is None:
            self.feat = self.d.FeatureByPositionReverse(0)
            self.feat.Name = self.name + '_SK'


# ---- features ----------------------------------------------------------------------------------------------------------

def extrude(d, sk, name, depth, cut=False, mode=BLIND, want=None, min_dv=1.0, expect_dv=None):
    """Extrude a sketch (cut=True removes material) and check what it did.

    mode MID extrudes depth in total, half each side of the sketch plane: nothing to get backwards, so put the sketch
    plane at the middle of the feature whenever you can. BLIND goes depth one way; THRU_ALL cuts one way, and both ways are tried until the volume moves the right way.
    For BLIND and UP_TO_NEXT both directions are tried, and want = (axis index 0/1/2, sign, plane coordinate mm) keeps
    the one whose new faces lie on that side of the sketch plane.
    Raises unless the volume changed by more than min_dv mm3 the right way, and, when expect_dv is given, by that
    amount within 1 %.
    """
    fm = d.FeatureManager
    dep = abs(depth) * m
    for rev in ((False,) if mode == MID else (False, True)):
        v0 = volume(d)
        d.ClearSelection2(True)
        sk.Select2(False, 0)
        if cut:
            f = fm.FeatureCut4(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False, False, False,
                               False, False, False, True, False, False, False, 0, 0, False, False)
        else:
            f = fm.FeatureExtrusion3(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False, False,
                                     False, False, True, False, True, 0, 0, False)
            if f is None:      # auto-select merge fails on some multi-body states; feature scope without it works
                d.ClearSelection2(True)
                sk.Select2(False, 0)
                f = fm.FeatureExtrusion3(True, False, rev, mode, 0, dep, dep, False, False, False, False, 0, 0, False,
                                         False, False, False, True, True, False, 0, 0, False)
        if f is None:
            continue
        d.ForceRebuild3(False)
        dv = (v0 - volume(d)) if cut else (volume(d) - v0)
        ok = dv > min_dv
        if ok and want is not None:
            ax, sign, c0 = want
            vals = []
            for fc in (call(f, 'GetFaces') or []):
                b = call(fc, 'GetBox')
                vals += [b[ax] * 1e3, b[ax + 3] * 1e3]
            ok = bool(vals) and (sum(vals) / len(vals) - c0) * sign > 0
        if ok:
            if expect_dv is not None:
                expect(name + ' volume change', dv, expect_dv, 0.01)
            f.Name = name
            log(f'{name}: {"cut" if cut else "added"} {dv:.2f} mm3')
            _after(d, name)
            return f
        d.EditUndo2(1)
    raise Failed(f'{name}: no {"cut" if cut else "extrude"} changed the volume the right way '
                 '(open sketch? sketch off the body? wrong side?)',
                 try_='draw the sketch again and check it is one closed loop; for a cut, check with bbox(d) that the '
                      'sketch lies over the body; for BLIND give want=(axis, sign, plane coordinate)',
                 stop='the same sketch has failed twice with a closed loop over the body: build the shape another way '
                      '(MID from a plane at its middle, or cut_half_space)')


def revolve(d, sk, name, cut=False, angle=360.0, mid=False, min_dv=1.0, expect_dv=None):
    """Revolve a closed profile about the centreline drawn in the same sketch (Sk.centerline)."""
    v0 = volume(d)
    d.ClearSelection2(True)
    sk.Select2(False, 0)
    f = d.FeatureManager.FeatureRevolve2(True, True, False, cut, False, False, 6 if mid else 0, 0, math.radians(angle),
                                         0, False, False, 0, 0, 0, 0, 0, True, False, True)
    d.ForceRebuild3(False)
    dv = (v0 - volume(d)) if cut else (volume(d) - v0)
    if f is None or dv < min_dv:
        raise Failed(f'{name}: revolve failed (profile open, or crossing its centreline?)',
                     try_='keep every profile point on one side of the centreline (a point on it is fine), close the '
                          'loop, and draw exactly one centerline in the sketch',
                     stop='a closed profile on one side of its centreline has failed twice: split it into two revolves')
    if expect_dv is not None:
        expect(name + ' volume change', dv, expect_dv, 0.01)
    f.Name = name
    log(f'{name}: {"cut" if cut else "added"} {dv:.2f} mm3')
    _after(d, name)
    return f


def loft(d, sketches, name, at=None):
    """Loft through closed section sketches, in order. Tries with and without merging into the existing body.

    at: one model point (x, y, z in mm) per sketch, ON that section's outline, the same corner of every section (all
    the lowest points, say). SolidWorks joins the sections where they were picked; picked nowhere it chooses for
    itself, and where its choice changes from one section to the next the loft is twisted and pinched there. Give
    `at` for any loft of more than two sections, then check the export with sheet.loft_twist(): if it still reads
    twisted, pick another corner."""
    v0 = volume(d)
    if at is not None and len(at) != len(sketches):
        raise Failed(f'{name}: {len(sketches)} sketches but {len(at)} pick points')
    for merge in (True, False):
        d.ClearSelection2(True)
        for n, k in enumerate(sketches):
            if at is not None:
                p = at[n]
                if d.Extension.SelectByID2(k.Name, 'SKETCH', p[0] / 1000.0, p[1] / 1000.0, p[2] / 1000.0, True, 1, NUL, 0):
                    continue
                log(f'{name}: section {k.Name} was not selected at {p}; selected without a point')
            k.Select2(True, 1)
        f = d.FeatureManager.InsertProtrusionBlend2(False, True, False, 1.0, 0, 0, 1.0, 1.0, True, True, False, 0, 0, 0,
                                                    True, merge, merge, 0)
        if f is not None:
            d.ForceRebuild3(False)
            f.Name = name
            log(f'{name}: added {volume(d) - v0:.2f} mm3 (merge {merge})')
            _after(d, name)
            return f
    raise Failed(name + ': loft failed (sections must be closed, and their start points roughly in line)',
                 try_='give every section the same number of points starting at the same side, in the same turning '
                      'direction; then loft the sections two at a time to find the pair that refuses',
                 stop='one pair of neighbouring sections refuses after its start points are in line: put a section '
                      'between them, or end the loft there and start a second one')


def offset_loop(pts, off):
    """A closed flat outline moved outwards by off mm in its own plane, point for point (inwards when off is negative).

    Each point moves square to the line through its two neighbours, so the count and the start point stay the same and
    the result lofts against the original. For smooth outlines; off must stay well under the tightest radius."""
    P = np.array(pts, float)
    c = P.mean(axis=0)
    nrm = sum(np.cross(P[i] - c, P[(i + 1) % len(P)] - c) for i in range(len(P)))
    nrm = nrm / np.linalg.norm(nrm)
    out = []
    for i in range(len(P)):
        o = np.cross(P[(i + 1) % len(P)] - P[i - 1], nrm)
        out.append(tuple(float(v) for v in P[i] + off * o / np.linalg.norm(o)))
    return out


def skirt(d, outline, axis, at, radius, name, side=+1, steps=5, sink=0.15):
    """Round a lofted stem into the flat face it stands on, with a small second loft laid over the junction.

    Use it where fillet() on the seam is not to be trusted or returns nothing. outline(c) -> the stem's closed outline as
    3D points in the plane axis = c (the function its own sections were drawn from; same count and start point at
    every height). The face is the plane axis = at and the stem rises towards side (+1 or -1) along that axis. The
    skirt's sections follow a quarter circle of the given radius: the first lies in the face, radius wider than the
    stem all round, and the last sits `sink` mm inside the stem at height radius, so no two faces coincide. It leaves
    a crease of a few degrees where it sinks into the stem and meets the face at a shallow angle, not at a tangent.
    Raises unless it added volume, left the body count alone and rebuilt clean. Needs `radius` of room on the face all
    round. Measured: playbook/03-modelling.md, eval/loft-blend.
    """
    v0, n0 = volume(d), len(solid_bodies(d))
    sks = []
    for k in range(steps):
        phi = math.radians(90.0 * k / (steps - 1))
        c = at + side * radius * (1 - math.cos(phi))
        off = radius * (1 - math.sin(phi)) if k < steps - 1 else -sink
        with Sk(d, plane(d, axis, c, f'{name}_P{k}'), f'{name}_S{k}') as s:
            s.spline(offset_loop(outline(c), off))
        sks.append(s.feat)
    f = loft(d, sks, name)
    dv, errs = volume(d) - v0, feature_errors(d)
    if dv <= 0 or len(solid_bodies(d)) != n0 or errs:
        raise Failed(f'{name}: skirt added {dv:.2f} mm3, bodies {n0} -> {len(solid_bodies(d))}, errors {errs}')
    return f


def shell(d, open_face_points, t, name):
    """Shell to wall thickness t mm, removing the faces at the given 3D points (each must lie on exactly one face).

    The faces are found by geometry and selected as objects: SelectByID2 by coordinates found nothing on a hidden
    instance (2026-11-12). With no points the part is hollowed with no opening.
    """
    hit = [pick(d, at=p) for p in open_face_points]
    if any(len(h) != 1 for h in hit):
        raise Failed(f'{name}: each point must lie on exactly one face; faces found {[len(h) for h in hit]} at '
                     f'{list(open_face_points)} (a point on an edge lies on two)')
    d.ClearSelection2(True)
    for h in hit:
        if not h[0].Select4(True, NUL):
            raise Failed(f'{name}: face not selected')
    v0 = volume(d)
    d.InsertFeatureShell(t * m, False)
    d.ForceRebuild3(False)
    f = d.FeatureByPositionReverse(0)
    if f is None or f.GetTypeName2 != 'Shell' or v0 - volume(d) < 1.0:
        raise Failed(f'{name}: shell failed (wall thicker than a local radius or a thin region?)')
    f.Name = name
    log(f'{name}: {t} mm wall, volume {volume(d):.1f} mm3')
    _after(d, name)
    return f


def edges_where(d, test):
    """Edges whose start, middle and end points (mm) all pass test(p). Select by where an edge IS, never by its name."""
    out = []
    for b in solid_bodies(d):
        for e in (call(b, 'GetEdges') or []):
            cp = e.GetCurveParams3
            mid = e.GetCurve.Evaluate2((cp.UMinValue + cp.UMaxValue) / 2, 0)
            pts = [np.array(cp.StartPoint[:3]) * 1e3, np.array(list(mid)[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3]
            if all(test(p) for p in pts):
                out.append(e)
    return out


def edge_info(e):
    """dict(length mm, start, mid, end as [x, y, z] mm, straight True/False) for one edge.

    The length is measured along 16 chords, so a full circle reads 0.6 % short. start and end are equal on a closed
    edge."""
    cp = e.GetCurveParams3
    u0, u1 = cp.UMinValue, cp.UMaxValue
    cv = e.GetCurve
    pts = np.array([list(cv.Evaluate2(u0 + (u1 - u0) * k / 16, 0))[:3] for k in range(17)]) * 1e3
    length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    chord = float(np.linalg.norm(pts[-1] - pts[0]))
    return dict(length=length, start=pts[0].tolist(), mid=pts[8].tolist(), end=pts[-1].tolist(),
                straight=bool(length > 1e-9 and abs(length - chord) < 1e-6 * max(length, 1.0)))


def edges_of(face_list):
    """The edges round the given faces, each once: the outline of a face found with pick() or side().

    edges_of(side(d, '+z')) is the rim of the top face. An edge shared by two of the faces comes back once."""
    out, seen = [], set()
    for f in face_list:
        for e in (call(f, 'GetEdges') or []):
            i = edge_info(e)
            key = tuple(round(v, 3) for v in sorted([i['start'], i['end']])[0] + sorted([i['start'], i['end']])[1] + i['mid'])
            if key not in seen:
                seen.add(key)
                out.append(e)
    return out


def edges_along(d, axis, inside=None, tol=0.02):
    """Straight edges that run along model axis 'X', 'Y' or 'Z', optionally only those lying within the box
    inside = [x0, y0, z0, x1, y1, z1] (mm). edges_along(d, 'Z') on a plate is its vertical corner edges."""
    k = 'XYZ'.index(axis.upper())
    out = []
    for b in solid_bodies(d):
        for e in (call(b, 'GetEdges') or []):
            i = edge_info(e)
            if not i['straight']:
                continue
            a, c = np.array(i['start']), np.array(i['end'])
            if max(abs(a[j] - c[j]) for j in range(3) if j != k) > tol:
                continue
            if inside is not None and not all(inside[j] - tol <= p[j] <= inside[j + 3] + tol for p in (a, c) for j in range(3)):
                continue
            out.append(e)
    return out


def fillet(d, edges, radii, name):
    """Round the edges with the first radius in radii (mm) that builds; returns that radius, or None if none did.

    Edge objects go stale once any feature is added: find them (edges_where) straight before this call.
    """
    if not edges:
        raise Failed(name + ': no edges to round (the edge test matched nothing)')
    # measured before the first attempt: after a refused round, edge_info on the same edges raised "disconnected from
    # its clients" (2026-11-14), though the edges could still be selected. Seventeen calls an edge, so not for huge sets
    info, why = None, f'{len(edges)} edges are too many to measure'
    if len(edges) <= 300:
        try:
            info = sorted((edge_info(e) for e in edges), key=lambda i: i['length'])
        except Exception as ex:      # noqa: BLE001 - only the explanation of a refusal needs them
            why = str(ex)[:100]
    for r in radii:
        v0 = volume(d)
        d.ClearSelection2(True)
        for e in edges:
            e.Select4(True, NUL)
        f = d.FeatureManager.FeatureFillet3(3, r * m, 0, 0, 0, 0, 0, NUL, NUL, NUL, NUL, NUL, NUL, NUL)
        if f is not None:
            d.ForceRebuild3(False)
            f.Name = name
            log(f'{name}: R{r} on {len(edges)} edges, volume change {volume(d) - v0:+.2f} mm3')
            _after(d, name)
            return r
    log(f'{name}: no round built on {len(edges)} edges at {tuple(radii)}')
    if info is None:
        log(f'{name}: the edges could not be measured ({why})')
    else:
        short = [i for i in info if i['length'] < min(radii)]
        log(f'{name}: the edges, shortest first (length mm, middle): '
            + '; '.join(f'{i["length"]:.2f} at {[round(v, 2) for v in i["mid"]]}' for i in info[:8])
            + (f'; and {len(info) - 8} more' if len(info) > 8 else ''))
        if short:
            log(f'{name}: {len(short)} of them are shorter than the smallest radius tried ({min(radii)} mm): an edge '
                'shorter than the round is the usual refusal. Leave those out, or remove the cause (a parent round '
                'drawn as a polyline makes slivers: playbook/03-modelling.md)')
        else:
            log(f'{name}: none is shorter than the radius, so look at what the round would run into: a neighbouring '
                'face narrower than the radius, or a round already there. Try the edges one at a time')
    return None


def chamfer(d, edges, width, name, angle=45.0):
    if not edges:
        raise Failed(name + ': no edges to chamfer')
    d.ClearSelection2(True)
    for e in edges:
        e.Select4(True, NUL)
    f = d.FeatureManager.InsertFeatureChamfer(0, 1, width * m, math.radians(angle), 0, 0, 0, 0)
    d.ForceRebuild3(False)
    if f is None:
        raise Failed(name + ': chamfer failed')
    f.Name = name
    _after(d, name)
    return f


def cut_half_space(d, axis, at, keep_sign, name, span=400.0, min_dv=1.0):
    """Remove everything on the far side of the plane axis = at; keep_sign +1 keeps the side with larger coordinates.

    min_dv: the smallest volume in mm3 the cut must remove (lower it to trim a sliver)."""
    c = at - keep_sign * span / 2
    i = 'XYZ'.index(axis)
    a, b = [-span] * 3, [span] * 3
    a[i] = b[i] = c
    with Sk(d, plane(d, axis, c, name + '_P'), name) as s:
        s.rect(a, b)
    return extrude(d, s.feat, name, span, cut=True, mode=MID, min_dv=min_dv)


def insert_body(d, part_path):
    """Bring another part's solid in as an extra body, at the same coordinates (multi-body models for contact FEA).

    The body stays separate even where it overlaps one already there (measured 2026-11-12), so nothing here tells you
    about an overlap: check for it yourself. The part must hold exactly one solid body.
    """
    n0 = len(solid_bodies(d))
    f = d.InsertPart3(str(part_path), 1, '')       # 1 = swInsertPartImportSolids
    d.ForceRebuild3(False)
    if f is None or len(solid_bodies(d)) != n0 + 1:
        raise Failed(f'{part_path} did not come in as its own body (bodies {bodies(d)})')
    _after(d, 'insert ' + Path(str(part_path)).name)
    return f


def delete_body(d, name):
    d.ClearSelection2(True)
    if not d.Extension.SelectByID2(name, 'SOLIDBODY', 0, 0, 0, False, 0, NUL, 0):
        raise Failed('no body ' + name)
    f = d.FeatureManager.InsertDeleteBody2(False)
    d.ForceRebuild3(False)
    return f


def single_body(d, crumb_mm3=0.2):
    """Delete crumbs under crumb_mm3 and stop unless exactly one solid body is left: the state every print part must be in."""
    for b in bodies(d):
        if b[1] < crumb_mm3:
            delete_body(d, b[0])
    if len(bodies(d)) != 1:
        raise Failed(f'expected one body, got {bodies(d)}')


# ---- faces: pick by geometry -------------------------------------------------------------------------------------------

def faces(d):
    return [f for b in solid_bodies(d) for f in (call(b, 'GetFaces') or [])]


def face_info(f):
    """dict(kind 'cyl' | 'plane' | 'other', r mm or None, normal or None, box [lo xyz, hi xyz] mm, area mm2)."""
    s = f.GetSurface
    x = [v * 1e3 for v in call(f, 'GetBox')]
    box = [min(x[i], x[i + 3]) for i in range(3)] + [max(x[i], x[i + 3]) for i in range(3)]
    kind, r, n = 'other', None, None
    if s.IsCylinder:
        kind, r = 'cyl', s.CylinderParams[6] * 1e3
    elif s.IsPlane:
        kind, n = 'plane', [round(v, 4) for v in f.Normal]
    return dict(kind=kind, r=r, normal=n, box=box, area=call(f, 'GetArea') * 1e6)


def pick(d, kind=None, r=None, inside=None, normal=None, at=None, area=None, tol=0.02):
    """Faces matching every given filter. Stop and print list_faces(d) if a pick returns the wrong count.

    kind 'cyl' or 'plane'; r: cylinder radius mm (within tol); inside: [x0, y0, z0, x1, y1, z1] the face's box must lie
    within; normal: (nx, ny, nz) of a planar face (within 0.01); at: a point (mm) that must lie on the face (0.05 mm);
    area: mm2, within 5 %.
    """
    out = []
    for f in faces(d):
        i = face_info(f)
        if kind and i['kind'] != kind:
            continue
        if r is not None and (i['r'] is None or abs(i['r'] - r) > tol):
            continue
        if inside is not None and not all(i['box'][k] >= inside[k] - tol and i['box'][k + 3] <= inside[k + 3] + tol for k in range(3)):
            continue
        if normal is not None and (i['normal'] is None or max(abs(a - b) for a, b in zip(i['normal'], normal)) > 0.01):
            continue
        if area is not None and abs(i['area'] - area) > 0.05 * area:
            continue
        if at is not None:
            q = f.GetClosestPointOn(at[0] * m, at[1] * m, at[2] * m)
            if q is None or math.dist([v * 1e3 for v in list(q)[:3]], at) > 0.05:
                continue
        out.append(f)
    return out


def list_faces(d, limit=200):
    """Print every face's kind, radius or normal, area and box: how to find out what a pick should ask for."""
    for k, f in enumerate(faces(d)[:limit]):
        i = face_info(f)
        print(k, i['kind'], 'r' if i['r'] is not None else 'n', round(i['r'], 3) if i['r'] is not None else i['normal'],
              'area', round(i['area'], 2), 'box', [round(v, 2) for v in i['box']], flush=True)


def side(d, where, tol=0.02):
    """The flat faces on one side of the part: where is '+x', '-x', '+y', '-y', '+z' or '-z'.

    Returns the planar faces whose normal points that way and which lie on that end of the part's box, so '+z' is the
    top however the part was built and whatever its features are called. A part whose top is not flat returns nothing:
    then use pick() with a box. Check the count like any pick, and list_faces(d) when it is not what you expect."""
    w = where.strip().lower()
    if len(w) != 2 or w[0] not in '+-' or w[1] not in 'xyz':
        raise Failed(f"side: where must be one of +x -x +y -y +z -z, not {where!r}")
    k, sign = 'xyz'.index(w[1]), 1.0 if w[0] == '+' else -1.0
    box = bbox(d)
    end = box[k + 3] if sign > 0 else box[k]
    want = [0.0, 0.0, 0.0]
    want[k] = sign
    out = []
    for f in faces(d):
        i = face_info(f)
        if i['kind'] != 'plane' or max(abs(a - b) for a, b in zip(i['normal'], want)) > 0.01:
            continue
        if abs((i['box'][k + 3] if sign > 0 else i['box'][k]) - end) <= tol:
            out.append(f)
    return out
