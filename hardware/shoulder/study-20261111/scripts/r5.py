from rv import *
import numpy as np
d=load_all()
items=[(d[k],COL[k]) for k in d]
F=(140,390,0)
render(items,'O1_overall_iso.png',pos=(520,640,600),focal=F,scale=165,size=(1400,1100),
 labels=[('pitch RS03',(80,480,40),(0.1,0.1,0.1)),('P1 L01',(200,490,30),(0.0,0.4,0.4)),('roll RS03',(225,470,-20),(0.1,0.1,0.1)),('P2 L04B',(215,410,70),(0.7,0.3,0.0)),('yaw RS02',(215,345,40),(0.1,0.1,0.1)),('hub',(215,305,40),(0.3,0.3,0.3)),('upper arm',(215,250,40),(0.3,0.3,0.3)),('2020 cage',(60,500,70),(0.3,0.3,0.4))])
render(items,'O2_overall_front.png',pos=(140,390,900),focal=F,scale=165,size=(1300,1100))
render(items,'O3_overall_back.png',pos=(500,560,-650),focal=F,scale=165,size=(1300,1100))
# exploded
off=dict(P1=(45,0,0),ROLL=(90,0,-70),SPACER=(45,0,60),P2=(45,0,120),YAW=(45,-70,120),HUB=(45,-120,120),UA=(45,-170,120))
ex=[]
for k,m in d.items():
    mm=m.copy(); 
    if k in off: mm.apply_translation(off[k])
    ex.append((mm,COL[k]))
lab=[('1 pitch RS03 (fixed in cage)',(60,520,-40)),('2 P1 L01',(185,500,30)),('3 roll RS03',(270,480,-70)),('4 PF03 spacer',(215,450,110)),('5 P2 L04B',(250,395,215)),('6 yaw RS02',(215,280,190)),('7 hub',(215,215,180)),('8 upper arm',(215,150,170))]
render(ex,'E1_exploded.png',pos=(560,640,700),focal=(185,300,40),scale=265,size=(1400,1200),labels=[(a,b,(0.1,0.1,0.1)) for a,b in lab])
