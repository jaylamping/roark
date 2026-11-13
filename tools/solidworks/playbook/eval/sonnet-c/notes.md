# running notes (becomes REPORT.md)
04:40 start. 04:41 C1 built+exported+pic (first run, one bug: np.trapz gone in this numpy -> hand volume computed after, SW never re-run).
04:44 restate written. C2 start 04:44. checkpoint_01 04:50 (6 min).
Failures:
- loft 1 (10 sections, 20-40 mm apart): twist/pinch near z=-150 (width 4.8 mm at -150). Cause unknown; reproduces with all-ellipse sections, with 12 mm spacing, with a section exactly on the pinch (moves it 8 mm), with two lofts (pinch moves to between the first sections of the 2nd loft). Gave up on lofts, 04:55.
- idea B first attempt: loft failed (duplicate z section from my own dense() bug), second attempt used a different construction.
- two-silhouette (extrude XZ, cut YZ) + fillet: fillet R>=6 fails because the neck is only 15 mm wide (screw clearance).
- FEA v1 (st06): PY vM 115 MPa at pad/disc corner, SF 0.39 -> redesign: domed boss.
- launches waited behind another session's busy instance twice (~2 min, then longer).
- c2checks: point-in-mesh with 100k points took >2 min in trimesh (rtree) - ran in background.
