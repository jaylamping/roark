# Left shoulder, roll drum and fork: first SolidWorks pass (2026-11-11)

The agreed concept ([concept-roll-fork/CONCEPT.md](../concept-roll-fork/CONCEPT.md), "drum and fork, no yaw ring") as
SolidWorks parts, dressed twice for the look of the organic arm.

- **Built by:** scripts in [cad/scripts/shoulder/](../../../../cad/scripts/shoulder/) (dims.py holds every dimension).
- **Files:** [cad/shoulder/left/](../../../../cad/shoulder/left/).
- **Frame:** parts are modelled in the old-frame torso coordinates of CONCEPT.md (X outboard, Y up, Z forward, mm).
  The rev A frame sits 38 mm further inboard on the assembly mate TORSO_X_SHIFT.
- **Shell:** option A, chosen by Joey: opening r 80.
- **Not done in this pass:** FEA and print files.

![look](D1_look_shell_optionA.png)

## Files

| File | What |
|---|---|
| `shoulder_skeleton_left.SLDPRT` | Pitch, roll and yaw axes; motor faces; interface sketches (bolt circles, keep-outs, 6808 section, passage sections, stop centrelines) |
| `shoulder_roll_drum_left.SLDPRT` | P1: closed drum round the roll RS03, pitch pad and flared neck, cable trunk under a spine fairing, branch to the RS03 top bay, 5 spokes for the flange ring |
| `shoulder_pitch_flange_ring_left.SLDPRT` | Moving front wall of the pitch loop channel, its own part: 1.8 mm, prints flat, 5 x M3 into inserts in the spokes |
| `shoulder_roll_cap_left.SLDPRT` | Rear cap: hollow stub OD 40.0 / bore 25 with 1 mm land, radial channel, 2 stop lugs, 3 x M4 ears |
| `shoulder_fork_front_left.SLDPRT` | Dome cap on the roll output (r 55), RS02 seat ring, cuff round the RS02, socket pockets and tap, joint pad |
| `shoulder_fork_rear_left.SLDPRT` | Rear cheek with the 6808 seat (Ø52), arm with power and signal channels, yaw exit |
| `shoulder_roll_drum_port_cap_left.SLDPRT` | Press-in cap closing the drum's driver port flush with the skin |
| `shoulder_hub_left.SLDPRT` | Hub with the dished top, on the frozen hub; spigot extension and second lug pair prepared, suppressed |
| `shoulder_pitch_loop_cover_left.SLDPRT` | Fixed cover round the pitch motor, bottom feed (FEED_*), 4 M5 placeholder pads |
| `shoulder_left_asm.SLDASM` | Everything above plus the motors, the 6808, the frozen upper arm and the rev A frame |
| `ref/` | Imported references: pitch RS03 as placed, rev A frame, upper arm halves and ring |

## Roll stops

- **Values:** inward **-11 deg** (confirmed), outward +110 deg.
- **Where to change them:** one place in `shoulder_roll_cap_left`, Tools > Equations: the global variables
  `ROLL_STOP_IN` and `ROLL_STOP_OUT`.
- **How they drive the lugs:** each variable sets one reference plane through the roll axis (`STOP_IN_AXIS`,
  `STOP_OUT_AXIS`). That plane carries the lug's contact face, set off by the arm's half-width.
- **Tested:** setting -15 and back to -11 rebuilds the lug in the right place.

## Masses (solid PETG 1.27 g/cc, SolidWorks volumes)

| Part | Bare (g) | Round 2 (g) | Organic, final (g) | What the cosmetics cost (organic) |
|---|---|---|---|---|
| Drum with pitch adaptor | 189.0 | 232.5 | **238.3** | Crowned closed skin with pockets under it, about +24 g; neck flare, about +10 g; lofted spine over trunk B and the branch, about +17 g |
| Flange ring | 29.2 | 29.2 | **29.2** | |
| Rear cap with stub and lugs | 74.1 | 79.5 | **75.2** | Closed plate, +6.8 g; rim follows the drum's r 54.5 end |
| Fork front | 92.2 | 153.9 | **140.8** | Crowned dome cap, pocketed behind (5 pockets), about +18 g; cuff with a gentle swell, 1.6 mm at the hub, about +31 g |
| Fork rear | 63.4 | 61.0 | **60.6** | R6 back dome, rounded arm and joint lugs |
| Fork press-in cap | 6.6 | 6.6 | **5.5** | Recessed 1.5 mm below the crown, like the arm's caps |
| Hub | 60.2 | 60.2 | **60.2** | Prepared features suppressed |
| **Shoulder total** | **514.7** | **622.9** | **609.8** | Working number about 600 g |
| Pitch loop cover (torso side) | 102.5 | 102.3 | **102.3** | |

- The round-2 rear web (cuff to fork rear arm) is dropped. It sat 0.5 mm off the fork rear arm and carried no load, so it
  was purely cosmetic (6.5 g).
- If mass matters, drop in this order:
  1. the spine (trunk B and the branch then show as rounded ducts), about 17 g
  2. a partial cuff (outboard and front faces only), about 12 g
- The drum skin and the cuff stay (Joey).

## Size

| | X | Y | Z |
|---|---|---|---|
| Body without cover and ring (old frame) | 97-227.5 | 288-500 | -56.7 to 51 |

- Rev A: add 38 to X.
- Every part fits the P2S 256 mm cube. The largest is the cover, 38.9 x 200.7 x 151.7.

## Checks

**Static interference** (exact solid booleans):

