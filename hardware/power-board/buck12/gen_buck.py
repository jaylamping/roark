"""12 V, 12 A buck board (rev B5): the 12 V converter and, since split S1, the 12 V distribution, on the -X rail at the J24 pigtail.
Edit this, not the .kicad_sch. Run: python -X utf8 gen_buck.py <this folder>, then ERC (regen_buck.sh in this folder).
Starting point: TI LM5146 datasheet SNVSBV0A, application circuit 2 (48 V to 12 V, 8 A, 400 kHz): same L, C and
compensation, uprated FETs and inductor for 12 A, our UVLO, an input filter and the J24 interface (split S1 pinout)."""
import os,sys,textwrap
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','schematic','gen'))
import kit
kit.PROJ='marengo_buck12'; kit.LIBNAME='marengo_buck12'
from kit import *
LIBN=kit.LIBNAME
wfile(OUT+'/fp-lib-table').write('(fp_lib_table\n\t(version 7)\n\t(lib (name "marengo_buck12")(type "KiCad")(uri "${KIPRJMOD}/marengo_buck12.pretty")(options "")(descr "buck board footprints (tools/fp_buck.py)"))\n)\n')
wfile(OUT+'/sym-lib-table').write('(sym_lib_table\n\t(version 7)\n\t(lib (name "marengo_buck12")(type "KiCad")(uri "${KIPRJMOD}/marengo_buck12.kicad_sym")(options "")(descr "buck board symbols"))\n)\n')
s=Sheet('buck12','marengo 12 V buck board (rev B5)','A1',comment='On the J24 pigtail (split S1 pinout). Main board: hardware/power-board/schematic.')
s.file='marengo_buck12.kicad_sch'
def head(t,at): s.text(t,at,size=2,bold=True)
def wnote(t,at,w): s.text('\n'.join(textwrap.fill(l,w) for l in t.split('\n')),at,size=1.27)
def Q(lid,val,at,b,e,c): r=s.nref('Q'); nic(s,lid,r,val,at,SOT23,{'1':b,'2':e,'3':c}); return r
mkic('LM5146',[('1','EN/UVLO','input'),('2','RT','passive'),('3','SS/TRK','passive'),('4','COMP','output'),('5','FB','input'),('6','AGND','power_in'),('7','SYNCOUT','output'),('8','SYNCIN','input'),('9','NC','passive'),('10','PGOOD','open_collector'),('11','ILIM','passive'),('12','PGND','power_in'),('13','LO','output'),('14','VCC','passive'),('15','EPC','passive'),('16','NC','passive'),('17','BST','passive'),('18','HO','output'),('19','SW','passive'),('20','VIN','power_in'),('21','EP','passive')],
     'Package_DFN_QFN:Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm_ThermalVias','https://www.ti.com/lit/ds/symlink/lm5146.pdf','100 V synchronous buck controller, voltage mode with line feed-forward, 7.5 V drivers')
head('12 V buck: LM5146, 48 V to 12 V, 12 A, 400 kHz',(20,20))
nic(s,'Connector_Generic:Conn_02x06_Odd_Even','J1','J24 mate: 1-2 +VIN, 3-4 GND, 5 ON/OFF (low = on), 6 +3V3_PI, 7-8 GND, 9 SP_EN, 10 GND, 11 SCL, 12 SDA',(40,70),'Connector_Molex:Molex_Micro-Fit_3.0_43045-1212_2x06_P3.00mm_Vertical',
    {'1':'VIN_P','2':'VIN_P','3':'GND','4':'GND','5':'ON_N','6':'+3V3_PI','7':'GND','8':'GND','9':'SP_EN','10':'GND','11':'I2C_SCL','12':'I2C_SDA'})
