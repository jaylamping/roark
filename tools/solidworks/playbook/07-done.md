# 7. Done means

The first benchmark runs (2026-11-13, [EVAL.md](EVAL.md)) showed that a session with these pages gets the same numbers as
the strongest model. What differed was how far each went after the numbers were right: one stopped at "it passes", the
other asked what the answer was hiding and what it would do next. This page turns that second habit into steps. They are
required, not optional extras: a report that skips one says so and says why.

## Predict, then run

Before every solve, write three numbers in the script's log: the node count you expect (from the element sizes), the
displacement, and where the peak should be (both from the hand estimate). After the solve compare.

| Off by | Do |
| --- | --- |
| nodes more than 2 times, displacement more than 3 times, or the peak on a feature you did not expect | **stop.** Do not read the stresses. Find out why first: wrong faces (read the fixture and load boxes `static()` logs), a loose body, a unit, a stale pick |
| less than that | go on, and put the comparison in the report |

**Why:** a study that solved the wrong problem still returns a clean reaction and a plausible picture. The only thing that
catches it is a number written down beforehand. Same for modelling: `expect_dv` on every feature you can compute.

## A model is done when

1. Volume, box and body count match the hand values, and the rebuild has no errors.
2. **Every dimension in the specification was measured on the finished solid,** not inferred from the volume: each hole
   centre and radius (`pick` + `face_info`), each face position. A hole in the wrong place has the right volume.
3. **The specification itself was checked:** every wall at least 0.6 mm, every hole inside its material, edge distances at
   least one hole diameter, nothing that cannot be printed or assembled, no two requirements that contradict. Build what
   was asked, and list what you would question, with the numbers.
4. Exports are checked as in [04-export.md](04-export.md).

## A study is done when

1. The five checks in [05-fea.md](05-fea.md) have numbers.
2. **The support was tried a second way** whenever the first one hides a stress that rises with refinement (a fixed hole
   wall, a fixed edge): a ring under the screw head, a bonded washer, a longer fixed face. Report both; the numbers that
   agree between them are the result.
3. **The load was tried a second way** whenever it is rigid (`'remote'`) or sits beside a hole, slot or thin wall: on
   the faces that really bear, or as an even force. Report the higher. Two benchmark runs passed a bracket that fails
   because a rigid load stiffened the wall round the screw holes ([05-fea.md](05-fea.md)).
4. **All three failure measures are reported,** each with its place and its factor: von Mises against yield, tension across
   layers, shear between layers (`layer_stress`, `layer_shear`).
5. **Every print direction the part could be made in is read from the same result,** as a table of the three measures.
   Whether or not a direction was given: if another one is better, say so and by how much.
6. Convergence followed the governing measure, not only von Mises (`converge(..., layers=normal)`), over three sizes.
7. The load path was followed in a sentence: which faces bear, which section carries it, where it leaves.
8. For contact: the proof that the set is contact and not a bond (reverse a tiny load: the bodies must part), the share
   the pads carry, and the contact force summed from the results against the applied load.

## "It passes" is not the end

When the requirement is met, the report still has these three, each with a number:

- **The thinnest margin** and what would eat it (a load 20 % higher, the other print direction, a sharper corner as
  printed).
- **The cheapest improvement you found** (mass, margin, print time, fewer supports), even if nobody asked: a direction to
  print it in, a radius, a wall. Try it if it takes under ten minutes; otherwise size it by hand.
- **What you did not check** that a reviewer would ask about.

When the requirement is not met, do not stop at "fail". Try the changes in this order, cheapest first, and show the one
that works: print direction, a radius at the peak, material where the stress is, a different load path.

When asked to make something better with no stated end (lighter, stiffer), keep going until two more steps in a row gain
under 3 %, or a requirement stops you. Say which requirement governs at the end: if none is at its limit, you stopped
early.

## Long jobs: show the work early

A job that will take more than an hour does not run to the end unseen. The cost of a wrong direction is the time until
somebody looks, so make that time short.

1. **Before modelling, restate the ask** in five lines: what the part is for, the faces and dimensions that are fixed,
   what "good" means for this part (the look, the mass, the factor), and what is yours to choose. If you cannot write
   the "good" line, ask before you start.
2. **First checkpoint within 20 minutes:** the crudest version that shows the whole shape (every body, every interface,
   right size, no detail), with pictures from all sides and the volume. Commit it and report it. Go on without waiting,
   but a reply that changes the direction wins over everything done since.
3. **A time budget per stage,** written at the start (shape, detail, study, report). At the end of each stage report in
   three lines: done, measured against the ask, next. A stage that runs past twice its budget stops and reports why.
4. **Compare with the ask, not with your last version.** At every checkpoint put the picture beside the reference or the
   written ask and list what is still missing. "Better than an hour ago" is not a measure.
5. **Never report a stage as done on effort.** Done is the list above for a model or a study; a part that is 60 % there
   is reported as 60 % there, with what the rest needs.

**Why:** the failure this prevents is four hours of work on a part nobody would have accepted at minute twenty.

## Before you hand a problem up

Handing up is right for the cases in [06-judgment.md](06-judgment.md). It is wrong as a way out of a hard step. Before
you do:

1. Three attempts that differ in kind, not in a parameter, each with what it ruled out.
2. The smallest case that still shows the problem (one body less, a coarser mesh, a simpler load).
3. A guess at the cause, and the one experiment that would test it.

Then hand up all of that. Most of the time step 2 finds the answer.

## The last ten minutes

Before writing the report, read your own results as a reviewer who wants to find the mistake:

- Which number here would I least like to be asked about? Go and check that one.
- Did anything surprise me that I explained away without testing? Test it.
- If the part were built from this report and broke, where would it break, and did I look there?
- Is there a small hole, a slot or a thin wall in a stressed region that my masks or my mesh never looked at?
