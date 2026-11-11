"""Locally reroute unlocked blockers while preserving each original terminal.

KiCad python finish_shove.py INPUT OUTPUT DRC_JSON [NET_REGEX]
Uses finish_route's exact geometry. Transactions roll back if any displaced
track's endpoints or any used layer of a displaced via cannot be reconnected.
Locked, Kelvin, gate, wide power and bus copper are never displaced. A complete
DRC and open-net comparison must validate the output before adoption.
"""
import sys,os,re,json,math
import pcbnew
from finish_route import Router,XY,UID,IU,CU,RL

def eligible(t):
    n=t.GetNetname()
    if os.getenv('PRESERVE') and re.search(os.environ['PRESERVE'],n): return False
    if n in ('/MID','/ABS','/ABS_N','/BAT','/VBUS','/SW_D') and not (n=='/MID' and os.getenv('MOVE_MID_TAPS')=='1'): return False
    if t.IsLocked() or n.startswith('/SH') or re.match(r'/(GATE|GA[12]$|G[12]$|G_L|GPU_|GPD_|UVLO)',n): return False
    if t.GetClass()=='PCB_TRACK': return pcbnew.ToMM(t.GetWidth())<=.251
    if t.GetClass()=='PCB_VIA': return not (n in ('/BAT','/MID','/SW_D','/VBUS') or n.startswith('/D_L'))
    return False

def actual_blockers(r,n,items,candidates):
    r.ignore -= candidates; found=set()
    for it in items:
        tests=[]
        if it[0]=='t':
            for a,c in zip(it[2],it[2][1:]): tests.append((it[1],pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(IU(a[0]),IU(a[1])),pcbnew.VECTOR2I(IU(c[0]),IU(c[1])),IU(r.width(n))),False))
        else:
            p=it[1]; sh=pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(IU(p[0]),IU(p[1])),IU(.3)); tests=[(L,sh,True) for L in CU]
        for L,sh,v in tests:
            while True:
                diag=set()
                if r.free(n,L,sh,via=v,diagnostics=diag): break
                if not diag: return None
                uid=next(iter(diag))[2]
                if uid not in candidates: return None
                r.ignore.add(uid); found.add(uid)
    return found

def repair_via(r,t,original):
    p=XY(t.GetPosition()); n=t.GetNetname(); layers=set()
    for s in original:
        if s.GetClass()!='PCB_TRACK' or s.GetNetname()!=n: continue
        for e in (s.GetStart(),s.GetEnd()):
            if math.dist(p,XY(e))<.31: layers.add(s.GetLayer())
    if not layers: return None
    cand=[]
    for radius in (.6,.8,1.,1.3,1.6,2.,2.5,3.):
        for a in range(16):
            q=(round(p[0]+radius*math.cos(a*math.pi/8),5),round(p[1]+radius*math.sin(a*math.pi/8),5))
            if not r.via(n,q): continue
            items=[('v',q)]
            for L in layers:
                paths=sorted(r.shapes(p,q),key=r.plen)
                path=next((ps for ps in paths if r.path(n,L,ps)),None)
                if path is None: break
                items.append(('t',L,path))
            else: return items
    return None

def touch(a,c):
    for L in RL:
        if a.IsOnLayer(L) and c.IsOnLayer(L) and a.GetEffectiveShape(L).Collide(c.GetEffectiveShape(L),IU(.001)): return True
    return False

def anchors(t):
    if t.GetClass()=='PAD': return [(XY(t.GetPosition()),L) for L in RL if t.IsOnLayer(L)]
    if t.GetClass()=='PCB_VIA': return [(XY(t.GetPosition()),L) for L in RL]
    return [(XY(t.GetStart()),t.GetLayer()),(XY(t.GetEnd()),t.GetLayer())]

def pad_components(r):
    r.b.BuildConnectivity(); con=r.b.GetConnectivity(); seen=set(); groups=[]
    for p in r.pads:
        if UID(p) in seen: continue
        ids={UID(t) for t in con.GetConnectedItems(p) if t.GetClass()=='PAD'}|{UID(p)}
        seen |= ids; groups.append(ids)
    return groups

def contact_items(r,aa):
    out=[]
    for t in r.tracks+r.pads:
        if UID(t) in r.ignore: continue
        if any(t.IsOnLayer(L) and t.GetEffectiveShape(L).Collide(pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(IU(p[0]),IU(p[1])),0),IU(.001)) for p,L in aa): out.append(t)
    return out

