"""sizes.py net.net: each part's footprint, courtyard size (mm, at rotation 0) and pad nets (KiCad Python; planning aid)"""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','schematic','tools')); from sx import *
import pcbnew
FP='C:/Program Files/KiCad/10.0/share/kicad/footprints/'; OWN=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','marengo_buck12.pretty')
N=parse(open(sys.argv[1]).read())
nets={}
for net in getall(get(N,'nets'),'net'):
    nm=str(get(net,'name')[1])
    for x in getall(net,'node'): nets.setdefault(str(get(x,'ref')[1]),{})[str(get(x,'pin')[1])]=nm
for c in getall(get(N,'components'),'comp'):
    ref=str(get(c,'ref')[1]); fp=str(get(c,'footprint')[1]); lib,name=fp.split(':')
    f=pcbnew.FootprintLoad(OWN if lib=='marengo_buck12' else FP+lib+'.pretty',name)
    bb=f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    print(ref,str(get(c,'value')[1])[:28],name[:40],'%.2fx%.2f'%(pcbnew.ToMM(bb.GetWidth()),pcbnew.ToMM(bb.GetHeight())),nets.get(ref,{}))
