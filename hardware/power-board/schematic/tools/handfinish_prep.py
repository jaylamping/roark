#!/usr/bin/env python3
"""Hand-finishing setup for the rev B5 board in KiCad: net classes and the E-stop DRC rule, so KiCad's interactive
router and DRC hold the rules tools/route_checks.py tests (tools/domains.py).
  - net classes: ESTOP (the E-stop safety list, 0.2 mm tracks), HV54 (the 54 V list, 0.25 mm tracks), P12 (12 V
    distribution, 0.6 mm tracks), all at 0.2 mm clearance; everything else Default 0.2/0.2;
  - E-stop rule in the .kicad_dru: 1.5 mm from ESTOP to HV54 copper on every layer, ahead of U1's package rule
    estop_at_U1 (a later rule wins in KiCad, so inside U1's courtyard its 0.2 mm applies);
  - the latch supply's rule latch_supply_leak (domains.leak_rule(): 1.5 mm from BAT_F, BAT_R, BAT_CTL to the
    leakage-sensitive E-stop nets), rewritten on every run, ahead of U1's rule;
  - the 54 V domain rule (0.6 mm outer, uncoated) stays in tools/route_checks.py: coated it is the 0.2 mm default.
Run with plain Python: python tools/handfinish_prep.py <project.kicad_pro> <rules.kicad_dru> <netlist.net>"""
import json,os,re,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import domains
pro,dru,netf=sys.argv[1:4]
nets=sorted(set(re.findall(r'\(name "(/[^"]*)"\)',open(netf,encoding='utf-8').read())))
P12=['/+12V_RAW','/+12V','/+12V_JET','/+12V_PI','/+12V_FAN','/SPARE_SW','/SPARE_ON','/SP_SW1']
d=json.load(open(pro)); ns=d['net_settings']
base=dict(ns['classes'][0])
def cls(name,w,cl,color):
    c=dict(base); c.update(name=name,track_width=w,clearance=cl,pcb_color=color,priority={'ESTOP':1,'HV54':2,'P12':3}[name]); return c
ns['classes']=[ns['classes'][0]]+[cls('ESTOP',0.2,0.2,'rgb(255, 0, 255)'),cls('HV54',0.25,0.2,'rgb(255, 64, 0)'),cls('P12',0.6,0.2,'rgb(255, 200, 0)')]
pat=[]
for n in nets:
    if domains.is_estop(n): pat.append(dict(netclass='ESTOP',pattern=n))
    elif domains.is_hv(n): pat.append(dict(netclass='HV54',pattern=n))
    elif n in P12: pat.append(dict(netclass='P12',pattern=n))
ns['netclass_patterns']=pat; ns['netclass_assignments']=None
json.dump(d,open(pro,'w',newline=chr(10)),indent=2)   # LF on every platform, so the file doesn't change wholesale
s=open(dru,newline='').read()
RULE="""# E-stop safety nets keep 1.5 mm to 54 V copper on every layer (LAYOUT_RULES.md, tools/domains.py); U1's package rule
# estop_at_U1 comes later in this file, so it wins inside U1's courtyard
(rule estop_to_54v
  (constraint clearance (min 1.5mm))
  (condition "A.hasNetclass('ESTOP') && B.hasNetclass('HV54')"))
"""
if 'estop_to_54v' not in s:
    k=s.find('(rule '); s=s[:k]+RULE+s[k:]
# the latch supply's leak rule, from domains.py's lists; it goes ahead of U1's package rule
NL=chr(10)
LEAKHDR=("# The latch supply chain keeps 1.5 mm to the leakage-sensitive E-stop nets (schematic/tools/domains.py LATCH_SUPPLY,"+NL+
         "# LEAK_SENSITIVE; LAYOUT_RULES.md, Leakage from the latch supply). Written by schematic/tools/handfinish_prep.py."+NL)
s=s.replace(LEAKHDR,'')
# remove the rule as written before: it ends at its condition's closing '"))' (its constraint line also ends in '))', so
# cutting at the first '))' would leave the condition behind and corrupt the file on a second run)
s=re.sub(r'\(rule latch_supply_leak\r?\n.*?"\)\)\r?\n','',s,flags=re.S)
k=s.find('# U1 (LM5069)'); k=len(s) if k<0 else k
if k==len(s) and not s.endswith(NL): s+=NL
s=s[:k]+LEAKHDR+domains.leak_rule()+s[k:]
open(dru,'w',newline='').write(s)
print('classes',[c['name'] for c in ns['classes']],'patterns',len(pat))
