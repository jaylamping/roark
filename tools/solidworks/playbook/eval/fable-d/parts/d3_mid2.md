
The hand volume is pi/4 x (outside^2 x T - bore^2 x T - nA x dA^2 x T - nB x dB^2 x T - nB x (cb^2 - dB^2) x depth).
Every STL is watertight, one shell, within 0.1 % of the part's volume and in the model frame; its box is up to
0.08 mm short of the true diameter across Y, which is the facets of a circle and not an error.

### Part two: the change, made by editing

The request, checked the same way before any part was opened, breaks two more things:

| Plate | What the change asks | The number | What I did |
| --- | --- | --- | --- |
| P3_b | Ring A on a dia 70 circle | An A hole at r 35 beside a dia 10 counterbore at r 42, both at 0 degrees: **0.30 mm** of wall | Ring A moved to dia 70 **and turned 22.5 degrees** (half its pitch): 9.82 mm |
| P1_b, P3_b | 1 mm chamfer round the top outside edge | The B counterbores stand 1.0 mm from the edge, so the chamfer meets them in a **knife edge, 0.0 mm** at the top face | **Chamfer 0.4 mm** on these two, leaving 0.6 mm. The other four get the 1 mm asked for |

How each part was changed (`edit()` in `d3_plates.py`): open `P?.SLDPRT`, save it as `P?_b.SLDPRT` (the original
stays as it was), then in place: the disc's depth dimension `D1@DISC` +1.5; the top plane `D1@TOP_P` +1.5; the
counterbore depth `D1@CBORE` +1.5, which is what keeps the floor where it was from the bottom; for P3 the circles of
the existing sketch `RING_A_SK` deleted and redrawn; one new feature, `TOP_CHAMFER`. Bore and hole rings were cut
through all from the bottom plane in part one, so they follow the new thickness by themselves.

**Edited, not rebuilt: true. How I know:** for every plate the feature tree after the change holds the same eleven
features with the same internal IDs and the same creation times as before (P3: 09:20:49 to 09:20:51, from part
one), plus the one chamfer created at 09:23; the script compares them and records both trees in
`d3_part_two.json`. The edit path calls no `new_part`, `extrude` or cut. The originals' file times (09:20:45 to
09:21:03) are from part one. Every counterbore floor was measured on the edited solid and is where it was.

Picture: `pictures/d3_part_two.png`.

