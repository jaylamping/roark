"""Roll drum and fork: concept mock-up of an improved left shoulder (cadquery / OCP), second pass.

Feasibility mock, not final CAD. Everything is built in the torso STEP frame used by the shoulder measurement study
(X outboard, Y up, Z forward, mm). Motors stay exactly where MEASUREMENTS.md puts them.

    python build_concept.py OUTDIR

writes OUTDIR/<part>.stl for every concept part and cut volume, OUTDIR/parts.json (volumes, masses, bounding boxes,
which joint group each part belongs to) and OUTDIR/roll_fork_concept.step (printed parts and bearing only).
Needs the repo's cad/reference/shoulder STEPs (the hub is modified from upper_arm_hub_left.step).
Set LIGHT=0 in the environment to build without the lightening of the second pass (for comparison).
"""
import json, os, sys, math
import numpy as np
import cadquery as cq

REPO = os.environ.get('ROARK', r'J:/code/roark-wt/shoulder-study')
HUB_STEP = REPO + '/cad/reference/shoulder/upper_arm_hub_left.step'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'concept_out'
LIGHT = os.environ.get('LIGHT', '1') != '0'
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
CAP_Z1 = -39.3                                    # cap rear face: 2.4 wall + 6 channel + 2.4 wall
CAPZ = (DRUM_Z0 + CAP_Z1) / 2                     # cap channel centre
LAND_Z = -40.3                                    # inner-race land on the stub (r 22.5)
BRG_Z = (-40.3, -47.3)                            # 6808 40x52x7, floating (radial support only)
STUB_Z1 = BRG_Z[1]                                # stub end, flush with the inner race
HOUSE_Z0 = CAP_Z1 - 2.5                           # fork bearing housing front face: 2.5 axial clear of the cap face
RZ = -51.3                                        # fork rear channel centre (6 high: Z -48.3..-54.3)
EAR_ANGLES = [130.0, 165.0, 200.0]                # cap ears, inboard/top where the fork never sweeps
FRONT_Z = (39.0, 47.0)                            # fork front cheek
SEAT_Y = (RS02_SEAT, 361.9)                       # fork seat ring on the RS02 rear housing face
SEAT_RI, SEAT_RO = 33.5, 45.0
DISH_R0, DISH_Y = 23.5, 315.8                     # hub top dished outside r 23.5 down to Y 315.8
ROLL_IN, ROLL_OUTW = -15.0, 110.0                 # roll range: stops engage exactly here
# pitch loop channel (fixed cover outside, moving skirt inside)
FL_X = (100.5, 103.0)                             # P1 flange: 3.5 clear of the pitch stator ring (X 97)
COVER_X1 = FL_X[0] - 2.0                          # cover outer wall ends 2 mm short of the flange
COVER_RO, COVER_RI = 75.9, 73.5
FL_RO = 77.5                                      # flange overlaps the cover wall: 2 mm axial slot, no straight path out
SKIRT = (56.5, 58.9, 77.4 + 2.4)                  # skirt r, and its end X (2.4 clear of the cover back wall X 75-77.4)


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


MIR = lambda s: ax_roll(s).mirror('XY', (0, 0, 0))   # roll axis, a = -Z (for features behind the motor)


def zring(r0, r1, z0, z1):
    """Ring about the roll axis between Z z0 and z1 (any order)."""
    za, zb = min(z0, z1), max(z0, z1)
    w = cq.Workplane('XY').workplane(offset=za).center(RX, RY).circle(r1)
    w = w.circle(r0).extrude(zb - za) if r0 > 0 else w.extrude(zb - za)
    return w


def polar(r, th, c=(RX, RY)):
    t = math.radians(th)
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))


def box_along(p0, p1, u, w, h, ext=0.0, off=(0.0, 0.0), slot=False, ext1=None):
    """Prism of section w (along u) x h (along d x u) from p0 to p1, extended ext before p0 and ext1 (default ext) after p1."""
    p0, p1, u = np.array(p0, float), np.array(p1, float), np.array(u, float)
    e1 = ext if ext1 is None else ext1
    d = p1 - p0; L = np.linalg.norm(d); d /= L
    u = u - d * (u @ d); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    o = p0 - d * ext + u * off[0] + v * off[1]
    pl = cq.Plane(origin=tuple(o), xDir=tuple(u), normal=tuple(d))
    wp = cq.Workplane(pl)
    wp = wp.slot2D(w, h) if slot else wp.rect(w, h)
    return wp.extrude(L + ext + e1)


