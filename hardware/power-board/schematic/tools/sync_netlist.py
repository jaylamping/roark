"""sync_netlist.py net.net in.kicad_pcb out.kicad_pcb (KiCad Python): bring an existing board back in line with the
schematic's netlist without touching placement or copper, so KiCad's schematic-parity check is clean:
  - every footprint's value, Datasheet field and attributes (exclude from BOM, DNP) from its symbol;
  - every pad's net from the netlist, and no net where the schematic has none (a pad whose net changes is listed, and
    the copper touching it is removed: re-route);
  - footprints with no symbol (mounting holes, heatsink and tie holes) marked "not in schematic".
tools/place.py sets the same on a rebuilt board."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from sx import *
import pcbnew
N=parse(open(sys.argv[1]).read()); b=pcbnew.LoadBoard(sys.argv[2])
fps={f.GetReference():f for f in b.GetFootprints()}; pads={r:list(f.Pads()) for r,f in fps.items()}
nets={}
for net in getall(get(N,'nets'),'net'):
    nm=str(get(net,'name')[1])
    for x in getall(net,'node'): nets[(str(get(x,'ref')[1]),str(get(x,'pin')[1]))]=nm
seen=set(); nval=nattr=nfield=0; moved=[]
def apply(fp,c):
    """value, datasheet and attributes of one footprint from its netlist component; returns what changed"""
    ch=[]
    v=str(get(c,'value')[1])
    if fp.GetValue()!=v: fp.SetValue(v); ch.append('value')
    ds=get(c,'datasheet'); ds=str(ds[1]) if ds and len(ds)>1 else ''
    if (fp.GetFieldText('Datasheet') if fp.HasField('Datasheet') else '')!=ds: fp.SetField('Datasheet',ds); ch.append('datasheet')
    props={str(get(p,'name')[1]) for p in getall(c,'property')}
    for name,getter,setter in (('exclude_from_bom',fp.IsExcludedFromBOM,fp.SetExcludedFromBOM),('dnp',fp.IsDNP,fp.SetDNP)):
        if getter()!=(name in props): setter(name in props); ch.append(name)
    return ch
if __name__=='__main__':
    for c in getall(get(N,'components'),'comp'):
        ref=str(get(c,'ref')[1]); fp=fps.get(ref)
        if fp is None: print('no footprint for',ref); continue
        seen.add(ref); ch=apply(fp,c); nval+='value' in ch; nfield+='datasheet' in ch; nattr+=any(k in ch for k in ('exclude_from_bom','dnp'))
        for p in pads[ref]:
            want=nets.get((ref,p.GetNumber()),'')
            if p.GetNetname()!=want and not (want=='' and p.GetNetname().startswith('unconnected-')):
                ni=b.FindNet(want) if want else None
                if want and ni is None: ni=pcbnew.NETINFO_ITEM(b,want); b.Add(ni)
                moved.append((ref,p.GetNumber(),p.GetNetname(),want))
                if ni: p.SetNet(ni)
                else: p.SetNetCode(0)   # no net in the schematic: the pad must not keep its old one
    # copper that touches a re-netted pad now shorts two nets: remove it (the rest of that route is left dangling for
    # tools/prune_dangling.py, and the pad's new net for tools/finish_route.py)
    tracks=list(b.GetTracks()); kill=[]
    for ref,num,old,want in moved:
        p=next(q for q in pads[ref] if q.GetNumber()==num)
        for t in tracks:
            if t.GetNetname()!=want and t.GetNetname() and any(t.IsOnLayer(L) and p.IsOnLayer(L) and t.GetEffectiveShape(L).Collide(p.GetEffectiveShape(L),0) for L in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.In3_Cu,pcbnew.In4_Cu,pcbnew.B_Cu)) and t not in kill: kill.append(t)
    for t in kill: b.Remove(t)
    extra=[r for r in fps if r not in seen]
    for r in extra: fps[r].SetBoardOnly(True)
    b.Save(sys.argv[3])
    print('values',nval,'datasheets',nfield,'attributes',nattr,'board-only',len(extra),sorted(extra))
    print('pad nets changed',len(moved))
    for m in moved: print('   ',m)
    print('tracks removed at those pads',len(kill))
