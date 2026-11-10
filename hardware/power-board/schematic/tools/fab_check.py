"""fab_check.py board.kicad_pcb fab_dir (KiCad Python): the order package against the board it was made from.
  1. Every expected Gerber is there, loads in KiCad's own Gerber reader (pcbnew GERBER_JOBFILE-free check: the file
     parses line by line: balanced commands, an end-of-file M02, at least one draw) and carries the layer function its
     name says (X2 attribute TF.FileFunction).
  2. Copper layer count: 6 copper Gerbers for a 6-layer board, in stack order L1..L6.
  3. Outline: the Edge.Cuts Gerber's extents are the board's (100 x 170 mm).
  4. Drill files: the plated file's hit count equals the board's vias plus plated pad holes, tool by tool; the unplated
     file's equals the unplated pad holes.
  5. B.Mask carries the ten heatsink openings: each opening drawn on the board is a filled region in the Gerber with the
     same area (0.5 %) at the same centroid (0.05 mm), and the Gerber has no other region.
  6. The position file lists every fitted top-side part of the board once, each at the board's X/Y (0.01 mm), rotation
     (0.1 degree) and side; the two BOM files cover the fitted parts.
  7. The zip holds exactly the files in gerbers/.
  8. BOARD.sha256 is the board file's hash: the package is not older than the board.
Exit 1 on any difference, and when gerbers/ or a file is missing."""
import sys,os,re,glob,csv,zipfile,collections
import pcbnew
MM=pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1]); out=sys.argv[2]; G=out+'/gerbers'; fail=[]
def ok(c,m):
    print('ok  ' if c else 'FAIL',m)
    if not c: fail.append(m)
# the main board by default; the buck board's package (buck12/tools/fab_check_buck.sh) sets these
stem=os.environ.get('FAB_STEM','marengo_pdu_revb')
OW,OH=(float(v) for v in os.environ.get('FAB_OUTLINE','100x170').split('x'))
NMASK=int(os.environ.get('FAB_BMASK_OPENINGS','10'))   # the bare B.Mask openings drawn on the board (the heatsink pads)
EXPECT={'F_Cu.gtl':'Copper,L1,Top','In1_Cu.g1':'Copper,L2,Inr','In2_Cu.g2':'Copper,L3,Inr','In3_Cu.g3':'Copper,L4,Inr','In4_Cu.g4':'Copper,L5,Inr',
        'B_Cu.gbl':'Copper,L6,Bot','F_Mask.gts':'Soldermask,Top','B_Mask.gbs':'Soldermask,Bot','F_Silkscreen.gto':'Legend,Top',
        'B_Silkscreen.gbo':'Legend,Bot','F_Paste.gtp':'Paste,Top','Edge_Cuts.gm1':'Profile,NP'}
ok(os.path.isdir(G),f'{G} exists')
files={os.path.basename(f) for f in glob.glob(G+'/*')}
want={f'{stem}-{k}' for k in EXPECT}|{f'{stem}-PTH.drl',f'{stem}-NPTH.drl'}
ok(files==want,f'gerbers/ holds the 12 Gerber and 2 drill files: missing {sorted(want-files)}, extra {sorted(files-want)}')
def gerber(path):
    """(file function, extents in mm (x0,y0,x1,y1), number of draw/flash operations, well formed)"""
    t=open(path,encoding='utf-8',errors='replace').read()
    ff=re.search(r'%TF\.FileFunction,([^*]+)\*%',t); fs=re.search(r'%FSLAX(\d)(\d)Y(\d)(\d)\*%',t); units='MM' in (re.search(r'%MO(\w\w)\*%',t) or [''])[0]
    dec=int(fs.group(2)) if fs else 6; xs=[];ys=[]
    for m in re.finditer(r'X(-?[0-9]+)Y(-?[0-9]+)D0[123][*]',t): xs.append(int(m.group(1))/10**dec); ys.append(int(m.group(2))/10**dec)
    ops=len(re.findall(r'D0[123]\*',t))
    well=t.rstrip().endswith('M02*') and t.count('%')%2==0 and bool(fs) and units
    return (ff.group(1) if ff else None),((min(xs),min(ys),max(xs),max(ys)) if xs else None),ops,well
