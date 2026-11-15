# SolidWorks playbook

How to do scripted SolidWorks work in this repo and get it right the first time. It is written so that a session
that has never driven SolidWorks can model, export and run a static study by following it, and knows when to stop and hand
the problem up. It holds what the left-arm, shoulder and torso work learned the hard way between 2026-11-05 and 2026-11-12,
with the helper code that makes the lessons hard to forget:

| File | What it is |
| --- | --- |
| [swkit.py](../swkit.py) | Modelling helpers: one instance per job, sketches in model coordinates, features that check their own result, face and edge picking by geometry, pinned exports |
| [swfea.py](../swfea.py) | Static studies: materials, fixtures, loads, contact sets, mesh, solve, nodal results, the checks on them |
| [selftest.py](../selftest.py) | Proves both against hand answers on this machine. Also the worked example: read it before writing a script |
| [sheet.py](../sheet.py) | Picture sheet of an STL from eight sides (`--together` draws several parts as one assembly), and numbers for how boxy it is. How a session sees its own part |
| [capped.py](../../pc/capped.py) | Runs a python job under a hard memory cap |

## Read in this order

1. [RULES.md](../RULES.md), "Rules" and "Hung, half-closed and orphaned instances". Not optional: one mistake there stops
   every thread on the machine.
2. [01-session.md](01-session.md): the machine, your worktree, starting and ending a job.
3. [02-com.md](02-com.md): how SolidWorks answers a python script. Ten minutes that save a day.
4. The page for the task:

| Task | Page |
| --- | --- |
| Build or change a part | [03-modelling.md](03-modelling.md) |
| Export STEP or STL, promote a part, commit CAD | [04-export.md](04-export.md) |
| Run a static study, or a study with contact | [05-fea.md](05-fea.md) |
| Decide whether a result can be trusted, and when to hand the problem up | [06-judgment.md](06-judgment.md) |
| Know when a model, a study or a report is finished: **read before every task** | [07-done.md](07-done.md) |

How well this works for a smaller model, measured: [EVAL.md](EVAL.md).

## The method, in seven lines

1. **Do the hand calculation first.** The volume of the part, the deflection of the beam, the stress in the section. A script
   result is only as good as the number you compare it with.
2. **One script, one job, one instance:** `with job() as j:`. Never reach "the running SolidWorks".
3. **Every step checks itself.** A SolidWorks call that fails returns `None` or `False` and carries on. The helpers raise
   instead; in your own calls, check the return value and the change in volume.
4. **Pick faces and edges by where they are,** never by name or index: names and order change with every rebuild.
5. **Save after every step that worked,** in `cad/_wip/<topic>/` until the part is chosen.
6. **Right numbers are the start, not the end.** [07-done.md](07-done.md) lists what a finished model, study and report
   contain; "it passes" is not on the list. Neither is stopping with tasks open: every task ends done, shown not possible, or
   blocked after three different tries.
7. **Report what you checked, not what you hope.** Give the numbers, the hand value beside them, what was excluded, and what
   you could not verify.

## Stop and hand it up

Stop **that task** and report it, with the log, instead of trying a fourth variation, when one of these holds. Each one
ends the task it happened in, never the whole job: carry on with every task it does not block
([07-done.md](07-done.md), "Do not stop early").

- an instance shows `HALF-CLOSED` in `sw_instance.py --status`, or a launch sits at the splash screen;
- the same step has failed three times in different ways;
- a study's peak stress keeps rising as the mesh shrinks and you cannot name the corner or edge that causes it;
- a solve fails with error 24 after the checks in [05-fea.md](05-fea.md);
- the result disagrees with the hand calculation by more than 20 % and you cannot say why;
- the machine is still under 8 GB free after `job(wait_s=1800)` has waited, or the job would need more than a
  450,000-node mesh;
- the task needs a decision about the design itself (a load path, a split line, a print orientation, a joint).

What still needs a stronger model or Joey is listed in [06-judgment.md](06-judgment.md).