- The printed parts against the vendor RS03/RS02 and each other: none, after the fixes below.
- The SolidWorks interference check at the brief's 36 poses (neutral and roll -11 / +45 / +110, each at pitch
  -30 / 0 / +90 and yaw -90 / 0 / +90) found no shoulder-to-shoulder, shoulder-to-motor or shoulder-to-arm interference.
  - Its hits against the frame part are shell parts in that model: the cover and drum against `shellpart__collar_1`,
    the drum against two collar screws, and the ring against the upper spine pad (6.45 mm³). The remaining hits are the
    frame model's own pitch RS03 envelope and bracket against our pitch RS03.
  - The frozen upper arm's own ring and keys overlap by 1.6 mm³ (not a shoulder part).

**Running clearances** (`check_clearance.py`; samples 0.7 mm, ±0.4 mm):

- **Coverage:**
  - the 36 brief poses
  - roll -11…+110 in 3 deg steps at yaw -90/0/+90
  - pitch -90…+180 at roll -11/0/+110
  - yaw -90…+90
- **Against:** the rev A frame (moved -38 X; shell parts excluded) and the pitch RS03.
- **Result:** on the organic final parts, every moving pair is **2.0 mm or more**. The only contacts are the intended
  stop contacts:

| Pair | Min (mm) | Pose (pitch, roll, yaw) |
|---|---|---|
| Fork rear arm ↔ stop lug | 0.02 | roll -11 and +110 (intended) |
| Flange ring ↔ cover | 2.00 | any (designed axial gap) |
| Fork rear ↔ hub | 2.16 | roll -11, yaw 78 |
| Fork front (cuff) ↔ hub | 2.17 | roll 110, yaw -12 (the yaw gap under the cuff) |
| Flange ring ↔ fork front | 2.40 | roll -12 (1 deg past the stop) |
| Drum ↔ cover | 2.41 | pitch 150 |
| Cap ↔ fork rear | 2.50 | any |
| Drum ↔ RS02 | 2.54 | roll 97 |
| Drum ↔ fork front (dome) | 3.00 | |
| Drum ↔ rev A frame | 3.50 | pitch -30 |

- Round 1's neck flare sat where the fork front's socket-tap sector and the RS02 swing in at the inward stop (0.04 mm).
  It was caught by this sweep, and the flare is now trimmed below Y = RY - 41.

**Stops:**

| Roll | Arm to lug |
|---|---|
| -10 | 0.72 |
| -11 | 0.04-0.06 |
| 110 | 0.02 |

At both stops everything else is 2.0 mm or more away.

## No-protrusions round (Joey, 2026-11-11: nothing may stand proud of the skin)

What changed against the organic round:

- **Cable:** no trunk, branch, spine or ridge stands on the drum.
  - The trunk runs along X at Y 470 inside a hollow egg-section **bell** round the pitch axis. The bell replaces the neck
    tube and flare: top r 60 over the trunk, bottom r 41 (clear of the fork and RS02 swing), Z +34 / -27, 2.5 mm wall.
  - It turns down at roll angle 135 deg (r 58, its width along the skin) and enters the cap.
  - The branch to the RS03 top bay runs inside the drum wall.
- **Drum outline:** a loft whose sections are the crown circle swelled (convex hull) over the down-run and the branch only.
  - The swell is +8.8 mm (r 65.8) in the 120-150 deg sector, fading to the plain crown by Z 10 (`envelope.py`).
  - It is hollowed from the rear under the cap.
  - The flange ring's hole moved to the new trunk height; its spokes turned to 108 deg to stay clear.
- **Cap:** no ears. Its outline continues the drum's rear section. It is held by 3 x M3 thread-forming screws axially inside
  the outline (r 50 at 0 / 180 / 270 deg), with heads in pockets on the flat rear face.
- **Stops inside the outline:**
  - A tooth on the fork rear cheek (r 27-33, 20 deg wide) runs in an arc slot (r 25-35) in a ring on the inside of the
    cap's rear face, with 2 mm all round.
  - The tooth meets the slot ends at -11 and +110 deg. The contact face is 8 x 8 mm (about 64 mm²) at r 25-33.
  - The slot's start plane and sweep are driven by `ROLL_STOP_IN` / `ROLL_STOP_OUT` (start 172 deg, sweep 141 deg).
  - The ring covers only the slot sector, plus 15 deg each end.
- **Fork rear arm and joint:**
  - The cuff is now an egg-section loft that swells back to the fork rear arm (0.5 mm static gap), so they read as one
    sleeve. It is hollow to 2 mm and open at the bottom.
  - The joint lugs are narrowed from X ±30 to ±21.5, a rounded flare of the arm, with screws in pockets from the back.
- **Not yet clean:**
  - a soft crease where the bell surface comes out of the swell (the SolidWorks blend fillet does not build there)
  - the fork rear arm, which still reads as a rounded bar from straight behind
  - the bottom feed, which sits inside the shell.

**Masses (solid PETG):**

| Part | g |
|---|---|
| Drum | 224.1 |
| Flange ring | 29.3 |
| Cap | 84.5 |
| Fork front | 131.3 |
| Fork rear | 59.9 |
| Fork cap | 5.5 |
| Hub (rev B with groove) | 69.3 |
| **Total** | **603.9** |
| Cover (torso side) | 102.3 |

**Final clearance sweep** (these parts with hub rev B):

- Every moving pair is **2.0 mm or more**. The only contact is the tooth on the slot ends (0.05 mm at +110 and -11).
- Tightest pairs:

| Pair | Min (mm) |
|---|---|
| Ring ↔ cover | 2.00 (designed) |
| Cuff ↔ hub | 2.04 (roll -11, yaw 30) |
| Fork rear ↔ hub | 2.16 |
| Ring ↔ fork front | 2.46 |
| Drum ↔ RS02 | 2.60 |
| Drum ↔ frame | 3.50 |

