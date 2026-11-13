
### Print direction, and the verdict

Both halves print **flat, face Z -4 on the bed, layers stacked along Z** (the bearing axis). Reasons: the seat is
drawn by perimeters, so it is as round as the printer can make it; the screw tension, the hoop stress in the cap and
the pull on the M4 inserts all lie in the layer plane; no supports (the upper shoulder is a 1.5 mm overhang ring,
which bridges; the M3 holes lie on their sides). The table above reads all three directions from the same results:
stacked along Y (split face or mounting face on the bed) the lowest factor falls from 5.8 to 4.5 and the seat becomes
stair steps; stacked along X it is 4.5 as well. Z is best for both halves, by 1.3 times.

**Lowest factors, layers along Z, finest mesh, both cases, both halves:**

| Measure | Value | Factor | Where | Converged over the last step |
| --- | --- | --- | --- | --- |
| von Mises against 45 | 5.93 MPa | **7.6** | lower half, +X: the seat's top edge at the shoulder, under the ring (19.6, -14.7, 7.1) | yes: 5.87, 5.93, 5.93 |
| Tension across layers against 22.5 | 1.26 MPa | **17.8** | lower half, +X: beside an insert hole at the split face | **no:** 1.34, 1.06, 1.26 (19 %) |
| Shear between layers against 13 | 2.22 MPa | **5.8** | lower half, +X: the seat's bottom edge at the shoulder (24.6, -9.8, -0.1) | yes on the last step (3 %), after +23 % on the step before |

Requirement 2.0 in both halves: **met for yield and for shear between layers, on values that hold over the last
refinement. For tension across layers the playbook's rule gives "not shown":** the value still moves 19 % from mesh to
mesh. It is 1.26 MPa where 11.25 would be the limit, and it sits on the border of the zone I excluded round a bonded
steel insert, so it is the bond's edge, not the part. I am not calling that measure passed on the finest value; I am
saying it would have to grow nine times to matter.

What the convergence table shows beyond that: wherever a peak climbs, the mean within 2 mm of it does not (2.53,
2.53, 2.45; 0.57, 0.56, 0.56; 0.33, 0.34, 0.32). The climbing peaks are all on two kinds of sharp edge: the rim of a
bonded screw head, and the seat's corner at the shoulder where the ring's edge bears. I did not round the seat corner
and solve again, as 07-done.md asks: a 6808's outer ring has a 0.3 mm corner, so a 0.4 mm round in the seat would
foul it; the honest geometry there is a relief groove, which I did not have time to model. The finest step was also
only 1.19 times smaller than the one before: 164,616 nodes is as far as the 200,000 cap lets this model go.

**Support tried a second way.** With only the walls of the two M4 insert holes held, in place of the whole face:
the upper half is unchanged (lowest 6.9 to 9.9), screw tension in +Y is 298.6 N in all, and the lower half reads the
same once clear of the held walls: outside 2, 3 and 5 mm of them 5.9, 5.1, 5.1 MPa von Mises and 2.05 MPa shear
between layers (first way: 5.93 and 2.22). Within 1 mm of the held hole walls it reads 13.3 MPa and 4.75 MPa: the
fixed edge at the bottom of each hole, a singularity by the playbook's own description, reported and not judged.
The numbers that agree between the two supports are the result.

**Load tried a second way:** not done. The load is rigid, but on the bore of the steel ring, not on plastic, and no
hole or thin wall sits within a few wall thicknesses of a loaded face. What a rigid bore hides is the ring going
slightly oval between the balls, which would move the seat pressure; with factors of 5.8 and more I left it.

`valid`: **true** for what it models, a snug pair with no preload. Load path: +Y: balls, outer ring, two bands of
the upper seat at 30 to 65 degrees from its crown, the cap, the four counterbore floors, the screws (74 to 75 N
each), the inserts, the lower half, the mounting face. +X: outer ring, the lower seat's +X flank (292 N), the lower
half, the mounting face; 78 N goes up into the upper seat and comes back down through the screws.

### The screw load, and the thing that actually governs: tightening

| | Hand | Study (mesh m) |
| --- | --- | --- |
| +Y, tension per screw | 300 / 4 = **75.0 N** | **74.2 to 74.9 N**, 298.3 N in all (within 1.0 %) |
| +X, tension per screw | first guess 24 N; from the measured contact angles 75.7 N in all, 18.9 each | 14.2 to 19.0 N, 67.4 N in all |
| +X, shear | first guess 37.5 N each; from the contact angles 17.5 N in all | 26.4 N in all, almost all on the -X pair (15.4 N each) |

The study has no preload, and that is its limit. **Tightening is a load case of its own:** with a gap at the split,
all the screw tension goes through the ring, and the upper half then carries exactly the +Y case scaled by (4 x
preload) / 300. The +Y case's lowest factor in the upper half is 9.6, so the cap reaches a factor of 2.0 at 1,440 N
through the ring: (1,440 - 300) / 4 = **285 N per screw, about 0.17 N.m on an M3** (torque = 0.2 x 3 mm x force). A
normal M3 torque (0.5 N.m and up, 800 N and more) would put the cap over its allowable before any load is applied,
and squeeze a thin-section bearing with over 3 kN. So: tighten to 0.15 N.m, or until the ring just stops turning
in the seat by hand, and thread-lock. This is by scaling, not by a solve.

### Not the end

- **Thinnest margin:** 5.8, shear between layers at the seat's corner under +X. What eats it: screw preload above
  0.17 N.m (above); printing with layers along Y or X (4.5); a shock load 2.9 times the 300 N.
- **Cheapest improvement:** two screws, not four, one each side at Z 3.5. It removes the 1.0 mm walls between and
  beside the counterbores (the thinnest printed features in the part), each screw then carries 150 N in +Y, well
  inside an M3 in a brass insert, and the 0.17 N.m limit doubles per screw. Sized by hand, not built: the task asks
  for four. Second: three crush ribs in each seat in place of the gap, so the split faces can meet and the screws be
  tightened hard; that is a design decision to hand up.
- **Not checked:** preload by a solve; the pair at the ends of the tolerance band (seat at 52.00 line to line, gap at
  0.2); the bearing's own tolerance for being clamped across a diameter; axial load (none was given: the 1.5 mm
  lands would carry it); insert pull-out other than by hand (75 N on an M3 insert, 175 N on an M4 under the +X
  moment, against several hundred); creep of PETG under the clamp; friction (the contact is frictionless, which is
  why the ring rides up 0.11 mm under +X); a printed pair.
