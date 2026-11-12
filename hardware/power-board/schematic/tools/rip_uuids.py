"""rip_uuids.py in.kicad_pcb out.kicad_pcb UUID[,UUID...] (KiCad Python): remove the listed unlocked tracks and vias
(for example escape_probe.py's RIP= line), refill and save; their nets are re-routed afterwards."""
import sys,pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); ids=set(sys.argv[3].split(','))
k=[t for t in b.GetTracks() if t.m_Uuid.AsString() in ids and not t.IsLocked()]
for t in k: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('ripped',len(k),sorted({t.GetNetname() for t in k}))
