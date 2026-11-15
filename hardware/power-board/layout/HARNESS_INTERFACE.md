# Power board rev B5: harness interface

This is the hand-off from the power board to the torso harness (the frame thread's `harness.py`). It covers what leaves the
board, where it leaves, and what each run ends in. In-torso routing is the frame thread's job once Joey places the board;
section 5 proposes the arm runs (board to the shoulder foot, the fuse and plug joint, the CAN adapters) for the floorplan position.

| File | Content |
| --- | --- |
| [marengo_pdu_revb_package.step](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/pdb/design/layout/marengo_pdu_revb_package.step) (in marengo, LFS) | board with parts, option-D heatsink, `KO_*` keep-outs, `WIRE_*` stubs |
| [harness_wires.csv](harness_wires.csv) | wire list: one row per conductor group (net, gauge, OD, from/to, twist) |
| [harness_exits.csv](harness_exits.csv) | one row per `WIRE_*` body: exit point, exit direction, bend radius, direction after the bend |
| [schematic/tools/package_step.py](../schematic/tools/package_step.py) | builds the STEP and `harness_exits.csv` from the board (`schematic/tools/conn_export.py` gives the connector data) |

## 1. Package frame (local origin and orientation)

- **X, Y are the board floorplan coordinates.** These are the same numbers as the torso frame docs: board X −50..50 (robot's
  left = +X), Y 170..340 (+Y up, the top edge at Y 340; 100 × 170 mm since option A, 2026-11-07). They match the torso only while the board sits at its floorplan
  position. Joey places the board in the upper cavity, so the frame thread applies one rigid transform to the whole package.
- **Z = 0 is the board's bottom face.** Components are on +Z (top face at Z 1.6) and the heatsink is on −Z (option D, chosen:
  thermal pad −0.5..0, 120 × 69 mm footprint at X −34.5..34.5, Y 196.5–316.5, base to −5.1, fins to −36.5). Air runs along Y;
  `KO_heatsink_air_inlet` / `_outlet` keep 20 mm free at both ends of the fins.
- **Units:** mm. All parts are on the top side; the bottom carries only the heatsink.

## 2. Exits

Every exit point and direction is in [harness_exits.csv](harness_exits.csv), with one row per `WIRE_*` body. The fields are:
- the start point (x, y, z);
- the initial direction (dx, dy, dz);
- the bend radius;
- the direction after the bend.

Each `WIRE_*` body runs 80–120 mm. Rows that bend the same way use concentric bends so they nest. Summary:

| Group | Exit | Leaves toward | Bend | Keep-out |
| --- | --- | --- | --- | --- |
| Pack pair J1 (8 AWG, 7.0 mm) | solder pads at (1, 335) and (15, 335), up from Z 1.6 | +Z, then +Y over the top edge | R15 | `KO_pack_8AWG_leads_R15_bend` |
| Limb pigtails J8, J10, J12 (arms, waist, aux: 16 AWG, 3.0 mm; legs: 14 AWG, 3.6 mm) | pads at X +45, Y 206–248 | +Z, then +X out of the side edge | 3 × OD (R9 / R11) | `KO_limb_pigtails_right` |
| Limb pigtails J9, J11, J13 | pads at X −45, Y 206–248 | +Z, then −X | 3 × OD | `KO_limb_pigtails_left` |
| Brake J3, J25 (Mini-Fit Jr, 18 AWG, 2.3 mm) | mated plug top, Z about 23.6, at X 29 and 37 | +Z, then +Y | R8 and up (nested) | `KO_brake_plugs_J3_J25` |
| Buck board pigtail J24 (Micro-Fit 2 × 6, 18 AWG, 1.9 mm) | plug top, Z about 17.6, X −37.5..−22.5 | +Z, then +Y | R6 and up | `KO_12V_converter_plug_J24` |
| 12 V outputs | on the buck board since split S1 (2026-11-09): J2 Jetson, J3 Pi buck, J4 fans, J5 SPARE_SW, J6 SPARE_ON | | | |
| Pi link J21 (GH 8, 26 AWG, 1.0 mm) | plug back at Y about 185, Z 3.8 | −Y (side entry) | none on the board | `KO_bottom_plug_J21` |
| E-stop loop J20 (GH 8, 26 AWG, 1.0 mm) | plug back at X about −48.5, Z 3.8 | −X (side entry) | none on the board | `KO_estop_plug_J20` |

