"""port_copper.py: the designed copper of one port block, used by port_template.py (KiCad Python).
Coordinates are port 1's page mm; port_template.T() maps them to the other ports. Layers: F = F.Cu, 2 = In2.Cu,
3 = In3.Cu, B = B.Cu. Each item is ('t', net role, layer, points[, width]) or ('v', net role, point).
The plan, pin by pin (eFuse U, top row = 54 V side facing the shunt, bottom row = logic side facing the meter):
  20 SHL_P   F.Cu from the shunt's P pad; via A below that pad starts the In2 Kelvin pair
  19 ISCP    inward, west under the pin ends to R1 (upper lane)
  18 CSP     inward, west to R0 (lower lane)
  17 SHL_N   F.Cu from the shunt's N pad, under the shunt body beside P; inward to a via, In2 west to join P
  15 GPU     outward, outer lane of the channel under the shunt, into R4 (100k) at the top of the corridor
  14 GPD     outward, inner lane, down the corridor's west side to R5 (the 22 R, at the gate pin)
  13 V_L     inward to a via; In3 east past the BST via, south to the V_L via at the gate zener and the meter's pin 8
  12 BST     inward to a via (In3 to the bootstrap cap)
  1 EN, 3 INP, 5 PORT_FLT_N, 2/6/7/10 GND: inward, one row of vias under the body at 0.85 mm pitch (In3 from there)
  8 IWRN, 9 TMR: outward to two vias between the eFuse and the meter
The Kelvin pair runs on In2 down the west side of the eFuse (P outside, N inside, 0.6 mm apart), feeds R0/C2 (P) and
R1 (N) through one via each, turns east between the eFuse and the meter and ends in a via per leg at meter pins 10/9.
Gate: R4 (GPU, 100k) and R5 (GPD, 22 R) stand in the corridor east of the eFuse, R5 at the bottom with its G pad 3.2 mm
from the gate pin (pad centre to the pin's end; 3.8 mm of F.Cu track, with the zener on the same line). GPD runs down
the west side of the corridor to R5, R4's G pad down the east side. A via on the gate line feeds the slew network (D0,
C4, R6) right of the FET on In3. Until 2026-11-10 both resistors sat at the pin channel, 7.5 mm from the gate."""
import pcbnew, port_template as PT
IU=pcbnew.FromMM
ITEMS=[
 # ---- Kelvin P
 ('t','P','F',[(161.6,189.92),(162.35,189.92),(162.75,190.4),(162.75,191.6)]),
 ('t','P','F',[(161.25,190.1),(161.25,190.9)]), ('v','P',(161.25,190.9)),
 ('t','P','2',[(161.25,190.9),(161.35,191.2),(161.35,197.85),(161.65,198.15),(163.6,198.15),(163.9,198.2)]),
 ('v','P',(161.35,196.6)), ('t','P','F',[(161.35,196.6),(160.6,196.2)]), ('t','P','F',[(160.275,196.3),(160.275,197.4)]),
 ('v','P',(163.9,198.2)), ('t','P','F',[(163.9,198.2),(165.0,198.2),(165.6,198.8),(166.0,198.9)]),
 # ---- Kelvin N
 ('t','N','F',[(167.6,187.38),(163.6,187.38),(163.2,187.78),(163.2,190.5),(163.6,190.9),(164.25,190.9),(164.25,191.6)]),
 ('t','N','F',[(164.25,192.6),(164.25,193.2),(164.45,193.5),(164.45,193.75)]), ('v','N',(164.45,193.75)),
 ('t','N','2',[(164.45,193.75),(163.9,193.2),(161.95,193.2)]),
 ('v','N',(161.95,192.3)), ('t','N','F',[(161.95,192.3),(161.3,191.6),(160.5,191.5)]),
 ('t','N','2',[(161.95,192.3),(161.95,197.2),(162.25,197.5),(164.6,197.5),(164.9,197.8),(164.9,199.6)]),
 ('v','N',(164.9,199.6)), ('t','N','F',[(164.9,199.6),(165.3,199.4),(166.0,199.4)]),
 # ---- sense resistors
 ('t','ISCP','F',[(163.25,192.6),(163.25,193.3),(160.5,193.3)]),
 ('t','CSP','F',[(163.75,192.6),(163.75,193.75),(161.2,193.75),(160.6,194.3)]),
 # ---- gate drive
 ('t','GPU','F',[(165.25,191.6),(165.25,190.62),(169.0,190.62),(169.0,193.15)]),   # outer lane of the channel, down into R4
 ('t','GPD','F',[(165.75,191.6),(165.75,191.02),(167.6,191.02),(168.0,191.42),(168.0,195.9),(168.3,196.2),(169.0,196.2)]),   # inner lane, down the west side of the corridor to R5
 ('t','G','F',[(169.0,194.8),(169.9,194.8),(169.9,198.2)]),   # R4's G pad, down the east side of the corridor
 ('t','G','F',[(169.0,197.85),(169.0,198.2)]),                # R5's G pad onto the gate line
 ('t','G','F',[(168.95,199.1),(168.95,198.2),(172.09,198.2),(172.09,198.9)]),   # zener, gate line, gate pin
 ('t','G','F',[(170.7,198.2),(170.7,197.35)]), ('v','G',(170.7,197.35)),
 ('t','G','3',[(170.7,197.35),(171.55,196.5),(181.2,196.5),(181.4,196.3),(181.4,194.2),(182.0,193.6),(184.6,193.6),(184.6,193.65)]),
 ('v','G',(184.6,193.65)), ('t','G','F',[(184.6,193.65),(185.5,192.8)]),
 # ---- V_L tap and bootstrap
 ('t','V','F',[(166.25,192.6),(166.25,193.6)]), ('v','V',(166.25,193.6)),
 ('t','V','3',[(166.25,193.6),(166.6,194.42),(167.9,194.42),(168.55,195.07),(168.55,201.25),(169.65,202.35),(169.95,202.35)]),
 ('v','V',(169.95,202.35)), ('t','V','F',[(169.3,202.65),(169.95,202.35)]), ('t','V','B',[(169.95,202.35),(172.3,202.35)],0.25),
 ('t','V8','3',[(168.55,199.7),(166.0,199.7),(165.4,200.3),(165.2,200.45)]), ('v','V8',(165.2,200.45)),
 ('t','V8','F',[(166.0,199.9),(165.6,199.9),(165.2,200.3),(165.2,200.45)]),
 ('t','BST','F',[(166.75,192.6),(166.75,193.2),(167.05,193.5),(167.05,193.75)]), ('v','BST',(167.05,193.75)),
 ('t','BST','3',[(167.05,193.75),(169.0,193.75),(169.3,194.05),(169.3,197.7),(169.6,198.0),(187.75,198.0),(188.05,197.7),(188.05,192.45),(188.5,192.0)]),
 ('v','BST',(188.5,192.0)), ('t','BST','F',[(188.5,192.0),(189.4,191.97)]),
 ('t','V','F',[(191.22,191.965),(192.25,191.965),(192.65,192.4),(192.65,197.0),(193.2,197.5)],0.25),
 # ---- logic row, inward slots
 ('t','EN','F',[(162.75,196.0),(162.75,195.5),(162.6,195.15)]), ('v','EN',(162.6,195.15)), ('t','EN','3',[(162.6,195.15),(159.2,195.15)]),
 ('t','GND','F',[(163.25,196.0),(163.25,194.4)],0.2), ('v','GND',(163.25,194.4)),
 ('t','GND','F',[(163.25,194.4),(165.2,194.4),(165.65,194.85),(165.65,195.15)],0.2),   # the plane is voided round this via: tie it to the pin 6/7 via
 ('t','INP','F',[(163.75,196.0),(163.75,195.5),(163.9,195.15)]), ('v','INP',(163.9,195.15)), ('t','INP','3',[(163.9,195.15),(163.9,196.9),(163.6,197.2),(159.2,197.2)]),
 ('t','FLT','F',[(164.75,196.0),(164.75,195.15)]), ('v','FLT',(164.75,195.15)), ('t','FLT','3',[(164.75,195.15),(164.75,197.3),(164.45,197.6),(163.4,197.6),(163.0,198.0),(159.2,198.0)]),
 ('t','GND','F',[(165.25,196.3),(165.75,196.3)]), ('t','GND','F',[(165.75,196.0),(165.75,195.5),(165.65,195.15)]), ('v','GND',(165.65,195.15)),
 ('t','GND','F',[(167.25,196.0),(167.25,195.5),(166.95,195.15)]), ('v','GND',(166.95,195.15)),
 # ---- logic row, outward
 ('t','IWRN','F',[(166.25,197.0),(166.25,197.5),(166.1,197.75),(166.1,198.0)]), ('v','IWRN',(166.1,198.0)),
 ('t','IWRN','2',[(166.1,198.0),(166.5,198.6),(188.35,198.6),(188.75,198.2),(188.75,195.07)]), ('v','IWRN',(188.75,195.07)), ('t','IWRN','F',[(188.75,195.07),(189.4,195.07)]),
 ('t','TMR','F',[(166.75,197.0),(166.75,197.5),(166.95,197.75),(166.95,198.0)]), ('v','TMR',(166.95,198.0)),
 ('t','TMR','2',[(166.95,198.0),(186.7,198.0),(187.45,197.25)]), ('v','TMR',(187.45,197.25)), ('t','TMR','F',[(187.45,197.25),(188.3,196.9),(189.4,196.65)]),
 ('t','TMR','2',[(187.45,197.25),(187.45,190.4),(188.2,189.65)]), ('v','TMR',(188.2,189.65)), ('t','TMR','F',[(188.2,189.65),(187.6,189.0)]),
 # ---- meter
 ('t','SDA','F',[(162.9,200.4),(163.4,200.4),(163.7,200.35)]), ('v','SDA',(163.7,200.35)),
 ('t','SCL','F',[(162.6,200.9),(163.0,200.95),(163.5,201.1),(164.5,201.1)]), ('v','SCL',(164.5,201.1)),
 ('t','3V3','F',[(167.2,200.9),(167.2,202.5)]),
 ('t','GND','F',[(167.2,200.4),(167.9,200.4)]), ('v','GND',(167.9,200.4)),
 # ---- slew network
 # ---- drain cap to the L6 drain mirror
 ('t','D','F',[(189.4,190.45),(188.7,190.45)],0.5), ('v','D',(188.7,190.45)), ('t','D','B',[(188.7,190.45),(181.5,190.45)],0.5),
 ('t','GC','F',[(182.465,192.0),(182.9,190.6)]),
 ('t','GC','F',[(183.15,189.3),(183.275,188.1)]),
]
def netname(role,k):
    return {'P':f'/SHL{k}_P','N':f'/SHL{k}_N','V':f'/V_L{k}','D':f'/D_L{k}','G':f'/G_L{k}','FLT':'/PORT_FLT_N','GND':'GND','3V3':'/+3V3_PI',
            'SDA':'/I2C_SDA','SCL':'/I2C_SCL'}.get(role) or f'/{role}_L{k}'