- Static booleans between the parts and the motors are clean.
- **Pictures:** D1-D6 as before, plus [D7_top_down.png](D7_top_down.png) and
  [D8_drum_top_view.png](D8_drum_top_view.png) (the review screenshot's camera).

### Back view (2026-11-11, after review of D3)

- **Fork rear arm:** the flat rounded bar is replaced by one loft of D sections.
  - The front is flat on the joint plane (Z -45.9), so the bolted joint keeps full face contact.
  - The back is a soft superellipse, depth 10.3-13.
  - It grows out of the rear cheek, flares to ±23 over the joint, narrows into the cable duct and closes at Y 314.
  - The joint screws sit in pockets from the back.
- **The foot:** the cuff's egg loft now runs up to the seat-ring top (Y 361.9). The fork front's joint pad and the socket-tap
  sector sit inside it, so no foot or boss shows beside the cuff.
- **The crease where the bell meets the drum swell is still there.** The blend fillet does not build in SolidWorks. A
  cross-loft or boundary surface across the two lofts was not tried in this round.
- **Masses:** fork rear 64.2 g (+4.3), fork front 134.2 g (+2.9). Shoulder total **611.1 g**.
- **Clearance sweep on these parts:** every moving pair is 2.0 mm or more; the tooth on the slot ends is the only contact
  (0.01 mm). The tightest five:

  | Pair | Min (mm) |
  |---|---|
  | Ring ↔ cover | 2.00 (designed) |
  | Cuff ↔ hub | 2.05 |
  | Fork rear ↔ hub | 2.17 |
  | Drum ↔ RS02 | 2.60 |
  | Ring ↔ fork front | 2.62 |

- **Pictures:** [D9_back_straight.png](D9_back_straight.png) (straight from behind) and
  [D10_back_below.png](D10_back_below.png) (behind and below, three-quarter).
- **Still not clean from behind:**
  - the cuff's top rim edge
  - the flat bottom end of the arm's duct
  - the yaw-exit duct under the cuff (seen from below)

### Sleeve round (2026-11-11, review of D9/D10)

What changed:

- **One sleeve.** The cuff (fork front) and the lower part of the fork rear arm now share one outline about the yaw axis
  (`envelope.SLEEVE`), split only at the joint plane: fork front Z ≥ JZ0 + 0.5, fork rear Z ≤ JZ0.
  - The front is round, r 42.9-43.8, with no flare at the top.
  - The back has one swell, out to r 63.5, that carries the 16 x 6 passage and its 2.4 mm wall inside the outline.
  - At the socket tap (Y 353-359) the swell reaches round to the inboard side, holding about 2.5 mm of skin over the tap
    arc. Lower down it is held tight to the duct behind the axis, and its inboard reach is capped (`x_in`).
  - The arm's duct no longer runs down the outside of the cuff, and no flat cut end remains. Above the cuff the arm
    tapers out of the sleeve into the D-section arm.
  - The joint screws keep their pockets; the pocket floor is 5.5 mm behind the joint plane.
- **The yaw exit** is inside the outline: a skirt runs down to Y 314.5 (bore r 41.5, 2.2 mm off the hub) over the cable
  turn, with a soft bottom edge. The cable path is unchanged: the passage still ends at r 41.5, Y 316.55-322.55.
- **The cuff top** is rounded (4 mm) at the front and sides, and the rounding fades out only where the arm rises out of
  the sleeve, so there is no ledge either side of the arm. The seat ring's outer material is now the sleeve itself.
- **The drum's oval slot** is the driver access to the 6 pitch-pad screws, so it stays. It gets a flush press-in cap
  (`shoulder_roll_drum_port_cap_left`, 2.0 g): the outer face is the drum skin sampled along the slot edges, 13.9 wide in
  the 14 slot, with a 0.8 mm hook at each end that snaps under the skin into the pocket.
- **The bell-to-drum "crease"** was the bell's flat end face at X 134, standing 3 mm out of the drum (bell top 60
  against drum r 57). The bell now runs to X 141 with its top tapered from 60 (X 127) to 56, so it dives under the drum
  skin. One clean intersection is left, and a 6 mm blend builds on it (`BELL_BLEND`). The multi-edge blend on the old
  end face never built.

Masses:

| Part | g |
|---|---|
| Drum | 230.8 |
| Flange ring | 29.3 |
| Cap | 84.5 |
| Fork front | 143.4 |
| Fork rear | 60.0 |
| Fork cap | 5.5 |
| Drum port cap | 2.0 |
| Hub (rev C) | 72.5 |
| **Total** | **628.0** |

Against the back-view round: fork front +9.2, fork rear -4.2, drum +6.7 (the bell run-on), port cap +2.0.

Clearances, moving pairs over the sweep (`check_clearance.py`). The stop tooth on the slot ends (0.05) is the intended
contact. The tightest five inside -11…+110:

| Pair | Min (mm) |
|---|---|
| Ring ↔ cover | 2.00 (designed) |
| Cuff ↔ hub | 2.13 (roll -11, yaw -66) |
| Ring ↔ fork front | 2.20 (roll -11; 1.15 at -12, past the stop) |
| Drum ↔ RS02 | 2.60 |
| Port cap ↔ RS02 | 2.61 |

The first sleeve version broke two rules, and both are fixed in the parts above:

- The inboard swell came within 0.93 mm of the flange ring at the stop. Capping the inboard reach brought it to 2.20.
- The skirt touched the shell skin at roll -9 to -10. Narrowing the low swell and raising the skirt to Y 314.5 fixed it.

Rev A sweep on the option-a parts (`check_reva.py`, capped at 6 GB, peak 1.5 GB), all four pitches:
- **Frame, gusset allowance and pitch wing:** no contact inside -11…+110; 25.5 mm at the stop.
- **Shell skin, r 80 opening, at the -11 stop:** 2.29 mm (pitch -30), 3.7 or more (0), 3.02 (+24), 7.8 (+90). The first
  skin contact is at -13, or -24 at pitch +90.
