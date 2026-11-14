# Shoulder size audit (2026-11-13)

**Status:** numbers and pictures only. No real part is changed. Measured on today's build meshes
(`cad/_wip/shoulder-pass1/stl`), the placed motors, and the outer shell panels of 2026-11-06.

**Pictures:**
- [size_audit/shoulder_with_shell.png](size_audit/shoulder_with_shell.png): the shoulder and upper arm with the outer body
  shell, solid and see-through.
- [size_audit/SLIM_OPTIONS.png](size_audit/SLIM_OPTIONS.png): today beside three slimmer ideas, as quick envelope models.

> **Correction, 2026-11-14.** The first version of this page said the drum's skin could come in by 2-3 mm over the lugs
> and its sides "from 96.8 toward 70". Both were wrong, and the "tight skin" row of SLIM_OPTIONS.png shows a drum that
> cannot be built (its skin is pulled inside its own lug slots). The rows below are corrected. What stands: the
> comparison with the built shoulder, the depth behind the motor, and the back-of-shoulder savings.

## The motors it wraps

| Motor | Size |
|---|---|
| Roll RS03 | 99.6 × 98.5 across, 56.6 deep; lugs to r 53.0 |
| Yaw RS02 | Ø78.5 × 45.4 |

## What is wrapped round them

| Where | Motor | Shoulder | Extra | What the extra is |
|---|---|---|---|---|
| Depth front to back at the roll joint | 56.6 | **110.6** (Z -60.8 to +49.8) | 54 | 34.8 behind the motor, 19.2 in front |
| Behind the motor | | 34.8 | | Drum rim 2.5; rear cap plate 10.8 (6 of it is the cable channel); gap 1; 6808 bearing 7.0; fork rear cheek 13.5 (6 cable channel, walls, R6 dome) |
| In front of the motor | | 19.2 | | Drum lip with its 8 screws 5.4; 2 mm gap; fork front plate 3 mm (Z 39-42) rising to Z 49 at the hub. The hub's height is a stack: pad for the six M4 and three 4 mm pins 11.7, screw heads, press-in cap |
| Drum, across the roll axis | Lugs to r 53.0 | Skin r 56.1-57.0; up to r 61 on top | 3-4 over the lugs; **1.6 mm of skin over the lug slots and the connector window (r 54.5)**; 4 more on top | The skin is as tight as the motor allows. The extra on top is the swell over the cable trunk and its branch |
| Drum, along the roll axis | 56.6 | 64.5, rim to rim | 8 | 2.5 behind and 5.4 in front, both needed (rear rim, front lip with the 8 screws) |
| The same printed part, at the body | Pitch RS03 Ø99 | 96.8 across (the bell, neck and spokes round the pitch motor) | | Joins the drum to the pitch motor; inside or at the shell's socket |
| Fork, side to side | 99.6 | 110 | 5 a side | Cheek walls |
| Sleeve round the yaw motor | Ø78.5 (r 39.30) | Bore r 39.75, outside r 41.35-43.0 | 0.45 gap, 1.6-3.3 wall | As tight as it can be. Higher up (Y 350-370) the fork is 94 wide and 110 deep: that is the seat ring on the RS02 (r 45), the socket tap (r 49), the plug channel, the bolted joint to the fork rear, and the fork rear's leg with the cable channel behind |
| Ring at the body | Drum Ø118 | Cover Ø152, flange ring Ø155 | 18 all round | The pitch cable channel (r 57 to 73.5) and its cover. It sits in the shell's socket |

**Overall:** 120 mm outboard of the body's side (shell at X 107-109, the fork's outer face at X 227.5); 110.6 deep; 198
high from the drum's top to the hub's underside.

**Mass:** about 630 g: drum 238, fork front 141, hub 80 (D3c7), rear cap 75, fork rear 61, flange ring 29, plugs 6. The
cable cover on the torso is another 102 g.

## Against the shoulder as built today (the bracket design, same motors)

