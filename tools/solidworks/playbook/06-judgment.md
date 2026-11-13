# 6. Judgment: what a script cannot check for you

The other pages make the mechanics repeatable. This page is the part that stays hard, written as the questions to ask and
the mistakes this project has already made once.

## Questions to ask before trusting your own result

1. **Did I answer the question that was asked?** Restate the task in one sentence and compare it with what the script did.
   "Check the lug" is not "check the lug under the load case I found easiest to set up".
2. **What is the hand number, and does the result agree?** If they differ by more than 20 %, one of them is wrong. Find out
   which before going on.
3. **What would this look like if it were wrong?** A part that came out mirrored still has the right volume. A load on the
   wrong face still solves. Check position (bounding box, a face's coordinates), not only size.
4. **What did I exclude, and would a reviewer agree?** Every mask, whitelist and "away from the fixture" hides something. Say
   what, and how large the hidden value was.
5. **Is the peak a stress or a corner?** See the singularity rule in [05-fea.md](05-fea.md).
6. **Does the load reach the ground the way the design intends?** Follow the force through the part: which faces bear, which
   bolts pull. A joint that passes on stress while the wrong feature carries the load has not passed.
7. **Would it print, and assemble?** Layers, supports on visible faces, an insertion path, driver access. A part that passes
   FEA and cannot be assembled is not done ([part-lifecycle.md](../../../conventions/part-lifecycle.md)).
8. **Did anything surprise me?** A surprise is information. Write it down and chase it before reporting.

## Mistakes already made here, so nobody makes them twice

| Mistake | How it was caught | Rule it became |
| --- | --- | --- |
| A stress peak reported from a fixture edge | it did not converge | exclude two elements round fixtures and loads; converge the rest |
| Steel bolt nodes scored as plastic | a 76 MPa "arm" peak sat exactly on the bolt radius | split bodies by geometry, with a guard |
| Error 24 read as "singular model" when it was out of memory | free memory fell from 26 to 12 GB in 11 s | watch memory; know both causes |
| Vendor flange position misread from a drawing by 2.9 mm | fit check against the vendor model | measure the vendor model, do not trust a reading of a drawing |
| STL shifted to positive space on a new machine | fit checks failed by the part's negative extents | pin export options in the script |
| A full revolve trimmed back left a 0.02 mm band | the mesher failed | no nearly-coincident faces |
| An instance 28 minutes into a solve killed as "hung" | orphaned solver processes | `busy` is not hung |
| A job under `timeout` left SolidWorks half-closed and stopped every thread | seven launches stuck at the splash | no bare `timeout` |
| A 61 GB python check took the machine offline | Remote Control dropped | cap every python job |

## What to hand up, and how

Hand the work to a stronger model, or to Joey, when it is one of these. What the evaluation found is in
[EVAL.md](EVAL.md).

- **A new design decision:** a load path, a joint concept, a split line, a print orientation, a trade between mass and
  margin. These need the whole robot in view (tenet 0) and Joey's standing preferences.
- **Organic surfaces that have to look right:** lofts, blends and shells judged by eye. Build the option, render it, and
  ask.
- **Two requirements that cannot both be met.** Do not stop: build the nearest thing that works, and give up the
  requirement nothing else depends on. A bolt circle, a mounting face, a bearing size or an interface to another part
  stays; an outside diameter, a depth or an envelope with room beside it moves. Say which one you gave up, by how
  much, and what the other choice would have cost, so the person can overrule it in one line.
- **A number you cannot explain.** Mark it "not shown" and never pass on it; then spend ten minutes on the cause
  before handing it up: where does the body really bear, and does the hand value assume the same? On the benchmark
  housing that question turned a screw load "not explained" into one that matched within 12 %.
- **Contact studies that decide a design,** and any study whose first result failed its checks twice.
- **Diagnosis of something not in these pages:** a new SolidWorks failure, a crash, a result nobody can explain.
- **Anything irreversible on the shared machine:** deleting files outside your worktree, stopping a process you did not
  start, changing a SolidWorks or system setting.
- **A review gate:** layout freeze, before print, before load ([part-lifecycle.md](../../../conventions/part-lifecycle.md)).

When you hand up, give: the task in one sentence, the script and model paths, the exact command, the last 40 lines of the
log, what you checked and its numbers, and what you already tried. Do not hand up a summary of a failure; hand up the
failure.

## Keeping these pages true

When a session learns something these pages lack, or finds a line that is wrong, it changes the page and the helper in the
same PR as the work that found it, with the date. A lesson that lives only in a chat or a review note is lost.
