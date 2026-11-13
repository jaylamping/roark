# Benchmark tasks, set B

Five tasks on parts the first set ([TASKS.md](TASKS.md)) did not use. Set A measured whether a session gets the right
numbers. Set B measures what it does once the numbers are right. Same rules as set A: frame X, Y, Z in mm; printed PETG as
in `swfea.PETG` (yield 45 MPa in the layer plane, 22.5 MPa in tension across layers, 13 MPa in shear between layers);
models in `cad/_wip/sw-eval/<run>/`; scripts, `REPORT.md` and `results.json` in `tools/solidworks/playbook/eval/<run>/`.
`results.json` holds one object per task with the keys named below, `"status"` and `"notes"`. Do not claim a check you did
not run.

## B1. Model a hub from a specification

A flanged hub, one solid body, axis along Z.

- Flange: Ø60, Z 0 to 5.
- Boss: Ø26, Z 5 to 25.
- Bore: Ø10, through, on the axis.
- Six Ø4.5 holes through the flange on a Ø44 circle, the first on +X, 60 degrees apart.
- Two Ø5.5 dowel holes through the flange on a Ø30 circle, on +Y and on -Y.
- A keyway in the bore, full length: 3 wide, centred on +X, its floor 6.4 from the axis.
- A Ø4 set-screw hole through the boss wall, radial, along +Y, its axis at Z 22.6, from the bore to the outside.

Save `hub.SLDPRT`, export `hub.step` and `hub.stl`.

Keys: `volume_mm3`, `hand_volume_mm3`, `mass_g`, `bbox_mm`, `bodies`, `stl_watertight`, `spec_questions` (a list of
sentences; empty if you have none).

## B2. A wall bracket: will it hold?

One solid body.

- Wall plate: X 0 to 5, Y 0 to 40, Z 0 to 60. It is screwed to a wall at X 0 through two Ø4.5 holes along X, at Y 20,
  Z 12 and Y 20, Z 48.
- Arm: X 5 to 65, Y 15 to 25, Z 40 to 52.
- 3 mm radius fillets where the arm meets the plate, on the arm's top and bottom (the edges along Y at X 5, Z 52 and
  X 5, Z 40).

Load: 60 N straight down (-Z), spread over the top face of the last 10 mm of the arm (X 55 to 65).

Requirement: a factor of at least 2.0 on von Mises against yield, on tension across layers and on shear between layers.
How it is printed is yours to choose.

Save `wall_bracket.SLDPRT`. Give a verdict.

Keys: `hand_root_stress_mpa`, `print_orientation`, `nodes`, `peak_vm_mpa`, `layer_stress_mpa`, `layer_shear_mpa`,
`sf_yield`, `sf_layer`, `sf_shear`, `max_disp_mm`, `reaction_n`, `converged`, `verdict`.

## B3. Make it lighter

Reduce the mass of the B2 bracket as far as you can. Fixed: the two screw holes, the wall face at X 0, the load (60 N on
a top face 10 mm long and 10 mm wide whose far end is at X 65 and whose height is Z 52), and the B2 requirement. Everything
else may change. Save `wall_bracket_light.SLDPRT`. Give this at most 45 minutes.

Keys: `mass_before_g`, `mass_after_g`, `saving_pct`, `steps` (a list: what changed, mass, the three factors),
`governing` (which requirement is at its limit at the end), `sf_yield`, `sf_layer`, `sf_shear`, `print_orientation`.

## B4. A tongue in a slot

Two PETG bodies.

- Block: X -20 to 20, Y -10 to 10, Z 0 to 20, with a slot through it along Y, open at the top: X -4.1 to 4.1, Z 8 to 20.
- Tongue: X -4 to 4, Y -10 to 10, Z 8.1 to 40. It stands in the slot with 0.1 mm clearance each side and 0.1 mm above
  the slot floor. Nothing else holds it.

The block's bottom face is fixed. The tongue is pushed sideways with 80 N in +X, spread over its -X face between Z 30 and
Z 40.

Find the forces the slot walls put on the tongue and the peak stress in the block, and show that the result is valid.
Give this at most 40 minutes; if it is not solved by then, report exactly how far you got.

Keys: `hand_wall_forces_n` (two numbers), `wall_forces_n` (two numbers, from the results), `nodes`,
`how_tongue_was_stabilised`, `block_peak_vm_mpa`, `block_peak_at_mm`, `tongue_tip_disp_mm`, `reaction_n`, `valid`, `why`.

## B5. Review a colleague's report

No SolidWorks needed. This report came with a request to approve the part for printing. List everything wrong with it,
most serious first, and say what has to be redone. Put the answer in `REPORT.md` under B5 and the count in
`results.json` (`problems_found`).

> **Motor plate, static study.** PETG, printed flat on the bed (layers stacked along Z). Load: 120 N along +X on the
> motor face. Supported at the four mounting-hole walls (fixed).
>
> Hand estimate: the plate bends as a cantilever 30 mm long, 40 mm wide and 4 mm thick. I = b h³ / 12 with b = 4 and
> h = 40 gives 21,333 mm⁴, so the stress is 120 × 30 × 20 / 21,333 = 3.4 MPa.
>
> Mesh: 2.0 mm, then 1.5 mm globally (212,000 and 520,000 nodes). I ran the fine one overnight beside the forearm solve
> to save time. Peak von Mises 37.6 MPa at 2.0 mm and 41.0 MPa at 1.5 mm, a 9 % change, so it has converged. The peak is
> at the edge of one mounting hole.
>
> Reaction 96 N, close enough to the 120 N applied. Displacement 0.9 mm.
>
> Tension across the layers: the largest σx is 19.5 MPa. Factor of safety 45 / 19.5 = 2.3. Factor on von Mises
> 45 / 41.0 = 1.1, but that is at a hole edge, so I ignored it.
>
> Export: `motor_plate.stl` written; volume 1.02 against the part's 16,700 mm³, which I put down to rounding.
>
> Verdict: pass, ready to print.
