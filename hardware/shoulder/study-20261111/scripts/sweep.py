import numpy as np, trimesh, json
from scipy.spatial import cKDTree
from rv import load_all
d=load_all()
rng=np.random.default_rng(0)
def samp(m,spacing=0.5):
    n=int(m.area/spacing**2); p,_=trimesh.sample.sample_surface_even(m,n,seed=1); return p
P={k:samp(m) for k,m in d.items()}
# split rotors
def split(p,axis,c,face,rot_r,depth):
    # axis index, c=(a,b) centre in the other two coords, face position along axis, sign toward output
    o=[i for i in range(3) if i!=axis]
    r=np.hypot(p[:,o[0]]-c[0],p[:,o[1]]-c[1]); s=np.sign(depth)
    rot=(r<rot_r)&(np.abs(p[:,axis]-face)<abs(depth))
    return p[~rot],p[rot]
P['PITCH'],P['PITCH_ROT']=split(P['PITCH'],0,(424.86,-0.014),97.0,23.6,-4.5)   # output toward +X; rotor within 4.5 of face
P['PITCH'],P['PITCH_ROT']=P['PITCH'],P['PITCH_ROT']
P['ROLL'],P['ROLL_ROT']=split(P['ROLL'],2,(170.49,424.86),30.64,23.6,-4.5)
P['YAW'],P['YAW_ROT']=split(P['YAW'],1,(170.49,5.99),319.86,21.6,-3.2)
for k in P: print(k,len(P[k]))
np.savez('samples.npz',**P)
