# Check (c): roll joint load share (RS03 output vs 6808 stub) and deflection (2026-11-12, beam model)

**Status: the beam model below is the result.** The FEA of the fork front and fork rear as two bodies (`fea_shoulder.py`
`FORK_*`, from `fork_fea_part.py`) fails to solve with code 24.
- Attempts: the direct solver (2.5 mm mesh), and on 2026-11-12 the one allowed retry on FFEPlus with a 3.5 mm mesh
  (51,215 nodes, 226 s, `fea_fork_MX_brg.txt` alongside).
- **Probable cause:** the two inserted bodies are not treated as bonded at the joint face (they touch at X 149-192,
  Y 352-361.5, Z -45.9). So the fork rear floats. A singular stiffness fails the same way on either solver.
- **Not pursued further,** per the coordinator. To fix it later: set the global contact to bonded explicitly, or
  model the joint screws as bolt connectors.

## The joint

- The fork is a U: the front cheek (fork front) and the rear arm (fork rear) both run from the roll axis (Y 424.86) down
  to the sleeve/collar round the RS02 (Y 314-362). The two parts are bolted at the joint pad.
- **Front support:** the front cheek is bolted to the RS03 output flange (face Z 30.64). The RS03's output bearing takes
  radial, axial and tilting load. Its centre is assumed 8 mm inside the face, at Z 22.6.
- **Rear support:** the fork rear's housing holds the 6808 outer race, floating axially, on the cap's stub. Centre Z -43.8.
  It takes radial load only.
- **Span:** L = 66.4 mm.
- **Load:** the arm's design load from check (a), at the hub point (X 170.49, Y 292, Z 5.99):
  - 310 N along -Y
  - 23 N·m about X (arm forward) or about Z (sideways; about Z it is roll torque for the motor)
  - 17 N·m about Y (the RS02 peak)
  - For the roll joint, the moments about X and Y are tilting moments: the force's line passes through the roll axis,
    so it adds no moment of its own.
- **RS03 output-bearing ratings and tilt stiffness are not in the vendor manual.** RS03 User Manual 261013 has no radial,
  axial or moment rating; CONCEPT.md §12 says the same. So the share is given as bounds.

## Section properties of the legs (from the STL, Y-cuts)

| Y | Front cheek: area / I for X deflection (in-plane) / I for Z deflection (out-of-plane) | Rear leg: area / I (X) / I (Z) |
|---|---|---|
| 365 | 610 / 248,000 / 16,900 | 545 / 155,000 / 10,100 |
| 375 | 819 / 608,000 / 20,100 | 316 / 48,600 / 4,950 |
| 385 | 548 / 454,000 / 5,500 | **167 / 12,500 / 2,530** |
| 395 | 431 / 344,000 / 3,930 | 211 / 25,300 / 2,640 |
| 405 | 750 / 701,000 / 16,200 | 372 / 140,000 / 3,660 |

(mm² and mm⁴.) The rear leg is the compliant member: it is narrowest at Y 385, where it holds the cable channel.

## Load share

**Upper bound for the 6808** (the RS03 bearing as a pin, taking no moment; statics):

| Load | 6808 | RS03 output |
|---|---|---|
| 310 N radial at Z 5.99 | 78 N | 232 N |
| 23 N·m tilt (about X) | ±346 N (along Y) | ∓346 N |
| 17 N·m tilt (about Y) | ±256 N (along X) | ∓256 N |
| **Worst combination** | **495 N** | **632 N** radial, no moment |

**With a moment-stiff RS03 bearing** (crossed-roller type, as is usual in this class of actuator):
- The tilting moments split between the RS03's tilt stiffness K_t and a couple through the fork to the 6808.
- The fork's stiffness at the 6808 is the rear leg in series with the cap/drum path (drum about 47 kN/mm, cap and stub
  stiffer):
  - for X loads: in-plane leg bending, about 570 N/mm, so about 560 N/mm in series
  - for Y loads: axial in the leg, about 7.5 kN/mm, so about 6 kN/mm
- The 6808's share of a tilting moment is k·L² / (k·L² + K_t):

| K_t (N·m/mrad) | X-tilt share to the 6808 | Y-tilt share to the 6808 | 6808 load, worst (N) |
|---|---|---|---|
| 10 (soft: a small bearing pair) | 20% | 72% | about 330 |
| 100 (typical crossed roller of this size) | 2.4% | 21% | about 160 |
| 300 | 0.8% | 8% | about 110 |

The radial 310 N splits about 25 / 75 in all cases: 78 N to the 6808.

