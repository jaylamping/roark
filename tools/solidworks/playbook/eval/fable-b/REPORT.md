# Benchmark run fable-b (task set B)

Model: `claude-fable-5-2`. Machine: holly-pc, SolidWorks 2026 SP0, worktree `J:\code\roark-wt\sw-eval-fable-b` pinned at
`d533ba0`. Numbers are in [results.json](results.json); every number below comes from a log or JSON file in this folder.

## How this run was made: two sessions

The run was started by one session (02:17 to 04:01 local time, 2026-11-13) that died with nothing pushed, and finished
by a second (from 04:02). The second session read every script, log and result of the first before keeping anything.

| Part | Made by | Kept or redone |
| --- | --- | --- |
| B1 model, measurements, exports (`b1_hub.py`, `b1.log`, `b1.json`) | first | kept: every check has its number in the log. The second session added `spec_questions`, which the first had measured but not written |
| B2 model, study, edge study, all-round-fillet variant (`b2_*.py/.log/.json`, `bracket_fea.py`) | first | kept: all 24 solves have complete logs. The verdict and this write-up are the second session's |
| B3 steps s1 to s8 (`b3_step.py`, `b3_s1..s8.log`, `b3_steps.json`) | first | kept as the record of the search. The first session stopped without choosing: `wall_bracket_light.SLDPRT` on disk was a copy of s8, which is at no limit. Steps s9 onward, the choice and the write-up are the second session's |
| B4 build and three solves (`b4_contact.py`, `b4_r1..r3.log`, `b4_runs.json`) | first | kept, with one caveat: the 244,072-node solve broke the memory rule (below). The reverse-load proof, the coarse mesh (`b4_r4.log`, `b4_r5.log`) and the write-up are the second session's |
| B5 | second | |
| `results.json`, `REPORT.md`, `make_results.py` | second | |

Clean-up at the restart: `sw_instance.py --status` showed two instances, PIDs 43420 and 131988, both started at 04:02 by
other sessions (`build_parts.py` under the shoulder venv, and `organic_fea.py` in the left-arm-organic worktree). Neither
is this run's: left alone. The first session's last instance (PID 130820) had closed itself at 04:01:31 (`b4_r3.log`);
the claim held no PID and the worktree no state file, so there was nothing of this run's to close. No `HALF-CLOSED`
instance. `C:\joe\.fea_solve.lock` existed and belongs to a live process of another session (`left-arm-organic`, PID
134928): left alone; this session ran no solve above 200,000 nodes, so it never needed the lock. The stale claim
`upper-arm-r1` is another session's: left alone.

I kept to the rule on other runs: in `tools/solidworks/playbook/eval/` I read `TASKS_B.md` and this folder only. The
`git fetch` printed the names of two other paths there in a diff summary; I did not open them.

### The 13 GB solve

`B4_80N_c0p5_e0p2` (first session, 03:34 to 03:47, `b4_r2.log`): 244,072 nodes, direct sparse solver, three
no-penetration sets, 14 contact iterations, each a full factorisation; 610 s in the solver, 785 s with readback. It was
that large because, after the first 88,263-node result showed a rising peak on the slot-mouth edge, the first session
refined in two ways at once: the four contact faces from 0.8 to 0.5 mm **and** a 0.2 mm control on the six bearing
edges, each 20 mm long. The edge control alone put roughly 100 elements along each edge and several rings round it. The
script's own prediction line said "60,000 to 200,000 nodes" and the mesh came back at 244,072; by
[07-done.md](../../07-done.md) that is inside the factor of two, so nothing stopped it, and neither the playbook at
`d533ba0` nor `static()` had a 200,000-node rule then (the table in 05-fea.md gives memory only for 300,000 nodes and
up). It bought nothing: the wall forces moved by 0.4 N against the 88,263-node mesh, and the peak it was chasing is a
line-contact singularity that no mesh settles. The second session's solves are all under 200,000 nodes (largest 88,263).

## B1. Hub

Built by `b1_hub.py`, one feature per item of the specification, each with its hand volume change checked.

| | Result | Hand |
| --- | --- | --- |
| Volume | 21,865.54 mmÃ‚Â³ | 21,865.51 mmÃ‚Â³ (flange 14,137.17 + boss 10,618.58 Ã¢Ë†â€™ bore 1,963.50 Ã¢Ë†â€™ six holes 477.13 Ã¢Ë†â€™ two dowel holes 237.58 Ã¢Ë†â€™ keyway 110.70 Ã¢Ë†â€™ set screw 101.33) |
| Mass (1.19 g/cmÃ‚Â³) | 26.02 g | |
| Box | Ã¢Ë†â€™30, Ã¢Ë†â€™30, 0 to 30, 30, 25 | same |
| Bodies, rebuild errors | 1, 0 | |
| STL | watertight, 1 shell, 21,811.0 mmÃ‚Â³ (0.25 % under: facets), in the model frame | |
| STEP | millimetres | |

