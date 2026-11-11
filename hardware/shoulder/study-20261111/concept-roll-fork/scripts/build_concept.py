"""Roll drum and fork: concept mock-up of an improved left shoulder (cadquery / OCP).

Feasibility mock, not final CAD. Everything is built in the torso STEP frame used by the shoulder measurement study
(X outboard, Y up, Z forward, mm). Motors stay exactly where MEASUREMENTS.md puts them.

    python build_concept.py OUTDIR

writes OUTDIR/<part>.stl for every concept part and cut volume, OUTDIR/parts.json (volumes, masses, bounding boxes,
which joint group each part belongs to) and OUTDIR/roll_fork_concept.step (printed parts and bearings only).
Needs the repo's cad/reference/shoulder STEPs (the hub is modified from upper_arm_hub_left.step).
"""
import json, os, sys, math
import numpy as np
import cadquery as cq

REPO = os.environ.get('ROARK', r'J:/code/roark-wt/shoulder-study')
HUB_STEP = REPO + '/cad/reference/shoulder/upper_arm_hub_left.step'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'concept_out'
os.makedirs(OUT, exist_ok=True)

# ---- frame (MEASUREMENTS.md section 0) ----
RX, RY = 170.49, 424.86          # roll axis (along Z) and pitch axis height
PZ = -0.014                      # pitch axis Z
YZ = 5.99                        # yaw axis Z (yaw axis along Y through X = RX)
ROLL_OUT, ROLL_REAR = 30.64, -25.96
RS02_REAR, RS02_SEAT, RS02_UNDER = 365.26, 351.86, 323.3
PETG = 1.27e-3                   # g/mm3

# ---- chosen dimensions (see CONCEPT.md "Dimensions chosen") ----
DRUM_RI, DRUM_RO = 48.0, 57.0    # bore over the RS03 body (r 47) / outside of ribs, rim and ears
WALL_RO, LIP_RO = 51.5, 56.0     # drum wall between ribs / front lip (RS02 rear cap is 59.6 from the roll axis)
LUG_ANGLES = [22.5 + 45 * k for k in range(8)]   # RS03 cast lugs, r 53, 8.5 wide
SLOT_HALF, SLOT_R = 5.5, 54.5
LIP_Z0, LIP_Z1, LIP_RI = 28.3, 36.0, 40.0         # front lip, 8 x M4 on PCD 98 (today's lip ends at Z 39.5)
DRUM_Z0 = -28.5                                   # drum rear rim = cap front face (RS03 rear face -25.96)
CAP_Z1 = -40.5                                    # cap rear face
STUB_Z1 = -51.0                                   # stub end
BRG_Z = (-42.5, -49.5)                            # 6808 40x52x7
EAR_ANGLES = [130.0, 165.0, 200.0]                # cap ears, inboard/top where the fork never sweeps
FRONT_Z = (39.0, 47.0)                            # fork front cheek
REAR_Z = (-46.0, -54.0)                           # fork rear cheek / arm (duct shell to -58)
SEAT_Y = (RS02_SEAT, 361.9)                       # fork seat ring on the RS02 rear housing face
SEAT_RI, SEAT_RO = 33.5, 45.0
FOOT_Z = -39.5                                    # bolted joint face between fork rear arm and seat ring
DISH_R0, DISH_Y = 23.5, 315.8                     # hub top dished outside r 23.5 down to Y 315.8


def ax_roll(s):  # profile built about +Y -> roll axis (+Z through RX, RY)
    return s.rotate((0, 0, 0), (1, 0, 0), 90).translate((RX, RY, 0))


def ax_pitch(s):
    return s.rotate((0, 0, 0), (0, 0, 1), -90).translate((0, RY, PZ))


def ax_yaw(s):
    return s.translate((RX, 0, YZ))


def rev(pts, axis):
    """Revolve a closed (r, a) profile (a = position along the axis) 360 deg."""
    w = cq.Workplane('XY').polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
    return axis(w)


def ring(r0, r1, a0, a1, axis):
    return rev([(r0, a0), (r1, a0), (r1, a1), (r0, a1)], axis)


def cyl(r, a0, a1, axis):
    return rev([(0, a0), (r, a0), (r, a1), (0, a1)], axis)


def polar(r, th, c=(RX, RY)):
    t = math.radians(th)
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))


