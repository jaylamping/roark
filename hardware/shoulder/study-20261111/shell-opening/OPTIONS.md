# Left shoulder: getting the arm cable past the body shell (option A or B)

Quick mock-up for a decision, 2026-11-11. Rev A frame coordinates (X lateral, +X left, Y up, Z forward, mm). Pitch axis
along X through Y 424.86, Z 0.

- **Shoulder parts:** the first-pass SolidWorks solids (`cad/shoulder/left/`, built in the old frame, moved +38 X).
- **References:** the vendor RS02/RS03, the pitch RS03 as placed, the frozen upper arm, and from
  `J:\code\_transfer\shoulder\`: `torso_frame.step` (SHA-256 9e3ff578…b0b7) and `shell_inner.step` (6a975342…7f7b335).
- **Simplification:** the shell is drawn as its inner surface only (no 2.4 mm wall), cut at the opening radius.
- **Script:** [scripts/options.py](scripts/options.py).

Rough geometry; the numbers below are the point.

| | A: bigger shell opening | B: keep the 120 mm opening |
|---|---|---|
| Look, shell opaque | [A1_look.png](A1_look.png) | [B1_look.png](B1_look.png) |
| Shell translucent, power red, signal blue | [A2_cables.png](A2_cables.png) | [B2_cables.png](B2_cables.png) |
| Section Y 424.86, seen from above | [A3_section.png](A3_section.png) | [B3_section.png](B3_section.png) |

Side by side: [AB_look.png](AB_look.png), [AB_section.png](AB_section.png).

## Shell at the shoulder (measured on shell_inner.step)

- **Inner side at the shoulder band** (Y 360-460, |Z| ≤ 40): X 133.1-133.3. With the 3 mm skin, the outer face is about X 136.
- **Inner surface X at each radius round the pitch axis:**

  | r | X range |
  |---|---|
  | 60 | 132.6-133.1 |
  | 75.9 | 127.2-133.7 |
  | 79.5 | 125.4-135.2 |

  The skin curves inboard toward the top and bottom.
- **The shell model has no opening cut.** Its collar is in `torso_frame.step` as `shellpart__collar_1`: r 60 at X 135-137,
  with 7 screws `fastener__c1_*` at r about 45, X 128-142.

## Option A: shell opening enlarged to r 80

**Shoulder:** as designed in the first CAD pass.

- Fixed cover ring r 55-75.9, X 113-140.5. The outer wall now runs to 2 mm short of the flange ring; the concept had it end
  at X 136.5.
- Bottom feed from under the step: a riser at X 101.6-112.4, Y 300-343, run under the cover, up into its bottom at
  about Y 349, Z -16.4 to +16.4.
- Moving flange ring r 42-77.5, X 142.5-144.3 (1.8 mm, its own part).

**Shell:**

- Opening at least r 77.9 to pass the fixed cover (r 75.9 + 2). The flange ring is outboard of the skin, so it overlaps the
  opening edge as a labyrinth.
- With cover + flange + 2: r 79.5.
- The shell's own collar (r 60, X 135-137) and its 7 screws go. **The screw heads at r 45 sit where the drum's spokes turn.**

**Cover against the skin:** 80 % of the cover ring's surface is inside the shell. The outer wall passes through the skin
and stands 4-7 mm proud of it (X 136 to 140.5).

**Clash found:** the upper spine pad of the shell (`shellpart__spine_upper_1`: X 68-147, Z -124 to -77, Y 368-481):

- 1.1 mm from the fixed cover (r 75.9 reaches Z -75.9)
- overlaps the moving flange ring by about 0.5 mm at Z -77.5, so it rubs.

The pad must end inboard of X 140, or the ring's radius drop to about 75 at the back. That second fix needs the cover
labyrinth reworked.

**Cable form:** two flat bundles as designed (power 16 x 6 passage for 4 x 14.5; signal 10 x 5 for 2.2 x 8). They loop
round the pitch housing in the r 57.4-73.5 channel for 270 deg of pitch.

**Mass:**

| Part | g (solid PETG) | Notes |
|---|---|---|
| Cover, torso side | 102.5 | |
| Flange ring, moving | 29.2 | |
| Drum with neck and spokes, moving | 189.0 | |

**Unverified:** bundle flex life over 270 deg in the channel; the shell edge detail at r 80.

## Option B: opening r 60 kept, clock-spring cassette in front of the pitch output

**Does it fit as asked? No, not without moving the shoulder.**

- **One deck fails.** A flat spiral between hub r 27 and case r 56.8 with all three bands stacked in one 8 mm deck
  (4 + 4 + 2.2 = 10.2 mm per turn, 10.8 with slack) gives at most **164 deg** of travel, in theory. 270 deg is needed.
- **Three decks work, just.** Each band needs its own deck (power 4 x 7, power 4 x 7, signal 2.2 x 8).
  - Each power deck gives at most **394 deg** in theory with an 840 mm band (3.8 turns on the hub). About 275 deg is
    usable at 70 %, which is marginal for 270 deg.
  - The signal deck (2.2 thick) gives about 650 deg.
- **The decks need axial room.** Three decks with 0.6 mm side clearance, two 1 mm separators, a 1.2 mm floor and a 1.2 mm
  lid make a case at X 135-165.
  - Moving parts must stay 2 mm off the lid: from X 167.
  - Today the drum's inboard face is at X 151.5, and the cap ears at X 149.3 sit inside the cassette's shadow.
- **So the shoulder moves +16 mm outboard** (the drum face to X 167.5).
  - The cap ears must also move out of r < 58 round the pitch axis. As placed, they would need +17.7.
  - With +16 mm, the roll and yaw axes go to X 224.5. Pitch output to arm centreline grows 73.5 → 89.5 mm (+22 % pitch
    moment). The robot is 32 mm wider across the shoulders.
- **Bend radius.** A 4 mm thick power band wound at r 27 bends at 6.75 x its thickness. Its flex life is not known.

**What changes:**

- **Shell:** none (opening r 60, collar at X 135-137 kept). The collar screws at r 45 must clear the cassette's fixed floor:
  they can hold it.
- **Shoulder:**
  - Fixed cassette case (floor, outer wall r 56.8-58, two separators, lid) on the pitch housing rim.
  - Moving hub tube r 22-27 round the 6 x M4 PCD 30.4 pad, extended to X 167, with a web to the drum.
  - The P1 neck, spokes and flange ring go. The trunk starts at the hub.
  - Cover ring gone.
- **Feed to the fixed case:** up the void under the step, outboard under the housing inside the shell, then along the
  housing bottom in the 7 mm annulus between housing r 53 and opening r 60. Walls 1.2 mm leave about 4.6 mm, enough for
  4 mm bands side by side round the circumference.
- **Cable form:**
  - Power is split into two flat bands of 4 x 7 standing on edge, with signal 2.2 x 8.
  - Band lengths: about 840 mm per power band, about 600 mm signal.
  - The bands must be made as flat cables and anchored at the case wall and at the hub.

**Mass (mock geometry, solid PETG):**

| Part | Option B (g) | Option A (g) |
|---|---|---|
| Cassette case, fixed | 62 | |
| Feed duct, fixed | about 10 as thin walls (the mock box is 26) | |
| Hub tube, moving | 35 | |
| Web, moving | 29 | |
| Drum without neck and spokes, moving | 140.6 | 189.0 |
| Flange ring, moving | | 29.2 |
| **Moving** | **about 205** | **218** |
| **Fixed** | **about 72** | **102.5** |

B is about 25-45 g lighter in total, but every gram of the arm sits 16 mm further out.

**Unverified:**

- the cassette's real travel and friction with three 3-4 turn spirals
- band anchoring and the U-turn at each end
- flex life at r 27
- whether flat 4 x 7 power bands exist in the needed copper section
- the 16 mm outboard move against the rev A frame, the shell and the other arm's reach
- assembly through a 120 mm opening: the case is 116 mm across, so it must go in before the shell, or the shell goes on
  over it.

## Summary

- **A:** keeps the designed shoulder and arm position. It needs a shell opening of r 78-80 (from r 60) and a trimmed rear
  spine pad, and the cover shows 4-7 mm proud of the skin.
- **B:** keeps the shell. It needs a 3-deck cassette, split flat power bands and a +16 mm outboard shoulder, with marginal
  travel (about 275 deg usable for 270 needed).
