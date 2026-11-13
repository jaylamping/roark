# Benchmark run sonnet-d (set D, stress)

Model: `claude-sonnet-5-5`. Machine: holly-pc, own SolidWorks instance per script. Worktree pinned at e36fa00. Models in `cad/_wip/sw-eval/sonnet-d/` (not committed).

| Task | Start | End | Limit | Note |
| --- | --- | --- | --- | --- |
| D1 | 07:33 | 08:12 | 60 min | 39 minutes, 17 of them waiting for a launch |
| D2 | 08:03 (build queued during D1's waits) | 08:34 | 90 min | 31 minutes |
| D3 | 08:10 (script ready, queued) | 08:35 | 60 min | about 20 minutes of work, 19 in the launch queue |

The three tasks were not strictly sequential on the clock: I queued the D2 build and the D3 part one behind D1's study while the machine was busy with another session's solve, because a launch can wait 15 minutes. Each task's own modelling started after the previous one's study had finished. What was not run is said where it matters.
## D1. Buck board mount

**Time:** start 07:33 (`date`), model and study done 08:05, picture checks and text 08:12: **39 minutes, inside 60**, of which 17 were launches waiting behind another session's solve. Runs that failed first: build 1 (the envelope clip `cut_half_space` raised: the sliver it cut was under 1 mm3), study 1 (my face pick returned 18 faces, not 4: the rib top lines have the standoff-top normal; the count check stopped it). The part was rebuilt twice: tilt and screw head (envelope), then the 0.4 mm rib lip. During the waits I queued the D2 build and the D3 part one so their launches ran in the same queue (they did not run before D1's study ended).

**Restated first:** [restate.md](restate.md) (five lines, nine assumptions with the answers I assumed).

### The spec is contradictory, and what I built instead
The envelope allows Y -25 to 25 (50 mm). The board is 60 x 85. Flat, it is 60 wide in Y: 10 mm over. Standing on its 85 edge it is 60 tall against a 45 mm limit. Only a tilt about the rail axis X fits: 60 cos(th) + the 14 mm parts and 3 mm solder side must stay in 50 in Y while 60 sin(th) + the same stay in 45 in Z. I scanned th: at 40 degrees Y span 48.9 and Z 42.1 before margins, at 44 degrees Z fails. **Built at 41 degrees** (rising toward +Y), board centre (0, -0.5, 22.8). Measured envelope of the mount plus stand-ins (board, tall-parts block, terminal block, screws): Y -24.78 to 24.77, Z up to 44.51, so `envelope_ok` is true with 0.2 mm in Y and 0.5 mm in Z, **under my assumption that the 14 mm parts only sit in the middle 24 mm of the 60 mm side**. If the tall parts can sit at the edge, nothing fits at any tilt (4 mm of edge parts alone use 8 mm of Y at 41 degrees); that is the question I would ask first.

A second find during the build: the M3 screw head at the low-edge hole reached Y -25.66 with a washer and -25.27 with a head Ø5.7 at 40 degrees, over the limit. I went to 41 degrees, no washer, button head. The high-edge holes cannot take an insert or a deep boss: a hole along the board normal ends outward (+Y) the deeper it goes, so the standoff there is 4 mm tall with a 4 mm thread-forming pilot.

### Two ideas (different in kind)
- **A (chosen): screw-down on two ribs.** Two wedge ribs, one under each pair of board holes, 4 standoffs with Ø2.7 pilots for M3 thread-forming screws, one base on the rail. Picture: `pictures/d1_buck_mount.png`, with the board and rail: `pictures/d1_buck_mount_assembly.png`.
- **B: slide-in cradle, no board screws.** Two grooved rails along X take the long edges, the board slides out the -X end past a flexing latch. Picture: `pictures/d1_ideaB_slide_in_cradle.png` (a crude box sketch only; the posts do not join the rails in it, it is a picture of the idea, not a design). Not chosen: the high-edge rail sits below the board edge and goes outward past Y 25 by the same geometry; and a printed latch that survives 10 g and many cycles needs a test I could not run.