def box_along(p0, p1, u, w, h, ext=0.0, off=(0.0, 0.0), slot=False):
    """Prism of section w (along u) x h (along d x u) from p0 to p1, extended ext at both ends."""
    p0, p1, u = np.array(p0, float), np.array(p1, float), np.array(u, float)
    d = p1 - p0; L = np.linalg.norm(d); d /= L
    u = u - d * (u @ d); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    o = p0 - d * ext + u * off[0] + v * off[1]
    pl = cq.Plane(origin=tuple(o), xDir=tuple(u), normal=tuple(d))
    wp = cq.Workplane(pl)
    wp = wp.slot2D(w, h) if slot else wp.rect(w, h)
    return wp.extrude(L + 2 * ext)


def hull_plate(circles, z0, z1, n=36):
    """Extruded convex hull of circles [(x, y, r)] between z0 and z1, outline as a smooth periodic spline."""
    from scipy.spatial import ConvexHull
    pts = []
    for (x, y, r) in circles:
        for t in np.linspace(0, 2 * np.pi, n, endpoint=False):
            pts.append((x + r * np.cos(t), y + r * np.sin(t)))
    pts = np.array(pts); h = ConvexHull(pts); P = pts[h.vertices]
    # resample the hull evenly so the spline stays smooth
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))]
    s = np.linspace(0, seg[-1], 90, endpoint=False)
    Q = np.c_[np.interp(s, seg, np.r_[P[:, 0], P[0, 0]]), np.interp(s, seg, np.r_[P[:, 1], P[0, 1]])]
    wp = cq.Workplane('XY').workplane(offset=z0).spline([tuple(q) for q in Q], periodic=True).close()
    return wp.extrude(z1 - z0)


def sector_yaw(a0, a1, r0, r1, y0, y1):
    """Annular sector about the yaw axis, angles as atan2(z - YZ, x - RX) in degrees, between heights y0 and y1."""
    A = np.linspace(a0, a1, 16)
    pts = [(r1 * math.cos(math.radians(-a)), r1 * math.sin(math.radians(-a))) for a in A] +           [(r0 * math.cos(math.radians(-a)), r0 * math.sin(math.radians(-a))) for a in A[::-1]]
    if r0 <= 0:
        pts = [(0.0, 0.0)] + pts[:16]
    w = cq.Workplane('XY').polyline(pts).close().extrude(y1 - y0)
    return w.rotate((0, 0, 0), (1, 0, 0), -90).translate((RX, y0, YZ))


def soft(wp, r, sel=None):
    """Fillet if OCC allows it; mock-up, so a failed fillet is skipped (logged)."""
    try:
        e = wp.edges(sel) if sel else wp.edges()
        return e.fillet(r)
    except Exception as ex:
        print('  fillet skipped', r, sel, type(ex).__name__)
        return wp


# ======================================================================================================== wire passages
# Each passage = shell (part material) + power channel (red, 14 x 8) + signal channel (blue, 10 x 5), side by side along
# u with a 2 mm rib. Power 14 x 8 also holds the whole shoulder bundle (4 x 14.5 slot) on its own; signal 10 x 5 holds 2.2 x 8.
PW, PH, SW, SH, RIB, WALL = 14.0, 8.0, 10.0, 5.0, 2.0, 2.0
TOT = PW + RIB + SW


def duct(p0, p1, u, ext=4.0, shell=True, shell_ext=None):
    po = (-TOT / 2 + PW / 2, 0.0); so = (TOT / 2 - SW / 2, 0.0)
    red = box_along(p0, p1, u, PW, PH, ext, po)
    blue = box_along(p0, p1, u, SW, SH, ext, so)
    se = ext + WALL if shell_ext is None else shell_ext
    sh = box_along(p0, p1, u, TOT + 2 * WALL, PH + 2 * WALL, se) if shell else None
    return sh, red, blue


parts, cuts = {}, {}

# ================================================================================================ P1: drum + pitch adaptor
print('P1 drum')
# fluted drum: 4.5 mm wall over the RS03 body, 8 outside ribs over the lug slots, front lip for the 8 x M4 (PCD 98),
# rear rim for the cap. The bottom (no lug at -90 deg) stays at r 52.5, 7 mm clear of the RS02 rear cap.
drum = rev([(DRUM_RI, DRUM_Z0), (DRUM_RO - 2, DRUM_Z0), (DRUM_RO, DRUM_Z0 + 2), (DRUM_RO, DRUM_Z0 + 4.5),
            (WALL_RO, DRUM_Z0 + 7.5), (WALL_RO, LIP_Z0 - 3), (LIP_RO, LIP_Z0), (LIP_RO, LIP_Z1 - 2.5),
            (LIP_RO - 2.5, LIP_Z1), (LIP_RI, LIP_Z1), (LIP_RI, LIP_Z0), (DRUM_RI, LIP_Z0)], ax_roll)