def hull_plate(circles, z0, z1, n=36):
    """Extruded convex hull of circles [(x, y, r)] between z0 and z1, outline as a smooth periodic spline."""
    from scipy.spatial import ConvexHull
    pts = []
    for (x, y, r) in circles:
        for t in np.linspace(0, 2 * np.pi, n, endpoint=False):
            pts.append((x + r * np.cos(t), y + r * np.sin(t)))
    pts = np.array(pts); h = ConvexHull(pts); P = pts[h.vertices]
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))]
    s = np.linspace(0, seg[-1], 90, endpoint=False)
    Q = np.c_[np.interp(s, seg, np.r_[P[:, 0], P[0, 0]]), np.interp(s, seg, np.r_[P[:, 1], P[0, 1]])]
    wp = cq.Workplane('XY').workplane(offset=min(z0, z1)).spline([tuple(q) for q in Q], periodic=True).close()
    return wp.extrude(abs(z1 - z0))


def sector_yaw(a0, a1, r0, r1, y0, y1, n=24):
    """Annular sector about the yaw axis, angles as atan2(z - YZ, x - RX) in degrees, between heights y0 and y1."""
    A = np.linspace(a0, a1, n)
    pts = [(r1 * math.cos(math.radians(-a)), r1 * math.sin(math.radians(-a))) for a in A] + \
          [(r0 * math.cos(math.radians(-a)), r0 * math.sin(math.radians(-a))) for a in A[::-1]]
    if r0 <= 0:
        pts = [(0.0, 0.0)] + pts[:n]
    w = cq.Workplane('XY').polyline(pts).close().extrude(y1 - y0)
    return w.rotate((0, 0, 0), (1, 0, 0), -90).translate((RX, y0, YZ))


def sector_roll(a0, a1, r0, r1, z0, z1, n=24):
    """Annular sector about the roll axis (angles atan2(y - RY, x - RX)), between Z z0 and z1."""
    A = np.linspace(a0, a1, n)
    pts = [(RX + r1 * math.cos(math.radians(a)), RY + r1 * math.sin(math.radians(a))) for a in A] + \
          [(RX + r0 * math.cos(math.radians(a)), RY + r0 * math.sin(math.radians(a))) for a in A[::-1]]
    return cq.Workplane('XY').workplane(offset=min(z0, z1)).polyline(pts).close().extrude(abs(z1 - z0))


def rot_roll(s, deg):
    return s.rotate((RX, RY, 0), (RX, RY, 1), deg)


def soft(wp, r, sel=None):
    """Fillet if OCC allows it; mock-up, so a failed fillet is skipped (logged)."""
    try:
        e = wp.edges(sel) if sel else wp.edges()
        return e.fillet(r)
    except Exception as ex:
        print('  fillet skipped', r, sel, type(ex).__name__)
        return wp


# ======================================================================================================== wire passages
# Each passage = shell (part material) + power channel (red) + signal channel (blue), side by side along u with a 2 mm
# rib. Power 16 x 6 holds the 4 x 14.5 flat shoulder bundle (1 mm each way); signal 10 x 5 holds 2.2 x 8. Walls 2.4.
PW, PH, SW, SH, RIB, WALL = 16.0, 6.0, 10.0, 5.0, 2.0, 2.4
TOT = PW + RIB + SW
SHW, SHH = TOT + 2 * WALL, PH + 2 * WALL         # 32.8 x 10.8 duct shell


def duct(p0, p1, u, ext=4.0, ext1=None, shell=True, shell_ext=None, shell_ext1=None):
    po = (-TOT / 2 + PW / 2, 0.0); so = (TOT / 2 - SW / 2, 0.0)
    red = box_along(p0, p1, u, PW, PH, ext, po, ext1=ext1)
    blue = box_along(p0, p1, u, SW, SH, ext, so, ext1=ext1)
    se = ext + WALL if shell_ext is None else shell_ext
    se1 = (ext1 + WALL if ext1 is not None else se) if shell_ext1 is None else shell_ext1
    sh = box_along(p0, p1, u, SHW, SHH, se, ext1=se1) if shell else None
    return sh, red, blue


def u_of(cut):
    c = cut[0]
    for x in cut[1:]:
        c = c.union(x)
    return c


parts, cuts = {}, {}