- The collar and spine-pad touches are as before; they're on the shell option A change list.

Rev A frame, gussets and shell option A, on these parts (`check_reva.py`):

- **Frame, gusset allowance and pitch wing:** no contact inside -11…+110. At the stop the nearest frame point is
  25.5 mm away. The first frame contact is at roll -20/-21 (upper arm on hardpoint H5).
- **Shell skin, r 80 opening:** at the stop the fork front clears it by 2.24 mm (pitch -30), 3.7 mm (pitch 0) and
  2.98 mm (pitch +24). The first skin contact is at -13. The pitch +90 run was still going at commit time; in every
  earlier run it had no contact.
- The shell collar with its screws, and the upper and lower spine pads, are touched as before. They are already on the
  shell option A change list.

**Frame decision** (Joey, 18:07Z: "nope frame is fine as is if that works"): rev A is built as drawn and the inward stop
stays at -11 deg. Pictures: [frame-options/F1_frame_as_drawn_stop_m11.png](frame-options/F1_frame_as_drawn_stop_m11.png),
[frame-options/F2_frame_first_contact_m21.png](frame-options/F2_frame_first_contact_m21.png).

Still not clean:

- The seam at the joint plane shows as a line down the sleeve's back sides (a part split, like the arm's seams).
- The pitch cover's bottom feed is still an L-shaped duct (inside the torso shell, behind the skin).

### Look option a (Joey, 2026-11-11 20:01Z: "shape only")

[look-options/OPTIONS.md](look-options/OPTIONS.md) has the variants. On the real parts:

- **Drum as a bobbin**, copying the forearm cheeks: rims r 57 at Z -22 and +27.5, middle r 56.1. That's a 0.9 mm relief,
  milder than the mock-up's 1.5. The middle can't go lower: the RS03 lug slots and the top connector window inside
  reach r 54.5, and 56.1 keeps 1.6 mm of skin over them.
  - The window's top corners are clipped to r 54.5.
  - The pockets stay at r 54.
  - The bell's top taper ends at 55.8 (X 141), so it still dives under the drum skin.
- **Cuff waist**, copying the upper-arm neck: r 42.1 at Y 330, against 43.0-43.6 at the ends. It stays clear of the
  socket pockets (r 40.5 from Y 340.9). The hollowing loft now has a station every 4 mm, so it follows the waist with no
  bulge.
- **Fork cap dropped**, copying the forearm caps: the 6 front screws show in the recessed disc (r 24, 8 deep). Driver
  access is straight along +Z from the front; nothing stands in front of the fork front.
  `shoulder_fork_cap_left.SLDPRT` is removed.
- **Sleeve back fixed in this round:** the 16 x 6 power channel is centred on RZ (Z -54.3..-48.3), 3 mm deeper than the
  sleeve round's cover check assumed, so the skin over its inboard corner was only 1.0 mm.
  - The back now goes to r 66.5 (67.0 from Y 354, where the signal channel joins), giving 2.4 mm walls plus about
    0.5-0.9 mm of margin.
  - The rear hollow stops 1.6 mm short of the joint plane, which leaves a front plate instead of a feather edge on the
    joint face.
- **Port cap:** rebuilt on the new skin, same slot and hooks.

Thinnest walls, measured on sections and inward rays:

- **Drum skin:** 1.6 mm over the lug slots and window. The one exception is 0.97 mm where the bell dives into the drum
  over trunk A. That spot dates from the crease fix and option a didn't change it; it's still open.
- **Cuff:** 1.48 mm at the bore step at Y 320.4, otherwise 1.6 or more.
- **Fork rear:** the 1.6 mm front plate; skins 2.0 or more.
- **Port cap:** 1.9 mm.
- The RS02 counterbores at the seat leave 1.2 mm to the seat bore. That's vendor-interface geometry and unchanged.

Masses:

| Part | g |
|---|---|
| Drum | 226.5 |
| Flange ring | 29.3 |
| Cap | 84.5 |
| Fork front | 144.6 |
| Fork rear | 70.4 |
| Drum port cap | 1.4 |
| Hub (rev C+, fill to r 23) | 77.1 |
| **Total** | **633.8** |

Fork cap dropped (-5.5 g). Against a71b446: drum -4.3, fork front +1.2, fork rear +10.4 (the deeper back that really
covers the channel, plus the front plate), hub +4.6 (rev C+ wall fill, to r 23).

Clearances, moving pairs (`check_clearance.py`, capped at 6 GB). The stop tooth (0.05) is the intended contact. The
tightest five inside -11…+110:

| Pair | Min (mm) |
|---|---|
| Ring ↔ cover | 2.00 (designed) |
| Ring ↔ fork front | 2.12 (roll -11; 1.15 at -12, past the stop) |
| Cuff ↔ hub | 2.13 |
| Drum ↔ RS02 | 2.60 |
| Port cap ↔ RS02 | 2.61 |

## Rev A frame and shell: inward roll from 0 to -25 deg

`check_reva.py`: roll in 1 deg steps, yaw -90…+90 in 15 deg steps. Contact means under 0.5 mm.

| Pitch | Frame (and the 6 mm PETG gusset allowance) | Shell skin (opening region ignored) |
|---|---|---|
| -30 | roll -21: upper arm on hardpoint H5 | roll -14: hub, yaw 15 |
| 0 | none to -25 | roll -13: upper arm, yaw -60 |
| +24 | roll -20: upper arm on hardpoint H5, yaw -75 | roll -15: hub, yaw -75 |
| +90 | none to -25 | none to -25 with the r 80 opening |

- **Frame:**
  - no contact with the frame, the PETG gusset allowance (Z ±76) or the pitch wing inside -11…+110
  - at roll -11 the nearest frame point is 25.5 mm away (top side rail)
