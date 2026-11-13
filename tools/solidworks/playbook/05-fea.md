# 5. Static studies

Everything below uses [swfea.py](../swfea.py). Worked examples: `beam()` and `rod()` in [selftest.py](../selftest.py).

A study answers one question: does this part survive this load, with what margin, and where does it fail first? The solver
always returns a number. Most of this page is about making sure it is the answer to the question you asked.

## Before SolidWorks: write the case down

| Item | Write down | Example |
| --- | --- | --- |
| The load | where it comes from, its size, where it enters the part | elbow stop: 34 N·m back-driven at r 38.25 mm = 889 N on the stop face |
| The support | what really holds the part, and what that leaves free | screwed to the ring by six M3: the six hole walls fixed |
| The hand estimate | the nominal stress in the governing section, and the deflection | σ = M c / I, δ = F L³ / 3 E I |
| The allowable | printed PETG: yield 45 MPa in the layer plane, **22.5 MPa in tension across layers**, 13 MPa interlayer shear | which way the layers run in this part, as printed |
| The pass mark | the factor of safety the part's requirements ask for | `cad/<region>/*_requirements.md` |

If you cannot fill in the hand estimate, you are not ready to run the study.

## One study

```python
r = static(j, d, 'STOP_889N', PETG,
           fixtures=[('fixed', pick(d, kind='cyl', r=1.6, inside=[148, 160, -45, 152, 260, 55]))],
           loads=[('normal', pick(d, kind='plane', at=(142.5, 174.6, 20.9)), 889.0)],
           el=2.0, ctrl=[(pick(d, kind='plane', at=(142.5, 174.6, 20.9)), 0.6)])
print(r.summary())
```

- **Faces come from `pick()`**, and every pick is checked for its count before it is used. An empty or over-wide pick is
  the commonest way to solve the wrong problem: `static()` refuses empty lists, and you print `len()` of every pick.
- **Fixtures:** `'fixed'` holds a face in all directions. `'hinge'` on a cylindrical face lets it turn about its axis.
  Restrain what the real part restrains, on the faces that really bear. A model with too little restraint fails with error
  24; one with too much hides the stress you were looking for.
