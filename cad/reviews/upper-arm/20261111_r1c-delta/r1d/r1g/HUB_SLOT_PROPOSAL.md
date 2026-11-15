# Shoulder thread's hub cable slot proposal: our check (2026-11-15)

**The proposal (shoulder thread, quoted by the coordinator):** a dog-leg tunnel, 4.5 mm (radial plane) × 11 mm (tangential), with
corners and mouth edges R 1.5, centred on 68 deg.
- The mouth is in the dish floor at r 27.0-31.5, straight down.
- Then it slants inward (a 40 deg knee 5.5 mm below the floor) and exits through the bore wall (r 23) between Y 302.1 and 309.1.
- It continues in the bore toward Y 298, where the opening lies between r 16.0 and about r 19.6 (centre about r 18).
- Elsewhere: the pocket is filled solid, the six boss tubes go from Dia 8.8 to 10.8, and the centre plate gets 4 mm thicker
  downward. Bare wires are threaded from the dish side, and the tie stays in the bore.

**The bundle:**
- One 18 AWG power pair (OD 2.6 to be safe) and two 28 AWG pairs plus one reserved (1.2 mm per wire, per the 11-11 scheme).
- Laid flat: the power pair side by side plus the six signal wires as two layers of three, **8.8 × 2.6** (power 5.2 + signals
  3.6). This replaces the 8.5 × 2.6 I gave earlier with 1.1 mm signal wire.
- In the 4.5 × 11 tunnel that leaves 0.95 radial and 1.1 tangential per side.

## (a) Our route from the opening, Y 298 down to the rib gap and the tie bridge

- `cable_slack.py` from a centre at r 18.0 (68 deg, R1h halves, the conservative 3.5 × 13 reserve bundle; `cad/_wip/route_r18/`):
  **PASS**.
  - Smallest clearance 5.43 at the hub end (Y 298-284), R 24.1 at each bend, steepest slope 0.66, no twist.
  - The front half's assembly sweep is 0 mm².
- At r 17.45 it was 5.63 / R 24.7. Our earlier entry scan passes every centre r 15-21.5 with 3.6 or more at R ≥ 24.
- **The route itself doesn't need the 1 mm outward shift. The tube does: see (c).**
- **Assumption in our route:** the bundle leaves Y 298 heading along the hub axis (straight down), as today. If it arrives on the
  tunnel's 40 deg inward slant, it has to straighten inside the bore above Y 298 (see (b)).

## (b) Static bends

The bundle bends across its thin direction (2.6) in the tunnel's 4.5 plane, never edgewise.
- **The knee, 40 deg:** the 0.95 per side lets an arc through the corner of R up to about 31. The real limit is the 5.5 mm straight
  run above the knee: R ≤ 5.5 / tan 20° ≈ **15** (5.8 × OD 2.6). That is above the 4-6 × usually used for static silicone wire.
  The R 1.5 corner rounds only help.
- **The bore-wall exit and the turn to straight down by Y 298:** the run from the exit (Y 302.1-309.1) to Y 298 is 4-11 mm, so
  R ≈ 11-30. Make the bore side give at least R 11 (4.2 × OD), i.e. keep the opening's lower edge at Y 298 or above.
- Every bend here is static: the bundle is clamped at the window and tied in the bore.

## (c) What the hub changes reach of ours

- **Nothing of ours is above Y 302.6.** That covers the halves' end face (Y 302), the shim ring (r 36.2-38.4, Y 301.3-302), the
  lug bolts and their heads and tool access (lugs at Y 288-296, bolts along Z, heads on our back posts), the RS02 ring (at the
  elbow), and the M14 splice and fuse holders (neck, Y 255-295).
  - The thicker centre plate (down to about Y 312), the filled pocket and the thicker tubes are all above that.
  - The bundle in the bore runs below Y 309.1, so it stays 2.9 or more under the thicker plate.
- **The Dia 10.8 tube at 98 deg (r 12) against the bundle**, flat 8.8 × 2.6:
  - If the bundle hangs straight at r 17.8 through the tube's Y 300-304, it is 0.54 from a Dia 10.8 tube (1.54 from today's
    Dia 8.8). Their tie band (about 1.5) then has no room.
  - On the tunnel's slant, the bundle is at r 19.7 or more by Y 300, which gives 2.4 or more.
  - **With the offered 1 mm outward shift** (centre r 19), even a straight bundle is 1.7 from the Dia 10.8 tube.
  - **So take the shift, or keep the tube's thickening off the bundle side.**
- The slot opening's own footprint (r 16.0-19.6 × 11) touches a Dia 10.8 tube in plan. That only matters if the tube reaches down
  to Y 298; it starts at Y 300 today.

## (d) Assembly and removal

1. With the hub on the bench, thread the bare trunk wires from the dish side, one or two at a time, through the knee into the bore
   and out at Y 298.
2. Make the M14 splice and fuse holders in our neck, lay the hub in the back half, route up the neck, close the front half: our
   order, unchanged.
- No plug or fuse holder passes the tunnel.
- **Removing the arm** then means unsoldering at M14, unless there is a joint break inside the neck. The trunk spec's optional
  joint break (XT30U pair plus a GH pair), placed between the hub and M14, lets the arm come off by opening the front half and
  unplugging. The neck has room for it (cavity 1438 mm² or more at every 5 mm, Y 250-295).
- **Recommended:** keep that joint break.

## Correction from the shoulder thread, and our re-check (2026-11-15, 05:41Z)

**Correction.** The tunnel ends where it breaks through the bore wall (r 23, Y 302.1-309.1).
- Below that is open bore. The bundle hangs straight down against the bore wall, centre about r 21.5 for our 2.6 flat bundle.
- At Y 298 the free opening runs from the Dia 10.8 tube (r 15.8 on the centre line; the tubes start at Y 298.06) to the bore wall
  at r 23. That is 7.2 radial, centre r 19.4, with about 4 mm between the bundle and the 98 deg tube for the tie.
- No r 19 shift is made, and all six tubes stay thickened. The knee gets R 2 on its inner corner, and the tunnel's long corners
  R 1.5.

**Our route from r 21.5** at θ 68 (`cable_slack.py`, R1h halves, the conservative 3.5 × 13 reserve bundle;
`cad/_wip/route_r21.5/`): **PASS**.
- Smallest clearance 3.64, to the arm wall at Y 278. Fin end 3.66 (Y 273), hub post / web corner 4.09 (Y 292), the waist's front
  wall 4.94 (Y 269).
- R 24.7 at each bend of the S, steepest slope 0.68.
- The front half's assembly sweep is 0 mm².
- Near the top, our seat bore and end face are 11.6-11.8 away at Y 296-298, and 5.6 at Y 295, so it rubs nothing of ours there.
- The tie bridge (Y 255-261) is in the checked halves and clear.
- That compares with 5.43 from r 18. The real 2.6 bundle gains about 0.45 per side over the 3.5 reserve.
- The RS02 ring sits at the elbow, far from this.
- **It does not hurt us.** Requests 1 (the shift) and the tube concern are withdrawn: the bundle hangs at r 21.5, about 4 from the
  98 deg tube.
- Request 2 stands: a joint break in our neck so the arm can be removed without unsoldering.