Every dimension was measured on the finished solid (`b1.log`, `b1.json` Ã¢â€ â€™ `measured`): flange and boss radii, axes and
Z ranges; the bore; each of the six holes by angle (0, 60 Ã¢â‚¬Â¦ 300Ã‚Â°), pitch radius 22.0 and radius 2.25; both dowel holes
(0, Ã‚Â±15), radius 2.75, Z 0 to 5; the keyway floor at X 6.4, Y Ã‚Â±1.5, full length; the set-screw hole radius 2.0, axis
along Y through Z 22.6, from the bore to the outside.

The 0.03 mmÃ‚Â³ between model and hand is the set-screw hole's inner end, which follows the curved bore; the hand value
treats it as flat.

Questions on the specification (built as written; these are what I would ask before printing):

1. **The set-screw hole leaves 0.4 mm of boss above it.** Axis at Z 22.6, radius 2.0, so the hole reaches Z 24.6 and
   the boss ends at Z 25. That is under the 0.6 mm minimum wall and would print as one or two broken layers. An edge
   distance of one diameter puts the axis at Z 19 or lower. Is 22.6 a typing error for 12.6 or 20.6?
2. **The dowel holes run under the boss.** On a ÃƒËœ30 circle a ÃƒËœ5.5 hole spans radius 12.25 to 17.75, and the boss
   radius is 13. "Through the flange" was built as Z 0 to 5, so each hole is blind over a 0.75 mm lune (1.79 mmÃ‚Â² each)
   where the boss covers it: a ÃƒËœ5.5 dowel cannot pass through, and a pin pressed in from below stops against the boss.
   The circle needs to be ÃƒËœ31.5 or more, or the holes need to go on up through the boss edge.
3. **The set screw does not sit on the key.** The keyway is on +X and the set screw on +Y, 90Ã‚Â° apart. A set screw
   that holds a key is normally over it. Intended (a second, clamping screw on the shaft) or an error?
4. **ÃƒËœ4 for a set screw is neither a tap size nor a thread.** M4 taps in ÃƒËœ3.3; printed threads or a heat-set insert
   need their own size. Which is it?
5. Smaller: the keyway (3 wide, 1.4 deep from the ÃƒËœ10 bore) matches a 3 Ãƒâ€” 3 key; its two floor corners are sharp, and
   printed with the axis vertical that is fine. Bolt-hole edge distances are fine (5.75 mm to the flange edge, 6.75 mm
   to the boss, 6.7 mm to the nearest dowel hole).

## B2. Wall bracket

**Verdict: fail.** As specified the bracket does not show a factor of 2.0. Its best case is 1.9 to 2.1 on von Mises;
two of the three ways to print it fail outright.

The case, written down before SolidWorks (`b2_study.py`): 60 N at X 60, so 55 mm from the plate face. Arm section 10
wide, 12 deep: I = 1,440 mmÃ¢ÂÂ´, c = 6. Root stress 60 Ãƒâ€” 55 Ãƒâ€” 6 / 1,440 = **13.75 MPa**; 13.0 MPa where the fillet ends;
with a stress concentration of about 1.35 for the R3 fillet, 17.6 MPa. Tip deflection of the arm alone 1.38 mm.
Transverse shear 0.75 MPa.

Support, tried two ways as [07-done.md](../../07-done.md) asks: the two hole walls fixed (soft bound, the plate can
lean off the wall) and the whole wall face fixed (stiff bound). The real part, clamped by two screw heads, lies
between. Peaks are read outside a fixed 2.0 mm from fixture and load nodes at every mesh size.

| Check (finest mesh, 138,694 nodes) | Holes fixed | Wall face fixed |
| --- | --- | --- |
| Reaction against 60 N | 59.996 N, Fz | 59.999 N, Fz |
| Largest displacement | 1.88 mm | 1.51 mm (hand, arm alone: 1.38) |
| ÃÆ’x on the arm's top face at X 35 against M c / I = 6.25 MPa | 6.265 | 6.265 |
| Peak von Mises, upper root fillet | 18.65 MPa at (7.7, 20.2, 52.0) | 19.60 MPa at (7.4, 23.9, 52.1) |
| Over 2.5, 1.75, 1.25 mm (23,518, 55,505 and 138,694 nodes) | 18.06, 18.51, 18.65 | 19.35, 19.40, 19.60 |
| Left out by the mask | 30.6 MPa on the upper hole's rim, a fixture edge | 4.4 MPa |

Predicted before each solve: 21,588, 62,941 and 172,710 nodes (got 23,518, 55,505, 138,694), 1.4 to 2.5 mm, peak 16
to 20 MPa in a root fillet. All inside the limits, so the stresses were read.

All three measures, for each way it could be printed, from the same results (finest mesh; value and factor):

| Layers stacked along | Tension across layers (22.5) | Shear between layers (13) | von Mises (45) | Verdict |
| --- | --- | --- | --- | --- |
| X (plate flat on the bed, arm upright) | 20.1 MPa, **1.12** | 6.8 to 7.4, 1.75 to 1.92 | 2.30 to 2.41 | fail: the arm's bending stress pulls the layers apart |
| Z (standing as mounted) | 5.8 to 6.4, 3.5 to 3.9 | 6.7 to 7.4, **1.75 to 1.95** | 2.30 to 2.41 | fail on shear, in the upper fillet |
| **Y (on its side: chosen)** | see below | see below | 2.30 to 2.41 | not shown |