for th in LUG_ANGLES:
    rib = cq.Workplane('XY').workplane(offset=DRUM_Z0).center(RX + (WALL_RO + DRUM_RO) / 2 - 2, RY).rect(
        DRUM_RO - WALL_RO + 4, 16.0).extrude(LIP_Z0 - DRUM_Z0)
    rib = soft(rib, 3.0, '|Z').rotate((RX, RY, 0), (RX, RY, 1), th)
    drum = drum.union(rib)
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    drum = drum.union(cq.Workplane('XY').workplane(offset=DRUM_Z0).center(x, y).circle(7.5).extrude(9.0))
# pitch adaptor: pad (r 22, X 97-108.7 solid: the six pitch screws clamp it, heads at X 108.7 as today) inside the RS03
# stationary ring (r 28 at the face), flange (X 100-103, r 72), skirt (r 56.5-58.5, X 78-103) = inner wall of the pitch
# loop channel, and a hollow neck into the drum (core r 21 open to the drum bore: pitch screws reached from inside)
pad = cyl(22.0, 97.0, 108.7, ax_pitch)
flange = rev([(52.0, 100.5), (70.5, 100.5), (72.0, 101.5), (72.0, 103.0), (52.0, 103.0)], ax_pitch)
for k in range(5):
    t = math.radians(90 + 72 * k)
    sp = cq.Workplane('YZ').workplane(offset=100.5).center(RY + 37 * math.cos(t), PZ + 37 * math.sin(t)).rect(8, 32).extrude(2.5)
    flange = flange.union(sp.rotate((0, RY + 37 * math.cos(t), PZ + 37 * math.sin(t)), (1, RY + 37 * math.cos(t), PZ + 37 * math.sin(t)), 72 * k))
skirt = rev([(56.5, 80.0), (58.5, 80.0), (58.5, 103.0), (56.5, 103.0)], ax_pitch)
neck = rev([(21.0, 100.5), (40.0, 100.5), (40.0, 130.0), (34.0, 130.0), (34.0, 106.0), (21.0, 106.0)], ax_pitch).intersect(
    cq.Workplane('XY').workplane(offset=DRUM_Z0 + 1).rect(400, 1200).extrude(LIP_Z1 - DRUM_Z0 - 1))
p1 = drum.union(pad).union(flange).union(skirt).union(neck)
# re-open the drum bore and the lug slots (open to the rear: the RS03 slides in from behind)
p1 = p1.cut(cyl(DRUM_RI, DRUM_Z0 - 1, LIP_Z0, ax_roll))
for th in LUG_ANGLES:
    sl = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(RX + SLOT_R / 2, RY).rect(SLOT_R, 2 * SLOT_HALF).extrude(
        LIP_Z0 - DRUM_Z0 + 1).rotate((RX, RY, 0), (RX, RY, 1), th)
    p1 = p1.cut(sl)
# 8 x M4 into the RS03 lugs (PCD 98), counterbore from the front
for th in LUG_ANGLES:
    x, y = polar(49.0, th)
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=LIP_Z0 - 1).center(x, y).circle(2.25).extrude(15))
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=LIP_Z1 - 4.2).center(x, y).circle(4.8).extrude(10))
# pitch output: 6 x M4 on PCD 30.4 (clock -134 + 60k as measured); bore 21.5
p1 = p1.cut(cyl(10.75, 95, 110, ax_pitch)).cut(cyl(21.0, 108.7, 130, ax_pitch))
for k in range(6):
    t = math.radians(-134 + 60 * k); yy, zz = RY + 15.2 * math.cos(t), PZ + 15.2 * math.sin(t)
    p1 = p1.cut(cq.Workplane('YZ').workplane(offset=96).center(yy, zz).circle(2.25).extrude(14))
# ear holes (M4 heat-set inserts)
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(x, y).circle(2.8).extrude(10))
# window over the roll RS03 top connector bay (bay X 145-196, Z -26 to -8)
WIN = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(RX, RY + 60).rect(56, 40).extrude(DRUM_Z0 + 1 + 7)
p1 = p1.cut(WIN)

