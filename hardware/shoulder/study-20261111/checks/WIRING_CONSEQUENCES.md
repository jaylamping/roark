# What the shoulder's cable crossings mean for the arm trunk wiring (2026-11-13)

For the owner of the arm trunk plan (marengo `hardware/electrical/wiring/left-arm-trunk/README.md`). It follows from
[CABLE_TRAVEL.md](CABLE_TRAVEL.md). Nothing here is decided: the three crossing choices are with Joey, and each is to be
proven on a rig ([CABLE_RIGS.md](CABLE_RIGS.md)).

## If the recommended crossings are chosen

| Crossing | Form | Wire in it | Length inside the crossing | Clamp, fixed side | Clamp, moving side |
|---|---|---|---|---|---|
| Pitch | Wrap on the loop channel's inner wall, with a bight hanging in the void under the frame's step | 2 × 16 AWG + 2 pairs of 28 AWG, side by side | About 450 mm (up to 285 mm wrapped, the rest in the bight) for -50° to +180° | On the frame, at the top of the void | On the drum's flange, at the trunk mouth |
| Roll | Not settled: today's route on the roll axis if the rig passes it, otherwise a spiral in the rear cap | 2 × 16 AWG + 2 pairs of 28 AWG | On-axis: about 60 mm. Spiral: about 300 mm | On the cap (drum side) | On the fork rear |
| Yaw | Spiral in the dish under the RS02, 2 to 2.5 turns | **2 × 18 AWG** (agreed, with a 10 A fuse at the step; Joey decides the gauge after the yaw rig) + 2 pairs of 28 AWG | **About 470 mm** | At the fork's exit | At the hub's cable window (a tie round a boss tube) |

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

## Open, for the wiring owner

- Is 18 AWG acceptable for S3, with the 10 A fuse?
- Where do the drop fuses for the roll and yaw motors go?
- Is silicone acceptable in the crossings if it passes the rigs, or must the jumpers be flex-rated regardless?
