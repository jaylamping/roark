# T3 load model check

Why two runs of benchmark task T3 gave a layer factor of 2.21 (pass) and a third gave 1.40 (fail) on the same bracket.

**Answer: the rigid remote load really lowers the stress at the Ø3.4 holes. No mask and no mesh size hid it.** With the
bore wall held rigid the rim of the Ø3.4 holes reads σz 10.4 MPa; with the same 150 N as an even traction on the bore wall
it reads 16.0 MPa, and with the load on the four Ø3.4 hole walls 15.4 MPa. All three are converged at a 0.8 mm control.

## Setup

- Part: `bracket.SLDPRT` of run fable-playbook, copied to `cad/_wip/sw-eval/check/`; volume 32,974.02 mm³ (hand 32,974).
- Four Ø5.5 base hole walls fixed. 150 N along +X. PETG (`swfea.PETG`). Layers along Z, so the layer measure is σz.
- Mesh: global 3 mm, one control on the four Ø3.4 hole walls at 0.8, 0.4, 0.25 mm, nothing else refined. The three cases
  use the same three meshes, so they differ in the load only.
- a: rigid remote load at the bore centre (3, 25, 28), carried rigidly to the bore wall (as `fable-playbook/case.py`).
- b: 150 N in total along +X as an even traction on the bore wall (`AddForce2` against the Right Plane, as
  `sonnet-bare/t3_study.py`).
- c: 150 N in total along +X shared by area over the four Ø3.4 hole walls, bore free.
- "Overall" peaks exclude only nodes within 6 mm of the fixed hole walls (the same distance at every mesh). "Hole rim"
  is every node of the upright within 1.2 mm of a Ø3.4 hole wall.
- Script [check.py](check.py), rows [rows.json](rows.json), solver direct sparse, nodal results in
  `cad/_sim/sw-eval/check/CHK_<case>_<control>.npz`.

## Results

| Case | Control mm | Nodes | Reaction Fx N | Max disp mm | Peak von Mises MPa, at | Peak σz MPa, at | Hole rim σz MPa, at | Hole rim von Mises MPa, at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | 0.8 | 28,216 | -150.00 | 2.345 | 13.92 (10, 30.9, 6) | 10.60 (0, 34.4, 16.5) | 10.60 (0, 34.4, 16.5) | 10.92 (0, 15.6, 16.2) |
| a | 0.4 | 59,363 | -150.00 | 2.345 | 14.43 (8.8, 25.7, 6.2) | 11.52 (0, 26.4, 17.1) | 10.40 (0, 15.7, 16.8) | 11.07 (6, 15.6, 16.4) |
| a | 0.25 | 116,213 | -150.00 | 2.346 | 14.29 (8.7, 33.1, 6.2) | 11.76 (0, 23.6, 17.1) | 10.43 (0, 15.7, 16.7) | 11.07 (6, 15.6, 16.5) |
| b | 0.8 | 28,216 | -150.00 | 2.738 | 17.88 (6, 15.7, 17.4) | 16.03 (0, 37.7, 17.1) | 16.03 (0, 37.7, 17.1) | 17.88 (6, 15.7, 17.4) |
| b | 0.4 | 59,363 | -150.00 | 2.738 | 18.54 (5.8, 34.3, 17.3) | 16.38 (0.2, 12.3, 17.1) | 16.38 (0.2, 12.3, 17.1) | 18.54 (5.8, 34.3, 17.3) |
| b | 0.25 | 116,213 | -150.00 | 2.739 | 18.57 (5.9, 15.7, 17.3) | 16.02 (0.1, 12.3, 16.9) | 16.02 (0.1, 12.3, 16.9) | 18.57 (5.9, 15.7, 17.3) |
| c | 0.8 | 28,216 | -150.00 | 2.823 | 17.38 (5.5, 15.7, 17.3) | 15.22 (0, 15.7, 17.4) | 15.22 (0, 15.7, 17.4) | 17.38 (5.5, 15.7, 17.3) |
| c | 0.4 | 59,363 | -150.00 | 2.824 | 18.63 (5.8, 15.7, 17.5) | 15.59 (0.2, 34.3, 17.3) | 15.59 (0.2, 34.3, 17.3) | 18.63 (5.8, 15.7, 17.5) |
| c | 0.25 | 116,213 | -150.00 | 2.824 | 18.81 (5.8, 34.3, 17.5) | 15.39 (0.1, 34.3, 17.3) | 15.39 (0.1, 34.3, 17.3) | 18.81 (5.8, 34.3, 17.5) |

In case a the overall σz peak at 0.4 and 0.25 mm (11.5, 11.8 MPa) sits on the lower edge of the rigidly loaded bore
(Y 24 to 26, Z 17.1) and climbs with the mesh: it is the edge of the rigid patch, which fable-playbook's 1.5 mm bore mask
rightly drops. The fillet peak (13.9 to 14.4 MPa von Mises) is where the rigid case puts its von Mises maximum.

### What the masks and the mesh did

