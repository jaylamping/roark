"""kelvin_buck.py board.kicad_pcb (KiCad Python): the buck board's two Kelvin pairs (RS1 -> U2: SH12_P/SH12_N; RS2 -> U4:
SHSP_P/SHSP_N), measured as the main board's route_checks.py check 3 does. Each leg is traced from the shunt's sense pad
to the meter's pin over a layer-aware track graph (track ends on different layers join only through a via of the net or a
through-hole pad); the leg's length, and the share of both legs' length that runs within 1.0 mm, centre to centre on the
same layer, of the other leg. LAYOUT_RULES: the legs run as a pair on one layer, so the legs' inner-layer copper must all
be on one layer, the same for P and N (the F.Cu stubs at the sense pad and the meter's pins are allowed).
The sense pads sit at opposite corners of the 2512 four-terminal footprint, so a leg can't be paired over the distance
between them; FLOOR is set below what the designed copper gives (tools/copper_buck.py) and above an unpaired layout.
Exit 1 on a pair under its floor, a leg that can't be traced, or legs on different inner layers."""
import os,sys,math,heapq
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','schematic','tools'))
import pcbnew
IU,MM=pcbnew.FromMM,pcbnew.ToMM
FLOOR={'/SH12':55.0,'/SHSP':40.0}   # % of both legs paired; the designed copper gives 59.0 and 45.6 (the 3cd770b board: 11.8 and 0)
PAIR=1.0
b=pcbnew.LoadBoard(sys.argv[1])
def ptseg(p,a,c):
    dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
    f=0 if ll==0 else max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/ll))
    return math.hypot(p[0]-a[0]-f*dx,p[1]-a[1]-f*dy)
def leg(net):
    """(tracks of the leg as (layer, a, c), None) or (None, why)"""
    T=[(t.GetLayer(),(MM(t.GetStart().x),MM(t.GetStart().y)),(MM(t.GetEnd().x),MM(t.GetEnd().y))) for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net]
    V=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net]
    R=lambda L,q:(L,round(q[0],2),round(q[1],2)); adj={}
    def edge(u,v,w,i): adj.setdefault(u,[]).append((v,w,i)); adj.setdefault(v,[]).append((u,w,i))
    for i,(L,s,e) in enumerate(T): edge(R(L,s),R(L,e),math.dist(s,e),i)
    for i,(L,s,e) in enumerate(T):   # T-joins on the same layer
        for q in (s,e):
            for j,(L2,s2,e2) in enumerate(T):
                if j!=i and L2==L and ptseg(q,s2,e2)<0.02 and R(L,q) not in (R(L,s2),R(L,e2)):
                    edge(R(L,q),R(L,s2),math.dist(q,s2),j); edge(R(L,q),R(L,e2),math.dist(q,e2),j)
    for k,v in enumerate(V):
        for u in list(adj):
            if u[0] not in ('via','pad') and v.HitTest(pcbnew.VECTOR2I(IU(u[1]),IU(u[2]))): edge(('via',k),u,0.0,-1)
    src=[]; dst=[]
    for pd in b.GetPads():
        if pd.GetNetname()!=net: continue
        ref=pd.GetParentFootprint().GetReference(); node=('pad',ref,pd.GetNumber())
        for u in list(adj):
            if u[0] in ('via','pad'): continue
            if pd.IsOnLayer(u[0]) and pd.HitTest(pcbnew.VECTOR2I(IU(u[1]),IU(u[2]))): edge(node,u,0.0,-1)
        for k,v in enumerate(V):   # a via in the pad (the sense pads' Kelvin taps)
            if pd.HitTest(v.GetPosition()): edge(node,('via',k),0.0,-1)
        (src if ref.startswith('RS') else dst if ref.startswith('U') else []).append(node)
    if not src or not dst: return None,f'sense pads {len(src)}, meter pins {len(dst)}'
    dist={u:0.0 for u in src}; prev={}; h=[(0.0,repr(u),u) for u in src]; heapq.heapify(h)
    while h:
        d,_,u=heapq.heappop(h)
        if d>dist.get(u,1e30): continue
        for v,w,i in adj.get(u,()):
            if d+w<dist.get(v,1e30)-1e-9: dist[v]=d+w; prev[v]=(u,i); heapq.heappush(h,(d+w,repr(v),v))
    lost=[f'{t[1]}.{t[2]}' for t in dst if t not in dist]
    if lost: return None,f'no copper path from the sense pad to {lost}'
    used=set()
    for t in dst:
        while t in prev: u,i=prev[t]; used.add(i); t=u
    used.discard(-1)
    return ([T[i] for i in sorted(used)],None) if used else (None,'no track on the path')
def near(A,B):
    tot=nr=0.0
    for L,s,e in A:
        ln=math.dist(s,e); tot+=ln; k=max(1,int(ln/0.25))
        for i in range(k):
            q=(s[0]+(e[0]-s[0])*(i+0.5)/k,s[1]+(e[1]-s[1])*(i+0.5)/k)
            if any(L2==L and ptseg(q,s2,e2)<=PAIR for L2,s2,e2 in B): nr+=ln/k
    return tot,nr
print(f'Kelvin pairs, sense pad to meter pin: leg lengths (mm), share within {PAIR} mm of the other leg, inner layers; floor')
bad=[]; done=0
for base,fl in FLOOR.items():
    (P,ep),(N,en)=leg(base+'_P'),leg(base+'_N')
    if ep or en: bad.append(f'{base}: leg not traced: P {ep}, N {en}'); continue
    lp,np_=near(P,N); ln,nn=near(N,P); both=100*(np_+nn)/max(lp+ln,1e-9); done+=1
    inner={b.GetLayerName(L) for L,_,_ in P+N if L not in (pcbnew.F_Cu,pcbnew.B_Cu)}
    ip={b.GetLayerName(L) for L,_,_ in P if L not in (pcbnew.F_Cu,pcbnew.B_Cu)}; inn={b.GetLayerName(L) for L,_,_ in N if L not in (pcbnew.F_Cu,pcbnew.B_Cu)}
    print(f'   {base}: P {lp:.1f}, N {ln:.1f}; P {100*np_/max(lp,1e-9):.0f} %, N {100*nn/max(ln,1e-9):.0f} %, both {both:.1f} %; P on {sorted(ip)}, N on {sorted(inn)}; floor {fl} %')
    if both<fl: bad.append(f'{base}: {both:.1f} % paired, floor {fl} %')
    if len(inner)!=1 or ip!=inn: bad.append(f'{base}: legs not on one inner layer: P {sorted(ip)}, N {sorted(inn)}')
if done!=len(FLOOR): bad.append(f'{len(FLOOR)-done} pairs not measured')
for r in bad: print('FAIL:',r)
print('kelvin_buck fails',len(bad)); sys.exit(1 if bad else 0)
