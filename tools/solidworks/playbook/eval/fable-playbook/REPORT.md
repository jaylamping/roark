# Benchmark run fable-playbook

holly-pc, SolidWorks 2026 SP0, 2026-11-12, 22:25 to 23:12 local (about 47 minutes including reading the playbook).
Worktree `sw-eval-fable` at d3251391. Models in `cad/_wip/sw-eval/fable-playbook/`, nodal results in
`cad/_sim/sw-eval/*.npz` (both gitignored). Every script ran as its own `job()`; 16 launches, all closed by the `with`
block. Numbers are in [results.json](results.json); this page says what was done and what was not.

| Task | Result | Time |
| --- | --- | --- |
| T1 | done, first run | 3 min |
| T2 | done; one rerun for a mistake in my own check | 2 min |
| T3 | done: **pass** (yield 2.85, layers 2.21), converged | 5 min, plus 9 min on a support cross-check |
| T4 | done: not converged at the corner, **fail** | 3 min |
| T5 | done: no change required; side printing offered for margin | 1 min |
| T6 | done: **valid**, peak bearing pressure 6.26 MPa | 18 min of the 40 |
| T7 | answered below | |

## T1. Bracket

`t1.py`, `bracket.py`. Base and upright as mid-plane extrudes, the three rounds, then the holes; cutting tools overshoot
1 mm each side into empty space. Every feature carries its hand volume (`expect_dv`).

Hand volume: 24000 + 12000 + 171.68 (inside fillet, (1 − π/4)·4²·50) − 570.20 (base holes) − 2280.80 (bore) − 217.90
(motor holes) − 64.38 − 64.38 (rounds) = **32974.02 mm³**. Model: 32974.02. Mass 39.24 g at 1.19 g/cm³.

Checked: volume; box 0, 0, 0 to 80, 50, 46; one body; no rebuild errors; the centre of every hole, the bore and the
fillet measured on the model against the specification (position, not only size). STL: watertight, one shell, bounds
equal the part box (model frame, not shifted), volume 32990.38 (+0.05 %, faceting). STEP: `SI_UNIT(.MILLI.,.METRE.)`,
AP203. Not done: `record_export.py` (these are `_wip` files, not exports of record).

## T2. Change the saved part

`t2.py`. Opened `bracket.SLDPRT`, saved as `bracket_b.SLDPRT` at once, then added features on top. The SHA-256 of
`bracket.SLDPRT` is the same before and after. Hand: 32974.02 − 657.38 (four counterbore rings, π(5² − 2.75²)·3) −
673.65 (slot, (14·6 + π·3²)·6) = **31643.00 mm³**. Model: 31643.00.

Checked: four counterbore floors at Z 3.0, centred on the four holes; four Ø10 walls; the slot's round ends span X 35 to
55, Y 22 to 28, Z 0 to 6; one body; no rebuild errors. The slot is three features (a rectangle cut and two round-end
cuts), not one: `Sk.arc` leaves the arc direction to be found by trial and I did not spend the time.
The first run stopped at my own check: `pick(kind='cyl', r=5)` also matches the four R5 corner rounds. The count check
caught it; the geometry was already right.

## T3. Static study, 150 N on the bore

`case.py`, `series.py`, `t3_explore.py`, `t3.py`, `t3b.py`.

