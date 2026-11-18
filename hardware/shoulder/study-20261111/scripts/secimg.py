import numpy as np, trimesh, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MP
from rv import load_all, COL
d=load_all()
NAMES=dict(P1='P1 pitch bracket L01',P2='P2 roll bracket L04B',SPACER='PF03 spacer',ROLL='roll RS03',YAW='yaw RS02',PITCH='pitch RS03',HUB='shoulder hub',UA='upper arm (frozen)',FRAME='2020 frame',PBRK='torso pitch mount')
def sec(plane_o,plane_n,ax2,title,out,xlim,ylim,axes=(),notes=()):
    fig,ax=plt.subplots(figsize=(11,9))
    for k,m in d.items():
        s=m.section(plane_origin=plane_o,plane_normal=plane_n)
        if s is None: continue
        for e in s.discrete:
            P=e[:,ax2]
            if np.linalg.norm(P[0]-P[-1])<1e-3 and k not in ('PITCH','PBRK'): ax.fill(P[:,0],P[:,1],color=COL[k],alpha=0.55,lw=0)
            ax.plot(P[:,0],P[:,1],color=np.array(COL[k])*0.6,lw=1.0 if k in ('PITCH','PBRK','ROLL','YAW') else 0.7)
    for (x0,y0,x1,y1,lab) in axes:
        ax.plot([x0,x1],[y0,y1],'k-.',lw=1); ax.text(x1,y1,lab,fontsize=9)
    for (x,y,t) in notes: ax.annotate(t,(x,y),fontsize=8.5,xytext=(5,5),textcoords='offset points',bbox=dict(fc='white',ec='0.6',alpha=0.85))
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect('equal'); ax.grid(alpha=0.25); ax.set_title(title,fontsize=11)
    hs=[plt.Rectangle((0,0),1,1,color=COL[k],alpha=0.6) for k in NAMES]; ax.legend(hs,list(NAMES.values()),fontsize=8,loc='lower left',ncol=2)
    fig.tight_layout(); fig.savefig(out,dpi=110); plt.close(fig)
