import numpy as np, trimesh, json
out={}
def slices(name,axis,vals):
    m=trimesh.load(f'w/{name}.stl'); res=[]
    for v in vals:
        o=np.zeros(3); o[axis]=v; n=np.zeros(3); n[axis]=1
        s=m.section(plane_origin=o,plane_normal=n)
        if s is None: res.append((v,0,0)); continue
        pl,_=s.to_2D(); a=sum(p.area for p in pl.polygons_full)
        res.append((round(v,1),round(a,1),len(pl.polygons_full)))
    return res
def thick(name,n=60000):
    m=trimesh.load(f'w/{name}.stl'); p,fi=trimesh.sample.sample_surface_even(m,n,seed=2)
    nr=m.face_normals[fi]; o=p-nr*1e-3
    loc,ir,_=m.ray.intersects_location(o,-nr,multiple_hits=False)
    t=np.full(len(p),np.nan); t[ir]=np.linalg.norm(loc-o[ir],axis=1)
    k=np.isfinite(t); tt=t[k]; pp=p[k]
    idx=np.argsort(tt)[:15]
    return dict(p1=round(float(np.percentile(tt,1)),2),p5=round(float(np.percentile(tt,5)),2),median=round(float(np.median(tt)),2),
                thinnest=[(round(float(tt[i]),2),pp[i].round(1).tolist()) for i in idx[::3]])
out['P1_X']=slices('P1',0,np.arange(97.5,131,1.5))
out['P2_Y']=slices('P2',1,np.arange(352.5,454,3))
out['P2_Z']=slices('P2',2,np.arange(-36,72,3))
out['HUB_Y']=slices('HUB',1,np.arange(288.5,320,1.5))
for k in ['P1','P2','SPACER','HUB']: out[k+'_thick']=thick(k); print(k,out[k+'_thick'],flush=True)
for k in ['P1_X','P2_Y','P2_Z','HUB_Y']: print(k,out[k])
json.dump(out,open('sections.json','w'),indent=0,default=float)
