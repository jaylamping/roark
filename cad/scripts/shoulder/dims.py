"""Left shoulder, roll drum and fork: every dimension of the first SolidWorks pass, in one place.

Torso STEP frame, mm: X outboard, Y up, Z forward (hardware/shoulder/study-20261111/MEASUREMENTS.md section 0).
Values come from concept-roll-fork/CONCEPT.md and build_concept.py (second pass); changes against it are marked CHANGED.
"""
import math

# ---- axes (MEASUREMENTS.md section 0) ----
RX, RY = 170.49, 424.86          # roll axis along Z through (RX, RY); pitch axis height
PZ = -0.014                      # pitch axis Z (pitch axis along X)
YZ = 5.99                        # yaw axis along Y through (RX, YZ)
ROLL_OUT, ROLL_REAR = 30.64, -25.96      # roll RS03 output face / rear face (Z)
PITCH_OUT, PITCH_REAR = 97.0, 40.4       # pitch RS03 output face / rear face (X)
RS02_REAR, RS02_SEAT, RS02_UNDER, RS02_OUT = 365.26, 351.86, 323.86, 319.86   # yaw RS02 (Y)
PETG = 1.27e-3                   # g/mm3, solid

# ---- roll stops (CHANGED: inward -11, was -15; the upper arm reaches the cage at -12..-13 when yawed 45-75 deg) ----
# Driven in the cap part by the global variables ROLL_STOP_IN / ROLL_STOP_OUT (Tools > Equations).
ROLL_STOP_IN, ROLL_STOP_OUT = -11.0, 110.0