- **Shell skin:** at roll -11 it is 3.5 mm or more from every moving part outside the opening (`check_shell_trim.py`). No
  trim is needed for the -11 stop. The skin limits inward roll at -13…-15, so rev A allows more than -11 only with a
  reshaped skin there.
- **Lower spine pad** (`shellpart__spine_lower_1`, rev A X 73-129, Y 166-295, Z -124 to -77):
  - The upper arm reaches it at pitch -30 from roll -8, and is **0.01 mm** from it at -11 (yaw -45).
  - **Minimum trim for 3 mm at the -11 stop:** up to 2.99 mm off the pad's outboard end, over rev A X 119.4-129,
    Y 202-276. That means the pad ending at about X 126, with its outboard edge eased by 3 mm.
  - Picture: [C1_spine_pad_contact.png](C1_spine_pad_contact.png).
- **Shell skin contact:** first at pitch 0, roll -13, yaw -60, past the stop. Picture:
  [C2_shell_skin_contact.png](C2_shell_skin_contact.png).

**Shell changes for option A**, for the body shell work:

1. Shoulder opening enlarged to **r 80** round the pitch axis. The fixed cover ring is r 75.9; the moving flange ring is
   r 77.5 and sits outboard of the skin.
2. The shell collar (r 60 at X 135-137) and its **8 screws** at r about 45 are removed. They overlap the cover and sit where
   the drum's spokes turn.
3. The **upper spine pad** ends inboard of rev A **X 140**. It overlaps the moving flange ring by about 0.5 mm, and is
   1.1 mm from the cover.
4. The **lower spine pad** is trimmed as above (end at about X 126) for 3 mm at the -11 stop.

## Hub: prepared for the arm joint work (nothing active)

The frozen interface is unchanged: spigot r 35.8 at Y 296-302, lugs, seam bolts, hub screws, cable window at 7.9 deg.
Two suppressed features are driven by global variables in `shoulder_hub_left`:

- **`SPIGOT_EXT`:** a ring r 28-35.8 below Y 296.
  - `SPIGOT_EXT_LEN` sets the length (6 mm placeholder).
  - The draft angle is in the feature: `SPIGOT_TAPER` is not linked yet.
  - `SPIGOT_EXT_ON` = 1 turns it on.
- **`LUG2`:** a second lug pair r 19-30, ±15 deg, Y 288-296.
  - Its plane through the yaw axis is set by `LUG2_ANGLE` (90 = at 90 deg to the seam).
  - `LUG2_ON` = 1 turns it on.
  - No bolt holes until the arm thread gives positions.

**Where a second lug pair fits:**

- The existing lugs sit at yaw angles 0 and 180 deg (on the seam), r 19-30, Y 288-295.
- At ±90 deg (front and back, mid-half) the arm halves have only their wall there (r 33-40). The same r 19-30 sector is free
  over Y 288-296, so a pair at 90 deg fits.
- It is clear of the cable window (7.9 deg, above Y 298) and of the yaw cable loop (above Y 315.8).
- The arm halves would need matching bosses on their inner walls at ±90 deg.
- **Not checked yet:** 23 N·m bending plus yaw torque.

## What changed against the mock-up

1. **Inward stop -11 deg** (was -15).
2. **Pitch flange is its own flat part.** It sits at X 104.5-106.3 on five drum spokes.
3. **Cap ears at 125 / 148 / 212 deg.** The ears at 165 and 200 deg hit the flange ring.
4. **RS02 socket pockets 4 deg wider** each side.
5. **Relief in the drum wall** for an RS03 housing boss at r 50.25. It overlapped the vendor solid by 200 mm³; the concept
   never checked that fit.
6. **Pitch loop cover: bottom feed and M5 pads** for the rev A frame:
   - The duct rises in the void under the step overhang (rev A X 101.6-112.4, Y 300-343).
   - It enters the cover bottom at about Y 349, Z -16.4 to +16.4 (power Z -14 to +2, signal Z +4 to +14).
   - The pads sit at the posts (Y 425, Z ±60), the step side rail (Y 363.6) and the top side rail (Y 485).
7. **Dressing for the look of the arm** (rounds 1 and 2):
   - Closed drum skin with the lightening under it, and one styled oval port for the pitch pad screws.
   - The neck flares into the drum.
   - Full dome cap r 55 on the fork front, running 3 mm in front of the drum lip. It covers the 8 lip screws: take the fork
     front off (6 screws under the press-in cap) before reaching them, as in the service order.
   - A cuff round the RS02, tapering to r 41.7, 2 mm above the hub rim, notched round the yaw exit.
   - A spine fairing over the trunk.
   - The rear cap and fork rear cheek with R6 edges.
   - The rear web from the cuff to the fork rear arm.

## Organic round (Joey: "organic", not excessive; stop being jarring next to the arm)

- **Drum:** the skin is a loft through crowned circles. It is r 54.5 at both ends and r 57 over the middle; r 57 is the most
  the RS02 swing allows (2.54 mm). The pockets under it follow the crown.
- **Rear cap:** its rim continues the drum's r 54.5 end.
- **Fork front:** its face crowns forward to Z 49 (an elliptical loft, 9 mm in, 7 mm forward). The press-in cap sits 1.5 mm
  below the crown rim, as the arm's caps sit in their recess.
- **Cuff:** a gentle convex swell, 2 mm above the hub rim.
- **Spine:** a low lofted spine covers trunk B and the branch, and its nose eases into the drum crown.
- **Rounded details:** the trunk on the neck has R5 edges, the fork-rear joint lugs R4.5 corners, the stop lugs R3.7.
- **Remaining box shapes:**
  - the trunk mouth on the neck top (rounded)
  - the fork rear arm seen from behind (rounded edges)
  - the cover's bottom feed, which sits inside the shell.