g=Grid(s,80,50,17,30,300)
g.D('SK810L-TP','VIN_P','GND',SMC); g.C('1uF 100V X7R','VIN_P','GND',C1210); g.L('2.2uH XAL7030-222MEC','VIN_P','VIN','Inductor_SMD:L_Coilcraft_XAL7030-222')
g.CP('47uF 100V EMVH101ARA470MKE0S','VIN','GND','marengo_buck12:CP_Elec_12.5x13.5_ChemiCon'); g.C('2.2uF 100V X7R','VIN','GND',C1210,k=5); g.C('100nF 100V X7R','VIN','GND',C805)
g.F('VIN_P'); g.F('VIN'); g.F('GND')
nic(s,LIBN+':LM5146','U1','LM5146RGYR',(120,140),'Package_DFN_QFN:Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm_ThermalVias',
    {'1':'EN','2':'RT','3':'SS','4':'COMP','5':'FB','6':'GND','7':None,'8':'GND','9':None,'10':None,'11':'ILIM','12':'GND','13':'LO','14':'VCC','15':'GND','16':None,'17':'BST','18':'HO','19':'SW','20':'VIN_C','21':'GND'},ds='https://www.ti.com/lit/ds/symlink/lm5146.pdf')
nfet5(s,'Q1','BSC070N10NS5ATMA1',(200,120),'VIN','HO','SW')
nfet5(s,'Q2','BSC040N10NS5ATMA1',(200,160),'SW','LO','GND'); s.refc['Q']=2
g=Grid(s,230,100,17,30,330)
g.L('6.8uH XAL1010-682MED','SW','VOUT','Inductor_SMD:L_Coilcraft_XAL1010-XXX'); g.C('22uF 25V X7R','VOUT','GND',C1210,k=5); g.F('VOUT')
g=Grid(s,160,190,15,30,330)
g.R('2.2R','VIN','VIN_C',R603); g.C('100nF 100V X7R','VIN_C','GND',C805); g.F('VIN_C'); g.R('300k 1%','VIN','EN',R1206); g.R('12.4k 1%','EN','GND',R603)
g.R('24.9k 1%','RT','GND'); g.C('47nF X7R','SS','GND'); g.C('2.2uF 25V X7R','VCC','GND',C805); g.D('BAT46W','VCC','VOUT')
g.nl(); g.R('2.2R','SW','BST_R',R603); g.C('100nF 25V X7R','BST','BST_R',C603); g.R('402R 1%','ILIM','SW'); g.C('15pF 100V C0G','ILIM','GND')
g.R('0R (loop injection)','VOUT','VOUT_S',R603); g.R('21k 1%','VOUT_S','FB'); g.R('1.5k 1%','FB','GND')
g.nl(); g.R('100R','VOUT_S','FB_Z'); g.C('1nF C0G','FB_Z','FB'); g.R('8.06k 1%','COMP','COMP_Z'); g.C('4.7nF C0G','COMP_Z','FB',C603); g.C('10pF C0G','COMP','FB')
g.R('220k','VIN','ON_N',R1206); g.R('10k','ON_N','ON_B')
Q('Transistor_BJT:Q_NPN_BEC','MMBT3904',(320,250),'ON_B','GND','EN')
wnote('''Input: SK810L crowbar (a reversed pigtail clamps at about 1 V; U7 on the main board limits and times out), 1 uF at the connector, 2.2 uH filter, 47 uF aluminium (Chemi-Con MVH, 12.5 mm can, 0.33 Ohm ESR damps the filter and the pigtail: 24 dB of margin against the converter's input impedance at 30 V, 158 W), 5 x 2.2 uF hot-loop ceramics at Q1. tools/absorber_sim.py (main board) runs the bank-trip spike through U7, F2, the pigtail and this filter.
UVLO: 300k / 12.4k: on at 30.2 V, off at 27.2 V (10 uA hysteresis current). Below the 30.5 V worst sag at 90 A from a 38 V pack, so motor load can't brown out compute before the BMS does; the Pi still shuts down on its load-aware threshold.
ON/OFF: the main board's 2N7002 pulls pin 5 low through 220R when U7's PGD is good. Pin 5 open: 220k from VIN biases the NPN, which holds EN low (off). Pin 5 low: NPN off, EN rises: on. Pin 5 idles at about 2.7 V, like the DVE's.
Power train (TI design 2 uprated): 400 kHz (RT 24.9k), 6.8 uH 8.9 mOhm 21.8 A Isat, 3.3 A ripple; Q1 BSC070N10NS5 (low Qgd), Q2 BSC040N10NS5. Valley limit by Q2 RDS(on) (LM5146 eq. 6: I_OUT,CL = I_RDSON x R_ILIM / RDS(on)Q2 + dIL/2): 200 uA x 402R = 80.4 mV; cold, RDS(on) 3.5-4.5 mOhm: valley 17.9-23 A, output limit 19.5-24.6 A; hot (TJ 100 C, I_RDSON +34 %, RDS(on) about x1.6): valley 15-19 A, output 16.6-20.9 A: over the 12 A rating at every corner. C18 15 pF 100 V C0G: R_ILIM x C_ILIM = 6.0 ns (TI: about 6 ns); ILIM swings with SW to VIN. Hiccup on overload.
Output: 12.0 V (0.8 V x (1 + 21k / 1.5k)), 5 x 22 uF at VOUT plus the 330 uF bulk cap on +12V behind RS1 (12 V distribution, below). Compensation is TI's for this L and 5 x 22 uF only (40 kHz crossover): recheck it for the 330 uF and measure the loop with an injection resistor in place of the 0R before loading. VCC from VOUT through BAT46W (TI's D1) cuts bias loss.
Loss at 12 A, 48 V (est): Q1 0.4 W conduction + 1.2 W switching, Q2 0.7 W, inductor 1.3 W, controller 0.3 W: about 4 W, 97 %. Board: about 60 x 85 mm with the 12 V distribution and its six outputs, bolted to the rail with a thermal pad like the DVE.''',(20,280),170)
# ---------- 12 V distribution (split S1, 2026-11-09: moved here from the main board, same parts and values) ----------
head('12 V distribution: meter, fused outputs, SPARE_SW and SPARE_ON eFuses',(20,330))
s.refc['J']=1   # J1 is the pigtail
SHK='Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm'; INA='INA237AIDGSR'; INADS='https://www.ti.com/lit/ds/symlink/ina237.pdf'
MF2='Connector_Molex:Molex_Micro-Fit_3.0_43045-0212_2x01_P3.00mm_Vertical'; MF4='Connector_Molex:Molex_Micro-Fit_3.0_43045-0412_2x02_P3.00mm_Vertical'
EF='Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm'; EFDS='https://www.ti.com/lit/ds/symlink/tps2595.pdf'
mkic('TPS259541DSG',[('1','dVdt','passive'),('2','EN/UVLO','input'),('3','IN','passive'),('4','IN','passive'),('5','OUT','passive'),('6','FLT','open_collector'),('7','ILM','passive'),('8','GND','power_in'),('9','EP','power_in')],EF,EFDS,'TPS2595 eFuse, 18 V 4 A 34 mOhm, 13.7 V clamp, auto-retry')
nic(s,'Device:R_Shunt','RS1','2mR 2512 Kelvin WSK25122L000FEA',(40,360),SHK,{'1':'VOUT','2':'SH12_P','3':'SH12_N','4':'+12V'})
nic(s,'Sensor_Energy:INA228','U2',INA,(90,360),'Package_SO:TSSOP-10_3x3mm_P0.5mm',{'1':'I2C_SCL','2':'+3V3_PI','3':None,'4':'I2C_SDA','5':'I2C_SCL','6':'+3V3_PI','7':'GND','8':'+12V','9':'SH12_N','10':'SH12_P'},ds=INADS)
for nm,x,n in (('Jetson',140,'+12V_JET'),('Pi 5 V buck',175,'+12V_PI'),('fans',210,'+12V_FAN')):
    nic(s,'Connector_Generic:Conn_01x02',s.nref('J'),'12 V to '+nm+' (fused)',(x,360),MF2,{'1':n,'2':'GND'})