| Case | Control mm | Rim σz on X 0 | on X 6 | Rim σz over 0.05 mm off the wall | σz left by `Result.away()` (6 mm from fixture and load faces), at | Rim nodes that mask keeps | σz left by the 1.5 mm bore mask | Back face Z 8 to 12 σz | Section Z 12 back face mean (hand 8.0) | σz within 1.5 mm of the bore |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | 0.8 | 10.60 | 0.43 | 8.29 | 10.23 (0, 24.6, 10.6) | 1,424 of 5,875 | 10.60 | 10.23 | 8.09 | 10.26 |
| a | 0.4 | 10.40 | 0.49 | 8.89 | 10.17 (0, 22.1, 10.1) | 7,633 of 29,829 | 10.40 | 10.17 | 7.78 | 11.52 |
| a | 0.25 | 10.43 | 0.51 | 9.26 | 10.16 (0, 25.1, 10.3) | 19,797 of 82,439 | 10.43 | 10.16 | 7.84 | 11.76 |
| b | 0.8 | 16.03 | 2.06 | 12.32 | 12.60 (0, 37.5, 16.3) | 1,424 of 5,875 | 16.03 | 9.35 | 7.92 | 7.26 |
| b | 0.4 | 16.05 | 2.43 | 13.61 | 13.63 (0, 37.6, 16.5) | 7,633 of 29,829 | 16.38 | 9.39 | 7.78 | 7.35 |
| b | 0.25 | 16.02 | 2.49 | 14.42 | 13.93 (0, 37.6, 16.6) | 19,797 of 82,439 | 16.02 | 9.35 | 7.86 | 7.35 |
| c | 0.8 | 15.22 | 1.69 | 11.92 | 9.84 (0, 48.7, 11) | 0 of 5,875 | 15.22 | 9.84 | 7.86 | 7.98 |
| c | 0.4 | 15.15 | 1.82 | 12.68 | 9.86 (0, 50, 11.7) | 0 of 29,829 | 15.59 | 9.86 | 7.73 | 8.03 |
| c | 0.25 | 14.93 | 1.85 | 13.72 | 9.84 (0, 48.7, 12.4) | 0 of 82,439 | 15.39 | 9.83 | 7.81 | 8.03 |

- **The earlier rigid runs' 10.2 MPa is reproduced** (10.16 to 10.23 on the back face at Z 10), and with the rigid load
  the hole rim itself is only 10.4 MPa. The 1.5 mm bore mask keeps every rim node, so it hid nothing. `Result.away()`
  drops three quarters of the rim nodes, but in the rigid case what it drops is 10.4 against the 10.2 it keeps.
- **The 0.8 mm control did not hide it either:** the rim value is within 2 % from 0.8 to 0.25 mm in every case.
- **`Result.away()` would hide it when the load is not rigid:** in case b it reports 12.6 to 13.9 MPa where the rim is
  16.0, and in case c (load on the hole walls) it removes the rim altogether and reports 9.8.
- The third run's numbers are reproduced by case b: σz 16.0 MPa at a Ø3.4 rim on X 0, von Mises 18.57 at (5.9, 15.7, 17.3)
  (theirs 16.1 and 18.6 at the mirror hole).
- Statics is the same in all three (reaction −150.00 N, plain section at Z 12 within 3 % of M c / I). What changes is how
  the upright bends round the bore: the rigid patch stops the bore going out of round and out of plane, so the 2.8 mm
  ligaments between the bore and the holes do not flex, the load runs down the middle (bore edge 11.8 MPa, holes 10.4)
  and the part is 15 % stiffer (2.35 mm against 2.74 and 2.82). Hand value for a small hole in the bending field at
  Z 17: 5.5 MPa × 3 = 16.5 MPa, which is what b and c give.

### Factors

| Case | Governing σz MPa | Layer factor (22.5) | Peak von Mises MPa | Yield factor (45) | Verdict against 2.0 |
| --- | --- | --- | --- | --- | --- |
| a rigid on the bore | 10.4 (rim), 10.2 (back face) | 2.16 | 14.3 | 3.15 | pass |
| b even traction on the bore | 16.0 | 1.40 | 18.6 | 2.42 | fail |
| c on the four hole walls | 15.4 (14.9 on the X 0 face) | 1.46 | 18.8 | 2.39 | fail |

## Which to trust

For a motor screwed on through the four Ø3.4 holes, with its boss only located by the bore, the force goes in at the
screws (a +X pull is along the bore axis, so the bore wall cannot carry it at all): cases b and c are the load path, they
agree, and the part fails the layer requirement at about 1.4 to 1.5. The rigid remote load on the bore wall is a lower
bound only, because it lends the plate the motor's stiffness over exactly the region being judged.

For the playbook: a rigid remote load makes its faces a rigid body, so it stiffens everything within about a hole
pitch and unloads small holes and thin ligaments next to it (here 10.4 against 16 MPa at holes 2.8 mm from the loaded
bore); when a feature that could govern lies within a few wall thicknesses of the loaded face, run the load a second
way (a distributed force, or on the faces that really bear) and report the higher, and never let the load-face mask
(`Result.away()`) cover that feature.

## Not verified

- A real motor flange clamped over the holes was not modelled. It would stiffen the region like case a and also clamp
  the rims; the true rim stress lies between a and b/c. That needs the flange as a body with contact.
- Case c loads the hole walls with an even traction along X, not washer rings on a face; the peak node is on or within
  0.2 mm of the loaded wall (13.7 MPa at more than 0.05 mm off it at the finest mesh).
- Interlayer shear and other print directions were not read here; this check is on σz and von Mises only.

## Solver note

Every case was solved twice, on Automatic ([rows_automatic.json](rows_automatic.json)) and on direct sparse
([rows.json](rows.json), the tables above). The two sets agree to 0.01 MPa and 0.001 mm in every number.

On both solvers the solver put up "Excessive displacements detected" on the finer meshes: b and c at 59,363 and 116,213
nodes, a at 116,213 only (2.3 to 2.8 mm on a 46 mm part). Nothing is loose: answered No it returns the linear result,
with the same reaction, displacement and section stress as the 0.8 mm runs that were not asked. On a hidden instance
the prompt blocks until it is answered: the first one sat for ten minutes, because the first version of `check.py`
had no dialog watcher, and I answered No by hand on my own instance. `check.py` now runs the watcher of
`swfea.static()`. `static()` itself raises on this prompt unless `loose_ok=True`, so this series run through
`static()` would stop at the second mesh of case b: the prompt is not proof of a loose body.
