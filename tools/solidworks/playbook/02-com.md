# 2. How SolidWorks answers a python script

SolidWorks is driven through COM with `pywin32`, from outside its process, with late binding. The API documentation is
written for VBA inside SolidWorks; these are the differences that cost time. [swkit.py](../swkit.py) hides most of them. You
need them the moment you call the API yourself.

## The eleven rules

| # | Rule | What goes wrong otherwise |
| --- | --- | --- |
| 1 | **Lengths are metres, angles radians,** in every API call. The helpers take mm and degrees and convert. | A 10 mm extrude asked for as `10` is ten metres. It "works" |
| 2 | **Failure is a quiet `None`, `False` or non-zero code,** not an exception. Check every return value, then check the model (volume, body count, box). | The script runs to the end and saves a part with half its features |
| 3 | **An optional object argument is `NUL`** (`VARIANT(VT_DISPATCH, None)`), never Python `None`. | "Type mismatch" |
| 4 | **Out-arguments are by-reference VARIANTs:** `e, w = L(), L(); d.Save3(1, e, w); e.value`. A boolean one is `VARIANT(VT_BYREF \| VT_BOOL, False)` (`IFeature.GetErrorCode2`). Leaving one out raises "Parameter not optional". | The call fails, or the error code is lost |
| 5 | **A member may be a property on one call and a method on the next** (`GetBox`, `GetFaces`, `GetEdges`, `GetArea`, `RunAnalysis`). Use `call(obj, 'Name')`. | "'tuple' object is not callable", or a bound method where a value was expected |
| 6 | **Arrays of objects** (faces, edges) pass as a Python list to most calls, but some need `dispatch_array(list)` (`CreateContactSet`). Arrays of numbers for sketch splines need `VARIANT(VT_ARRAY \| VT_R8, [...])`. | "Type mismatch", or an empty selection |
| 7 | **An array result may come back wrapped** as `(data, error)`. Unwrap before reshaping (`swfea._arr`). | A reshape error, or silently reading the error code as data |
| 8 | **Face, edge and feature objects go stale after any feature is added or the model rebuilds.** Find them again, straight before use. | Fillets that build on the first edge and fail on the rest; selections that select nothing |
| 9 | **Selection is state.** `ClearSelection2(True)` before every selection; a selection `Mark` matters for lofts, revolves and offset-from-surface ends. Select faces and edges as objects (`face.Select4(True, NUL)`), found by geometry: `SelectByID2('', 'FACE', x, y, z, ...)` by coordinates found nothing on a hidden instance (2026-11-12). | A feature built from the previous step's leftovers, or from nothing |
| 10 | **Never call `GetActiveObject` or `Dispatch("SldWorks.Application")`.** Use the handle from `job()`. | You drive another thread's SolidWorks |
| 11 | **Never wrap an API call in a bare `except` that carries on.** Catch it, log the message, and prove the call once on a case where it must return something. | `feature_errors` swallowed "Parameter not optional" on every feature and reported every tree clean until 2026-11-12; the reaction readback tried a call that does not exist and quietly returned nothing |

## Numbers the scripts use

These are enum values written as numbers, because late binding has no constants.