**What it means:**
- **The 6808 sees 80-500 N.** Its static rating (C0 about 3 kN) is far above this.
- **The printed seats:** at 495 N, 1.8 MPa on the stub (Ø40 × 7) and 1.4 MPa in the housing. Fine.
- **The RS03 output bearing carries most of the tilting moment** (up to 28.6 N·m combined) unless its tilt stiffness is
  low. Its moment rating is not published. This is the open risk, as MEASUREMENTS.md already flagged ("all three joints
  hang on the motor output bearings").
- **The 6808 relieves the RS03 mainly for the Y-direction tilt** (arm forward: about X), where the fork is axially stiff.
  It does much less for the X-direction tilt (the RS02 yaw torque), where the rear leg bends.
- **Stiffening the rear leg at Y 375-395** (wider in X) would raise the 6808's share of the yaw-torque tilt. It is limited
  by the cable channel inside it.

## Deflection under the design load

| Path | Estimate | Against |
|---|---|---|
| RS03 tilt at 28.6 N·m, K_t 100 N·m/mrad | 0.29 mrad: 0.03 mm at the cuff bottom (r about 110 from the bearing) | 2.0 mm gaps |
| Rear leg, X bending at the full 256 N couple (pinned-RS03 bound) | 0.45 mm at the 6808 relative to the collar. With a stiff RS03, under 0.1 mm | fork rear ↔ cap 2.5; 6808 seat |
| Rear leg axial at 346 N | 0.05 mm | |
| Front cheek, out of plane (Z) | Small. A Z force at the collar is taken as a Y-couple between the two supports (the U-frame acts as a portal), not by cheek bending. Only the RS03 takes axial (Z) load, because the 6808 floats | |

- **Moving gaps:** the largest relative motion at a moving pair is about 0.45 mm. That is the collar against the cap
  side, in the pinned bound under the full design load; realistically under 0.1 mm. All moving pairs are ≥ 2.0 mm
  nominal, so at least about 1.5 mm remains in the worst case.
- **Stack-up:** with the 6808 lip now 0.4 mm clear (check (d)), the closed axial loop no longer preloads the RS03 bearing
  through printed parts.

## Not covered

- The RS03 output bearing's real ratings and tilt stiffness: ask RobStride, or measure the tilt on the bench (a dial
  gauge at 100 mm under a known moment).
- The bolted joint pad between fork front and fork rear (2 × M4): assumed rigid here. The FEA treats it as bonded.
- Dynamic loads beyond the check (a) design set.

## The fork front on the RS03 roll output: rotational location (2026-11-12, paper)

**The joint:**
- Six M4 (counterbored, heads at Z 43) clamp the fork front's 12.4 mm boss to the RS03 output face (Z 30.64).
- The screws sit on r 15.2 at ±30°, ±90° and ±150°, in Ø4.5 clearance holes.
- The boss face is r 10.75-22, so the friction radius is 17.0.
- **Torque through it:** the whole roll torque, 20 N·m rated and 60 N·m at a stall (RS03 manual 261013 §1.3). At the
  stops this includes the full stop reaction (checks/B_ROLL_STOPS.md).

**Friction alone:** 6 × 0.35 kN × 0.25 × 17.0 mm = **8.9 N·m** (5.1 once crept). That is under the rated 20. It slips, and
the Ø4.5 holes allow up to **0.94°** of roll backlash.

**Two close-fit screws are not enough here.** An M4 × 25 partially threaded has only 5 mm of plain shank in the 12.4 mm
boss: 33 MPa bearing at rated.

**Cheapest fix: three dowels in the RS03's own locating holes.**
- The vendor RS03 output has, besides the six tapped M4, **three plain Ø4.0 holes at 0° and ±120° on r 15.2**.
- Ø4 × 16 steel pins, half in the RS03 and half in the fork front boss.
- In the fork front: holes printed Ø3.8, hand-reamed Ø4.00.
- **The pins can be free:** the plain shank of an M4 × 30 partially threaded screw, cut to 16 mm, is a Ø3.96-3.99 pin.
  Buying Ø4 m6 dowels is better but optional (about 0.10 each in a kit, so a kit is over Joey's $5 line).
- **Check the depth of the RS03's plain holes** with a probe first; they must take about 8 mm of pin.

| Torque | Load per pin | Bearing on the Ø4 × 8 printed wall | Bulk SF |
|---|---|---|---|
| Rated 20 N·m | 439 N | 13.7 MPa | 3.3 |
| Stall 60 N·m | 1316 N | 41 MPa | 1.09 |

- The stall case is the same open question as the roll stops (Joey's call).
- **Backlash:** a shank of 3.98 or more in a reamed 4.00 gives ≤ 0.02 mm radial, about **0.08°**.
- The six screws stay in clearance holes at 0.3 N·m (hook-scale method, A_HUB_LUGS.md). No threadlocker in testing.
- **Model:** add three Ø3.8 holes at 0° and ±120° on r 15.2 through the fork front boss. This is queued for the next
  SolidWorks gap, with the hub's two Ø3.8 locating holes.