def contacts_connected(r,n,A,B=None,ground=False):
    if os.getenv('TRIM_REDUNDANT')!='1': return False
    r.b.BuildConnectivity(); con=r.b.GetConnectivity()
    aa=[t for t in contact_items(r,A) if t.GetNetname()==n]
    bb={UID(t) for t in contact_items(r,B or []) if t.GetNetname()==n}
    for t in aa:
        items=list(con.GetConnectedItems(t))
        if ground and any(UID(i) not in r.ignore and (i.GetClass()=='PCB_VIA' or (i.GetClass()=='PAD' and i.HasHole())) for i in items): return True
        if any(UID(i) in bb for i in items): return True
    return False

def restore_groups(r,blockers,original):
    # Internal vertices of a displaced chain are routing artifacts, not terminals.
    # Preserve contacts to retained copper and pads, allowing the chain to move.
    groups=[]
    for t in blockers:
        matches=[g for g in groups if g[0].GetNetname()==t.GetNetname() and any(touch(t,c) for c in g)]
        group=[t]
        for g in matches: group+=g; groups.remove(g)
        groups.append(group)
    removed={UID(t) for t in blockers}
    retained=[t for t in original+r.pads if UID(t) not in removed]
    endpoints={}
    zonecontacts={}
    for gi,group in enumerate(groups):
        n=group[0].GetNetname(); endpoints[gi]=[]; zonecontacts[gi]=[]
        for t in group:
            if t.GetClass()!='PCB_TRACK': continue
            for p,L in anchors(t):
                point=pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(IU(p[0]),IU(p[1])),0)
                if any(c is not t and c.IsOnLayer(L) and c.GetEffectiveShape(L).Collide(point,IU(.001)) for c in group): continue
                zs=[z for z in r.zones if not z.GetIsRuleArea() and z.GetNetname()==n and z.IsOnLayer(L) and z.HitTestFilledArea(L,pcbnew.VECTOR2I(IU(p[0]),IU(p[1])))]
                if zs: zonecontacts[gi] += [(z,p,L) for z in zs]
                else: endpoints[gi].append([(p,L)])
    if any(zonecontacts.values()): pcbnew.ZONE_FILLER(r.b).Fill(r.b.Zones())
    for gi,group in enumerate(groups):
        n=group[0].GetNetname(); terms=[]
        for t in retained:
            if t.GetNetname()!=n or not any(touch(t,c) for c in group): continue
            aa=anchors(t)
            # The contact's closest endpoint suffices; pads and vias use centres.
            if t.GetClass()=='PCB_TRACK':
                ps=[p for c in group for p,L in anchors(c)]
                aa=[min(aa,key=lambda a:min(math.dist(a[0],p) for p in ps))]
            terms.append(aa)
        terms += endpoints[gi]
        for z,p,L in zonecontacts[gi]:
            it={'uuid':UID(z),'description':f'Zone [{n}] on {r.b.GetLayerName(L)}, priority 0'}
            aa=r.zone_anchors(it,[(p,L)])
            if aa: terms.append(aa)
        print('  restore group',n,len(group),'items',len(terms),'contacts',flush=True)
        if not terms: continue
        connected=terms.pop(0)
        if n=='GND' and any(t.GetClass()=='PCB_VIA' for t in group) and not contacts_connected(r,n,connected,ground=True):
            candidates=[]
            for p,L in connected:
                for radius in (.6,.8,1.,1.3,1.6,2.,2.5,3.):
                    for k in range(16):
                        q=(round(p[0]+radius*math.cos(k*math.pi/8),5),round(p[1]+radius*math.sin(k*math.pi/8),5))
                        if r.via(n,q): candidates.append((q,L))
            fix=r.simple(n,connected,candidates) if candidates else None
            if fix is None and candidates: fix=r.maze(n,connected,candidates)
            if fix is None: r.failed_restore=n; return False
            vp=next(it[2][-1] for it in reversed(fix) if it[0]=='t'); fix.append(('v',vp)); r.commit(n,fix)
            connected += [(vp,L) for L in RL]
        while terms:
            term=min(terms,key=lambda aa:min(math.dist(a[0],c[0]) for a in aa for c in connected)); terms.remove(term)
            if contacts_connected(r,n,term,connected): connected+=term; continue
            fix=r.simple(n,term,connected) or r.maze(n,term,connected)
            if fix is None: r.failed_restore=n; return False
            r.commit(n,fix); connected+=term
            for it in fix:
                if it[0]=='t': connected += [(p,it[1]) for p in it[2]]
                else: connected += [(it[1],L) for L in RL]
    return True