Printed on its side nothing needs support and the bending stress lies in the layers, so that is the direction. But
there the two layer measures peak on the **two sharp edges where the arm's side faces meet the plate** (X 5, Y 15 and
Y 25): the specification rounds the arm's top and bottom and leaves its sides square. `b2_edges.py` put a mesh control
on those edges alone:

| Edge element | Tension across layers, peak | its 1 mm average | Shear between layers, peak | von Mises anywhere near |
| --- | --- | --- | --- | --- |
| 0.4 mm | 13.3 MPa | 2.9 | 7.7 | 19.6 |
| 0.2 mm | 19.6 | 3.6 | 10.5 | 22.4 |
| 0.1 mm | 30.1 | 4.5 | 14.7 | 29.0 |

(wall face fixed; holes fixed gives 11.8, 17.4, 26.6.) Doubling every time the element halves, while the average
over 1 mm stays under 5 MPa: a re-entrant corner, not a section stress. So for the part as drawn `converged` is false
for the layer measures, and the numbers in results.json for them (7.85 and 5.38 MPa at 1.25 mm) are what a normal mesh
shows, not a limit. A printed corner is not perfectly sharp, so I bounded it from the kind side: the same bracket with
the R3 fillet carried all round the arm (`b2_variant.py`, `wall_bracket_allround.SLDPRT`, +0.07 g):

| All-round R3, 179,895 nodes | Holes fixed | Wall face fixed |
| --- | --- | --- |
| von Mises, at the corner blend of the fillet (7.6, 25.0, 52.0) | 21.59 MPa, **2.08** | 23.89 MPa, **1.88** |
| over three sizes | 20.74, 21.46, 21.59 | 22.98, 23.69, 23.89 |
| Tension across Y layers | 4.76, 4.73 | 5.71, 3.94 |
| Shear between Y layers | 5.80, 2.24 | 6.06, 2.14 |

So the arm's corners at the root carry more than the middle of the fillet that the as-drawn mesh reports (the corners
of a rectangular section in bending are where the fillet's concentration and the edge meet). With a generous radius
there the factor on von Mises is 1.88 to 2.08, converged to 1 %; with the drawn square edge it is lower. 2.0 lies
inside that band for the kindest geometry and the softer support, and outside it otherwise.

Load path: the pressure on the top patch bends the arm about Y; the root section carries 3.3 NÃ‚Â·m and 60 N into the
plate just below the upper screw (the arm covers that hole: its head cannot be reached with a driver along X, which
I would also raise); the upper screw pulls on the plate, the plate's foot presses on the wall.

Thinnest margin: von Mises at the root corners, 1.88 to 2.08 against 2.0; a load 5 % higher, the stiffer support or
a sharper corner as printed takes it under.

Cheapest improvement found: do not thicken this shape, change the load path. The B3 bracket holds the same load on
the same screws at about a quarter of the mass with every factor above 2. If the cantilever must stay, the hand value
says the arm needs to be 13 mm deep at the root for 2.0 with the corner concentration (stress falls with depth
squared: 12 Ãƒâ€” Ã¢Ë†Å¡(2.0 / 1.88) = 12.4 mm, rounded up), and its side edges need the same radius as top and bottom.

Not checked: creep (PETG under a standing 60 N), the screws and the wall, fatigue, a load that is not exactly
vertical, and the stress under the screw heads, which neither support models.

## B3. Lighter bracket

**22.70 g to 5.67 g, 75.0 % less,** `wall_bracket_light.SLDPRT` (step s10). Factors, worst of both supports and three
mesh sizes, printed on its side (layers along Y): **yield 2.62, tension across layers 3.72, shear between layers
4.13.**

The idea: the B2 arm is a cantilever, so nearly all its material sits at low stress. The light bracket is an open
triangle in the X-Z plane, 10 mm wide: a wall strip carrying the two screw holes, a thin top chord in tension from the
strip's top to the load pad, and a strut in compression from under the pad to the strip above the lower screw. Printed
on its side the whole profile lies in the layers and needs no support. Both screws can now be reached with a driver
along X, which the B2 arm prevented for the upper one. Hand, by a cut at X 30: chord 89 N (7.4 MPa), strut 101.5 N
(2.7 MPa); the mesh gives 7.41 to 7.48 MPa in the chord.

Fixed things, measured on the final solid: holes at (Y 20, Z 12) and (Y 20, Z 48), radius 2.25, along X; one wall face
at X 0; load patch 10 Ã— 10 at X 55 to 65, Y 15 to 25, Z 52.