# ---- wire passages on the P1 side ----
TRUNK_Y, TRUNK_X = 489.0, 140.0   # duct over the neck, then along the drum at theta ~115 deg
TU = (1, -0.45, 0)
segs_p1 = [((84.0, TRUNK_Y, 0.0), (TRUNK_X, TRUNK_Y, 0.0), (0, 0, 1), 4.0),            # out of the pitch loop channel
           ((TRUNK_X, TRUNK_Y, 0.0), (TRUNK_X, TRUNK_Y, DRUM_Z0), TU, 4.0)]            # along the drum to the cap
red_l, blue_l = [], []
for a, b, u, e in segs_p1:
    sh, r_, b_ = duct(a, b, u, ext=e, shell_ext=0 if b[2] == DRUM_Z0 else None)
    p1 = p1.union(sh); red_l.append(r_); blue_l.append(b_)
# drop to the RS03 top bay: short branch from the trunk into the window (both cables of the roll motor)
sh, r_, b_ = duct((TRUNK_X, TRUNK_Y, -17.0), (RX - 8, 474.5, -17.0), (0, 0, 1), ext=2)
p1 = p1.union(sh); red_l.append(r_); blue_l.append(b_)
for c in red_l + blue_l:
    p1 = p1.cut(c)
p1 = p1.cut(cyl(DRUM_RI, DRUM_Z0 - 1, LIP_Z0, ax_roll)).cut(WIN)      # keep the bore and bay window clean
BEHIND = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 40).center(RX + 50, RY).rect(2 * 50 + 2 * (RX - 106), 400).extrude(40)
p1 = p1.cut(BEHIND)   # nothing of the drum side behind the rim (the pitch flange is left alone)
parts['P1_drum'] = p1
cuts['WIRE_P1_power'] = [r.cut(BEHIND) for r in red_l]
cuts['WIRE_P1_signal'] = [r.cut(BEHIND) for r in blue_l]

# ======================================================================================================== P1: rear cap
print('rear cap')
MIR = lambda s: ax_roll(s).mirror('XY', (0, 0, 0))
CAPZ = (DRUM_Z0 + CAP_Z1) / 2
# spoked cap: 4 mm plate at the back, 12 mm rim and centre boss, cable spoke (12 mm deep) up to the trunk
cap = rev([(0, -CAP_Z1), (DRUM_RO - 2.5, -CAP_Z1), (DRUM_RO, -CAP_Z1 - 2.5), (DRUM_RO, -DRUM_Z0), (DRUM_RO - 4.5, -DRUM_Z0),
           (DRUM_RO - 4.5, -CAP_Z1 - 4.0), (26.0, -CAP_Z1 - 4.0), (26.0, -DRUM_Z0), (0, -DRUM_Z0)], MIR)
for th in [35, 125, 215, 305]:            # lightening holes in the plate
    x, y = polar(39.0, th)
    cap = cap.cut(cq.Workplane('XY').workplane(offset=CAP_Z1 - 1).center(x, y).circle(8.0).extrude(6))
dvec = np.array([RX - TRUNK_X, RY - TRUNK_Y, 0.0]); dvec /= np.linalg.norm(dvec); CU = (-dvec[1], dvec[0], 0.0)
spoke = box_along((TRUNK_X, TRUNK_Y, CAPZ), (RX, RY, CAPZ), CU, TOT + 2 * WALL, DRUM_Z0 - CAP_Z1, 0)
cap = cap.union(spoke.cut(cyl(12.5, CAP_Z1 - 1, DRUM_Z0 + 1, ax_roll)))
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    cap = cap.union(cq.Workplane('XY').workplane(offset=CAP_Z1).center(x, y).circle(7.5).extrude(DRUM_Z0 - CAP_Z1))
# stub: shoulder r 22.5, OD 40.0 for the 6808 (40 x 52 x 7), bore 25
cap = cap.union(ring(0, 22.5, -CAP_Z1, -BRG_Z[0], MIR))
cap = cap.union(ring(0, 20.0, -BRG_Z[0], -STUB_Z1, MIR))
cap = cap.cut(cyl(12.5, -STUB_Z1 - 1, -DRUM_Z0 + 1, MIR))
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    cap = cap.cut(cq.Workplane('XY').workplane(offset=CAP_Z1 - 1).center(x, y).circle(2.25).extrude(15))
    cap = cap.cut(cq.Workplane('XY').workplane(offset=CAP_Z1 - 1).center(x, y).circle(4.0).extrude(4.5))
