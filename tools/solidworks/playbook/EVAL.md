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
- **Depth can mostly be written down.** After the first set, what separated Fable from Sonnet was how far each went
  once the numbers were right. Those habits became required steps ([07-done.md](07-done.md)). On a fresh set built to
  test them, Sonnet did nearly every one, level with Fable on four tasks of five and faster.
- **What is left is judgment under temptation.** On the fifth task both saw a stress that kept climbing with the mesh.
  Sonnet reported the last value and passed the part; Fable would not, and failed it. The rule was on the page.
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

| | Sonnet + playbook ([sonnet-b](eval/sonnet-b/)) | Fable + playbook ([fable-b](eval/fable-b/)) |
| --- | --- | --- |
| Wall time | 62 min, every limit kept | about 160 min over two sessions (the first died), two task limits overrun |
| B1 volume against hand 21,865.51 | 21,865.54 | 21,865.54 |
| B1 hidden problems found (2 planted) | 2, plus two more questions | 2, plus two more questions |
| B2 hand root stress (13.75 MPa) | 13.75 | 13.75 |
| B2 von Mises, printed on its side | 19.5 MPa, factor 2.31 | 19.6 MPa, factor 2.30 |
| B2 other print directions | both shown to fail (1.12 and 1.79) | both shown to fail (1.12 and 1.75 to 1.95) |
| B2 second support | yes | yes |
| B2 layer measures at the square side edges | noticed they rise with the mesh, reported the finest value | showed they double with every halving, rounded the edges to get a real number: 1.88 to 2.08 |
| **B2 verdict** | **pass** | **fail** |
| B3 mass, from 22.7 g | 7.8 g, 66 % less | 5.7 g, 75 % less |
| B3 what stopped it | von Mises 2.08 | strut buckling by hand (2.02), a check the task did not ask for; caught two lighter candidates failing under the load pad, inside the mask |
| B4 wall forces against hand 180.8 / 100.8 N | 183.3 / 103.3 | 183.6 / 102.5 |
| B4 proof it is contact | reversed tiny load | forward tiny load; its reversed run did not converge and was marked invalid |
| B4 block peak called singular, not a design number | yes | yes |
| B4 largest solve | 149,700 nodes | 244,072 nodes, 13 GB, which pushed another thread's solve off the machine |
| B5 planted flaws found (8) | 8, plus 6 more | 8, plus 7 more |

**What set B shows.** On four of five tasks the two are level, and Sonnet was faster and better behaved: it kept every
time limit and every solve small. The difference is B2. Both saw the same numbers. Sonnet reported the finest value of
a stress that was still climbing and passed the part; Fable refused to read a number off a sharp edge, changed the
geometry until the number meant something, and failed it. The playbook already said that a peak which keeps rising is not a
stress ([05-fea.md](05-fea.md)); Sonnet read it and still passed the part. 07-done.md now makes it a gate: no verdict
of pass on a measure that is still moving. That is the remaining gap: not knowledge, and not effort, but
holding a rule against a convenient answer. B3 shows the same thing from the other side: Fable went looking for the
failure the requirement did not name.

The grading keys for sets B to D are kept outside the repository so that later runs cannot read them.

## Set C: design sense ([TASKS_C.md](eval/TASKS_C.md))

A boxy forearm link and the request "make this more organic, like it grew that way", with the mounting faces, the
loads and the mass fixed. The engineering is a gate; the form is judged by Joey from picture sheets.

| | Sonnet + playbook ([sonnet-c](eval/sonnet-c/)) | Fable + playbook ([fable-c](eval/fable-c/)) |
| --- | --- | --- |
| Wall time, limit 100 min | 92 min | 71 min, 27 of them waiting behind other sessions' solves |
| Mass, from 261 g | 160 g | 137 g |
| Lowest factor (need 2.0) | 3.46, shear between layers, reported as "not shown" because it still moved | 2.58, shear between layers, two meshes within 5 to 7 % |
| Fixed items intact | yes, checked on the export | yes, checked on the export |
| First picture inside 20 minutes | yes, at 6 | yes, at 18, drawn from the section table because SolidWorks would not launch |
| Ideas that differ in kind | a waisted strap, a flat leaf | a bone, a wishbone |
| Section through the shaft | rounded rectangle; the round loft pinched and was dropped after six tries | oval; the same loft pinched, cured by drawing each section as two open curves |
| Sharp edge per root of area (boxy 12.3) | 7.9 | 3.4 |
| Its own verdict on the form | "a smooth flat strap, less boxy more than grown" | "a bone"; names the neck crease under the lower screws as the weak spot |
| Joey's pick ([sheet](eval/fable-c/pictures/c2_before_after.png)) | | **this one** |

Both hit the same wall, a loft that pinches when its sections change shape. One stopped at a form it knew was short of
the request and said so; the other found why and got through. The cure is now in [03-modelling.md](03-modelling.md),
and the same task run again by Sonnet with it is the measure of whether a lesson written down is a lesson learned.
The pick was not fully blind: the card that asked for it carried a recommendation.

## Set D: stress ([TASKS_D.md](eval/TASKS_D.md))

A mount from a need with no drawing; a split bearing housing whose specification has three planted errors, with
contact and screws; six plates from a table with bad rows, then a change of mind to be made by editing.