| Step | What changed | Mass, g | Yield | Layer tension | Layer shear | Under the pad (yield, tension, shear) | Strut buckling | Kept |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B2 | cantilever as specified | 22.70 | 1.9 to 2.4 | not converged | 2.1 to 2.5 | | | |
| s1 | open triangle: strip 5, chord 3, strut 4.5, all 10 wide | 8.48 | 5.70 | 14.4 | 8.47 | not read | 4.21 | yes |
| s2 | members narrowed to 5 mm in Y; chord 2.0, strut 5.2 | 5.71 | 1.88 | 4.66 | 1.99 | not read | 2.98 | no |
| s3 | chord 2.5 | 5.86 | 2.17 | 5.57 | 2.03 | not read | 3.04 | |
| s4 | strip thinned to 2 mm between the screws | 5.38 | 2.17 | 5.83 | 2.07 | not read | 3.04 | |
| s5 | foot and tip block trimmed; three mesh sizes from here | 5.27 | 2.32 | 4.97 | 2.06 | not read | 3.08 | |
| s6 | R1.5 where the pad overhangs the narrow members; pad zone read | 5.27 | 2.32 | 5.09 | 2.05 | 2.08, 1.64, **1.23** | 3.08 | **no** |
| s7 | chord and pad one full-width strap, only the strut narrow | 6.02 | 1.78 | 7.52 | **0.95** | 1.78, 5.76, 0.95 | 3.08 | no |
| s8 | full-width members again, thinner: chord 2.0, strut 4.1 | 6.97 | 4.47 | 11.3 | 7.68 | 8.87, 33.0, 40.2 | 3.05 | yes |
| s9 | chord 1.2, strut 3.6 | 6.12 | 4.45 | 9.64 | 7.13 | 4.66, 10.7, 10.2 | 1.97 | yes |
| **s10** | strip 5 to 3.5 mm, strut 3.7 | **5.67** | **2.62** | **3.72** | **4.13** | 4.83, 11.8, 10.6 | 2.02 | **final** |

What the table hides and the logs show: s5 looked like the answer at 5.27 g with every factor above 2. It was not.
Its pad is 10 wide and its members 5, and the step where the pad overhangs them lies inside the 2 mm load mask. Read
on its own (s6, `pad_zone`), shear between layers there is 10.3 MPa: a factor of 1.26, steady over three meshes. A
radius did not cure it (s6) and a full-width strap moved the problem to the strut's end (s7, 0.95 to 1.61). So
narrowing in Y is out for a part printed on its side, and s2 to s7 are a dead end that would have passed with the
default mask. The first session stopped at s8, which is safe but at no limit (4.47); the second took the full-width
shape down in two steps.

Governing at the end: **none of the three required factors is at 2.0.** What stopped the thinning:

1. The strut. Its Euler load with pinned ends is 205 N in the plane against 101.5 N: 2.02. The requirement names no
   buckling factor; I set a floor of 2.0 on the pinned value, which is the low bound (its ends are filleted into the
   strip and the tip block).
2. The chord at 1.2 mm: three 0.4 mm perimeters. Its stress is 7.4 MPa.
3. The strip between the upper screw and the chord: 17.2 MPa, 2.62, with the hole walls fixed (10.2 MPa, 4.42, with
   the wall face fixed). Stress there goes with 1 / tÂ², so 3.0 mm gives 1.94 by hand; 3.2 mm would pass and save 2 %.

So the next step on each of the three is worth under 3 % or breaks a limit, which is the stopping rule in
[07-done.md](../../07-done.md), reached by hand sizing for the last one and not by two more solves.

Checks on s10 (finest mesh, 115,492 nodes; predicted 111,000): reaction 60.000 and 60.001 N; displacement 0.61 mm
(wall fixed) and 0.82 mm (holes fixed), predicted 0.3 to 1.0; chord stress within 1 % of hand; von Mises over three
sizes 16.96, 17.05, 17.17 MPa (holes) and 9.87, 10.06, 10.18 (wall). Tension across layers at the upper screw is the
least settled number: 5.49, 5.68, 6.06 MPa (+6.7 % on the last step), because it sits on the edge of the 2 mm mask
round the fixed hole; at 3.72 it has room. Left out by the mask: 42.8 MPa on the fixed hole rim, a fixture edge that
climbs with the mesh.

Other print directions, from the same results (yield, tension across layers, shear between layers): layers along X
2.62, 2.05, 2.03; layers along Z 2.62, **1.31**, 2.03. Only on its side does it pass with room, and that is also the
only way it prints without support.

Thinnest margin: the strut's buckling floor, then 2.62 on yield above the upper screw. A load 30 % higher takes the
yield factor to 2.0. What I would least like to be asked about: the screw itself. Neither support models a screw head
clamping a 3.5 mm strip, and that ligament is now the highest-stressed place in the part. A washer under the upper
screw, or the strip left at 5 mm for 6 mm round that hole (+0.2 g), is what I would do before printing.

Not checked: buckling by a study (hand only), creep, the pad under a point load instead of an even pressure, a load
with a sideways component (the part is 10 wide and 1.2 to 3.7 thick in places: little out-of-plane stiffness in the
chord).

Time: the first session spent 43 minutes of wall clock on s1 to s8 (02:45 to 03:28), of which about 20 were stalls
(one launch queued, one launch lost after 4.5 minutes, one hidden dialog for 10 minutes). The second spent 6 minutes
on s9 and s10. That is over the 45 minutes by the clock and under it in working time; I went on because s8 was at no
limit and said so here instead of presenting s8 as the answer.