# cable channel inside the cap spoke: from the trunk (theta ~115, r 71) radially to the stub bore
sh, r_, b_ = duct((TRUNK_X, TRUNK_Y, CAPZ), (RX, RY, CAPZ), CU, ext=0)
cap = cap.cut(r_).cut(b_)
cuts['WIRE_CAP_power'] = [r_]; cuts['WIRE_CAP_signal'] = [b_]
# stub bore cables (the roll crossing): power above, signal below the roll axis
cuts['WIRE_STUB_power'] = [box_along((RX, RY + 4.5, CAPZ), (RX, RY + 4.5, STUB_Z1 - 4), (1, 0, 0), PW, PH)]
cuts['WIRE_STUB_signal'] = [box_along((RX, RY - 3.5, CAPZ), (RX, RY - 3.5, STUB_Z1 - 4), (1, 0, 0), SW, SH)]
parts['P1_cap'] = cap

# ================================================================================================= fork (P2 replacement)
print('fork front')
ff = hull_plate([(RX, RY, 34.0), (RX - 22, 362.0, 10.0), (RX + 22, 362.0, 10.0)], FRONT_Z[0], FRONT_Z[1])
ff = soft(ff, 2.5, '|Z or >Z or <Z')
boss = ring(0, 22.0, ROLL_OUT, FRONT_Z[0] + 0.5, ax_roll)
seat = ring(SEAT_RI, SEAT_RO, SEAT_Y[0], SEAT_Y[1], ax_yaw)
seat_lug = cq.Workplane('XY').workplane(offset=FOOT_Z).center(RX, (SEAT_Y[0] + SEAT_Y[1]) / 2 + 0.0).rect(40, SEAT_Y[1] - SEAT_Y[0]).extrude(12)
fork_f = ff.union(boss).union(seat).union(seat_lug)
fork_f = fork_f.cut(cyl(SEAT_RI, SEAT_Y[0] - 1, SEAT_Y[1] + 1, ax_yaw))
fork_f = fork_f.cut(cyl(10.75, ROLL_OUT - 1, FRONT_Z[1] + 1, ax_roll))
for k in range(6):
    x, y = polar(15.2, 30 + 60 * k)
    fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=ROLL_OUT - 1).center(x, y).circle(2.25).extrude(30))
    fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 4).center(x, y).circle(4.25).extrude(10))
# press-in cap recess on the front cheek (arm language): r 24 x 2 deep
fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 2).center(RX, RY).circle(24.0).extrude(5))
# RS02 rear-face screws: 5 x M3 on PCD 73 (angles in the X-Z plane about the yaw axis, as measured)
for a in [-136, -96, -56, 64, 104]:
    t = math.radians(a); x, z = RX + 36.5 * math.cos(t), YZ + 36.5 * math.sin(t)
    fork_f = fork_f.cut(cq.Workplane('XY').add(cq.Solid.makeCylinder(1.8, 30, cq.Vector(x, SEAT_Y[0] - 5, z), cq.Vector(0, 1, 0))))
    fork_f = fork_f.cut(cq.Workplane('XY').add(cq.Solid.makeCylinder(3.3, 10, cq.Vector(x, SEAT_Y[1] - 3.5, z), cq.Vector(0, 1, 0))))
# pockets for the two RS02 radial sockets (inboard 180 +- 14 deg, outboard 4 +- 26 deg)
for a0, a1 in [(166, 194), (-22, 30)]:
    fork_f = fork_f.cut(sector_yaw(a0, a1, 0.0, 40.5, SEAT_Y[0] - 1, SEAT_Y[0] + 9.0))
# front press-in cap (separate part)
parts['FORK_front_cap'] = cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 2).center(RX, RY).circle(23.8).extrude(4.0).faces('>Z').edges().chamfer(1.2)

