# D1 restate: buck board mount (written before modelling)

1. **Purpose.** A printed PETG mount that holds the 85 x 60 x 1.6 mm 12 V buck board on the top front rail (20 x 20, along X, top face Z 0), and lets the board come out with the mount left on the rail.
2. **Fixed.** Rail interface: M5 into T-nuts in the 6 mm top slot. Board: four Ø3.2 holes 3.5 mm in from each edge (78 x 53 pattern), parts 14 mm above and 3 mm below, wire pairs out of one 60 mm edge. Envelope: Z <= 45, Y -25 to 25. Load 9 N any direction. Both faces of the board at least half open.
3. **Good.** The board leaves with only the M3 board screws undone (no M5 touched), every screw has a tool path with the board in place, 9 N at a factor of at least 2 on all three measures (yield 45, across layers 22.5, interlayer shear 13 MPa), light, prints without supports.
4. **Mine to choose.** The tilt, the fasteners, the shape, the print direction, the extras (key into the slot, strain relief for the wires).
5. **Contradiction found before any modelling.** The envelope is 50 mm wide in Y and the board is 60 x 85: it cannot lie flat in Y. Standing on its 85 mm edge, 60 tall, it is over the 45 mm height. Only a tilt about the rail axis X works: the 60 mm side must satisfy 60 cos(th) + parts <= 50 and 60 sin(th) + parts + clearance <= 45. I build the nearest thing that works: **tilt 41 degrees** (see report), and say so.

## Assumptions (answers I am assuming so that work goes on)
| Question I would ask | Answer I assume |
| --- | --- |
| Can the board be tilted, or is the 50 mm Y envelope firm? | Tilt is fine, envelope firm. Tilted about X by 41 degrees, rising toward +Y. |
| Where are the 14 mm tall parts, and the 3 mm underside parts? | Tall parts only inside the middle 24 mm of the 60 mm side and the middle 60 mm of the 85 mm side; the 3 mm underside (solder joints, pins) can be anywhere on the board but nothing but the four hole keep-out rings (Ø9) is guaranteed clear. |
| Which 60 mm edge do the wires leave from, and do they leave sideways? | The +X edge, along X, crimped lugs or a terminal block at that edge. Nothing of the mount beyond X +42.5 above the base. |
| Is the keep-out round each mounting hole free of parts on both faces? | Yes, Ø9. |
| Screw type? | M3 thread-forming button-head screws (ISO 7380, head Ø5.7 x 1.65), 6 mm, no washer, into Ø2.7 pilots in the printed standoffs (no inserts, because the envelope has no room for the deeper boss an insert needs on the high edge). |
| T-nuts? | Two standard M5 drop-in T-nuts (slot 6 mm), M5 x 14 socket head screws, 4 mm hex key. |
| Tall robot-side loads (10 g) act through the board centre of mass at 90 g. | Yes. 9 N through the centre of the board. |
| Is a wire strain relief wanted? | Yes: 4 mm2 wire is stiff; two zip-tie slots on the base at the +X end. |
| Print material and direction? | PETG, base flat on the bed. |
