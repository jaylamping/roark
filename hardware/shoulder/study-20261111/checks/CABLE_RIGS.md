# Cable crossing rigs (2026-11-13)

Small printed rigs that settle, by hand and with the real wires, what [CABLE_TRAVEL.md](CABLE_TRAVEL.md) could only
work out on paper. PLA, flat, no support. Script: `cad/scripts/shoulder/cable_rigs.py`. Files:
`cad/exports/fixtures/fixtures_cable_rig_*.STL`, already turned to print flat.

**Not released for printing yet.** The roll rig is ready; the yaw update and the pitch rig follow.

**Wires for every test:** the real ones. Two 16 AWG high-strand silicone wires (OD 3.0) and one twisted 26 AWG pair,
loose, not sleeved, about 400 mm long.

## Roll rig

**Why first:** if today's route through the stub bore survives with real silicone wire, the roll joint needs no rework.
If it fails, the same print shows whether a spiral deck works.

![roll rig](cable_rigs/roll_rig.png)

| Part | File | Mass (sliced) | Print time |
|---|---|---|---|
| On-axis rig, base | `fixtures_cable_rig_roll_axis_base.STL` | 8.5 g | 27 min |
| On-axis rig, top | `fixtures_cable_rig_roll_axis_top.STL` | 4.2 g | 14 min |
| Deck rig, tray | `fixtures_cable_rig_roll_deck_tray.STL` | 16.4 g | 28 min |
| Deck rig, lid | `fixtures_cable_rig_roll_deck_lid.STL` | 6.8 g | 17 min |
| **All four** | | **35.9 g** | **about 1 h 35 min on one plate** |

- Sliced at 0.20 mm with the arm's PETG settings; PLA will be close. Turn supports off (the slicer adds a little under
  the on-axis parts that they don't need).
- All four pass the integrity scan.
- Also needed: one M4 × 16 screw and nut (deck rig), two small cable ties, tape, a marker.

**What each reproduces:**

| Rig | Real geometry | In the rig |
|---|---|---|
| On-axis | Rear cap's radial channel, 16 × 6 | Channel on the base, running into the bore |
| | Stub bore Ø25 | The base's tube |
| | 18 mm between the two channels' centres | Lower channel centre 3 mm up, upper 21 mm up |
| | Fork rear's radial channel, 16 × 6 | Channel in the top, which turns on the tube |
| Deck | Cap cavity: boss r 24, 7.8 deep | Tray: boss wall r 24, floor to lid 7.8 |
| | Spiral band r 28 to 41.6 | Tray's outer wall at r 43 (wire centre at 41.5) |
| | Outer anchor where the trunk's spoke comes in | Gap in the outer wall with a tie bar |
| | Post on the fork rear's housing face, r 28-31 | Post under the lid, with the exit slot and tie holes beside it |

Not reproduced: the bends above and below each rig, PETG, the weight of the arm on the wires (none).

### Test A: today's route (on-axis rig)

1. **Thread** the three wires along the base's channel, up the bore, and out along the top's channel. Fit the top on the
   tube.
2. **Tape the wires down** in each channel 25 mm from the bore, with the top at 85° from the base's channel (mid travel)
   and the wires neither tight nor slack in the bore.
3. **Mark** each wire with a line where it enters the bore at the bottom and where it leaves at the top.
4. **Turn the top from 25° to 146° and back** (that is roll +110° to -11°: the two channels are 135° apart at roll 0).
   Use the scale on the base. Do it slowly five times and watch the wires in the bore from above.
5. **Then 200 cycles by hand.**
6. **Look:** kinks, a wire climbing over another, a mark that has moved (the wire is being pulled through the tape),
   white stress marks or a flattened spot in the insulation, a wire that has taken a set.

**Pass:** no kink, no mark moved by more than 1 mm, insulation unmarked after 200 cycles, and it turns by a light touch
at both ends of travel.
**Fail:** any kink, or it needs force near either end, or the wires spring the top back.

### Test B: spiral deck (deck rig)

1. **Lay the spiral.** With the lid off, clamp the wires at the outer anchor with a tie (power wires stacked one on the
   other, the pair beside them). Lay them clockwise round the tray, about 1.2 turns, against the outer wall.
2. **Fit the lid** with its pointer at mid travel, lead the inner end up through the slot beside the post, and tie it to
   the two tie holes with the wires lying against the post's trailing side. Fit the M4 and nut so the lid turns freely.
3. **Turn the lid stop to stop** (the tray's two stops are roll -11° and +110°). In one direction the spiral winds onto
   the boss; in the other it opens against the wall. If it runs the wrong way (the wires go slack then tight), re-lay it
   the other way round.
4. **Five slow cycles,** watching through the lid's slots: does the band stay one wire thick, do the wires stay stacked,
   does anything bunch or cross?
5. **Then 200 cycles by hand.**
6. **Look,** as in test A, and at the tie points: has either end pulled?

**Pass:** the wires stay in their band, nothing bunches or lifts the lid, no kink at the post or the anchor, light and
even feel over the whole travel, wires unmarked after 200 cycles.
**Fail:** bunching, a wire trapped under another, the lid lifting, or a tight spot.

**What to send back:** for each test, pass or fail, at what angle anything happened, and a photo of the wires afterwards.
If test A passes cleanly, say so plainly: it decides whether the cap and fork rear are redesigned.

## Yaw rig (second version)

*To follow.*

## Pitch rig

*To follow.*
