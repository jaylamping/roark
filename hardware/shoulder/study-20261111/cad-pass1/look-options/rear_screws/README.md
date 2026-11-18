# Fork joint screws seen from behind (2026-11-12)

![sheet](SHEET_rear_screws.png)

Rows: back, rear three-quarter. Columns: the earlier two-screw joint (X ±17), and the real six-screw joint, both on the
r 47 sleeve.

**Why six:** the roll stop's torque runs through this joint (checks/B_ROLL_STOPS.md).
- Six M4 bring the rated-torque layer SF at the joint from 1.32 to 1.64.
- They are X ±17 and ±27 at Y 356.9, and X ±22 at Y 345.5.
- Heads are recessed in counterbores. Nothing is proud.

**Seen from behind:** six round holes, four in a row and two lower, just above the Y 340 shut line.

**One untidy spot:** the outer ±27 counterbores sit right at the fork rear's side edge, by the split, so each reads as a
hole partly open at that edge. Moving them in to ±25 would clear the edge, at a small cost in joint margin. Say if Joey
would rather have that.

## Update 2026-11-12: layout N adopted

![sheet](SHEET_rear_screws.png)

Columns: layout N (on the real parts since 8130d8e), the rejected symmetric layout G, and N with flush printed caps
(option b, mock-up for Joey's pick). The edge-breaking "before" layout is shown in the sheet at commit 9b4569c.

- **N:** top row X -27, -17, +17, +26 at Y 357; lower row -22, +20 at Y 345.5.
  - Every counterbore is fully closed, with at least 1.5 mm of skin to the fork rear's edge. The swell is off-centre, so
    the right edge allows only +26.6 / +21.
  - Rated-torque joint layer SF **1.49** (FEA), against 1.5. Accepted as inside FEA scatter.
- **G** (symmetric ±12/±24, ±20) looks tidier but drops the joint to 1.33. Rejected.
- **Screws:** all six are ISO 7380 M4 button heads, because the outer recesses are only about 3.1 mm deep.
- **Caps option (b) on N:** a 0.3 mm shut circle round each Ø8 cap, flush with the surface. Mock-up only.

