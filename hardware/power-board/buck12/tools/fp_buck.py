"""fp_buck.py: the buck board's own footprints, written into ../marengo_buck12.pretty from KiCad's stock ones (plain Python).
  CP_Elec_12.5x13.5_ChemiCon  C2, Chemi-Con EMVH101ARA470MKE0S (12.5 x 13.5 mm can): Chemi-Con's land, 5.7 x 2.5 mm pads
                              with a 4.0 mm gap (pad centres at +/-4.85 mm); outline, silk and courtyard scaled from
                              CP_Elec_10x10 to the 13.5 mm base plate
  CP_Elec_10x10.5_ZA          C24, Panasonic EEH-ZA1E331V: CP_Elec_10x10.5 with the pads 4.2 mm wide (was 2.5), so the V
                              version's support terminals (out to about +/-1.9 mm) are wetted as well as its main terminals
Usage: python fp_buck.py"""
import os,re
STOCK=os.environ.get('KICAD_FP') or next(p for p in ('C:/Program Files/KiCad/10.0/share/kicad/footprints/','/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/') if os.path.isdir(p))
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','marengo_buck12.pretty'); os.makedirs(OUT,exist_ok=True)
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
body=re.sub(r'\(at -?[\d.]+ 0\)\s*\(size [\d.]+ [\d.]+\)',lambda m:m.group(0),body)
pads=re.findall(r'\t\(pad "(\d)"',body)
body=re.sub(r'(\(pad "1"[\s\S]*?)\(at -?[\d.]+ 0\)([\s\S]*?)\(size [\d.]+ [\d.]+\)',r'\1(at -4.85 0)\2(size 5.7 2.5)',body,count=1)
body=re.sub(r'(\(pad "2"[\s\S]*?)\(at -?[\d.]+ 0\)([\s\S]*?)\(size [\d.]+ [\d.]+\)',r'\1(at 4.85 0)\2(size 5.7 2.5)',body,count=1)
t=head+body
# text positions above/below the body move out with it
t=re.sub(r'(\(property "(?:Reference|Value)" "[^"]*"\s*\(at 0 )(-?[\d.]+)',lambda m:m.group(1)+f'{float(m.group(2))*K:.4g}',t)
wr('CP_Elec_12.5x13.5_ChemiCon',t)
