# Body shell

The printed torso shell: panels, doors, grilles, hatches and hardpoint brackets.

**Where the design is today.** The design and its notes are in marengo, read-only from here:
[hardware/designs/body-shell/](https://github.com/jaylamping/marengo/tree/main/hardware/designs/body-shell), with the manufacturing plan in
[manufacturing/README.md](https://github.com/jaylamping/marengo/blob/main/hardware/designs/body-shell/manufacturing/README.md).
The native SolidWorks parts are on the CAD workstation in `J:\code\marengo\cad\shell\`. They come into `cad/shell/` here at
the next rebuild ([conventions/cad.md](../../conventions/cad.md)).

**Hold.** Only the fit kit (two hardpoint brackets, four caps, a pilot patch) is cleared to print. The rest of the shell waits
for the torso frame to be assembled and validated. After that, measure the frame as built, adjust the brackets first, and
change the panels only if needed.

## Changes owed at the next rebuild

### 1. Shoulder opening grows to r 80 (shoulder option A, 2026-11-11)

The arm cable passes through the shell beside the pitch actuator, so the shell changes and the shoulder stays as designed.
The study is [hardware/shoulder/study-20261111/shell-opening/OPTIONS.md](../shoulder/study-20261111/shell-opening/OPTIONS.md)
(PR #47). Coordinates are the rev A frame: X lateral (+X left), Y up, Z forward, in mm. The pitch axis runs along X through
Y 424.86, Z 0.

| Item | Now | Change |
| --- | --- | --- |
| Opening round the pitch axis, both sides | r 60 | **r 80**. r 77.9 is the least that clears the fixed cable cover (r 75.9 + 2). r 79.5 also clears the moving flange ring |
| Shell collar at X 135-137 and its 8 screws at r ≈ 45 | fitted | **Removed.** The screw heads sit where the shoulder drum's spokes turn |
| Lower spine pad (X 119.4-129, Y 202-276) | ends at X 129 | **Proposed, not yet chosen:** trim up to 3 mm off the outboard end, to end at about X 126, so the pad keeps 3 mm from the upper arm at the 11° inward stop. Today it comes within 0.01 mm of the arm at pitch -30°, yaw -45°. The other fix is moving the inward stop from 11° to 8°, with no trim |
| Upper spine pad (X 68-147, Y 368-481, Z -124 to -77) | ends at X 147 | **End it inboard of X 140.** It overlaps the moving flange ring (r 77.5, X 142.5-144.3) by about 0.5 mm and is 1.1 mm from the fixed cover |
| Fixed cable cover ring (X 113-140.5) | | Stands 4-7 mm proud of the skin (outer face X ≈ 136). The opening edge needs a finish that suits a part passing through it |

Check at the rebuild:

- The skin itself needs no trim for the 11° inward stop: it stays 3.5 mm or more from the arm, and first contact comes at
  13-15°. Pitch +90° had not been swept yet when this was written
  ([CAD_NOTES.md](../shoulder/study-20261111/cad-pass1/CAD_NOTES.md)).

- The moving flange ring sits outboard of the skin and overlaps the opening edge as a labyrinth. Keep at least 2 mm between
  the edge and the ring through full pitch travel.
- In the marengo shell, the socket floor is a cone starting at r 78 round the pitch axis, with a hole of r 53.5 and stepped
  collars. A cut at r 80 takes out the whole floor, so the opening edge lands on the cone wall. Re-run the wall-thickness and
  print-support checks there.
- All the numbers above come from the shell inner-surface STEP (`shell_inner.step`, SHA-256 6a975342…7f7b335), which has
  not been checked against a printed shell.

### 2. Carried over from the marengo shell (2026-11-07)

These use the marengo torso frame: X lateral, Y up from the frame base, Z forward.

- **Sternum splice plates** on the upper front panels stay out of Y 465-505. The 12 V converter on the top front rail
  (X ±40, 24.2 mm proud) has about 7 mm of air to the panel, and a splice plate there would take about 5 mm of it.
- **Two screw holes** on the bottom edge of upper_front_L leave webs about 0.1 mm thick
  ([MESH_CHECK.md](https://github.com/jaylamping/marengo/blob/main/hardware/designs/body-shell/prints/MESH_CHECK.md)). Move
  them at least 1 mm from the next face.
- **Brake resistor and converter clearance** to the panels is in the manufacturing plan. The panels are PETG HF, and the
  air gaps there need no vent.

## Rules for every shell print file

- List every changed setting in the 3MF's `different_settings_to_system`, or Bambu Studio reloads the preset defaults on
  open (for example, infill drops to 15 %). The marengo script is
  [mark_changed_settings.py](https://github.com/jaylamping/marengo/blob/main/hardware/designs/body-shell/prints/mark_changed_settings.py).
- Before shipping, scan the mesh for stray bodies, spikes, slivers and thin walls
  ([check_mesh.py](https://github.com/jaylamping/marengo/blob/main/hardware/designs/body-shell/prints/check_mesh.py)), and add an
  all-sides picture sheet that includes the bed side.
- Use tree supports. Use normal supports only where a face needs a flat slab.
