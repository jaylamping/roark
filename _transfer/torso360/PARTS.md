# Torso 360 render: what is in the picture

Rendered 2026-11-13 on holly-pc with `C:\joe\_render\torso360\{scene,build,render}.py` (vtk offscreen, trimesh, cadquery,
manifold3d). Picture only: no CAD was changed, nothing committed or pushed, SolidWorks was not started. All source files
were read in place.

Coordinates are the rev A torso frame: X lateral (+X = robot's left), Y up, Z forward, mm. The shoulder pitch axis is
along X through Y 424.86, Z 0. Pose: neutral, all joints zero, arm hanging.

## Files

| File | What |
| --- | --- |
| `torso360.mp4` | 360° turntable, 1920x1080, 150 frames, 15 fps, 10 s, H.264 yuv420p |
| `torso360.gif` | Same orbit, 800 px wide, 75 frames |
| `torso360_xray.mp4` | Same orbit with the shell and pads at 35 % opacity, 120 frames, 8 s |
| `torso360_xray.png` | One still of the 35 % shell, front-left |
| `torso360_sheet.png` | Contact sheet, 8 views at 45° steps, labelled, 3200x2000 |

Camera: orbits the vertical axis through X 0, Z 0, aimed at Y 272, 13° above level. 0° = seen from the front; 90° = seen
from the robot's left.

## Parts drawn

| Part | Source file (on holly-pc) | Branch / commit or file date |
| --- | --- | --- |
| Rev A 2020 frame: extrusions, gussets, brackets, fasteners, hardpoints, right pitch motor envelope, pitch brackets, waist adapter and waist RS03 envelope, electronics and proposed-compute envelopes | `C:\joe\code\_transfer\shoulder\torso_frame.step` (byte-identical to `cad/reference/torso_frame.step`) | `claude/project-thread-0hwikl` (PR #54), 9aa849e; file 2026-11-11 |
| Body shell Rev B: 8 panels (upper/lower, front/back, L/R), doors D1 and D2, hatches D3 L/R, 2 intake grilles, 16 hardpoint brackets (30 pieces) | `C:\joe\code\marengo\cad\exports\shell\marengo_shell_*.STL` (copy of Joey-PC `J:\code\marengo\cad\exports\shell`, hash-checked 2026-11-11) | marengo, not a git checkout here; files dated 2026-11-06 |
| TPU spine pads (4) | Box envelopes from `torso_frame_parts.json` (`spine_upper_±1`, `spine_lower_±1`) | PR #54, 9aa849e |
| Shoulder: roll drum, flange ring, rear cap, fork front, fork rear, hub, cable cover, port cap, access plugs | `roark-wt\shoulder-study\cad\_wip\shoulder-pass1\stl\*.stl` | `claude/project-thread-90ef87` (PR #47) at f8fba7c; STL files dated 2026-11-11 to 2026-11-13 |
| ... of those, fork front, access plugs and hub are byte-identical to | `cad\exports\shoulder\shoulder_fork_front_left.STL`, `shoulder_fork_access_plugs_left.STL`, `shoulder_hub_left.STL` | Fork front and plugs 2026-11-13 08:22. Hub: working-tree file of 2026-11-13 10:19, **modified and not committed** relative to f8fba7c |
| RS03 pitch motor (left) | `cad\reference\shoulder\torso_pitch_rs03_left.step` | PR #47, 92c08f2 |
| RS03 roll motor | `cad\vendor\robstride\vendor_robstride_rs03.stp`, placed by `build_asm.T_ROLL_RS03` | PR #47, 57d0572 |
| RS02 yaw motor | `cad\vendor\robstride\vendor_robstride_rs02.step`, placed by `build_asm.T_RS02` | PR #47, 57d0572 |
| Upper arm, organic concept A, **revision r1g** (front half, back half) and the RS02 ring | `roark-wt\left-arm-organic\cad\_wip\r1d_r1g_print\exports\upper_arm_organic_{front,back,rs02_ring}_left.STL` | Local only (gitignored `_wip`), halves dated 2026-11-12 23:58 / 2026-11-13 00:00; branch `left-arm-organic-r1` at 50a2a07 |
| RS02 elbow motor | `roark-wt\left-arm-organic\cad\_wip\organic-arm\cad\rs02_placed.stl` | Local only, 2026-11-13 14:14 |
| Forearm and wrist: inboard/outboard shells, lower front/back shells, cheeks, caps, hub, drive plate, drive shaft, stub ring, stub nut, output pin, wrist plate (15 files) | `roark-wt\left-arm-organic\cad\exports\forearm\forearm_organic_*.STL` | `left-arm-organic-r1`, exports last committed 210b8a6 (2026-11-10) |

Placement: the frame and shell are in rev A coordinates as exported (shell STLs are in the robot frame, mapped
X = y, Y = z - 810, Z = x as in `shell_inner.md`). Shoulder, motors and arm are modelled in the old-frame coordinates
and were moved +38 mm in X (`build_asm.FRAME_SHIFT`), the same step the shoulder scripts use.

## Faked or simplified for the picture

- **Shoulder opening, option A.** The r 80 opening round the pitch axis is not in the shell CAD yet. Here it is a mesh
  boolean (manifold3d) on the 8 panel STLs: a r 80 cylinder along the pitch axis, |X| 100 to 175, cut on **both** sides.
  The opening edge is the raw cut through the socket cone, with no edge finish.
- **Collar and its 8 screws removed.** `marengo_shell_collar.STL` and the frame model's `shellpart__collar_±1` are not
  drawn. The collar screws are not separate solids in any file used, so nothing else had to be taken out.
- **Spine pad trims.** The pads exist only as box envelopes in the frame parts list (the panel STLs carry no pads). They
  are drawn as dark boxes, with the upper pads ended at |X| 140 (was 147) and the lower pads at |X| 126 (was 129), on both
  sides. They are plain boxes that run into the shell back, not the real pad shape or its standoffs.
- **Frame is box-level.** 2020 profiles are solid boxes without slots; electronics, compute, fans, the right pitch motor
  and the waist RS03 are envelopes (as in `torso_frame.md`). The frame model's harness reserves are left out.
- **Right side.** No right shoulder or arm exists: the right socket is open (also cut to r 80) and shows the frame
  model's pitch motor envelope.
- **Colours and materials** are render choices (white PETG shell and arm, grey frame, dark motors), not a print plan.
  The shell screw cap (`marengo_shell_screw_cap.STL`, a single part at its own origin) is not instanced.

## Missing or not yet merged

- **RS00 forearm motor is not drawn.** Only a native `robstride_rs00_vendor.SLDPRT` is on this PC (marengo
  `cad\vendor\incoming`); no STEP/STL and no placed copy. It sits inside the forearm shell and would not show with the
  arm closed, so SolidWorks was not started for it.
- **6808 shoulder bearing** is not drawn (hidden inside the drum and cap).
- **Upper arm r1h** exists locally (`cad\_wip\r1d_r1h_print\exports`, 2026-11-13 16:58) and is newer than r1g, but that
  thread was still running solves on it when this was rendered. r1g is the newest revision with sliced print files
  (`cad\prints\upper-arm\*_r1g.3mf`). Only r1c is committed under `cad\exports\upper-arm`.
- **Shell:** the Rev B panels are still marengo files; they are not in roark `cad/shell` yet. The option A opening, the
  collar removal and both pad trims are still owed in the shell CAD (`hardware/shell/README.md`, "Changes owed"). The
  lower pad trim is listed there as proposed, not yet chosen.
- **Not merged to main:** shoulder (PR #47), frame and shell reference (PR #54), arm (`left-arm-organic-r1`).
- Hand, head, right arm, pelvis and legs are not part of this picture.

## Checks made on the frames

- The arm sits on the left (+X) pitch face: the drum starts at X 135.0, the pitch motor's output face, and the pitch
  axis of the shoulder parts is at Y 424.86.
- The shell encloses the frame; only the waist RS03 envelope shows below it (Y 92 to 149), as intended.
- Nothing floats or is mirrored; the forearm cheeks sit round the elbow RS02 and the upper arm's lower end.
- Looked at front, left, back and the 8-view sheet.
