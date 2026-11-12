"""Render layout/renders/routed_<layer>.png (one per copper layer: pads, tracks, vias, pours, open connections as
ratsnest) and routed_critical_nets.png (Kelvin pairs, gates/UVLO, E-stop class, all layers) from tools/render_export.py's
JSON. Plain Python (matplotlib). Usage: python tools/render_routed.py <copper.json> <renders dir>"""
import json,os,re,sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Circle
from matplotlib.collections import PatchCollection,LineCollection
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import domains
D=json.load(open(sys.argv[1])); OUT=sys.argv[2]
X0,Y0,X1,Y1=D['edge']; NAMES=D['layers']; NL=len(NAMES)
OZ={0:'2 oz',NL-1:'2 oz'}
PTMM=11.92*72*.98/(X1-X0+2)   # points per mm on the page, so tracks draw at their real width
def zcol(n): return '#c6d8f0' if n=='GND' else '#f3d0d0' if domains.is_hv(n) else '#e8e0c0'
def frame(title):
    f,ax=plt.subplots(figsize=(11.92,20.2),dpi=100); ax.set_xlim(X0-1,X1+1); ax.set_ylim(Y1+1,Y0-1); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([]); ax.add_patch(plt.Rectangle((X0,Y0),X1-X0,Y1-Y0,fill=False,lw=1)); ax.set_title(title,fontsize=14)
    f.subplots_adjust(left=.01,right=.99,top=.975,bottom=.01); return f,ax
def polypatches(ax,its,color,z,alpha=1):
    ps=[Polygon(p,closed=True) for it in its for p in it['p'] if len(p)>2]
    ax.add_collection(PatchCollection(ps,facecolor=color,edgecolor='none',zorder=z,alpha=alpha))
for i,name in enumerate(NAMES):
    its=[it for it in D['items'] if it['L']==i]
    f,ax=frame(f'L{i+1} ({name}{", "+OZ[i] if i in OZ else ""}): copper, open connections as ratsnest ({len(D["open"])})')
    for n in sorted({it['net'] for it in its if it['k']=='zone'}):
        polypatches(ax,[it for it in its if it['k']=='zone' and it['net']==n],zcol(n),1)
    polypatches(ax,[it for it in its if it['k']=='pad'],'#e3a73d',3,.85)
    tr=[it for it in its if it['k']=='trk']
    ax.add_collection(LineCollection([(t['a'],t['b']) for t in tr],linewidths=[t['w']*PTMM for t in tr],colors='#2e7d32',zorder=4,capstyle='round'))
    ax.add_collection(PatchCollection([Circle(v['c'],v['r']*.6) for v in its if v['k']=='via'],facecolor='#4a3030',zorder=5))
    ax.add_collection(LineCollection(D['open'],colors='magenta',linewidths=1,zorder=6))
    mk=[Polygon(p,closed=True) for it in its if it['k']=='mask' for p in it['p'] if len(p)>2]
    if mk:
        ax.add_collection(PatchCollection(mk,facecolor='none',edgecolor='black',linewidths=1.6,linestyles='--',zorder=7))
        f.text(.02,.004,'dashed black: bare heatsink pads (solder-mask openings on B.Mask)',fontsize=11)
    f.savefig(os.path.join(OUT,f'routed_{name.replace(".","_")}.png')); plt.close(f)
# critical nets
KEL=re.compile(r'/SH\w*_[PN]$'); GATE=re.compile(r'/(G\d|G_L\d|GC_L\d|GATE|UVLO|BRK_GATE)')
def cat(n):
    if KEL.match(n): return '#d62728' if n.endswith('_P') else '#1f77b4'
    if domains.is_estop(n): return '#ff7f0e'
    if GATE.match(n): return '#2ca02c'
f,ax=frame('Critical nets, all layers: Kelvin pairs (P red / N blue), gates and UVLO (green), E-stop class (orange)')
polypatches(ax,[it for it in D['items'] if it['k']=='zone' and it['L'] in (0,NL-1)],'#ececec',1)
polypatches(ax,[it for it in D['items'] if it['k']=='pad' and it['L'] in (0,NL-1)],'#d4d4d4',2)
for t in D['items']:
    if t['k']!='trk': continue
    c=cat(t['net'])
    if c: ax.plot([t['a'][0],t['b'][0]],[t['a'][1],t['b'][1]],color=c,lw=2,ls='-' if t['L'] in (0,NL-1) else '--',zorder=4,solid_capstyle='round')
ax.add_collection(LineCollection(D['open'],colors='magenta',linewidths=.8,linestyles=':',zorder=6))
f.text(.02,.004,'solid = outer layer, dashed = inner layer, magenta dotted = open connection',fontsize=11)
f.savefig(os.path.join(OUT,'routed_critical_nets.png')); plt.close(f)
print('rendered',NL+1,'pictures to',OUT)