Rev B5 change in this hand-off: J20 was turned 180° so its plug enters from the −X edge. It used to face into the board.

Mated heights (Micro-Fit about 16 mm, Mini-Fit Jr about 22 mm above the top face) are approximate. They come from the Molex
series, not from a drawing, and should be checked against the 43025 and 5557 drawings before the frame clearances are frozen.

## 3. Wire list

The full list is in [harness_wires.csv](harness_wires.csv): 23 rows with net, gauge, OD including the jacket, from, to,
length, twist and status. It also covers the off-board thermostat pair, the fan leads and the two arm CAN pairs.

## 4. Connectors at the far ends

All dimensions marked "about" are approximate. Take the drawing before freezing the frame clearances.

| Run | Board end | Far end, part number | Mated envelope |
| --- | --- | --- | --- |
| Pack | 8 AWG soldered pair → **Amass XT90 (board half, solder cups take 8 AWG)** | **Pack-side XT90S half in a case-wall pocket** (battery main ec2513d): X +10..+45, Y 323..345, Z −45..−60 in torso coordinates, **mating face toward −X**, leads inside the case | about 21 × 11 mm section, about 55 mm mated length along −X/+X. The 8 AWG pair has to arrive along +X into the pocket face, so it needs space for an R15 turn before the plug (8 AWG plus the plug back is about 30 mm straight) |
| L arm, R arm, waist (aux the same) | **16 AWG** silicone pigtail, as in the arm trunk plan → inline 58 V MINI blade fuse holder (20 A, Littelfuse 997 class) → **Amass XT30(2+2)-F** on the pigtail (live side), joint in the void under the step (section 5). **This row is the board pigtail only**: after the plug the arm trunk stays 16 AWG through shoulder pitch and roll and is 18 AWG from the yaw drive down (table below) | arm trunk XT30(2+2)-M | fuse holder about 40 × 20 × 15 mm (inline 58 V part still to choose); XT30(2+2) mated about 15 × 8 × 32 mm. The 2 signal pins carry the trunk's CAN from the Pi's USB-CAN adapter; this board carries no CAN |
| L leg, R leg (rev C) | 14 AWG pigtail (kept heavier for the leg ports, rev C) → fuse → **Amass XT60** + separate JST GH CAN at the leg | — | XT60 mated about 16 × 8 × 32 mm |
| Aux | as arms | — | unfitted |
| Brake ×2 | Mini-Fit Jr 5557-02R plug | HS50 tabs (solder or ring) | plug about 10 × 10 mm, 22 mm above the board |
| Buck board pigtail | Micro-Fit 3.0 43025-1200 | the same plug on the buck board | plug about 21 × 10 mm |
| 12 V outputs (buck board) | Micro-Fit 3.0 43025-0200/-0400 | loads | plug about 7 × 10 mm |
| Pi link, E-stop | JST GH GHR-08V-S (both) | Pi adapter; E-stop and reset buttons | plug about 11 × 4.25 × 6.5 mm |

**Arm, waist and aux pigtails are 16 AWG** (coordinator 18:55Z, matching
[wiring/left-arm-trunk](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/wiring/left-arm-trunk/README.md): 16 AWG trunk power on XT30, GH1.25 CAN). The XT30 cups
take 16 AWG, and the board's SolderWire-2.5sqmm pads (2.4 mm hole, 3.6 mm relief) take it unchanged. Check, for a twisted
pair of 16 AWG silicone (13.2 mΩ/m, 3.0 mm OD), in still air with about 12 W/m²K from the surface and a 1.3 factor for the pair:

