# Cable crossing rigs (2026-11-13)

Small printed rigs that settle, by hand and with the real wires, what [CABLE_TRAVEL.md](CABLE_TRAVEL.md) could only
work out on paper. PLA, flat, no support. Script: `cad/scripts/shoulder/cable_rigs.py`. Files:
`cad/exports/fixtures/fixtures_cable_rig_*.STL`, already turned to print flat.

**Not released for printing yet.** All three rigs are exported: roll (do this one first), yaw (second version), pitch.

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

**What changed from the first yaw rig** ([CABLE_LOOP_RIG.md](CABLE_LOOP_RIG.md)): the bundle is clamped at both ends and
no longer slides through the window. The hub's chutes are the slot of hub D3c6 (not cut inside 15.7 mm along its line),
four hollow posts stand where the boss tubes beside the two windows are, and the exit stub's roof has two tie slots. The
boss and cap of the first rig are used unchanged.

![yaw rig](cable_rigs/yaw_rig2.png)

| Part | File | Mass (sliced) | Print time |
|---|---|---|---|
| Hub | `fixtures_cable_rig_yaw2_hub.STL` | 15.4 g | 43 min |
| Fork side | `fixtures_cable_rig_yaw2_fork.STL` | 9.6 g | 26 min |
| Boss, cap (first rig) | `fixtures_yaw_loop_rig_boss.STL`, `_cap.STL` | 3.2 g, 2.2 g | 9 min, 5 min |
| **All four** | | **30.4 g** | **about 1 h 30 min on one plate** |

- Turn supports off. All parts pass the integrity scan.
- Also needed: one M4 × 16 screw and nut, two small cable ties, tape.

### Test C: spiral with 18 AWG

**Wires:** two **18 AWG** silicone wires (OD 2.3) and one 26 AWG pair, about 700 mm.

1. **Clamp at the exit:** thread the wires in through the exit stub and tie them down through the two slots in its roof,
   power wires side by side.
2. **Lay the spiral** on the hub's floor with the fork side off: from the exit, about 2.25 turns round the boss toward the
   68° window, the two power wires stacked one on the other, the pair beside them.
3. **Clamp at the window:** lead the end down the 68° chute and tie it to the post beside the chute, below the floor. Tape
   over the 248° window.
4. **Assemble** (boss, fork side, cap, M4) with the pointer at 0.
5. **Turn -90 to +90, five slow cycles,** watching through the roof slots. One way the spiral winds onto the boss, the
   other it opens against the skirt. If it runs the wrong way, re-lay it the other way round.
6. **Then 200 cycles by hand.** Look at the wires and at both clamps.

**Pass:** the wires stay in one band about 4 mm wide, stacked; nothing bunches, crosses or lifts the roof; nothing enters
the gap between the hub's rim and the skirt; even, light feel; wires unmarked after 200 cycles.
**Fail:** bunching, a wire trapped under another, a tight spot, the roof lifting, or the pair in the rim gap.

### Test D: plain arc with 16 AWG, ±37°

**Wires:** two 16 AWG and one pair, about 400 mm.

1. Clamp at the exit as in test C.
2. Lay one arc from the exit round the +X side (the short way from the exit to the window with the pointer at +37) to
   the 68° window, flat, power wires side by side. Clamp at the post.
3. Turn between -37 and +37. The arc should move from the skirt (short) to the boss (long) and back.
4. Five slow cycles, then 200. Try ±45 and ±50 once, gently, and note where it goes tight or bunches.

**Pass:** free from -37 to +37 with nothing bunching. **Report** the largest travel that stayed free.

## Pitch rig

**What it reproduces:** the loop channel round the pitch motor (inner wall r 57.4, outer wall r 73.5, 21.1 high) as a
fixed tray with a 30 mm slot at the bottom, a round guide finger (R 10) at the slot, and a tongue below the slot with
two tie holes for the fixed clamp. The lid is the drum's flange: it turns on an M4 at the centre and carries the trunk
mouth (13 × 4) with two tie holes at r 65.

![pitch rig](cable_rigs/pitch_rig.png)

| Part | File | Mass (sliced) | Print time |
|---|---|---|---|
| Tray | `fixtures_cable_rig_pitch_tray.STL` | 31.3 g | 53 min |
| Lid | `fixtures_cable_rig_pitch_lid.STL` | 11.6 g | 40 min |
| **Both** | | **42.9 g** | **about 1 h 40 min on one plate** |

- 149 × 180 mm on the bed. No support. Both pass the integrity scan.
- Also needed: one M4 × 30 screw and nut, three small cable ties, about 30 g to hang (six M8 nuts on a paper clip) or a
  thin elastic, a pen to mark angles on the tray's rim (the lid has a pointer).

### Test E: spiral, about 115°

**Wires:** two 16 AWG and one pair, about 1.2 m.

1. Lay the tray flat. Tie the wires to the tongue's tie holes, lead them over the finger into the channel and lay 2 turns
   against the outer wall, the three wires side by side across the channel's height.
2. Bring the end up through the lid's mouth and tie it to the lid's two holes. Fit the lid and the M4.
3. Mark the lid's start on the tray's rim. Turn the lid in the winding direction until the wires are snug on the inner
   wall; mark that. Measure the angle between the marks.
4. Five slow cycles between the marks, then 200.

**Pass:** at least 110° between the marks, the wires staying side by side in one layer, light even feel.
**Report** the angle.

### Test F: wrap and bight, 230°

**Wires:** as test E, about 900 mm.

1. **Hold the tray upright,** slot at the bottom (clamp the tongue's lower edge in a vice, or tape the tray to a shelf's
   edge with the tongue hanging over).
2. Tie the wires to the lid's mouth with the lid's pointer 20° past the slot. Lead them round the inner wall, over the
   finger, down through the slot.
3. **Hang the weight** on the wires as a loop below the slot, and tie the free end to the tongue's tie holes so that the
   loop is about 140 mm deep.
4. **Turn the lid through 230°** in the direction that wraps the wires onto the inner wall. The loop should rise to
   about 15 mm. Turn back: the loop should fall to 140 mm again, on its own.
5. Five slow cycles, then 200. Try 270° once.
6. Repeat with the elastic in place of the weight (anchored about 300 mm below the slot, just taut at the loop's
   deepest), and with no pull at all.

**Pass:** the loop follows both ways on its own with the weight, the wires stay on the inner wall and leave it at the
finger, nothing bunches in the channel, wires unmarked after 200 cycles.
**Report:** the smallest pull that still makes the loop follow (weight in grams), whether the elastic does it, the loop
depth at each end, and whether 270° also works.