## B4. Tongue in a slot

**Result: the +X slot wall pushes the tongue with 184 N at the slot mouth, the Ã¢Ë†â€™X wall with 102 N at the tongue's
foot. Valid for the forces, the load path and the displacement; not valid for the peak stress at the bearing edge,
which is a line contact on a sharp edge.**

Hand, before SolidWorks (`b4_contact.py` header): the tongue tilts until it bears on the +X wall at the slot mouth
(Z 20) and on the Ã¢Ë†â€™X wall at its own foot (Z 8.1). Moments about the foot: R_top Ãƒâ€” 11.9 = 80 Ãƒâ€” 26.9, so
**R_top = 180.8 N, R_foot = 100.8 N**, and they differ by the 80 N applied. Real bearing patches have depth, which
shortens the lever, so the result should be a little above both. Tilt to close both gaps 0.2 / 11.9 = 0.0168 rad; tip
0.44 mm from the tilt plus 0.08 mm bending: 0.5 to 0.6 mm.

Model: four bodies in `tongue_slot.SLDPRT` (block, tongue, two pads), real 0.1 mm gaps, three no-penetration sets
(each slot wall against its tongue face, floor against tongue bottom), direct sparse solver (the macro log shows
`before 0 | set err 0 | after 7`).

How the tongue was held: nothing holds it until it touches, so it carries two 2 Ãƒâ€” 2 Ãƒâ€” 2 mm soft pads (E 0.5 MPa), one
on each Y face at Z 13 to 15, on the tilt axis where it hardly moves, clear of the block and of every contact face,
outer faces fixed. Their share, bounded from their own stress times their area: 0.05 N of 80 (0.06 %).