- **Loads:** `'normal'` presses on faces along their normals with the total in newtons, shared between the faces by
  area as one even pressure (SolidWorks' own normal force puts the value on each face: [02-com.md](02-com.md)). Positive
  pushes into the material. `'remote'` applies a force and a moment
  at a point and carries them rigidly to the faces: use it for a load that acts away from the part (a hand load at the end
  of the forearm, a motor torque).
- **Material:** `PETG`, `STEEL`, `BRASS` in swfea.py; `materials={body name: dict}` when bodies differ. A linear study
  scales: twice the load is twice the stress, so one solve per load direction is enough.
- **Mesh:** `el` is the global element size, `ctrl` puts smaller elements on named faces. Start at 2 to 3 mm globally with
  0.6 to 0.8 mm on the loaded and restrained faces and on the fillets that carry the load. Thin walls need two elements
  through the thickness.

## Is the result right? Five checks, every time

| # | Check | Pass |
| --- | --- | --- |
| 1 | **Reaction equals load.** `r.reaction` is `[Fx, Fy, Fz, resultant]` in N, what the fixtures push back with: equal and opposite to the load. Compare each component with the load you meant, and the resultant with `r.applied` | within 1 %. If not, the load is not the one you meant |
| 2 | **Displacement is sane.** `r.max_disp()` against the hand estimate | same order of magnitude. Metres of displacement means a loose body |
| 3 | **Stress in the plain section matches the hand estimate.** `r.average(point, 2.0)` at a point away from corners, and at least one section depth from a fixed face: a fixed face stops the part widening, which raised a Ø20 rod's stress 5.5 % over F / A 11 mm from the face (2026-11-12) | within about 15 % |
| 4 | **The peak is not at a fixture or load face.** `r.peak()` already excludes nodes within two elements of them; say so, and look at `r.vm.max()` to see what was excluded | you can name the feature the peak sits on |
| 5 | **The peak has converged.** `converge(run, (3.0, 2.0, 1.5))` | the last step moves it under 5 % |

A peak that keeps rising as the mesh shrinks is a **singularity**: a sharp inside corner, or the edge of a fixture. It is
not a stress. Either the real part has a radius there (model it, then it converges), or it is an artefact of the fixture
(move the fixture, or judge that spot by the average: `r.average(at, 0.5)`, `1.0`, `2.0` with their node counts. A value
that recovers within 1 mm on fewer than about 10 nodes is a corner; one that holds over 2 mm is the section).

Report the layer direction too: `r.layer_stress((0, 0, 1))` is the largest tension across layers stacked along Z, judged
against 22.5 MPa. Printed parts fail there first.

## Sizing the job

| Nodes | Solver | Peak memory | Time on holly-pc |
| --- | --- | --- | --- |
| under 20,000 | automatic | under 2 GB | 2 to 7 s for mesh, solve and readback together |
| under 100,000 | automatic | under 2 GB | seconds to a minute |
| 300,000 to 450,000 | automatic, or direct sparse for contact | about 11 GB with direct sparse | 7 to 11 minutes with contact |
| about 800,000 with contact, direct sparse | | **ran out of memory** on the 32 GB machine, reported as error 24 | |

`static()` refuses meshes over 450,000 nodes. To get under it, coarsen the global size and keep the local controls: a 4 mm
global mesh with 0.8 mm controls on the joint gave about 400,000 nodes where 0.8 mm everywhere-near-the-joint gave 800,000.
Make the control catch only the faces that matter (by area and position), not every face that crosses a box.

Solves that size run **one at a time** on holly-pc, with three minutes between cases. Reading the results of a
multi-million-node model back over COM takes over an hour and has crashed: stay under the limit.

## Contact between bodies

Bodies in one part that touch are **bonded** by default. A joint that can open or slide needs a no-penetration contact set
between the two groups of faces, and that changes the whole study.

```python
r = static(j, d, 'JOINT', PETG, fixtures=..., loads=..., el=4.0, ctrl=[(seat_faces, 0.8)],
           contacts=[(NO_PENETRATION, hub_faces, arm_faces), (BONDED, insert_outer, hole_faces)],
           materials={...}, solver=SOLVER_DIRECT)
```

What was learned on the upper-arm hub joint, 2026-11-11 and 12:

1. **Use the direct sparse solver.** Automatic picks the iterative one, which stalled at contact iteration 7.
   `solver=SOLVER_DIRECT` sets it with a macro; the benchmark log beside the model confirms which solver ran.
2. **Every body must be held without the contact.** A body kept in place only by no-penetration contact, with clearance, is
   free until it touches: the solve fails with error 24. Model the real gap and hold the loose body with small soft pads
   (four Ø1.8 pads, modulus 0.5 MPa, bonded both sides), then check that the pads carry under 1 % of the load.
3. **Do not model a fit as line-to-line.** Faces that exactly touch are bistable: the solver may or may not see contact.
   Give the faces their real clearance, or a real interference.
4. **A face in a contact set is no longer bonded by the global bond.** Anything that must stay stuck to it (a brass insert
   in its hole, a bolt in its thread) needs its own `BONDED` set. An insert that came loose showed 5 km of displacement.
5. **Split the results by body with geometry, not node order.** Label each node by which solid it lies inside, with a
   margin at the interfaces, and stop if any node of one body lies inside another. A split by index range scored steel
   bolt nodes as plastic and moved every reported number.
6. **Check the load path, not just the stress:** the force each bolt or lug carries (mean stress over a section × its
   area) against what the joint is meant to do. A tie that should be carried by a ridge showing up as bolt tension means
   the contact is not engaged.
7. **Soft springs and the solver options cannot be set from python** ([02-com.md](02-com.md)). Use the macro for the solver,
   pads instead of soft springs.

A contact study with more than two bodies, a gap, or a result that decides a design is work to hand up
([06-judgment.md](06-judgment.md)), or at least to have reviewed before anyone acts on it.

## When the solve fails

| What you see | Likely cause | Check, in order |
| --- | --- | --- |
| Mesh fails, or stalls for minutes | sliver faces, a 0.02 mm band, an element size larger than a thin wall | list small faces (`list_faces`, area under 0.5 mm²) and fix the geometry; smaller local size on the thin wall |
| Error 24 at once | a body free to move | every body restrained or bonded? any body held only by contact? fixture faces empty? |
| Error 24 after a minute or more, memory falling | out of memory in the factorisation | node count; free memory when it failed; coarsen |
| Solver iterates and never finishes | iterative solver on contact | direct sparse |
| Displacement of metres | a loose body, or a bond lost to a contact set | explicit `BONDED` sets |
| `GetStress` raises or the instance dies on readback | result too large | smaller model |
| Launch sits at the splash screen | another instance is solving, or one is half-closed | [01-session.md](01-session.md) |

Never fix a failed solve by changing two things at once, and never report a number from a study whose checks you did not
run. An invalid result is recorded as **INVALID** with the reason, not quietly replaced.

## What goes in the report

For each case: the model file and its SHA-256, the load and support in words, element sizes and node count, the solver,
the five checks with their numbers, the peak with its location and what was excluded, the layer stress and its direction,
the factor of safety against the right allowable, and anything you could not verify. Nodal results go to
`cad/_sim/<region>/<case>.npz` so the numbers can be recomputed without solving again.
