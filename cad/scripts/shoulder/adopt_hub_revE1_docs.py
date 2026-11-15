"""PREPARED, NOT RUN: the PRINT_NOTES and CAD_NOTES text for the adoption of hub rev E1. Run once, right after
adopt_hub_revE1.sh, from this folder:   python adopt_hub_revE1_docs.py YYYY-MM-DD <sha256 of the adopted STL>
Each replacement asserts that its anchor is there exactly once."""
import sys
from pathlib import Path

DATE, SHA = sys.argv[1], sys.argv[2]
R = Path(__file__).resolve().parents[3] / 'hardware' / 'shoulder' / 'study-20261111' / 'cad-pass1'


def edit(name, pairs):
    p = R / name
    s = p.read_text(encoding='utf-8')
    for a, b in pairs:
        assert s.count(a) == 1, (name, s.count(a), a[:70])
        s = s.replace(a, b)
    p.write_bytes(s.encode('utf-8'))
    print('edited', name)


HUB = f"""### Hub (rev E1, adopted {DATE})

**Print file:** `shoulder_hub_left_revE1.3mf` with the STL and a README, on holly-pc in `C:\\joe\\prints\\shoulder-hub\\`
and on Joey-PC in `J:\\code\\prints\\shoulder-hub\\`. Not in the repo. **Rev D3c7's file there is superseded:** D3c7 has
six slits through its top and is good for the fit bench only.

- **Colour:** black PETG. **Settings:** Generic PETG, 0.20 mm, 6 walls, **100 % infill, no brim**, tree supports with
  blockers round the groove and at the two lugs, Cool Plate SuperTack. Motor face down, lugs up.
- **Sliced:** 113.8 g, 3 h 12 min; 4.9 g of it support. Part 115.2 g by volume.
- **Supports:** all in the lowest 4.6 mm on the plate side: a ring under the floor of the cable space, open at the rim,
  and small plugs in the mouths of the six screw holes, the centre hole and the cable tunnel. **Nothing inside the hub.**
- **After printing:** peel the ring off at the rim; pick out the plugs; smooth the cable space's floor and the tunnel's
  mouth. **Clear the cable tunnel with a 4 mm rod:** straight down the mouth from the cable-space side (6 mm), and up
  from the bore at about 40° to the bore's axis. Check the lug holes with a 3.8 mm drill shank. Measure the spigot
  (CAD 71.6 mm). Ream the two smaller holes to 4.00 mm when the shoulder goes together.
- **What rev E1 is** (A_HUB_LUGS.md, "Rev E1"): the centre 3 mm taller (cable gap 8.5 mm; the hub and the arm sit 3 mm
  lower on the yaw axis), the six top slits filled, the inner pocket solid, the centre plate 11 mm thick, the six screw
  tubes dia 10.8, a 4.5 × 11 mm cable tunnel with one bend that stays clear of the step ring. The arm's side is unchanged.
- **Screws: six M4 × 30, each with ONE standard flat washer** (dia 9, 0.8 thick), **snug by hand.** 6.2 mm into the
  motor. Without the washer 7.0 mm, which is all the thread the RS02's drawing promises: do not leave it out. Two
  washers, or a flat and a split spring washer (about 1.0 mm): 5.2 to 5.4 mm, still enough. Any two of the six go in
  the reamed holes; they need not be partially threaded.
- **Threading the cable:** bare wires only, from the cable-space side, one or two at a time with tweezers; they come
  out in the bore and hang straight down against its wall (about r 21.5). Tie the bundle to the screw tube next to the
  tunnel, inside the bore. Cut the length in the cable space to about 500 mm (CABLE_TRAVEL.md).

### Hub rev D3c7 (superseded {DATE}; kept for the record of the stage 1 print)
"""

edit('PRINT_NOTES.md', [
    ("### Hub (rev D3c7, released for the stage 1 print 2026-11-14)\n", HUB),
    ("| **Hub** | `shoulder_hub_left` | 80.2 g | 2026-11-14 (rev D3c7, adopted) | **Released for the stage 1 print. Print file ready** (hub section below) |",
     f"| **Hub** | `shoulder_hub_left` | 115.2 g | {DATE} (rev E1, adopted) | **Print file ready** (hub section below). Rev D3c7's print is superseded: fit bench only |"),
    ("| Hub → RS02 output | 6 × M4: **M4 × 28**, or M4 × 30 with 1.6-2 mm of washer under the head. 2 of them partially threaded, in the reamed holes |",
     "| Hub → RS02 output | 6 × **M4 × 30, each with one standard flat washer** (dia 9, 0.8 thick). Rev E1's seats are set for it: 6.2 mm into the motor |"),
])

CAD = f"""

## Adopted {DATE}: hub rev E1 (taller, solid top)

Joey's decisions of 2026-11-15: the hub's centre 3 mm taller; M4 × 30 with washers; stronger over sooner. The arm thread
checked the candidate against rev D3c7 on its side and gave its go.

- **Built by** `hub_candidate2.py` on the archived rev D3c7 part (`cad/_archive/hub_revD3c7/`, not in git), through
  `adopt_hub_revE1.sh`. The part's last feature moves the body 3 mm down the yaw axis, so the part file and the exports
  are in the assembly frame: top face on the RS02's output face at Y 319.86, body Y 285.00 to 319.86.
- **STL SHA-256** `{SHA}`. 90,700 mm³, 115.2 g PETG (rev D3c7: 63,202 mm³, 80.3 g).
- **For the arm and the URDF:** RS02 output face to the hub's disc underside, where the arm's end face seats: 17.86 mm
  before, **20.86 mm** now. Everything on the arm moves 3.00 mm down the yaw axis.
- **What changed** (in the arm's coordinates nothing below Y 302 moved): top face +3.0; six slits r 19.0-19.5 filled;
  pocket under the spigot's ledge solid; centre plate thickened 4 mm downward between the tubes; tubes dia 10.8; head
  seats at Y 299.86 (were 298.06); cable slot 4.5 × 11 as a dog-leg (down through the dish floor at r 27.0-31.5, then
  50° inward, out through the bore wall at Y 302.1-309.1), mouth rounded 1.5, knee rounded 2.0, exit lip cut square;
  R 2 from the step wall into the dish floor; seat-face hole edges square.
- **Strength:** A_HUB_LUGS.md, "Rev E1". Hub top 3.2 / 2.1 / 3.7 (layer / shear / von Mises, worst 0.5 mm ball) against
  0.65 / 0.38 / 0.73 for rev D3c7; lug gate 1.56 (1.44); elbow stop 3.10 (2.49).
- **Not done here:** the fork front's skirt, 3.00 mm longer to follow the hub (with the fork front's next revision,
  OPEN_ASSUMPTIONS item 49); the clearance sweep's result (`clearance_adopt_hubE1.json`) is to be read after the
  adoption run.
"""
p = R / 'CAD_NOTES.md'
s = p.read_text(encoding='utf-8')
p.write_bytes((s.rstrip('\n') + CAD).encode('utf-8'))
print('appended CAD_NOTES.md')
