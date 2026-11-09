"""lock_nets.py in.kicad_pcb out.kicad_pcb NET_REGEX [report.json] (KiCad Python): lock every track and via of the
matching nets and print each net's routed length, layers and via count; with rip_nets.py's report, also the old values
and the length ratio."""
import sys,re,json,pcbnew,collections
b=pcbnew.LoadBoard(sys.argv[1]); rx=re.compile(sys.argv[3]); I=pcbnew.ToMM
old=json.load(open(sys.argv[4])) if len(sys.argv)>4 else {}
rep=collections.defaultdict(lambda:{'length':0.0,'layers':set(),'vias':0})
for t in b.GetTracks():
    n=t.GetNetname()
    if not rx.search(n): continue
    t.SetLocked(True); r=rep[n]
    if t.GetClass()=='PCB_VIA': r['vias']+=1
    else: r['length']+=I(t.GetLength()); r['layers'].add(b.GetLayerName(t.GetLayer()))
b.Save(sys.argv[2])
for n in sorted(set(rep)|set(old)):
    r=rep.get(n,{'length':0,'layers':set(),'vias':0}); o=old.get(n)
    ratio=f" ratio {r['length']/o['length']:.2f}" if o and o['length'] else ''
    print(f"{n:12s} new {r['length']:.2f} mm {sorted(r['layers'])} vias {r['vias']}"+(f" | old {o['length']} mm {o['layers']} vias {o['vias']}{ratio}" if o else ''))
