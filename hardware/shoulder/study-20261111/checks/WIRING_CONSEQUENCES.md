# What the shoulder's cable crossings mean for the arm trunk wiring (2026-11-13)

For the owner of the arm trunk plan (marengo `hardware/electrical/wiring/left-arm-trunk/README.md`). It follows from
[CABLE_TRAVEL.md](CABLE_TRAVEL.md). The three crossing choices are with Joey, and each is to be proven on a rig
([CABLE_RIGS.md](CABLE_RIGS.md)).

**Decided by Joey, 2026-11-15:** both shoulder RS03s stay on 16 AWG; 18 AWG from the yaw RS02 on down the arm. Not
decided: whether 18 AWG also replaces the scheme's 20 AWG below the elbow (the arm thread's elbow pocket was sized for
20 AWG and is 0 to 0.8 mm short for 18 AWG). That question is Joey's.

## If the recommended crossings are chosen

| Crossing | Form | Wire in it | Length inside the crossing | Clamp, fixed side | Clamp, moving side |
|---|---|---|---|---|---|
| Pitch | Wrap on the loop channel's inner wall, with a bight hanging in the void under the frame's step | 2 × 16 AWG + 2 pairs of 28 AWG, side by side | About 450 mm (up to 285 mm wrapped, the rest in the bight) for -50° to +180°. **Corrected 2026-11-14: the bight alone gives about 140° in the room there is; -50° to +180° needs the spiral as well (PITCH_BIGHT.md)** | On the frame, at the top of the void | On the drum's flange, at the trunk mouth |
| Roll | Not settled: today's route on the roll axis if the rig passes it, otherwise a spiral in the rear cap | 2 × 16 AWG + 2 pairs of 28 AWG | On-axis: about 60 mm. Spiral: about 300 mm | On the cap (drum side) | On the fork rear |
| Yaw | Spiral in the dish under the RS02, 2 to 2.5 turns | **2 × 18 AWG** (decided by Joey 2026-11-15; a 10 A fuse at the step is in the scheme) + 2 pairs of 28 AWG | **About 470 mm** | At the fork's exit | At the hub's cable window (a tie round a boss tube) |

## Changes this asks of the trunk plan

1. **18 AWG from the yaw joint down** (segment S3, RS02 splice to elbow splice): **already in the agreed scheme** (Joey,
   2026-11-11). The dish only takes a spiral whose band is 4 mm wide or less; two 16 AWG wires don't fit, two 18 AWG do.
   **New with two signal pairs:** the band is 3.5 mm only if the pairs lie untwisted in the dish (about 0.5 m, four
   singles stacked). Left twisted, the band is 4.7 mm and the spiral gives about ±72°, not ±90°. The third, reserved
   pair does not fit in the dish in either case. Is half a metre of untwisted pair beside the power wires acceptable
   for the bus? (Table in CABLE_TRAVEL.md.)
2. **A 10 A fuse at the RS02 splice** (already in the agreed scheme), in the positive wire of that segment. The board's port trips at 15-20 A, above
   what 18 AWG should carry for long. Loads past the yaw joint by the plan's own fuses: elbow RS02 5 A, forearm RS00 3 A,
   hand 3 A.
3. **Longer cuts.** S3 grows by about 470 mm (to about 900 mm). S1 (pitch) is about 450 mm in the crossing alone, against
   350 mm estimated for the whole segment. S2 depends on the roll choice.
4. **Voltage drop and heat,** S3 at 18 AWG, 1 m out and 1 m back: 0.17 V and 0.67 W at 4 A (a realistic continuous load);
   0.46 V and 5.1 W at 11 A (all three fuses at their limit).
5. **Loose singles through every crossing,** not sleeved, clamped at both ends of the crossing and nowhere inside it. The
   plan asks for flex-rated wire with a PTFE or TPE jacket there, not silicone. The rigs are to be run with the silicone
   wire in hand; if it marks or kinks in 200 cycles, the jumpers need the flex-rated wire.

## Where things can and cannot sit

- **No plug and no plug-in joint break fits inside the shoulder's channels.** An XT30(2+2) body is 16 × 6.5 × 15 mm; the
  channels are 16 × 6. The plan's optional breaks J1 to J3 have no place at these crossings. The wires are threaded bare
  and terminated afterwards.
- **Splices:**
  - **Pitch RS03 (M11):** in the torso, at the motor's top-rear flat, before the pitch crossing. Room there.
  - **Roll RS03 (M12):** on the drum, where the branch to the motor's top bay leaves the trunk. The channel is 16 × 6;
    the plan's staggered splice is about 6 mm across, so it only just fits. Not tried.
  - **Yaw RS02 (M13):** in the fork rear, where the RS02's lead comes through the 7 × 6 tap and meets the trunk channel
    (TAP_LINK). Same 16 × 6 channel, same concern. The 10 A fuse for the 18 AWG segment would also be here, and there is
    no room for a fuse holder in the channel.
  - **Elbow RS02 (M14):** in the upper arm; the arm thread's.