## Still open

- **Cover fixing:** the M5 pads are placeholders; the T-nut positions on the rev A rails are not checked.
- **Feed position:** waits for the final shell.
- **Printing:**
  - The fork front with the cuff prints as installed, with removable support under the RS02 seat ledge (open from below,
    no enclosed cavity). The seat face is then a supported face, so it needs checking.
  - The drum pockets open into the bore through the inner-wall windows (no enclosed cavity).
- **Bearing fits:** 6808 on the Ø40.0 printed stub, in the Ø52 printed housing, and inner-race retention.
- **Not analysed (no FEA in this pass):** stop-lug strength and impact; hub step ring and hub-to-arm joint (23 N·m bending
  plus yaw torque).
- **Deflection and stack-up:** all clearances are nominal CAD.
- **Plug bodies and cable flex life:** not checked.
- **Right shoulder:** a mirror, later.

## Method notes

- **Python environment:** a separate venv, `C:\joe\code\_venvs\shoulder` (cadquery 2.8, vtk, trimesh, shapely, pywin32).
  A package update by another job broke cadquery in the PC's shared Python.
- **SolidWorks:** one session-owned instance through `sw_instance.session()`. The shared import options were changed only
  for each import and restored right after.
- **Pitch RS03 reference:** in `TORSO.step` it is open shells. `sew_solid.py` sews it into 19 solids.

## Pictures

| File | What |
|---|---|
| [D1_look_shell_optionA.png](D1_look_shell_optionA.png) | Dressed, with the shell (option A), same camera as the option renders |
| [D2_front_clean.png](D2_front_clean.png) | Dressed, front-outboard, no frame or shell |
| [D3_back_clean.png](D3_back_clean.png) | Dressed, back |
| [D4_bare_vs_dressed.png](D4_bare_vs_dressed.png) | Bare first pass against dressed, front and back |
| [D5_whole_arm.png](D5_whole_arm.png) | With the whole organic arm (upper arm, elbow, forearm) |
| [D6_shoulder_vs_arm_render.png](D6_shoulder_vs_arm_render.png) | Beside the arm's own render |
| [C1_spine_pad_contact.png](C1_spine_pad_contact.png), [C2_shell_skin_contact.png](C2_shell_skin_contact.png) | The two shell contacts |
| [P1_look_front_outboard.png](P1_look_front_outboard.png) - [P5_today_vs_pass1.png](P5_today_vs_pass1.png) | Look, back, exploded, roll-axis section with bearing and cable path, today against the first pass |

## Hub rev C+ exports for the arm side (from fd0cef8)

The hub as committed at fd0cef8 (rev C+, wall fill to r 23). The working copy is byte-identical to that revision
(SHA256 below matches the LFS object). Both exports are recorded in `cad/manifests/exports.json`.

| File | Settings | SHA256 |
|---|---|---|
| `cad/shoulder/left/shoulder_hub_left.SLDPRT` (source) | | `625c70d823630b4958f0a7fc9dec6373f982ffeb452d0842ecad83bf25d53047` |
| `cad/exports/shoulder/shoulder_hub_left.STL` | binary, mm, model coordinates kept; deviation 0.01 mm, angle 5°; 41,700 facets, watertight | `523eb9946660f90e92bf84c16c820bc1c9c4296ebbe1852d6a1f80397356d176` |
| `cad/exports/shoulder/shoulder_hub_left.STEP` | SolidWorks default (AP214), mm | `39f002b915ce916eb8ff256c39f99f4f1015a02a0972ccfe14087cd88802f690` |

- The seam-bolt (lug) holes in the hub are Ø3.4 (r 1.7), for M3 bolts (r 1.5).
- Bounds (mm, model frame): X 131.19-209.79, Y 288.00-319.86, Z -33.31-45.29.

## Front blend 3: the true wrap, adopted (2026-11-12)

- Joey chose variant 3 (02:54Z: *"that looks much better"*). The fork front is now one loft from the cuff's front half
  into the cheek (`FRONT_BLEND = '3'` in `dims.py`; `FRONT_BLEND=0` builds the old cheek).
- Details, clearances and the section modulus: [look-options/front_blend/README.md](look-options/front_blend/README.md).
- **New part:** `shoulder_fork_access_plugs_left`, two press-in plugs for the RS02 access bores, 0.7 g.
- **Masses:**
  - fork front 150.5 g (+5.9 against 144.6), plugs 0.7 g
  - shoulder total **640.4 g**
- **Clearances:**
  - drum ↔ fork front 2.0, the designed envelope (was 3.0)
  - ring ↔ fork front 2.13 at -11
  - cuff ↔ hub 2.11
  - port cap ↔ fork front 2.63
- **Shell and frame:** the shell at the -11 stop clears by 2.27 at pitch -30 (was 2.29). The rest of the rev A sweep was
  still running when this was written; see the next update.
- **Pictures:** D1-D3 and D5-D10 re-rendered with the wrap and the plugs. D4 is the first-pass comparison and is left as it
  was.
- **STL export:** custom 0.01 mm / 3° (`swk.export`). The 'fine' preset left sliver triangles that the pictures' 40°
  feature-edge pass drew as false lines.

## Side centre r 47, adopted (2026-11-12)

Joey (05:33Z) gave the go on the r 47 sleeve ([look-options/side_centre/README.md](look-options/side_centre/README.md)). It
is now on the real fork front and fork rear (`dims.SIDE_CENTRE = '47'`; `SIDE_CENTRE=0` builds the earlier sleeve).
Pictures of the real parts: [look-options/side_centre/real/](look-options/side_centre/real/).

**What changed:**
- **Fork front:** below Y 340 the sleeve is one closed lofted ring round the RS02, with a 2 mm skin, hollow, and open at
  the bottom.
