from swlib import *
NUL=VARIANT(pythoncom.VT_DISPATCH,None)
def open_(sw,p):
    n=p.split('/')[-1];e=L();d=sw.ActivateDoc3(n,False,0,e)
    return d
def edit(d,name):
    f=d.FeatureByName(name)
    if f is None: raise RuntimeError('no '+name)
    d.ClearSelection2(True);f.Select2(False,0);d.EditSketch()
    return d.GetActiveSketch2
def segs(sk):
    return [s for s in (sk.GetSketchSegments or [])]
def selall(d,sk):
    d.ClearSelection2(True)
    for s in segs(sk): s.Select4(True,NUL)
def close(d):
    d.ClearSelection2(True);d.InsertSketch2(True)
def move(d,name,dx,dy=0):
    sk=edit(d,name);n=len(segs(sk));selall(d,sk)
    ok=d.Extension.MoveOrCopy(False,1,False,0,0,0,dx/1000,dy/1000,0)
    close(d);print(name,'segs',n,'move',ok)
