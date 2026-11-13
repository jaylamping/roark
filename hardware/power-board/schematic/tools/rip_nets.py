"""rip_nets.py in.kicad_pcb out.kicad_pcb NET_REGEX report.json (KiCad Python): remove ALL copper (tracks and vias,
locked or not) of the matching nets, so they can be routed again from scratch, and record each net's old routed length
(mm), layers and via count in report.json for the before/after comparison (gate drives: new route no more than 20 %
longer, same layers). Only for nets the scripted locks protect; lock_nets.py locks the new routes again."""
import sys,re,json,pcbnew,collections
b=pcbnew.LoadBoard(sys.argv[1]); rx=re.compile(sys.argv[3]); I=pcbnew.ToMM
rep=collections.defaultdict(lambda:{'length':0.0,'layers':set(),'vias':0,'locked':0})
kill=[]
for t in b.GetTracks():
    n=t.GetNetname()
    if not rx.search(n): continue
    r=rep[n]; r['locked']+=t.IsLocked()
    if t.GetClass()=='PCB_VIA': r['vias']+=1
    else: r['length']+=I(t.GetLength()); r['layers'].add(b.GetLayerName(t.GetLayer()))
    kill.append(t)
for t in kill: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
out={n:{'length':round(r['length'],2),'layers':sorted(r['layers']),'vias':r['vias'],'locked':r['locked']} for n,r in rep.items()}
json.dump(out,open(sys.argv[4],'w'),indent=1); print('ripped',len(kill),json.dumps(out))