# ================================================================================================ P1: drum + pitch adaptor
print('P1 drum')
# fluted drum: 3.5 mm wall over the RS03 body, 8 outside ribs over the lug slots, front lip for the 8 x M4 (PCD 98),
# rear rim for the cap.
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
# stationary ring (r 28 at the face); flange X 100.5-103.5 to r 77.5 (over the end of the fixed cover wall); skirt
# r 56.5-58.9 back to X 79.8 = inner (moving) wall of the pitch loop channel; hollow neck into the drum (core r 21 open to
# the drum bore: pitch screws reached from inside once the roll motor is out).
pad = cyl(22.0, 97.0, 108.7, ax_pitch)
flange = rev([(52.0, FL_X[0]), (FL_RO - 1.5, FL_X[0]), (FL_RO, FL_X[0] + 1.5), (FL_RO, FL_X[1]), (52.0, FL_X[1])], ax_pitch)
for k in range(5):
    t = math.radians(90 + 72 * k)
    sp = cq.Workplane('YZ').workplane(offset=FL_X[0]).center(RY + 37 * math.cos(t), PZ + 37 * math.sin(t)).rect(8, 32).extrude(FL_X[1] - FL_X[0])
    flange = flange.union(sp.rotate((0, RY + 37 * math.cos(t), PZ + 37 * math.sin(t)), (1, RY + 37 * math.cos(t), PZ + 37 * math.sin(t)), 72 * k))
skirt = rev([(SKIRT[0], SKIRT[2]), (SKIRT[1], SKIRT[2]), (SKIRT[1], FL_X[1]), (SKIRT[0], FL_X[1])], ax_pitch)
NECK_RI = 34.0
neck = rev([(21.0, FL_X[0]), (40.0, FL_X[0]), (40.0, 130.0), (NECK_RI, 130.0), (NECK_RI, 106.0), (21.0, 106.0)], ax_pitch).intersect(
    cq.Workplane('XY').workplane(offset=DRUM_Z0 + 1).rect(400, 1200).extrude(LIP_Z1 - DRUM_Z0 - 1))
p1 = drum.union(pad).union(flange).union(skirt).union(neck)
p1 = p1.cut(cyl(DRUM_RI, DRUM_Z0 - 1, LIP_Z0, ax_roll))
for th in LUG_ANGLES:
    sl = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(RX + SLOT_R / 2, RY).rect(SLOT_R, 2 * SLOT_HALF).extrude(
        LIP_Z0 - DRUM_Z0 + 1).rotate((RX, RY, 0), (RX, RY, 1), th)
    p1 = p1.cut(sl)
for th in LUG_ANGLES:
    x, y = polar(49.0, th)
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=LIP_Z0 - 1).center(x, y).circle(2.25).extrude(15))
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=LIP_Z1 - 4.2).center(x, y).circle(4.8).extrude(10))
p1 = p1.cut(cyl(10.75, 95, 110, ax_pitch)).cut(cyl(21.0, 108.7, 130, ax_pitch))
for k in range(6):
    t = math.radians(-134 + 60 * k); yy, zz = RY + 15.2 * math.cos(t), PZ + 15.2 * math.sin(t)
    p1 = p1.cut(cq.Workplane('YZ').workplane(offset=96).center(yy, zz).circle(2.25).extrude(14))
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    p1 = p1.cut(cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(x, y).circle(2.8).extrude(10))
WIN = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 1).center(RX, RY + 60).rect(56, 40).extrude(DRUM_Z0 + 1 + 7)
p1 = p1.cut(WIN)

# ---- wire passages on the P1 side: mouth on the flange face (X 100.5) -> over the neck -> along the drum -> into the cap
TRUNK_Y, TRUNK_X = 489.0, 140.0
TU = (1, -0.45, 0)
red_l, blue_l = [], []
sh, r_, b_ = duct((FL_X[0], TRUNK_Y, 0.0), (TRUNK_X, TRUNK_Y, 0.0), (0, 0, 1), ext=1.0, ext1=4.0, shell_ext=0.0)
p1 = p1.union(sh); red_l.append(r_); blue_l.append(b_)
sh, r_, b_ = duct((TRUNK_X, TRUNK_Y, 0.0), (TRUNK_X, TRUNK_Y, DRUM_Z0), TU, ext=4.0, ext1=0.0, shell_ext1=0.0)
p1 = p1.union(sh); red_l.append(r_); blue_l.append(b_)
# drop to the RS03 top bay: short branch from the trunk into the window (both cables of the roll motor)
sh, r_, b_ = duct((TRUNK_X, TRUNK_Y, -17.0), (RX - 8, 474.5, -17.0), (0, 0, 1), ext=2)
p1 = p1.union(sh); red_l.append(r_); blue_l.append(b_)
for c in red_l + blue_l:
    p1 = p1.cut(c)