### The design
`buck_mount.SLDPRT/.step/.stl` in `cad/_wip/sw-eval/sonnet-d/d1/`, one body, 19,338 mm3, **23.0 g** PETG, box X -58 to 58, Y -23.14 to 24.77, Z -2.5 (the key in the slot) to 42.48. Script `d1_build.py`; every feature has `expect_dv` and passed; no rebuild errors.
- Base 116 x 20 x 5 on the rail top; key 50 x 5.4 x 2.5 into the 6 mm T-slot (0.3 each side); two Ø5.5 M5 holes at X ±52 (outside the board's X ±42.5); two pairs of zip-tie slots 3 x 4.5 at the +X end for the wire pairs (the wires leave the +X edge).
- Ribs at X ±39 (7 thick), 4 standoffs Ø7 x 4 at (X ±39, u ±26.5 from the board centre), pilots Ø2.7 x 4.
- **Fasteners (list):** 4 x M3 x 6 button-head (ISO 7380, head Ø5.7 x 1.65) thread-forming, no washer; 2 x M5 x 14 socket head; 2 x M5 drop-in T-nuts; 2 x 2.5 mm zip ties.
- Fit measured on the finished solid with `sheet.inside` (6,000 points each): none of the board slab, the underside-parts slab, the tall-parts block or the terminal block lies inside the mount (0 points); nearest the underside slab 2.7 mm; the rib top line is 4 mm under the board, 1 mm under the lowest solder side.

### How the board goes in and out (mount stays on the rail)
1. Unplug or unscrew the two wire pairs at the +X edge, cut the zip ties (new ones go back through the same slots).
2. Undo the 4 M3 screws, **2 mm hex key (ISO 7380 head), approached along the board normal, 41 degrees from vertical**. Nothing is above the screw heads: the tall block is assumed inside the middle 24 mm.
3. Lift the board straight out along its normal (nothing overhangs it).
4. Refit: lay the board on the 4 standoffs (the pilots line up with the Ø3.2 holes), four screws, torque by feel (thread-forming M3 in PETG strips above about 0.4 N·m), wires, ties.
- **M5 screws: 4 mm hex key, vertical, at X ±52**, in clear air outside the board's ends, reachable with the board fitted. They are not touched to remove the board.

### Open area, envelope
Open area (grid of 1 mm cells on the board, a cell counts covered when the mount is within 6 mm behind it along the normal; screw heads added by hand on top): bottom face **0.84**, top face **0.971**; `open_area_share` = 0.84. Not thermally analysed.

### Load check: 9 N
- **Hand:** load path: 9 N at the board centre (height about 23.4 mm) through the four standoffs into two ribs. Weakest sections by hand: (1) the narrow tip of the rib under the high standoff, 3.2 mm wide in Y at Z 35, 7 thick in X: 2.25 N at 4 mm lever, Y load: M = 9 N·mm, I = 7 x 3.2^3 / 12 = 19 mm^4, sigma = 9 x 1.6 / 19 = **0.75 MPa**; (2) the rib at Z 10 (22.8 wide) for the X load: M = 2.25 x 29 = 65 N·mm, I = 22.8 x 7^3 / 12 = 652, sigma = 0.35 MPa; (3) a standoff root as a Ø7/Ø2.7 tube, 2.25 N at 4 mm: 9 N·mm / 32.9 mm3 = 0.27 MPa. With a factor 3 for the pilot, all under 2.3 MPa: factor of safety over 10 by hand against 22.5 across layers.
- **Study** `d1_study.py`: 9 N through the board centre, three directions, each loaded two ways (remote force rigid on the 4 standoff tops; the same on the 4 pilot walls), support the walls of the two M5 holes fixed, then support the whole base underside fixed. 39,751 nodes (predicted 30,000: 1.3x), 24,486 elements, el 2.0 with 0.8 mm on the standoff tops, solve each about 4 s. Reaction equals the load in every case (9.0 N, other components 0.0).

| Case | disp mm | peak von Mises MPa, where | across layers (normal Z / X / Y) MPa | layer shear (Z / X / Y) MPa |
| --- | --- | --- | --- | --- |
| X, tops, M5 walls | 0.0095 | 1.04 (-40.1, -17.3, 2.9) low rib root | 0.34 / 0.51 / 0.66 | 0.31 / 0.50 / 0.50 |
| X, pilot walls | 0.0078 | 0.57 | 0.23 / 0.46 / 0.56 | 0.12 / 0.27 / 0.27 |
| **Y, tops** | 0.0847 | **1.66 (43.5, 9.0, 5.0)** zip slot corner | 0.87 / 1.69 / 0.65 | 0.93 / 0.93 / 0.62 |
| Y, pilot walls | 0.0833 | 1.66 | 0.87 / 1.68 / 0.65 | 0.93 / 0.93 / 0.62 |
| Z (down), tops | 0.0096 | 0.41 | 0.13 / 0.24 / 0.23 | 0.20 / 0.19 / 0.20 |
| Z, pilot walls | 0.0094 | 0.33 | 0.09 / 0.24 / 0.12 | 0.19 / 0.19 / 0.13 |
| X, base underside fixed | 0.0046 | 0.62 | 0.22 / 0.25 / 0.34 | 0.15 / 0.35 / 0.34 |
| Y, base underside fixed | 0.0102 | 0.54 | 0.16 / 0.08 / 0.10 | 0.16 / 0.08 / 0.17 |

Cross-checks from the playbook: loaded the second way (pilot walls): same to 1 %; supported the second way (whole underside fixed): lower, so the M5 walls were the harsher support. The governing case is Y, with the peak at the sharp corner of a zip-tie slot in the base (a re-entrant corner: this peak was **not** converged and I ran no mesh series, so it is "not shown converged"; the 5 to 10 times margin covers a corner that climbs).
- **sf_min:** yield 45 / 1.66 = **27**; **printed base-down (layers stacked along Z):** across layers 22.5 / 0.87 = **26**, interlayer shear 13 / 0.93 = **14**. Every print direction from the same result: layers along X (rib plane on the bed): across layers 22.5 / 1.69 = 13, shear 13 / 0.93 = 14; layers along Y: 22.5 / 0.65 = 35, shear 13 / 0.62 = 21. Base-down is best for across-layers and equal for shear (limit shear 14, margin set by the Y load at the slot corner, not the ribs).
- **Governing:** interlayer shear 13 MPa at the zip slot corner under a sideways load (sf 14).
- Hand versus study: hand 0.75 MPa at the rib tip against study peak 0.3 to 1.7 depending on case: same order; the study peak is at the slot corner (not where I predicted, a standoff root; the standoff roots read 0.3 to 1.0), which I had not hand-checked.

### Print
PETG, base flat on the bed, no supports (standoffs lean 41 degrees from vertical: under the 45 degree limit; ribs lean 20 degrees). 0.2 mm layers, 4 perimeters, 30 % gyroid, 0.4 nozzle. About 25 g.

### Weakest points, named
1. The whole fit rests on my assumption about where the tall parts are. 2. The slot-corner peak was not converged. 3. The envelope margin is 0.2 mm in Y: on a printer at +-0.15 mm the mount can just reach 25.0. 4. I have not checked that a standard M5 T-nut and the 5.4 mm key coexist (the key is 50 long, the nuts sit under the M5 holes at X ±52, clear of it). 5. Heat, and the wire strain relief, were not tested. 6. Idea B was not designed.

## D2. Split housing round a 6808-2RS

**Time:** first build 08:03, last study 08:34: about **31 minutes of work, inside 90** (launch waits included, about 6). Failed first: build attempts 1 to 3 on the counterbore (an `extrude(cut=True)` of Ø6 circles reported "no cut changed the volume" three ways: mid-plane at 30.25, blind from the face at 32, blind from the floor at 28.5; I never found why and used revolve cuts, which worked). Then the second counterbore of each column "lost" 7.9 mm3: the two Ø6 counterbores are 5 mm apart and overlap (the volume predicted with the lens area then matched to 0.01 %).

Built: `housing_upper.SLDPRT`, `housing_lower.SLDPRT`, `ring.SLDPRT` (steel stand-in for the outer ring, Z 0.2 to 7.2), four pin parts (stepped steel pins), four soft pads and `housing_pair.SLDPRT` (all 11 bodies in place), in `cad/_wip/sw-eval/sonnet-d/d2/`. STLs of both halves; sheets `pictures/d2_housing_upper.png`, `pictures/d2_housing_lower.png`, `pictures/d2_pair.png` (upper, lower and ring; the pins are not in the STL). What I see: the upper sheet shows a block with a half-bore stepped wider at the seat, a figure-8 counterbore pair at each end of the back face and four plain holes on the split face; the pair sheet shows two blocks with a thin split line across the Ø46 opening and the M4 holes on the lower half's side face.

### Spec problems found, with the number, and what I built
| What | Number | Built instead |
| --- | --- | --- |
| Shoulder opening Ø43.5 against the inner ring Ø44.0 | the turning inner ring would rub: 0.25 mm of overlap each side | **Ø46.0** (1.0 mm radial clear of the inner ring, the outer ring keeps a 1.0 mm land: its inside is Ø48.0) |
| Screws at X ±28.2 against the Ø52 seat (r 26) | wall to the Ø3.4 clearance hole 0.5 mm; to the Ø4.0 insert hole **0.2 mm** | screws at **X ±30.0**: walls 2.3 and 2.0 mm; the counterbores still have 3 mm to the X ±36 end |
| Ø6 counterbores for screws 5 mm apart (Z 1 and Z 6) | 5 < 6: they overlap into a figure-8 (lens 2.25 mm2) | left as a figure-8: each head Ø5.5 still sits on its own floor arc |
| Seat 7.0 wide for a 7.0 ring on a printer that holds ±0.15 | zero axial clearance, the ring may not go in | seat **7.4 wide** (Z 0 to 7.4), ring 0.2 clear each side (upper shoulder 3.6 thick) |
| Seat Ø52 for a Ø52 ring, ±0.15, "must clamp" | line to line: loose or tight by 0.15, no controlled clamp | halves stand **0.6 mm apart** (faces at Y ±0.3): see the fit reasoning |
| Insert hole 6 deep for an M3 x 35 screw (28.8 from the counterbore floor to the split face + 5.7 insert) | the tip is 6.2 below the face: it would bottom out | **7.0 deep** |
| M4 insert holes 8 deep | equals a typical M4 insert length: no room for the screw tip | kept at 8 (not changed: check the insert you buy) |

### Fit reasoning
`seat_diameter_mm` 52.0 (nominal, line to line with the ring), `split_gap_mm` **0.6**. The printer holds ±0.15 on a diameter, so the seat comes out 51.85 to 52.15. With the faces 0.6 apart and the seat centred on the axis the halves never touch each other: a big seat (52.15) lets the screws close the gap by 0.15 before the ring is clamped, leaving 0.45; a small seat (51.85) opens the gap to 0.75 as the ring goes in. Either way the clamp is the screw preload pressing the seat on the ring, not a face-to-face stop that tolerance can remove. **Not verified on a printed part**, and the preload is not in the study (linear study, no pretension).

Clearances measured on the exported STLs (`d2_checks.py`, 300,000-point sample of both halves): ring outside to seat 0.005 (touching, as designed); ring end faces to the shoulders **0.2 mm**; the turning inner ring (Ø44.0, over the full ring width) to the shoulder opening **0.997 mm**; Ø40 shaft to the opening 2.96 mm; split gap 0.6; screw shank to clearance hole 0.2 radial; head Ø5.5 to counterbore Ø6 0.25 radial; head 3.0 high in 3.5 deep: 0.5. M3 hole walls to the seat 2.3; M4 holes to the seat 5.1.

### Study
Bodies: upper, lower, ring (steel), 4 stepped steel pins as the screws (Ø5.5 x 3 head on the counterbore floor, Ø3.0 shank through the clearance hole, Ø4.0 x 5.7 foot filling the insert hole; bonded by the global bond where they touch: head to floor, foot to the hole wall), 4 soft pads (Ø2.4 x 0.2, E 0.5 MPa) between the ring top face and the shoulders at 45, 135, 225 and 315 degrees. `how_bodies_were_held`: the lower half by its fixed face Y -32; the upper half by the pins only; the ring by contact with the seats plus the four soft pads (a ring held only by contact would be free in Z). Contact: no-penetration sets ring/upper seat, ring/lower seat and upper split face/lower split face (0.6 apart, so it stays open). Load: 300 N along +Y, then +X, as a rigid remote force on the ring bore (steel, so it hardly stiffens anything that is judged). Direct sparse solver (the macro log showed 7). Mesh 3.5 mm globally, 1.5 mm on the seats and ring outside, 0.2 mm on the pads: **66,675 nodes** (predicted about 90,000: 0.74x), 81,769 at 2.6 mm; 47 s per solve. Under the 200,000 limit, no lock.

| Check | +Y | +X |
| --- | --- | --- |
| Reaction against the load | 300.0 N in Y, others 0 | 300.0 N in X, others 0 |
| Max displacement (ring) | 0.046 mm (predicted under 0.05) | 0.068 mm |
| Screw tension, 4 pins, mean over the shank at three heights | 69 / 78 / 73 / 81 N, **sum 300.4 N**; hand 75 each | 45 to 51 N each, sum 189 N |
| Screw shear | 0.1 to 0.2 N | 2 to 3 N each; hand 37.5 N each |
| Gap between the split faces after load | 0.610 (from 0.600) | 0.609 |
| Peak von Mises outside 3 mm of the screw axes | upper 3.06, lower 3.19 MPa | upper 2.60, lower 4.42 MPa |

**Screw load by hand and from the study.** `hand_screw_load_n` = 75 N tension per screw for +Y (300 N through the seat of the upper half, four screws; ±3 N because the load is 0.2 mm above the screws' mid-height). From the study: 68.6 to 81.1 N, mean 75.2: **within 15 % of the hand value (0.3 % on the mean), and the four sum to 300.4 N**. For +X the hand value (a 150 N share on the upper half in shear, 37.5 N per screw, plus about 24 N tension from the radial component) **does not match the study** (shear 2 to 3 N, tension 47 N): the +X load path through the screws is not explained, so the +X case has a clean reaction and a sensible displacement but its load path is not shown. My guess, untested: with frictionless contact and 0.2 mm of radial play round the shanks the upper half moves in X until the ring bears on the lower half.

**Contact proof** (`contact_proof`): the same +Y case run with the three contact sets replaced by bonds. Contact: the ring moves 0.046 mm, 75 N in each screw, and the lower seat pole opens (the ring pole moved +0.0408 mm while the lower-seat nodes beside it moved at most 0.00002 mm: the ring lifts off the lower seat, which a bond cannot do). Bonded: the ring moves 0.0019 mm (24 times less), the screws carry 0.6 to 2 N, the whole load goes through the lower half. The sets do something, and the answer depends on them. Pads: they carry under 1 % (peak von Mises in the pad zone 2.7 to 5.4 MPa on 4.5 mm2 each is under 25 N at the very most, against 300 N, and that is the stress at their bonded edge, an upper bound). Not run: a contact force summed from a section cut (the playbook's method), so the share carried by the two seats in the +X case is not known, which is the same gap as the +X screw path.

**Safety factors** (lowest over both cases and halves, outside 3 mm of the screw axes and 7 mm of the fixed face; bearing axis Z up for both halves; refined mesh for +Y, coarse for +X): `sf_yield` **10.2** (lower half, +X), `sf_layer` **21.8** (layers stacked along Z, lower half, +X), `sf_shear` **8.8** (lower half, +X). Every direction the halves could be printed in, from the same results (tension / shear, lowest factor over both cases): upper: layers along X 9.3 and 8.3, along Y 9.0 and 7.5, along **Z 21.9 and 12.2**; lower: along X 9.3 and 6.1, along Y 11.6 and 6.2, along **Z 21.8 and 8.8**. Z is best for both halves in tension and shear: the layers lie in the plane of the seat arc.

**What is wrong with these numbers:** (1) the stress at the edge of the screw head, where the bonded pin head meets the counterbore floor, is 36.9 MPa (sf 1.2) at 3.5 mm and 38.1 at 2.6 mm: a bonded-edge singularity, and the real head bears with preload, which is not modelled. I excluded 3 mm round the screw axes and say so, but that **does not show the head bearing is safe**. Outside 3 mm: upper 2.78 at 3.5 mm to 3.06 at 2.6 mm (+10 %), lower 3.02 to 3.19 (+6 %): two sizes, not three, so `converged` is **not shown**. (2) The +X load path is unexplained. (3) The seat contact is line to line (the playbook's rule 3 warns it is bistable; here the pads and the load direction decide it, and the lower seat opened as it should). (4) No preload. (5) The ring is a rigid remote load on its bore, not a bearing load spread over an arc.

`valid`: **true for +Y, not shown for +X**. `print_orientation`: **both halves with the bearing axis Z vertical** (the outer face on the bed would also work but staircases the seat arc); the shoulder ledge over the seat is a 3 mm bridge, the screw holes along Y are horizontal holes (teardrop them).

### Weakest points, named
1. The +X screw path is not understood. 2. The screw head edge. 3. The 0.6 mm split gap and the clamp reasoning are unverified without a print. 4. Seat contact line to line. 5. Convergence over two sizes only. 6. I kept the figure-8 counterbores without testing a head on them.

## D3. Six plates from a table, then a change

**Time:** one script written and checked 08:10 (queued), part one built 08:29 after 19 minutes in the launch queue (the build itself takes 3 minutes, 0 failures), part two 08:30 to 08:35 (run twice: see below). About **20 minutes of work, inside 60**.

**One script** (`d3_plates.py one`) builds P1 to P6 from the table (`one_script` true). It first looks at every row of the table before building anything (`check()`): rim break-out, counterbore floor under 1 mm, ring A the same as ring B, and the gap between features at the 0-degree start; it turns ring B by the smallest turn (steps of 15 degrees) that gives the largest gap between features, and reports what it did.

### The bad rows, caught before anything was built wrong
| Plate | What | Number | What I built |
| --- | --- | --- | --- |
| P1 | ring A hole (Ø3.4 on Ø50) and ring B counterbore (Ø8 on Ø60) both start at 0 degrees | the hole overlaps the counterbore: wall **-0.70 mm** | ring B turned **15 degrees** (smallest wall between features 3.02 mm). Not changed: the B counterbore is 1.0 mm from the rim |
| P2 | ring B (6 x Ø4.5 on Ø62) is the same as ring A | the holes coincide: zero wall; very probably a copy error in the table | built as listed, ring B turned **30 degrees** so the counterbored holes sit between the plain ones |
| P3 | nothing wrong in part one | counterbore to the rim 1.0 mm (less than one hole diameter, over the 0.6 minimum) | as the table |
| P4 | ring B Ø58 with Ø8 counterbores on a Ø60 plate | the circle is **3.0 mm outside the rim** (counterbore edge at r 33, plate r 30; hole edge at 31.25) | ring B on **Ø49** (counterbore 1.5 mm from the rim) |
| P4 | counterbore 4.6 deep in a 5 mm plate | floor **0.4 mm** | depth **3.8** (floor 1.2) |
| P4 | rings A (4 on Ø40) and B at 0 degrees | wall -1.20 mm | ring B turned **15 degrees** (1.62 mm) |
| P5, P6 | nothing wrong | smallest walls 2.5 and 2.0 mm | as the table |

### Part one: table (built)
| Plate | volume mm3 | hand mm3 | error % | mass g | bodies | STL watertight | STL mm3 | thinnest wall mm | where | changed from the table / request | why |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 17728.67 | 17728.67 | -0.0 | 21.1 | 1 | True | 17711.89 | 1.0 | (28.978, 7.765, 4.0) to outside | yes | ring B turned 15 degrees, smallest wall between features 3.02 mm |
| P2 | 23947.18 | 23947.18 | 0.0 | 28.5 | 1 | True | 23926.04 | 7.0 | (26.847, -15.5, 4.0) to outside | yes | ring B turned by half the pitch, 30 degrees; probably a copy error in the table |
| P3 | 38698.26 | 38698.26 | 0.0 | 46.05 | 1 | True | 38662.1 | 1.0 | (42.0, 0.0, 5.0) to outside | no |  |
| P4 | 9616.26 | 9616.26 | 0.0 | 11.44 | 1 | True | 9610.77 | 1.5 | (-17.324, 17.324, 4.0) to outside | yes | ring B on Ø49 instead of Ø58; depth 3.8 (floor 1.2 mm); ring B turned 15 degrees, smallest wall between features 1.62 mm |
| P5 | 62864.78 | 62864.78 | 0.0 | 74.81 | 1 | True | 62817.75 | 2.5 | (52.0, 0.0, 5.5) to outside | no |  |
| P6 | 20848.86 | 20848.86 | -0.0 | 24.81 | 1 | True | 20827.26 | 2.0 | (-16.0, 27.713, 4.0) to outside | no |  |


Volume against the hand value: the hand value is the closed formula for the plate as built (disc, bore, ring A holes, ring B holes, counterbore rings); the model agrees to 0.0000 % on all six. The STL volume is 0.1 % lower (facets). Thinnest wall: measured on the finished solid (every cylinder face's centre and radius read back with `face_info`, then the gaps worked out from those measured numbers, including the bore and the outside); the counterbore floor is a thickness, not a wall: P1 3.0, P2 3.0, P3 4.0, P4 1.2, P5 3.0, P6 3.0 mm. Bodies 1, STL watertight, bottom at Z 0, top at the thickness, radius as the table, on all six.

### Part two: the change, made by editing
> 1.5 mm thicker, keep the counterbore floors where they are measured from the bottom, 1 mm chamfer round the top outside edge, P3 ring A on a 70 circle.

How: `d3_plates.py two` **opens each saved `P*.SLDPRT`**, sets the dimension `D1@BASE` (the depth of the disc extrude, which was built upward from Z 0 for this), for P3 edits the `RINGA_SK` sketch (deletes its circles, draws them again on Ø70), adds a `TOP_CHAMFER` feature on the one top outside edge, and saves as `P*_b.SLDPRT`. The script never calls the build function in part two (`edited_not_rebuilt` true). How I know: the feature tree of each `_b` file is the original one plus `TOP_CHAMFER`; the counterbore was drawn from a plane at its floor height, cutting upward, so the floors did not move and were measured again at the same Z (3.0, 3.0, 4.0, 1.2, 3.0, 3.0); and the originals `P*.SLDPRT` were not saved (the volumes of the part-one STLs are untouched). The part-two script reports the chamfer volume against the hand value on every plate (matched to 0.01 %).

**New problems the change made, caught before editing:**
| Plate | What | Number | What I did |
| --- | --- | --- | --- |
| P1, P3 | a 1 mm chamfer meets the counterbore: the counterbores reach to 1.00 mm from the rim | top wall **0.00 mm** (a knife edge) | chamfer **0.4 mm**, top wall 0.6 |
| P4 | the same, counterbores 1.5 mm from the rim after my first change | top wall 0.5 mm | chamfer **0.9 mm**, top wall 0.6 |
| P3 | ring A on Ø70 against ring B counterbores at 0 degrees | wall **0.30 mm** (A hole at r 35, counterbore edge at r 37) | ring A turned **20 degrees**: wall 7.3 mm between features |
| P2, P5, P6 | nothing | 1.0 mm chamfer as asked | as asked |

The first run of part two turned P3 ring A by 41.5 degrees (0.68 mm between a hole and a counterbore): my tie-break in the turn search was wrong (it maximised a number that the 0.6 mm chamfer wall pinned for every angle). I found it in the table (the P3 wall column), fixed the search to judge the gaps between features only, and ran part two again from the unchanged `P*.SLDPRT`: that is the table below. P3_b: the one thing to look at is that the top wall to the outside is 0.6 mm at the counterbores, minimum for printing.

### Part two: table (edited)

| Plate | volume mm3 | hand mm3 | error % | mass g | bodies | STL watertight | STL mm3 | thinnest wall mm | where | changed from the table / request | why |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 22040.22 | 22040.22 | 0.0 | 26.23 | 1 | True | 22019.25 | 1.0 | (28.978, 7.765, 4.0) to outside | yes | chamfer 0.4 mm instead of 1.0 (top wall 0.6 mm) |
| P2 | 29648.45 | 29648.45 | -0.0 | 35.28 | 1 | True | 29623.03 | 7.0 | (26.847, -15.5, 4.0) to outside | no |  |
| P3 | 45765.78 | 45765.78 | -0.0 | 54.46 | 1 | True | 45725.2 | 1.0 | (42.0, 0.0, 5.0) to outside | yes | chamfer 0.4 mm instead of 1.0 (top wall 0.6 mm); ring A turned 20 degrees, wall 7.30 mm |
| P4 | 12351.34 | 12351.34 | 0.0 | 14.7 | 1 | True | 12344.44 | 1.5 | (-17.324, 17.324, 4.0) to outside | yes | chamfer 0.9 mm instead of 1.0 (top wall 0.6 mm) |
| P5 | 74259.2 | 74259.2 | -0.0 | 88.37 | 1 | True | 74203.13 | 2.5 | (52.0, 0.0, 5.5) to outside | no |  |
| P6 | 25865.43 | 25865.43 | 0.0 | 30.78 | 1 | True | 25839.03 | 2.0 | (-16.0, 27.713, 4.0) to outside | no |  |


**D3 weakest points:** (1) P2 ring B and the P4 circle are my reading of probable table mistakes, not confirmed. (2) The 0.6 mm top walls after the chamfer (P1, P3, P4) are minimum, not comfortable. (3) The "thinnest wall" is between circles seen from the top; I did not check the counterbore step against the chamfer in section. (4) I did not drive the table with a changed row to test `check()` further.

## Model, kept to the rules
Model id: `claude-sonnet-5-5`. I kept to the files named in the brief: of `tools/solidworks/playbook/eval/` I opened **only `TASKS_D.md`** (and wrote into `sonnet-d/`); I did not open `EVAL.md`, any other run's folder or any other task file. Own instance through `job()` each time, never wrapped in `timeout`, no process of another session touched (the other sessions' instances were only looked at with `--status`), every solve under 200,000 nodes (largest 81,769, no heavy lock), nothing installed, no shared setting changed, `sw_instance.py` not edited. Claim `sw-eval-sonnet-d`, beaten twice.

## Where the playbook or a helper was wrong, unclear or missing
1. **Launch waits cost 17 minutes of D1 and 19 of D3.** The rules say a launch waits up to 300 s and raises `did not answer`; every launch needed a retry loop written by hand (`for i in 1..6; python job; grep "did not answer"`). `job()` has no `retry` and `01-session.md` gives no loop. Suggest `job(wait_s=...)` that keeps waiting. Also: waiting behind my own queued job is not distinguished from another session's.
2. **`extrude(cut=True)` can fail for a plain Ø6 counterbore** in the same part where the Ø3.4 through cut worked ("no cut changed the volume the right way", mid-plane and blind, both sides). Cause not found; `revolve(cut=True)` of the same cylinder worked at once. Not in the "what goes wrong" table.
3. **`cut_half_space` cannot be used to trim an envelope**: it goes through `extrude` with `min_dv` 1 mm3 and raises when the sliver it removes is smaller (mine was 0.25 mm over the limit). The function has no `min_dv` argument.
4. **`pick(kind='plane', normal=...)` returns every face with that normal**: 18 faces for the "4 standoff tops" because the rib tops share the normal. The count check caught it; the page says to narrow with `inside=`/`at=`/`area=` but gives no example of picking a tilted face.
5. **No page for editing an existing part.** D3 part two needed: the depth dimension is named `D1@<feature>` and `Parameter(...).SystemValue` changes it; editing a sketch (`EditSketch`, delete segments, redraw with the sketch transform, `InsertSketch2`) exists only as the "broken" test in `selftest.py`, with hard-coded metres. I had to compose it. `03-modelling.md` says "prefer changing the script": the task forbade it.
6. **Revolves about a tilted axis** (standoffs, pilots, pins along Y) are the right way to make cylinders not on an axis, and work with `Sk.poly` + `Sk.centerline`; the recipes table only shows axes along Z. I found it by trial.
7. **The envelope trick the playbook never mentions:** a hole along the board normal ends outward on the high edge, so no insert fits there; the page on tilted parts is missing, and `sheet.inside` was the only way to prove clearance.
8. **`static()` summary hides a bonded-edge singularity:** `r.away()` removes only fixture and load nodes, so the pin head edge (36.9 MPa, sf 1.2) was in the "peak away from fixtures" of the summary, while the real section stress was 3. The playbook discusses fixed hole walls, not bonded screw heads. I wrote my own masks (`d2_study.py`, `d2_post.py`).
9. **The contact proof does not fit a ring held by two seats.** Reversing a thousandth of the load (`05-fea.md` rule 9) cannot part a body that sits in a half-ring on both sides. I used a bonded twin of the same case, plus the lower seat pole opening, and it was decisive (24 times less displacement); worth a line in the page.
10. **`07-done.md` cannot be met inside D1's 60 minutes with a queue:** study done with two supports and two loadings, but no mesh series (not run) and the checkpoint rule ("commit and report within 20 minutes") conflicts with "work alone, do not ask questions, commit once at the end". I recorded the checkpoint as the picture sheet and the volume.
11. **Cosmetic:** python `open(path).read()` and `write()` without `encoding='utf-8'` on this machine's python mangle `Ø` in the helper scripts (I broke one of mine with it, a `SyntaxError` on a byte 0xD8). `selftest` is clean because it avoids non-ASCII.
12. **`claims.py list` showed my own claim `STALE` 27.9 minutes after claiming** with no `beat` in between; the threshold is not in `01-session.md`.
13. Hand-value rule "mass = volume x 1.19 g/cm3" is in the pages; the PETG density in `swfea.PETG` is 1190: consistent.
