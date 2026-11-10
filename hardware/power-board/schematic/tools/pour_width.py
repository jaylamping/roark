"""pour_width.py board.kicad_pcb [board2 ...] (KiCad Python): narrowest copper cross-section of the 60 A pours, measured
on the filled zone polygons (not the outlines): for each cut line across the current's direction, the filled width of
the net on F.Cu and on B.Cu, sampled every 0.05 mm; the cut with the least total is reported.
  VBUS, bank to ports: cuts Y = 178..190 (page mm; the neck where all 60 A flows) over X 130..170
  MID, bank A sources to bank B tabs: cuts Y = 150..158 over X 130..170
Boards given together are printed side by side for a before/after comparison."""
import sys,pcbnew
IU=pcbnew.FromMM
CUTS=[('/VBUS','VBUS neck Y 178-190',178.0,190.0,130.0,170.0),('/MID','MID band Y 150-158',150.0,158.0,130.0,170.0)]
def measure(path):
    b=pcbnew.LoadBoard(path); out=[]
    for net,name,y0,y1,x0,x1 in CUTS:
        zs=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()==net]
        best=None; y=y0
        while y<=y1+1e-9:
            w={}
            for L,ln in ((pcbnew.F_Cu,'F'),(pcbnew.B_Cu,'B')):
                polys=[z.GetFilledPolysList(L) for z in zs if z.IsOnLayer(L)]; n=0; x=x0
                while x<=x1:
                    p=pcbnew.VECTOR2I(IU(x),IU(y))
                    if any(ps.Contains(p) for ps in polys): n+=1
                    x+=0.05
                w[ln]=n*0.05
            t=w['F']+w['B']
            if best is None or t<best[0]: best=(t,y,w['F'],w['B'])
            y+=0.25
        out.append((name,best))
    return out
if __name__=='__main__':
    for p in sys.argv[1:]:
        print(p)
        for name,(t,y,f,bk) in measure(p): print(f'   {name}: narrowest total {t:.2f} mm at Y {y:.2f} (F.Cu {f:.2f} + B.Cu {bk:.2f})')
