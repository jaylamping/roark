"""Left shoulder, roll drum and fork: every dimension of the first SolidWorks pass, in one place.

Torso STEP frame, mm: X outboard, Y up, Z forward (hardware/shoulder/study-20261111/MEASUREMENTS.md section 0).
Values come from concept-roll-fork/CONCEPT.md and build_concept.py (second pass); changes against it are marked CHANGED.
"""
import math
import os

# ---- axes (MEASUREMENTS.md section 0) ----
RX, RY = 170.49, 424.86          # roll axis along Z through (RX, RY); pitch axis height
PZ = -0.014                      # pitch axis Z (pitch axis along X)
YZ = 5.99                        # yaw axis along Y through (RX, YZ)
ROLL_OUT, ROLL_REAR = 30.64, -25.96      # roll RS03 output face / rear face (Z)
PITCH_OUT, PITCH_REAR = 97.0, 40.4       # pitch RS03 output face / rear face (X)
RS02_REAR, RS02_SEAT, RS02_UNDER, RS02_OUT = 365.26, 351.86, 323.86, 319.86   # yaw RS02 (Y)
PETG = 1.27e-3                   # g/mm3, solid
DISH_R0 = 23.5
DISH_Y = float(__import__('os').environ.get('DISH_Y', 318.36))   # HUB REV B: floor top raised 315.8 -> 318.36 (yaw-loop gap 8.06 -> 5.5)
DISH_FILLET = 1.5

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
SKIN_RI = 54.0                   # DRESSED: closed outer skin r 55-57 over the roll RS03; pockets r 51.5-55 between the lug ribs
POCKET_Z = (DRUM_Z0 + 9.5, LIP_Z0 - 3.0)   # SMOOTH: start deeper, the cap screws' inserts go into the rear end
DRUM_CROWN = [(DRUM_Z0, 54.5), (-24.0, 56.2), (-14.0, 57.0), (14.0, 57.0), (27.0, 56.2), (33.0, 55.2), (LIP_Z1, 54.5)]
LOOK = os.environ.get('LOOK', '')
SHAPE_A = True       # look option a, chosen by Joey 2026-11-11 20:01Z (look-options/OPTIONS.md)
FRONT_BLEND = '3'    # front blend variant 3, the true wrap: adopted by Joey 2026-11-12 02:54Z (look-options/front_blend)
if SHAPE_A:
    # option a (match the arm): the drum as a bobbin like the forearm cheeks (forearm_organic_cheek_*: rolled rims at both
    # ends, a slightly smaller middle). Never above the round-1 r 57, so every clearance to the drum holds.
    # middle r 56.1, not lower: the RS03 lug slots and the top connector window inside reach r 54.5 (1.6 mm skin)
    DRUM_CROWN = [(DRUM_Z0, 54.0), (-26.0, 56.0), (-22.0, 57.0), (-17.5, 56.6), (-11.0, 56.1), (17.0, 56.1), (23.0, 56.6), (27.5, 57.0),
                  (31.5, 56.0), (LIP_Z1, 54.0)]
# ORGANIC: the drum skin is a loft through these (Z, r) circles: crowned, r 57 at most (RS02 passes 2.6 mm below it)
CAP_RIM_R = 54.5                 # ORGANIC: the cap rim continues the drum's rear end
FRONT_CROWN = dict(z0=42.0, z1=49.0, inset=9.0)   # ORGANIC: the fork front face crowns forward to Z 49 (was flat at 47)
CAP_FLOOR = 45.0                 # floor of the press-in cap recess (cap top 48.5: 0.5 below the crown, like the arm's caps)
BELL = dict(x=(106.3, 113.0, 120.0, 127.0, 134.0, 141.0), top=60.0, bot=41.0, front=34.0, rear=27.0, wall=2.5,
            top_taper=((127.0, 60.0), (141.0, 56.0) if not SHAPE_A else (141.0, 55.8)))   # CREASE: the top dives under the drum skin (r 57) instead of ending in a 3 mm step at X 134
# SMOOTH: the pitch adaptor is an egg-section bell round the pitch axis (top r 60 over the trunk, bottom r 41 clear of the
# fork and RS02 swing, Z +34 / -27 inside the drum's span), hollow (2.5 wall), replacing the neck tube and flare
CAP_SCREW_ANGLES = [0.0, 180.0, 270.0]   # SMOOTH: 3 x M3 thread-forming, axial, inside the outline, into 2.6 mm pilots in the drum wall
CAP_SCREW_R = 50.0
# STOP REV 2 (A2, checks/B_ROLL_STOPS.md, approved 2026-11-12): one tooth at fork angle 270, where the fork rear's layers
# (normal to Y) are normal to the tooth's radial direction, so its bending and shear lie in the layer plane; r 30-40, +-14
# deg; carries a 60 N.m stall (RS03 peak) with SF 1.65. Was r 27-33, +-10 deg at 193 deg (SF 0.44 at a stall).
STOP_SLOT = dict(r=(28.0, 42.0), z_floor=-31.0, tooth_r=(30.0, 40.0), tooth_angle=270.0, tooth_half=14.0, ring_r=(26.0, 44.0),
                 ring_past=20.0, pad_r=(33.0, 42.0), pad_half=19.0, pad_corner=3.0, root_r=1.5)   # pad within the leg's width (X +-13.7 at r 42)
