# Left shoulder concept: what it needs from the torso frame

Torso-side interface of the roll drum and fork concept ([CONCEPT.md](CONCEPT.md)), for the torso frame work. The right
shoulder is the mirror image about X = 0.

**Read this first: the numbers below are in the OLD frame's coordinates.** `TORSO.step` (`marengo_torso_asm.STEP`,
exported 2026-11-05) is the old 150-wide cage. The rev A stepped frame is 38 mm wider per side in its upper box, and the
shoulder moves outboard with it. Nothing inside the shoulder changes.

| | Old frame (this page, CONCEPT.md) | Rev A frame |
|---|---|---|
| Cage side face at the shoulder | X 75 | X 113 |
| Pitch output face | X 97 | X 135 |
| Roll and yaw axes | X 170.49 | X 208.49 |
| Cover ring | X 75-98.5 | X 113-136.5 |
| Below the step (Y < 353.62) | side at X 75 | lower box side stays at X 75: 38 mm further from the arm |

**Agreed with the torso frame work (2026-11-11), replacing the back entry of section 2:**

- The back entry does not fit rev A. It clashes with the pitch wing (X 78.4-93, Y 400-450, Z ±69), a rear gusset screw
  head at Y 410-420, the temporary gussets (to Z ±76) and the shell's back and spine pads.
- **The feed enters from below.** The two bundles rise through the void under the step overhang (rev A X 75-113,
  Y 285-353, outside the lower box, inside the shell) into the bottom of the cover at about Y 349. Second choice: over the
  top side rail at Y 495.
- **Cover screws** go into T-nuts in the X 113 outward slots: upper posts (Z ±60, Y about 425), step side rail (Y 363.6)
  and top side rail (Y 485). Nothing on the frame is cut or drilled.
- The cover ring clears rev A: nothing sits outboard of X 113 within r 80 of the pitch axis.
- Still to do: re-check the arm against the rev A frame once its STEP exists. The inward roll contact found on the old
  frame was measured against a side face that is now 38 mm further away below the step.

Frame: X outboard (left), Y up, Z forward, mm. Pitch axis along X through Y 424.86, Z 0.

## 1. Fixed and unchanged

| Item | Value |
|---|---|
| Pitch RS03 and its torso mount | Unchanged. Output face X 97.0. The shoulder bolts to the output with 6 x M4 on PCD 30.4, as today |
| Cage side at the shoulder | X 75. The pitch mount ring fills the side window (Y 373.6-475, Z ±50): 2.3 mm² free |
| Cage top | Y 495 |
| Pitch RS03 connector bays | X 40.4-55, inside the cage. The pitch motor's own leads never cross a joint |

## 2. Where the arm cable leaves the torso

The arm trunk cannot leave through the cage side (closed by the pitch mount) or through any motor (no actuator is hollow).
It leaves the cage and enters a fixed printed cover round the pitch motor, loops there for the pitch travel, and goes on
into the moving shoulder.

| Item | Value in the mock-up |
|---|---|
| What comes out, per arm | One flat power bundle 4 x 14.5 and one signal bundle 2.2 x 8, in separate passages |
| Passage sizes | Power 16 x 6, signal 10 x 5, 2 mm rib between, 2.4 mm walls. A round Ø10 cable does not fit |
| Entry point of the feed duct | X 50, Y 430.9, Z -79: against the cage's back face, 6 mm above the pitch axis |
| Feed duct run | Along +X from X 50 to X 86.5 at Z -79, then forward (+Z) into the cover's outer wall |
| Feed duct envelope | X 47.6-98.5, Z -73.6 to -84.4, about 25 mm tall round Y 430.9 |

**The entry point is free to move.** The cover is a ring round the pitch axis, so the feed can enter anywhere on its rim:
from the back (as drawn), the top (above the top rail), the front or below. What suits the trunk inside the torso decides
it. The frame must provide one opening or clear run for the two bundles from the trunk to that point, on each side.

## 3. Space the shoulder takes at the torso

| Volume | Extent | Moves? |
|---|---|---|
| Pitch loop cover (fixed to the torso) | Ring r 55-75.9 round the pitch axis, X 75-98.5. That is Y 349-501, Z ±76 | No |
| Pitch flange on the shoulder | Disc r 77.5 at X 100.5-102.3 (Y 347-502, Z ±77.5) | Turns with pitch |
| Shoulder body | Outboard of X 104. At neutral: Y 288-501, Z -56.7 to +51 | Swings round the pitch axis |
| Rear reach | 30.7 mm behind the roll motor's rear face (today 11.6) | With the body |

- The cover and flange rise about 6-7 mm above the cage top (Y 495), outboard of X 75.
- Keep everything on the frame outboard of X 75 (gusset edges, brake resistors, brackets, screw heads) outside r 80 round
  the pitch axis, between Y 345 and Y 505.
- Outboard of X 102.5 the shoulder and arm sweep a full disc round the pitch axis. Nothing fixed may stand there.

## 4. Mounting the cover: not designed yet

The cover's back wall sits on the cage side at X 75 (annulus r 56-75.9). The mock-up does not fix it to anything. It needs
three or four screw points near that annulus: T-nuts in the 2020 rails, or tapped holes in the pitch mount. The cover
weighs 89 g and carries only cable, no arm load.

## 5. Open on the shoulder side

- Flex life of the bundles in the pitch loop over 270 deg of pitch travel is not checked.
- The torso shell, head and other arm are not in the model.
