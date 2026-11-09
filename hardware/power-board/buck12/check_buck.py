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
ok([n(J,p) for p in range(1,13)]==['VIN_P','VIN_P','GND','GND','ON_N','+3V3_PI','GND','GND','SP_EN','GND','I2C_SCL','I2C_SDA'],'J1 mates the main board J24 pin for pin (check.py checks the same list on J24)')
# SPARE_SW enable: fail-off
pd=two('SP_EN','GND',('R',))
ok(len(pd)==1 and val(pd[0])=='68k' and sorted(r for r,p in nets['SP_EN'] if r[0]!='#')==sorted([J,'U3',pd[0]]) and n('U3',2)=='SP_EN',
   'SPARE_SW EN: only J1 pin 9, the eFuse EN and a 68k pull-down (off when RUN drops, the diode opens or the pigtail is unplugged)')
ok(not two('SP_EN','+3V3_PI') and not two('SP_EN','+12V'),'nothing here pulls SP_EN up')
# 12 V path
ok(n('RS1',1)=='VOUT' and n('RS1',4)=='+12V' and n('U2',9)==n('RS1',3) and n('U2',10)==n('RS1',2) and n('U2',8)=='+12V','12 V meter Kelvin on RS1, after the converter output')
ok(n('U3',3)==n('U3',4)==n('U5',3)==n('U5',4)=='+12V','both eFuses behind RS1, so the 12 V meter counts them')
ok(n('RS2',1)==n('U3',5) and n('U4',10)==n('RS2',2) and n('U4',9)==n('RS2',3) and n('U4',8)==n('RS2',4)=='SPARE_SW','RS2 Kelvin to the SPARE_SW meter')
outs={j:[n(j,p) for p in range(1,5) if n(j,p)] for j in comp if j[0]=='J' and j!=J}
ok(sum(1 for j,v in outs.items() if v==['SPARE_SW','GND','SPARE_SW','GND'])==1,'SPARE_SW on a 4-pin header, keyed apart from the 2-pin outputs')
ok(any(v==['SPARE_ON','GND'] for v in outs.values()) and n('U5',5)=='SPARE_ON','SPARE_ON output behind its eFuse')
hi=two('+12V','SPON_EN',('R',)); lo=two('SPON_EN','GND',('R',))
ok(n('U5',2)=='SPON_EN' and [val(r) for r in hi]==['100k'] and [val(r) for r in lo]==['33k'],'SPARE_ON EN divider 100k/33k keeps EN under 6 V up to 20 V of back-feed')
ok([val(r) for r in two('SP_ILM','GND',('R',))]==['499R 1%'] and n('U3',7)=='SP_ILM' and [val(r) for r in two('SPON_ILM','GND',('R',))]==['1.02k 1%'] and n('U5',7)=='SPON_ILM'
   and all(n(u,p)=='GND' for u in ('U3','U5') for p in (8,9)),'eFuse limits: 499R on SPARE_SW (3.87-4.42 A), 1.02k on SPARE_ON (about 2 A)')
ok(val('RS1').startswith('2mR') and val('RS2').startswith('5mR'),'shunts: 12 V 2 mOhm, SPARE_SW 5 mOhm (the values software scales by)')
ok(any(val(c).startswith('330uF') for c in two('+12V','GND',('C',))),'330 uF bulk cap on +12V (servo back-feed and spare-output shorts land in it)')
for net,nm,a in (('+12V_JET','Jetson','5A'),('+12V_PI','Pi buck','5A'),('+12V_FAN','fans','2A')):
    ok(any(v==[net,'GND'] for v in outs.values()) and [val(r).split()[0] for r in comp if r[0]=='F' and {n(r,1),n(r,2)}=={'+12V',net}]==[a],nm+' output fused at '+a)
ok(all(any(r[0]=='D' and n(r,1)==o and n(r,2)=='GND' for r in comp) for o in (n('U3',5),'SPARE_ON')),'eFuse outputs clamped to GND')
ok(any(r[0]=='D' and n(r,1)=='+12V' and n(r,2)=='GND' and val(r).startswith('SMBJ15') for r in comp),'+12V back-feed TVS')
SYM={'GND':0,'+3V3_PI':1,'I2C_SDA':2,'I2C_SCL':3}
addr={0x40|(SYM.get(n(u,1),9)<<2)|SYM.get(n(u,2),9):u for u in comp if val(u).startswith('INA2')}
ok(addr.get(0x4D)=='U2' and addr.get(0x47)=='U4' and n('U2',8)=='+12V' and n('U4',8)=='SPARE_SW' and len(addr)==2 and all(n(u,4)=='I2C_SDA' and n(u,5)=='I2C_SCL' and n(u,6)=='+3V3_PI' and n(u,7)=='GND' for u in addr.values()),
   'two meters: 0x4D on the 12 V shunt, 0x47 on the SPARE_SW shunt, on the Pi bus and supply')
ok(not two('I2C_SDA','+3V3_PI',('R',)) and not two('I2C_SCL','+3V3_PI',('R',)),'no I2C pull-ups here (the Pi has them)')
print('audited',cnt[0]); print('FAILS',len(fail))
sys.exit(1 if fail else 0)
