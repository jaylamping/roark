import numpy as np, json
from scipy.spatial import cKDTree
P=dict(np.load('samples2.npz'))
T={k:cKDTree(v) for k,v in P.items()}
def gap(a,b):
    dd,ii=T[b].query(P[a],k=1,distance_upper_bound=60)
    j=np.argmin(dd); return float(dd[j]),P[a][j].round(1).tolist()
pairs=[('P1','PITCH'),('P1','PITCH_ROT'),('P1','PBRK'),('P1','FRAME'),('P1','ROLL'),('ROLL','PITCH'),('ROLL','PBRK'),('ROLL','FRAME'),
('SPACER','ROLL'),('SPACER','P1'),('P2','ROLL'),('P2','P1'),('P2','SPACER'),('P2','PITCH'),('P2','FRAME'),('P2','YAW'),
('YAW','ROLL'),('YAW','P1'),('HUB','YAW'),('HUB','P2'),('UA','YAW'),('UA','P2'),('UA','FRAME'),('UA','P1'),('UA','HUB'),('HUB','YAW_ROT')]
out={}
for a,b in pairs:
    g,p=gap(a,b); out[f'{a}-{b}']=(round(g,2),p); print(a,b,round(g,2),p)
json.dump(out,open('neutral_gaps.json','w'),indent=0)