p1 = p1.cut(cyl(DRUM_RI, DRUM_Z0 - 1, LIP_Z0, ax_roll)).cut(WIN)
BEHIND = cq.Workplane('XY').workplane(offset=DRUM_Z0 - 40).center(RX + 50, RY).rect(2 * 50 + 2 * (RX - 106), 400).extrude(40)
p1 = p1.cut(BEHIND)
P1_LIGHT = []          # lightening cuts, filled in the trim section below
parts['P1_drum'] = p1
cuts['WIRE_P1_power'] = [r.cut(BEHIND) for r in red_l]
cuts['WIRE_P1_signal'] = [r.cut(BEHIND) for r in blue_l]

# ======================================================================================================== P1: rear cap
print('rear cap')
# rim r 52.6-57 and centre boss full depth, 4 mm back plate, spoke with the cable channel from the trunk to the stub bore
cap = zring(DRUM_RO - 4.4, DRUM_RO, DRUM_Z0, CAP_Z1)
cap = cap.union(zring(0, DRUM_RO, CAP_Z1 + 4.0, CAP_Z1)).union(zring(0, 26.0, DRUM_Z0, CAP_Z1))
dvec = np.array([RX - TRUNK_X, RY - TRUNK_Y, 0.0]); dvec /= np.linalg.norm(dvec); CU = (-dvec[1], dvec[0], 0.0)
spoke = box_along((TRUNK_X, TRUNK_Y, CAPZ), (RX, RY, CAPZ), CU, SHW, DRUM_Z0 - CAP_Z1, 5.5)
cap = cap.union(spoke)
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    cap = cap.union(cq.Workplane('XY').workplane(offset=CAP_Z1).center(x, y).circle(7.5).extrude(DRUM_Z0 - CAP_Z1))
# stub: inner-race land r 22.5 (1 mm), seat OD 40.0 for the 6808, bore 25 (power above, signal below the roll axis)
cap = cap.union(zring(0, 22.5, CAP_Z1, LAND_Z)).union(zring(0, 20.0, LAND_Z, STUB_Z1))
cap = cap.cut(zring(0, 12.5, DRUM_Z0 + 1, STUB_Z1 - 1))
for th in EAR_ANGLES:
    x, y = polar(61.0, th)
    cap = cap.cut(cq.Workplane('XY').workplane(offset=CAP_Z1 - 1).center(x, y).circle(2.25).extrude(15))
    cap = cap.cut(cq.Workplane('XY').workplane(offset=CAP_Z1 - 1).center(x, y).circle(4.0).extrude(4.5))
# channel in the spoke: inlet under the trunk end, radially to the stub bore
sh, r_, b_ = duct((TRUNK_X, TRUNK_Y, CAPZ), (RX, RY, CAPZ), CU, ext=4.0, ext1=4.0, shell=False)
inlet_r = box_along((TRUNK_X, TRUNK_Y, DRUM_Z0 + 1), (TRUNK_X, TRUNK_Y, CAPZ - PH / 2), TU, PW, PH, 0, (-TOT / 2 + PW / 2, 0))
inlet_b = box_along((TRUNK_X, TRUNK_Y, DRUM_Z0 + 1), (TRUNK_X, TRUNK_Y, CAPZ - SH / 2), TU, SW, SH, 0, (TOT / 2 - SW / 2, 0))
cap = cap.cut(r_).cut(b_).cut(inlet_r).cut(inlet_b)
cuts['WIRE_CAP_power'] = [r_, inlet_r.intersect(zring(0, 200, DRUM_Z0, CAP_Z1))]
cuts['WIRE_CAP_signal'] = [b_, inlet_b.intersect(zring(0, 200, DRUM_Z0, CAP_Z1))]
# stub bore cables (the roll crossing): power above, signal below the roll axis, into the fork rear channel
cuts['WIRE_STUB_power'] = [box_along((RX, RY + 4.5, CAPZ), (RX, RY + 4.5, RZ), (1, 0, 0), PW, PH)]
cuts['WIRE_STUB_signal'] = [box_along((RX, RY - 3.5, CAPZ), (RX, RY - 3.5, RZ), (1, 0, 0), SW, SH)]