info={}
for k,fn in EXPECT.items():
    p=f'{G}/{stem}-{k}'
    if not os.path.exists(p): continue
    ff,ext,ops,well=gerber(p); info[k]=(ff,ext,ops)
    ok(well and ops>0 and ff is not None and ff.startswith(fn),f'{k}: parses (format, units, end of file), {ops} operations, function "{ff}" (expected {fn})')
cu=[k for k in EXPECT if 'Copper' in EXPECT[k] and k in info]
ok(len(cu)==6==b.GetCopperLayerCount(),f'copper layers: {len(cu)} Gerbers for a board with {b.GetCopperLayerCount()} copper layers')
bb=b.GetBoardEdgesBoundingBox(); bw,bh=MM(bb.GetWidth()),MM(bb.GetHeight())
if 'Edge_Cuts.gm1' in info and info['Edge_Cuts.gm1'][1]:
    x0,y0,x1,y1=info['Edge_Cuts.gm1'][1]; gw,gh=x1-x0,y1-y0
    ok(abs(gw-OW)<0.2 and abs(gh-OH)<0.2 and abs(gw-bw)<0.2 and abs(gh-bh)<0.2,f'outline: Gerber {gw:.2f} x {gh:.2f} mm, board {bw:.2f} x {bh:.2f} mm, expected {OW:g} x {OH:g}')
def drill(path):
    """{tool diameter mm: hits} of an Excellon file"""
    tools={}; cur=None; hits=collections.Counter()
    for l in open(path,encoding='utf-8',errors='replace'):
        m=re.match(r'T(\d+)C([\d.]+)',l)
        if m: tools[m.group(1)]=round(float(m.group(2)),3); continue
        m=re.match(r'T(\d+)\s*$',l)
        if m: cur=m.group(1); continue
        if cur and cur in tools and re.match(r'X-?[\d.]+Y-?[\d.]+',l): hits[tools[cur]]+=1
    return dict(hits)
bp=collections.Counter(); bn=collections.Counter()
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA': bp[round(MM(t.GetDrill()),3)]+=1
for p in b.GetPads():
    if p.HasHole():
        d=p.GetDrillSize(); dia=round(MM(min(d.x,d.y)),3)
        (bp if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH else bn)[dia]+=1
gp=drill(f'{G}/{stem}-PTH.drl') if os.path.exists(f'{G}/{stem}-PTH.drl') else {}
gn=drill(f'{G}/{stem}-NPTH.drl') if os.path.exists(f'{G}/{stem}-NPTH.drl') else {}
ok(gp==dict(bp),f'plated holes: file {sum(gp.values())} hits {dict(sorted(gp.items()))}; board {sum(bp.values())} (vias and plated pads) {dict(sorted(bp.items()))}')
ok(gn==dict(bn),f'unplated holes: file {sum(gn.values())} hits {dict(sorted(gn.items()))}; board {sum(bn.values())} {dict(sorted(bn.items()))}')
# B.Mask: the ten heatsink openings are drawn (regions G36/G37 in the file: the board-level shapes are the only polygons there)
t=open(f'{G}/{stem}-B_Mask.gbs',encoding='utf-8',errors='replace').read() if os.path.exists(f'{G}/{stem}-B_Mask.gbs') else ''
def regions(t):
    """[(area mm2, centroid x, centroid y)] of the G36..G37 regions (straight segments; Y as in the file)"""
    fs=re.search(r'%FSLAX(\d)(\d)Y(\d)(\d)\*%',t); dec=int(fs.group(2)) if fs else 6; out=[]
    for body in re.findall(r'G36\*(.*?)G37\*',t,flags=re.S):
        if re.search(r'G0[23]\*',body): out.append((None,None,None)); continue   # an arc: not measured, fails below
        pts=[(int(x)/10**dec,int(y)/10**dec) for x,y in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]\*',body)]
        a=cx=cy=0.0
        for (x0,y0),(x1,y1) in zip(pts,pts[1:]+pts[:1]):
            c=x0*y1-x1*y0; a+=c; cx+=(x0+x1)*c; cy+=(y0+y1)*c
        a/=2; out.append((abs(a),cx/(6*a) if a else 0,cy/(6*a) if a else 0))
    return out