LAY={'F':PT.F,'2':PT.I2,'3':PT.I3,'B':PT.B}
# The port's own analog and gate nets: on these the board must equal the template (MODE=check). The logic exits and the
# buses (EN, INP, PORT_FLT_N, I2C, 3V3, GND, V_L, D_L) are re-routed between the blocks by finish_route.py and may differ.
ROLES=('P','N','ISCP','CSP','GPU','GPD','G','BST','GC','IWRN','TMR')
def prims(b,k,fps,roles=None):
    """the template's primitives for port k, page mm: ('v', net, (x,y)) and ('t', net, layer, a, c, width)"""
    out=[]; R=PT.refs(k)
    v8=next(p.GetNetname() for p in fps[R['INA']].Pads() if p.GetNumber()=='8')   # port 2's meter senses D_L, not V_L
    for it in ITEMS:
        if roles and it[1] not in roles: continue
        if it[1]=='V8':
            if v8!=f'/V_L{k}': continue   # no designed tap: finish_route connects pin 8
            net=v8
        else: net=netname(it[1],k)
        assert b.FindNet(net),(it[1],k)
        if it[0]=='v': out.append(('v',net,PT.T(k,it[2])))
        else:
            w=it[4] if len(it)>4 else (.25 if it[1]=='GND' else .2)
            out+=[('t',net,LAY[it[2]],PT.T(k,a),PT.T(k,c),w) for a,c in zip(it[3],it[3][1:])]
    return out
