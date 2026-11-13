# Benchmark tasks, set C: design sense

Sets A and B have answers. This one does not: it measures what a session makes when the request is a look, the way
Joey asks for one. The engineering is the gate, the form is the result. Rules as in set B (frame X, Y, Z in mm, printed
PETG as in `swfea.PETG`, models in `cad/_wip/sw-eval/<run>/`, scripts, `REPORT.md` and `results.json` in
`tools/solidworks/playbook/eval/<run>/`). Here the pictures are part of the deliverable and are committed: every PNG
goes in `tools/solidworks/playbook/eval/<run>/pictures/`.

Time: 100 minutes for the whole set. Follow "Long jobs: show the work early" in [07-done.md](../07-done.md) to the
letter; the checkpoints are graded.

Pictures: `python tools/solidworks/sheet.py part.stl -o name.png` draws a part from eight sides and prints numbers for how
much of it is flat plates and sharp edges. Run it after every change of shape and **open the PNG and look at it**
before deciding the next step.

## C1. The link as it is

A forearm link for a humanoid robot arm, as an engineer would first draw it. One solid body. The joint axes run along Y.

- Elbow end: a disc Ø70, Y -4 to 4, centred on the origin, axis along Y. It bolts to a motor's output through six
  Ø3.4 holes on a Ø50 circle (the first on +X in the X-Z plane, 60 degrees apart), with a Ø30 locating bore through it.
- Beam: a box X -20 to 20, Y -15 to 15, running from Z -32 to Z -170. It runs into the rim of the disc.
- Wrist end: a fork. Two cheeks, each X -15 to 15, Z -170 to -215, one at Y 16 to 22 and one at Y -22 to -16, joined to
  the beam by a block X -20 to 20, Y -22 to 22, Z -170 to -180. A Ø8 pin hole through both cheeks along Y at X 0,
  Z -200.

Build it, save `link_boxy.SLDPRT`, export `link_boxy.stl`, make `pictures/c1_boxy.png`.

Keys: `volume_mm3`, `hand_volume_mm3`, `mass_g`, `bodies`, `shape` (the numbers `sheet.py` prints).

## C2. Make it more organic

The request, as it would arrive:

> Make this link more organic. It should look like it belongs on a humanoid arm: smooth, flowing, restrained, like it
> grew that way and was not bolted together from plates. Nothing boxy, nothing sticking out. It still has to do its
> job.

Fixed, to be measured on the finished solid:

- the elbow mounting face: the flat ring on Y -4 between Ø30 and Ø62, the six Ø3.4 holes and the Ø30 bore, and a
  Ø7 clear cylinder 10 mm long in front of each hole on the Y +4 side for a screw head and a driver;
- the wrist: the Ø8 pin axis at X 0, Z -200 along Y, the two inner cheek faces at Y ±16 flat over at least Ø16 round
  the pin, at least 5 mm of material round the pin hole, and a clear slot between the cheeks from Z -183 downward for
  the part that swings there (it sweeps a Ø30 cylinder about the pin axis);
- a straight clear passage of Ø6 for a cable from the elbow end to the wrist end. Where it runs is yours to choose; it
  need not be enclosed, but the cable must not hang outside the form.

Requirements:

- 60 N at the wrist pin in +X, in -X and in +Y (three cases, bearing on the pin holes), with the elbow face held: a
  factor of at least 2.0 on von Mises, on tension across layers and on shear between layers, for the print direction
  you choose.
- Mass no more than the boxy link's.
- Printable on a 256 mm bed in PETG, one piece, no enclosed cavity; say how it lies on the bed and where supports go.

Everything else is yours: the section, the taper, how the ends grow out of the middle, where material is and is not.

Deliver:

1. `restate.md` before any modelling: the five lines 07-done.md asks for, plus one sentence saying what "organic"
   means for this part in your own words, and three things you will not do.
2. `pictures/checkpoint_01.png` within 20 minutes of starting C2: the whole form, crude. Then a checkpoint picture at
   the end of each stage, numbered, with one line in `REPORT.md` on what is still missing against the request.
3. At least two different ideas for the form (not two sizes of one idea), each as a quick model with a picture
   (`pictures/idea_a.png`, `idea_b.png`), and a sentence on why you chose one.
4. `link_organic.SLDPRT`, `link_organic.step`, `link_organic.stl`, and `pictures/c2_before_after.png` made with both
   STLs in one call so they share a scale.
5. The checks: every fixed item above measured, mass, the three load cases with the three measures in the chosen print
   direction (one mesh under 200,000 nodes is enough; say what is not converged), exports checked.
6. `DESIGN.md`, at most 25 lines: the idea in one sentence; what you tried and dropped, with why; what you would still
   change with another hour; the part of it you are least happy with, honestly.

Keys: `mass_before_g`, `mass_after_g`, `shape_before`, `shape_after`, `print_orientation`, `sf_yield`, `sf_layer`,
`sf_shear` (the lowest of the three cases, each), `governing`, `fixed_items_ok` (true or false, with the measurements in
the report), `ideas_tried`, `checkpoints` (a list: time, picture, what was missing), `minutes`.

## How set C is graded

1. **The gate.** Fixed items intact, one body, watertight, requirement met, mass not above the boxy link. A part that
   fails the gate is not ranked.
2. **The process.** Restatement written first; first picture inside 20 minutes; two ideas that really differ; each
   checkpoint compared with the request and not with the previous version.
3. **The form, blind.** Joey sees the before-and-after sheets of all runs labelled only with letters and ranks them.
   His ranking is the result. The shape numbers are reported beside it, as a check on whether they mean anything.
4. **Honesty.** Whether `DESIGN.md` names the same weak spot a reviewer finds.
