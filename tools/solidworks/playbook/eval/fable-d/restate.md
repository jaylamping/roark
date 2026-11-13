# D1 restated (written before any modelling, 2026-11-13 08:45)

## The five lines

1. **What it is for:** a printed PETG mount that holds the 12 V buck board (85 x 60 x 1.6 mm, 90 g) on the top front
   rail of the torso, and lets the board come out while the mount stays screwed to the rail.
2. **Fixed:** rail 20 x 20 along X, top face Z 0, 6 mm T-slot on the centre of each face, M5 into T-nuts. Board holes
   4 x dia 3.2, 3.5 mm in from each edge, so at X +/-39, Y +/-26.5 on a board centred on the rail. Keep-outs 14 mm above
   and 3 mm below the board. Wires leave one 60 mm edge.
3. **Good means:** the board comes out with a common tool from one side, every screw reachable; 10 g (9 N) in any
   direction with a factor of at least 2 on yield, across layers and between layers; both board faces at least half
   open; inside Z 45 and Y +/-25; light, prints without supports.
4. **Mine to choose:** how the board is held, its height and attitude, where the M5 screws go, the print direction.
5. **Budget (60 min):** restate 5, two ideas and first shape 15, detail and exports 10, study 15, report 15.

## The request contradicts itself: found before modelling

The board is 60 mm wide and the envelope is 50 mm wide (Y -25 to 25) and 45 mm high. The board with its keep-outs is a
60 x 18.6 mm rectangle in section (85 long). Tilted by an angle t it needs 60 cos t + 18.6 sin t in Y and
60 sin t + 18.6 cos t in Z:

| Attitude | Y needed | Z needed | Over the envelope |
| --- | --- | --- | --- |
| flat, centred on the rail | 60 | 18.6 + standoff | Y by 5 mm each side |
| tilted 30 degrees | 61.3 | 46.1 | both |
| tilted 55 degrees (first angle that fits Y) | 49.6 | 59.8 | Z by 15 mm and more |
| on edge | 18.6 | 60 + 2 | Z by 17 mm |
| on edge, hanging in front of the rail | 18.6 in a 15 mm strip | fits | Y by 3.6 mm in front, and uses space below the rail top nobody gave me |

No attitude fits. **Decision:** board flat, centred on the rail, overhanging Y by 5 mm on each side (Y -30 to 30); the
height is then 24 mm of the 45 allowed. It is the smallest excursion that needs nothing unknown, it keeps the load
path short, and it is one constant in the script (`BOARD_Y0`) to move the whole overhang to the back if the front is
the hard limit. The printed part stays inside the board's own outline. `envelope_ok` is reported false, with the number.

## Assumptions

- Frame: X along the rail, Y across (front is -Y), Z up, rail top at Z 0, rail centred on Y 0. Board centred at X 0.
- The 14 mm and 3 mm keep-outs cover the whole board face except a dia 7 land round each hole.
- The wires leave the +X end, and can be dressed either side of a dia 9.5 screw head on the rail centre line.
- "Open to air" means not covered in plan by the mount; the rail itself, 8 mm below the board, is reported separately.
- M3 heat-set inserts (dia 4.0 hole, 6 deep, as the housing task uses) are acceptable in the mount.
- 10 g acts on the board's 90 g only, at a centre of mass 5 mm above the board; the mount's own 11 g adds 1 N at most.
- The space below the rail top, in front of and behind the rail, is not mine to use.

## Questions I would ask (with the answer I am assuming, so work goes on)

1. The board cannot fit in Y +/-25 in any attitude. May it overhang 5 mm each side, lying flat? Or is one side hard
   (the front skin) and the other soft? **Assumed: 5 mm each side is acceptable; `BOARD_Y0` shifts it.**
2. Which 60 mm edge do the wires leave, and where along it are the terminals? **Assumed: +X end, clear of the centre
   10 mm, or the wires lift 7 mm over a screw head.**
3. Is there a bare land round the mounting holes, and how large? **Assumed: dia 7.**
4. Does anything sit on the top slot of the rail within 60 mm either side of the board? The mount is 117 mm long.
   **Assumed: no.**
5. How hot does the board run? PETG softens near 70 C. **Assumed: board under 60 C at the holes; if hotter, the same
   part prints in ASA or PC.**
6. How often does the board come out? **Assumed: many times, hence brass inserts and not screws cut into plastic.**
7. Is 10 g a static equivalent or a shock from a fall? **Assumed: static equivalent, 9 N on the board, any direction.**
