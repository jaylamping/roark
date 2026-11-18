"""Key access to the 104 deg RS02 screw through the fork front's key slot: a section at the screw's X plane with the key
drawn in, and a clearance figure for the key's shank (checks/size_audit/KEY_ACCESS.png).

    python key_access.py STL_DIR        (e.g. stl_look_ykK, or stl for the real part)

The key: a 2.5 mm ball-end hex key for the M3 socket screw (shank drawn as dia 3.0 with a dia 6 long arm from 60 mm up).
It sits KEY_SLOT_DEG back from the screw's axis; a ball end works to about 25 deg. The RS02 goes onto the fork front on
the bench, before the fork front goes onto the drum, so the drum's envelope behind the cheek is open.
"""
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from dims import KEY_SLOT_DEG, RS02_ACCESS_ANG, RX, RY, SEAT_Y, YZ
from swk import WIP

REPO = WIP.parents[2]
src = WIP / (sys.argv[1] if len(sys.argv) > 1 else 'stl')
m = trimesh.load(src / 'fork_front.stl')
a = [q for q in RS02_ACCESS_ANG if YZ + 36.5 * math.sin(math.radians(q)) > 38.0][0]
xk, zk = RX + 36.5 * math.cos(math.radians(a)), YZ + 36.5 * math.sin(math.radians(a))
yh = SEAT_Y[1] - 3.5 + 3.0            # top of the M3 cap head (seat at Y 358.4, head 3.0 high)
t = math.radians(KEY_SLOT_DEG)
u = np.array([0.0, math.cos(t), -math.sin(t)])
p0 = np.array([xk, yh - 1.5, zk])     # the ball sits 1.5 into the socket
res = {}
for nm, rad, s0, s1 in (('shank dia 3.0', 1.5, 3.0, 60.0), ('long arm dia 6', 3.0, 60.0, 110.0)):
    pts = np.array([p0 + u * s for s in np.arange(s0, s1, 0.5)])
    d = trimesh.proximity.ProximityQuery(m).signed_distance(pts)      # positive inside the solid
    res[nm] = float(-d.max() - rad)
    print(f'{nm}: least clearance to the fork front {res[nm]:.2f} mm (negative = it cuts the part)', flush=True)
sec = m.section(plane_origin=(xk, 0, 0), plane_normal=(1, 0, 0))
fig, ax = plt.subplots(figsize=(9, 8))
for e in sec.entities:
    q = sec.vertices[e.points]
    ax.plot(q[:, 2], q[:, 1], 'k', lw=0.8)
k0, k1 = p0, p0 + u * 110.0
ax.plot([k0[2], k1[2]], [k0[1], k1[1]], color='tab:red', lw=3, label=f'ball-end key, {KEY_SLOT_DEG:.0f} deg from the screw axis')
ax.plot([zk, zk], [SEAT_Y[1] - 9.5, yh], color='tab:blue', lw=5, label='M3 screw (104 deg), head top Y %.1f' % yh)
th = np.linspace(0, 2 * math.pi, 200)
ax.plot(59.0 * 0 + np.nan, np.nan)
yy = np.linspace(RY - 59.0, RY - 20.0, 100)
ax.plot([38.5] * 2, [RY - math.sqrt(59.0 ** 2 - (xk - RX) ** 2), 395], color='0.6', ls='--', lw=1, label="drum's envelope (open on the bench)")
ax.set_xlim(-10, 60); ax.set_ylim(335, 470); ax.set_aspect('equal')
ax.set_xlabel('Z (forward), mm'); ax.set_ylabel('Y (up), mm')
ax.set_title(f'Fork front, section at the 104 deg RS02 screw (X offset {xk - RX:+.1f}).\nShank clearance {res["shank dia 3.0"]:.1f} mm, long arm {res["long arm dia 6"]:.1f} mm')
ax.legend(loc='upper right', fontsize=8)
out = REPO / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'size_audit' / 'KEY_ACCESS.png'
fig.savefig(out, dpi=110)
print('saved', out)