- **Inline drop fuses:** the plan puts a blade fuse holder on each motor's drop "where a hatch gives access". The
  shoulder has no hatch and no pocket for a holder at the roll or yaw motors. Either those fuses sit in the torso (a
  separate fused feed per motor instead of a drop from the trunk), or the shoulder gets pockets for them. Open.
- **CAN pair in the yaw dish:** the 2.2 mm gap between the hub's rim and the fork's skirt will take a 2.0 mm pair. Keep
  the pair tied to the power wires at both clamps, on the side away from the rim.

## The 16 to 18 AWG step and its fuse (2026-11-15)

Picture: [wiring/STEPDOWN_ROOM.png](wiring/STEPDOWN_ROOM.png). **From the repo** unless marked assumed.

- **Where the step has to be.** A 16 AWG tail must not enter the dish, and no joint fits in a channel, the stub or the
  dish. The RS02's own tap (M13) joins the trunk at TAP_LINK in the fork rear (Y 354-360). So the step sits between
  TAP_LINK and the yaw exit, which is **the cavity behind the yaw RS02**: inside the fork front's cuff, between the
  motor body (r 39.25) and the cuff's rear wall, from the dish (Y 320) up to the fork rear's underside (Y 340).
  Measured on the adopted exports: about 44 mm across, 20 mm front to back on the centre line (12 mm at its two ends),
  20 mm high. The trunk already passes through it on its way from the fork rear's channel to the exit.
- **The splice fits there.** The trunk plan's staggered solder splice is about 6 mm across; three of them in a row
  (16 AWG in, the RS02 tap off, 18 AWG out) need about 40 mm of wire length, which the cavity has if the wires run
  across it. Not tried by hand.
- **A fuse holder fits, but cannot be reached.** An inline MINI blade holder is about 36 × 14 × 9 mm (assumed, a
  typical one: measure the one bought). One lies in the cavity; two (the 10 A step fuse and the RS02's own 5 A drop
  fuse) only end to end across the 44 mm, which they exceed. The cavity is closed from above by the fork rear and from
  outside by the cuff. **Changing a fuse there means taking the fork rear off** (six joint screws, and the fork rear
  carries the 6808). The present design has no door.
- **What the plan has** (marengo `left-arm-trunk/README.md`): the board's arm port trips at 15 A with a 20 A, 58 V
  fuse behind it, both sized for 16 AWG and the XT30; drop fuses M11 and M12 7.5 A, M13 5 A, M14 5 A, M15 3 A, hand
  3 A. The plan has no 10 A fuse; the 10 A at the step is in the agreed scheme of 2026-11-11, for which I found no
  document in either repo.
- **Loads below the yaw joint:** fuse-limited 11 A (5 + 3 + 3). Stall currents on the bus are **not in the repo**: the
  trunk plan gives phase currents only (RS02 23 A peak, RS03 43 A peak) and says bus current is not measured; its
  estimate for the whole arm is a few amps typical and 10 to 15 A at peak.
- **What 18 AWG takes** (assumed: 21 mΩ/m, OD 2.3; heating by the method in the power board's HARNESS_INTERFACE.md,
  a pair in still air, 12 W/m²K, factor 1.3). No ampacity figure for this wire is in the repo; the common chart value
  for 18 AWG chassis wiring is 16 A (assumed, not from a datasheet).

  | Current | Rise over ambient, 18 AWG | 16 AWG for comparison |
  |---|---|---|
  | 4 A | 5 K | 3 K |
  | 10 A | 32 K | 15 K |
  | 11 A | 38 K | 18 K |
  | 15 A | 71 K | 34 K |
  | 20 A | 126 K | 61 K |

  Inside a printed channel or coiled in the dish the wire cools worse than in still air. PETG softens at about 70 °C
  (assumed). So 10 A is about the most 18 AWG should carry for long inside these parts, which is what the scheme's
  10 A fuse says; the port's 15 A trip alone does not protect it against a sustained overload.