| Call | Values |
| --- | --- |
| `OpenDoc6(path, type, options, config, e, w)` | type 1 part, 2 assembly, 3 drawing; options 1 silent |
| `Save3(options, e, w)`, `Extension.SaveAs(path, 0, options, NUL, e, w)` | options 1 silent. `SaveAs` picks the format from the extension |
| End conditions (`FeatureExtrusion3`, `FeatureCut4`) | 0 blind, 1 through all, 2 up to next, 5 offset from surface, 6 mid plane |
| `InsertRefPlane(first, value, 0, 0, 0, 0)` | 8 distance; add 256 to flip; 16 angle about a selected axis |
| `GetBodies2(0, True)` | 0 solid bodies, visible only |
| `body.GetMassProperties(density)` | `[0:3]` centre of mass m, `[3]` volume m³, `[4]` area m², `[5]` mass kg |
| `InsertPart3(path, 1, '')` | 1 import solid bodies |
| Unit system `Extension.SetUserPreferenceInteger(263, 0, 5)` | 5 MMGS |
| Export toggles and integers | 69 STL binary, 71 STL keep the model frame, 211 STL units (0 mm), 78 STL quality (2 fine), 75 STEP AP (203) |
| Default part template `GetUserPreferenceStringValue(8)` | empty on holly-pc: pass a template |
| Simulation `AddRestraint(kind, faces, NUL, e)` | 0 fixed, 4 fixed hinge |
| Simulation `CreateContactSet(kind, a, b, e)` | 0 no penetration, 1 bonded |
| Simulation solver | 0 automatic, 1 direct sparse, 2 FFEPlus, 7 Intel direct sparse. Setting 1 reads back as 7 on SolidWorks 2026 SP0 |
| Simulation `GetStress(0, 1, NUL, 3, e)` | units 3 = MPa; 12 columns per node: id, σx σy σz, τxy τxz τyz, P1 P2 P3, von Mises, stress intensity (P1 − P3). Compression is negative. Measured 2026-11-12 on a rod and a beam bent two ways |
| Simulation `GetTranslationalDisplacement(1, NUL, units, e)` | three arguments and the error; units 0 mm, 1 cm, 2 m, 3 inch; 5 columns per node: id, UX UY UZ, resultant. The four-argument form is a type mismatch |
| Simulation `GetReactionForcesAndMoments(0, NUL, units, e)` | units 0 N (1 lbf); 9 columns per node: id, Fx Fy Fz Fres, Mx My Mz Mres, zero except on restrained nodes. Sum the Fx Fy Fz columns for the whole model; do not sum Fres. `GetReactionForces2` does not exist on SolidWorks 2026 |
| Simulation `AddForce3(1, 0, -1, ..., value, ..., faces, ...)` (normal force) | the value in N goes on **each** face in the list, positive pushing into the material. `swfea.static` makes one call per face so that its number is the total |
| Simulation `AddRemoteLoad(1, faces, 0, x, y, z, e)` | location in mm in the model frame; with `ForceUnit = 0` and `MomentUnit = 0` the force is N and the moment N·m; moments follow the right-hand rule about the model axes |
| Simulation `CreateMesh(0, size, tolerance)` | sizes in **mm**, unlike the rest of the API |

## Things that look like bugs and are not

- **`sw.Visible = False` reads back True.** The instance is hidden by a helper process; see RULES.md.
- **A new part will not open on holly-pc:** no default template. `new_part()` finds one.
- **`NewDocument` throws after a failed build:** the failed part is still open. `sw.CloseAllDocuments(True)` first
  (`new_part()` does).
- **A second copy of a model by the same file name will not open.** Close the first, or use another name.
- **Reading or writing `StaticStudyOptions` from python** fails ("can not be set", "server threw an exception") and logs an
  access violation in SolidWorks. Set the solver with a macro run inside SolidWorks (`swfea.solver_macro`). Never read it
  back from python.
- **`StudyManager.GetStudy(i)` returns nothing from python,** even with a study present and `StudyCount` 1. Keep the study
  object `CreateNewStudy3` returned. Inside a macro `GetStudy(i)` works. `StudyManager.DeleteStudy(name)` works from python.
- **Result calls fail with "Memory is locked"** when they are given face objects from before a rebuild. `save()` rebuilds:
  between picking faces and reading results for them, save with `Save3` alone (`swfea.solver_macro` does).
- **A STEP import splits every full cylinder into two half faces.** `pick(d, kind='cyl', r=4.0)` finds two faces on the
  imported plate where the native plate has one. Count accordingly, and give both to a fixture.
- **The Simulation solver writes each body's surface nodes before its interior nodes.** Node order does not tell you which
  body a node is in: decide by geometry ([05-fea.md](05-fea.md)).
- **SolidWorks deletes the solver's `.OUT` file after a failure.** The benchmark log next to the model
  (`<model>-<study>-BenchMark-Solver.txt`) survives and names the solver and the last stage reached. On a model of a few
  thousand nodes Automatic also picks the Intel direct solver, so there the log looks the same either way.

## Finding an API call you have not used

1. Search the proven scripts first: `cad/scripts/` on branch `left-arm-organic-r1` (`git show origin/left-arm-organic-r1:cad/scripts/arm/organic_master.py`).
2. Then the API help for the interface (`IModelDoc2`, `IFeatureManager`, `ICWStudy`), reading the VBA signature and
   applying the rules above.
3. Try it on a scratch part in `cad/_wip/`, print the return value and the volume before and after, and only then use it on
   real work. Record what worked in the page it belongs to, in the same PR.
