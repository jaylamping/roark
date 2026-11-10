"""add_parts.py net.net in.kicad_pcb out.kicad_pcb REF=cx,cy[,p1x,p1y] ... (KiCad Python): put parts that the schematic
has and an existing routed board lacks onto the board, without touching anything else. Each REF is loaded from its
library as tools/place.py does (value, datasheet, attributes and pad nets from the netlist, so the parity check is
clean) and placed with its courtyard centre at (cx, cy) page mm, turned so that pad 1 lies at (p1x, p1y) when given.
A net the board doesn't have yet is created. Stops if a REF is already on the board or not in the netlist.
Connect the new pads with tools/lay_path.py or tools/finish_route.py afterwards. tools/place.py holds the same
positions for a rebuild (its MOVED table: J27, TP17 and R139 of the heatsink tie)."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from sx import *
import pcbnew, blocks
HERE=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
FPDIR=os.environ.get('KICAD_FP') or next((p for p in ('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/','C:/Program Files/KiCad/10.0/share/kicad/footprints/') if os.path.isdir(p)),None)
assert FPDIR,'set KICAD_FP to the KiCad footprints folder'
N=parse(open(sys.argv[1]).read()); b=pcbnew.LoadBoard(sys.argv[2])
have={f.GetReference() for f in b.GetFootprints()}
comp={str(get(c,'ref')[1]):c for c in getall(get(N,'components'),'comp')}
padnet={}
for net in getall(get(N,'nets'),'net'):
    nm=str(get(net,'name')[1])
    for x in getall(net,'node'): padnet[(str(get(x,'ref')[1]),str(get(x,'pin')[1]))]=nm
new=[]
for spec in sys.argv[4:]:
    ref,xy=spec.split('='); v=[float(x) for x in xy.split(',')]
    assert ref in comp,f'{ref} is not in the netlist'; assert ref not in have,f'{ref} is already on the board'
    c=comp[ref]; lib,name=str(get(c,'footprint')[1]).split(':')
    fp=pcbnew.FootprintLoad(os.path.join(HERE,'marengo_revb.pretty') if lib=='marengo_revb' else FPDIR+lib+'.pretty',name)
    fp.SetReference(ref); fp.SetValue(str(get(c,'value')[1])); fp.SetFPID(pcbnew.LIB_ID(lib,name))
    ds=get(c,'datasheet'); fp.SetField('Datasheet',str(ds[1]) if ds and len(ds)>1 else '')
    props={str(get(p,'name')[1]) for p in getall(c,'property')}
    fp.SetExcludedFromBOM('exclude_from_bom' in props); fp.SetDNP('dnp' in props)
    for pad in fp.Pads():
        nm=padnet.get((ref,pad.GetNumber()))
        if not nm: continue
        ni=b.FindNet(nm)
        if ni is None: ni=pcbnew.NETINFO_ITEM(b,nm); b.Add(ni)
        pad.SetNet(ni)
    b.Add(fp); blocks.place_fp(fp,(v[0],v[1]),(v[2],v[3]) if len(v)>3 else None); new.append(ref)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3]); print('added',new)