| | Sonnet + playbook ([sonnet-d](eval/sonnet-d/)) | Fable + playbook ([fable-d](eval/fable-d/)) |
| --- | --- | --- |
| Time on the tasks, limit 210 min | 90 min (39, 31, 20) | 61 min (13, 34, 14) |
| D1: the 60 mm board in a 50 mm envelope (a real contradiction in the task) | caught; tilted the board 41 degrees to fit, which rests on the tall parts sitting in the middle of the board | caught; built flat, 5 mm over each side, and reported the envelope as not met |
| D1 mass, parts | 23 g, one piece | 11 g, one piece |
| D1 board out with the mount on the rail | yes, four M3 screws | yes, four M3 screws into inserts |
| D1 ideas that differ | two, the second a sketch only | three, the second a crude model, the third on paper |
| D1 study | one mesh, not converged, said so | three meshes; one measure still moving, reported as "not shown" |
| D2 planted errors found (3) | 3, plus 4 more | 3, plus 3 more |
| D2 what was built for the overlapping counterbores | left overlapping, as a figure of eight | screws moved apart, 1.0 mm between |
| D2 fit for a ±0.15 printer | seat 52.0, split gap 0.6 | seat 52.15, each face set back 0.4, gap 0.2 to 1.1 after clamping |
| D2 screw load along the load, hand 75 N | 75.2 | 74.2 to 74.9 on three meshes |
| D2 screw load across the load | 45 to 51 N against a hand 37.5, "not explained", case marked not shown | 67 N in total; found the ring wedges under one half and redid the hand value: 75.7 |
| D2 contact proof | bonded twin, 24 times stiffer | 1 N across the clearance: 0.077 mm against 0.0005 bonded |
| D2 lowest factor | 8.8, shear between layers | 5.85, shear between layers |
| D2 what the study leaves out | head-edge peak named as not shown safe | screw preload: larger than the service load, factor 2.0 at about 285 N per screw |
| D3 bad rows caught before building (P1, P2, P4) | all | all |
| D3 the plate that cannot be built (P4) | moved the hole circle inward, from 58 to 49 | kept the hole circle, which mates with something, and grew the disc to 70 |
| D3 problems the change itself made (P3 holes 0.3 mm apart, chamfer into counterbores) | both caught | both caught |
| D3 volumes against hand, twelve parts | all equal | all equal |
| D3 edited, not rebuilt | yes | yes, shown by feature IDs before and after |

**What set D shows.** The checks hold up under stress: neither model built a broken part, both caught every planted
error and the two that the change request created, and care did not drift between the first plate and the twelfth.
The gap is again in what happens at an unexplained number and at a choice. Sonnet met a screw load it could not
explain and marked the case "not shown", which is the honest answer the playbook asks for; Fable chased it to the
cause. Sonnet resolved two impossible requirements by changing the thing a neighbouring part depends on (a bolt
circle, a board attitude that leans on an assumption); Fable changed the thing nothing else depends on and said which
requirement it gave up. And Fable named the load nobody asked about, the tightening of the screws.

The two answers to D1 are a real difference of opinion, not a right and a wrong: one keeps the envelope, the other
keeps the design simple. That choice is Joey's.

## What each run changed in the playbook

| Run | Changes |
| --- | --- |
| sonnet-playbook | Nine helper bugs fixed (reactions, per-face loads, materials matching, stale faces, the hidden solver prompt, error 24 after an unsaved close) |
| fable-playbook | Screwed-down supports, partial-face loads, pad placement, study order on multi-body parts, print-direction table, `max_nodes` |
| sonnet-bare | Confirmed what the playbook saves; exposed the rigid-load error |
| t3-load-check | Load placement, second load model, the mask warning, the harmless excessive-displacement prompt |
| sonnet-b | Study names, three sizes in `converge()`, four studies per instance, section forces, twin-model check, exclusion distance at a fixed hole |
| fable-b | The heavy-solve lock, one refinement at a time, the unanswered contact-convergence prompt, which contact proof fits which joint, buckling of lightened parts |
| sonnet-c, fable-c | Lofts whose sections change shape, a point-in-solid check (`sheet.inside`), a crop for close-ups, one launch per job when the clock matters |
| sonnet-d, fable-d | Changing a saved part (`set_dim`, `redraw_circles`), screws and clamped joints, results per body (`summary(mask=)`, `converge(mask=)`, shear in `converge()`), the proof for a body seated both sides, a launch that waits (`job(wait_s=)`), assembly pictures (`sheet.py --together`), `call()` on members that return objects, the node-count rule |

## What still needs the strongest model, or Joey

- **Design decisions:** a load path, a split line, a joint, how something should look. The benchmark does not test
  these, and [06-judgment.md](06-judgment.md) still hands them up.
- **Writing the playbook itself.** Every correction above came from comparing runs and asking why they differed.
- **Long open-ended modelling** (an organic shell, a whole link) is untested. The early check-in and time budgets in
  07-done.md are the guard; they have not been exercised on a multi-hour job.
- **Contact models at the machine's limit** (400,000 nodes, many bodies) were not in any set.
- **Which requirement to give up** when two cannot both be met. Set D shows the smaller model picks the one a
  neighbouring part depends on more often; [06-judgment.md](06-judgment.md) hands the choice up.

## Limits of this measurement

One run per model per set, on small parts, graded by the author of the playbook. The model that served the first
Sonnet run could not be confirmed afterwards; later runs reported their own model id. Set B had the corrected
playbook, so set A and set B are not a before-and-after of the same tasks. The Fable run of set B was done by two
sessions, the second picking up the first one's files. Opus has not been run.

## Running it on another model

1. A fresh session with its own worktree, told to read [README.md](README.md) and do one task set under a run name.
2. Forbid it from opening other runs' folders; ask it to report its model id, times, failed runs and playbook problems.
3. Grade `results.json` against the hand values in the task file and the table above.
4. Fix what it tripped on in the playbook or the helpers, not in the session.
5. Keep one run without the playbook as a control: it is the only thing that catches the playbook being wrong.
