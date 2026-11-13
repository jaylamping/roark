# Roll crossing: where a spiral deck and the roll stop can both live (2026-11-13)

Follows [CABLE_TRAVEL.md](CABLE_TRAVEL.md), roll section. **Only needed if the roll rig fails today's on-axis route**
([CABLE_RIGS.md](CABLE_RIGS.md), test A). Nothing is built; no real part is changed.

## The conflict

- **The rear cap is already hollow:** a cavity from the boss (r 24) to the rim (r 51.5), 7.8 mm deep, behind a 3 mm rear
  plate. A spiral for 121° needs the ring from r 28 to r 41.6 of it.
- **That ring is the roll stop's:** a solid stop ring r 26-44 with an arc slot r 28-42; the fork rear's tooth (r 30-40, at
  270°, standing on the 6808 housing's face) runs in it.
- **Outside r 44 are the three cap screws** (r 50, at 0 / 180 / 270°, bosses r 5).
- **The tooth must stay at 270°:** only there does the fork rear have material beyond r 35 (the leg).

## Options

| | What | Parts touched | Outline, depth | Roll travel | What is uncertain |
|---|---|---|---|---|---|
| **(h)** | Stop out to r 44.5-51.5 on the cap's rim; cap screws moved out of the stop's arc to about 70 / 180 / 222°, with a printed hook tab near 310°; spiral in the freed ring | Cap, fork rear, drum (three pilots) | Unchanged | Full, -11° to +110° | The tooth is 5 mm in radial height on a 12.9 mm cantilever from the joint plane (10 mm and 8.8 mm today). Stop force falls to about 1,250 N from 1,710 N at a stall. The cap's fixing is lopsided: three screws within 152° |
| **(d)** | Keep the stop where it is but narrower (tooth r 37.5-43); spiral in r 26.5-36 | Cap, fork rear | Unchanged | **About 72°**, for example -11° to +61° | The narrower tooth: about 35% less section |
| **(c)** | Move the roll stop to the front; the whole cap ring goes to the spiral | Cap, fork rear, drum (lip), fork front (dome) | Unchanged | Full | See below |
| (a) | Stack the spiral behind the stop | Cap, fork rear | **Grows 7-8 mm at the back** | Full | Against the rule |

## (c) A stop at the front: an honest look

**What it would be:**
- The fork front's dome (r 55, Z 39-47) faces the drum's front lip (r 43-57, Z 28.3-36.0) across a 3 mm gap. The dome's
  back is pocketed: five pockets, r 24.5-52.6, 5.6 mm deep, behind a 2.4 mm skin.
- **A tooth on the drum's lip face,** between two of the roll motor's eight mounting screws, standing 7.5 mm forward into
  one of the dome's pockets. That pocket's two end walls are the stops.
- The tooth can be about 10 mm wide and 4.5 mm in radial height, at r 46-52. Lever arm about 49 mm.

**What it bears on:**
- **Drum side:** the lip, which is bolted to the roll motor's housing by the eight screws. A short, direct path.
- **Fork side:** a pocket end wall of the dome. Today those walls are 10° ribs between pockets, about 4.5 mm thick at
  r 49, standing on a 2.4 mm skin. The fork front prints upright, so the rib is loaded across its layers in bending.
- **Then:** through the fork front to the roll motor's output (six screws and three pins). The fork rear and the 6808
  are no longer in the stop's path.

**Numbers on paper:**
- Stop force 1,220 N at a 60 N·m stall, 350 N at the 17 N·m software limit.
- Contact 4.5 × 5 mm: 54 MPa at a stall, 15.5 MPa at the software limit.
- Tooth root, 10 × 4.5 mm in shear: 27 MPa at a stall, 7.8 MPa at the limit.

**What it costs:**
- The pocket has to span the travel plus the tooth: about 135°. Two pockets (50-130° and 140-200°) merge into one of
  150°, so one rib of the dome goes. That weakens the dome between the roll output and the sleeve.
- The whole of B_ROLL_STOPS.md is redone for a different torque path, and C_LOAD_SHARE.md checked again (the 6808 no
  longer shares the stop load).
- Four parts change instead of three.

**Does it show from outside?** No. The tooth and the pocket are between the dome and the lip, inside the 3 mm gap.

**Judgement:** it can probably be made to work at the software limit, like today's stop. It is not better than (h) on
the evidence so far: (h) keeps the stop on the fork rear, where the layers suit it, and touches fewer parts. (c) is the
fallback if the tooth of (h) fails in section or the lopsided cap fixing is not accepted.