# ================================================================================================= fork (P2 replacement)
print('fork front')
ff = hull_plate([(RX, RY, 34.0), (RX - 22, 362.0, 10.0), (RX + 22, 362.0, 10.0)], FRONT_Z[0], FRONT_Z[1])
ff = soft(ff, 2.5, '|Z or >Z or <Z')
boss = ring(0, 22.0, ROLL_OUT, FRONT_Z[0] + 0.5, ax_roll)
seat = ring(SEAT_RI, SEAT_RO, SEAT_Y[0], SEAT_Y[1], ax_yaw)
# thickened back-inboard sector of the seat ring carries the RS02 socket tap
seat = seat.union(sector_yaw(-100, -170, SEAT_RI, 49.0, SEAT_Y[0], SEAT_Y[1]))
# joint pad behind the seat ring: the fork rear arm bolts to it with 2 x M4 along Z, heads at the back
JX, JZ0 = 30.0, RZ + PH / 2 + WALL      # pad half width; joint face Z -45.9 (front face of the rear arm)
pad_j = cq.Workplane('XY').workplane(offset=JZ0).center(RX, (SEAT_Y[0] + SEAT_Y[1]) / 2).rect(2 * JX, SEAT_Y[1] - SEAT_Y[0]).extrude(-30.0 - JZ0)
fork_f = ff.union(boss).union(seat).union(pad_j)
fork_f = fork_f.cut(cyl(SEAT_RI, SEAT_Y[0] - 1, SEAT_Y[1] + 1, ax_yaw))
fork_f = fork_f.cut(cyl(10.75, ROLL_OUT - 1, FRONT_Z[1] + 1, ax_roll))
for k in range(6):
    x, y = polar(15.2, 30 + 60 * k)
    fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=ROLL_OUT - 1).center(x, y).circle(2.25).extrude(30))
    fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 4).center(x, y).circle(4.25).extrude(10))
fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 2).center(RX, RY).circle(24.0).extrude(5))
for a in [-136, -96, -56, 64, 104]:
    t = math.radians(a); x, z = RX + 36.5 * math.cos(t), YZ + 36.5 * math.sin(t)
    fork_f = fork_f.cut(cq.Workplane('XY').add(cq.Solid.makeCylinder(1.8, 30, cq.Vector(x, SEAT_Y[0] - 5, z), cq.Vector(0, 1, 0))))
    fork_f = fork_f.cut(cq.Workplane('XY').add(cq.Solid.makeCylinder(3.3, 10, cq.Vector(x, SEAT_Y[1] - 3.5, z), cq.Vector(0, 1, 0))))
for a0, a1 in [(166, 194), (-22, 30)]:
    fork_f = fork_f.cut(sector_yaw(a0, a1, 0.0, 40.5, SEAT_Y[0] - 1, SEAT_Y[0] + 9.0))
# RS02 inboard socket tap: arc in the thickened sector (r 40.5-47.5, 7 x 6) from the back to the inboard socket pocket,
# and a radial link at -96 deg through the joint pad into the rear arm channel
TAP_Y = (353.4, 359.4)
tap_arc = sector_yaw(-94, -168, 40.5, 47.5, TAP_Y[0], TAP_Y[1])
tap_link = box_along((RX - 4.0, sum(TAP_Y) / 2, YZ - 41.0), (RX - 4.0, sum(TAP_Y) / 2, RZ), (1, 0, 0), 7.0, 6.0, 0)
fork_f = fork_f.cut(tap_arc).cut(tap_link)
for dx in (-JX + 4.5, JX - 4.5):
    fork_f = fork_f.cut(cq.Workplane('XY').workplane(offset=JZ0 - 1).center(RX + dx, (SEAT_Y[0] + SEAT_Y[1]) / 2).circle(2.8).extrude(12))
fork_f = fork_f.cut(cq.Workplane('XY').box(400, 50, 400).translate((RX, 316.6 - 25, 0)))
parts['FORK_front_cap'] = cq.Workplane('XY').workplane(offset=FRONT_Z[1] - 2).center(RX, RY).circle(23.8).extrude(4.0).faces('>Z').edges().chamfer(1.2)

