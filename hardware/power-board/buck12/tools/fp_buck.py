"""fp_buck.py: the buck board's own footprints, written into ../buck12.pretty from KiCad's stock ones (plain Python).
  CP_Elec_12.5x13.5_ChemiCon  C2, Chemi-Con EMVH101ARA470MKE0S (12.5 x 13.5 mm can): Chemi-Con's land, 5.7 x 2.5 mm pads
                              with a 4.0 mm gap (pad centres at +/-4.85 mm); outline, silk and courtyard scaled from
                              CP_Elec_10x10 to the 13.5 mm base plate
  Texas_RGY_..._ThermalVias_0.3mm  U1, LM5146: the stock footprint with its four exposed-pad vias at 0.6/0.3 mm (stock 0.5/0.2)
  CP_Elec_10x10.5_ZA          C24, Panasonic EEH-ZA1E331V: CP_Elec_10x10.5 with the pads 4.2 mm wide (was 2.5), so the V
                              version's support terminals (out to about +/-1.9 mm) are wetted as well as its main terminals
Usage: python fp_buck.py"""
import os,re
STOCK=os.environ.get('KICAD_FP') or next(p for p in ('C:/Program Files/KiCad/10.0/share/kicad/footprints/','/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/') if os.path.isdir(p))
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','buck12.pretty'); os.makedirs(OUT,exist_ok=True)
def rd(n): return open(os.path.join(STOCK,'Capacitor_SMD.pretty',n+'.kicad_mod'),encoding='utf-8').read()
def wr(n,t): open(os.path.join(OUT,n+'.kicad_mod'),'w',encoding='utf-8',newline='\n').write(t); print('wrote',n)
def rename(t,old,new,descr):
    t=t.replace(f'(footprint "{old}"',f'(footprint "{new}"',1)
    t=re.sub(r'\(descr "[^"]*"\)',f'(descr "{descr}")',t,count=1)
    t=t.replace(f'"{old}"',f'"{new}"')
    return re.sub(r'\(model "[^"]*"[\s\S]*?\n\t\)\n','',t)   # no 3D model of the new size in the stock library
# C24: wider pads
t=rename(rd('CP_Elec_10x10.5'),'CP_Elec_10x10.5','CP_Elec_10x10.5_ZA','CP_Elec_10x10.5 with 4.2 mm wide pads for Panasonic EEH-ZA (V version: support terminals beside the main ones)')
assert t.count('(size 4.4 2.5)')==2; t=t.replace('(size 4.4 2.5)','(size 4.4 4.2)')
# the courtyard's pad extensions (stock: +/-1.5 mm, for 2.5 mm pads) follow the wider pads: +/-2.1 mm + 0.25 = +/-2.35 mm
def crt(m):
    return re.sub(r'\((start|end) (-?[\d.]+) (-?)1\.5\)',lambda q:f'({q.group(1)} {q.group(2)} {q.group(3)}2.35)',m.group(0))
t,n=re.subn(r'\(fp_line\s*\(start [^()]*\)\s*\(end [^()]*\)[^()]*\(stroke[^()]*\([^()]*\)[^()]*\([^()]*\)[^()]*\)\s*\(layer "F\.CrtYd"\)',crt,t)
assert n==14 and t.count('2.35)')==16, (n,t.count('2.35)'))   # 14 courtyard lines, 16 ends at +/-1.5
wr('CP_Elec_10x10.5_ZA',t)
# C2: 12.5 mm can on Chemi-Con's land
t=rename(rd('CP_Elec_10x10'),'CP_Elec_10x10','CP_Elec_12.5x13.5_ChemiCon','Aluminium electrolytic 12.5 x 13.5 mm (Chemi-Con MVH J-case), Chemi-Con land: 5.7 x 2.5 mm pads, 4.0 mm gap')
K=13.5/10.3   # base plate 13.5 mm against the 10 mm can's 10.3 mm
def scale(m):
    return f'({m.group(1)} {float(m.group(2))*K:.4g} {float(m.group(3))*K:.4g})'
head,sep,rest=t.partition('\t(pad ')
body='\t(pad '+rest
# graphics (fp_line/fp_circle/fp_arc/fp_poly points) scale; pads are set explicitly below
head=re.sub(r'\((start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)\)',scale,head)
body=re.sub(r'(\(pad "1"[\s\S]*?)\(at -?[\d.]+ 0\)([\s\S]*?)\(size [\d.]+ [\d.]+\)',r'\1(at -4.85 0)\2(size 5.7 2.5)',body,count=1)
body=re.sub(r'(\(pad "2"[\s\S]*?)\(at -?[\d.]+ 0\)([\s\S]*?)\(size [\d.]+ [\d.]+\)',r'\1(at 4.85 0)\2(size 5.7 2.5)',body,count=1)
t=head+body
# text positions above/below the body move out with it
t=re.sub(r'(\(property "(?:Reference|Value)" "[^"]*"\s*\(at 0 )(-?[\d.]+)',lambda m:m.group(1)+f'{float(m.group(2))*K:.4g}',t)
wr('CP_Elec_12.5x13.5_ChemiCon',t)
# U1: the stock RGY thermal-via footprint with the four exposed-pad vias at the board's own via size, 0.6 mm pad, 0.3 mm
# drill (stock: 0.5/0.2 mm, the only drill under 0.3 mm, which costs a finer-drill price at JLC). The exposed pad is
# 2.05 x 3.05 mm (TI RGY land pattern); the stock diamond (+/-0.775, 0), (0, +/-1.275) would put a 0.6 mm pad 0.05 mm
# past the pad's edge, so the vias move in to (+/-0.7, 0) and (0, +/-1.2): each via pad stays 0.025 mm inside the
# exposed pad, holes 1.09 mm wall to wall at the closest (JLC asks 0.2 mm). Filled and capped like every via on the board.
src=open(os.path.join(STOCK,'Package_DFN_QFN.pretty','Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm_ThermalVias.kicad_mod'),encoding='utf-8').read()
old,new='Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm_ThermalVias','Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm_ThermalVias_0.3mm'
t=src.replace(f'(footprint "{old}"',f'(footprint "{new}"',1).replace(f'"{old}"',f'"{new}"')
t=re.sub(r'\(descr "',r'(descr "Four 0.6/0.3 mm thermal vias (stock: 0.5/0.2 mm); ',t,count=1)
MOVE={'-0.775 0':'-0.7 0','0.775 0':'0.7 0','0 -1.275':'0 -1.2','0 1.275':'0 1.2'}
def via(m):
    at=m.group(1); assert at in MOVE, at
    return f'(pad "21" thru_hole circle\n\t\t(at {MOVE[at]})\n\t\t(size 0.6 0.6)\n\t\t(drill 0.3)\n\t\t(zone_connect 2)'   # solid: inside the exposed pad a thermal relief has no room for spokes (DRC starved_thermal)
t,n=re.subn(r'\(pad "21" thru_hole circle\s*\(at (-?[\d.]+ -?[\d.]+)\)\s*\(size 0\.5 0\.5\)\s*\(drill 0\.2\)',via,t)
assert n==4 and '(drill 0.2)' not in t, n
wr(new,t)