| Contact-face element | 1.2 mm | 0.8 mm | 0.5 mm + 0.2 mm on the bearing edges |
| --- | --- | --- | --- |
| Nodes | 43,133 | 88,263 | 244,072 (first session; see "The 13 GB solve") |
| Reaction, N | Ã¢Ë†â€™80.0, 0, 0 | Ã¢Ë†â€™80.0, 0, 0 | Ã¢Ë†â€™80.0, 0, 0 |
| Force on the +X wall (cut through the block's +X pillar at Z 12) | 185.0 | 184.0 | 183.6 |
| Force on the Ã¢Ë†â€™X wall (cut through the tongue at Z 14) | 102.9 | 102.1 | 102.5 |
| Their difference (80 applied) | 82.2 | 81.8 | 81.0 |
| Check on the cutting method: tongue at Z 25 must carry 80 N and 800 NÃ‚Â·mm | 79.94, 800.0 | 80.0, 800.0 | 80.01, 800.0 |
| Shear in the Ã¢Ë†â€™X pillar (must be none) | Ã¢Ë†â€™0.05 | Ã¢Ë†â€™0.08 | Ã¢Ë†â€™0.03 |
| Centre of pressure, +X wall / Ã¢Ë†â€™X wall, Z | 19.71 / 8.68 | 19.71 / 8.45 | 19.69 / 8.20 |
| Tip of the tongue, UX | 0.830 mm | 0.826 | 0.827 |
| Penetration left at the walls | 0.005 / 0.015 mm | 0.005 / 0.010 | 0.002 / 0.002 |
| Block peak von Mises, on the slot-mouth edge (4.1, y, 20.0) | 35.2 MPa | 37.8 | 53.5 |
| its average over 1 mm / 2 mm | 21.0 / 12.6 | 17.0 / 11.2 | 20.8 / 16.0 |
| Block peak 2 mm clear of the bearing edge and the slot's root corners | 9.4 at (6.3, 1.4, 20.0) | 8.6 | 8.7 at (6.2, 0.6, 20.0) |
| Within 1 mm of the slot's root corners (4.1, 8) / (Ã¢Ë†â€™4.1, 8) | 5.8 / 5.2 | 6.8 / 9.5 | 12.4 / 17.5 |
| Solve | 32 s | 85 s | 785 s |

The forces come from cutting free bodies through smooth interior stress, not from summing contact pressure on the wall
faces: the wall-face sums (170 to 172 and 80 to 94 N) are 6 to 22 % low because the pressure is a spike one or two nodes
wide. The cut at Z 25 shows the method is good to 0.1 %.

Why it is valid:

1. **It is contact, not a bond.** The same model with 0.08 N (a thousandth of the load, `b4_r3.log`) moves the tip
   0.444 mm: the tongue swings through the clearance as a rigid body (fitted rotation 0.01717 rad, hand 0.0168 to
   0.0176; elastic part under 0.0001 mm) and comes to rest on the two predicted lines with 0.18 and 0.10 N. Bonded
   faces would have moved it a thousandth of the 80 N value, under 0.001 mm. The response is also not proportional:
   1,000 times the load gives 1.9 times the displacement.
2. **Equilibrium:** reaction Ã¢Ë†â€™80.0 N in X; wall forces differ by 81 to 82 against 80 (1 to 2.7 %, closing as the mesh
   shrinks); the Ã¢Ë†â€™X pillar carries nothing; the +X pillar's moment at Z 12 is 1,437 NÃ‚Â·mm against 183.6 Ãƒâ€” (19.69 Ã¢Ë†â€™ 12)
   = 1,412.
3. **Against the hand values:** 183.6 and 102.5 N against 180.8 and 100.8, both 1.6 % above, as predicted (the foot
   patch is 0.1 to 0.4 mm deep and the top one sits at 19.7, so the lever is 11.5 mm, not 11.9).
4. **Three meshes:** forces within 0.8 %, tip UX within 0.4 %.
5. **The pads carry 0.06 %** and nothing passes through the floor (axial force in the tongue 0.3 N).
6. **Displacement:** predicted 0.5 to 0.6 mm, got 0.83. Inside the factor of three, and explained: the fitted tilt is
   0.0290 rad, not the rigid 0.0168, because the +X pillar leans (0.067 mm at the mouth) and both bearing lines dent.

What is not valid, and why:

- **The peak stress at the bearing edge** (`block_peak_vm_mpa` 53.5 MPa at (4.1, Ã¢Ë†â€™0.5, 20.0)) rose 35 Ã¢â€ â€™ 38 Ã¢â€ â€™ 53 MPa
  over the three meshes and is above yield. A flat face on a sharp 90Ã‚Â° edge is a line contact: the elastic stress has
  no limit. What the part does is yield there until the strip is wide enough: 184 N over 20 mm at 45 MPa needs about
  0.2 mm. The numbers that hold are the 1 mm average (17 to 21 MPa) and the 8.7 MPa peak 2 mm away, on the top face
  beside the edge. The same applies to the tongue's foot edge (53.6 MPa at the finest mesh).
- **The slot's two root corners** are sharp too and climb the same way (5 Ã¢â€ â€™ 7 to 9 Ã¢â€ â€™ 12 to 17 MPa within 1 mm). The
  nominal bending stress there is 2.5 MPa (183.6 N Ãƒâ€” 11.7 mm on a 20 Ãƒâ€” 15.9 section), so with any real radius they are
  not the problem; without one the model cannot say.
- **The reverse-load run failed** (`b4_r4.log`, second session): Ã¢Ë†â€™0.08 N, to see the tongue swing the other way.
  The solver ran 100 contact iterations in 11 minutes and put up "Failure to achieve equilibrium during task 'Solving
  contact constraints'", which `static()` logged and did not answer; I read it in my own instance and pressed OK. The
  saved result is **INVALID** (wall forces of hundreds of newtons for 0.08 N applied) and is not used. Point 1 above
  rests on the forward 0.08 N run alone. My guess at the cause: pulling on the patch with a negative normal force
  leaves the tongue balanced on the pads between two walls 0.1 mm away with nothing to pick a side; the one experiment
  that would test it is the same case with the pads at Z 9 instead of on the tilt axis. Not run: it is a 5 to
  12 minute solve and the task's time was already spent.
- At 88,263 nodes the tongue also lifted 0.21 mm and turned 0.0098 rad about X (`b4_rigid.py`), a drift on the soft
  pads in the directions no contact holds (pad load 0.47 N there, against 0.05 N on the other two meshes). It does not
  change UX or the forces, but the resultant tip displacement on that mesh (0.97 mm) includes it, so
  `tongue_tip_disp_mm` is the 0.84 mm of the finest mesh (UX 0.83).
- No friction. With friction the tongue's foot would not slide freely and the forces would shift a little.

Time: the first session reached a complete answer (88,263 nodes, checked) about 6 minutes after starting the task, spent
13 minutes on the 244,072-node solve and 5 on the 0.08 N run, and died at 33 minutes while writing nothing down. The
second session added 21 minutes of wall clock (8 queued behind another session's solve, 12 in the failed reverse
solve, under 1 in the coarse mesh). So the 40 minutes were overrun: at minute 40 of work the state was "forces and
contact proof done, convergence on two meshes, reverse-load proof not done".

## B5. Review of the motor-plate report

**Not approved.** Nothing in the report supports "pass", and three things in it each say on their own that the study
or the export is wrong. Most serious first:

1. **Reaction 96 N against 120 N applied is not "close enough".** It is 20 % off; the check is 1 %. The solver balanced
   a different load from the one described (a force that is not along +X, a face missed, a normal force on a face that
   is not normal to X, part of the plate left out). Every stress and displacement after that line belongs to another
   problem. This alone voids the result.
2. **The exported STL is the wrong size.** "Volume 1.02 against 16,700 mmÃ‚Â³" is not rounding: 16,700 mmÃ‚Â³ is 1.02 cubic
   inches. The file is in inches (or was read as such), so a slicer taking it as millimetres prints the plate 25.4
   times too small. Watertightness, shell count and position in the model frame are not reported either. "Ready to
   print" is false on the file alone.
3. **The across-layer check uses the wrong stress and the wrong allowable.** Layers are stacked along Z, so tension
   across layers is ÃÆ’z, not ÃÆ’x; ÃÆ’x lies in the layers. And the allowable across layers is 22.5 MPa, not 45. If 19.5 MPa
   really were across the layers the factor would be 1.15, not 2.3. The real ÃÆ’z was never read.
4. **Shear between layers (13 MPa) was not checked at all.** A plate printed flat and loaded in its own plane through
   screws is exactly where that can govern.
5. **A factor of 1.1 on von Mises was ignored without evidence.** "It is at a hole edge" is a guess. The holes are the
   fixtures, so it may be a fixture singularity, but then the report must show it: the peak outside a stated distance
   from the fixed faces, the averages over 0.5, 1 and 2 mm with node counts, and what was left out. The plate's whole
   load passes through those four holes, so the hole edges are also where it would really fail.
6. **It has not converged.** 37.6 to 41.0 MPa is 9 %; the mark is under 5 % on the last step, over three sizes, not
   two. A peak that climbs 9 % on a refinement at a fixed hole edge is behaving like a singularity, which is the
   opposite of the conclusion drawn.
7. **The support was modelled one way only,** and the way that puts a singular edge at the peak. It needs a second
   support (the rings under the screw heads, or bonded washers), with the numbers the two agree on.
8. **The hand estimate does not match the study and nobody asked why.** 3.4 MPa by hand against 37.6 to 41 from the
   mesh is a factor of eleven; the rule is 20 %. The estimate itself is also doubtful: b = 4, h = 40 is the plate
   bending in its own plane; if the 120 N bends the plate across its 4 mm thickness the right numbers are b = 40,
   h = 4, I = 213 mmÃ¢ÂÂ´ and 120 Ãƒâ€” 30 Ãƒâ€” 2 / 213 = 33.8 MPa, a factor of 1.3 on yield in the plain section. The report does
   not say which way the plate bends, and no stress was read in a plain section to compare.
9. **The displacement was not compared with anything.** 0.9 mm fits neither reading (0.03 mm in plane, 2.7 mm across
   the thickness, by F LÃ‚Â³ / 3 E I). With item 1 that points at a load or support that is not what is described.
10. **No requirement is stated.** "Pass" against what factor? 2.3 is quoted as if it were enough, 1.1 is waved away.
11. **Machine rules broken.** 520,000 nodes is over the 450,000 limit; it was run beside another large solve, and on
    holly-pc solves that size run one at a time (a pair of 390,000 crashed); even the 212,000-node mesh needs the
    solve lock. Running both "to save time" risked the other thread's work.
12. **The mesh was refined globally.** Two global sizes cost 520,000 nodes and still give under three elements
    through a 4 mm plate at the peak. A 2.5 to 3 mm global size with 0.5 mm controls on the hole walls and the motor
    face answers the question at a tenth of the size.
13. **The load is not justified.** Where 120 N along +X comes from, why a motor plate sees no torque or moment from
    the motor's overhang, and whether "the motor face" is where a motor really loads the plate (it bears through its
    screws and its pilot) are all missing. A load on a face beside small holes needs to be tried a second way.
