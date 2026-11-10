"""Net classes for the rev B5 spacing rules (LAYOUT_RULES.md), shared by tools/grid_route.py (plain Python) and
tools/route_checks.py / hv_spacing.py / gnd_fanout.py (KiCad's Python), so the router routes to the rules the checks test.
  - 54 V copper (HV): LAYOUT_RULES.md's list (BAT, SW_D, MID, VBUS, ABS, CL_D, BRK_*, SH*, V_L*) plus ABS_N and the
    port drains D_L*, and U8's supply and sense pins VS_A, CSP_A, CSN_A (on RS1's pads through 0R; added 2026-11-10,
    no copper had to move). The latch's own supply chain (BAT_F, BAT_R, BAT_CTL) and the divider taps are not in it.
  - E-stop safety nets (ESTOP): keep >= 1.5 mm to 54 V copper (the HV list) on every layer, 0.6 mm (outer) to copper
    riding on 54 V (0.44 MOhm of leakage into UVLO enables bank
    B by itself).
  - Voltage domains: copper that rides on one 54 V node (a port's gate and bootstrap on its V_L, sense taps on VBUS, bank
    B's gate on MID, ...). Pairs inside one domain are tens of volts apart at most, so the 0.6 mm rule (outer layers,
    IPC-2221B B2, 51-100 V) applies only between different domains where one side is 54 V.
"""
import re
ESTOP_NAMES='RUN RUN_A RUN_B RUN_P SP_ENR UVLO EN_A FLT_A FLT_D L_B L_E L_PB L_PC MID_B VB_B INT_B WDO_N VWD'.split()
def is_estop(n): return n in {'/'+x for x in ESTOP_NAMES} or bool(re.match(r'/(LOOP_|RST_)',n))
import os
# MARENGO_HV_EXTRA=BAT_F,BAT_CTL,...: a what-if for tools/route_checks.py, treating these nets as 54 V copper too
HV_EXTRA={'/'+x for x in os.environ.get('MARENGO_HV_EXTRA','').split(',') if x}
def is_hv(n):
    return (bool(re.match(r'/(BAT|SW_D|MID|VBUS|ABS|ABS_N|CL_D|VS_A|CSP_A|CSN_A)$|/(BRK_|SH|V_L|D_L)',n)) or n in HV_EXTRA) and not is_estop(n) and not n.startswith('/SH12')
DOMRE=[('BAT',r'/(BAT|SW_D|SH_[PN]|SH9_[PN]|BRK_D|CSP_A|CSN_A|VS_A)$'),('MID',r'/(MID|GA1|GA2|GATE_A|BST_A|G1PD_A)$'),
       ('VBUS',r'/(VBUS|D_L\d|CSP_L\d|INP_L\d|SHL\d_[PN]|G1|G2|GATE|SHSP_[PN])$'),('ABS',r'/ABS$'),('CLD',r'/CL_D$'),
       ('BRK',r'/BRK_(F|P|T|PG|IN|GATE|G1)$')]+[(f'VL{k}',rf'/(V|G|GPD|GPU|BST|GC)_L{k}$') for k in range(1,7)]
def dom(n):
    """domain name of a net, or None for ground-referenced copper"""
    for name,rx in DOMRE:
        if re.match(rx,n): return name
    return None
def rides(n):
    """54 V copper, or copper riding on a 54 V node (a gate or bootstrap on its source, a sense tap on VBUS)"""
    return is_hv(n) or dom(n) is not None
# The latch's own 54 V supply chain (BAT -> F1 -> BAT_F -> 22R -> BAT_R -> ES1D -> BAT_CTL -> U2) lies at the latch
# block, so it is not on the 54 V list (the fail-safe E-stop nets may pass it at 0.2 mm). These E-stop nets are the ones
# that leakage from 54 V could push toward "run" at over 100 kOhm (LAYOUT_RULES.md, "Leakage from the latch supply": the
# table net by net), and they keep 1.5 mm to the chain on every layer:
#   L_B, RST_C  0.47-0.56 MOhm turns the seal-in NPN on: the latch sets without a reset press
#   MID_B       20 MOhm reports "MID healthy" and releases the reset interlock
#   RUN_A, EN_A 4.3 MOhm enables bank A;  RUN_B, UVLO, FLT_D  0.44-0.7 MOhm enables bank B
# tools/latch_block.py places the chain and L_B's parts so that this holds; clearance() gives the routers and
# tools/route_checks.py the 1.5 mm, the .kicad_dru rule latch_supply_leak (leak_rule() below; tools/handfinish_prep.py
# writes it, tools/check.py compares) gives it to KiCad's DRC and fill, and route_checks check 10 counts the pairs: 0.
LATCH_SUPPLY={'/BAT_F','/BAT_R','/BAT_CTL'}
LEAK_SENSITIVE={'/L_B','/RST_C','/MID_B','/RUN_A','/EN_A','/RUN_B','/UVLO','/FLT_D'}
LEAK_PAIRS_MAX=0
def leak_rule():
    """the .kicad_dru rule for the two lists, exactly as tools/handfinish_prep.py writes it"""
    sup=' || '.join(f"A.NetName == '{n}'" for n in sorted(LATCH_SUPPLY)); sen=' || '.join(f"B.NetName == '{n}'" for n in sorted(LEAK_SENSITIVE))
    return f'(rule latch_supply_leak\n  (constraint clearance (min 1.5mm))\n  (condition "({sup}) && ({sen})"))\n'