print('fork rear')
# cheek disc round the bearing (r 38, under the stop lugs at r 44), bearing housing r 26-33 from 2.5 behind the cap face,
# arm straight down behind the RS02 (box 44 x 10.8 with the channels inside), lugs to the joint pad, and the exit forward
# into the gap under the RS02.
ARM_HW = 22.0
Y_EX = 319.55                       # exit channel centre: hub dish top 315.8, RS02 underside 323.86
Y_BOT = Y_EX - 3 - WALL             # floor of the exit (outside r 41 only)
cheek = zring(0, 38.0, JZ0, RZ - PH / 2 - WALL)
house = zring(0, 33.0, HOUSE_Z0, JZ0)
arm = box_along((RX, RY, RZ), (RX, Y_BOT, RZ), (1, 0, 0), 2 * ARM_HW, SHH, 0)
lugs = cq.Workplane('XY').workplane(offset=RZ - PH / 2 - WALL).center(RX, (SEAT_Y[0] + SEAT_Y[1]) / 2).rect(2 * JX, SEAT_Y[1] - SEAT_Y[0]).extrude(SHH)
exit_sh = box_along((RX - 6.0, Y_EX, RZ), (RX - 6.0, Y_EX, YZ - 37.0), (1, 0, 0), 16.0 + 2 * WALL, 6.0 + 2 * WALL, 0)
fork_r = soft(cheek.union(house).union(arm), 2.0, '|Z').union(lugs).union(exit_sh)
fork_r = fork_r.cut(zring(0, 26.0, HOUSE_Z0 + 1, BRG_Z[1]))                     # 6808 seat (outer race)
fork_r = fork_r.cut(zring(0, 24.0, BRG_Z[1] + 0.1, RZ))                         # lip r 24 behind the outer race; stub chamber
red_r = [box_along((RX, RY + 9.0, RZ), (RX, Y_EX - 3.0, RZ), (1, 0, 0), PW, PH, 0, (-TOT / 2 + PW / 2, 0))]
blue_r = [box_along((RX, RY + 9.0, RZ), (RX, Y_EX - 3.0, RZ), (1, 0, 0), SW, SH, 0, (TOT / 2 - SW / 2, 0))]
exit_cut = box_along((RX - 6.0, Y_EX, RZ - 3.0), (RX - 6.0, Y_EX, YZ - 37.0), (1, 0, 0), 16.0, 6.0, 0)
for c in red_r + blue_r + [exit_cut]:
    fork_r = fork_r.cut(c)
for dx in (-JX + 4.5, JX - 4.5):
    hole = cq.Workplane('XY').workplane(offset=RZ - PH / 2 - WALL - 1).center(RX + dx, (SEAT_Y[0] + SEAT_Y[1]) / 2).circle(2.25).extrude(SHH + 2)
    cb = cq.Workplane('XY').workplane(offset=RZ - PH / 2 - WALL - 1).center(RX + dx, (SEAT_Y[0] + SEAT_Y[1]) / 2).circle(4.0).extrude(4.5)
    fork_r = fork_r.cut(hole).cut(cb)
# nothing of the rear part inside r 41.5 of the yaw axis below the RS02 (the hub and the cable loop turn there)
fork_r = fork_r.cut(tap_link).cut(cyl(41.5, Y_BOT - 5, SEAT_Y[0], ax_yaw))
cuts['WIRE_FORK_power'] = red_r + [tap_link, tap_arc]
cuts['WIRE_FORK_signal'] = blue_r
cuts['WIRE_YAWEXIT_power'] = [exit_cut]
parts['FORK_front'] = fork_f
parts['FORK_rear'] = fork_r

# ------------------------------------------------------------------- roll stops: printed lugs on the cap's rear face
# Each lug is an r 44-55 sector minus the rear arm placed at the end of travel, so the arm's flank lands flat on the lug
# face exactly at roll -15 and +110.
ARM2D = cq.Workplane('XY').workplane(offset=RZ - 20).center(RX, RY - 80).rect(2 * ARM_HW, 160).extrude(40)
STOP_Z = (CAP_Z1 + 0.5, RZ - PH / 2 - WALL + 1.2)      # from inside the cap plate to 1.2 short of the arm's back face
stops = None
for (a0, a1, ang) in [(-150.0, -122.0, ROLL_IN), (36.0, 64.0, ROLL_OUTW)]:
    blk = sector_roll(a0, a1, 44.0, 55.0, STOP_Z[0], STOP_Z[1]).cut(rot_roll(ARM2D, ang))
    stops = blk if stops is None else stops.union(blk)
