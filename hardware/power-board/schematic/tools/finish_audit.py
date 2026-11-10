"""Verify protected PCB definitions and baseline pad connectivity after routing.

KiCad python finish_audit.py BASELINE CANDIDATE
Compares footprint/zone definitions (excluding generated fill), locked copper,
new routing geometry and original connected pad components. Exits nonzero on
any changed protected item, new pad-touching via, forbidden layer/band, wrong
new primitive size, or any lost baseline pad-to-pad connection.
"""
import sys,math
import pcbnew
from sx import parse,get,getall
from finish_route import UID,XY,CU,RL,IU
import domains

def ident(x):
    u=get(x,'uuid'); return str(u[1]) if u else None
def stripfill(x): return [a for a in x if not isinstance(a,list) or a[0] not in ('filled_polygon','fill_segments')]
base=parse(open(sys.argv[1],encoding='utf-8').read()); cand=parse(open(sys.argv[2],encoding='utf-8').read()); fails=[]
for kind in ('footprint','zone'):
    aa={ident(x):stripfill(x) if kind=='zone' else x for x in getall(base,kind)}
    bb={ident(x):stripfill(x) if kind=='zone' else x for x in getall(cand,kind)}
    changed=[k for k in aa if aa[k]!=bb.get(k)]+[k for k in bb if k not in aa]
    print('protected',kind,'changed:',len(changed))
    if changed: fails.append((kind,changed))
for kind in ('setup','net_class','net','layers'):
    if getall(base,kind)!=getall(cand,kind): fails.append(('definitions',kind))
oldc={ident(x):x for kind in ('segment','via','arc') for x in getall(base,kind)}
newc={ident(x):x for kind in ('segment','via','arc') for x in getall(cand,kind)}
locked={k:v for k,v in oldc.items() if 'locked' in v or get(v,'locked') is not None}
lc=[k for k,v in locked.items() if newc.get(k)!=v]; print('locked copper changed:',len(lc))
if lc: fails.append(('locked',lc))
ob=pcbnew.LoadBoard(sys.argv[1]); nb=pcbnew.LoadBoard(sys.argv[2]); ob.BuildConnectivity(); nb.BuildConnectivity()
op=list(ob.GetPads()); np=list(nb.GetPads()); nt=list(nb.GetTracks()); oldids=set(oldc); added=[t for t in nt if UID(t) not in oldids]
bad=[]; nv=0
for t in added:
    if t.GetClass()=='PCB_VIA':
        nv+=1; x,y=XY(t.GetPosition())
        if domains.in_vbus_band((x,y)): bad.append(('band',UID(t)))
        if abs(pcbnew.ToMM(t.GetWidth(CU[0]))-.6)>1e-6 or abs(pcbnew.ToMM(t.GetDrillValue())-.3)>1e-6: bad.append(('via size',UID(t)))
        for p in np:
            if any(p.IsOnLayer(L) and p.GetEffectiveShape(L).Collide(t.GetEffectiveShape(L),IU(.000001)) for L in CU): bad.append(('via touching pad',UID(t),p.GetParentFootprint().GetReference(),p.GetNumber()))
    else:
        if t.GetLayer() not in RL: bad.append(('plane track',UID(t)))
        if min(abs(pcbnew.ToMM(t.GetWidth())-.2),abs(pcbnew.ToMM(t.GetWidth())-.25))>1e-6: bad.append(('track width',UID(t)))
print('new primitives:',len(added),'vias:',nv,'geometry violations:',len(bad))
if bad: fails.append(('geometry',bad))
def components(b,pads):
    con=b.GetConnectivity(); comp={}; groups=[]
    for p in pads:
        uid=UID(p)
        if uid in comp: continue
        connected={UID(i) for i in con.GetConnectedItems(p) if i.GetClass()=='PAD'}|{uid}
        k=len(groups); groups.append(connected)
        for u in connected: comp[u]=k
    return comp,groups
oc,og=components(ob,op); nc,ng=components(nb,np); lost=[]
for group in og:
    if len({nc.get(p,('missing',p)) for p in group})>1: lost.append(sorted(group))
print('baseline pad components split:',len(lost))
if lost: fails.append(('lost connections',lost))
oldlocked=[t for t in list(ob.GetTracks()) if t.IsLocked()]
newnodes={UID(t):t for t in nt+np}; con=nb.GetConnectivity(); oldcon=ob.GetConnectivity(); splitlocked=[]
nodeids={UID(p) for p in op}|{UID(t) for t in oldlocked}
for t in oldlocked:
    before={UID(i) for i in oldcon.GetConnectedItems(t) if UID(i) in nodeids}|{UID(t)}
    obj=newnodes.get(UID(t))
    after={UID(i) for i in con.GetConnectedItems(obj)}|{UID(t)} if obj else set()
    if not before<=after: splitlocked.append(UID(t))
print('baseline locked-copper connections split:',len(splitlocked))
if splitlocked: fails.append(('lost locked-copper connections',splitlocked))
for f in fails: print('FAIL',f)
print('finish_audit FAILS',len(fails))
sys.exit(bool(fails))
