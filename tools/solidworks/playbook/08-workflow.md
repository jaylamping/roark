# 8. Who plans, who builds, who reviews

Which model does which part of a SolidWorks job, chosen from the runs in [EVAL.md](EVAL.md). The names are the
models measured there; the rule behind each choice is given so another model can be slotted in once it has been
run on the same sets.

## Choose the lane by one question: is the shape already decided?

| | Shape decided | Shape not decided |
| --- | --- | --- |
| Examples | a part from dimensions, an edit to a saved part, a study with a verdict, a family of parts from a table | an organic link, a cover, anything that will be looked at, anything where the load path is the design |
| Plan | the strongest model, without SolidWorks: steps, the expected change in volume at each step, hand numbers for every check, the branches for the failures it can foresee | the same model that builds |
| Build | the smallest model that follows a plan (measured: Haiku, about 20 minutes a set) | the strongest model, or the next one down (measured: Fable first, Sonnet second) |
| Review | the planner, from the files: rows against logs, verdicts worked again, hand numbers worked again | a second look by the same model at the picture sheet and the weakest section, then a person ranks it blind |
| Fixes | written instructions back to the builder, one round at a time | by the builder itself |
| Stop when | every task is right, or a fix needs a new idea rather than a correction: then it has become the other lane | the gate passes and the form is accepted |

Why the split. On decided shapes the plan carries the judgement and the builder only has to be careful: nine of ten
tasks closed that way, and a plan roughly halves what a right task costs. On undecided shapes the judgement is in
the building. Four review rounds removed every fault a check could name from the small model's organic link (a
twisted loft, the print direction) and it still ended under the strength target and last in a blind ranking of
three.

A plan from a weaker planner still works, but its hand numbers are wrong more often, and the builder checks
itself against them faithfully and cannot repair them. Each wrong hand number costs a "not explained" line and
time.

## A typical part, stage by stage

This is how parts on the robot have gone so far, and it is the job the two lanes are there to serve. Most parts
pass through both: the shape is undecided at the start and decided from the moment the owner picks.

| Stage | What happens | Lane | Who |
| --- | --- | --- | --- |
| 1. The need | a few lines: what it holds, what it must clear, the load, how it prints. Restated, with the questions and the answer assumed for each so work goes on | not decided | strongest model |
| 2. Options | two or three ideas that differ in kind, crude models, a picture sheet of each, the numbers that separate them | not decided | strongest model |
| 3. The pick | the owner chooses from pictures. Nothing real changes before this | | the owner |
| 4. Layout freeze | interfaces, envelope, fasteners, cable paths; the list of things assumed and never checked, each settled. Review gate 1 | not decided | strongest model, outside reviewers |
| 5. The plan | from here the shape is decided: steps, expected volumes, hand numbers, the studies and their branches | decided | strongest model, without SolidWorks |
| 6. Build and studies | the part, its exports, the gate studies, the print-direction table, the picture sheet | decided | smallest model that follows a plan |
| 7. Review from files | rows against logs, verdicts and hand numbers worked again; fixes go back as written instructions. Review gate 2, before print or promotion | decided | the planner |
| 8. Small parts round it | fit coupons, cable rigs, test pieces, spacers, the print project | decided | plan and build, as 5 to 7 |
| 9. Print and bench | the owner prints, fits and loads it. What breaks or does not fit comes back as a change | | the owner |
| 10. A change | a correction (a clearance, a wall, a hole moved) goes back in at stage 5; a new idea (a different load path, a different look) goes back in at stage 2. Every redesign is validated again. Review gate 3 before anything load-bearing or powered | either | by which it is |

The test at stage 10 is the same as the lane question. A reviewer who finds itself writing a fourth round of
instructions is looking at a new idea, not a correction.

## When the strongest model is not available

If the Fable allowance is used up, Opus takes its place in every role above: planner, reviewer, and designer of
undecided shapes. Work does not wait for the allowance to come back. What changes, from the one set of runs with
Opus as the planner:

- **Its hand numbers were wrong more often** (a load model said to read low that read high, a section stress
  with the wrong sign, a screw load 27 % off). The builder cannot repair them. So the planner works each hand
  number twice, by two routes where it can, and marks any it is unsure of as low confidence; the builder treats a
  mismatch against a low-confidence number as the plan's fault after ten minutes, records it and moves on.
- **The plan comes with a shared `common.py`** (allowables, paths, the checks), which that planner left out.
- **The report says who planned and who reviewed**, and `metrics.json` carries it in `plan`, so a result can be
  read with that in mind.
- **Gate 3 work waits.** A review before anything load-bearing or powered is done by the strongest model or by the
  outside reviewers, not by the fallback alone.

Opus has been measured only as a planner. As a reviewer and as the designer of an undecided shape it is
untried; the first such jobs get a second look when the allowance is back.

## Rules for both lanes

1. **The verdict word comes from `swfea.judge()` on the rows.** Never from prose. Both directions have happened:
   "fail" written beside passing factors, and "pass" written beside a caveat that said it was not shown.
2. **Keep the job logs with the run.** Without them a review can check arithmetic and judgement, not what the
   solver returned.
3. **The builder's report is a claim.** The reviewer reads rows and logs, and works the volumes by hand.
4. **Print direction from the table** in [04-export.md](04-export.md): height, support on faces that show,
   strength. Not from strength alone.
5. **A lofted part gets the twist check** ([03-modelling.md](03-modelling.md)) before any review of its strength.
6. **A blind pick carries no recommendation**, and the key stays outside the repository until the pick is in.
7. **One `metrics.json` per run** in its `eval/` folder, with the machine's name.

## Not adopted

- A building model with a stronger model on call as an advisor: the results were good and a right task cost about
  ten times as much as plan and build.

## Not yet measured

- The middle model as the builder under a plan. It may be the right choice for parts that are half decided.
- The fallback model as reviewer, and as the designer of an undecided shape.
- More than one run of each arrangement. Every comparison above is one run.
