# A 150 mm shell opening at the shoulder: what it does to the pitch cable crossing (2026-11-14)

**Status:** a study with numbers. No part is changed. Joey asked for the opening at 150 mm (r 75) instead of 160; 140
(r 70) is given for reference. Numbers from `cad/scripts/shoulder/pitch_opening_study.py` and `dims.py`.

## Short answer

- **The 150 mm opening leaves an 11.1 mm cable channel** (16.1 today). Everything else in the stack keeps its gaps.
- **The spiral alone does not give a useful pitch travel at 150 mm:** about 59° at best with 2 × 16 AWG, about 73° with
  2 × 18 AWG (today's opening: 118° and 148°). These are the ideal limits; expect about three quarters on the rig.
- **Wrap and bight is not affected by the opening:** it needs one layer on the inner wall (4.5 mm of channel). Its travel
  is set by the room under the frame's step: **about 140°** (loop radius 30), up to about 160° with a tighter loop.
- **Both together at 150 mm: about 185° to 200°** (the spiral's 44-59° on top of the bight's 140°). Two mechanisms.
- **So 150 mm costs the simple option.** Today's opening gives about 115° with a plain spiral and two clamps; at 150 the
  same travel needs the bight, its guide and a pull-down.
- A second pitch rig tray and lid with the 11.1 mm channel are ready to print, to run tests E and F beside today's.

> **Correction to [PITCH_BIGHT.md](PITCH_BIGHT.md).** Its depth table left the loop's own radius out of the 230° and
> 270° rows. With it in, wrap and bight alone stores 144 mm in the 117 mm of room: **140°, not 230°.** That page is
> corrected. The earlier "230° is marginal" was wrong.

## The stack-up

Outward from the pitch axis. Gaps and walls as today; only the channel changes.

| | Today (r 80) | 150 mm (r 75) | 140 mm (r 70), reference |
|---|---|---|---|
| Cover inner wall | r 55.0-57.4 | same | same |
| **Loop channel** | r 57.4-73.5: **16.1** | r 57.4-68.5: **11.1** | r 57.4-63.5: **6.1** |
| Cover outer wall (2.4) | r 73.5-75.9 | r 68.5-70.9 | r 63.5-65.9 |
| Flange ring's rim (1.6 proud of the wall) | r 77.5 | r 72.5 | r 67.5 |
| Gap to the opening (2.5 at the ring, 4.1 at the cover) | r 80 | r 75 | r 70 |

Opening radius = 63.9 + channel width. This agrees with `dims.py` (`COVER`, `RING`) and with the render notes.

## Pitch travel

The band is one wire thick: 3.0 mm with 2 × 16 AWG and two pairs, 2.4 mm with 2 × 18 AWG and two pairs.

| Arrangement | Wires | Today (r 80) | **150 mm (r 75)** | 140 mm (r 70) |
|---|---|---|---|---|
| Spiral, ideal limit | 2 × 16 AWG + pairs | 118° (2.9 turns) | **59°** (1.9 turns) | 18° |
| Spiral, with slack between turns (three quarters, assumed) | 2 × 16 AWG + pairs | 89° | **44°** | 14° |
| Spiral, ideal limit | 2 × 18 AWG + pairs | 148° (3.6 turns) | **73°** (2.4 turns) | 23° |
| Spiral, with slack (assumed) | 2 × 18 AWG + pairs | 111° | **55°** | 17° |
| Wrap and bight, loop radius 30, 30 mm spare | either | 140° | **140°** | 140° |
| Wrap and bight, loop radius 24 / 18 | either | 152° / 163° | **152° / 163°** | the same |
| Spiral and bight together (loop radius 30) | 2 × 16 AWG + pairs | about 230-260° | **about 185-200°** | about 155° |

- The spiral model: the same length wound tight on the inner wall and lying out against the outer wall; the travel is
  the difference in turns. It is the model behind "2 to 2.3 turns, about 115°" in CABLE_TRAVEL.md. The slack factor is
  an assumption until the rig is run.
- Wrap and bight: wrapped length changes by 1.03 mm per degree. Loop depth = half the stored length + the loop's
  radius + half the spare. Room: 117 mm (Y 295 down to hardpoint H6 at Y 178).
- Thinner power wires help the spiral (more turns in the same channel) and do nothing for the bight, except that a
  thinner cable takes a tighter loop.

**The smallest opening at which the spiral alone still works:**

| Spiral travel | 2 × 16 AWG + pairs | 2 × 18 AWG + pairs |
|---|---|---|
| 115°, ideal / with slack | Ø160 / Ø165 | Ø156 / Ø161 |
| 230°, ideal / with slack | Ø174 / Ø182 | Ø169 / Ø176 |

So today's Ø160 is already the smallest opening for a 115° spiral with 16 AWG, with no margin for slack.

## What the bight needs (the same at any opening)

- **A pull-down.** A cable cannot be pushed: when the wrap shortens, something draws the freed length down.
  - A weight of 20-30 g on the loop: works with the torso upright only.
  - A spring retractor (badge-reel type, about 0.5-1 N, 600 mm of cord) on hardpoint H6: works in any attitude. About
    15 g. Not a printed part.
  - Elastic alone does not work in the height available.
- **The pull needed is not known.** Friction round the wall multiplies it by about 2 at 140° of wrap with a friction
  coefficient of 0.3, and by about 3.4 at 0.5. Test F on the rig measures it.
- **A guide finger** at the channel's bottom and **the keep-out window** in the torso (PITCH_BIGHT.md).

## What else moves if the cover shrinks to r 70.9

| Item | Today | At 150 mm | Effect |
|---|---|---|---|
| Ring screws and spokes | r 46, spokes to r 50 | unchanged | None |
| Trunk on the drum | centre r 58, about r 52.6-63.4 | unchanged | Fits inside the outer wall (r 68.5) with 5.1 mm |
| Trunk mouth in the flange ring | about r 63.5-67.5 | about r 61-65, mid channel | The ring's mouth and its tie pad move in 2.5 mm |
| Drum bell | r 60 at most | unchanged | 12.5 mm inside the ring's rim (17.5 today) |
| Rolled rim B on the ring | r 68.3-77.5 | r 63.3-72.5 | Still 3.3 mm outside the bell: no shortening needed (at Ø140 it would be) |
| Cable feed risers into the channel's bottom | reach Y 351 | 5 mm longer | Small change to the cover's feed |
| Cover tabs to the frame | placeholders | follow the cover | Not fixed yet either way |
| Shell socket floor | flat at X 97.5 (old frame) from r 53.5 to r 79 | the r 75 cut lands on the flat floor | The opening's edge becomes a plain flat ring, 4 mm of floor left outside it. Easier to finish than today's cut through the cone wall |
| Labyrinth to the shell | ring 2.5 inside the opening, 6.6 or more outboard of the edge | the same gaps | Kept |
| Fork front to ring at the -11° stop | about 2.1 mm at r 61.5 | not swept at this size | The ring's rim moves in toward that point; it needs a sweep before the ring is redrawn |

## The rig parts for it

`fixtures_cable_rig_pitch_tray_r75` and `fixtures_cable_rig_pitch_lid_r75`: the pitch rig's tray with the outer wall at
r 68.5 and a lid with the trunk mouth at mid channel. Same tests E and F as [CABLE_RIGS.md](CABLE_RIGS.md), on the narrow
channel.