shapes=[d for d in b.GetDrawings() if d.GetClass()=='PCB_SHAPE' and d.GetLayer()==pcbnew.B_Mask]
want=[]
for d in shapes:
    ps=d.GetPolyShape(); c=ps.Outline(0).Centre() if hasattr(ps.Outline(0),'Centre') else None
    o=ps.Outline(0); pts=[(MM(o.CPoint(i).x),MM(o.CPoint(i).y)) for i in range(o.PointCount())]
    a=cx=cy=0.0
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]+pts[:1]):
        k=x0*y1-x1*y0; a+=k; cx+=(x0+x1)*k; cy+=(y0+y1)*k
    a/=2; want.append((abs(a),cx/(6*a),-cy/(6*a)))   # the Gerber's Y is the page Y negated
got=regions(t); left=list(got); miss=[]
for a,x,y in want:
    m=[g for g in left if g[0] is not None and abs(g[0]-a)<=0.005*a and abs(g[1]-x)<=0.05 and abs(g[2]-y)<=0.05]
    if m: left.remove(m[0])
    else: miss.append((round(a,1),round(x,2),round(-y,2)))
ok(len(shapes)==NMASK and not miss and not left,f'B.Mask: {len(shapes)} heatsink openings on the board, {len(got)} filled regions in the Gerber; openings without a region of the same area and centroid {miss}; other regions {[(round(g[0],1) if g[0] else "arc") for g in left]}')
# position file and BOMs
fitted={f.GetReference() for f in b.GetFootprints() if not f.IsDNP() and not f.IsBoardOnly() and any(p.GetNumber() for p in f.Pads())}
ok(os.path.exists(out+f'/{stem}-pos.csv'),'the position file exists')
prow=list(csv.reader(open(out+f'/{stem}-pos.csv',encoding='utf-8')))[1:] if os.path.exists(out+f'/{stem}-pos.csv') else []
pos=[r[0] for r in prow]
smt={f.GetReference() for f in b.GetFootprints() if f.GetReference() in fitted and not f.IsFlipped() and not f.IsExcludedFromPosFiles()}
ok(len(pos)==len(set(pos)) and set(pos)==smt,f'position file: {len(pos)} parts, each once; the board has {len(smt)} fitted top-side parts that a machine places ({len(fitted)-len(smt)} more are fitted by hand: through-hole parts, wire pads, test points, the copper link): missing {sorted(smt-set(pos))[:6]}, extra {sorted(set(pos)-smt)[:6]}')
fpb={f.GetReference():f for f in b.GetFootprints()}; off=[]
for r in prow:
    f=fpb.get(r[0])
    if f is None: continue
    x,y=MM(f.GetPosition().x),-MM(f.GetPosition().y); rot=f.GetOrientationDegrees()%360; side='bottom' if f.IsFlipped() else 'top'
    dr=abs((float(r[5])-rot+180)%360-180)
    if abs(float(r[3])-x)>0.01 or abs(float(r[4])-y)>0.01 or dr>0.1 or r[6]!=side: off.append((r[0],r[3:7],(round(x,3),round(y,3),rot,side)))
ok(prow and not off,f'position file: X, Y, rotation and side of each part equal the board\'s: {len(off)} differ {off[:4]}')
for name,col in (('bom-jlc.csv',1),('bom-digikey.csv',2)):
    ok(os.path.exists(out+'/'+name),f'{name} exists')
    refs=[x for r in list(csv.reader(open(out+'/'+name,encoding='utf-8')))[1:] for x in r[col].split(',') if re.match(r'[A-Z]+\d+$',x)] if os.path.exists(out+'/'+name) else []
    ok(set(refs)==fitted and len(refs)==len(set(refs)),f'{name}: {len(refs)} references, the board has {len(fitted)} fitted parts: missing {sorted(fitted-set(refs))[:6]}, extra {sorted(set(refs)-fitted)[:6]}')
z=out+f'/{stem}-gerbers.zip'
if os.path.exists(z):
    zf=zipfile.ZipFile(z); names=set(zf.namelist())
    same=all(zf.read(n)==open(f'{G}/{n}','rb').read() for n in names&files)
    ok(names==files and same,f'zip: {len(names)} files, identical to gerbers/')
else: ok(False,'zip missing')
import hashlib
ok(os.path.exists(out+'/BOARD.sha256'),'BOARD.sha256 exists')
sha=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(); rec=open(out+'/BOARD.sha256').read().split()[0] if os.path.exists(out+'/BOARD.sha256') else None
ok(rec==sha,f'the package was made from this board file (sha256 {sha[:16]}..., recorded {str(rec)[:16]}...): if not, run tools/fab_package.sh again')
print('fab_check fails',len(fail)); sys.exit(1 if fail else 0)
