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

## The outer race must carry radial load with no play (2026-11-15)

Found with the bearing's outer race as a body in the fork model (`fea_shoulder.py` R6_* cases, `fork_r6_post.py`; a stiff
ring r 23 to 26.0 or 26.1 in the housing, its bore held radially, no-penetration contact, boss fixed, direct sparse, no
RS02 in the model). Fork nodes only; nothing left out but the 4 mm at the fixed boss face. Released fork; the candidate
with the revised RS02 seats behaves the same.

| Roll stop at 17 N·m, worst 0.5 / 1 mm ball | Bearing seat | Rest of the fork |
|---|---|---|
| Race r 26.1: no radial clearance | von Mises 2.56 / 3.29, layer 2.47 / 3.46, shear 1.76 / 2.36 | 1.61 / 2.42, 1.72 / 1.97, 1.43 / 2.09 |
| Race r 26.0: 0.1 mm radial clearance (as drawn: Ø52.2 for a Ø52 bearing) | 3.05 / 3.87, 3.37 / 4.42, 2.23 / 2.84 | **0.35 / 0.64, 0.32 / 0.57, 0.28 / 0.53** |

| Forward design load | Bearing seat | Rest of the fork |
|---|---|---|
| No radial clearance | 11 or more | 2.21 / 3.45, 1.57 / 2.20, 1.59 / 2.38 |
| 0.1 mm radial clearance | the race is not touched | 0.83 / 1.11, 0.94 / 0.94, 0.55 / 0.71 |

- **The seat and its lip are not the weak place:** with the race carrying load they read 1.76 or better on the 0.5 mm
  ball. The low of 1.45 in the audit of 2026-11-15 was the fixture on the PETG face.
- **With play the bearing does nothing until the fork has bent by the play.** Under the design load it never comes to
  bear, and the boss on the RS03 carries everything. At the stop the tooth's force goes round through the collar and the
  front cheek to the boss before the race takes any: the lows are in the collar round the RS02 (Y 354 to 361) and at
  the boss's root (r 26.5 from the roll axis, Z 39).
- **Pessimistic in one known way:** no RS02 in these models; its bolted housing stiffens the collar. A model with both
  stand-ins is to follow, for the record.
- Every fork figure on record before this was made with the seat held radially, which is the no-clearance case.

**Decision (coordinator, 2026-11-15), for the fork rear's next revision:**
- The outer race is a **snug fit: a hand push, with no radial play.** Housing nominal **Ø52.0** (`BRG_SEAT_R` 26.0), flat-topped
  teardrop kept; the final size comes from the seat-ring coupon, printed upright like the fork rear, **before the fork
  rear prints**.
- **Axial float** stays: the lip stands 0.4 mm behind the bearing, and a hand-push outer race still slides. The inner
  race on the stub (Ø40.0) is the fixed one.
- **At assembly, Joey checks:** with the bearing pushed into the fork rear by hand, the race must not rock or rattle in
  the seat. If it does, that fork rear is not for a loaded arm: shim the seat (one turn of 0.05 mm tape) or reprint from
  the coupon's size.

### Both stand-ins in one model (2026-11-15): the motor does not rescue a loose seat

`R26_*` cases: the RS02 bolted in (aluminium stand-in, five M3 at 250 N, steel washers as bodies) and the 6808's race with
or without its 0.1 mm radial clearance, in the same model. Fork body only, by body, nothing left out
(`fork_r2_body_post.py`); 222k nodes, about 4 minutes a solve. Candidate fork (sf5) unless said.

| Case | Race | Lowest at the five screws: layer tension / shear / von Mises (0.5 mm ball) | Rest of the fork |
|---|---|---|---|
| Roll stop at 17 N·m | no clearance | 3.24 / 1.91 / 2.90 | 1.71 / 1.62 / 2.32 |
| Roll stop at 17 N·m | 0.1 mm clearance | **0.47 / 0.43 / 0.61** (104° and −16° screws) | 0.47 / 0.38 / 0.57 |
| Roll stop at 17 N·m, released fork | 0.1 mm clearance | 0.40 / 0.40 / 0.57 | 0.48 / 0.36 / 0.56 |
| Forward design load, yaw +17 | no clearance | 1.20 / 1.12 / 1.87 (104°) | 1.77 / 2.04 / 2.58 |
| Forward design load, yaw +17 | 0.1 mm clearance | **0.98 / 0.70 / 1.21** (104°) | 0.99 / 0.51 / 0.77 |

- With no clearance the figures are those of the candidate's record. With 0.1 mm the fork is under 1.0 at the stop
  whether or not the motor is in the model, and the motor's own screw seats are dragged down with it.
- So the decision above stands on its own: **the bearing's outer race must sit without play**, and a fork rear whose
  race rocks is not for a loaded arm.