# SMOOTH: roll stops inside the outline: a tooth on the fork rear cheek runs in an arc slot in a ring on the cap's rear face
FLARE = dict(x0=105.0, x1=119.0, x2=124.0, r=56.0, fillet=12.0)   # DRESSED: neck flares into the drum (pitch axis)
CUFF = dict(ri=39.75, ro_top=43.0, ro_bot=41.35, ro_mid=(42.9, 336.0), y0=DISH_Y + 2.0, notch=(-122.0, -78.0))
# DRESSED 2: cuff round the RS02 housing (r 39.25), tapering to r 41.7 and down to 2 mm above the hub rim (Y 315.8), to
# continue the arm's top (r 39 at Y 302); notched round the fork rear's yaw exit
DOME = dict(r=55.0, edge=5.0, back_t=2.4, pocket_r=(24.5, 52.6), pockets=[(-20.0, 40.0), (50.0, 130.0), (140.0, 200.0), (212.0, 252.0), (288.0, 328.0)])
# DRESSED 2: fork front as a full dome cap r 55 (drum skin r 57: the dome sits 3 mm in front of the lip face), R5-ish
# front edge (arm cheeks R5, drum R7), pocketed from the back
RS03_BUMP = dict(x0=RX - 53.0, x1=RX - 46.0, y=9.5, z0=18.6)   # relief for the RS03 housing boss at r 50.25 inboard (Z 19.6-28.1)
TOPWIN = dict(x=14.0, z0=-28.5, z1=-6.0)   # window over the roll RS03 top connector bay (half width X)
# pitch adaptor
PAD_R, PAD_X = 22.0, (97.0, 108.7)
PAD_HOLES = [-134.0 + 60 * k for k in range(6)]   # 6 x M4 on PCD 30.4 (angle in the Y-Z plane from +Y toward +Z)
NECK = dict(ri_core=21.0, ro=40.0, ri=35.6, x0=100.5, x_disc=106.0, x1=130.0)
SPOKES = dict(n=5, a0=108.0, w=9.0, r0=21.0, r1=50.0, x0=100.5, x1=104.5, screw_r=46.0, insert_depth=3.8)   # M3 x 4 inserts   # carry the flange ring
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
# SMOOTH: the down-run (trunk B) sits at roll angle 135 deg, r 58, its width along the skin; trunk A runs along X at Y 470
# inside the bell; the outline swells about 7 mm over trunk B only
TRUNK_ANG, TRUNK_R = 135.0, 58.0
TRUNK_X, TRUNK_Y = RX + TRUNK_R * math.cos(math.radians(TRUNK_ANG)), RY + TRUNK_R * math.sin(math.radians(TRUNK_ANG))
TRUNK_AY = 470.0
TRUNK_B_ZTOP = SHW / 2 + WALL      # trunk B runs forward to take trunk A's full width
BRANCH_END = (RX - 8.0, 474.5)
TU = (math.cos(math.radians(TRUNK_ANG - 90)), math.sin(math.radians(TRUNK_ANG - 90)), 0.0)
# ---- rear cap ----
CAP_Z1 = -39.3                   # rear face of the cap plate
CAPZ = (DRUM_Z0 + CAP_Z1) / 2    # cap channel centre
CAP_T, BOSS_R, RIM_T = 3.0, 24.0, 3.0
CAP_WINDOWS = [(-112, -72), (-32, 14), (154, 194)]
LAND_Z, LAND_R = -40.3, 21.5      # check (d): Ø43 inner-race land (was Ø45: reached the seal)
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
RS02_ACCESS_ANG = (64.0, 104.0)  # the two front screws the cheek covers: straight-up driver bores, plugged flush
# PLUG POCKET pp_r, adopted (Joey "go", 2026-11-13; look-options/plug_pocket): the RS02 re-clocked +40 deg, so its in-use
# socket sits at 228 deg over the socket tap and the radial XT30(2+2) plug and folded lead stay inside the wall. Its five
# screws, both socket pockets and the access bores turn with it (144 is under the cheek). RS02_RECLOCK=0 builds the old clock.
# The RS02's zero is then a +40 deg software offset.
RS02_RECLOCK = os.environ.get('RS02_RECLOCK', '1') != '0' or LOOK == 'pp_r'
if RS02_RECLOCK:
    RS02_SCREWS = [a + 40.0 for a in RS02_SCREWS]
    SOCKET_POCKETS = [(a0 + 40.0, a1 + 40.0) for a0, a1 in SOCKET_POCKETS]
    RS02_ACCESS_ANG = (104.0, 144.0)
