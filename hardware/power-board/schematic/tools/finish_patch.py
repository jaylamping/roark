"""Export/replay a headless routing delta, or merge an additive trial by net.

KiCad python finish_patch.py export BASE FINAL PATCH_JSON
KiCad python finish_patch.py apply BASE OUTPUT PATCH_JSON
KiCad python finish_patch.py merge BASE BRANCH TARGET OUTPUT NET_REGEX
Replay requires the exact baseline SHA256, never removes locked copper, and
refills zones before saving. Run DRC, route_checks and finish_audit afterwards.
"""
import sys,json,hashlib,re
import pcbnew
from finish_route import Router,UID,XY,CU,RL,IU,V

def records(base,final):
    old=list(base.GetTracks()); new=list(final.GetTracks()); oi={UID(t):t for t in old}; ni={UID(t):t for t in new}
    remove=[u for u in oi if u not in ni]
    assert not any(oi[u].IsLocked() for u in remove)
    add=[]
    for t in new:
        if UID(t) in oi: continue
        rec=dict(net=t.GetNetname(),uid=UID(t),kind=t.GetClass())
        if rec['kind']=='PCB_VIA': rec.update(p=XY(t.GetPosition()),width=pcbnew.ToMM(t.GetWidth(CU[0])),drill=pcbnew.ToMM(t.GetDrillValue()))
        else:
            assert rec['kind']=='PCB_TRACK'
            rec.update(a=XY(t.GetStart()),b=XY(t.GetEnd()),layer=final.GetLayerName(t.GetLayer()),width=pcbnew.ToMM(t.GetWidth()))
        add.append(rec)
    return remove,add

def add_records(r,add,check=False):
    for x in add:
        n=x['net']
        it=('v',tuple(x['p'])) if x['kind']=='PCB_VIA' else ('t',r.b.GetLayerID(x['layer']),[tuple(x['a']),tuple(x['b'])])
        if check:
            assert r.via(n,it[1]) if it[0]=='v' else r.path(n,it[1],it[2]), x
        if x['kind']=='PCB_VIA':
            t=pcbnew.PCB_VIA(r.b); t.SetPosition(V(x['p'])); t.SetWidth(IU(x['width'])); t.SetDrill(IU(x['drill'])); t.SetViaType(pcbnew.VIATYPE_THROUGH); t.SetLayerPair(CU[0],CU[5])
        else:
            t=pcbnew.PCB_TRACK(r.b); t.SetStart(V(x['a'])); t.SetEnd(V(x['b'])); t.SetLayer(r.b.GetLayerID(x['layer'])); t.SetWidth(IU(x['width']))
        t.SetNet(r.b.FindNet(n)); r.b.Add(t); r.tracks.append(t); r.index_track(t)

def main():
    mode=sys.argv[1]
    if mode=='export':
        base,final=map(pcbnew.LoadBoard,sys.argv[2:4]); remove,add=records(base,final)
        obj=dict(baseline_sha256=hashlib.sha256(open(sys.argv[2],'rb').read()).hexdigest(),remove=remove,add=add)
        json.dump(obj,open(sys.argv[4],'w'),indent=2); print('finish_patch exported removals:',len(remove),'additions:',len(add))
    elif mode=='apply':
        obj=json.load(open(sys.argv[4])); assert hashlib.sha256(open(sys.argv[2],'rb').read()).hexdigest()==obj['baseline_sha256'],'wrong baseline'
        r=Router(sys.argv[2]); ids=set(obj['remove']); old={UID(t):t for t in r.tracks}; assert ids<=set(old)
        for u in ids: assert not old[u].IsLocked(); r.b.Remove(old[u])
        add_records(r,obj['add']); r.save(sys.argv[3]); print('finish_patch replayed removals:',len(ids),'additions:',len(obj['add']))
    elif mode=='merge':
        base,branch=map(pcbnew.LoadBoard,sys.argv[2:4]); remove,add=records(base,branch); assert not remove,'only additive branches can merge'
        only=re.compile(sys.argv[6]); add=[x for x in add if only.search(x['net'])]
        r=Router(sys.argv[4]); add_records(r,add,check=True); r.save(sys.argv[5]); print('finish_patch merged additions:',len(add))
    else: raise ValueError(mode)

if __name__=='__main__': main()
