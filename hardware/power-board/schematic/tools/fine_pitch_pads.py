"""fine_pitch_pads.py in.kicad_pcb out.kicad_pcb (KiCad Python): narrow the pin pads of the fine-pitch ICs to TI's land
patterns, so that every copper gap on the board is at least 0.2 mm (JLCPCB's minimum track and space for 2 oz outer
copper) and no fine-pitch clearance rule is needed.
KiCad's library footprints draw these pads wider than TI's drawings and leave 0.15 mm between them:
  U1, U7  LM5069 in MSOP-10 (TI DGS, 0.5 mm pitch): library pad 1.5 x 0.35 mm, TI's land pattern 1.45 x 0.3 mm
  U2      TPS7A4001 in HVSSOP-8 (TI DGN, 0.65 mm pitch): library pad 1.45 x 0.5 mm, TI's land pattern 1.4 x 0.45 mm
Only the width across the pitch is changed (0.30 and 0.45 mm); length, position, paste and mask follow the pad.
The narrowed footprints are in the project library (marengo_revb:..._TI, written by gen/genfp.py) and the schematic
names them, so tools/place.py loads them on a new board. This script brings an existing board to them: pad widths and
footprint IDs. MODE=check: exit 1 if a listed pad is wider than its value."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew
IU,MM=pcbnew.FromMM,pcbnew.ToMM
WIDTH={'U1':(0.30,10),'U7':(0.30,10),'U2':(0.45,8)}   # ref: (pad width across the pitch in mm, number of pin pads)
FPID={'U1':'marengo_revb:MSOP-10_3x3mm_P0.5mm_TI','U7':'marengo_revb:MSOP-10_3x3mm_P0.5mm_TI','U2':'marengo_revb:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm_TI'}
def pins(fp,n): return [p for p in fp.Pads() if p.GetNumber().isdigit() and 1<=int(p.GetNumber())<=n]
def narrow(fps,dry=False):
    """set the pads; returns the pads that were (or, dry, are) wider than their value"""
    wide=[]
    for ref,(w,n) in WIDTH.items():
        for p in pins(fps[ref],n):
            s=p.GetSize(pcbnew.F_Cu); narrow_x=s.x<s.y   # the narrow side is the one across the pitch
            cur=MM(min(s.x,s.y))
            if cur>w+1e-6:
                wide.append((ref,p.GetNumber(),round(cur,3),w))
                if not dry: p.SetSize(pcbnew.F_Cu,pcbnew.VECTOR2I(IU(w),s.y) if narrow_x else pcbnew.VECTOR2I(s.x,IU(w)))
    if not dry:
        for ref,fid in FPID.items(): fps[ref].SetFPID(pcbnew.LIB_ID(*fid.split(':')))
    return wide
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); fps={f.GetReference():f for f in b.GetFootprints()}
    if os.environ.get('MODE')=='check':
        wide=narrow(fps,dry=True); print('fine-pitch pads wider than TI\'s land pattern:',len(wide),wide[:6]); sys.exit(1 if wide else 0)
    wide=narrow(fps); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('narrowed',len(wide),'pads')