| Case | Current | Temperature rise | Verdict |
| --- | --- | --- | --- |
| Expected arm load (drop fuses 7.5 + 7.5 + 5 + 5 + 3 A; real draw is a few amps) | 5 A | about 4 K | fine |
| Heavy arm load | 10 A | about 16 K | fine |
| Software trip limit (sustained) | 15 A | about 39 K → about 80 °C at 40 °C torso air | fine for 200 °C silicone; XT30 contacts are the limit, as the trunk plan says |
| Fuse rating, software failed | 20 A | about 79 K → about 120 °C | survivable (silicone 200 °C), not a running point; the 20 A fuse clears a few × 20 A within seconds |
| Port overload trip (TPS48111, 30 A, about 16 ms) | 30 A | 0.04 K (adiabatic) | negligible |
| Short at the pigtail end (1.1–1.4 kA, under 2 µs) | — | 0.01 K | negligible |

**18 AWG down the arm (decided 2026-11-14).** The arm harness drops to 18 AWG where it crosses the upper-arm yaw joint
(16 AWG allowed only about ±37° there; 18 AWG gives ±90°). The board pigtails J8 and J9 stay 16 AWG: they carry the whole
arm, and the shoulder pitch and roll runs stay 16 AWG (decided 2026-11-15). The 20 A inline fuse on each arm port stays. Nothing on the board changes: the pads take either gauge, and
the port breaker (30 A overload, 35–45 A short circuit) opens on a short at the end of an 18 AWG run as it does on 16 AWG.

The same check for a twisted pair of 18 AWG silicone (20.9 mΩ/m, 2.3 mm OD), copper resistance corrected for temperature:

| Current, sustained | Temperature rise | Verdict |
| --- | --- | --- |
| 5 A | about 9 K | fine |
| 7.5 A | about 20 K | fine: the software limit for the 18 AWG section |
| 10 A | about 39 K → about 80 °C at 40 °C | fine: the fuse rating for the 18 AWG section |
| 15 A | about 105 K → about 145 °C | survivable for 200 °C silicone, not a running point: the most an 18 AWG run may ever be fused at |
| 20 A | about 265 K | over the insulation rating: **18 AWG must never sit behind only the 20 A port fuse** |

So every 18 AWG run needs its own fuse, **10 A** (the same 58 V MINI family), with the sustained
software limit for that section at 7.5 A. It feeds the upper-arm yaw, elbow and forearm drives and the hand. The drives'
bus currents are not measured yet; the arm trunk plan's branch fuses for them add up to 13 A plus 3 A for the hand, and it
expects a real draw of a few amps. A shoulder run on 18 AWG would need the arm port's inline fuse at 15 A at most
instead of 20 A; that is not the plan.

Why the shoulder stays 16 AWG: the shoulder section carries the whole arm, two RS03 drives included. The RS03 manual
(RS03_User_Manual_261013, section 1.3) gives phase currents only: 13 Apk at the rated 20 N·m and 43 Apk at the 60 N·m
peak. Supply current is not in the manual and not measured; rated load at 100 rpm is about 210 W at the shaft, so about
5 to 6 A from the bus per RS03 with losses assumed. Two of them working hard plus the rest of the arm fits the 15 A
software limit on 16 AWG (about 43 K rise) but not the 7.5 to 10 A that keeps 18 AWG at the same temperature. The wire runs
through PETG parts, which soften near 80 °C, so the sustained wire temperature matters more than the 200 °C silicone
rating. Voltage drop is not the issue either way: about 13 mΩ against 21 mΩ for a 0.5 m section there and back, 0.26 V
against 0.42 V at 20 A.

**Arm trunk gauges and fuses, as of 2026-11-15.** This table replaces the gauges in the reference repo's
[left-arm-trunk README](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/wiring/left-arm-trunk/README.md)
(S3 at 16 AWG, S4 as four paralleled 18 AWG wires); its segment names and splices still apply; its fuses are replaced by the plan below.

