# How well the playbook works, measured

The question: can a smaller model do scripted SolidWorks work as well as the strongest one, given this playbook and the
helpers? Tested on holly-pc on 2026-11-13 with two task sets, each run a fresh session in its own worktree that was
not allowed to read any other run's folder. Every number below is in the run's `results.json` and `REPORT.md` under
[eval/](eval/).

## Short answer

- **For routine work, yes.** With the playbook Sonnet models, edits, exports and analyses to the same numbers as Fable,
  within about 2 %, in a similar time.
- **The playbook is worth about a third of the time and nearly all of the failed runs.** Sonnet without it finished the
  same tasks in 91 minutes with about 17 crashed or wrong runs; with it, 55 minutes.
- **Depth can be written down.** After the first set, what separated Fable from Sonnet was how far each went once the
  numbers were right. Those habits became required steps ([07-done.md](07-done.md)). On a fresh set built to test
  them, Sonnet did every one: it found both problems hidden in a drawing, all eight flaws planted in a report (and six
  more), chose a print direction and showed the others fail, tried a second support, and took 66 % off a part's mass
  while holding the requirement.
- **A playbook can make every model wrong together.** Both playbook runs of the first set, Fable's included, passed a
  bracket that fails. The playbook steered them to a rigid load; the run without the playbook got it right. That is the
  strongest argument for keeping the benchmark and a no-playbook control beside the playbook.

## Set A: seven tasks ([TASKS.md](eval/TASKS.md))

Model a bracket, change it, run a static study, the same on a sharp-cornered variant, make it pass, a pin-in-hole
contact study, five diagnoses.

| | Sonnet + playbook | Fable + playbook | Sonnet, no playbook |
| --- | --- | --- | --- |
| Run folder | [sonnet-playbook](eval/sonnet-playbook/) | [fable-playbook](eval/fable-playbook/) | [sonnet-bare](eval/sonnet-bare/) |
| Wall time | 55 min | 45 min | 91 min |
| Tasks done | 7 of 7 | 7 of 7 | 7 of 7 |
| Failed or wrong runs on the way | not counted | not counted | about 17 |
| T1 volume, hand 32,974.02 mm³ | 32,974.02 | 32,974.02 | 32,976.08 (2 mm³ off, unexplained) |
| T3 peak von Mises, MPa | 15.52 | 15.78 | 18.57 |
| T3 tension across layers, MPa | 10.19 | 10.20 | 16.13 |
| T3 factor on layers (need 2.0) | 2.21, pass | 2.21, pass | **1.40, fail** |
| T3 displacement, mm | 2.355 | 2.361 | 2.743 |
| T4 sharp corner recognised as singular | yes | yes | yes |
| T6 pin rise, mm | 0.1285 | 0.1276 | 0.127 |
| T6 contact pressure, MPa (Hertz 6.8) | 6.1 to 6.5 | 6.26 | 6.55 |

**The T3 disagreement** ([t3-load-check](eval/t3-load-check/CHECK.md)). The two playbook runs put the 150 N on the bore
as a rigid remote load. That makes the bore wall a rigid body and stops the 2.8 mm ligaments to the motor-screw holes
flexing. Nine solves settled it: rigid load 10.4 MPa at the hole rims; even force on the bore 16.0; load on the screw
holes, where a motor really puts it, 15.4; by hand 5.5 × 3 = 16.5. The bracket fails at about 1.4. No mask or mesh hid
it. The playbook now says where a load belongs, requires a second load model beside small features, and asks for a
hand value at every small hole in a stressed wall.

**What Fable did that Sonnet did not, in set A.** A second support model (bonded washers) to show the result did not
hang on the fixture; interlayer shear; a table of all three print directions (side printing takes the layer factor
from 2.2 to 4.6); contact pressure integrated back to the load; and it caught a study that had silently solved the
wrong problem. None of it needed knowledge Sonnet lacked. All of it is now a required step.

## Set B: five depth tasks ([TASKS_B.md](eval/TASKS_B.md))