JX = 21.5                        # joint pad half width (SMOOTH: a rounded flare of the arm, was 30)
JZ0 = RZ + PH / 2 + WALL         # -45.9: joint face (front face of the rear arm)
BACK_Z = RZ - PH / 2 - WALL      # -56.7: fork rear back face
ARM_HW = 17.0
Y_EX = 319.55                    # yaw exit channel centre
Y_BOT = Y_EX - 3 - WALL
CHEEK_R, HOUSE_R = 35.0, 33.0
BRG_SEAT_R, BRG_LIP_R = 26.1, 24.0   # check (d): housing Ø52.2 (printed on its side) with a flat-topped teardrop
BRG_LIP_Z = -47.7                # check (d): the outer-race lip 0.4 behind the bearing's rear face (the outer race floats)
STUB_LEAD = 0.5                  # check (d): 0.5 x 45 lead-in on the stub's free end (stub stays Ø40.0, as the arm's coupon)
# ---- hub (frozen interface; dished top) ----

HUB_WIN_A = float(os.environ.get('HUB_WIN_A', '7.9'))   # D3c4 candidate: 248 (back half, midway between the -82 / -142 boss tubes)
HUB_WIN_CLIP = float(os.environ.get('HUB_WIN_CLIP', '0'))   # D3c6: the window's slot is not cut inside this distance along its centre line (15.7 keeps both boss tubes beside it whole); 0 = off
# Hub lower half, prepared for the arm joint work (all OFF by default; the frozen interface is unchanged when off):
HUB = dict(spigot_ext_on=0, spigot_ext_len=6.0, spigot_taper=0.0, spigot_ri=28.0, spigot_ro=35.8, spigot_y0=296.0,
           groove_on=1,
           # spigot groove for the arm's ridge (arm thread section, roark 3d23f91 r1c/ridge_groove_profile.png): opens Y 297-301
           # at r 35.8, bottom r 34.3 from Y 297.87 to 299.50, load flank (low Y) 30 deg from the radial plane, high flank 45 deg;
           # full depth over theta 50-130 and 230-310 (theta from +X toward +Z about the yaw axis; seam at 0/180), run-outs to
           # full wall at 40/140 and 220/320
           groove=dict(r_out=35.8, r_bot=34.3, y_open=(298.0, 302.0), y_bot=(298.87, 300.50), centres=(90.0, 270.0), full_half=60.0,
                       runout=10.0, steps=4),
           # REV C (arm thread, roark 7ad03f9 ridge_groove_profile_land2.png): 2 mm land Y 296-298, groove Y 298-302, full depth
           # 30-150 / 210-330, smooth run-outs to 20/160 and 200/340 (lofted)
           band_fill=dict(on=1, r=(30.0, 39.3), y=(302.3, 312.8), sectors=((60.0, 120.0), (240.0, 300.0))),
           # REV C+ lever (a), agreed with the arm side 20:33Z, deepened to r 23 at 22:45Z (stop case, R1.0 corner near the ridge end): the
           # spigot wall thickened inward over the groove arcs (the cable
           # window passes r 15-19 at these heights, so the bundle never needs these sectors); rounded ends
           wall_fill=dict(on=1, r=(23.0, 28.2), y=(296.0, 302.3), sectors=((25.0, 155.0), (205.0, 335.0)), end_r=1.2),
           disc_corner_r=0.3,
           # REV C: the window band is filled over the two sectors the fore-aft moment loads (clear of the cable window at 8 deg)
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
# STOP REV 2, torque path (checks/B_ROLL_STOPS.md): the fork rear's channels shifted 0.6 mm in the leg (side walls 1.6 / 2.4 mm
# where the leg is narrowest, Y 380-395; were 1.0 / 3.0), and two more joint screws at X +-27 (span 54, was 34)
CH_DX = 0.6      # 1.0 put the power channel's wall tangent to the X -17 counterbore; 0.6: walls 1.6 / 2.4 at Y 390 (were 1.0 / 3.0)
# SIDE CENTRE r 47 (Joey 2026-11-12 05:33Z, go): the lower sleeve a closed ring on the fork front, split at Y 340.
# SIDE_CENTRE=0 builds the earlier sleeve; 1 the r 54.5 mock-up.
SIDE_CENTRE = os.environ.get('SIDE_CENTRE', '47')
SIDE_CENTRE = '' if SIDE_CENTRE == '0' else SIDE_CENTRE
JY = (SEAT_Y[0] + SEAT_Y[1]) / 2   # joint screw row (Y 356.9)
# fork joint screws (X offset from RX, Y): the original pair at +-17, the outer pair at +-27 (stop torque path), and with
# the r 47 sleeve a lower pair at +-22, Y 345.5 (the fork rear now reaches down to Y 340): the stop couple per screw drops
# by about a third against four
JOINT_PTS = [(-JX + 4.5, JY), (JX - 4.5, JY), (-27.0, JY), (27.0, JY)] + ([(-22.0, 345.5), (22.0, 345.5)] if SIDE_CENTRE == '47' else [])
if SIDE_CENTRE == '47':
    # layout N (adopted 2026-11-12): every counterbore closed with >= 1.5 mm to the fork rear's edge, whose swell is off-centre
    # (counterbore centres within X -32.8..+26.6 on the top row, -26..+21 on the lower). Rated joint layer SF 1.49 (FEA).
    # Screws: ISO 7380 M4 button heads, all six (the outer recesses are only about 3.1 mm deep)
    JOINT_PTS = [(-17.0, JY), (17.0, JY), (-27.0, JY), (26.0, JY), (-22.0, 345.5), (20.0, 345.5)]
if os.environ.get('JOINT_LAYOUT') == 'N2':  # N with the top row 1.1 mm higher (Y 358.0): more spread between the rows
    JOINT_PTS = [(-17.0, 358.0), (17.0, 358.0), (-27.0, 358.0), (26.0, 358.0), (-22.0, 345.5), (20.0, 345.5)]
if os.environ.get('JOINT_LAYOUT') == 'N':   # rear_screws (a), as built: today's spread with the two right-hand holes moved in 1-2 mm
    JOINT_PTS = [(-17.0, JY), (17.0, JY), (-27.0, JY), (26.0, JY), (-22.0, 345.5), (20.0, 345.5)]
if os.environ.get('JOINT_LAYOUT') == 'G':   # rear_screws mock-up (a): symmetric two rows, every counterbore >= 1.5 mm from the edge
    JOINT_PTS = [(-12.0, JY), (12.0, JY), (-24.0, JY), (24.0, JY), (-20.0, 345.5), (20.0, 345.5)]
if os.environ.get('JOINT2'):          # the earlier two-screw joint, for the look-options/rear_screws comparison only
    JOINT_PTS = JOINT_PTS[:2]
HUB_RIM_CHAMFER = 0.5 if os.environ.get('HUB_CHAMFER') else 0.0
# REV D candidate (arm thread's split-collar stop case, 2026-11-12): the groove a full ring at full depth (no run-outs) and the
# inward wall fill a full ring (r 23-28.2). Default off until the arm thread's result says it fixes the stop case.
HUB_GROOVE_RING = bool(os.environ.get('HUB_GROOVE_RING'))   # hub-top fix (A_HUB_LUGS): 0.5 x 45 on the six screw-hole rims at the RS02 face
# REV D2 (bolster on rev D, default off; needs HUB_GROOVE_RING): '1' the inward fill deepened to r 20 (the lugs' inner
# corners are at r 19.4) and carried up to the floor as a 45 deg cone, outside the cable sector (-22..38 deg), where it only goes to
# r 21 (bundle r 15.5-20 + 1); '2' adds a backing block (r 14.5-19.4) behind the -X lug below Y 296, clear of the hub-screw
# driver columns at 158 and 218 deg. No interface surface changes (groove, r 35.8, lug faces, holes, land).
# 'c' trimmed: the r 20 bore only behind the -X lug (140-220 deg, Y 296-302.3, 45 deg top) plus the cable-sector r 21; 'd' = 'c'
# plus the backing; 'e' D2's full profile (bore + 45 deg cone into the floor) over 140-220 deg only, plus the cable-sector r 21
HUB_D2 = os.environ.get('HUB_D2', '') if HUB_GROOVE_RING else ''
# REV D3 (D3b as agreed 2026-11-13 05:43Z; yaw torque path, default off): both lugs grown outward to one straight outer face at
# X offset 34.4 (from 29.5) over their whole height, Y 288 to the spigot underside (Y 296), on their own Z faces (Z 1.0 / 11.0).
# The arm's seam-split collar pockets pinch the lugs along Z through picked flat shim plates, so the yaw torque bears on the
# whole lug face at a larger radius instead of through the lug bolts. Also remakes the spigot skin (topology; see build_parts)
HUB_D3 = bool(os.environ.get('HUB_D3')) and HUB_GROOVE_RING      # on rev D, with or without D2
CH_DZ = -1.0 if os.environ.get('LEG2') else 0.0   # LEG2 mock-up: the fork rear's channels 1 mm further back (front wall 3.4)
