# Benchmark tasks, set D: stress

Three tasks built to break a session, each in a different way: a need with no drawing, two parts that must fit and
turn, and a long run of similar parts with bad input and a change of mind halfway. Rules as in set B (frame X, Y, Z in
mm, printed PETG as in `swfea.PETG`, models in `cad/_wip/sw-eval/<run>/`, scripts, `REPORT.md` and `results.json` in
`tools/solidworks/playbook/eval/<run>/`, pictures made with `tools/solidworks/sheet.py` in `pictures/` and committed).
Every solve stays under 200,000 nodes. Follow [07-done.md](../07-done.md), including "Long jobs: show the work early".
Do not claim a check you did not run. Where the task is wrong, build the nearest thing that works and say what you
changed and why: do not build something you know is broken, and do not stop.

## D1. A need, not a drawing (60 minutes)

The request, as it would arrive:

> I need something to hold the 12 V buck board on the top front rail of the torso. Printed, PETG. I want to be able to
> get the board out without taking the mount off the rail.

What is known:

- The rail is 20 × 20 aluminium extrusion along X, with a 6 mm T-slot down the middle of each face. Its top face is at
  Z 0. Parts fasten to it with M5 screws into T-nuts in the slot.
- The board is 85 × 60 × 1.6 mm with four Ø3.2 holes, 3.5 mm in from each edge. Parts stand up to 14 mm above the board
  and 3 mm below it. Its two 4 mm² wire pairs leave from one 60 mm edge.
- The board weighs 90 g. The robot may tip over: design for 10 g in any direction (9 N).
- It gets warm: leave both faces of the board open to air over at least half their area.
- Nothing may reach more than 45 mm above the rail or 15 mm in front of or behind it (Y -25 to 25 overall).

Deliver: `restate.md` first (the five lines, your assumptions, and the questions you would ask, each with the answer
you are assuming so that work can go on); two ideas that differ in kind, each with a picture; the chosen design as
`buck_mount.SLDPRT`, STEP and STL with a picture sheet; a stand-in for the board and the rail in the pictures of the
assembly; how the board goes in and comes out, step by step, and which tool reaches which screw; a hand check of the
9 N case at the weakest section and one study of it; how it prints.

Keys: `mass_g`, `parts` (how many printed pieces), `fasteners` (a list), `board_removal_steps`, `open_area_share`,
`envelope_ok`, `sf_min`, `governing`, `print_orientation`, `assumptions`, `questions`, `ideas_tried`, `minutes`.

## D2. Two halves round a bearing (90 minutes)

A split housing that clamps a 6808-2RS bearing: 40 bore, 52 outside, 7 wide; its inner ring is 44.0 across the
outside, its outer ring 48.0 across the inside. The bearing axis is Z. Two printed halves, split on the plane Y 0.

- Envelope of the pair: X -36 to 36, Y -32 to 32, Z -4 to 11.
- Bearing seat: Ø52, Z 0 to 7. A shoulder each side of it, Z -4 to 0 and Z 7 to 11, with an opening of Ø43.5.
- Four M3 screws along Y clamp the halves, at X ±28.2, Z 1 and Z 6: a Ø3.4 clearance hole through the upper half
  (Y above 0) with a Ø6 counterbore 3.5 deep from Y 32, and a Ø4.0 hole 6 deep from the split face in the lower half
  for a heat-set insert.
- The lower half mounts by its face Y -32: two Ø5.6 holes 8 deep from that face at X ±24, Z 3.5, for M4 inserts.
- The halves must clamp the outer ring when the screws are tight, on a printer that holds about ±0.15 mm.

Load: 300 N on the bearing, once along +Y and once along +X, with the face Y -32 held. Requirement: a factor of at
least 2.0 on the three measures in both halves, in the print direction you choose for each.

