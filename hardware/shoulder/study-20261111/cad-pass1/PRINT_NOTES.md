# Shoulder print package: notes for assembly (2026-11-12)

Collected from the checks. Each item names the check it comes from.

## Coupons first

- **6808 housing seat ring** (D_6808_FITS.md): a thin ring with the fork rear's Ø52.2 bore, about 3 mm wall, 7 mm deep,
  printed upright like the fork rear. Adjust Ø52.2 to a hand-push fit.
- The cap's Ø40.0 stub needs no coupon; the arm thread's coupon already proved Ø40.0.

## Ream steps (holes printed Ø3.8, hand-reamed Ø4.00 with a 4 mm H7 hand reamer or a sharp 4.0 drill turned by hand)

| Part | Holes | Takes |
|---|---|---|
| Hub (top, RS02 side) | 2, at -142° and 38° on r 12 | the plain shank of M4 × 30 partially threaded screws (locating) |
| Fork front (RS03 boss) | 3, at 0° and ±120° on r 15.2 | Ø4 × 16 pins into the RS03's three plain locating holes |

Pick screws and pins with a shank of 3.98 or more (calipers). That holds backlash to about 0.1° or less.

## Screws

| Joint | Screws | Notes |
|---|---|---|
| Hub → RS02 output | 6 × M4: 2 × ISO 4762 M4 × 30 partially threaded in the reamed holes, 4 × M4 × 30 in the Ø4.3 clearance holes | 0.3 N·m. Probe the RS02's tapped depth first (about 8 mm of thread engages) |
| Fork front → RS03 output | 6 × M4 (existing counterbores) + 3 × Ø4 × 16 pins | 0.3 N·m. Pins can be cut from M4 × 30 screw shanks; probe the RS03's plain-hole depth (about 8 mm) |
| Fork rear → fork front (joint) | **6 × ISO 7380 M4 button heads** | Layout N. The outer recesses are only about 3.1 mm deep, so a DIN 912 head would stand proud |

## Torque without a torque screwdriver

- 0.3 N·m: pull the long arm of the hex key with a luggage or kitchen hook scale at a measured lever L from the screw axis:
  F = 0.3 / L. At L = 60 mm that is 5.0 N, about a 0.51 kg reading.
- **No threadlocker in testing.** Re-torque after 24 h and after the first bench session.

## RS02 plug

- One socket per motor (the 173° one). The other socket stays capped.
- The plug pocket is open: see look-options/plug_pocket/README.md. It waits on Joey's measurement of a real XT30(2+2)-F:
  its height above the mated socket, and the lead gauges.