- **Options, for the power thread and Joey** (none designed here):
  1. **The 10 A fuse in the cavity behind the RS02.** Fits. A blown fuse means a strip-down.
  2. **No separate 10 A fuse.** Everything below the yaw joint is behind its own drop fuse (11 A in all), so a
     sustained overload of the 18 AWG run can only come from a fault in that run itself, which the port's 15 A trip
     clears. The weak case is a partial short that draws 11 to 15 A without tripping: 38 to 71 K of rise.
  3. **The 10 A fuse just below the yaw joint,** in the upper arm, where the arm's halves open. The dish stretch
     (about 0.5 m of 18 AWG) is then upstream of it and protected only by the port. The arm thread's part.
  4. **A door in the cuff's rear,** a flush cover about 45 × 20 mm at the back of the shoulder. Reachable; a visible
     seam on the outline, so it needs Joey's yes before it is drawn.
  5. **The step upstream, on the drum at the roll RS03's splice.** The roll crossing would then carry 18 AWG, against
     the decision that the shoulder stays 16 AWG, and the yaw RS02's 5 A would sit behind the 10 A fuse with the rest
     (16 A of drop fuses behind 10 A). Not recommended.
- The RS02's own 5 A drop fuse has the same problem as the 10 A one (already listed under "Inline drop fuses").

## Sleeve or bare (2026-11-15)

The trunk plan sleeves the trunk in 1/4 in PET braid. In the shoulder:

| Stretch | Sleeve? | Why |
|---|---|---|
| Torso, board pigtail to the pitch clamp | Sleeve | Fixed run |
| Pitch crossing (wrap and bight) | **Bare, separate singles** | The band has to lie one wire thick; a sleeve makes it a 6 mm rope |
| Drum trunk, pitch clamp to roll clamp | Sleeve only if it lies flat | The channel is 16 × 6: the sleeved bundle must lie flat (about 4 mm high) |
| Roll crossing (stub bore or cheek spiral) | **Bare, separate singles** | Twist and bend inside 25 mm |
| Fork rear channel, roll clamp to the cavity behind the RS02 | Sleeve only if it lies flat | 16 × 6 channel |
| Yaw dish spiral and the hub's window | **Bare, separate singles** | 3.5 mm band; a sleeved bundle gives about ±51° at best |
| Below the window tie, into the upper arm | Sleeve | Fixed run; the arm thread's |

- End every sleeve at a clamp or tie, with adhesive-lined heat-shrink over its end (trunk plan), and put a tie at each
  end of every bare stretch.
- Bare stretches need rounded edges where the wires bear. As modelled, the hub window's mouth in the dish floor is
  sharp (three edges; the slot's own corners are R1.5). It gets a 1.5 mm round in the next hub revision.
- If the yaw rig shows scuffing on the dish floor, the fix is PTFE tape on the floor, not a sleeve.

## Places outside this study that still say 16 AWG down the arm (2026-11-15; not edited)

- marengo `hardware/electrical/wiring/left-arm-trunk/README.md`: the conductor table ("16 AWG high-strand silicone to
  M14; 18 AWG from M14 to M15"), segment S3, the cut list ("3.5 m each of red and black 16 AWG"), and the port note
  (15 A trip as "the real overload limit for XT30 contacts and 16 AWG"). No 10 A fuse in the fuse table.
- marengo `left-arm-trunk/BUY_LIST.md`: item 8 (16 AWG, 3.5 m each), item 7 (five holders with 16 AWG leads), item 6
  (fuses: no 10 A), item 9 (18 AWG only for the elbow section), and the sleeving table (trunk in PTN0.25 throughout).
- marengo `left-arm-trunk/wiring_diagram.py` and its picture `LEFT_ARM_TRUNK_WIRING.png`.
- marengo `hardware/electrical/wiring/left-arm-trunk-plan.md`, section 4 table: jumpers J1 to J3 (shoulder and upper
  arm) 16 AWG, J4 and J5 18 AWG.
- marengo `hardware/electrical/wiring/left-shoulder-bench-harness.md` (the bench harness).
- marengo files that mention 16 AWG and that I have not read line by line: `hardware/designs/left-arm/BUY_ORDER.md`,
  `prints/upper-arm/PARTS_LIST.md`, `upper-arm/clamshell/CONCEPT.md`, `renders/harness_turntable.py`.
- roark `hardware/power-board/`: `layout/HARNESS_INTERFACE.md`, `layout/harness_wires.csv` (W3, W4) and
  `REVB5_CHANGES.md` give the arm pigtails as 16 AWG with a 20 A inline fuse. That is the torso end and stays 16 AWG;
  what changes is that the port's 15 A / 20 A protection no longer matches the thinnest wire behind it.
- The arm thread's `cad/upper-arm/README.md` and `CABLE_SLACK.md` already say 18 AWG (2026-11-15).
- In this study, [CABLE_LOOP_RIG.md](CABLE_LOOP_RIG.md) (a superseded page) still says 16 AWG.

## Open, for the wiring owner

- ~~Is 18 AWG acceptable for S3?~~ Decided 2026-11-15: yes. Open: where its 10 A fuse sits, or whether it is needed.
- Where do the drop fuses for the roll and yaw motors go?
- Is silicone acceptable in the crossings if it passes the rigs, or must the jumpers be flex-rated regardless?
