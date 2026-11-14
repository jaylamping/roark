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

### 1. Shoulder opening grows (shoulder option A, 2026-11-11; target r 75 from 2026-11-14)

The arm cable passes through the shell beside the pitch actuator, so the shell opening grows. With the r 75 target the
shoulder's flange ring gets a rolled rim and the cover band behind it is shell white; the ring and cover sizes in the table
below are from the r 80 layout and will change with the final radius.
The study is [hardware/shoulder/study-20261111/shell-opening/OPTIONS.md](../shoulder/study-20261111/shell-opening/OPTIONS.md)
(PR #47). Coordinates are the rev A frame: X lateral (+X left), Y up, Z forward, in mm. The pitch axis runs along X through
Y 424.86, Z 0.

| Item | Now | Change |
| --- | --- | --- |
| Opening round the pitch axis, both sides | r 60 | **Target r 75 (150 mm), not yet confirmed.** A smaller opening narrows the pitch cable channel (16 mm at r 80, 6 mm at r 70), and a printed cable rig decides the final radius. Don't rebuild the socket until the shoulder work gives the final radius and the ring and cover sizes |
| Shell collar at X 135-137 and its 8 screws at r ≈ 45 | fitted | **Removed.** The screw heads sit where the shoulder drum's spokes turn |
| Lower spine pad (X 119.4-129, Y 202-276) | ends at X 129 | **Trim up to 3 mm off the outboard end**, to end at about X 126, so the pad keeps 3 mm from the upper arm at the 11° inward stop (today 0.01 mm at pitch -30°, yaw -45°). Chosen 2026-11-11 over moving the stop to 8°: the trim is out of sight on the back and keeps the arm's full inward range |
| Upper spine pad (X 68-147, Y 368-481, Z -124 to -77) | ends at X 147 | **End it inboard of X 140.** It overlaps the moving flange ring (r 77.5, X 142.5-144.3) by about 0.5 mm and is 1.1 mm from the fixed cover |
| Fixed cable cover ring (X 113-140.5) | | Stands 4-7 mm proud of the skin (outer face X ≈ 136). The opening edge needs a finish that suits a part passing through it |

Check at the rebuild:

- **The skin needs about 0.54 mm trimmed just below the opening** (X 142-143, Y 332-342). At the 11° inward stop,
  pitch -30°, yaw -90°, it clears the shoulder's fork front by 2.46 mm against the 3 mm the check asks for. This replaces
  the earlier note that the skin needed no trim, which was true until the fork front changed on 2026-11-13. Re-run the
  shoulder study's `check_shell_trim.py` against the rebuilt shell
  ([CAD_NOTES.md](../shoulder/study-20261111/cad-pass1/CAD_NOTES.md)).

- The moving flange ring sits outboard of the skin and overlaps the opening edge as a labyrinth. Keep at least 2 mm between
  the edge and the ring through full pitch travel.
- In the marengo shell, the socket floor is flat out to r 78 round the pitch axis (X 133.1-135.5), with a hole of r 53.5 and
  stepped collars, and a cone wall beyond it. At r 75 the opening lands on the flat floor, 3 mm inside its edge, so its edge is a plain flat ring.
  A cut at r 78 or more would take out the whole floor and put the edge on the cone wall: re-run the wall-thickness and
  print-support checks if the radius grows that far.

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
