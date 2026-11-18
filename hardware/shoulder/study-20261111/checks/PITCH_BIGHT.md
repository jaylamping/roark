# Pitch crossing as a wrap and bight: the pieces, the room, and a keep-out note (2026-11-13)

Follows [CABLE_TRAVEL.md](CABLE_TRAVEL.md), pitch section. Checked against the torso frame model
(`torso_frame.step`) and the shell's inner surface (`shell_inner.step`). Old-frame X throughout (rev A = +38). No real
part is changed.

## Short answer

> **Corrected 2026-11-14.** The depth table below left the loop's own radius out of the 230° and 270° rows. With it in,
> the bight alone gives about 140°, not 230°. The rows and this summary are corrected; see also
> [PITCH_OPENING_150.md](PITCH_OPENING_150.md).

- **It is tighter than the first sketch showed.** The loop cannot hang straight down from the channel: the shell's side
  wall closes in below it, and the cable feed duct stands in the same void.
- **The bight alone gives about 140°** in the 117 mm of room (loop radius 30, 30 mm spare); about 160° with a tighter
  loop. **230° and 270° do not fit** as a bight alone.
- **Spiral and bight together give about 230° to 260°** with today's channel.
- **A pull-down by elastic alone does not work in the height available.** A weight works only with the robot upright. A
  small spring retractor would work in any attitude.
- The spiral alone (about 115°) needs none of this.

## The room, as measured

| What | Where (old-frame X; Y; Z) | Effect |
|---|---|---|
| Loop channel's lowest point | X 77-98; Y 351; Z 0 | Where the cable leaves the channel |
| Shell inner side wall | X 104 at Y 330-350; 101 at Y 310; 92 at Y 290; 81 at Y 270; 73-76 from Y 260 down | A loop hanging straight down from X 88 meets the wall after 55 mm |
| Lower frame's side | X 37 (posts at Z ±50-70; open between them to the pack) | Inboard limit of the void |
| **The void for the loop** | X 37 to 73; Y 175 to 350; Z ±70 between the gussets | 36 mm deep in X |
| Cable feed duct (power and signal risers) | X 63.6-74.4; Y 300-343; Z ±16.4; then outboard under the cover at Y 332-343 to X 88 | Takes the outer 11 mm of the void above Y 300, and the channel's bottom centre |
| Step side rail | X 55-75; Y 353.6-373.6; Z ±50 | The cable must pass under it |
| Hardpoints H5 | X 37-49; Y 245-265; Z ±45-75 | Loop must stay within Z ±40 there |
| **Hardpoints H6** | X 37-49; Y 155-175; Z ±20-50 | **Floor of the void for the loop: Y 178** |
| Power board, pack, Jetson, Pi | all inboard of X 21 | Not in the void |

## The pieces

| Piece | Where | What it is |
|---|---|---|
| Clamp on the drum | On the flange ring, at the trunk mouth (r 65) | Two tie slots beside the mouth. The flange ring is 1.8 mm thick, so the tie bears on a 3 mm pad added under it |
| Guide finger | At the channel's bottom, **off centre at Z +24** (22° round from the bottom), R 12 or more, part of the cover | The cable leaves the inner wall over it. Off centre because the feed comes up at the centre |
| Jog inboard | From the channel (X 88) to the void (X 50), passing under the step rail beside the feed duct | An S of R 30 needs 56 mm of drop for the 38 mm sideways: Y 351 down to 295. A printed chute on the cover's underside guides it |
| Loop (bight) | X 44-56, Z ±30, from Y 295 down | 60 mm wide (R 30), 12 mm thick |
| Fixed clamp | On the step side rail's underside slot, at Z -30 | A printed saddle on one M5 T-nut. The cover's placeholder tab at (Y 363.6, Z 30) uses the same slot, 60 mm away. Whether a spare T-nut is there is the torso thread's to say |
| Pull-down | See below | |

## Depth against travel

- Wrapped length changes by 1.03 mm per degree (r 58.9).
- Loop depth needed: half the change, plus the loop's radius (30), plus half the spare length.

| Travel taken by the bight | Change | Depth needed (spare 30 / 60 mm) | Room (Y 295 to 178) | |
|---|---|---|---|---|
| 115° (the spiral takes another 115°: 230° together) | 118 mm | 104 / 119 mm | 117 mm | **Fits with the smaller spare** |
| **140°** | 144 mm | 117 / 132 mm | 117 mm | **The most the room takes** |
| 230° (-50° to +180°) | 236 mm | 163 / 178 mm | 117 mm | **No** |
| 270° | 278 mm | 184 / 199 mm | 117 mm | **No** |

- A loop of radius 24 or 18 instead of 30 stores 12 or 24 mm more: 152° or 163°. Whether the wires take that radius
  for the life of the robot is not known.
- More room would come from moving hardpoint H6 (the torso thread's), or from starting the loop higher, which needs the
  feed duct moved out of the void's top. For 230° as a bight alone the room would have to be 163 mm: 46 mm more.

## Pull-down

- **Travel of the loop's bottom:** up to 72 mm (half of 144 mm).
- **Elastic alone:** its anchor has to be below the loop's lowest point (Y 178), and the frame ends at Y 155. That leaves
  about 20 mm of elastic to stretch 72 mm. **It does not work** without a turn round a pulley and a long run along the
  frame.
- **Weight (20-30 g on the loop):** simplest. Works with the torso upright; not lying down or inverted, where the loop
  goes slack and can leave the channel.
- **Spring retractor** (a badge-reel mechanism, about 0.5-1 N, 600 mm of cord) on hardpoint H6, cord to a ring on the
  loop: constant pull in any attitude. About 15 g. Not a printed part.
- **Force needed:** unknown. Friction round the channel wall multiplies it by about 2 at 140° of wrap if the friction
  coefficient is 0.3, by about 3.4 if it is 0.5. The pitch rig (test F) measures it.

## Keep-out note for the torso frame and body shell threads

If the pitch crossing is built as a wrap and bight, the left side needs this kept clear (mirror it for the right side):

| Keep clear | Old-frame X | Rev A X | Y | Z |
|---|---|---|---|---|
| Loop sweep | 40 to 60 | 78 to 98 | 175 to 300 | -40 to +40 |
| Jog from the channel to the loop | 44 to 98 | 82 to 136 | 295 to 352 | +8 to +40 |
| Fixed clamp on the step rail's underside | 55 to 75 | 93 to 113 | 340 to 354 | -45 to -15 |
| Pull-down (weight or retractor) below the loop | 40 to 60 | 78 to 98 | 155 to 178 | -15 to +15 |

- **Shell:** the inner side wall must not come further in than it is now between Y 175 and 300 (X 73-76 old frame).
- **Frame:** nothing new on the lower box's outer face between the posts in that window. Hardpoint H6 (Y 155-175) sets
  the loop's floor; moving it down 46 mm would be needed for 230° as a bight alone.
- **Cable feed:** stays at Z ±16.4 and X 63.6-74.4; the loop passes inboard of it and the jog passes beside it at
  Z +8 to +40.
- None of this is needed if pitch is limited to about 115° and the crossing is a spiral in the channel.
