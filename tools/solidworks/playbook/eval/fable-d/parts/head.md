# Benchmark run fable-d: set D (stress), three tasks

Run on holly-pc, 2026-11-13, worktree `J:/code/roark-wt/sw-eval-fable-d` at `e36fa00`, SolidWorks 2026 through
`swkit.job()` (its own instance for every script, eleven launches, none left running). Model id: `claude-fable-5-2`
as configured for this session (I had no tool to read back which model served each turn, so it may differ).

**I kept to the reading rule:** under `tools/solidworks/playbook/eval/` I opened `TASKS_D.md` and nothing else, and I
did not open `playbook/EVAL.md`. Two helper pages point into `eval/` (05-fea.md cites `eval/t3-load-check/CHECK.md`
and `eval/sonnet-b/b4_tongue.py`); I did not follow them and wrote the section-force fit myself.

Everything in `results.json` is collected by `make_results.py` from the JSON each script wrote; no number in it was
retyped. Models are in `cad/_wip/sw-eval/fable-d/` (plates in its `d3/` folder), not committed.

## Times

| Task | Limit | Used | Clock |
| --- | --- | --- | --- |
| D1 | 60 min | about 13 min | 08:42 restate, 08:44 first models (the 20-minute checkpoint, at minute 2), 08:46 four studies done, 08:49 pictures looked at, 08:52 convergence done; report text about 3 min later |
| D2 | 90 min | about 34 min | 08:52 start, 08:52:31 models built, 08:54 fit check and pictures (checkpoint, minute 3), 09:05 two load cases and two proofs, 09:15 three meshes, 09:20 second support; report text about 5 min |
| D3 | 60 min | about 14 min | script and table check written between 08:57 and 09:01 while D2 solved (about 8 min), part one 09:20:30 to 09:21:03, its table written 09:21:50, part two 09:21:57 to 09:23:40 (two failed launches inside that); report text about 3 min |

All three inside their limits; nothing was cut for time. Setup and reading the playbook took 08:37 to 08:42 before D1.
The checkpoints were made and looked at, but not committed one by one: the brief asks for one commit at the end.

## Runs that failed before it worked

| Where | What happened | Cause | Cost |
| --- | --- | --- | --- |
| D3 part two, launch 1 | `Member not found` on `GetFirstDisplayDimension` | `swkit.call()` decides "method or property" with `callable()`, but a late-bound COM object is itself callable, so for a member that returns an object it calls the result. A helper fault: item 13 at the end | one launch, 25 s |
| D3 part two, launch 2 | `'int' object is not callable` | my own replacement for `call()` then called a plain value (`GetID`) | one launch, 16 s; the third launch worked |
| D3 table check (no SolidWorks) | stopped on "P3_b still 0.3 mm" | my rule looked only at the thinnest wall, and P3_b had two problems at once (chamfer and ring A); now each wall is tested | none |
| D3 table, STL column | read "NO" for all six | my box tolerance (0.02 mm) against a faceted circle, which falls up to 0.08 mm short of the true diameter across Y; all six were watertight with one shell and the right volume | none |
| D2 fit check | screw engagement printed 6.9 mm, then a crash | a wrong formula of mine (6.25 is right), then a typing slip | none (no SolidWorks) |
| D1 plain-section check | 0.97 MPa against 1.235 by hand | `r.average()` on a surface in bending: item 1 at the end | none |
| D1 and D2 predictions | displacement off by 4.7 and 3.6 times | not failures of a run: the stop the playbook asks for, each explained in its section | a few minutes each |

No study failed to mesh or solve, no solver question appeared, no instance hung. A partial `P1_b.SLDPRT` of my own
from the first failed launch was deleted before the rerun.