cap = cap.union(stops)
parts['P1_cap'] = cap

# ============================================================================================================= bearings
parts['BRG_6808'] = zring(20.0, 26.0, BRG_Z[0], BRG_Z[1])

# ==================================================================================================== hub: dished top
print('hub')
hub0 = cq.importers.importStep(HUB_STEP)
hub = hub0.cut(ring(DISH_R0, 45.0, DISH_Y, 330.0, ax_yaw))
hub = hub.union(ring(19.5, DISH_R0 + 0.01, 312.8, 319.86, ax_yaw))
hub = hub.union(ring(DISH_R0 - 0.5, 38.6, 312.8, DISH_Y, ax_yaw))
hub = hub.union(ring(38.5, 39.3, 305.0, DISH_Y, ax_yaw))
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
cover = rev([(56.0, 75.0), (COVER_RO, 75.0), (COVER_RO, COVER_X1 - 1.5), (COVER_RO - 1.5, COVER_X1), (COVER_RI, COVER_X1),
             (COVER_RI, 77.4), (56.0, 77.4)], ax_pitch)
# feed from the cage's back face: along X behind the cage, then forward into the outer wall (ends flush with its inside)
FY, FZ, FX = RY + 6.0, -79.0, 86.5
zin = -math.sqrt(COVER_RI ** 2 - 6.0 ** 2)
sh_a, r_a, b_a = duct((50.0, FY, FZ), (FX, FY, FZ), (0, 1, 0), ext=0.0, ext1=4.0)
sh_b, r_b, b_b = duct((FX, FY, FZ - 4.0), (FX, FY, zin), (0, 1, 0), ext=0.0, ext1=0.3, shell_ext=0.0, shell_ext1=0.0)
cover = cover.union(sh_a.cut(cyl(COVER_RO - 0.2, 74, 100, ax_pitch))).union(sh_b.cut(cyl(COVER_RO - 0.2, 74, 100, ax_pitch)))
for c in (r_a, b_a, r_b, b_b):
    cover = cover.cut(c)
parts['PITCH_cover'] = cover
loop_p = ring(65.0, COVER_RI - 0.3, 77.7, COVER_X1 + 1.7, ax_pitch)
loop_s = ring(SKIRT[1] + 0.3, 63.0, 77.7, COVER_X1 + 1.7, ax_pitch)
cuts['WIRE_PITCHLOOP_power'] = [loop_p, r_a, r_b]; cuts['WIRE_PITCHLOOP_signal'] = [loop_s, b_a, b_b]

# =============================================================================================== trim (second pass)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trim_concept.py')).read()) if LIGHT and \
    os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trim_concept.py')) else None

# ================================================================================================================ export
GROUP = dict(P1_drum='pitch', P1_cap='pitch', FORK_front='roll', FORK_rear='roll', FORK_front_cap='roll',
             BRG_6808='bearing', HUB_dished='yaw', PITCH_cover='fixed')
info = {}
for k, s in parts.items():
    sol = cq.Workplane('XY').add(s.vals() if isinstance(s, cq.Workplane) else [s])
    vol = sum(x.Volume() for x in sol.solids().vals())
    bb = sol.val().BoundingBox() if len(sol.vals()) == 1 else cq.Compound.makeCompound(sol.vals()).BoundingBox()
    cq.exporters.export(sol, os.path.join(OUT, k + '.stl'), tolerance=0.05, angularTolerance=0.1)
    info[k] = dict(group=GROUP[k], vol_mm3=round(vol, 0), mass_petg_g=round(vol * PETG, 1),
                   bb=[round(bb.xmin, 2), round(bb.ymin, 2), round(bb.zmin, 2), round(bb.xmax, 2), round(bb.ymax, 2), round(bb.zmax, 2)],
                   size=[round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)], solids=len(sol.solids().vals()))
    print(k, info[k])
for k, lst in cuts.items():
    cq.exporters.export(u_of(lst), os.path.join(OUT, k + '.stl'), tolerance=0.05, angularTolerance=0.1)
json.dump(info, open(os.path.join(OUT, 'parts.json'), 'w'), indent=1)
asm = cq.Assembly()
for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'BRG_6808', 'HUB_dished', 'PITCH_cover']:
    asm.add(parts[k], name=k)
asm.save(os.path.join(OUT, 'roll_fork_concept.step'))
print('done')
