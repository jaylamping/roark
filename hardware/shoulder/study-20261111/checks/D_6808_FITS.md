# Check (d): 6808 seat fits (2026-11-12)

**The bearing:** 6808-2RS, 40 × 52 × 7, floating at the rear of the roll joint.
- Inner race on the cap's printed stub.
- Outer race in the fork rear's printed housing.
- The RS03 output bearing locates the joint axially; the 6808 only takes radial load.

**Geometry** (`dims`, `build_cap` `STUB`, `build_fork_rear` `SEAT`):

| Feature | Model | Prints as |
|---|---|---|
| Stub (inner race) | Ø40.0, Z -40.3…-47.3 (7.0 long, the bearing width), hollow Ø25 | the cap prints front face down: the stub's axis is vertical, so its section is round |
| Inner-race land | Ø45.0 (r 22.5) at Z -40.3 | flat, upward-facing |
| Housing (outer race) | Ø52.0, from Z -40.8 to -47.3 (6.5); material from Z -41.8, so the race sits in it for 5.5 mm | the fork rear prints upright: the bore's axis is horizontal, so it prints as a round hole on its side, with the usual undersize and a flattened top |
| Outer-race lip | Ø48.0 at Z -47.3, back to Z -51.3 | |

## Findings

1. **Inner-race land too large.**
   - The land is Ø45 against the bearing's front face. The 6808 inner ring's shoulder is about Ø43.4-43.6
     (the catalogue d1).
   - So the outer 0.7-0.8 mm of the land faces the rubber seal. Seals are recessed about 0.2-0.3 mm, so it probably
     doesn't rub, but it is marginal.
   - **Change:** land Ø43.0 (r 21.5). The catalogue's shaft shoulder range is about Ø42-43.3.
2. **Axial stack: zero gap at the lip.**
   - The lip face is at Z -47.3, exactly at the bearing's rear face. The inner race is held forward by the land at Z -40.3.
   - The loop RS03 output → fork → lip → 6808 → stub → cap → drum → RS03 housing is closed. A negative print tolerance
     anywhere in it preloads the 6808 and the RS03 output bearing axially, through printed parts.
   - **Change:** move the lip back 0.4 mm (lip face and seat end at Z -47.7). The outer race then really floats.
3. **Outer-race fit.**
   - A floating outer race wants a light clearance: about +0.02…+0.05 mm on Ø52.
   - Horizontal printed holes come out about 0.1-0.2 mm under, and oval.
   - **Change:** model the housing at Ø52.2, and add a teardrop or flat (0.4 mm) at the top so the overhang prints
     without support.
   - **For the print package:** a thin seat-ring coupon (the housing's bore with about 3 mm of wall, 7 mm deep, printed
     upright like the fork rear). The orientation is new, so this one is worth a coupon. Adjust Ø52.2 to a hand-push fit
     from it.
4. **Inner-race fit.**
   - Vertical printed shafts come out about +0.05…+0.15 mm. That is a press fit on the 6808's Ø40 (0/-0.012) bore.
   - The hollow stub (7.5 mm wall) takes that as hoop compression, which is fine for PETG at this size.
   - **Decision (2026-11-12):** keep the stub at **Ø40.0**. The arm thread test-printed a Ø40.0 PETG stub coupon for the
     6808 on this printer and it fits perfectly; the arm keeps Ø40.0 on that evidence. Add only a 0.5 × 45° lead-in at
     the free end (Z -47.3).
   - Retention is the press fit plus the land. That is enough: the 6808 sees radial load only, and the outer race floats.
5. **Load:**
   - Radial load on the 6808 is a fraction of the joint's radial load (check (c)): tens of newtons in normal use.
   - Contact pressure on the printed seats is under 1 MPa.
   - The 6808 rating (C0 about 3 kN) is far above it.

## Summary of changes for the next cap / fork-rear revision

| Part | Feature | Now | Change |
|---|---|---|---|
| Rear cap | Inner-race land | Ø45.0 | **Ø43.0** |
| Rear cap | Stub | Ø40.0, square end | Ø40.0 kept (the arm's coupon fits), **0.5 × 45° lead-in** |
| Fork rear | Housing | Ø52.0 | **Ø52.2**, flat-topped teardrop (0.4 above the bore); seat-ring coupon in the print package |
| Fork rear | Lip | face at Z -47.3 (0 gap) | **Z -47.7** (0.4 axial float) |

**Status (2026-11-12):**
- Approved and in the build scripts: `dims.LAND_R` 21.5, `BRG_SEAT_R` 26.1, `BRG_LIP_Z` -47.7 and `STUB_LEAD` 0.5, plus
  `SEAT_TEARDROP` in `build_fork_rear`.
- The cap and fork rear SLDPRTs are **not rebuilt yet**. SolidWorks launches on holly-pc are on hold until the stuck
  instance is cleared.