def make(b,p):
    if p[0]=='v':
        v=pcbnew.PCB_VIA(b); v.SetPosition(PT.V(p[2])); v.SetWidth(IU(.6)); v.SetDrill(IU(.3)); v.SetNet(b.FindNet(p[1]))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(PT.F,PT.B); return v
    t=pcbnew.PCB_TRACK(b); t.SetStart(PT.V(p[3])); t.SetEnd(PT.V(p[4])); t.SetWidth(IU(p[5])); t.SetLayer(p[2]); t.SetNet(b.FindNet(p[1])); return t
def lay(b,k,fps):
    new=[make(b,p) for p in prims(b,k,fps)]
    for t in new: t.SetLocked(True); b.Add(t)
    print(f'port {k}: template copper {len(new)} items')
def key(t):
    """a board track or via in the form prims() gives, rounded to 1 um; a track's ends in sorted order"""
    r=lambda p:(round(pcbnew.ToMM(p.x),3),round(pcbnew.ToMM(p.y),3))
    if t.GetClass()=='PCB_VIA': return ('v',t.GetNetname(),r(t.GetPosition()))
    return ('t',t.GetNetname(),t.GetLayer())+tuple(sorted((r(t.GetStart()),r(t.GetEnd()))))+(round(pcbnew.ToMM(t.GetWidth()),3),)