print('fork rear')
fr = hull_plate([(RX, RY, 24.0), (RX - 13, 366.0, 9.0), (RX + 13, 366.0, 9.0)], REAR_Z[1], REAR_Z[0])
fr = fr.union(ring(0, 33.0, -REAR_Z[0], -(REAR_Z[1] - 4.0), MIR))
fr = soft(fr, 2.5, '|Z or >Z or <Z')
foot = cq.Workplane('XY').workplane(offset=REAR_Z[1]).center(RX, (SEAT_Y[0] + SEAT_Y[1]) / 2).rect(40, SEAT_Y[1] - SEAT_Y[0]).extrude(FOOT_Z - REAR_Z[1])
house = ring(26.0, 33.0, -(BRG_Z[0] - 1.0), -REAR_Z[0], MIR)
fork_r = fr.union(foot).union(house)
fork_r = fork_r.cut(cyl(26.0, -(BRG_Z[0] - 1.5), -BRG_Z[1], lambda s: ax_roll(s).mirror('XY', (0, 0, 0))))   # 6808 seat
fork_r = fork_r.cut(cyl(23.0, -BRG_Z[1] + 0.5, -BRG_Z[1] + 2.0, MIR)).cut(cyl(18.0, -BRG_Z[1], -(REAR_Z[1] - 1.5), MIR))  # shoulder + chamber
# joint to the seat ring: 2 x M4 along Z
for dx in (-12, 12):
    for part in ('r', 'f'):
        hole = cq.Workplane('XY').workplane(offset=REAR_Z[1] - 1).center(RX + dx, 357.0).circle(2.25).extrude(35)
        if part == 'r':
            fork_r = fork_r.cut(hole); fork_r = fork_r.cut(cq.Workplane('XY').workplane(offset=REAR_Z[1] - 1).center(RX + dx, 357.0).circle(4.0).extrude(5))
        else:
            fork_f = fork_f.cut(hole)
# passages on the fork: down the rear arm, along the inboard side of the RS02, a finger down past the housing,
# then into the gap under the RS02 (yaw crossing)
RZ = -52.0
XF = RX - 47.3                     # finger centreline: 2 mm outside the RS02 housing (r 39.25) after the shell
_d = np.array([XF - RX, 364.0 - RY]); _d /= np.linalg.norm(_d)
segs_r = [((RX, RY, RZ), (XF, 364.0, RZ), (-_d[1], _d[0], 0.0))]
segs_f = [((XF, 364.0, FOOT_Z), (XF, 364.0, YZ - 3), (0, 1, 0)),
          ((XF, 364.0, YZ - 3), (XF, 323.0, YZ - 3), (0, 0, 1))]
red_r, blue_r, red_f, blue_f = [], [], [], []
for a, b, u in segs_r:
    sh, r_, b_ = duct(a, b, u); fork_r = fork_r.union(sh); red_r.append(r_); blue_r.append(b_)
# the inboard run is split at the joint face FOOT_Z: rear part on the rear arm
sh, r_, b_ = duct((XF, 364.0, RZ), (XF, 364.0, FOOT_Z), (0, 1, 0), ext=0, shell_ext=0)
fork_r = fork_r.union(sh); red_r.append(r_); blue_r.append(b_)
for a, b, u in segs_f:
    sh, r_, b_ = duct(a, b, u, ext=0 if a[2] == FOOT_Z else 4.0, shell_ext=0 if a[2] == FOOT_Z else None); fork_f = fork_f.union(sh); red_f.append(r_); blue_f.append(b_)
# RS02 inboard socket tap
sh, r_, b_ = duct((XF, 358.0, YZ - 3), (RX - 31.0, 358.0, YZ - 3), (0, 0, 1), ext=0)
red_f.append(r_); blue_f.append(b_)
# exit of the finger into the annular gap under the RS02 (upper-arm bundle only: 3.5 x 13 reserve)
exit_cut = box_along((XF, 319.55, YZ - 3), (RX - 37.0, 319.55, YZ - 3), (0, 0, 1), 16.0, 6.0, 0)
exit_sh = box_along((XF, 319.55, YZ - 3), (RX - 41.0, 319.55, YZ - 3), (0, 0, 1), 20.0, 6.0 + 2 * WALL - 1.0, WALL)
fork_f = fork_f.union(exit_sh.translate((0, 0.5, 0)))
for c in red_r + blue_r:
    fork_r = fork_r.cut(c)
for c in red_f + blue_f + [exit_cut]:
    fork_f = fork_f.cut(c)
