import numpy as np
P=dict(np.load('samples.npz'))
def resplit(a,b,ax,c,rr):
    p=np.vstack([P[a],P[b]]); o=[i for i in range(3) if i!=ax]
    r=np.hypot(p[:,o[0]]-c[0],p[:,o[1]]-c[1]); st=r>=rr
    P[a]=p[st]; P[b]=p[~st]
resplit('PITCH','PITCH_ROT',0,(424.86,-0.014),23.8)
resplit('ROLL','ROLL_ROT',2,(170.49,424.86),23.8)
# RS02: rotor = r<21.8 and Y<323.5
p=np.vstack([P['YAW'],P['YAW_ROT']]); r=np.hypot(p[:,0]-170.49,p[:,2]-5.99); rot=(r<21.8)&(p[:,1]<323.5)
P['YAW']=p[~rot]; P['YAW_ROT']=p[rot]
np.savez('samples2.npz',**P)