| Segment | Power wire | Fuse ahead of it | Sustained limit |
| --- | --- | --- | --- |
| Board pigtail, S0, S1 (pitch), S2 (roll) | one 16 AWG pair | 20 A, inline at the board pigtail | 15 A |
| Taps to the pitch, roll and yaw drives | one 16 AWG pair each | the same 20 A; no drop fuses | |
| S3 (upper-arm yaw to the elbow drive) | one 18 AWG pair | 10 A, in the upper arm just below the yaw joint | 7.5 A |
| S4 (across the elbow to the forearm drive and the hand drop) | one 18 AWG pair | the same 10 A; no fuse of its own | 7.5 A |

**One 10 A fuse for everything below the yaw joint (decided 2026-11-15).** The 16 to 18 AWG splice stays in the shoulder,
in the cavity behind the yaw drive, but a fuse there cannot be reached once the fork is closed. So the 10 A fuse sits in
the upper arm, in the neck just below the hub, where the arm's front half comes off. It is the only fuse below the
shoulder apart from the hand's own 3 A: the elbow drive's 5 A drop fuse and the 5 A segment fuse at the elbow are
dropped, since all the wire behind the 10 A fuse is 18 AWG (39 K rise at 10 A in free air) and the drives limit their
own current.

- Fuse: Littelfuse **0997010.WXN** (MINI blade, 58 V DC, 10 A). Ordinary MINI fuses are 32 V and must not be used on
  this bus.
- Holder: a generic inline MINI holder (about 36 × 14 × 9 mm, assumed; measure the one bought). These are marked 32 V.
  The fuse does the interrupting and the holder only has to insulate 58 V, so this is accepted here as a judgment, not
  as a rating. The one inline MINI holder found with a 58 V marking is Littelfuse FHM (0FHM0001XP, 14 AWG leads), larger
  and about $7 to $10.
- Pocket: about 70 × 16 × 11 mm with the straight wire at each end, in the upper arm neck.
- Not covered by this fuse: about 0.5 m of 18 AWG between the splice and the fuse (the yaw cable space and the hub's
  tunnel). A hard short there opens the port breaker. A steady 10 to 15 A partial short would put about 500 W into the
  fault point and is not expected to stay partial.
- The board cannot measure this section alone (it meters the whole port), so the 7.5 A sustained limit is for software
  to hold from the drives' own current reports.
- **No drop fuses on the shoulder drives (decided 2026-11-15).** The trunk plan's drop fuses for the pitch, roll and yaw
  drives (7.5, 7.5 and 5 A) have no reachable place in the shoulder. Their three taps are 16 AWG instead, so the 20 A
  fuse at the board covers them. The shoulder's tap channels take a 16 AWG pair (checked on the part exports, not with
  real wire). A seller's page for the XT30(2+2) gives its power pins as 20 A with 16 AWG; the plug's real length and
  lead exit at the yaw drive are still to be measured.
- Fit, checked on the part exports by the arm and shoulder work, not yet with real wire: the holder sits in the neck
  12 to 51 mm below the hub seat with no change to the arm halves, and the fuse is changed with the front half off; the
  three-way splices fit behind the yaw drive side by side with a 5 mm stagger, each insulated on its own.

S4 carries the RS00 and a future hand. One 18 AWG pair is enough: 5 A sustained is about 9 K of rise in free air, 7.5 A
about 20 K, and 0.5 m there and back drops 0.1 V at 5 A. The second pair in the old spec was margin for "about 6 A", not a
need. Expected sustained load is about 3 to 3.5 A: the RS00 manual (RS00_User_Manual_260713) gives 4.7 Apk phase current at
the rated 5 N·m and 15.5 Apk at the 14 N·m peak, which is about 1.5 A from the bus at rated load with losses assumed, and
the hand budget is 2 A at 48 V (an estimate; no hand is designed). Neither is measured. A hand that needs more than about 7.5 A sustained (360 W) would need a
second pair, which the elbow spiral does not fit.

**Arm wire to buy** (replaces the wire rows of the reference repo's left-arm-trunk BUY_LIST; connectors and fuses there
still apply, less the drop fuses, plus one 58 V 10 A MINI fuse, Littelfuse 0997010.WXN, and holder per arm):