| | Built today | New |
|---|---|---|
| Outboard reach (X) | 97 to 228 | 97 to 227.5 |
| Height | 194 | 198 |
| Depth | 109.5 (Z -37.5 to +72) | 110.6 (Z -60.8 to +49.8) |

- **The new shoulder is not larger** in reach, height or depth. The reach is set by the two motors in line.
- **What changed:** the brackets were open and thin; the drum and fork are closed, rounded volumes. And the depth has
  moved backward by about 23 mm.
- No human-scale shoulder figure exists in the repo to compare with.

## The ring at the body

- The disc between the torso and the drum is two parts: the moving flange ring on the drum (r 77.5, 1.8 thick) in front
  of the fixed cable cover (r 75.9 where it passes through the shell).
- With the r 80 opening of option A, the ring's face stands 5 to 8 mm proud of the opening's edge, and is level with, or
  up to 2 mm below, the body's surface just outside the socket. It sits in a shallow dish in the shell.
- Visible gap: 2.5 mm round the flange ring.
- The shell model has not been rebuilt for the r 80 opening; the pictures draw it in.

## Where it can shrink

| # | Idea | Saves | Keeps Joey's decisions | Cost |
|---|---|---|---|---|
| 1 | **Fork front hub lower,** from +49 to about +46, with shorter output screws; the pins keep their 8 mm | 3 mm of depth at the hub | Yes | Little. The face away from the hub is already 3 mm thick and held 2 mm off the drum's lip |
| 1b | **Drum's top swell removed** (r 61 back to r 57), only if the roll cable no longer runs over the top of the drum | 4 mm of height at the top | Yes | Follows from the roll cable decision. The drum's sides and bottom cannot come in: 1.6 mm of skin over the lug slots |
| 2 | **Wires out from behind the motor:** the cap's and the fork cheek's cable channels (12 of the 34.8 mm) moved to the side of the bearing | Up to 12 mm of depth | Yes | Depends on the roll cable decision, which the roll rig informs. New rear cap and fork rear |
| 3 | ~~Thinner sleeve round the yaw motor~~ | None | | **Withdrawn:** the sleeve wall is 1.6-3.3 mm round a 0.45 mm gap |
| 4 | **Smaller ring at the body** | Up to 18 mm of radius | Yes | Follows from the pitch cable choice: only if pitch travel is limited to what a smaller loop takes. Mostly inside the shell |
| 5 | **No rear support** (no 6808, no rear fork leg; the same as a one-sided fork) | 21 mm of depth | **No:** breaks "bearings on moving surfaces" | The RS03's own output bearing would take all the tilting moment, up to 28.6 N·m (C_LOAD_SHARE.md), and its rating is not published. Not recommended |
| 6 | A thinner rear bearing | 1-2 mm | Yes | The cable bore sets the bearing's size. Not worth it |
| 7 | Clocking the motors | Little | Yes | The RS03's lugs are every 45° |

## What the pictures show

`SLIM_OPTIONS.png` (re-rendered 2026-11-14) puts today beside "short back" (item 2) and "no rear support" (item 5). Depth
at the roll joint: 111, 99 and 89 mm. The earlier "tight skin" row is withdrawn.

- **The rows are hard to tell apart from the front.** The change is at the back, in the side and top views.
- **Nearly every skin is already within 2-4 mm of a motor or a working face.** The millimetres that exist are the 12 mm of
  cable channel behind the motor and 3 mm at the fork front's hub.
- **The visible lever is the fork front's face,** which today covers the roll motor's whole front: see
  `IN_BETWEEN_OPTIONS.png` (in work).
- A real reduction in how far the shoulder stands off the body would need the motors themselves arranged differently,
  which is outside "drum and fork".
- No mass saving is claimed: the earlier "about 60 g" had no basis.

The variants are today's meshes with their skins pulled in by simple rules (`render_slim_options.py`); they are not CAD
and have not been checked for clearance or strength.
