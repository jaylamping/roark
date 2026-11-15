# 3. Building and changing parts

Everything below uses [swkit.py](../swkit.py). The worked example is `model()` in [selftest.py](../selftest.py).

## The frame

Parts are modelled **in place**, in the frame of the assembly they belong to (for the robot: X forward, Y left, Z up, mm; a
limb's parts share that limb's frame). A point in a script is a real coordinate on the robot. **Why:** bodies inserted into
another part land where they belong, exports line up with every other export, and FEA results can be read by coordinate.

Put the numbers that define a part at the top of its script as named constants with their source (a vendor drawing, a
measured part, a requirement). Derive everything else from them.

## One feature, the same five steps

```python
with Sk(d, plane(d, 'Z', 5.0, 'BOSS_P'), 'BOSS') as s:      # 1. plane at the MIDDLE of the feature, normal to an axis
    s.circle((20, 15, 5.0), 6.0)                              # 2. draw with 3D model points that lie on that plane
extrude(d, s.feat, 'BOSS', 10.0, mode=MID,                   # 3. mid-plane: no direction to get backwards
        expect_dv=math.pi * 36 * 10)                          # 4. say what volume it must add; it raises otherwise
save(d)                                                       # 5. save
```

- **Planes** are normal to a model axis at a coordinate: `plane(d, 'X' | 'Y' | 'Z', mm, name)`. For an angled plane, see
  `organic_master.py` on branch `left-arm-organic-r1` (the crush ribs): an axis from two planes, then `InsertRefPlane(16, ...)`,
  then check that the points lie on it.
- **Sketch points are model points.** `Sk` maps them through the sketch's own transform, so you never work out which way a
  sketch's axes point, and it raises if a point is off the plane.
- **Mid-plane extrudes** wherever the feature is symmetric about a plane you can name. For a one-sided feature use `BLIND`
  with `want=(axis index, sign, plane coordinate)`: both directions are tried and the right one kept.
- **`expect_dv`** is the hand-calculated volume change. Give it whenever the feature is a prism, a cylinder or a ring you
  can compute; for shapes you cannot, at least read the logged volume change and ask whether it is plausible.
- **Name every feature** for what it is (`RS02_SEAT`, `STOP_LUG`). The helpers name the sketch `<name>_SK`.
- **Read the line after every feature.** Each feature helper logs the measured part once it has built
  (`BOSS: part is now 19130.97 mm3, box [0.0, 0.0, 0.0, 60.0, 30.0, 10.0], 1 body`) and keeps it in `swkit.last`;
  `state(d)` gives the same at any time. Compare that line with what you meant, every time: a box that grew where
  nothing should stick out, a second body, or `REBUILD ERRORS` is the mistake showing itself one step after it was
  made, not ten.
- **A refusal says what to do next.** A helper that raises `Failed` gives, where it can, a `try:` line (what to change
  before running again) and a `stop when:` line (when to give that way up and build the shape differently). Do the
  `try:` first; reaching the `stop when:` is not the end of the task, it is the point to change the approach
  ([07-done.md](07-done.md), "Do not stop early").

## Recipes

