"""Netlist checks for the buck board's 12 V distribution (split S1, 2026-11-09): what moved from the main board, and the
SPARE_SW enable failing off. Usage: python check_buck.py <path to schematic/tools> <buck netlist>"""
import sys
sys.path.insert(0,sys.argv[1]); from sx import *
N=parse(open(sys.argv[2]).read())
pin={}; nets={}
for net in getall(get(N,'nets'),'net'):
    nm=str(get(net,'name')[1]).lstrip('/'); nodes=[(str(get(x,'ref')[1]),str(get(x,'pin')[1])) for x in getall(net,'node')]
    nets[nm]=nodes
    for k in nodes: pin[k]=nm
comp={str(get(c,'ref')[1]):c for c in getall(get(N,'components'),'comp')}
val=lambda r:str(get(comp[r],'value')[1])
n=lambda r,p:pin.get((r,str(p)))
fail=[]; cnt=[0]
def ok(c,m):
    cnt[0]+=1; print('ok  ' if c else 'FAIL',m)
    if not c: fail.append(m)
def two(a,b,pre=('R','C')):
    return [r for r in comp if r[0] in pre and r[1].isdigit() and {n(r,1),n(r,2)}=={a,b}]
J='J1'
ok([n(J,p) for p in range(1,13)]==['VIN_P','VIN_P','GND','GND','ON_N','GND','+3V3_PI','I2C_SDA','GND','I2C_SCL','SP_EN','GND'],'J1 mates the main board J24 pin for pin')
# SPARE_SW enable: fail-off
pd=two('SP_EN','GND',('R',))
ok(len(pd)==1 and val(pd[0])=='68k' and sorted(r for r,p in nets['SP_EN'] if r[0]!='#')==sorted([J,'U3',pd[0]]) and n('U3',2)=='SP_EN',
   'SPARE_SW EN: only J1 pin 11, the eFuse EN and a 68k pull-down (off when RUN drops, the diode opens or the pigtail is unplugged)')
ok(not two('SP_EN','+3V3_PI') and not two('SP_EN','+12V'),'nothing here pulls SP_EN up')
# 12 V path
ok(n('RS1',1)=='VOUT' and n('RS1',4)=='+12V' and n('U2',9)==n('RS1',3) and n('U2',10)==n('RS1',2) and n('U2',8)=='+12V','12 V meter Kelvin on RS1, after the converter output')
ok(n('U3',3)==n('U3',4)==n('U5',3)==n('U5',4)=='+12V','both eFuses behind RS1, so the 12 V meter counts them')
ok(n('RS2',1)==n('U3',5) and n('U4',10)==n('RS2',2) and n('U4',9)==n('RS2',3) and n('U4',8)==n('RS2',4)=='SPARE_SW','RS2 Kelvin to the SPARE_SW meter')
outs={j:[n(j,p) for p in range(1,5) if n(j,p)] for j in comp if j[0]=='J' and j!=J}
ok(sum(1 for j,v in outs.items() if v==['SPARE_SW','GND','SPARE_SW','GND'])==1,'SPARE_SW on a 4-pin header, keyed apart from the 2-pin outputs')
ok(any(v==['SPARE_ON','GND'] for v in outs.values()) and n('U5',5)=='SPARE_ON','SPARE_ON output behind its eFuse')
ok(two('+12V','SPON_EN',('R',)) and val(two('SPON_EN','GND',('R',))[0])=='33k','SPARE_ON EN divider keeps EN under 6 V up to 20 V of back-feed')
for net,nm in (('+12V_JET','Jetson'),('+12V_PI','Pi buck'),('+12V_FAN','fans')):
    ok(any(v==[net,'GND'] for v in outs.values()) and any(r[0]=='F' and {n(r,1),n(r,2)}=={'+12V',net} for r in comp),nm+' output fused')
ok(all(any(r[0]=='D' and n(r,1)==o and n(r,2)=='GND' for r in comp) for o in (n('U3',5),'SPARE_ON')),'eFuse outputs clamped to GND')
ok(any(r[0]=='D' and n(r,1)=='+12V' and n(r,2)=='GND' and val(r).startswith('SMBJ15') for r in comp),'+12V back-feed TVS')
SYM={'GND':0,'+3V3_PI':1,'I2C_SDA':2,'I2C_SCL':3}
addr={0x40|(SYM[n(u,1)]<<2)|SYM[n(u,2)]:u for u in comp if val(u).startswith('INA2')}
ok(set(addr)=={0x4D,0x47} and all(n(u,4)=='I2C_SDA' and n(u,5)=='I2C_SCL' and n(u,6)=='+3V3_PI' and n(u,7)=='GND' for u in addr.values()),
   'two meters, 0x4D (12 V) and 0x47 (SPARE_SW), on the Pi bus and supply')
ok(not two('I2C_SDA','+3V3_PI',('R',)) and not two('I2C_SCL','+3V3_PI',('R',)),'no I2C pull-ups here (the Pi has them)')
print('audited',cnt[0]); print('FAILS',len(fail))
sys.exit(1 if fail else 0)