14. **Only one print direction was read,** and no table of the three measures per direction.
15. **The record is missing:** model file and hash, solver, element counts, the excluded region, the place of each
    peak in coordinates, and where the nodal results are kept.

What has to be redone: (a) the study, from the load definition up: state the load case and the pass mark, get the
reaction to 120 N within 1 %, match a plain-section stress to the hand value within 15 %, both supports, three mesh
sizes under 200,000 nodes with local controls, all three measures with the right components (ÃÆ’z and the shear on Z
planes for this print direction) for each print direction; (b) the export, in millimetres with pinned options, checked
for volume, watertightness and frame; (c) the verdict. If the plate does bend across its thickness the hand value
already says it fails at 1.3 and needs to be thicker before any of this is rerun.

## Time, failed runs

| Task | First session | Second session | Notes |
| --- | --- | --- | --- |
| B1 | 3 min (02:17 to 02:20) | 2 min, the questions | |
| B2 | 25 min (02:20 to 02:45): model, 6 + 6 + 12 solves | 5 min, verdict and write-up | |
| B3 | 43 min (02:45 to 03:28), about 20 stalled | 6 min (04:27 to 04:33) | limit 45 |
| B4 | 33 min (03:28 to 04:01) | 21 min (04:06 to 04:27), 8 queued and 12 in a solve that failed | limit 40 |
| B5 | | 5 min | |
| Reading the first session's work, clean-up, report | | about 20 min | |

Runs that failed, and why:

- First session, 02:52: a launch queued behind another session's solve and was retried (`run_retry.sh`).
- First session, 03:01: a launch gave up after about 4.5 minutes with `PID 133492 never registered in the ROT` while
  another session was launching or solving. Retried.
- First session, 03:04 to 03:15: `load_simulation` sat behind a hidden dialog in its own instance (PID 99312), "Yes,
  continue to load SOLIDWORKS Simulation / No, disable SOLIDWORKS Simulation". Read with `read_dialog.py` and answered
  Yes by hand after 10 minutes.
