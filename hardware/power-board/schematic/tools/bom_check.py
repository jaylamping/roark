"""bom_check.py <tools dir> <main net.net> <power-board dir> [<buck net.net>] (plain Python): the BOM and kit files
against the netlists.
  1. bom-rev-B.csv is exactly what tools/bom.py writes from the main netlist (and buck12/bom-buck12.csv from the buck
     netlist, when it is given).
  2. kit-2sets.csv lists every fitted part of each board once, each row's counts follow its references, and its rows
     for the pigtail connectors (main J24, buck J1) carry the netlist's value text.
  3. The pinout written in the pigtail connector's value ("1-2 +VIN, 3-4 GND, 5 ON/OFF (low = on), 6 +3V3_PI, ...") is the
     netlist's: each listed pin is on the net the text names.
Exit 1 on any difference."""
import sys,csv,re,io
sys.path.insert(0,sys.argv[1]); from sx import *
PB=sys.argv[3]; fail=[]
def ok(c,m):
    print('ok  ' if c else 'FAIL',m)
    if not c: fail.append(m)
def load(path):
    N=parse(open(path,encoding='utf-8').read()); pin={}
    for net in getall(get(N,'nets'),'net'):
        nm=str(get(net,'name')[1]).lstrip('/')
        for x in getall(net,'node'): pin[(str(get(x,'ref')[1]),str(get(x,'pin')[1]))]=nm
    comp={str(get(c,'ref')[1]):c for c in getall(get(N,'components'),'comp')}
    return N,pin,comp
def bom_rows(N):
    """the rows tools/bom.py writes"""
    G={}
    for c in getall(get(N,'components'),'comp'):
        r=str(get(c,'ref')[1]); v=str(get(c,'value')[1]); fp=get(c,'footprint'); fp=str(fp[1]) if fp else ''
        d=any(str(get(p,'name')[1])=='dnp' for p in getall(c,'property'))
        G.setdefault((v,fp,d),[]).append(r)
    key=lambda s:(re.match(r'[A-Za-z#]+',s).group(),int(re.search(r'\d+',s).group()))
    rows=sorted(G.items(),key=lambda kv:key(sorted(kv[1],key=key)[0]))
    return [['Refs','Value','Footprint','Qty','DNP']]+[[','.join(sorted(rs,key=key)),v,fp,str(len(rs)),'DNP' if d else ''] for (v,fp,d),rs in rows]
def read_csv(path): return [r for r in csv.reader(open(path,encoding='utf-8',newline=''))]
ALIAS={'+VIN':'BRK_F','ON/OFF':'BRK_ON','SCL':'I2C_SCL','SDA':'I2C_SDA','VIN':'VIN','EN':'EN'}
def pinout(text):
    """{pin: name} from '1-2 +VIN, 3-4 GND, 5 ON/OFF (low = on), 6 +3V3_PI, ...'"""
    out={}
    for m in re.finditer(r'(\d+)(?:-(\d+))?\s+([+\w/]+)',text.split(':',1)[1]):
        for p in range(int(m[1]),int(m[2] or m[1])+1): out[p]=m[3]
    return out
kit=read_csv(PB+'/kit-2sets.csv')
for label,netf,bomf,board,rx,alias in (('main',sys.argv[2],PB+'/bom-rev-B.csv','main',r'Buck board pigtail',ALIAS),
                                       ('buck',sys.argv[4] if len(sys.argv)>4 else None,PB+'/buck12/bom-buck12.csv','buck',r'J24 mate',None)):
    if not netf: continue
    N,pin,comp=load(netf)
    want=bom_rows(N); have=read_csv(bomf)
    diff=[(i+1,h,w) for i,(h,w) in enumerate(zip(have,want)) if h!=w]
    ok(have==want,f'{bomf.split("/")[-1]} equals tools/bom.py on the {label} netlist'+(f': line {diff[0][0]} has {diff[0][1][:2]}, netlist gives {diff[0][2][:2]}' if diff else '' if have==want else f': {len(have)} rows, netlist gives {len(want)}'))
    # the kit lists every fitted part of this board once, and each row's counts follow its references
    fitted={r for r,c in comp.items() if not any(str(get(p_,'name')[1])=='dnp' for p_ in getall(c,'property'))}
    krows=[r for r in kit if len(r)>5 and r[0]==board]; kref=[x for r in krows for x in r[1].split(',')]
    wrong=[r[1][:24] for r in krows if not (len(r[1].split(','))==int(r[4]) and int(r[5])==2*int(r[4]))]
    ok(set(kref)==fitted and len(kref)==len(set(kref)) and not wrong,f'kit-2sets.csv {board} rows cover the fitted parts of the {label} netlist: missing {sorted(fitted-set(kref))[:8]}, extra {sorted(set(kref)-fitted)[:8]}, rows with wrong counts {wrong[:5]}')
    j=[r for r,c in comp.items() if re.match(rx,str(get(c,'value')[1]))]
    ok(len(j)==1,f'{label}: one pigtail connector ({j})')
    if len(j)!=1: continue
    j=j[0]; val=str(get(comp[j],'value')[1])
    rows=[r for r in kit if len(r)>2 and r[0]==board and r[1]==j]
    ok(len(rows)==1 and rows[0][2]==val,f'kit-2sets.csv {board} {j} carries the netlist value'+('' if rows and rows[0][2]==val else f': kit has "{rows[0][2] if rows else None}"'))
    if alias is None:   # the buck board's own net names differ: its text must name the same pins as the main board's
        ok(pinout(val)==MAINPINS,f'{label} {j} value lists the same pinout as the main board\'s J24')
    else:
        MAINPINS=pinout(val); bad=[(p,nm,pin.get((j,str(p)))) for p,nm in MAINPINS.items() if pin.get((j,str(p)))!=alias.get(nm,nm)]
        ok(len(MAINPINS)==12 and not bad,f'{label} {j} value text matches the netlist pin for pin'+(f': {bad}' if bad else ''))
print('bom_check fails',len(fail)); sys.exit(1 if fail else 0)
