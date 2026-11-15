# Torso frame (stepped two-box frame), reference model

`torso_frame.step` is a box-level model of the torso frame now being built: the stepped 2020 frame with the 226 mm
upper box. It is made by [parts_to_step.py](../scripts/torso/parts_to_step.py) from `torso_frame_parts.json`, a copy of
the frame generator's parts list (marengo `hardware/designs/torso-frame/generator/parts.json` at
`77bbf495f4d350fad37cab98914421d57dc7eb99`). Use it for clearance checks. It is not native CAD.

## Coordinates (mm)

X lateral (+X is the robot's left), Y up, Z forward. X = 0 and Z = 0 are the centre planes; the frame bottom is Y 155.

| Feature | Value |
|---|---|
| Lower box | X ±75 outside, Y 155 to 353.62, Z ±70 |
| Shared step rails | Y 353.62 to 373.62 |
| Upper box | X ±113 outside, Y 373.62 to 495, Z ±70 |
| Upper posts | X 93 to 113, Z ±50 to ±70 |
| Step side rail, top side rail | X 93 to 113; Y 353.62 to 373.62 and 475 to 495 |
| Shoulder pitch axis | Y 424.86, Z 0, along X |
| Pitch motor (RS03) | X 92 to 132.5, r 49.5; output face X 135 |

Rev A is the older 150 mm cage (`TORSO.step`, 2026-11-05) widened by 38 mm per side: add 38 mm to |X| for anything
measured on the old side face (X 75 becomes X 113).

## What is in it

Each part is one named solid, `<group>__<id>`, grouped by `group`. The groups are extrusion, gusset, bracket, fastener,
actuator, electronics, harness reserves, shell hardpoints, shell parts (spine pads, shoulder collars), waist and proposed
compute. Left out: the third compute board (no home yet) and the pelvis draft.

## Superseded entries

Two shell parts in this model no longer match the design. The shell's shoulder opening grew from r 60 to r 80 round the
pitch axis (shoulder study, `hardware/shoulder/study-20261111/shell-opening/OPTIONS.md`):

- `shellpart__collar_±1`, the r 60 collar at X 135 to 137, is gone.
- `shellpart__spine_upper_±1`, the upper spine pads, must now end inboard of |X| 140.

The frame itself is unchanged.

## Simplifications

- 2020 profiles are solid boxes, with no slots.
- Gusset corner radii are left square.
- Electronics, harness runs and fans are envelopes, not models.
- The gussets are the 3 mm aluminium plates (Z ±70 to ±73). The frame is first built with 6 mm PETG stand-ins, which reach
  Z ±76.