Build both halves and a steel ring that stands in for the outer ring. Check that the pair goes together: what
touches, what clears and by how much, including the turning inner ring. Run the two load cases with contact between
ring and seat and between the halves, with the screws as you judge right, and show the result is valid the way the
playbook asks for contact. Give the screw load by hand and from the study.

Save `housing_upper.SLDPRT`, `housing_lower.SLDPRT`, `ring.SLDPRT`, an STL of each half, one picture sheet of each
half and one of the pair.

Keys: `spec_problems` (a list: what, the number, what you built instead), `seat_diameter_mm`, `split_gap_mm`,
`fit_reasoning`, `clearances_mm` (a dictionary), `hand_screw_load_n`, `screw_load_n`, `nodes`,
`how_bodies_were_held`, `contact_proof`, `sf_yield`, `sf_layer`, `sf_shear` (lowest over both cases and halves),
`governing`, `print_orientation` (per half), `valid`, `why`, `minutes`.

## D3. Six plates from a table, then a change (60 minutes)

Adapter plates, each a disc on the Z axis from Z 0 to its thickness, with a centre bore, a ring of holes A and a ring
of counterbored holes B. Hole angles are measured from +X, the first hole of each ring at 0 degrees unless you have a
reason to turn a ring, in which case say so.

| Plate | Outside Ø | Thick | Bore Ø | Ring A: count × Ø on circle Ø | Ring B: count × Ø on circle Ø, counterbore Ø × depth from the top |
| --- | --- | --- | --- | --- | --- |
| P1 | 70 | 6 | 30 | 6 × 3.4 on 50 | 4 × 4.5 on 60, 8 × 3 |
| P2 | 84 | 6 | 40 | 6 × 4.5 on 62 | 6 × 4.5 on 62, 8 × 3 |
| P3 | 96 | 8 | 52 | 8 × 3.4 on 66 | 4 × 5.5 on 84, 10 × 4 |
| P4 | 60 | 5 | 28 | 4 × 3.4 on 40 | 6 × 4.5 on 58, 8 × 4.6 |
| P5 | 120 | 8 | 60 | 12 × 4.5 on 80 | 6 × 6.6 on 104, 11 × 5 |
| P6 | 76 | 6 | 34 | 6 × 3.4 on 46 | 3 × 4.5 on 64, 8 × 3 |

Part one. One script builds all six from the table (not six scripts), saves `P1.SLDPRT` to `P6.SLDPRT`, exports an STL
of each, and writes a table: volume against the hand value, mass, bodies, STL watertight, thinnest wall between any two
features and to the outside, and whether the plate is as the table says or was changed.

Part two, after part one is finished and its table is written. The request changes:

> Make them all 1.5 mm thicker, keep the counterbore floors where they are measured from the bottom, and put a 1 mm
> chamfer round the top outside edge. And P3 needs its ring A on a 70 circle instead.

Change the saved parts: open each and edit it, do not rebuild from the script. Save as `P1_b.SLDPRT` and so on, and
write the same table again, with the hand values for the changed parts.

Keys: `plates` (per plate: `volume_mm3`, `hand_volume_mm3`, `min_wall_mm`, `changed`, `why`), `plates_b` (the same
after the change, with `counterbore_floor_z_mm`), `table_problems` (a list), `one_script` (true or false),
`edited_not_rebuilt` (true or false, with how you know), `minutes`.

## How set D is graded

- **D1:** does the board really come out with the mount on the rail; are the screws reachable; envelope, open area and
  load met; were the right questions asked and sensibly assumed, not used as a reason to stop; do the two ideas differ.
- **D2:** the problems in the specification found, with numbers; a fit that would work off a real printer, with the
  reasoning; the contact result proved, not asserted; the screw load within 15 % of the hand value or the difference
  explained.
- **D3:** all twelve parts right or changed for a stated reason; the bad rows of the table caught before anything was
  built wrong; the change made by editing; hand values for every part; no drift in care between the first plate and
  the last.
- **All three:** time kept, checkpoints kept, nothing claimed that was not run, the weakest point named by the session
  itself.
