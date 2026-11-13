# Right shoulder: plan (2026-11-13)

**Status:** a plan only. Nothing is built. **Start it only when the left shoulder has stopped moving:** the hub (D3c6),
the cap screws, and the three cable crossings are all still open, and each would have to be mirrored again.

**Mirror plane:** X = 0, the torso's centre plane (TORSO_INTERFACE.md).

## What mirrors directly

| Item | Why |
|---|---|
| Hub | The lugs, fills, groove and boss tubes are the same under a mirror; the RS02's output is a rotor and takes any clocking. Cable window 68° → **112°** |
| Fork rear, flange ring, port cap, access plugs | No motor-handed features |
| Fork front | The RS02 is close to mirror-symmetric (below), so the mirrored seat, screws, sockets and plug channel fit a real RS02 at the mirrored clock |
| Roll stops, soft limits, torque limits | Same values; roll and yaw angles change sign |
| 6808, screws, pins, inserts | Not handed. Every thread in the shoulder is right-hand on both sides |
| Print orientations and supports | The same, mirrored |
| Strength checks | The loads mirror with the parts; no new solve is needed for a pure mirror |

## What must not be mirrored blindly

**The motors are real parts, not mirror images.** Checked on the vendor models (surface compared with its own mirror
image, best plane through the axis):

| Motor | Result | Consequence |
|---|---|---|
| RS02 (yaw) | Close to symmetric: 99% of the surface within 1.0 mm of its mirror image, worst 1.75 mm, about a plane 86° round in the vendor's frame | A real RS02 stands in for the mirror image if clocked to that plane. The 1.75 mm is inside the smallest clearance round it (drum 2.60), but the **plug channel and socket pockets** must be checked against the real motor |
| RS03 (pitch and roll) | **Not symmetric:** 13% of the surface is more than 1 mm from its mirror image, up to 6.3 mm. On the outer wall (lugs, body) 39% of the surface is off, up to 4.7 mm; on the rear cover (connector bays) 18%, up to 6.3 mm | **The drum, the rear cap and the pitch cover cannot be plain mirrors** where they follow the RS03 |

**So, part by part:**

| Part | Right side |
|---|---|
| Drum | Mirror the outside. **Re-derive from the real roll RS03 at its right-side clock:** the bore relief for the housing boss (`RS03_BUMP`), the window over the top connector bay (`TOPWIN`), the branch to that bay, and the pitch pad's hole clock |
| Rear cap | Mirror. Check its windows and the cap screws against the real RS03's rear cover |
| Pitch loop cover | Mirror the outside. Re-derive what follows the pitch RS03's housing and its connector. The torso mount is the torso thread's |
| Fork front | Mirror, then check the RS03 roll output's pin and screw clock (the output is a rotor: any clock) and the RS02 plug channel on the real motor |

**Other handed things:**

| Item | Left | Right |
|---|---|---|
| RS02 clock | Vendor x-axis at 138° (re-clocked +40°) | The clock that puts the real RS02's mirror plane where the mirror image's is. To be computed from the model, not assumed |
| RS02 socket in use | The one at 228° (fork front frame) | The one that lands in the mirrored channel (312°). One connector per motor; the other capped |
| Yaw zero offset | +40° | **Not simply -40°.** It follows from the right-side clock above and from which of the six hub positions is used. Compute it in the build and write it into SOFTWARE_HANDOFF.md; it is set once at zeroing either way |
| Hub cable window | 68° | 112° |
| Yaw exit on the fork rear | 261.7° | 278.3° |
| Cable loop direction | Round the +X side | Round the -X side |
| Roll soft limits | -9° to +108° | The same numbers in the right joint's own sign convention |
| Hub locating holes | -142° and 38° | -38° and 142° |

## How to build it

1. **Add a side switch to the build scripts** (`dims.SIDE`), so the right parts are built from the same code, mirrored in
   X, with the motor-following features taken from the real motors at their right-side clocks. Derived mirrored parts in
   SolidWorks would be quicker for the plain mirrors, but they cannot re-derive the RS03 features.
2. **Place the real motors** in the right assembly (`build_asm.py`): pitch RS03, roll RS03, RS02, each rotated, never
   mirrored.
3. **Build** the nine parts as `..._right`, the skeleton and the assembly.
4. **Check:** integrity of every export; a surface comparison of each right part against the mirrored left part, listing
   exactly what differs (it should be only the RS03-following features); the full clearance sweep with the real motors;
   the plug channel with the real RS02; the driver-reach check for the RS02 screws.
5. **Strength:** no new solve for the plain mirrors. One solve on the right drum if its RS03 relief or bay window moves
   by more than a millimetre.
6. **Export and record** `cad/exports/shoulder/*_right.STEP/.STL`; picture sheet, left beside right.
7. **Docs:** CAD_NOTES.md, PRINT_NOTES.md (the right-side angles in the ream and screw tables), SOFTWARE_HANDOFF.md (the
   right side's offset and signs).

## Machine time on holly-pc

| Step | Time |
|---|---|
| Side switch in the scripts, and the RS03 feature derivation | No machine time; about half a day of script work |
| Builds: skeleton, nine parts, assembly (one SolidWorks instance) | about 45 min |
| Integrity, surface comparisons, exports, records | about 15 min |
| Clearance sweep (36 poses, 492 sweeps) | about 30 min |
| Plug channel and driver-reach checks | about 10 min |
| Pictures | about 10 min |
| One drum solve, if needed | about 20 min |
| **Total** | **about 2 h, plus 20 min if the drum is solved** |

Memory: one instance, under the 6 GB cap; no large solve.

## Open before starting

- The left shoulder's open items (hub release, cap screws, cable crossings).
- Whether the right roll RS03's connector bays end up where the mirrored drum has its window, or on the other side of
  the drum. That decides how much of the right drum is new.
- The torso frame's right-side pitch mount (torso thread).
