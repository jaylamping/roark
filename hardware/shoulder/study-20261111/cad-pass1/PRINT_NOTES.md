# Left shoulder print package (updated 2026-11-13)

Collected from the checks. Each item names where it comes from. **No shoulder part has been sliced yet:** orientations
and supports below are judged from the geometry, and each part still needs its pre-print gate
([part-lifecycle.md](../../../../conventions/part-lifecycle.md)).

## What can print now, and what waits

| Part | File | Mass (PETG) | Geometry last changed | Status |
|---|---|---|---|---|
| Yaw loop test rig (PLA) | `cad/exports/fixtures/fixtures_yaw_loop_rig_*.STL` | 25.9 g, 1 h 15 min | 2026-11-13 | **Print now.** It decides the hub window and the yaw exit ([CABLE_LOOP_RIG.md](../checks/CABLE_LOOP_RIG.md)) |
| 6808 housing seat coupon | not modelled yet | about 5 g | | **Print before the fork rear** (D_6808_FITS.md) |
| Drum | `shoulder_roll_drum_left` | 226.5 g | 2026-11-11 | Geometry settled. **No recorded export** |
| Flange ring | `shoulder_pitch_flange_ring_left` | 29.3 g | 2026-11-11 | Geometry settled. **No recorded export** |
| Rear cap | `shoulder_roll_cap_left` | 85.2 g | 2026-11-11 (stop rev 2, 6808 land) | Geometry settled. **No recorded export** |
| Drum port cap | `shoulder_roll_drum_port_cap_left` | 1.4 g | 2026-11-11 | Geometry settled. **No recorded export** |
| Fork front | `shoulder_fork_front_left` | 155.2 g | 2026-11-13 (plug pocket pp_r) | Export current. **Waits** for a real plug tried in the channel, and for the rig (the skirt bounds the dish loop) |
| Access plugs (2) | `shoulder_fork_access_plugs_left` | 0.7 g | 2026-11-13 | Export current. Print with the fork front |
| Fork rear | `shoulder_fork_rear_left` | 63.7 g | 2026-11-12 (six-screw joint) | **Waits** for the 6808 coupon and for the rig (it carries the yaw exit). **No recorded export** |
| Hub | `shoulder_hub_left` | 80.2 g | in work | **Waits.** See below |
| Pitch loop cover | `shoulder_pitch_loop_cover_left` | 102.3 g | 2026-11-11 | **Waits:** its M5 pads are placeholders and the feed position waits for the final shell (CAD_NOTES "Still open") |

**Exports that don't match their part:**
- **Hub:** the committed `cad/exports/shoulder/shoulder_hub_left.STEP/.STL` is rev C+ (2026-11-11). The hub has moved on
  to rev D3c (lugs to X 34.4, r 20 fill behind both lugs, cable window moved). The window angle is being settled
  (68°, hub D3c5, in checks), so the export is replaced when that hub is released. Do not print the committed hub.
- **Drum, flange ring, rear cap, port cap, fork rear:** no export in `cad/exports/` at all. The STLs made with each build
  are in the scratch folder only. They need exporting and recording before a print.
- Fork front and access plugs: exported and recorded with the part, 2026-11-13.

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
- **Orientation:** flat. No support. 5 × M3 into the drum's spoke inserts.

### Rear cap
- **Orientation:** front face down, so the stub's axis is vertical and the Ø40.0 stub prints round.
- **Supports:** under the plate between rim and boss (open from the front).
- **Fit:** the stub is Ø40.0 with a 0.5 × 45° lead-in. No coupon needed; the arm's coupon proved Ø40.0 (D_6808_FITS.md).
- **Stops:** the stop slot ends are part of this cap and the drum; the tooth is on the fork rear (B_ROLL_STOPS.md).

### Drum port cap
- **Orientation:** outer face down. Press-in, no screws.

### Fork front
- **Orientation:** upright, Y up; the sleeve ring's bottom edge is the first layer.
- **Supports,** all open from below and removable: the sleeve hollow's roof (Y 340-350), the RS02-cap clearance roof
  (Y 361-367), the dome pocket ceilings. The RS02 seat face is a supported face: check its flatness after printing
  (CAD_NOTES "Still open").