nic(s,LIBN+':TPS259541DSG','U3','TPS259541DSGR',(40,410),EF,{'1':'SP_DV','2':'SP_EN','3':'+12V','4':'+12V','5':'SP_SW1','6':None,'7':'SP_ILM','8':'GND','9':'GND'},ds=EFDS)
nic(s,'Device:R_Shunt','RS2','5mR 2512 Kelvin WSK25125L000FEA',(90,410),SHK,{'1':'SP_SW1','2':'SHSP_P','3':'SHSP_N','4':'SPARE_SW'})
nic(s,'Sensor_Energy:INA228','U4',INA,(140,410),'Package_SO:TSSOP-10_3x3mm_P0.5mm',{'1':'+3V3_PI','2':'I2C_SCL','3':None,'4':'I2C_SDA','5':'I2C_SCL','6':'+3V3_PI','7':'GND','8':'SPARE_SW','9':'SHSP_N','10':'SHSP_P'},ds=INADS)
nic(s,'Connector_Generic:Conn_01x04',s.nref('J'),'SPARE_SW, off with the motors (2 x 2, keyed apart from the 2-pin outputs)',(190,410),MF4,{'1':'SPARE_SW','2':'GND','3':'SPARE_SW','4':'GND'})
nic(s,LIBN+':TPS259541DSG','U5','TPS259541DSGR',(40,460),EF,{'1':'SPON_DV','2':'SPON_EN','3':'+12V','4':'+12V','5':'SPARE_ON','6':None,'7':'SPON_ILM','8':'GND','9':'GND'},ds=EFDS)
nic(s,'Connector_Generic:Conn_01x02',s.nref('J'),'SPARE_ON, always on',(90,460),MF2,{'1':'SPARE_ON','2':'GND'})
g=Grid(s,240,350,17,30,400)
for o,f in (('+12V_JET','5A 32V 0466005'),('+12V_PI','5A 32V 0466005'),('+12V_FAN','2A 32V 0466002')): g.two('Device:Fuse','F',f,'+12V',o,'Fuse:Fuse_1206_3216Metric')
g.C('100nF','+3V3_PI','GND',C603,k=2); g.CP('330uF 25V EEH-ZA1E331V','+12V','GND','marengo_buck12:CP_Elec_10x10.5_ZA'); g.Z('SMBJ15A','+12V','GND','Diode_SMD:D_SMB')
g.nl(); g.R('68k','SP_EN','GND',R603); g.R('499R 1%','SP_ILM','GND',R603); g.C('3.3nF C0G','SP_DV','GND',C603); g.C('100nF 25V','+12V','GND',C603); g.C('22uF 25V','SP_SW1','GND',C1210); g.D('B340A-13-F','SP_SW1','GND','Diode_SMD:D_SMA')
g.nl(); g.R('100k','+12V','SPON_EN',R603); g.R('33k','SPON_EN','GND',R603); g.R('1.02k 1%','SPON_ILM','GND',R603); g.C('3.3nF C0G','SPON_DV','GND',C603); g.C('100nF 25V','+12V','GND',C603); g.D('B340A-13-F','SPARE_ON','GND','Diode_SMD:D_SMA')
g.F('+12V'); g.F('+3V3_PI'); g.F('SP_EN')
wnote('''Moved from the main board (split S1): the 12 V meter (0x4D) and SPARE_SW meter (0x47) on the Pi's I2C, powered by the Pi's 3.3 V through J1 pin 6; pull-ups only at the Pi.
SP_EN (J1 pin 9, between GND pins) comes from the main board's RUN through 100k and a series diode; the 68k here pulls EN low, so SPARE_SW is off when RUN drops, the diode opens or the pigtail is unplugged (fail-off). EN about 2.6 V with RUN up.
SPARE_SW: limit 3.87-4.42 A (499R), dV/dt 3.3 nF about 12 V/ms. SPARE_ON: unswitched, about 2 A limit. B340A clamps on both outputs. SMBJ15A: servo back-feed clamp on +12V.
330 uF + 5 x 22 uF now sit at the converter output, not at the far end of the pigtail: recheck the compensation and measure the loop at the 0R injection point before loading.\nThe DVE fallback no longer plugs into J24: this board has no 12 V input, and the old DVE adapter pinout puts 12 V on SCL and SP_EN.''',(20,500),170)
writelib()
s.write([('/'+kit.ROOT,'1')])
print('ok',{k:v for k,v in s.refc.items() if not k.startswith('#')})