- **Fork rear:** starts on the ring's flat top at Y 340, which is its first print layer. That leaves a horizontal shut
  line across the back at Y 340.
- **Back profile:** curves in from r 66.5 (Y 352) to r 48.4 at the bottom edge. The bottom 3.5 mm leans at most 40°
  from vertical, so it prints without support.
- **Fore-aft centre:** the sleeve's centre is now 2.3 mm behind the yaw axis at the bottom edge (was 11.4). The back step
  to the arm's top band is about 9 mm (was 27).
- **Power channel:** the 16 × 6 channel bends into the yaw exit on a 24 mm radius through the ring's back cavity. The
  10 × 5 signal channel joins it above Y 357.
- **Fork joint, now six M4:**
  - X ±17 and ±27 at Y 356.9
  - X ±22 at Y 345.5, the lower pair, which the fork rear now reaches
  - Heads recessed in counterbores.
  - Seen from behind: **six holes**, four in a row at Y 356.9 and two lower at Y 345.5 just above the shut line.
  - The fork front's joint pad runs down to Y 341.5. Insert bosses for the lower pair sit inside its hollow.

**Masses (g):**

| Part | g |
|---|---|
| Drum | 226.5 |
| Flange ring | 29.3 |
| Cap (stop rev 2, 6808 land) | 85.2 |
| Fork front (wrap, ring, six inserts) | 154.6 |
| Fork rear (from Y 340, tooth, 6808 seat) | 63.7 |
| Drum port cap | 1.4 |
| Hub (rev C+) | 77.1 |
| Access plugs | 0.7 |
| **Total** | **638.5** |

**Clearances** (`check_clearance.py`, roll -11…+110, all yaw; `clearance_r47.json`):
- **The stop tooth on the slot ends:** 0.05 at -11 and +110. This is the intended contact; elsewhere 2.0.
- **Ring ↔ fork front:** 2.12 at -11 (1.05 at -12, past the stop).
- **Drum ↔ fork front:** 1.99 (the 2 mm envelope, sampled).
- **Ring ↔ cover:** 2.00 (designed).
- **Cuff ↔ hub:** 2.20.
- **Drum ↔ RS02:** 2.60.
- **Port cap ↔ fork front:** 2.62.
- Every other pair 3.0 or more.

**Print (upright, Y up):**
- Both parts are a single shell: no enclosed cavity.
- The ring's bore needs no support. Its only overhang is the 1.75 mm ledge where the r 41.5 skirt steps to the r 39.75
  bore.
- Supports, all open from below and removable:
  - fork front: the sleeve hollow's roof (Y 340-350), the RS02-cap clearance roof (Y 361-367), and the dome pocket ceilings
  - fork rear: its hollow's roof (Y 340-349), and under the stop tooth's outer face

**Assembly order:**
1. Lay the 16 × 6 and 10 × 5 bundles in the ring's back cavity, separately (24 mm bend).
2. Slide the RS02 in bare from below. The vendor body is r 39.30 at most against the r 39.75 bore, so 0.45-0.50 mm
   radial clearance.
3. Connect the plugs.
4. Fit the fork rear.

**RS02 plugs: they do not fit as modelled. This predates r 47.**
- The RS02 uses one combined power and CAN connector: AMASS XT30PB(2+2)-M on the board, XT30(2+2)-F on the lead (RS02
  manual 260713 §2.3). There are two sockets (in and out) at X ±31…36, r 32.6-36.2, Z -4…16, tops at Y 360.1.
- **The way out is blocked:**
  - Above each socket, the seat ring's top 1 mm (Y 360.9-361.9) roofs the socket pocket: 51% of the plug's column is
    blocked at Y 361.5.
  - The fb3 wrap edge and the cuff top fill 25% → 7% of it from Y 362.5 to 367.5.
  - Above that it is clear to the drum's 2 mm envelope at about Y 375-378.
  - Sideways, the cuff wall (r 41-45) closes the pocket.
- **To fix:**
  - open each pocket upward through the seat ring's top and the wrap edge, about 16 × 9 mm at X ±30…38, up to Y 368
  - check the plug body's length and lead bend against the 15-18 mm to the drum envelope
  - this needs the real plug's dimensions: measure an XT30(2+2)-F with its leads
- The opening shows as a notch in the cuff top at each side. It is not done yet.

**r 47 checks, completed:**
- **Shell and frame** (`check_reva.py`): the fork front clears the r 80 shell opening at the -11 stop by 2.21 / 3.75 / 2.96
  (pitch -30 / 0 / +24; was 2.27 / 3.79 / 3.03). At pitch -30 first contact is now at roll -12, 1° past the stop (was
  -13). Frame, gussets and wing are unchanged: 25.5 to the drum at -11, and first contacts are the arm on hardpoint H5
  at -20/-21 as before.
- **Stop torque path:** rated layer SF ≥ 1.64 everywhere (see checks/B_ROLL_STOPS.md).