- **Holes printed Ø3.8, reamed Ø4.00:** three on the RS03 boss, at 0° and ±120° on r 15.2. They take Ø4 × 16 pins into the
  RS03's three plain locating holes.
- **Inserts:** six M4 for the fork joint.
- **Before the first print:** try a real XT30(2+2)-F with its lead in the plug channel's size (r 36-50, 16.5 wide,
  Y 353.9-361.1). The plug's height along the motor axis is assumed.
- Source: CAD_NOTES "Side centre r 47" and "RS02 re-clocked +40°".

### Access plugs
- **Orientation:** flat. They press into the 104° and 144° access bores after the RS02 screws are in.

### Fork rear
- **Orientation:** upright, Y up; it starts on its flat bottom at Y 340.
- **Supports:** its hollow's roof (Y 340-349); a small one under the stop tooth's outer face (that face carries no load).
- **6808 housing:** modelled Ø52.2 with a 0.4 mm flat at the top, because the bore prints on its side. **Print the seat
  coupon first** and adjust Ø52.2 to a hand-push fit.
- **Joint:** 6 × ISO 7380 M4 button heads into the fork front's inserts. The recesses are about 3.1 mm deep, so a DIN 912
  head would stand proud.
- Source: CAD_NOTES "Side centre r 47"; D_6808_FITS.md; B_ROLL_STOPS.md.

### Hub (when released)
- **Orientation:** RS02 face (Y 319.86) down; spigot and lugs grow up.
- **Supports:** in the dish annulus only (the dish floor is 1.5 mm above the bed); it pulls out at the open rim. The
  groove's load flank is a 60° overhang, 1.5 mm tall; expect about 0.2 mm of droop on it (A_HUB_LUGS.md, "Print
  orientation").
- **Iron the disc face (Y 302).** It is an up-facing surface in this orientation, and the arm's shim ring seats on it.
- **Holes printed Ø3.8, reamed Ø4.00:** two on the top, at -142° and 38° on r 12. They take the plain shank of the
  partially threaded M4 screws (lengths under "Screws").
- **Lug holes:** printed Ø3.8 for the arm's fixed shim plates; the arm thread owns that fit.

### Pitch loop cover
- **Orientation:** not settled. Back wall (X 75) down puts the whole wall on support, because the feed riser stands
  about 6 mm proud of it (sliced: 23.5 g of support, 84% of it under the wall). Turn it over, or split the riser off.
  Waits, as above.

## Coupons first

- **6808 housing seat ring** (D_6808_FITS.md): a thin ring with the fork rear's Ø52.2 bore, about 3 mm wall, 7 mm deep,
  printed upright like the fork rear. Adjust Ø52.2 to a hand-push fit.
- The cap's Ø40.0 stub needs no coupon.
- **Yaw loop rig** (above).

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
| Rear cap → drum | 3 × **M3 × 14 or M3 × 16, thread-forming** (for plastic), at r 50, 0 / 180 / 270° | Ø2.6 pilots, 8.5 deep, in the drum | 8.3 mm of cap under the head. M3 × 14 gives 5.7 mm in the pilot, M3 × 16 gives 7.7; **M3 × 18 bottoms.** **Open:** the pilots have only 0.7 mm of wall toward the drum's bore, and these screws carry the roll stop's reaction ([OPEN_ASSUMPTIONS.md](../checks/OPEN_ASSUMPTIONS.md), item 38) |

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

- **Shim ring:** a printed ring, r 36.2-38.4, picked by measurement, between the arm's end face and the hub's disc face.
  It is why the disc face is ironed.
- **Lug shim plates:** fixed plates with a Ø3.8 hole in the arm's collar pockets; they pinch the hub's lugs and carry the
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
3. Press in the two access plugs.
4. Feed the bundle down from the ring's open top (Y 340), round the bend and out of the exit, as bare wire with no
   plug on it. Then fit the fork rear (six button heads).
   - The side-centre round laid the bundles first and slid the RS02 in past them. With the RS02 fitted first, the
     bundle goes in from the top instead. Not tried by hand ([OPEN_ASSUMPTIONS.md](../checks/OPEN_ASSUMPTIONS.md), item 12).
   - **No plug or joint break fits inside any channel** (item 13): thread the wires, then terminate.
5. Hub onto the RS02 output from below, six M4 at 0.3 N·m; lay the arm bundle in the dish and through the window. Then
   the arm halves.
