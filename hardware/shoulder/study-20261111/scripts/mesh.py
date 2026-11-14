import cadquery as cq, numpy as np, trimesh, json, os
T=np.array([[-1,0,0,97],[0,0,1,424.860667548201],[0,1,0,-0.0141253439872],[0,0,0,1]])
I='J:/code/roark-wt/shoulder-study/cad/reference/shoulder/'
os.makedirs('w',exist_ok=True)
parts={'P1':('shoulder_pitch_bracket_left_l01.step',True),'P2':('shoulder_roll_bracket_left_l04b.step',True),
 'SPACER':('shoulder_roll_spacer_left_pf03.step',True),'ROLL':('shoulder_roll_rs03_placed_left.step',True),
 'YAW':('shoulder_yaw_rs02_placed_left.step',True),'HUB':('upper_arm_hub_left.step',False),
 'P2L05':('J:/code/marengo/cad/exports/shoulder/marengo_p2_l05_left.step',None)}
info={}
for k,(f,src) in parts.items():
    p=f if ':' in f else I+f
    sh=cq.importers.importStep(p)
    vals=sh.vals(); c=cq.Compound.makeCompound(vals)
    vol=sum(s.Volume() for s in c.Solids())
    c.exportStl(f'w/{k}_raw.stl',tolerance=0.05,angularTolerance=0.1)
    m=trimesh.load(f'w/{k}_raw.stl')
    if src: m.apply_transform(T)
    m.export(f'w/{k}.stl')
    info[k]=dict(vol=vol,mass=vol*1.27e-3,bb=np.round(m.bounds,2).tolist(),wt=m.is_watertight,src=src)
    print(k,info[k],flush=True)
json.dump(info,open('w/info.json','w'),indent=1)