# keep the RS02 housing and seat face clear of duct shells
fork_f = fork_f.cut(cyl(40.4, RS02_UNDER - 10, SEAT_Y[0], ax_yaw)).cut(cyl(SEAT_RI, SEAT_Y[0] - 1, SEAT_Y[1] + 1, ax_yaw))
# clip the finger shell above the hub (hub dish top Y 315.8; rotating)
fork_f = fork_f.cut(cq.Workplane('XY').box(400, 50, 400).translate((RX, 316.6 - 25, 0)))
cuts['WIRE_FORK_power'] = red_r + red_f; cuts['WIRE_FORK_signal'] = blue_r + blue_f
cuts['WIRE_YAWEXIT_power'] = [exit_cut]
parts['FORK_front'] = fork_f
parts['FORK_rear'] = fork_r

# ------------------------------------------------------------------- roll stops: printed lugs on the cap's rear face
# angular half-width of the rear arm at r 44-55 is measured from the solid itself, so the stops land on -20 / +110
def arm_extent(solid, r0=44, r1=55, z0=REAR_Z[1], z1=REAR_Z[0]):
    import trimesh
    tmp = os.path.join(OUT, '_tmp_arm.stl'); cq.exporters.export(solid, tmp, tolerance=0.2, angularTolerance=0.2)
    m = trimesh.load(tmp); p, _ = trimesh.sample.sample_surface_even(m, 60000, seed=0)
    r = np.hypot(p[:, 0] - RX, p[:, 1] - RY); s = (r > r0) & (r < r1) & (p[:, 1] < RY)
    th = np.degrees(np.arctan2(p[s, 1] - RY, p[s, 0] - RX))
    return th.min(), th.max()


tmin, tmax = arm_extent(fork_r)
STOP_LO, STOP_HI, STOP_W = -20.0, 110.0, 12.0
lo_face = tmin + STOP_LO - 0.5        # arm's inboard flank at roll -20 (theta measured about +Z)
hi_face = tmax + STOP_HI + 0.5
print(f'  rear arm flank at r 44-55: {tmin:.1f} .. {tmax:.1f} deg -> stop faces {lo_face:.1f} / {hi_face:.1f}')
stops = None
for a0, a1 in [(lo_face - STOP_W, lo_face), (hi_face, hi_face + STOP_W)]:
    pts = [(44 * math.cos(math.radians(a)), 44 * math.sin(math.radians(a))) for a in np.linspace(a0, a1, 6)] + \
          [(55 * math.cos(math.radians(a)), 55 * math.sin(math.radians(a))) for a in np.linspace(a1, a0, 6)]
    blk = cq.Workplane('XY').workplane(offset=-52.0).polyline(pts).close().extrude(CAP_Z1 + 52.0 + 0.5).translate((RX, RY, 0))
    stops = blk if stops is None else stops.union(blk)
parts['P1_cap'] = parts['P1_cap'].union(stops)

# ============================================================================================================= bearings
parts['BRG_6808'] = ring(20.0, 26.0, -BRG_Z[0], -BRG_Z[1], lambda s: ax_roll(s).mirror('XY', (0, 0, 0)))

# ==================================================================================================== hub: dished top
print('hub')
hub0 = cq.importers.importStep(HUB_STEP)
hub = hub0.cut(ring(DISH_R0, 45.0, DISH_Y, 330.0, ax_yaw))
hub = hub.union(ring(19.5, DISH_R0 + 0.01, 312.8, 319.86, ax_yaw))       # step ring carrying the torque down
hub = hub.union(ring(DISH_R0 - 0.5, 38.6, 312.8, DISH_Y, ax_yaw))         # new dished floor
hub = hub.union(ring(38.5, 39.3, 305.0, DISH_Y, ax_yaw))                  # outer wall up to the dish
# cable window: from the dish (theta 8 deg, between the hub screws at -22 and 38) down into the arm's Ø43 opening
WIN_A = 7.9
t = math.radians(WIN_A); ux, uz = math.cos(t), math.sin(t)
win = box_along((RX + 31.0 * ux, DISH_Y + 2, YZ + 31.0 * uz), (RX + 15.5 * ux, 298.0, YZ + 15.5 * uz), (-uz, 0, ux), 16.0, 9.0, 0)
hub = hub.cut(win)
parts['HUB_dished'] = hub
ann_p = ring(31.0, 38.5, DISH_Y + 0.3, RS02_UNDER - 0.3, ax_yaw)
ann_s = ring(DISH_R0 + 0.3, 30.0, DISH_Y + 0.3, RS02_UNDER - 0.3, ax_yaw)
cuts['WIRE_YAWLOOP_power'] = [ann_p]; cuts['WIRE_YAWLOOP_signal'] = [ann_s]; cuts['WIRE_HUBWIN_power'] = [win]

