# Side centre: the sleeve's rear curving in toward the arm (2026-11-12, mock-up)

Joey (02:4xZ, side-view screenshot): *"why is the upper arm so off center?"* and (02:58Z): *"it feels like we could curve
that rear side and make that transition not so abrupt"*.

![sheet](SHEET_side_centre.png)

Rows: side from outboard, side from inboard, back three-quarter, back. Columns: current (front blend 3), mock-up.
Section through the power channel plane: [section_channel.png](section_channel.png). Mock-up parts are in
`cad/_wip/look/sc` (`LOOK=sc SIDE_CENTRE=1`); the real parts are unchanged.

## Measured (fore-aft Z, from the yaw axis at Z 5.99; + front)

| | Bottom edge (Y 315) | Y 322 | Mid height (Y 330) | Y 350 |
|---|---|---|---|---|
| Sleeve now: back / front, centre | -65.7 / +42.9, **-11.4** | -66.4 / +42.8, -11.8 | -66.4 / +42.1, -12.1 | -66.4 / +43.2, -11.6 |
| **Mock-up** | **-54.0 / +42.9, -5.5** | -58.9 / +42.8, -8.0 | -62.5 / +42.1, -10.2 | -66.3 / +43.2, -11.6 |

- **Arm neck** (the arm thread's part): top band at Y 300 is -38.9 / +38.6, centred.
  - Lower down it leans back on its own: centre -2.1 at Y 290, -5.5 at Y 280, -7.5 at Y 270.
- **Hub band** (Y 300-314): ±39.3.
- **Side to side (X)**, the sleeve is centred within 0.1 mm.
- **The bottom edge is level:** Y 314.5 at every yaw angle. It reads as sloped because the back ends in a wide flat ledge
  over a neck that leans back, while the front ends in a 4 mm step.

## Causes

- **Back:**
  - The sleeve's rear swell is r 66.5. It holds the 16 × 6 power channel at Z -54.3…-48.3 with its 2.4 mm wall.
  - The channel drops straight down from the fork rear arm (centre Z -51.3) to Y 316.6, then turns into the yaw exit
    through a square corner.
  - The 10 × 5 signal channel joins the power channel above Y 357, so it does not add depth lower down.
- **Front:** the fb3 wrap is all above Y 354 and does not change the bottom of the sleeve.
- **Below the hub:** the arm's own neck leans back.

## Mock-up

- **Rear swell:** below Y 350 it curves in toward the arm as it goes down, from r 66.5 to r 54.5 at the bottom edge.
  - The curve is vertical at the top, so it runs on from the wall above with no line.
  - At the bottom edge it is about 34° from vertical, so it prints upright without support.
- **Power channel:** it no longer runs straight down to a square corner. Its centreline turns into the yaw exit on a
  **24 mm radius** (`exit_bend`).
  - That is the same as the yaw loop's r 23.8, and the old corner had no radius at all.
  - The flat bundle bends about its 6 mm direction.
- **Unchanged:**
  - the 10 × 5 signal channel
  - the bore (cuff ↔ hub 2 mm)
  - the yaw exit, still hidden behind the skirt
  - the joint-plane split
- **Mass:** fork rear 67.6 g (was 70.4); fork front unchanged.
- **Shell:** the swell only gets smaller, so its shell clearance can only grow.

## What cannot be evened out, and why

- **The joint plane is the limit, not the channel.** The fork rear owns the sleeve behind the split plane at Z -45.9
  (51.9 mm behind the axis), and needs some depth behind it to exist at the bottom edge. At r 54.5 it is 2.6 mm deep there.
- **The channel alone would allow about r 47** at the bottom edge. Its bend comes in to about r 44 at the exit, plus the wall.
- **Getting to r 47** means the lower sleeve (below about Y 340) becomes all fork front, as a closed ring round the RS02,
  with the split stepping up above it. That is not modelled yet, because two things need checking first:
  - the RS02 is fitted into the cuff from below, and its socket bodies reach r 40.5, against the cuff bore's r 39.75
  - the fork rear would then end above the sleeve's bottom edge
- **The front step (4.3 mm) is set by the RS02 body (r 39.25)** inside the cuff, plus the 2 mm skin and the hub gap. It
  cannot come in further.
- With r 54.5 the back step to the arm's top band is about 15.6 mm (was 27). With r 47 it would be about 8 mm.
