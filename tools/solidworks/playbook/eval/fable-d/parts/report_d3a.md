## D3. Six plates from a table, then a change

One script, `d3_plates.py`: `check` (the table only, no SolidWorks), `one` (build all six), `two` (open and edit
all six). `d3_post.py` draws the sheets and writes the two tables below from the script's JSON.

### The table was checked before anything was built

`walls()` works out every wall of a plate from its row: hole to hole, hole to counterbore, to the bore, to the
outside, and the counterbore floor. It ran on all six rows as given, before the first sketch. Three rows cannot be
made as written:

| Plate | What the row says | The number | What I built, and why |
| --- | --- | --- | --- |
| P1 | Ring A 6 x 3.4 on 50 and ring B 4 x 4.5 on 60 with dia 8 counterbores, both from 0 degrees | At 0 and 180 degrees an A hole (r 25) and a B counterbore (r 30) are 5.0 apart and need 5.7: the hole **cuts 0.70 mm into the counterbore** | **Ring B turned 45 degrees.** Every A hole is then 15 degrees from a B hole and the wall is 3.02 mm. Turning ring A by 15 degrees would give the same spacing; I turned B and left the plain ring where the table put it. Which ring may turn is a question for whoever owns the mating parts |
| P2 | Ring A 6 x 4.5 on 62 and ring B 6 x 4.5 on 62, both from 0 degrees | **The two rings are the same six holes.** Twelve holes become six | **Ring B turned 30 degrees:** twelve holes, plain and counterbored in turn, 9.80 mm between a hole and a counterbore |
| P4 | Outside dia 60 with ring B on dia 58 | The dia 4.5 holes reach r 31.25 and the counterbores r 33.0, on a disc of r 30: **every B hole breaks through the edge** (-3.0 mm) | **Outside dia 70.** A bolt circle mates with another part, an outside diameter usually does not, so the circle is kept and the disc grows to leave 2.0 mm outside the counterbores, as P6 has. If the 60 is the hard number, ring B has to come in to dia 50 or less and I need to be told |
| P4 | Counterbore dia 8 x 4.6 deep in a 5.0 plate | **Floor 0.4 mm**, under the 0.6 mm minimum wall, under a screw head | **Depth 3.0**, floor 2.0 mm: the depth of the other three dia 8 counterbores in the table. (4.6 is the stock depth for an M4 cap head; the plate is too thin for it) |

Rows that are thin but can be made, built as given and flagged: P1 and P3 leave **1.0 mm** between the B
counterbores and the outside edge. P5 and P6 are as the table says with nothing to flag.

Everything else follows the table: first hole of each ring at 0 degrees, counterbores from the top face.