**RS02 plug: decided (coordinator, 2026-11-12)**
- One socket per motor, robot-wide (Joey's rule). The 173° socket takes the plug. The -7° socket stays capped.
- The plug pocket was to be option (a), a hidden column ([look-options/plug_pocket/README.md](look-options/plug_pocket/README.md)).
  **Its check failed:** the power lead's bend needs 5.2-6.6 mm above the plug, and there are 3.7 mm under the drum at
  the worst-credible plug height. Not on the real part. It stands or falls on Joey's measurement; the fallback is a
  right-angle adapter board.
- It is sized for the worst credible plug: about 15 mm above the socket's top. Joey's measurement of a real XT30(2+2)-F
  confirms it or reopens it.
- **Assembly step:** with the fork front on the bench and the RS02 in, feed the lead down the column into the tap. Then
  push the plug straight down onto the socket with long-nose pliers or a push-stick; the opening is 16.5 × 10 mm.
  Unplug with the same pliers, pulling straight up.



## RS02 power/CAN plug: radial (2026-11-13)

The RS02's two XT30PB(2+2) sockets face sideways: r 36.17, Y 354.9-360.1, at 188° (in use) and 8°. The plug mates radially. The
vendor model and our reference are right; the plug-pocket study's earlier "plug mates down onto the rear face" was a misreading.
Rework in [look-options/plug_pocket](look-options/plug_pocket/README.md): at today's clocking only a lead folded to 7 mm fits (1-2 mm wall left);
with the RS02 re-clocked +40° the 10 mm envelope fits inside the outline, over the middle of the socket tap. Mock-up next; real parts unchanged.

## RS02 re-clocked +40°: plug pocket pp_r on the real parts (2026-11-13, Joey "go")

**What changed:**
- **RS02 clock:** `build_asm.T_RS02` 98 → 138° (`dims.RS02_RECLOCK`, default on; `RS02_RECLOCK=0` builds the old clock).
  - **Socket in use:** the one at **228°**, over the middle of the socket tap.
  - **Spare socket:** at 48°, left capped.
- **RS02 zero:** a **+40° software offset** in the yaw joint's zero.
- **Fork front, five RS02 M3 screws:** at -96 / -56 / -16 / 104 / 144°.
  - The RS02's seat face has M3 holes at six positions on PCD 73: -176 / -96 / -56 / -16 / 104 / 144° after the re-clock.
  - The other three 40° positions carry the socket bosses.
- **Socket pockets:** 202-238° and 14-74°.
- **Access bores and plugs:** at 104 / 144°, where they were at 64 / 104°. The 144° screw sits under the cheek too.
- **PLUG_CHANNEL at 228°:** r 36-50, 16.5 wide, Y 353.9-361.1. It holds the XT30(2+2)-F and its folded lead (envelope r 36.17-49.25).
  - It opens only into the socket pocket and the tap.
  - **Its back corner is clipped at Z - YZ -39.4,** 1.5 mm off the blind end of the fork joint's insert bore (Ø5.6, X - RX -27, Y 356.9).
  - **Wall left outside the envelope:** 11.6 mm minimum.
- **Skeleton:** the seat sketch follows.

**Masses:**
- Fork front 155.2 g, against 154.3 g before (the 144° bore removes less than the 64° one).
- Access plugs 0.7 g.

**Mesh:**
- **The fork front STL carried 2 needle triangles,** collinear T-junction slivers at (213.3, 358.6, 5.8) and (172.5, 361.9, 49.7).
  - They come from tiny B-rep faces that predate pp_r: the pre-pp_r export has the same two.
- **Fix:** `tools/cad/mesh_fix_needles.py` splits each needle's neighbour and drops the needle.
  - The mesh is unchanged: mesh_diff 0.0000 mm both ways.
  - `finish_part` now runs it whenever only zero-area faces fail.
- **All exports pass integrity.**

**Clearance sweep:**
- **Method:** `check_clearance.py`, full, 36 brief poses, 492 sweeps.
- **RS02 pairs, all unchanged or better:**

  | Pair | Clearance |
  |---|---|
  | Drum ↔ RS02 | 2.60 |
  | Port cap ↔ RS02 | 3.09 |
  | Hub ↔ RS02 | 3.42 |
  | Cap ↔ RS02 | 5.58 |
  | Ring ↔ RS02 | 7.68 |
  | Cover ↔ RS02 | 11.81 |
  | RS02 ↔ arm | 21.86 |
  | RS02 ↔ torso | 26.28 |

- **Fork front:**

  | Pair | Clearance |
  |---|---|
  | Ring | 1.04 |
  | Drum | 1.99 |
  | Hub | 2.19 |
  | Port cap | 2.62 |
  | Roll RS03 | 4.51 |
  | Arm | 12.77 |
  | Torso | 15.73 |

- **Same-code before/after** (the full sweep re-run on the pre-pp_r fork front and plugs with `RS02_RECLOCK=0`;
  `_wip/.../clearance_pre_pp_r_same.json`): every pair is within 0.05 mm, except:

  | Pair | Before | After |
  |---|---|---|
  | Cap ↔ RS02 | 5.52 | 5.58 |
  | Ring ↔ RS02 | 7.73 | 7.68 |
  | RS02 ↔ torso | 25.97 | 26.28 |

  The fork front's pairs are identical.
- **The drum ↔ fork front 1.98-1.99 is the designed 2 mm drum-envelope cut,** read through the ±0.4 mm sampling.
  - It is identical on the pre-pp_r fork front at every roll angle and at the same spots (Y 367-372, Z +27), so pp_r did not change it.

**Driver reach** (rays straight up from each screw seat, the assembled shoulder at the neutral pose):
- **On the bench** (fork front alone): all five screws are reachable. 104° and 144° go through their access bores.
- **Assembled:** only 104° is reachable. The drum or cap blocks the other four, 144° at Y 374.8.
- **This matches the old layout,** whose rear screws (-136 / -96 / -56) were also blocked by the drum or cap. So the assembly order is unchanged: the RS02 goes onto the fork front before the fork front goes onto the drum.

**Exports** (recorded):
- `cad/exports/shoulder/shoulder_fork_front_left.STEP/.STL`
- `cad/exports/shoulder/shoulder_fork_access_plugs_left.STEP/.STL`

**Pictures:**
- [real_set_pp_r/SHEET_real_pp_r.png](real_set_pp_r/SHEET_real_pp_r.png): the outside is unchanged.
- Mock-up comparison and sections: [look-options/plug_pocket/radial](look-options/plug_pocket/radial/).
