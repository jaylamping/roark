import time,sys,pythoncom,win32com.client as wc
from win32com.client import VARIANT
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'/'solidworks'))
from sw_instance import session, end_session
W=Path(os.environ.get('ARM_SW_DIR',Path(__file__).resolve().parents[2]/'_wip'/'arm-sw'))   # PID file and build log (gitignored)
W.mkdir(parents=True,exist_ok=True)
def log(*a):
    s=time.strftime('%H:%M:%S ')+' '.join(str(x) for x in a);print(s,flush=True)
    with open(W/'build_log.txt','a',encoding='utf8') as f:f.write(s+'\n')
def _call_with_timeout(fn, timeout):
    """Run fn() in a worker thread (its own COM apartment); returns (done, result_or_exception)."""
    import threading
    box = {}
    def run():
        pythoncom.CoInitialize()
        try:
            box['r'] = fn()
        except BaseException as ex:
            box['r'] = ex
        finally:
            pythoncom.CoUninitialize()
    t = threading.Thread(target=run, daemon=True); t.start(); t.join(timeout)
    return (not t.is_alive()), box.get('r')
HUNG = W / 'HUNG_PID'
def app():
    """This session's own instance, reused across scripts. See tools/solidworks/RULES.md.
    2026-11-12 (holly-pc hangs): a state file naming a dead PID is cleared; a recorded instance that is alive but does not answer
    a COM call in 30 s is NOT attached to (stop and report its PID; this shell must not force-stop SolidWorks)."""
    import sw_instance as SI
    st = W / '.sw_instance_pid'
    if HUNG.exists():
        raise RuntimeError(f'an instance of this folder is recorded as hung ({HUNG.read_text().strip()}); not launching. End it, then delete {HUNG}')
    if st.exists():
        pid = SI._session_pid(str(st))
        if pid is None:
            st.unlink()          # stale: that process is gone (or the PID was reused)
        else:
            done, r = _call_with_timeout(lambda: int(SI.attach(pid).sw.GetProcessID), 30)
            if not done or isinstance(r, BaseException):
                HUNG.write_text(f'{pid} unresponsive at attach {time.strftime("%H:%M:%S")}')
                raise RuntimeError(f'recorded instance PID {pid} does not respond; not attaching or launching. taskkill /PID {pid} /T /F')
    return session(st).sw
def finish(timeout=120):
    """Close this folder's instance cleanly. If the close does not finish in `timeout` s, record the PID in HUNG_PID and raise:
    no force-kill from here (the machine's guard forbids it; report the PID instead)."""
    import sw_instance as SI
    st = W / '.sw_instance_pid'
    pid = SI._session_pid(str(st)) if st.exists() else None
    done, r = _call_with_timeout(lambda: end_session(st), timeout)
    if not done:
        HUNG.write_text(f'{pid} close timed out {time.strftime("%H:%M:%S")}')
        raise RuntimeError(f'closing PID {pid} timed out after {timeout} s; recorded in {HUNG}. taskkill /PID {pid} /T /F')
    if isinstance(r, BaseException):
        raise r
def L(v=0): return VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,v)
def imp(sw,step,target):
    """Import STEP and save it as target; returns the saved doc title and type."""
    d=sw.GetImportFileData(str(step));e=L()
    t=time.time();doc=sw.LoadFile4(str(step),'r',d,e);log('import',step.name,'err',e.value,'s',round(time.time()-t,1),'doc',doc is not None)
    if doc is None: raise RuntimeError(f'import failed {step} err {e.value}')
    typ=doc.GetType
    tgt=target.with_suffix('.SLDASM' if typ==2 else '.SLDPRT');ee,ww=L(),L()
    ok=doc.Extension.SaveAs(str(tgt),0,1,VARIANT(pythoncom.VT_DISPATCH,None),ee,ww)
    log('saved',tgt.name,'ok',ok,'err',ee.value,'warn',ww.value,'type',typ)
    if not ok: raise RuntimeError(f'save failed {tgt}')
    return tgt,typ