| Use | Wire | Outside diameter | Buy | For both arms |
| --- | --- | --- | --- | --- |
| Power, board to the roll drive (S0–S2, RS03 drops) | 16 AWG silicone, red and black | 3.0 mm (catalogue figure, not checked) | BNTECHGO 16 gauge silicone, red + black | about 3 m per colour |
| Power, yaw drive to the forearm (S3, S4, RS02 / RS00 / hand drops) | 18 AWG silicone, 150 × 0.08 mm strands, red and black | **2.3 ± 0.1 mm** (seller specification for this construction); passages are sized for 2.6 mm, which covers every catalogue figure found (2.3 to 2.6) | BNTECHGO model **SW18G150008F25C2** (red 25 ft + black 25 ft) | about 3 m per colour |
| CAN pairs (arm bus and hand bus), twisted about 1 turn per 25 mm | **28 AWG** silicone, 16 × 0.08 mm strands, two colours per pair | about 1.2 mm (from memory, not checked against a specification) | BNTECHGO 28 gauge silicone in a multi-colour kit (the red + black spool is model SW28A16008F10C2; pick the kit with yellow and green) | about 10 m per colour |

**The CAN pairs are 28 AWG, not 26 AWG.** The 2026-11-06 trunk spec chose 26 AWG "so it fits the JST-GH and GH1.25 crimps",
but those crimps take 26 to 30 AWG, and the pre-crimped GH leads on the same buy list are already 28 AWG. Electrically
the gauge does not matter at these lengths: 28 AWG is about 0.21 Ω/m, so a 3 m bus adds about 1.3 Ω of loop resistance
against the 60 Ω of the two terminators (wire resistance from standard tables; arm bus length assumed). 28 AWG is what fits
the yaw joint with the third reserved pair.

**Pi link J21 pinout** (JST GH 8, 26 AWG; rev B5 added pin 8 for the power-fail warning). Every Pi input here is
open drain or driven at 3.3 V from the Pi's own rail; nothing above 3.3 V reaches the cable.

| Pin | Net | Direction | Pi side |
| --- | --- | --- | --- |
| 1 | +3V3_PI | Pi → board | Pi 3.3 V: meters' supply, I²C and NO pull-ups |
| 2 | I2C_SDA | both | dedicated Pi I²C controller, Pi pull-ups |
| 3 | GND | | |
| 4 | I2C_SCL | Pi → board | Pi pull-ups |
| 5 | ESTOP_PI_N | board → Pi | GPIO input, no pull: low = E-stop pressed |
| 6 | WD_FEED | Pi → board | GPIO output, heartbeat toggled from the control loop |
| 7 | PORT_FLT_N | board → Pi | GPIO input, 10k pull-up on the board: low = a port latched off |
| 8 | PWR_FAIL_N | board → Pi | GPIO input **with a pull-up to the Pi's 3.3 V** (10k, or the internal pull-up): low = converter input under 31.4 V (re-arms at 34.4 V) |

The CAN pair for the XT30(2+2) signal pins doesn't come from this board. It comes from the Pi's USB-CAN adapter and joins at
the pigtail's XT30(2+2)-F (section 5).

## 5. Arm runs in the torso: board to the shoulder foot

**Status: proposed 2026-11-15, from numbers only.** Nothing here has been drawn or clash-checked in CAD. It holds for the
board at its floorplan position (section 1); if Joey places the board elsewhere, legs 1 and 2 change and the rest stays.
Sources: the reference repo's [torso-frame README](https://github.com/jaylamping/marengo/blob/main/hardware/designs/torso-frame/README.md)
(frame members, side bands, compute shelf, Pi) and the shoulder scripts' `FEED` numbers (riser foot). Coordinates are
torso coordinates: X to the robot's left, Y up, Z forward. The left arm is given; the right arm is the mirror in X.