Case. Support: the four base hole walls fixed (the playbook's own example for a screwed part), underside free. Load: 150 N
along +X as a rigid remote load on the bore wall, at the bore centre (3, 25, 28). Layers along Z.

Hand. The upright is a cantilever 50 × 6, I = 900 mm⁴. Root (Z 6): 150·22·3/900 = **11.0 MPa**; at Z 12: 8.0 MPa.
The corner closes, so the inside (fillet) face is in compression and the back face X 0 in tension across the layers.
Displacement: upright bending 0.31 mm plus the base turning between the corner and the screws, about 2.0 mm at the top.

| el / local mm | nodes | peak von Mises | layer tension (σz) | left out at the fixed holes |
| --- | --- | --- | --- | --- |
| 4.0 / 1.2 | 57,278 | 15.65 | 10.21 | 28.65 |
| 3.0 / 0.8 | 143,635 | 15.78 at (9.3, 32.9, 6.1), on the fillet | 10.20 at (0, 24.8, 10.0), back face | 33.18 |

The step moved the peak 0.8 % and the layer stress 0.1 %: converged. **Yield 45 / 15.78 = 2.85; layers 22.5 / 10.20 =
2.21. Pass.**

The five checks: (1) reaction −150.0, 0, 0 N; (2) displacement 2.36 mm against 2.0 by hand; (3) plain section at Z 12:
+8.07 on the back face, −7.89 on the inner face against ±8.00; (4) the peak is on the fillet, the layer peak on the back
face just above the base, neither at a fixture or load; (5) converged as above.

What was excluded. Nodes within two global elements of the fixed hole walls, and within 1.5 mm of the bore wall. I did
not use the playbook mask for the bore: two global elements (6 to 8 mm) round the bore hides the motor holes, which are
real. The playbook mask gives the same peaks (15.78 and 10.20). The excluded maximum at the fixed hole edges is 33 MPa
and rising, a fixture singularity, but it sits where the base really does carry the corner moment past the screws. So I
ran a second support (`t3b.py`): steel washers bonded on the base top and fixed, hole walls free. Fillet 15.56, back-face
layer stress 10.18 (the T3 numbers do not depend on the support), hole walls below the washers and the underside 12.5 to
12.9 MPa.

Not verified: the bearing stress under the screw heads (both supports are singular there). Interlayer shear is not in the
requirement but the playbook lists 13 MPa for it: it is 7.2 MPa at the fillet, a factor of 1.8. The layer margin is 10 %.
The finer mesh, at 143,635 nodes, is nearer the 150,000 ceiling than I intended (the back-face control was too generous).

## T4. No inside fillet

`t4.py`. `bracket_sharp.SLDPRT` is the same script with the fillet left out (volume 32802.34 = hand). Global 3 mm, a
mesh control on the corner edge.

| corner edge mm | nodes | peak at the corner | σz there | node mean within 0.5 / 1 / 2 mm | back-face layer tension |
| --- | --- | --- | --- | --- | --- |
| 1.0 | 36,616 | 19.83 | −1.0 | 14.1 / 11.6 / 9.0 | 11.36 |
| 0.5 | 44,270 | 26.45 | −6.0 | 17.3 / 12.9 / 10.3 | 11.46 |
| 0.25 | 59,237 | 40.36 | −48.9 | 18.1 / 14.4 / 12.0 | 11.47 |
| 0.125 | 87,972 | 54.68 | −57.9 | 20.9 / 17.3 / 15.6 | (see below) |

**Not converged: +33 %, +53 %, +36 % per halving. It is a singularity, and 54.68 MPa is not a stress.**

How I judged it:

1. The section there carries 11.0 MPa by hand, compressive; the node means bracket it.
2. A sharp corner cannot be printed. `bracket_r05.SLDPRT`, the same part with a 0.5 mm radius as a stand-in, converges:
   37.16 then 36.46 MPa (−1.9 %) with 0.25 and 0.15 mm elements on the radius. That is a factor of **1.23** on yield.
   This is the `reported_stress_mpa`. The real as-printed radius is unknown; a smaller one gives more.
3. Away from the corner, the back-face tension across the layers converges at **11.46 MPa**, a factor of **1.96**.
   The fillet was holding this down too (10.20 with it).

**Verdict: fail.** It fails on item 3 alone, a converged number clear of any corner, fixture or load; item 2 says the
corner itself is worse. In the last row the largest σz tension is a node 0.12 mm from the corner (13.2 MPa): part of the
singular field, not used. Every row: reaction −150.0 N, plain section within 2 % of hand.

`Result.average()` is a mean over nodes, so it climbs as the mesh is refined toward the corner (see the 2 mm column).
The playbook's rule "a value that holds over 2 mm is the section" needs a mesh-independent average to be usable.

## T5. Make it pass

`t5.py`. T3 passed, so the condition of this task is not met and **no change is required**. `bracket_c.SLDPRT` is the T1
geometry unchanged (volume 32974.02, 39.24 g, growth 0 %), so that the file exists.

The one change worth having costs nothing: print it on its side (the Y 0 face on the bed, layers along Y). The solve does
not depend on print direction, so the T3 results were re-read for each direction, same mask:

| Layers along | tension across layers | factor | interlayer shear | factor on 13 MPa |
| --- | --- | --- | --- | --- |
| Z, base on the bed (T3) | 10.20 | 2.21 | 7.24 | 1.80 |
| **Y, on its side** | 4.89 | **4.60** | 4.67 | 2.78 |
| X, upright on the bed | 13.13 | 1.71 | 7.24 | 1.80 |

Von Mises is 15.78 MPa (2.85) in all three. `results.json` gives the side-printed numbers for `bracket_c`.
Not checked: printability on the side in a slicer. A print orientation is a decision the playbook says to hand up; this
is a recommendation, not a decision.

## T6. Pin in a hole, contact

`t6.py` (build, main0, lift, main1, main2), `t6_post.py`.

Model. Block and pin as specified, with the real 0.1 mm radial gap. Pin steel, block PETG. Block bottom fixed. 250 N in
+Z on each pin end face as a rigid remote load at its centre. No-penetration set between the hole wall and the pin.
Direct sparse solver by macro (`before 0 | set err 0 | after 7`).

Holding the pin. Two soft pads (modulus 0.5 MPa, 3 × 2 mm), one outside each end of the hole and under the pin, each
bonded to the block's side face below the hole and to the pin's underside, with explicit bonded sets (the pin face is in
the contact set, so the global bond no longer holds it).

Hand. Mean bearing stress F / (d L) = 500 / (10 · 30) = **1.67 MPa**. Peak, Hertz line contact of a Ø10 pin in a Ø10.2
hole (relative radius 255 mm, E* 2199 MPa, 16.7 N/mm): half-width 1.57 mm, **6.76 MPa**. Ligament tension beside the
hole: 500 / (2 · 14.9 · 30) = 0.559 MPa.

| hole / pin mm | nodes | peak contact pressure | peak von Mises in the block | pin rise | pressure integral | ligaments |
| --- | --- | --- | --- | --- | --- | --- |
| 0.8 / 1.0 | 86,289 | 6.45 | 5.39 | 0.1277 | 506.1 N | 498.6 N |
| 0.6 / 1.0 | 111,601 | 6.13 | 5.43 | 0.1277 | 490.6 N | 505.1 N |
| 0.5 / 1.0 | 135,714 | **6.26** at (0, −11.5, 15.1) | **5.44** at (−1.9, −15, 15.7) | 0.1276 | 491.6 N | 502.1 N |

**Peak bearing (contact) pressure 6.26 MPa**, at the top of the hole, 7 % under Hertz, 3.8 times the mean. Even along the
hole (5.5 to 5.6 MPa mean along the crown in five bands); contact half-width 1.9 mm. The peak von Mises in the block,
5.44 MPa, is 0.9 mm under the contact at the hole's end face.

Why it is valid:

- Reaction 0, 0, −500.0 N.
- The contact pressure integrated over the hole wall gives 492 N, and the two ligaments carry 502 N: the load goes
  through the contact, then through the block, to the ground.
- The pin rises 0.128 mm: the 0.1 mm gap, then deformation. It bends 0.011 mm more at its ends.
- The hole wall outside the contact is stress-free (radial stress under 0.09 MPa beyond 45° from the crown).
- The contact set is contact, not a bond: with 0.02 N the pin floats 0.00105 mm on the pads alone with the gap open
  (19 N/mm). Bonded, 0.02 N would move it about 1 × 10⁻⁶ mm.
- The pads carry 19 N/mm × 0.128 mm = 2.4 N, 0.48 % of the load (under the 1 % mark).
- Mesh: peak pressure moved −5.1 % then +2.3 %; peak von Mises +0.6 % then +0.1 %.
- Bodies were split by geometry from undeformed coordinates; no node fell in two bodies or in none.

What is wrong with it, and what I could not verify:

- **The pads leave a mark.** Each bridges the gap at the bottom end of the hole, and where its bond meets the hole edge
  the block shows a spike: 3.9, 5.3, then 98 MPa at a single node on the finest mesh (displacement five times its
  neighbours, one pad corner of four). With 2.4 N in the pads it is a numerical artefact of the bond, at the unloaded
  side, 10 mm from the bearing zone, and it is left out of both peaks. I did not find its exact cause. A pad bonded
  clear of the hole edge would avoid it.
- A first attempt at the finer mesh (0.5 on the hole, 0.625 on the pin) meshed 227,182 nodes; my 150,000 ceiling stopped
  it before the solve. The pin's mesh was therefore not refined.
- Frictionless contact (the default); no friction study.
- The "excessive displacements" prompt never appeared.

## T7. Diagnose

**a.** PID 20948 is another session mid-solve (`busy`): not hung, and my launch would simply wait behind it. PID 2536 is
half-closed (one thread, no windows, 3.6 GB): it stalls every launch on the machine. Do: do not launch. Run
`claims.py who 2536` to find its owner. If it is mine, end it through `end_session(state_file)`. If not, report the PID
and the line `taskkill /PID 2536 /T /F` to Joey and stop. Must not: launch anyway or retry in a loop, kill either PID
myself, touch 20948 at all, or run the job under `timeout` to "get past" the wait.

**b.** Out of memory in the factorisation, not a singular model: 796,000 nodes with direct sparse, failing at
decomposition as free memory collapses. Do: coarsen to under 450,000 nodes (4 mm global, keep the 0.8 mm controls on
only the faces that matter), solve it alone, three minutes after anything else, and watch memory. Record the failed run
as INVALID. Must not: add restraints or pads as if a body were loose, switch to the iterative solver (it stalls on
contact), change two things at once, rerun the same size, or run it beside another solve.

**c.** The STL was exported with "do not translate to positive space" off, a per-machine setting the new machine has at
its default. SolidWorks moved the part's minimum corner to the origin, so the offset is the part's negative extent. Do:
export again through `swkit.export()`, which pins the options; check `mesh.bounds` against `bbox(d)` and the volume;
record the export; rerun the fit check. Must not: move the native part, add the offset into the fit check or the STL by
hand, or fix it by changing the SolidWorks setting by hand instead of in the script.

**d.** A singularity at the fixture edge: +24 % and +30 % per step, and growing. 61 MPa is not a stress, and neither is
38. Do: report the peak away from the fixture and converge that; judge the fixture region by the hand section stress and
by averages over 0.5, 1 and 2 mm with their node counts; if that region governs, model what really holds the part (the
real radius, or the faces that really bear) until it converges; then compare with 22.5 MPa. State what was excluded and
how large it was. Must not: fail the part on 61, pass it by quietly masking the region, or report whichever mesh size
gives the number wanted.

**e.** `busy` is not hung: an instance does not answer while it solves. Do: tell the other thread it is solving and that
launches wait for it. Read `%TEMP%\sw_hidden_<pid>.log` for a hidden dialog (`#32770 | Simulation`) and look at whether
the solver's files beside the model are still changing; answer a dialog only in my own instance. Beat the claim. If it
truly must end, end it through its own handle (`j.inst.close()` or `end_session`). Must not: restart or kill SolidWorks
or the python client mid-solve, start a second instance, or let the other thread stop it.

## Playbook problems

1. **A study on a freshly opened multi-body file solved the wrong problem, silently.** `t3b.py`, first study after a
   launch, on a part with four inserted bodies: 282,484 nodes instead of 53,556, displacement 9.4 mm instead of 2.35,
   peak in another place. The reaction was still −150.0 N, so check 1 passed. The second study in the same job was
   right. The order was the playbook's own: `open_doc`, `pick`, `static` (which loads the Simulation add-in after the
   picks). Calling `j.simulation()` before `open_doc` and `ForceRebuild3` before `pick` cured it; I changed both at
   once, so I do not know which matters. Single-body parts did not show it. The playbook should give the order, and
   `static()` should log the box of its fixture and load nodes so that a wrong face is seen.