- First session, 03:31, `b4_r1.log`: the 88,263-node solve finished and its results were saved, then the script's own
  post-processing raised (`np.cross` on 2-D vectors, which numpy 2 refuses). Fixed in the script and the saved result
  post-processed without solving again.
- First session, 03:34: the 244,072-node solve. It ran to the end; it is listed because it should not have been run.
- Second session, 04:06 to 04:11: first launch waited 300 s behind another session's solve and raised, as
  01-session.md says it will; the loop ran it again.
- Second session, 04:14 to 04:26, `b4_r4.log`: reverse-load solve did not converge; INVALID (B4 above).
- Design steps that failed the requirement (s2, s6, s7) are in the B3 table; they are results, not failed runs.

The first session's `launch_waits.log` is kept as it wrote it; the second session's lines in it start with "restart".

## Where the playbook or a helper was wrong, unclear or missing something

1. **`static()` leaves "Failure to achieve equilibrium during task 'Solving contact constraints'" unanswered.** It
   logs "solver dialog NOT answered" and the hidden solve then waits for ever, `busy`, with every other session's
   launch behind it. 05-fea.md rule 8 covers only the excessive-displacement prompt. It needs the same treatment: press
   OK and raise, or return with a flag. After I pressed OK the unconverged result came back as an ordinary `Result`
   with a clean reaction and nothing to mark it.
2. **The reverse-load proof (05-fea.md contact rule 9, 07-done.md study item 8) does not work for a body with
   clearance on both sides.** It is written for faces drawn line-to-line. Here it cost 12 minutes and gave nothing.
   For a clearance fit the forward tiny load is the proof: the body crosses the gap as a rigid body by exactly the
   clearance. The pages should say which test fits which case.
3. **Nothing at `d533ba0` stopped a 244,072-node contact solve.** The sizing table in 05-fea.md has no row between
   100,000 and 300,000 nodes, gives memory only for the top rows, and 07-done.md's "nodes more than 2 times" rule
   passes a mesh that is 2.8 times the one before when the prediction was written as a range. (The branch head now
   has a 200,000-node lock in `static()`.) A prediction should be one number, and a refinement that more than doubles
   the nodes of a result that already passed its checks should need a reason in the log.
4. **Contact forces "summed from the results" (07-done.md item 8) is ambiguous and the obvious reading is wrong.**
   Integrating contact pressure over the wall faces gave 170 and 80 to 94 N where free-body cuts through the interior
   gave 184 and 102 (and returned 80.0 N on a check section). `swfea` has neither; a `section_force(body mask, plane)`
   helper would be the right one to add. The first session wrote its own (`b4_contact.section`).
5. **The fixed-distance mask exists but the pages do not mention it.** `r.away(dist=...)` is in swfea.py; 05-fea.md
   only describes the default of two elements, which shrinks with the mesh. The first session did not find it and
   wrote its own (`bracket_fea.mask`, 2.0 mm). One line in 05-fea.md, check 4, would do.
6. **The load mask hid the governing feature in B3,** exactly as 05-fea.md warns, and the warning worked: the pad
   zone was read on its own. But the warning is about holes; it should say "any step, overhang or junction under or
   beside the loaded face".
7. **Nothing about buckling.** "Make it lighter" ends in a slender compression member, the requirement table has
   three stress measures, and `swfea` has no buckling study. I used Euler with pinned ends by hand and a floor I
   chose. 07-done.md should name it as a fourth check whenever a member in compression is longer than about ten times
   its thickness.
8. **A hidden "continue to load SOLIDWORKS Simulation?" dialog at `load_simulation`** is not in RULES.md or
   01-session.md and nothing answers it. It cost 10 minutes.
9. **01-session.md names one retriable launch message** (`did not answer for 300 s`). `never registered in the ROT`
   is a second one seen here under the same conditions.
10. **Time limits and the queue.** A launch can wait 5 to 15 minutes behind another session's solve and a task limit
    of 40 or 45 minutes does not say whether that counts. Here it was 28 of the 103 task minutes.
11. **Claims and instance PIDs.** With one instance per script the PID changes every few minutes and nothing writes it
    to the claim, so the first session's claim held `sw_pid: null` and its heartbeat was 29 minutes old while it was
    still solving. `job()` could beat the claim with its PID on entry and clear it on exit.
12. **The solve lock on disk does not have the format the helper reads.** `C:\joe\.fea_solve.lock` held
    `left-arm-organic 134928 1794564134 r1g3_stop0b`: no `pid=`. `heavy_solve_lock` at the branch head treats such a
    file as held and can never find it stale, so if that writer dies every heavy solve waits out its full `wait_s`.
    One format, written by one helper, for every script that takes the lock.
13. **TASKS_B, B2:** "3 mm radius fillets ... on the arm's top and bottom" leaves the arm's side edges square against
    the plate. If that is deliberate it is the point of the task; if not, the specification should say "all round".
14. Small: `static()` cuts the study name to 24 characters without a word, so two long tags that differ at the end
    would collide; the first session cut its own tags to 24 to keep them distinct. Not seen to fail here.

The selftest and the lock test asked for after the push are reported in the thread, not here.