A hub from a specification with two hidden problems; a wall bracket with the print direction left open; make it
lighter; a tongue in a slot held only by contact; review a colleague's report with eight planted flaws.

| | Sonnet + playbook ([sonnet-b](eval/sonnet-b/)) | What the task was looking for |
| --- | --- | --- |
| Wall time | 62 min | about two hours allowed |
| B1 volume against hand | 21,865.54 against 21,865.51 | every dimension measured on the solid: done |
| B1 hidden problems found | 2 of 2 (dowel holes run 0.75 mm under the boss; 0.4 mm wall over the set screw), plus two more questions | 2 |
| B2 hand root stress | 13.75 MPa, 19.4 with the fillet factor | 13.75 |
| B2 result | von Mises 19.5 MPa, factor 2.31; passes only printed on its side | a chosen direction with the other two shown |
| B2 other directions | along X: layer factor 1.12, fail; along Z: shear factor 1.79, fail | table of three measures by direction |
| B2 second support | yes: face fixed 19.5, hole walls fixed 18.4 | yes |
| B2 thinnest margin | a 20 % higher load gives 1.93 | named, with a number |
| B3 mass | 22.7 g to 7.8 g, 66 % less, 12 steps, four rejected | keep going until a requirement stops it |
| B3 governing at the end | von Mises 2.08 with the worse support | one requirement at its limit |
| B4 wall forces against hand 180.8 / 100.8 N | 183.3 / 103.3 (1.4 % and 2.5 %) | within 5 % |
| B4 proof it is contact, not a bond | reversed load parts the bodies; pads carry 0.5 % | yes |
| B4 honesty about the peak | block peak 41 MPa called singular and not a design number; a radius asked for | yes |
| B5 planted flaws found | 8 of 8, plus 6 more, ranked | 8 |

The Fable run of set B stopped with a service error after about 90 minutes and left no result, so set B has no
comparison yet. It also ran one 13 GB solve that pushed another thread's solve out of memory; the heavy-solve lock in
[05-fea.md](05-fea.md) comes from that.

## What each run changed in the playbook

| Run | Changes |
| --- | --- |
| sonnet-playbook | Nine helper bugs fixed (reactions, per-face loads, materials matching, stale faces, the hidden solver prompt, error 24 after an unsaved close) |
| fable-playbook | Screwed-down supports, partial-face loads, pad placement, study order on multi-body parts, print-direction table, `max_nodes` |
| sonnet-bare | Confirmed what the playbook saves; exposed the rigid-load error |
| t3-load-check | Load placement, second load model, the mask warning, the harmless excessive-displacement prompt |
| sonnet-b | Study names, three sizes in `converge()`, four studies per instance, section forces, twin-model check, exclusion distance at a fixed hole |

## What still needs the strongest model, or Joey

- **Design decisions:** a load path, a split line, a joint, how something should look. The benchmark does not test
  these, and [06-judgment.md](06-judgment.md) still hands them up.
- **Writing the playbook itself.** Every correction above came from comparing runs and asking why they differed.
- **Long open-ended modelling** (an organic shell, a whole link) is untested. The early check-in and time budgets in
  07-done.md are the guard; they have not been exercised on a multi-hour job.
- **Contact models at the machine's limit** (400,000 nodes, many bodies) were not in either set.

## Limits of this measurement

One run per model per set, on small parts, graded by the author of the playbook. The model that served the first
Sonnet run could not be confirmed afterwards; later runs reported their own model id. Set B had the corrected
playbook, so set A and set B are not a before-and-after of the same tasks. Opus has not been run: Sonnet did not fall
short enough to need it.

## Running it on another model

1. A fresh session with its own worktree, told to read [README.md](README.md) and do one task set under a run name.
2. Forbid it from opening other runs' folders; ask it to report its model id, times, failed runs and playbook problems.
3. Grade `results.json` against the hand values in the task file and the table above.
4. Fix what it tripped on in the playbook or the helpers, not in the session.
5. Keep one run without the playbook as a control: it is the only thing that catches the playbook being wrong.