# ---- drum (P1) ----
DRUM_RI, DRUM_RO = 48.0, 57.0    # bore over the RS03 body / outside of ribs and rear rim
WALL_RO, LIP_RO = 51.5, 56.0     # drum wall between the ribs / front lip
LUG_ANGLES = [22.5 + 45 * k for k in range(8)]   # RS03 cast lugs at r 53
SLOT_HALF, SLOT_R = 5.5, 54.5    # lug slots, 11 wide, to r 54.5
LIP_Z0, LIP_Z1 = 28.3, 36.0      # front lip, 8 x M4 on PCD 98 into the RS03 lugs
LIP_RI = 43.0
LIP_PCD_R = 49.0
DRUM_Z0 = -28.5                  # rear rim = cap front face
EAR_ANGLES = [125.0, 148.0, 212.0]   # cap screws, inboard/top; CHANGED from 130/165/200: those ears reached X 104 into the flange ring
EAR_R, EAR_PCD = 7.5, 61.0
WIN_ANGLES = [0.0, 45.0, 135.0, 225.0, 270.0, 315.0]   # windows in the inner wall into the pockets under the skin
PORT_ANGLE = 0.0                 # the one window through the skin: driver access to the 6 pitch pad screws (styled oval port)
SKIN_RI = 55.0                   # DRESSED: closed outer skin r 55-57 over the roll RS03; pockets r 51.5-55 between the lug ribs
POCKET_Z = (DRUM_Z0 + 4.0, LIP_Z0 - 3.0)
FLARE = dict(x0=105.0, x1=119.0, x2=124.0, r=56.0, fillet=12.0)   # DRESSED: neck flares into the drum (pitch axis)
CUFF = dict(ri=39.75, ro_top=43.5, ro_bot=41.7, y0=317.8, notch=(-122.0, -78.0))
# DRESSED 2: cuff round the RS02 housing (r 39.25), tapering to r 41.7 and down to 2 mm above the hub rim (Y 315.8), to
# continue the arm's top (r 39 at Y 302); notched round the fork rear's yaw exit
DOME = dict(r=55.0, edge=5.0, back_t=2.4, pocket_r=(24.5, 52.6), pockets=[(-20.0, 40.0), (50.0, 130.0), (140.0, 200.0)])
# DRESSED 2: fork front as a full dome cap r 55 (drum skin r 57: the dome sits 3 mm in front of the lip face), R5-ish
# front edge (arm cheeks R5, drum R7), pocketed from the back
RS03_BUMP = dict(x0=RX - 53.0, x1=RX - 46.0, y=9.5, z0=18.6)   # relief for the RS03 housing boss at r 50.25 inboard (Z 19.6-28.1)
TOPWIN = dict(x=14.0, z0=-28.5, z1=-6.0)   # window over the roll RS03 top connector bay (half width X)
# pitch adaptor
PAD_R, PAD_X = 22.0, (97.0, 108.7)
PAD_HOLES = [-134.0 + 60 * k for k in range(6)]   # 6 x M4 on PCD 30.4 (angle in the Y-Z plane from +Y toward +Z)
NECK = dict(ri_core=21.0, ro=40.0, ri=35.6, x0=100.5, x_disc=106.0, x1=130.0)
SPOKES = dict(n=5, a0=90.0, w=9.0, r0=21.0, r1=50.0, x0=100.5, x1=104.5, screw_r=46.0, insert_depth=3.8)   # M3 x 4 inserts   # carry the flange ring
# ---- flange ring (separate printed part; CHANGED: was the 1.8 mm flange on P1 at X 100.5-102.3) ----
RING = dict(ri=42.0, ro=77.5, x0=104.5, x1=106.3)   # 1.8 thick, printed flat
# ---- pitch loop cover (torso side, fixed); CHANGED: outer wall runs on to 2 mm short of the ring (X 104.5)
COVER = dict(ri=56.0, back_x=(75.0, 77.4), out=(73.5, 75.9), in_=(55.0, 57.4), in_x1=98.5)
COVER['x1'] = RING['x0'] - 2.0
# CHANGED (torso interface, 2026-11-11): the cable feed enters the cover from BELOW (the back entry does not fit the rev A
# frame). Two separate risers (power 16 x 6, signal 10 x 5, 2.4 walls) come straight up into the bottom of the channel.
# Placeholder position until the rev A frame model exists: one feature group (FEED_*) driven by these numbers.
# Rev A: the bundles rise in the void under the step overhang (rev A X 75-113 = old X 37-75, Y 300-353), run outboard
# under the cover and turn up into its bottom. Old-frame X below; rev A = +38. Duct section as the trunk (power and signal
# side by side across Z, 2 mm rib, 2.4 walls), the flat side across Z so both bends are about the bundles' thin axis.
FEED = dict(x_rise=69.0, x_up=88.0, y0=300.0, y_run=337.6, z=0.0)
# Cover fixing (placeholders): M5 into T-nuts in the rev A X 113 outward slots: upper posts (Z +-60, Y 425),
# step side rail (Y 363.6), top side rail (Y 485). (Y, Z) of each screw, old-frame coordinates.
COVER_TABS = [(RY, 60.0), (RY, -60.0), (363.6, 30.0), (485.0, -30.0)]
# ---- wire passages (power 16 x 6, signal 10 x 5, 2 mm rib, 2.4 walls) ----
PW, PH, SW, SH, RIB, WALL = 16.0, 6.0, 10.0, 5.0, 2.0, 2.4
TOT = PW + RIB + SW
SHW, SHH = TOT + 2 * WALL, PH + 2 * WALL         # 32.8 x 10.8 duct shell
P_OFF, S_OFF = -TOT / 2 + PW / 2, TOT / 2 - SW / 2   # channel centre offsets across the duct (-6, +9)
TRUNK_Y, TRUNK_X = 489.0, 140.0
TU = (1.0, -0.45, 0.0)
# ---- rear cap ----
CAP_Z1 = -39.3                   # rear face of the cap plate
CAPZ = (DRUM_Z0 + CAP_Z1) / 2    # cap channel centre
CAP_T, BOSS_R, RIM_T = 3.0, 24.0, 3.0
CAP_WINDOWS = [(-112, -72), (-32, 14), (154, 194)]
LAND_Z, LAND_R = -40.3, 22.5
BRG_Z = (-40.3, -47.3)           # 6808-2RS 40 x 52 x 7, floating
STUB_R, STUB_BORE = 20.0, 12.5   # stub OD 40.0, bore 25
STOP_R = (44.0, 55.0)
# ---- fork ----
HOUSE_Z0 = CAP_Z1 - 2.5
RZ = -51.3                       # fork rear channel centre
FRONT_Z = (39.0, 47.0)           # front cheek
SEAT_Y = (RS02_SEAT, 361.9)      # seat ring on the RS02 rear housing face
SEAT_RI, SEAT_RO = 33.5, 45.0
RS02_SCREWS = [-136.0, -96.0, -56.0, 64.0, 104.0]   # 5 x M3 on PCD 73 (yaw angle atan2(z - YZ, x - RX))
SOCKET_POCKETS = [(162.0, 198.0), (-26.0, 34.0)]   # CHANGED: 4 deg wider each side (RS02 socket body reached 196 deg)
TAP_Y = (353.4, 359.4)
JX = 30.0                        # joint pad half width
JZ0 = RZ + PH / 2 + WALL         # -45.9: joint face (front face of the rear arm)
BACK_Z = RZ - PH / 2 - WALL      # -56.7: fork rear back face
ARM_HW = 17.0
Y_EX = 319.55                    # yaw exit channel centre
Y_BOT = Y_EX - 3 - WALL
CHEEK_R, HOUSE_R = 35.0, 33.0
BRG_SEAT_R, BRG_LIP_R = 26.0, 24.0
# ---- hub (frozen interface; dished top) ----
DISH_R0, DISH_Y = 23.5, 315.8
HUB_WIN_A = 7.9
# Hub lower half, prepared for the arm joint work (all OFF by default; the frozen interface is unchanged when off):
HUB = dict(spigot_ext_on=0, spigot_ext_len=6.0, spigot_taper=0.0, spigot_ri=28.0, spigot_ro=35.8, spigot_y0=296.0,
           lug2_on=0, lug2_angle=90.0, lug_r=(19.0, 30.0), lug_half_deg=15.0, lug_y=(288.0, 296.0))

# ---- print bed ----
BED = 256.0


def polar(r, th, c=(RX, RY)):
    t = math.radians(th)
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))


def yaw_pt(r, a, y):
    """Point at radius r, yaw angle a (atan2(z - YZ, x - RX)), height y."""
    t = math.radians(a)
    return (RX + r * math.cos(t), y, YZ + r * math.sin(t))


def pitch_pt(r, a, x):
    """Point at radius r about the pitch axis, angle a in the Y-Z plane measured from +Y toward +Z, at X x."""
    t = math.radians(a)
    return (x, RY + r * math.cos(t), PZ + r * math.sin(t))


def roll_pt(r, a, z):
    t = math.radians(a)
    return (RX + r * math.cos(t), RY + r * math.sin(t), z)
