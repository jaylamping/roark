## D2. Two halves round a 6808-2RS

Scripts: `d2_build.py` (both halves, ring, the study's stand-ins, the eight-body study model), `d2_fit.py` (fit
check and pictures), `d2_fea.py` (contact studies), `d2_post.py` (bodies split by geometry, screw loads, factors).
Numbers: `d2_model.json`, `d2_fit.json`, `d2_fea_*.json`, `d2_post_*.json`.

### Problems in the specification, found before modelling

| # | What the task says | The number | What I built instead |
| --- | --- | --- | --- |
| 1 | Shoulder opening dia 43.5 | The inner ring is dia 44.0 across: the shoulder would overlap the **turning inner ring** by 0.25 mm on radius, with no axial clearance, and cover the seals (dia 44 to 48) | Opening **dia 49.0**: 2.5 mm clear of the inner ring, 0.5 mm outside the seal, and a 1.5 mm land on the outer ring's face only |
| 2 | Seat Z 0 to 7 for a 7.0 wide bearing | Axial clearance 0.00. The halves close along Y, so both shoulders slide across the bearing's faces; at -0.15 the pair cannot be assembled | Seat **Z -0.1 to 7.1**: 0.1 mm each side |
| 3 | Screws at X +/-28.2 | Seat radius 26.0. A dia 4.0 insert hole there leaves **0.2 mm** of wall to the seat at the split face (a dia 3.4 hole leaves 0.5 mm): under the 0.6 mm minimum, and a hot insert would break through | Screws at **X +/-31.0**: 2.9 mm to the seat, 3.0 mm to the outside |
| 4 | Screws at Z 1 and Z 6 with dia 6 counterbores | Centres 5 mm apart, counterbores 6 mm across: they **overlap by 1.0 mm**, and two dia 5.5 screw heads collide by 0.5 mm | Screws at **Z 0 and Z 7**: 1.0 mm between counterbores, 1.0 mm to each face (thin: see "not the end") |
| 5 | Dia 4.0 insert hole 6 deep, dia 6 counterbore 3.5 deep from Y 32 | Grip under the head is 28.75 mm. No stock screw works: M3 x 30 enters the lower half 1.25 mm, M3 x 35 needs 6.25 mm and would bottom in a 6 mm hole before clamping | Insert hole **8 deep**; **M3 x 35**: 6.25 mm in, 1.75 mm spare |
| 6 | Split on the plane Y 0, seat dia 52, "must clamp the outer ring" on a +/-0.15 printer | Line to line, the halves' faces meet at the same moment as the seat: with the seat 0.15 large the ring is loose, with it 0.15 small the faces never meet. It cannot clamp by design | Seat **dia 52.15** and each split face set back 0.4 mm (**0.8 mm gap** as modelled): see the fit below |

Not a problem, checked: the two dia 5.6 x 8 holes at X +/-24 on the face Y -32 end 8.8 mm from the seat and 4.7 mm
from each face; the envelope holds 6 mm of wall over the seat at the crowns.

### The fit, and why it would work off a real printer

- **Seat dia 52.15** (radial clearance 0.075). With +/-0.15 on the diameter the seat prints 52.00 to 52.30: never
  smaller than the ring. A seat that is never undersize always meets the ring first at its crown, in the direction
  the screws pull; an undersize seat would grip at its two edges beside the split and wedge.
- **Split gap 0.8 mm as modelled, 0.65 mm clamped.** Tightening brings the upper half down 0.15 (twice the radial
  clearance) until both crowns hold the ring. What can go against the gap: the seat at its smallest (closes 0.15 less,
  which helps), the seat at its largest (0.15 more), and the split face of each half up to 0.15 out against its own
  seat, twice. Clamped gap = 0.8 - (0.15 +/- 0.15) +/- 0.30 = **0.2 to 1.1 mm**, never zero: the screws always pull on
  the ring, never on plastic against plastic.
- **Held, not crushed.** The ring is located in Y by the two crowns and in X by the curvature (a 26.0 ring in a
  26.075 seat centres itself). The screw tension all goes through the ring, so it must be limited: see the screw load.
- **Axial:** 0.1 mm each side; the outer ring cannot walk out past the 1.5 mm lands.

### Does the pair go together

Checked on the STLs in the clamped state (ring 0.075 low, upper half 0.15 down), by sampling points
(`sheet.inside`), share of points found inside either half:

| Must be empty | Share inside |
| --- | --- |
| The turning inner ring and its sweep through both shoulders (r 20 to 22, Z -4 to 11) | 0 |
| Seals and balls (r 22 to 24) | 0 |
| Shaft (r under 20) | 0 |
| Screw shanks dia 3.0 and thread ends; heads dia 5.5 and the driver above them to Y 60 | 0, 0 |
| M4 screws into the mounting face | 0 |
| The split gap | 0 |
| The outer ring itself (r 24 to 25.99, Z 0 to 7) | 0.0027: 16 of 6,000 points, all at r over 25.97 and within 33 degrees of a crown, where the ring touches the seat and the STL's flat facets cut a few hundredths inside the true cylinder |

Must be solid: the shoulders over the outer ring's face 98.9 % (the rest is the split gap itself); the wall between
seat and insert holes 100 %.

What touches: the ring's outside on the two seat crowns. Nothing else. What clears, in mm:

| Clearance | mm |
| --- | --- |
| Shoulder opening to the turning inner ring, radial | 2.5 (as specified: -0.25) |
| Shoulder opening outside the seal, radial | 0.5 |
| Shoulder land on the outer ring's face, radial | 1.5 |
| Ring to each shoulder, axial | 0.1 |
| Seat to ring, radial | 0.075 nominal, 0 to 0.15 |
| Split gap clamped | 0.65 nominal, 0.2 to 1.1 |
| Screw shank in its hole, radial; head in its counterbore, radial | 0.2; 0.25 |
| Insert hole to seat; to the outside | 2.9 (as specified: 0.2); 3.0 |
| Counterbore to counterbore; to each Z face; to the outside in X | 1.0 (as specified: -1.0); 1.0; 2.0 |
| M3 x 35 tip above the bottom of its hole | 1.75 |
| M4 hole bottom to the seat | 8.8 |
