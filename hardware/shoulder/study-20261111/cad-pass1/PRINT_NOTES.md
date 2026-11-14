# Left shoulder print package (updated 2026-11-14)

Collected from the checks. Each item names where it comes from. **Only the hub has a sliced print file** (its section
below). For the other parts, orientations and supports are judged from the geometry and a first-look slice, and each
still needs its pre-print gate
([part-lifecycle.md](../../../../conventions/part-lifecycle.md)).

## What can print now, and what waits

| Part | File | Mass (PETG) | Geometry last changed | Status |
|---|---|---|---|---|
| Cable test rigs: roll, yaw, pitch (PLA) | `cad/exports/fixtures/fixtures_cable_rig_*.STL`; sliced plates in `C:\joe\prints\cable-rigs\` and `J:\code\prints\cable-rigs\` | 35 g / 45 g / 42 g | 2026-11-13 | **Print now, roll first.** They decide the three cable crossings ([CABLE_RIGS.md](../checks/CABLE_RIGS.md)) |
| 6808 housing seat coupon | not modelled yet | about 5 g | | **Print before the fork rear** (D_6808_FITS.md) |
| Drum | `shoulder_roll_drum_left` | 227.1 g | 2026-11-14 (rear cap screw fix: collars, Ø2.1 pilots) | Exported and recorded 2026-11-14. **Waits** for the roll cable decision (the roll rig) |
| Flange ring | `shoulder_pitch_flange_ring_left` | 38.1 g | 2026-11-14 (rolled rim B, adopted) | Exported and recorded 2026-11-14. Prints in the visible white |
| Rear cap | `shoulder_roll_cap_left` | 85.4 g | 2026-11-14 (rear cap screw fix: sockets, Ø2.9 holes) | Exported and recorded 2026-11-14. **Waits** for the roll cable decision (the roll rig) |
| Drum port cap | `shoulder_roll_drum_port_cap_left` | 1.4 g | 2026-11-11 | Geometry settled. **No recorded export** |
| Fork front | `shoulder_fork_front_left` | 146.8 g | 2026-11-14 (yoke, solid neck, root cone: adopted) | Exported and recorded 2026-11-14. **Waits** for a real plug tried in the channel, and for the rig (the skirt bounds the dish loop) |
| Access plug (1) | `shoulder_fork_access_plugs_left` | 0.3 g | 2026-11-14 (one plug, at the top of the hub's head) | Exported and recorded 2026-11-14. Print with the fork front |
| Fork rear | `shoulder_fork_rear_left` | 67.2 g | 2026-11-14 (stiffer leg, adopted) | Exported and recorded 2026-11-14. **Waits** for the 6808 coupon and for the rig (it carries the yaw exit) |
| Cover ring (optional) | `shoulder_roll_cover_ring_left` | 13.1 g | 2026-11-14 (new) | Exported and recorded 2026-11-14. Dark PETG. Can be left off |
| **Hub** | `shoulder_hub_left` | 80.2 g | 2026-11-14 (rev D3c7, adopted) | **Released for the stage 1 print. Print file ready** (hub section below) |
| Pitch loop cover | `shoulder_pitch_loop_cover_left` | 102.3 g | 2026-11-11 | **Waits:** its M5 pads are placeholders and the feed position waits for the final shell (CAD_NOTES "Still open") |

**Exports:**
- **Hub:** `cad/exports/shoulder/shoulder_hub_left.STEP/.STL` is rev D3c7 (2026-11-14), the adopted hub. STL SHA-256
  `a73103adb49bb9a4fe3b3901fea852e6668e928e7e1586953bc8b25a0c10259b`.
- **Drum, rear cap:** exported and recorded 2026-11-14, with the rear cap screw fix.
- **Fork front, access plug, fork rear, flange ring, cover ring:** exported and recorded 2026-11-14 with the adoption of
  the yoke (CAD_NOTES "Adopted 2026-11-14: yoke fork front").
- **Port cap:** no export in `cad/exports/` yet. Its STL is in the scratch folder only.

## Part by part

Material PETG throughout. "Not sliced" applies to every orientation and support line.

### Drum
- **Orientation:** front lip face down, roll axis vertical. Ribs, slots and wall windows stand vertical.
- **Supports:** under the neck tube's outside and inside its core (open to the bore, removable); under the trunk duct's
  outer end. The trunk channels bridge 6 mm. The skin pockets open into the bore, so nothing is enclosed.
- **Fasteners:** to the pitch RS03 output and the roll RS03 housing with the existing M4 patterns; five M3 inserts in the
  spokes for the flange ring.
- Source: CONCEPT.md section 10; CAD_NOTES "Still open".

### Flange ring
- **Orientation:** flat, on its inboard face (the flat one). No support. 5 × M3 into the drum's spoke inserts.
- **Colour:** the visible white PETG, like the drum and the fork (Joey, 2026-11-14).
- **Rolled rim B, adopted 2026-11-14:** the outboard face rolls R3.2 from the rim into a rim 4.2 deep and eases back to the
  1.8 mm web by r 68.3. The roll is on the top of the print.

### Rear cap

- **Three locating collars** on the drum's rear face sit in sockets in the cap (adopted 2026-11-14). Check that the cap
  seats flat on the drum with all three collars home before driving the screws.
- **Orientation:** front face down, so the stub's axis is vertical and the Ø40.0 stub prints round.
- **Supports:** under the plate between rim and boss (open from the front).
- **Fit:** the stub is Ø40.0 with a 0.5 × 45° lead-in. No coupon needed; the arm's coupon proved Ø40.0 (D_6808_FITS.md).
- **Stops:** the stop slot ends are part of this cap and the drum; the tooth is on the fork rear (B_ROLL_STOPS.md).

### Drum port cap
- **Orientation:** outer face down. Press-in, no screws.

### Fork front
- **Orientation:** upright, Y up; the sleeve ring's bottom edge is the first layer.
- **Shape, adopted 2026-11-14:** a yoke. Nothing above the hub; a solid neck; a 4.5 mm cone where the boss meets the
  cheek's back face.
- **Supports,** all open from below and removable: the sleeve hollow's roof (Y 340-350), the RS02-cap clearance roof
  (Y 361-367). **No pocket ceilings any more** (the neck is solid). The RS02 seat face is a supported face: check its
  flatness after printing (CAD_NOTES "Still open").
- **The opened area needs no support:** it is open air above the two shoulders, which face upward. The hub's head widens
  from the neck by 2 mm a side over 17 mm of height, and the root cone is 45°: both print without support.
- **The driver-access bore** (Ø7, for the 104° RS02 screw) runs up through the neck and comes out at the top of the hub's
  head. It prints as a vertical hole. Its plug goes in after the RS02 screws are tight.
- **Holes printed Ø3.8, reamed Ø4.00:** three on the RS03 boss, at 0° and ±120° on r 15.2. They take Ø4 × 16 pins into the
  RS03's three plain locating holes.
- **Inserts:** six M4 for the fork joint.
- **Before the first print:** try a real XT30(2+2)-F with its lead in the plug channel's size (r 36-50, 16.5 wide,
  Y 353.9-361.1). The plug's height along the motor axis is assumed.
- Source: CAD_NOTES "Side centre r 47" and "RS02 re-clocked +40°".

### Access plug
- **One plug** (Ø6.9 × about 7), flat. It presses into the 104° access bore at the top of the hub's head after the RS02
  screws are in; a pry notch on its back edge lifts it out.
- The 144° bore ends under the drum, out of sight, and gets no plug. (The second plug of the earlier part sat inside the
  drum's volume; it is dropped.)

### Cover ring (optional)
- **What:** a dark ring pressed into the drum's lip bore (Ø86), flush with the lip's face. It closes the 7 mm slot between
  the roll motor's turning face and the lip, which the yoke leaves open to view, and gives the opening one dark face.
- **Print:** dark PETG, flat, plate down, skirt up. No support. 13.1 g.
- **Fit:** modelled Ø85.9 against the Ø86 bore: a light push fit. If it is loose, a dab of glue at three points; if
  tight, sand the skirt. It goes in after the drum's eight lip screws and before the fork front.
- It can be left off: nothing depends on it.

### Fork rear
- **Leg, adopted 2026-11-14:** 2 mm wider each side and 2 mm deeper at its upper stations (Y 380 and 402). The thin
  section beside the cable channel read 0.87 on layer tension before and reads 2.6 or better now (FORK_FRONT_FE.md).
- **Orientation:** upright, Y up; it starts on its flat bottom at Y 340.
- **Supports:** its hollow's roof (Y 340-349); a small one under the stop tooth's outer face (that face carries no load).
- **6808 housing:** modelled Ø52.2 with a 0.4 mm flat at the top, because the bore prints on its side. **Print the seat
  coupon first** and adjust Ø52.2 to a hand-push fit.
- **Joint:** 6 × ISO 7380 M4 button heads into the fork front's inserts. The recesses are about 3.1 mm deep, so a DIN 912
  head would stand proud.
- Source: CAD_NOTES "Side centre r 47"; D_6808_FITS.md; B_ROLL_STOPS.md.

### Hub (rev D3c7, released for the stage 1 print 2026-11-14)

**Print file:** `shoulder_hub_left_revD3c7.3mf` with the STL and a README, on holly-pc in `C:\joe\prints\shoulder-hub\`
and on Joey-PC in `J:\code\prints\shoulder-hub\`. The 3MF is not in the repo (a 3MF under `cad/prints/` needs a
pre-print gate report). STL SHA-256 `a73103adb49bb9a4fe3b3901fea852e6668e928e7e1586953bc8b25a0c10259b`.

![plate](../checks/hub_print/shoulder_hub_left_revD3c7_plate.png)

| Setting | Value | Differs from the arm's PETG profile? |
|---|---|---|
| Printer, nozzle | P2S, 0.4 | |
| Filament | PETG (profile Generic PETG @BBL P2S, 255 °C) | |
| Plate | Cool Plate SuperTack, 70 °C, no glue | |
| Layer | 0.20 mm | |
| Walls | 6 | |
| Infill | **100%** | **Yes** (profile 50%). The strength checks and the 80 g are for a solid part |
| Brim | **None** | **Yes** (profile: outer, 5 mm). The foot is a flat Ø50 ring face; a brim would have to be trimmed off the face the RS02 seats on |
| Supports | Tree, automatic, **blocked round the groove and at the two lugs** | Blockers added |
| Sliced | **81.9 g, 2 h 47 min** | |

- **Orientation:** RS02 face (Y 319.86) down; spigot and lugs grow up. Layers are normal to the yaw axis.
- **Why this orientation, given that shear across the layers at the outer R1.2 lug root governs:** at that root the
  layers lie across the lug's cross-section, so the governing stress is exactly the weak direction. The other two
  orientations are worse or not printable as a fitted part:
  - On a lug's Z face: the plates then press through the lug's thickness, across the layers, and the lug peels.
  - On its side with the layers along the lugs: the root's stress would be in-plane, but the spigot, the groove and the
    RS02 face would print as stacked arcs. The spigot's roundness and the groove's flanks, which the arm's ring fits on,
    would need support on the flanks, and the hub top's bending under the six screws would then cross the layers.
  So the lug root's margin is carried in the figures (1.58 at the section loads, on an assumed 13 MPa), not in the
  orientation.
- **Supports:** only in the dish annulus (its floor is 1.5 mm above the bed); they pull out at the open rim. The groove's
  load flank is a 60° overhang, 1.5 mm tall, printed without support: expect about 0.2 mm of droop.
- **After printing:**
  1. Pull the support out of the dish.
  2. **Gauge both lug holes with a 3.8 mm drill shank.** If it does not pass freely, clear the hole by hand with a
     3.8 mm drill. The M3 bolt must be free in these holes: the arm's plates carry the load, and at the elbow stop the
     shank comes within 0.10 mm of the wall.
  3. **Measure the spigot** (Ø71.6 in CAD) with calipers in two directions at right angles and report both. The arm's
     ring and halves are fitted to the printed size.
  4. **Look at the groove's flanks:** smooth, no support marks, no sagging strands.
- **No ironing:** the print file has none, and the hub is printed as the file is. The disc face (Y 302), where the arm's
  shim ring seats, is an up-facing surface and prints as an ordinary top surface. If the first print shows that face is
  too rough for the ring, ironing it is the next thing to try.
- **Holes printed Ø3.8, reamed Ø4.00:** two on the top, at -142° and 38° on r 12, for the plain shank of the partially
  threaded M4 screws. Ream when the shoulder goes together, not for the stage 1 fit.
- **Bought parts the hub itself needs:** none to print or to fit the arm's parts to it. To bolt it to the RS02 later:
  six M4 screws with washers (four M4 × 28 or × 30 and two partially threaded ones for the reamed holes, lengths under
  "Screws"). The M3 lug bolts and their inserts belong to the arm's parts. Whether these are on the bench list is not
  recorded in this repo.

### Pitch loop cover
- **Colour:** the visible white PETG, like the shell (Joey, 2026-11-14). Its outer band shows between the shell's
  opening and the flange ring; in the shell's white it stops reading as a separate part. Colour only: no change to the part.
- **Orientation:** not settled. Back wall (X 75) down puts the whole wall on support, because the feed riser stands
  about 6 mm proud of it (sliced: 23.5 g of support, 84% of it under the wall). Turn it over, or split the riser off.
  Waits, as above.

## Coupons first

- **6808 housing seat ring** (D_6808_FITS.md): a thin ring with the fork rear's Ø52.2 bore, about 3 mm wall, 7 mm deep,
  printed upright like the fork rear. Adjust Ø52.2 to a hand-push fit.
- The cap's Ø40.0 stub needs no coupon.
- **The three cable test rigs** (table above; CABLE_RIGS.md).

## Ream steps (holes printed Ø3.8, hand-reamed Ø4.00 with a 4 mm H7 hand reamer or a sharp 4.0 drill turned by hand)

| Part | Holes | Takes |
|---|---|---|
| Hub (top, RS02 side) | 2, at -142° and 38° on r 12 | the plain shank of the partially threaded M4 screws (locating); reamed length 7.3 mm |
| Fork front (RS03 boss) | 3, at 0° and ±120° on r 15.2 | Ø4 × 16 pins into the RS03's three plain locating holes |

Pick screws and pins with a shank of 3.98 or more (calipers). That holds backlash to about 0.1° or less.

## Screws

Lengths are checked against the motors' thread depths (RobStride outline drawings) and the seats measured on the built
parts ([CAD_NOTES.md, "Screw and pin lengths"](CAD_NOTES.md)). **A screw that bottoms in a blind hole feels tight and
clamps nothing.**

| Joint | Screws | Thread in the motor or insert | Notes |
|---|---|---|---|
| Hub → RS02 output | 6 × M4: **M4 × 28**, or M4 × 30 with 1.6-2 mm of washer under the head. 2 of them partially threaded, in the reamed holes | 6 × M4, depth 7 min | 0.3 N·m. M4 × 30 bare goes in 8.2 mm and can bottom. Probe one hole: 9 mm or more clears M4 × 30 bare |
| Fork front → RS03 roll output | 6 × **M4 × 18** + 3 × Ø4 pins | 6 × M4, depth 6, blind; 3 × Ø4, depth 7, blind | 0.3 N·m. 5.6 mm engaged. M4 × 20 bottoms. Pins: at most 7 mm into the motor |
| Drum → pitch RS03 output | 6 × **M4 × 18 with one washer**, or M4 × 16 | 6 × M4, depth 6, blind | Pad 11.7 mm. M4 × 18 bare goes in 6.3 mm and bottoms; with a 0.8 mm washer 5.5 mm; M4 × 16 gives 4.3 mm |
| Drum → roll RS03 housing | 8 × **M4 × 10** | 8 × M4, depth 8 | Flange 3.5 mm under the head. M4 × 10 gives 6.5 mm; M4 × 12 goes in 8.5 mm and bottoms |
| Fork front → RS02 body | 5 × **M3 × 12** on PCD 73 at -96 / -56 / -16 / 104 / 144° | 9 × M3, depth 8 (given from the output side) | Seat 6.5 mm. 5.5 mm into the motor. M3 × 16 bottoms. **Check on the motor** that the holes are threaded from the rear, as the old bracket used them |
| Fork rear → fork front (joint) | 6 × ISO 7380 M4 button heads: **2 × M4 × 10** (X ±17) and **4 × M4 × 8** | M4 heat-set inserts, bore Ø5.6 × 7.3-7.8 deep | The recesses are about 3.1 mm deep, so a DIN 912 head would stand proud. **Use short inserts (4 mm):** a standard 8.1 mm insert stands proud of the joint face |
| Flange ring → drum spokes | 5 × **M3 × 5** | M3 × 4 inserts, bore 3.8 deep | Ring 1.8 mm. M3 × 6 bottoms in the bore |
| Rear cap → drum | 3 × **M2.5 × 14, thread-forming** (for plastics; pan or cap head up to Ø5.0), at r 50.6, 0 / 180 / 270°. M2.5 × 16 also fits | Ø2.1 pilots through a 2.5 mm locating collar on the drum, 11 mm deep from the collar's top | 5.6 mm of cap under the head. M2.5 × 14 gives 8.2 mm in the pilot; × 16 gives 10.2 with 0.8 to spare; **M2.5 × 18 bottoms.** The collars locate the cap and carry the roll stop's reaction; the screws only clamp. **Buy 3, and spares.** (Adopted 2026-11-14; before that the parts took M3 at r 50, which no longer fit) |

## Low preload and re-torque (every printed-to-RobStride joint)

- **0.3 N·m** on the M4 screws, so they don't crush the printed bosses.
- **Without a torque screwdriver:** pull the long arm of the hex key with a luggage or kitchen hook scale at a measured
  lever L from the screw axis: F = 0.3 / L. At L = 60 mm that is 5.0 N, about a 0.51 kg reading.
- **No threadlocker in testing.**
- **Re-torque after 24 h and again after the first bench session.**
- **Do the 24 h re-torque before a joint is closed in:**
  - RS02 on the fork front: on the bench, before the fork front goes onto the drum. Assembled, only the 104° screw
    can be reached.
  - Hub on the RS02: before the arm halves go on. Their heads are inside the bore.
- **The second re-torque of those two joints needs a strip-down** (arm halves off; for the RS02, the fork front off the
  drum). Decide before the first bench session whether to plan one.

## Arm-side parts at the hub (owned by the arm thread; for reference)

- **Shim ring:** a printed ring, r 36.2-38.4, picked by measurement, between the arm's end face and the hub's disc face
  (an ordinary top surface in the hub's print file; not ironed).
- **Lug shim plates:** fixed plates with a Ø3.4 hole (the hub's lug holes are Ø3.8, so the bolt is free in the hub) in the
  arm's collar pockets; they pinch the hub's lugs and carry the
  yaw torque. The lug M3 is capped at 0.3 N·m.
- Details: the arm thread's `R1D_NOTES.md` and its print-release packet (`cad/reviews/upper-arm/`).

## RS02 plug and clock (pp_r, 2026-11-13)

- **The RS02 is mounted re-clocked +40°.** Its in-use socket faces the socket tap at **228°**. The spare socket at 48° stays capped.
- **Software:** the yaw joint's zero carries a +40° offset ([SOFTWARE_HANDOFF.md](../../SOFTWARE_HANDOFF.md)).

## Assembly order

1. **RS02 onto the fork front first,** on the bench, with the fork front's back cavity open:
   1. Plug the XT30(2+2)-F onto the 228° socket radially.
   2. Fold the lead into the tap and run it to TAP_LINK.
   3. Fit the five RS02 screws: the three rear ones from above, and the 104° and 144° ones through their access bores.
2. **Fork front onto the drum,** after the 24 h re-torque of the RS02 screws. After this the drum blocks every RS02
   screw except 104°, so the order is fixed.
3. Press in the access plug at the top of the hub's head.
4. Feed the bundle down from the ring's open top (Y 340), round the bend and out of the exit, as bare wire with no
   plug on it. Then fit the fork rear (six button heads).
   - The side-centre round laid the bundles first and slid the RS02 in past them. With the RS02 fitted first, the
     bundle goes in from the top instead. Not tried by hand ([OPEN_ASSUMPTIONS.md](../checks/OPEN_ASSUMPTIONS.md), item 12).
   - **No plug or joint break fits inside any channel** (item 13): thread the wires, then terminate.
5. Hub onto the RS02 output from below, six M4 at 0.3 N·m; lay the arm bundle in the dish and through the window. Then
   the arm halves.
