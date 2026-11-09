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
def app():
    """This session's own instance, reused across scripts. See tools/solidworks/RULES.md."""
    return session(W/'.sw_instance_pid').sw
def finish():
    end_session(W/'.sw_instance_pid')
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
