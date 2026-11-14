"""Changed surface of a hub variant against D3b: nearest distance to the arm's r1g4 parts (left-arm-organic, read-only) and whether any of it is inside them."""
"""Changed surface of a D3c hub (vs D3b): its nearest distance to the arm's r1g4 parts, and whether any of it is inside them."""
import numpy as np, trimesh
A = r'J:/code/roark-wt/left-arm-organic/cad/_wip/r1d_r1g_print/'
H = r'J:/code/roark-wt/shoulder-study/cad/_wip/shoulder-pass1/'
RX, YZ = 170.49, 5.99
arm = trimesh.util.concatenate([trimesh.load(A + f) for f in ('upper_arm_organic_front_left.STL', 'upper_arm_organic_back_left.STL', 'checks/lug_plates_045_r1g4.STL')])
b = trimesh.load(H + 'stl_look_hubD3b/hub.STL')


def cp(m, p, k=5000):
    out = [trimesh.proximity.closest_point(m, p[i:i + k]) for i in range(0, len(p), k)]
    return np.vstack([o[0] for o in out]), np.concatenate([o[1] for o in out]), np.concatenate([o[2] for o in out])


for n in ('hubD3c4',):
    h = trimesh.load(H + f'stl_look_{n}/hub.STL')
    p, _ = trimesh.sample.sample_surface_even(h, 120000, seed=5)
    if n != 'hubD3b':
        _, d0, _ = cp(b, p)
        p = p[d0 > 0.005]
    else:
        p = p[(p[:, 1] < 297.5)]            # baseline: the hub surface below the land, where the arm sits
    c, d, tri = cp(arm, p)
    sd = np.einsum('ij,ij->i', p - c, arm.face_normals[tri])      # < 0: inside the arm (normal side test)
    ins = (sd < -0.01)
    q = p[ins]
    print(f'{n}: {len(p)} surface samples (changed vs D3b), min distance to the arm {d.min():.3f} mm, inside the arm {int(ins.sum())}'
          + (f' at X off {np.abs(q[:,0]-RX).min():.2f}-{np.abs(q[:,0]-RX).max():.2f}, Y {q[:,1].min():.2f}-{q[:,1].max():.2f}' if len(q) else ''))
    i = np.argmin(d); print('   closest at X off', round(float(p[i,0]-RX),2), 'Y', round(float(p[i,1]),2), 'Z-YZ', round(float(p[i,2]-YZ),2))
