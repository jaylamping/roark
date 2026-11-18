import numpy as np, json, sys
from scipy.spatial import cKDTree
P=dict(np.load('samples2.npz'))
def R(axis,deg):
    t=np.radians(deg); c,s=np.cos(t),np.sin(t)
    if axis==0: return np.array([[1,0,0],[0,c,-s],[0,s,c]])
    if axis==1: return np.array([[c,0,s],[0,1,0],[-s,0,c]])
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def sweep(name,axis,origin,moving,fixed,angles,sign=1,step=2):
    trees={f:cKDTree(P[f]) for f in fixed}
    res={}
    for a in angles:
        Rm=R(axis,sign*a); row={}
        for m in moving:
            q=(P[m][::step]-origin)@Rm.T+origin
            for f in fixed:
                dd,_=trees[f].query(q,distance_upper_bound=40); row[f'{m}|{f}']=float(dd.min()) if np.isfinite(dd.min()) else 40.0
        res[a]=row; print(name,a,round(min(row.values()),2),min(row,key=row.get),flush=True)
    json.dump(res,open(f'sweep_{name}.json','w'))
which=sys.argv[1]
if which=='pitch':
    sweep('pitch',0,np.array([0,424.86,-0.014]),['P1','ROLL','SPACER','P2','YAW','HUB','UA'],['PITCH','PBRK','FRAME'],list(range(-180,181,3)),sign=-1)
if which=='roll':
    sweep('roll',2,np.array([170.49,424.86,0]),['SPACER','P2','YAW','HUB','UA'],['ROLL','P1','PITCH','PBRK','FRAME'],list(range(-180,181,3)),sign=1)
if which=='yaw':
    sweep('yaw',1,np.array([170.49,0,5.99]),['HUB','UA'],['YAW','P2','ROLL','P1'],list(range(0,360,5)),sign=1)