def shove(r,n,A,B,avoid=None):
    avoid=avoid or set(); r.failed_restore=None
    original=list(r.tracks); oldignore=set(r.ignore); oldidx={k:list(v) for k,v in r.idx.items()}
    original_components=pad_components(r)
    pts=[p for p,L in A+B]
    cand={UID(t) for t in original if eligible(t) and t.GetNetname() not in avoid and any(r.overlap(r.bb(t.GetBoundingBox()),(p[0]-2.5,p[1]-2.5,p[0]+2.5,p[1]+2.5)) for p in pts)}
    if not cand: print('  no movable blockers',flush=True); return False
    r.ignore |= cand
    result=r.simple(n,A,B) or r.maze(n,A,B)
    if result is None:
        r.ignore=oldignore; return False
    found=actual_blockers(r,n,result,cand)
    if found is None or not found:
        r.ignore=oldignore; return False
    print('  displacing',[(t.GetNetname(),t.GetClass(),UID(t)) for t in original if UID(t) in found],flush=True)
    r.commit(n,result)
    blockers=sorted([t for t in original if UID(t) in found],key=lambda t:t.GetClass()=='PCB_VIA')
    preremoved=os.getenv('TRIM_REDUNDANT')=='1'
    if preremoved:
        for t in blockers: r.b.Remove(t)
    ok=restore_groups(r,blockers,original)
    if ok:
        if not preremoved:
            for t in blockers: r.b.Remove(t)
        r.tracks=[t for t in r.tracks if UID(t) not in found]
        pcbnew.ZONE_FILLER(r.b).Fill(r.b.Zones())
        current=pad_components(r); currentmap={u:i for i,g in enumerate(current) for u in g}
        split=[g for g in original_components if len({currentmap[u] for u in g})>1]
        if not split: return True
        print('  ROLLBACK: split',len(split),'existing pad components',flush=True)
        first=next(iter(split[0])); r.failed_restore=next(p.GetNetname() for p in r.pads if UID(p)==first)
        for t in blockers: r.b.Add(t)
        preremoved=False
    if preremoved:
        for t in blockers: r.b.Add(t)
    oldids={UID(t) for t in original}
    for t in r.tracks:
        if UID(t) not in oldids: r.b.Remove(t)
    r.tracks=original; r.idx=oldidx; r.ignore=oldignore
    pcbnew.ZONE_FILLER(r.b).Fill(r.b.Zones())
    return False

def main():
    r=Router(sys.argv[1]); d=json.load(open(sys.argv[3])); only=re.compile(sys.argv[4] if len(sys.argv)>4 else '.*'); edges=[]
    for i,u in enumerate(d['unconnected_items']):
        n,A=r.parse(u['items'][0]); _,B=r.parse(u['items'][1])
        if not only.search(n) or n.startswith('/SH') or (n=='/G2' and os.getenv('TRY_G2')!='1'): continue
        if not A and B and u['items'][0]['description'].startswith('Zone'): A=r.zone_anchors(u['items'][0],B)
        if not B and A and u['items'][1]['description'].startswith('Zone'): B=r.zone_anchors(u['items'][1],A)
        if A and B and os.getenv('COMPONENTS')=='1':
            A0,B0=A,B
            A=r.component_anchors(u['items'][0],B0,A0); B=r.component_anchors(u['items'][1],A0,B0)
        if A and B: edges.append((min(math.dist(a[0],b[0]) for a in A for b in B),i,n,A,B))
    done=[]
    for length,i,n,A,B in sorted(edges):
        print('SHOVE',i,n,round(length,2),flush=True)
        avoid=set(); success=False
        for attempt in range(int(os.getenv('ATTEMPTS','1'))):
            if shove(r,n,A,B,avoid): success=True; break
            if not r.failed_restore or r.failed_restore in avoid: break
            avoid.add(r.failed_restore); print('  RETRY preserving',sorted(avoid),flush=True)
        if success: done.append((i,n)); print('CLOSED',i,n,flush=True)
        else: print('LEFT',i,n,flush=True)
    r.save(sys.argv[2]); print('finish_shove added edges:',len(done),done,flush=True)

if __name__=='__main__':main()