# ============================================================================== fixed: pitch loop channel cover + feed
print('pitch cover')
cover = rev([(56.0, 75.0), (75.5, 75.0), (75.5, 93.5), (74.0, 95.0), (73.5, 95.0), (73.5, 77.0), (56.0, 77.0)], ax_pitch)
sh_a, r_a, b_a = duct((50.0, RY + 6, -79.0), (86.5, RY + 6, -79.0), (0, 1, 0))
sh_b, r_b, b_b = duct((86.5, RY + 6, -79.0), (86.5, RY + 6, -64.0), (0, 1, 0))
cover = cover.union(sh_b.intersect(cyl(80, 74, 100, ax_pitch))).union(sh_a.cut(cyl(75.4, 74, 100, ax_pitch)))
for c in (r_a, b_a, r_b, b_b):
    cover = cover.cut(c)
parts['PITCH_cover'] = cover
loop_p = ring(58.8, 72.2, 77.2, 86.6, ax_pitch)
loop_s = ring(58.8, 72.2, 88.4, 94.8, ax_pitch)
cuts['WIRE_PITCHLOOP_power'] = [loop_p, r_a, r_b]; cuts['WIRE_PITCHLOOP_signal'] = [loop_s, b_a, b_b]

# ============================================================== variant e (yaw ring): sleeve + 6816 + Ø80 hub band
print('variant e')
sleeve = rev([(40.25, SEAT_Y[1]), (SEAT_RO, SEAT_Y[1]), (SEAT_RO, SEAT_Y[0] - 2), (44.0, SEAT_Y[0] - 6), (44.0, 327.0),
              (54.0, 322.5), (54.0, 309.0), (46.5, 309.0), (46.5, 311.0), (50.0, 311.0), (50.0, 321.0), (46.0, 321.0),
              (46.0, 324.5), (40.25, 326.5)], ax_yaw)
parts['VAR_E_sleeve'] = sleeve
parts['VAR_E_6816'] = ring(40.0, 50.0, 311.0, 321.0, ax_yaw)
parts['VAR_E_hubband'] = ring(36.0, 40.0, 309.0, 321.0, ax_yaw).union(ring(36.0, 42.5, 303.0, 311.0, ax_yaw))

# ================================================================================================================ export
GROUP = dict(P1_drum='pitch', P1_cap='pitch', FORK_front='roll', FORK_rear='roll', FORK_front_cap='roll',
             BRG_6808='bearing', HUB_dished='yaw', PITCH_cover='fixed', VAR_E_sleeve='var', VAR_E_6816='var',
             VAR_E_hubband='var')
info = {}
for k, s in parts.items():
    v = s.val() if isinstance(s, cq.Workplane) else s
    sol = cq.Workplane('XY').add(s.vals() if isinstance(s, cq.Workplane) else [s])
    vol = sum(x.Volume() for x in sol.solids().vals())
    bb = sol.val().BoundingBox() if len(sol.vals()) == 1 else cq.Compound.makeCompound(sol.vals()).BoundingBox()
    cq.exporters.export(sol, os.path.join(OUT, k + '.stl'), tolerance=0.05, angularTolerance=0.1)
    info[k] = dict(group=GROUP[k], vol_mm3=round(vol, 0), mass_petg_g=round(vol * PETG, 1),
                   bb=[round(bb.xmin, 2), round(bb.ymin, 2), round(bb.zmin, 2), round(bb.xmax, 2), round(bb.ymax, 2), round(bb.zmax, 2)],
                   size=[round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)], solids=len(sol.solids().vals()))
    print(k, info[k])
for k, lst in cuts.items():
    c = lst[0]
    for x in lst[1:]:
        c = c.union(x)
    cq.exporters.export(c, os.path.join(OUT, k + '.stl'), tolerance=0.05, angularTolerance=0.1)
json.dump(info, open(os.path.join(OUT, 'parts.json'), 'w'), indent=1)
asm = cq.Assembly()
for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'BRG_6808', 'HUB_dished', 'PITCH_cover']:
    asm.add(parts[k], name=k)
asm.save(os.path.join(OUT, 'roll_fork_concept.step'))
print('done')
