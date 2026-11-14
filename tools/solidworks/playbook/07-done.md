# 7. Done means

The first benchmark runs (2026-11-13, [EVAL.md](EVAL.md)) showed that a session with these pages gets the same numbers as
the strongest model. What differed was how far each went after the numbers were right: one stopped at "it passes", the
other asked what the answer was hiding and what it would do next. This page turns that second habit into steps. They are
required, not optional extras: a report that skips one says so and says why.

## Predict, then run

Before every solve, write three numbers in the script's log: the node count you expect (about 12 times the volume
over the element size cubed, both in mm, on a plain part; half as many again with local refinement), the
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
   **A verdict of pass needs every one of the three measures converged.** If one still moves by more than 5 % at the
   last refinement, the verdict is "not shown", never pass on the finest value. The measure is climbing at a sharp
   edge: give that edge the radius the printed part will have (0.4 mm if nothing says otherwise, or the fillet the
   neighbouring edges have), solve again, and judge that. On the second benchmark set this was the one place the
   two models parted: same numbers, one passed the bracket on a climbing value, the other rounded the edge and found
   1.88 against 2.0.
7. The load path was followed in a sentence: which faces bear, which section carries it, where it leaves.
8. For contact: the proof that the set is contact and not a bond (the test that fits the joint, from
   [05-fea.md](05-fea.md) "Contact between bodies": reverse a tiny load where faces sit line to line, a tiny load in the
   working direction where the body has clearance on both sides), the share
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

## Do not stop early

Stopping before the work is finished is the most expensive mistake on this list, because nobody is watching: the person
comes back hours later to half a job. One benchmark run (2026-11-13) ended a five-task set after eight minutes: a
task left at "not shown" after one attempt, a design task given one try, and a task never started because free
memory was 0.4 GB under the floor for a moment. Every one of those had a next step written on these pages.

**Before you write the final report, go down the task list and give every task one of these three states.** There
is no fourth.

| State | It needs |
| --- | --- |
| done | every item of "A model is done when" or "A study is done when" has its number |
| not possible | the requirement that cannot be met, shown with numbers, and the nearest thing that can be |
| blocked | the same obstacle met **three times, in three different ways**, with what each try was and its log, **and** the task's time limit used up or the list below it worked through |

**What counts as a different way.** A different mesh size, pad stiffness or solver setting is the same way again. A
different way changes the model of the problem: another support or load model, another way to hold the loose body
(a soft spring, a pad somewhere else, a tiny load that seats it first), a simpler twin that isolates the part that
fails, the same question answered by hand or from section forces. When a coarse run works and finer ones do not, the
coarse run is the lead: find what changed between them before trying a fifth mesh. The repeat of that benchmark set
closed a contact task as blocked after four and a half of its forty minutes, on three mesh and stiffness variations
of one approach.

Then, for anything that is not done, these are not reasons to stop:

- **"Not shown" after one attempt.** It is a state to work out of, not a result. The page says what comes next (round
  the edge, try the second support, refine the control): do that, then judge.
- **A helper refused.** Memory under the floor: `job(wait_s=1800)` waits. A launch that did not answer: the same. A
  mesh over the node limit: coarsen the global size. A refusal tells you what to change, not to give up the task.
- **One task failed.** The others do not depend on it. Write down where it stands and do the rest, then come back to
  it with the time that is left.
- **Time.** If the brief gives a budget, use it: a report handed in at a tenth of the budget with tasks open is not
  early, it is unfinished. If it gives none, the tasks set the length, not your sense that it has been a while.
- **It seems good enough.** Check the brief line by line against what you have. A requirement you did not test is open.
- **You have a plan for the rest.** A plan is not a result. Do not end with "next I would": do it.

What does end a job early is on the short list in [README.md](README.md), "Stop and hand it up", and each item there
ends **that task**, not the job: report it, and carry on with every task it does not block.

**Why:** the models that did best here were not the ones with better numbers, they were the ones that kept asking what
was still open. The check above costs a minute and is the difference between a set finished and a set abandoned.

## Long jobs: show the work early

A job that will take more than an hour does not run to the end unseen. The cost of a wrong direction is the time until
somebody looks, so make that time short.

1. **Before modelling, restate the ask** in five lines: what the part is for, the faces and dimensions that are fixed,
   what "good" means for this part (the look, the mass, the factor), and what is yours to choose. If you cannot write
   the "good" line, ask before you start.
2. **First checkpoint within 20 minutes:** the crudest version that shows the whole shape (every body, every interface,
   right size, no detail), with pictures from all sides (`python tools/solidworks/sheet.py part.stl`; open the PNG and
   look at it) and the volume. Commit it and report it (when you are working alone and were told to commit once at
   the end, the picture and one line in the report with the time are the checkpoint). Go on without waiting,
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