2. **`static()` has no node ceiling of its own below 450,000 and no mesh-only mode.** You learn the node count after
   the solve. I set `swfea.MAX_NODES = 150_000` from my scripts, which stopped a 227,182-node mesh; before I did that,
   item 1 solved 282,484 nodes. A `max_nodes=` argument would do.
3. **`Result.away()` uses two *global* elements for fixtures and loads alike.** With a coarse global size and fine local
   controls it hides real features (the motor holes 2.8 mm from the loaded bore), and the hidden region changes from
   row to row in `converge()`. I wrote my own mask.
4. **`converge()` follows only the von Mises peak.** The layer stress, which governs printed parts, is not followed.
5. **`Result.average()` is a node mean** and rises with refinement (T4). The corner rule in 05-fea.md depends on it.
6. **"Screwed down: fix the hole walls" puts a singularity where the screw joint's real stress is, and the mask hides
   it.** There is no recipe for a screw-head support. Bonded washers worked for everything but the washer rim.
7. **No interlayer-shear helper,** although 05-fea.md lists 13 MPa as an allowable. T3 has 7.2 MPa there (1.8).
8. **The pad recipe says where pads go in one joint, not what they must avoid.** A pad that bridges the gap at a hole
   edge leaves a stress spike in the block (T6). Say: bond pads clear of the faces in the contact set and their edges.
9. **A mesh control on an edge works** (`ctrl=[([edge], size)]`), and is the cheap way to refine a corner. Not documented.
10. **`pick()` cannot filter by body,** and nothing says a radius pick also returns fillets and rounds of that radius
    (T2) or another body's faces (T6: pin and pad tops are both r 5). The count check catches it, as intended.
11. **README.md links `EVAL.md`, which does not exist** at this commit; 06-judgment.md refers to it too.
12. **`Sk.arc`** leaves the direction to trial and error, and there is no slot helper.
13. `%TEMP%\sw_hidden_<pid>.log` did not exist for my instance while it was solving. If the file only appears once
    something has been hidden, 01-session.md should say that its absence is normal.

## Not done or not verified, in one place

- No print, slicer or assembly check on any part; no `record_export.py`; nothing promoted out of `_wip`.
- T3: bearing under the screw heads. T4: the real as-printed corner radius. T5: printability on the side.
- T6: friction; the exact cause of the pad-edge spike; refinement of the pin mesh.
- SHA-256 of the model is logged for T3 only.