def pkey(p):
    r=lambda q:(round(q[0],3),round(q[1],3))
    return ('v',p[1],r(p[2])) if p[0]=='v' else ('t',p[1],p[2])+tuple(sorted((r(p[3]),r(p[4]))))+(round(p[5],3),)
def diff(b,k,fps):
    """the board against the template for port k: (template primitives missing from the board, locked copper of the
    port's own nets inside the block that the template doesn't have)"""
    want={pkey(p):p for p in prims(b,k,fps,ROLES)}; have={}
    for t in b.GetTracks(): have.setdefault(key(t),t)
    missing=[p for q,p in want.items() if q not in have]
    own={netname(r,k) for r in ROLES}
    stale=[t for q,t in have.items() if q not in want and t.IsLocked() and t.GetNetname() in own and PT.inblock(k,t)]
    return missing,stale
def sync(b,ports,fps,dry=False):
    """bring the ports' own nets to the template without ripping the routing between the blocks: add what is missing,
    remove stale locked copper and any router bridge that started from a stale primitive's end (a point the template no
    longer has). Everything is read from the board before the first Remove (KiCad 10's lookups can fail after it)."""
    plan=[]; tracks=list(b.GetTracks())
    for k in ports:
        missing,stale=diff(b,k,fps)
        ends={q for p in prims(b,k,fps,ROLES) if p[0]=='t' for q in pkey(p)[3:5]}
        old={q for t in stale if key(t)[0]=='t' for q in key(t)[3:5]}-ends
        own={netname(r,k) for r in ROLES}
        bridges=[t for t in tracks if t.GetClass()!='PCB_VIA' and not t.IsLocked() and t.GetNetname() in own and set(key(t)[3:5])&old]
        for p in missing: print(f'   port {k} missing:',p[1],[b.GetLayerName(p[2])]+list(p[3:]) if p[0]=='t' else p[2])
        for t in stale: print(f'   port {k} stale:',key(t)[1],key(t)[3:] if key(t)[0]=='t' else key(t)[2])
        for t in bridges: print(f'   port {k} router bridge at a stale end:',key(t)[1],key(t)[3:5])
        plan.append((missing,stale,bridges))
    if not dry:
        new=[make(b,p) for missing,_,_ in plan for p in missing]
        for _,stale,bridges in plan:
            for t in stale+bridges: b.Remove(t)
        for t in new: t.SetLocked(True); b.Add(t)
    return sum(len(m) for m,_,_ in plan),sum(len(s_)+len(br) for _,s_,br in plan)
