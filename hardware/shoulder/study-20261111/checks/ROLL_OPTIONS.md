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

## What every deck in the cap costs: the 6808's support

- **Today the stub** (the 6808's inner seat, on the cap's boss at r 24) is carried out to the rim by the spoke (a 33 mm
  wide bar from the trunk at 135° to the axis), the stop ring (solid, r 26-44, 189° of arc, 7.8 mm deep) and the 3 mm
  rear plate.
- **A spiral needs its ring free all the way round, over the full depth.** The spoke has to stop at r 43 and the stop
  ring goes. The boss then hangs on the 3 mm rear plate alone, and no rib can cross the spiral's ring.
- In (h) as first drawn, the plate also gets an arc slot for the cable post right beside the boss.
- **Softer versions:** the cable post on the outside of the spiral (inner end anchored to the boss, outer end on a fork
  post at r 42 through the stop's own slot), so the plate stays whole out to r 40; and a 6.5 mm deck with a 4.3 mm plate.
- Not calculated. It applies to (h), (d) and (c).

## Options

| | What | Parts touched | Outline, depth | Roll travel | What is uncertain |
|---|---|---|---|---|---|
| **(h)** | Stop out to r 44.5-51.5 on the cap's rim; cap screws moved out of the stop's arc to about 70 / 180 / 222°, with a printed hook tab near 310°; spiral in the freed ring | Cap, fork rear, drum (three pilots) | Unchanged | Full, -11° to +110° | The tooth is 5 mm in radial height on a 12.9 mm cantilever from the joint plane (10 mm and 8.8 mm today). Stop force falls to about 1,250 N from 1,710 N at a stall. The cap's fixing is lopsided: three screws within 152° |
| **(d)** | Keep the stop where it is but narrower (tooth r 37.5-43); spiral in r 26.5-36 | Cap, fork rear | Unchanged | **About 72°**, for example -11° to +61° | The narrower tooth: about 35% less section |
| **(c)** | Move the roll stop to the front; the whole cap ring goes to the spiral | Cap, fork rear, drum (lip), fork front (dome) | Unchanged | Full | See below |
| (a) | Stack the spiral behind the stop | Cap, fork rear | **Grows 7-8 mm at the back** | Full | Against the rule |
| **(f)** | Keep today's on-axis route; hold the wires only at the far ends of the two channels, so they twist over about 143 mm | None (two lips rounded) | Unchanged | Full, on paper | The two right-angle bends in the bore, about R 6-9 |
| (e) | Leave the cap alone: a spiral in the fork rear's cheek, behind the 6808, fed through the stub bore as today | Fork rear, cap (the stub runs on 6 mm as a post) | Unchanged | Full, **only with 18 AWG** | See below |

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

## (f) Keep the on-axis route and lengthen the free twist: paper check

**The idea:** change no structure. Let the wires twist over more than the 18 mm between the two channels.

- **What sets the twist length:** where each wire is first held. A loose single in a 16 × 6 channel can turn about its own
  length, so the twist spreads back along the channel to the first clamp. Today's count of 18 mm assumes the wires are
  held right at the bore.
- **How far back the clamps can go:**

  | Side | Straight channel from the bore | Clamp at |
  |---|---|---|
  | Rear cap | About 45 mm, from the bore to the trunk inlet at r 58 | The trunk inlet |
  | Fork rear | About 80 mm, from the axis down the leg to where the R 24 bend starts (Y 343.6) | The top of the bend |

- **Free length:** 45 + 18 + 80 = **about 143 mm.** Twist: 121° over 143 mm = **0.85° per mm.** The rule (150 mm per
  ±90°) allows 1.2° per mm. **On paper it meets the rule.**
- **With a funnel only** (each channel opened to a fan inside the cap's boss, r 12.5 to 24, and inside the fork's cheek,
  r 12.5 to 30, and the wires clamped at the fan's edge): 11.5 + 18 + 17 = about 47 mm, 2.6° per mm. Not enough alone.
- **What it does not fix:** the two right-angle bends at the bore's ends. They stay at about R 6-9 (the bore is r 12.5),
  under the static rule of 15 mm, and the bend's direction turns round the wire as the joint rolls. A rounded lip
  (R 5-6) at each channel mouth is the most the bore allows.
- **Needs:** loose singles, nothing tied within the channels, no splice lump in those 45 and 80 mm, and the mouths' lips
  rounded (two small cuts, inside the parts).
- **It is exactly what the roll rig's test A can show,** if the wires are left free in the rig's channels and held
  beyond them (test A2 in CABLE_RIGS.md).
- **Judgement:** the cheapest option by far, and the only one that leaves both bearing supports alone. The bends are
  the doubt.

## (e) A deck in the fork rear's cheek: paper check

- **Where:** behind the 6808, inside the cheek (r 35, Z -45.9 to -56.7). The cable comes through the stub bore as today,
  leaves the stub's end sideways (the stub runs on 6 mm as a post, r 13-20), and spirals out to an anchor at r 32, where
  the fork's channel starts down the leg.
- **Radial room:** inner wrap at r 21, outer wall at r 33. A 3 mm band needs r 32.3. **Fits,** but every radius is 21 to
  33 mm: under the 30 mm rule, and under the arm thread's 24 on the inner turn.
- **Depth:** from 1.5 mm behind the bearing (Z -49.2) to a 2 mm back skin (Z -54.7): **5.5 mm.** Two 16 AWG stacked need
  6.5. **Does not fit with 16 AWG.** Two 18 AWG (5.1 mm) fit, but this crossing carries the yaw motor and the whole arm
  (16 A by the fuses, about 6 A realistic).
- **Cost:** the cheek is the fork's bearing support, as the cap is the drum's. Hollowing it to a 2 mm back skin weakens
  the 6808 housing's path into the leg.
- **The two bends inside the Ø25 bore stay** (cap channel into the bore, bore into the deck), about R 8-10, but they no
  longer move.
- **Judgement:** no better than a deck in the cap. Every place for a spiral at the roll joint is inside a bearing
  support.

## Where this leaves the roll crossing

1. **Run the roll rig's tests A and A2 first.** If today's route survives with the wires held far back (option (f)),
   nothing structural changes.
2. If it fails, the choice is between a spiral that weakens one of the two bearing supports (cap or cheek), less roll
   travel, or 18 AWG through the roll joint. None is free; each needs its own load case before it can be offered.

