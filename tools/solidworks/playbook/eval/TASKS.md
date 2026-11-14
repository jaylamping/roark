# Benchmark tasks

Seven tasks that cover what SolidWorks work in this repo asks for, from routine to hard. They are used to measure how well
a session does with the playbook ([EVAL.md](../EVAL.md)). Each has an answer that can be checked without trusting the
session's own word.

Frame: X, Y, Z in mm. Material: printed PETG as in `swfea.PETG` (yield 45 MPa in the layer plane, 22.5 MPa in tension
across layers). Work in `cad/_wip/sw-eval/<run>/` (gitignored). Put your scripts, `REPORT.md` and `results.json` in
`tools/solidworks/playbook/eval/<run>/`.

`results.json` holds one object per task, with the keys named below (numbers as numbers, `null` for what you could not
get) plus `"status"`: `"done"`, `"partial"` or `"failed"`, and `"notes"`. `REPORT.md` says, per task: what you did, the
hand calculation, the checks you ran with their numbers, what you could not verify, and how long it took. Do not claim a
check you did not run.

## T1. Model a bracket from a specification

An L-shaped motor bracket, one solid body.

- Base plate: X 0 to 80, Y 0 to 50, Z 0 to 6.
- Upright: X 0 to 6, Y 0 to 50, Z 6 to 46.
- A 4 mm radius fillet in the inside corner where the upright meets the top of the base (the edge along Y at X 6, Z 6).
- Four Ø5.5 holes through the base at (X, Y) = (25, 10), (25, 40), (65, 10), (65, 40).
- A Ø22 bore through the upright, axis along X, centred at Y 25, Z 28.
- Four Ø3.4 holes through the upright on a Ø31 circle about the bore axis, at 45, 135, 225 and 315 degrees.
- 5 mm radius rounds on the two vertical corners of the base at X 80, and on the two top corners of the upright (the edges
  along X at Z 46).

Save `bracket.SLDPRT`, export `bracket.step` and `bracket.stl`.

Keys: `volume_mm3`, `hand_volume_mm3`, `mass_g`, `bbox_mm` (six numbers), `bodies`, `stl_watertight`, `stl_volume_mm3`.

## T2. Change an existing part

Open the saved `bracket.SLDPRT` from T1 (do not rebuild it from its script) and save the result as `bracket_b.SLDPRT`:

- a Ø10 counterbore, 3 mm deep, from the top of the base (Z 6) on each of the four base holes;
- a slot through the base, 20 long and 6 wide overall with round ends, centred at X 45, Y 25, its length along X.

Keys: `volume_mm3`, `hand_volume_mm3`, `counterbore_floor_z_mm`, `bodies`.

## T3. Static study with a verdict

The T1 bracket (`bracket.SLDPRT`) is screwed down through its four base holes and carries a motor in the bore. The motor
pulls on the bore with 150 N along +X. The bracket is printed with the base on the bed (layers stacked along Z). The
requirement is a factor of safety of at least 2.0 on von Mises against yield and on tension across the layers.

Run the study, run the checks the playbook asks for, and give a verdict.

Keys: `hand_root_stress_mpa`, `el_mm`, `nodes`, `peak_vm_mpa`, `peak_at_mm`, `layer_stress_mpa`, `sf_yield`, `sf_layer`,
`max_disp_mm`, `reaction_n`, `converged` (true or false), `convergence_rows`, `verdict` (`"pass"` or `"fail"`).

## T4. The same study on a variant

Build `bracket_sharp.SLDPRT`: the T1 bracket without the 4 mm inside-corner fillet. Run the T3 load case on it and report
what the stress in the inside corner is and whether the part meets the requirement.

Keys: `convergence_rows`, `converged`, `reported_stress_mpa`, `how_judged` (a sentence), `verdict`.

## T5. Make it pass

If the T3 bracket does not meet the requirement, change the design so that it does, and show it with a study. Everything is
open: geometry, and how it is printed. The hole positions, the bore and the outer footprint (X 0 to 80, Y 0 to 50, Z 0 to
46) are fixed by the parts it mates with, and the mass may grow by at most 10 %. Save `bracket_c.SLDPRT`.

Keys: `change` (a sentence), `mass_g`, `mass_growth_pct`, `sf_yield`, `sf_layer`, `print_orientation`, `verdict`.

## T6. Contact between two bodies

A PETG block, X -20 to 20, Y -15 to 15, Z 0 to 20, with a Ø10.2 hole through it along Y, centred at X 0, Z 10. A Ø10 steel
pin, 50 long, sits through the hole, centred, and sticks out 10 mm each side. The block's bottom face is fixed. Each end
of the pin is pulled up with 250 N (500 N in +Z in all). The pin is free in the hole: it carries its load to the block
through contact only.

Find the peak bearing stress the pin puts on the hole, and show that the result is valid.

This is the hard one. Give it at most 40 minutes; if it is not solved by then, stop and report exactly how far you got and
what failed.

Keys: `hand_bearing_mpa`, `nodes`, `solver`, `how_pin_was_stabilised`, `peak_contact_vm_mpa`, `block_peak_at_mm`,
`pin_rise_mm`, `reaction_n`, `valid` (true or false), `why`.

## T7. Diagnose

No SolidWorks needed. For each case say what is happening, what you do next, and what you must not do. Put the answers in
`REPORT.md` under T7.

a. You are about to launch. `python tools/solidworks/sw_instance.py --status` prints:

```
    pid   age_s threads windows private_MB answers
  20948    7890      61       3       9120   False  busy: launches wait for it
   2536    2710       1       0       3610   False  HALF-CLOSED: stalls every launch
```

b. A contact study with 796,000 nodes and the direct sparse solver fails with error 24 after 143 seconds. The benchmark log
ends at "GLOBAL-STIFFNESS-MATRIX-DECOMPOSITION-Start". Free memory went from 26 GB to 12 GB in the last eleven seconds.

c. A fit check of an exported STL against its mating part reports that the whole part is offset by (41.5, 0, 12.0) mm. The
native part is in the right place. The export was made on a machine set up last week.

d. A stress peak of 61 MPa sits on the edge of a fixed face. At element sizes 2.0, 1.5 and 1.0 mm it reads 38, 47 and 61.
The requirement is a factor of safety of 2 against 45 MPa.

e. Your FEA script has been silent for 25 minutes. `--status` shows your instance as `busy`. Another thread asks whether
SolidWorks is hung and suggests you restart it.