**Where the run ends.** The shoulder cover's two feed risers (power 16 × 6, signal 10 × 5) open downward at the
**shoulder foot: X 107, Y 300, Z 0**, in the void under the step overhang (X 75 to 113, Y 300 to 353.6, outside the lower
box's posts). The riser duct is 32.8 wide across Z (Z ±16.4).

**Power pigtail W3 (16 AWG pair, about 250 mm with the fuse holder):**

| Leg | From | To | Passage | Length |
| --- | --- | --- | --- | --- |
| 1 | J8 pads, board X 45, Y 241 and 248, top face (Z 49.1) | side band at the board's +X edge | the wires lie over the board edge and drop into the band, X 50 to 55, Z 42 to 50 (5 × 8 mm: two 3.0 mm wires side by side along Z). The front post face at X 55 is 5 mm outside the board edge, so the `harness_exits.csv` bend (+Z, then +X at R9) has to be laid flatter here | about 15 |
| 2 | band at Y 245 | band at Y 312 | up the side band | about 70 |
| 3 | band, Y 305 to 320 | void under the step, X 75 | outboard behind the front post (X 55 to 75, post at Z 50 to 70; the wires pass at Z 42 to 50), below the corner bracket at Y 325 to 353 | about 25 |
| 4 | X 75, Y 312, Z 46 | fuse holder, +Z end | up and outboard in the void | about 35 |

**Fuse and plug joint.** Both sit in the void under the step, side by side along Z, on one printed clip screwed to the two
spare M5 T-nuts in the step side rail's underside slot (X 103, Y 353.6):

| Part | Envelope | Position |
| --- | --- | --- |
| Inline 20 A MINI fuse holder | 40 × 20 × 15 | X 78 to 93, Y 333 to 353, Z 8 to 48, long axis along Z; the pigtail enters at the +Z end |
| XT30(2+2)-F on the pigtail, mated with the trunk's XT30(2+2)-M | 15 × 8 × 32 mated | X 78 to 93, Y 337 to 345, Z −27 to 5, long axis along Z, the trunk leaving at the −Z end |

From the plug the trunk (S0, about 70 mm) turns down and outboard to the shoulder foot, with the M11 splice for the pitch
drive on the way. The joint sits inboard of the riser (X 101.6 to 112.4) and under the 18 mm gap between the shelf rail
(X 75) and the step side rail (X 93), which is where the CAN pair and the pitch drive's drop come down.

**CAN adapters and CAN pairs W22, W23.** One USB-CAN adapter per bus (model not chosen, nothing bought; envelope
assumed 30 × 60 × 12). The two arm adapters sit on the compute shelf beside the Pi on its +X side, stacked: footprint
X 24 to 52, Z −45 to 15, left arm at Y 376 to 388, right arm at Y 390 to 402, USB toward the rear on short cables to the
Pi. The left arm's pair (28 AWG, twisted) runs outboard along the shelf to X 75, over the shelf rail and down the gap
between the shelf rail and the step side rail to the plug's two signal pins: about 120 mm. The right arm's pair crosses
the upper bay to the −X side first: about 270 mm. The compute bay is Joey's to pack, so this is a reserved space, not a
fixed one.

**Open in this proposal:**

- Not checked in CAD: the leg 3 crossing behind the front post (pack cradle, tray rail and bracket are near), the clip
  against the riser and the pitch bracket, and the adapter stack against the Pi power stub (X 22 to 52, Z 20 to 40) and
  the Jetson shelf (Y 410).
- Which shell piece uncovers the fuse.
- The hand bus pair: the XT30(2+2) has two signal pins, so the hand's CAN pair needs its own 2-pin plug beside it, and
  the hand, waist and leg buses need five more adapters with no place yet (the frame README has no home for a hub board).
- The board is 100 × 170 (Y 170 to 340); the frame model's envelope is still the older 100 × 150 (Y 190 to 340), and the
  bottom front rail is at Y 155 to 175, Z 50 to 70. The bottom 5 mm of the board and the J21 cable's exit need a check
  against that rail when the board is placed.