| Want | Do |
| --- | --- |
| Block, plate, boss, pocket, through hole | `Sk` + `rect` / `circle` / `poly`, `extrude(..., mode=MID)`; `cut=True` removes |
| Several holes in one feature | several `s.circle` in one sketch |
| Turned shape (bore, seat, groove, ring) | profile with `s.poly` in a plane through the axis, `s.centerline(a, b)` on the axis, `revolve(d, s.feat, name, cut=...)`. A partial ring: `angle=`, `mid=True`. A round in the profile is a true arc, `s.poly(..., closed=False)` runs joined by `s.arc(centre, p0, p1, +1)`: a round drawn as straight segments turns into a stack of cone faces that nothing crossing it can be filleted against (see "What goes wrong") |
| Round a lofted stem into the flat face it stands on | `fillet()` on the seam edge works there. `skirt(d, outline, 'Z', 0.0, 4.0, 'FOOT')` does the same with a second loft and is the one to use when the fillet will not build |
| Curved band between two radii and two angles | polygon of points along both arcs (60 per arc), `extrude` mid-plane. Arcs as polylines are fine for cuts and bosses; not for faces that must seal or bear |
| Organic skin | closed spline sections (`s.spline`) on parallel planes, resampled to **even arc length with the same point count**, then `loft`; `shell(d, [a point on each face to open], wall, name)` afterwards. Each point must lie inside one face, not on an edge. A 12-point spline circle lofts to within 0.03 % of the true cylinder. **That recipe holds only while the sections keep one shape.** When they change shape along the loft (round to oval to a fork), closed splines twist and pinch to a point, and no spacing cures it (two benchmark runs, 2026-11-13, lost 10 to 12 minutes each). Draw each section as two or four open curves that share end points, so the loft has corners to match from section to section, and put a point on the tip of any thin section. `loft()` gives one message for every cause: when it fails, loft the sections two at a time to find the pair |
| Is this region solid or clear | export the STL, then `sheet.inside(sheet.read_stl(stl), points)` on points sampled in the region: a clearance cylinder, a slot, a cable passage, a boss. Faces can be measured with `pick`; empty space cannot |
| The top, the bottom, a side face | `side(d, '+z')` (or `-z`, `+x`, `-x`, `+y`, `-y`): the flat faces that face that way and lie on that end of the part's box. It finds the same face however the part was built. A top that is not flat returns nothing: use `pick` with a box. Check the count |
| The edges round a face, or along an axis | `edges_of(side(d, '+z'))` is the rim of the top face, holes included (`edge_info(e)` gives each edge's length, ends, middle and whether it is straight, to keep the ones you want); `edges_along(d, 'Z', inside=box)` is the straight edges that run along Z. Both replace most hand-written `edges_where` tests |
| Rounded edges | `edges_where(d, test)` (it tests an edge's start, middle and end: an edge that only ends on an excluded curve is dropped, and a closed loop has no ends, so test the middle) straight before `fillet(d, edges, (2.0, 1.5, 1.0), name)`: it tries the radii in order. `chamfer(d, edges, width, name)` the same way |
| Split a part | copy the master file, `cut_half_space(d, 'Z', z, +1, name)` in one copy and `-1` in the other |
| Two parts in one model (for contact FEA) | `insert_body(d, other_part_path)`; both must have been modelled in the same frame. Find the new body by its box or volume in `bodies(d)`. An overlap is **not** reported: the bodies stay separate and overlapping, so compare their boxes yourself |
| Import a vendor STEP | `import_step(sw, step, target)`, into `cad/vendor/<maker>/`. Volume and box come back exact; every full cylinder comes back as two half faces |
| Change an existing part | prefer changing the script and rebuilding. To edit a native file with no script: open it, add features on top, never edit a sketch the script does not own |

## What goes wrong, and the cure

| Symptom | Cause | Cure |
| --- | --- | --- |
| `extrude` raises "no ... changed the volume" | sketch not closed (two points not exactly equal), sketch off the body, or a cut in empty space | print the points; build closed outlines from one list of points; check the body's `bbox` |
| A cut leaves a paper-thin wall or a 0.02 mm band | two surfaces meant to coincide differ by a rounding error, or a revolve was trimmed back to a face it nearly touches | make cutting tools overshoot by 0.1 to 0.5 mm into empty space; never leave faces "almost" flush. Slivers break the mesher later |
| Fillet builds on some edges and not others | stale edge objects, or one edge whose corner cannot take the radius | find edges again each time; if a group fails, round one edge at a time, smaller radii, then a chamfer; record which built |
| Fillet "works" but the part looks unchanged | the edge test matched other edges | print `len(edges)` and the edge end points before rounding |
| Extra small bodies after a cut | the cut separated a crumb | `single_body(d)` deletes crumbs under 0.2 mm³ and raises if more than one real body is left |
| Many short segments on a curved cut | polyline arcs with too many points | 5 to 10 segments on a short ramp; strip faces about 0.15 mm wide stalled the mesher |
| Loft twists or fails | sections with different point counts or start points | same count, start points in line, even arc-length spacing |
| Shell fails | wall thicker than a concave radius | smaller wall, larger radius, or shell before adding small features |
| `extrude(cut=True)` raises on a plain round pocket where other cuts worked | not found (benchmark run sonnet-d, a Ø6 counterbore) | `revolve(cut=True)` of the same cylinder; a revolve about any axis in the sketch plane also makes pins and bosses that are not along X, Y or Z |
| `cut_half_space` raises on a thin trim | it removes less than 1 mm³ | `cut_half_space(..., min_dv=0.01)` |
| `pick(kind='plane', normal=...)` returns far more faces than you meant | every face with that normal matches, tilted ones too | add `at=` or `inside=` and check the count |
| `fillet()` returns nothing | read the lines it logs: the edges, shortest first, with their lengths and middles, and whether any is shorter than the radius | an edge shorter than the round is the usual cause: leave those edges out or remove what made them (the loft row above). When none is short, the round runs into a narrow neighbouring face or an existing round: try the edges one at a time, then a smaller radius |
| `edges_where` finds no edge on a disc rim | a full circle has no middle distinct from its ends, and the test point lands on the seam | pick the rim face and take its edges (`call(face, 'GetEdges')`, then keep the ones you want by their middle point), or build the round into the revolved profile as a true arc (`s.arc`) |
| `fillet()` returns nothing where a loft meets another feature | not the loft: rounds in the parent drawn as polylines. Each straight segment of a revolved profile becomes its own cone face, the stem crosses them all, and the seam breaks into slivers: 32 edges against 14 faces on the benchmark link, the shortest 0.04 mm. Nothing builds on that seam: an edge fillet at 0.5 to 5 mm, the edges that round alone taken together, a face fillet, multi- and variable-radius (2026-11-14, [eval/loft-blend](https://github.com/jaylamping/cad-daddy/blob/main/eval/loft-blend/RESULTS.md)) | in this order. **1. Draw the parent's rounds as true arcs** (`s.arc` in the revolved profile): the same stem then met 5 faces in 12 edges, the shortest 1.64 mm, and `fillet()` built at 1 and 2 mm (not above: the rim round itself was 2.5 mm). **2. On a flat face just fillet:** the seam is one edge and every radius from 0.5 to 8 mm built. **3. Where neither can be had, lay a second loft over the junction** (next row). Do not leave it sharp in a stressed place without saying so |
| A loft has to be blended into a feature and no fillet builds | the seam cannot be repaired after the fact | **On a flat face:** `skirt(d, outline, axis, at, radius, name)`, where `outline(c)` is the function the stem's sections were drawn from: five sections along a quarter circle, the first in the face and `radius` wider than the stem, the last 0.15 mm inside it. On the test stem it built at 1 to 8 mm and read within 2 % of a real 4 mm fillet (5.04 against 4.95 MPa, sharp 6.67, same mesh), without touching the stem. Use five sections along the arc: a two-section skirt is a cone and gave half the gain. **Anywhere else** (a stem leaving a rim): draw the sections yourself, either as the stem's own first sections ("rooted": the last one lies wholly inside the parent and the surface crosses the parent's faces at a shallow angle, about 25° on the link) or as a separate short loft from inside the parent to 0.15 mm inside the stem. Both built on the benchmark link and took its junction peak from 25.3 MPa to 19.3 and 18.1 (2 mm mesh; 27.5 to 17.5 and 15.1 at 3 mm). **Limits:** neither is tangent to the parent, so a shallow crease is left and the peak there still crept up 10 to 17 % with the mesh: report it as not converged, with the mean over 2 mm (which did not move, 11 MPa). The blend needs room on the parent as wide as its radius. Putting the round into the stem's own loft on a flat face (crowded sections at the foot) also fattens the stem above it, and at 1 mm added five times the volume of a true round: use the skirt there |
| A loft fails when the section centres step sideways | not found (benchmark run sonnet-c2, a 2 mm step in Y between sections) | keep the centres on one line and move the outline within the section instead |
| Feature added to the wrong body or merged | multi-body state | check `bodies(d)` before and after |

## Before you call a part done

1. `feature_errors(d)` is empty and `bodies(d)` is what you expect (one body for a printed part). A feature that fails
   when it is first made returns nothing and the helpers raise; `feature_errors` is for the ones that break later, when
   something upstream changes (a cut whose sketch no longer meets the body reports code 71).
2. Volume and bounding box match the hand values; mass = volume × 1.19 g/cm³ for PETG is in the report.
3. The features that mate with something were checked against that something: a bore against the vendor model's diameter,
   a bolt pattern against the drawing, clearance on moving faces. Open the mating part or its export and measure.
4. Saved, exported if anything downstream needs it ([04-export.md](04-export.md)), and the script that built it is in
   `cad/scripts/`.
5. For a part that will be printed: no enclosed cavity, no knife edge, walls at least 0.6 mm, the orientation chosen, and
   the pre-print gate run ([part-lifecycle.md](../../../conventions/part-lifecycle.md)).