def latch_leak(a,b):
    """one net on the latch's supply chain, the other a leakage-sensitive E-stop net"""
    return (a in LATCH_SUPPLY and b in LEAK_SENSITIVE) or (b in LATCH_SUPPLY and a in LEAK_SENSITIVE)
# The latch block (tools/place.py, option A), floorplan mm (X0, X1, Y0, Y1). LAYOUT_RULES: no 54 V copper on L2-L5 under
# it, so no 54 V inner track or via there. latch_page() gives KiCad page mm (place.py: page X = X + 150, page Y = 440 - Y).
LATCH=(-48.0,-31.0,254.0,310.5)
def latch_page():
    X0,X1,Y0,Y1=LATCH; return (X0+150,X1+150,440-Y1,440-Y0)
# The board gets an acrylic conformal coat after bring-up (Joey, 2026-11-09; IPC-2221B Table 6-1, 51-100 V: A5/A7 0.13 mm,
# B4 0.13 mm, against B2 0.6 mm and A6 0.5 mm uncoated), so the 0.6 mm domain rule is the 0.2 mm default. The E-stop
# 1.5 mm rule and the hole keep-outs don't change. MARENGO_COATED=0 checks the bare-board rule.
COATED=os.environ.get('MARENGO_COATED','1')=='1'
def clearance(a,b,outer):
    """required copper clearance (mm) between nets a and b on an outer (True) or inner layer"""
    if a==b: return 0.0
    if (is_estop(a) and is_hv(b)) or (is_estop(b) and is_hv(a)): return 1.5   # the rule's net list; 54 V-riding nets get 0.6 below
    if latch_leak(a,b): return 1.5   # the latch supply chain against the leakage-sensitive E-stop nets
    if (rides(a) or rides(b)) and not (dom(a) and dom(a)==dom(b)): return 0.6 if (outer and not COATED) else 0.2
    return 0.2
# Documented exceptions (LAYOUT_RULES.md, "Exceptions and hand-laid copper"), tested by tools/route_checks.py checks 7 and 8.
# Each excepted via is pinned to its coordinates (page mm, VIA_TOL): a via of the same net anywhere else fails.
# Vias of another net inside a MID pour outline: the three VBUS vias at the bank B FETs' pins 2-3 (tools/route_power.py),
# GATE_A's at Q8's gate, GA2's in the pour's dead tip beside U8, and G2's at Q2's gate (the only way out of the slot
# between Q1's tab and Q2's pins; accepted in the project thread on 2026-11-10, to be confirmed at the review).
VIA_TOL=0.05
MID_VIA_OK={'/VBUS':[(151.2,161.46),(151.2,162.73),(132.0,162.73)],'/GATE_A':[(132.0,141.46)],'/GA2':[(167.95,157.0)],'/G2':[(149.9,160.19)]}
# Gate-drive nets (LAYOUT_RULES "Critical nets") take at most 2 vias. G2 may take 3 (same exception) and GATE_A has 3
# from the staged routing: for those two, every via must be one of the listed ones.
GATE_RE=r'/((G|GPD|GPU|BST)_L\d|GATE|GATE_A|GA[12]|G[12]|G1PD_A|BST_A|BRK_GATE|BRK_G1|PRE_G|CL_G)$'
GATE_VIAS_MAX=2
GATE_VIA_OK={'/G2':[(149.9,160.19),(130.2,167.0),(125.6,139.8)],'/GATE_A':[(132.0,141.46),(168.55,158.85),(168.55,164.75)]}
def via_listed(p,table,net):
    """is the via at p (page mm) one of the net's documented ones?"""
    return any(abs(p[0]-q[0])<=VIA_TOL and abs(p[1]-q[1])<=VIA_TOL for q in table.get(net,()))
# Kelvin pairs: the least share (percent) of the pair's whole length, both legs, that runs within 1.0 mm (centre to
# centre, same layer) of the other leg. tools/route_checks.py check 3 fails below it. The floors are the routed board's
# values of 2026-11-10 rounded down: a re-route may not make a pair worse. SH9 is exception 9 in LAYOUT_RULES.
KELVIN_FLOOR={'/SH':61,'/SH9':9,'/SHL1':56,'/SHL2':56,'/SHL3':56,'/SHL4':56,'/SHL5':56,'/SHL6':56}
