import numpy as np
P=dict(np.load('samples2.npz'))
def prof(axis,c,stations,parts,width=1.0,rmax=90):
    o=[i for i in range(3) if i!=axis]
    print('station | '+' | '.join(parts))
    for s in stations:
        row=[]
        for k in parts:
            p=P[k]; m=np.abs(p[:,axis]-s)<width/2
            r=np.hypot(p[m,o[0]]-c[0],p[m,o[1]]-c[1]); r=r[r<rmax]
            row.append(f'{r.min():5.1f}-{r.max():5.1f}' if len(r) else '   --    ')
        print(f'{s:6.1f} | '+' | '.join(row))
print('PITCH axis (X), radii from pitch axis')
prof(0,(424.86,-0.014),[60,70,75,80,85,90,95,97,99,102,105,110,115,120],['PITCH','P1','FRAME','PBRK','ROLL','P2'],rmax=120)
print('ROLL axis (Z), radii from roll axis')
prof(2,(170.49,424.86),[-45,-40,-35,-30,-27,-25,-20,-10,0,10,20,26,29,31,35,40,45,50,55,60,65,70],['ROLL','P1','SPACER','P2','YAW','PITCH'],rmax=110)
print('YAW axis (Y), radii from yaw axis')
prof(1,(170.49,5.99),[290,295,300,305,310,315,318,320,322,324,330,340,350,355,360,365,368,372,380],['YAW','HUB','UA','P2','P1','ROLL'],rmax=110)
