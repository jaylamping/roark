"""Remove DRC-reported unlocked dangling tracks/vias after local rerouting.

KiCad python finish_cleanup.py INPUT OUTPUT DRC_JSON [BASELINE]
Only removes items explicitly reported as track_dangling/via_dangling. Refills
zones and rejects the whole operation if any pad component is split. Repeat
DRC and cleanup until no dangling items remain; locked items are never removed.
"""
import sys,json
import pcbnew
from finish_route import Router,UID,CU,IU
from finish_shove import pad_components
from sx import parse,getall,get
r=Router(sys.argv[1]); groups=pad_components(r); d=json.load(open(sys.argv[3]))
ids={it['uuid'] for v in d['violations'] if v['type'] in ('track_dangling','via_dangling') for it in v['items']}
removed=[]
removedids=set()
affected=set()
for t in r.tracks:
    if UID(t) not in ids: continue
    assert not t.IsLocked(),('locked dangling item',UID(t))
    r.b.Remove(t); removed.append(t); removedids.add(UID(t)); affected.add(t.GetNetname())
# Trim the newly exposed end of each reported dead-end chain, rather than
# requiring a DRC pass for every 0.1 mm stair-step in the original raster route.
for _ in range(250):
    extra=[]
    for t in r.tracks:
        if UID(t) in removedids or t.IsLocked() or t.GetNetname() not in affected or t.GetClass()!='PCB_TRACK': continue
        L=t.GetLayer(); n=t.GetNetname()
        for e in (t.GetStart(),t.GetEnd()):
            sh=pcbnew.SHAPE_CIRCLE(e,t.GetWidth()//2)
            contact=False
            for cell in r.cells(r.bb(sh.BBox())):
                for ob in r.idx.get((L,)+cell,()):
                    on,osh,kind,bb,cy,uid=ob
                    if on==n and uid!=UID(t) and uid not in removedids and osh.Collide(sh,0): contact=True; break
                if contact: break
            if not contact:
                contact=any(not z.GetIsRuleArea() and z.GetNetname()==n and z.IsOnLayer(L) and z.GetFilledPolysList(L).Collide(sh,0) for z in r.b.Zones())
            if not contact: extra.append(t); break
    if not extra: break
    for t in extra:
        if UID(t) in removedids: continue
        r.b.Remove(t); removed.append(t); removedids.add(UID(t))
if len(sys.argv)>4:
    base=parse(open(sys.argv[4],encoding='utf-8').read())
    baselineids={str(get(t,'uuid')[1]) for kind in ('segment','via','arc') for t in getall(base,kind)}
    r.b.BuildConnectivity(); con=r.b.GetConnectivity()
    for u in d['unconnected_items']:
        for it in u['items']:
            t=r.byid.get(it['uuid'])
            if not t or UID(t) in removedids or t.GetClass() not in ('PCB_TRACK','PCB_VIA'): continue
            comp=list(con.GetConnectedItems(t)); objects={UID(c):c for c in comp if c.GetClass() in ('PCB_TRACK','PCB_VIA')}
            objects[UID(t)]=t
            # A newly created, wholly floating route fragment has no electrical
            # terminal and can be removed rather than counted as an open net.
            if any(c.GetClass() in ('PAD','ZONE') for c in comp): continue
            if any(uid in baselineids or c.IsLocked() for uid,c in objects.items()): continue
            for uid,c in objects.items():
                if uid in removedids: continue
                r.b.Remove(c); removed.append(c); removedids.add(uid)
pcbnew.ZONE_FILLER(r.b).Fill(r.b.Zones()); after=pad_components(r); amap={u:i for i,g in enumerate(after) for u in g}
split=[g for g in groups if len({amap[u] for u in g})>1]
if split:
    print('finish_cleanup ROLLED BACK: split pad components:',len(split))
    for t in removed: r.b.Add(t)
else: print('finish_cleanup removed dangling items:',len(removed))
r.save(sys.argv[2])
