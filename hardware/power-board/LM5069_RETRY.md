# U1 fitted with LM5069-2 (auto-retry) instead of LM5069-1 (latch-off)

Analysis only; the schematic still calls for LM5069MMX-1. Why it matters: on 2026-11-10 the LM5069-1 had no authorised
stock anywhere, and the LM5069-2 was in stock at Mouser and LCSC ([SOURCING.md](SOURCING.md)). The two are the same die
and pinout; only what happens after the fault timer runs out differs (LM5069 datasheet SNVS452G, 8.4.3).

## U1's values (schematic/gen/gen.py, block 1)

- R_s 0.5 mΩ: current limit 97–123 A, circuit breaker 160–260 A.
- R_PWR 34 kΩ: power limit 652 W at 54.6 V, 480–810 W with tolerance.
- C_T (TIMER) 4.7 nF C0G.
- C_dv 100 nF on the gate (through a BAV19W, emptied by the MMBTA92 when the gate drops). The gate charges at 10–22 µA,
  so the start ramps at 100–220 V/s.
- FETs: two IPB017N10N5LF in parallel (bank B). Junction to heatsink about 5.2 K/W per FET; the heatsink is about
  1.5 K/W with fan air and 3 K/W without ([THERMAL_OPTION.md](THERMAL_OPTION.md)).
- UVLO from RUN_B (22k / 33k).

## Retry timing with C_T = 4.7 nF

The LM5069-2 restarts on its own. After the fault timer ends, TIMER runs 4 V → 1.25 V seven times: down at 2.5 µA, up at
85 µA. It then falls to 0.3 V, and the gate turns on again.

| | typ | short end (3.75 µA sink, 120 µA source) | long end (1.25 µA, 51 µA) |
| --- | --- | --- | --- |
| Fault time on (4 V × C_T / 85 µA) | 0.22 ms | 0.15 ms | 0.39 ms |
| Off: 7 × (down 2.75 V + up) + the last fall to 0.3 V | 44 ms | 29 ms | 87 ms |
| Gate ramp to about 3 V through C_dv before the FETs conduct again | 19 ms | 14 ms | 30 ms |
| **Retry period** | **about 63 ms** | **about 44 ms** | **about 117 ms** |
| Time in power limit per period | 0.35 % | — | — |

The datasheet's own figure is a 0.5 % fault duty cycle (DC_FAULT), without the C_dv ramp.

## A hard short on the bus at 54.6 V

- **First event:** the breaker trips (160–260 A, the gate is pulled down at 2 mA). The ports open first on a limb short;
  U1 trips only on a short upstream of them.
- **Every retry after that:** the gate rises slowly through C_dv. With V_DS at 54.6 V, the power limit holds the FETs
  at 480–810 W, which is 8.8–14.8 A, until the timer runs out. The current never reaches the breaker on a retry.
- **Energy per retry, in one FET** (two paralleled FETs in linear mode don't share; take all of it in one):
  - typ: 652 W × 0.22 ms = 0.14 J;
  - worst: 810 W × 0.39 ms = 0.32 J.
- **Per-pulse SOA:** 14.8 A at 54.6 V for 0.39 ms is the same pulse the LM5069-1 already sees once. gen.py has about
  20.7 A allowed at 0.39 ms, 70 °C (1.4×). At 0.35–0.9 % duty, Z_th at 0.4 ms is within a few percent of the single-pulse
  value, so the margin holds as long as the case stays near 70 °C.
- **Continuous retries, average power:**
  - typ 0.14 J / 63 ms = 2.3 W;
  - worst 0.32 J / 44 ms = 7.2 W.
- **Temperatures, worst case** (7.2 W into one FET, 40 °C ambient). The tab sits only 0.4 K/W below the junction; the
  rest of the 5.2 K/W is the vias and the gap pad.

  | | Heatsink | Tab | Junction |
  | --- | --- | --- | --- |
  | No fan air (3 K/W, +22 K) | 62 °C | about 96 °C | about 99 °C |
  | Fan air (1.5 K/W, +11 K) | 51 °C | about 85 °C | about 88 °C |

  Both junction figures are under the 125 °C design limit (175 °C absolute).
- **Typical** (2.3 W): tab about 58 °C, junction about 60 °C.
- **SOA at those case temperatures:** the single-pulse SOA scales with (175 °C − T_case) / 150 K.
  - From the 70 °C reading (20.7 A at 0.39 ms), a 96 °C tab leaves about 15.6 A against the 14.8 A pulse: 1.05×.
  - An 85 °C tab leaves about 17.6 A: 1.19×.
  - At the typical 58 °C tab the margin is above the 1.4× of the single event.

So through continuous retries into a hard short the FETs stay inside SOA and thermal limits:
- at typical tolerances, with margin;
- at the worst tolerance corner, only just without fan air (5 %), and 19 % with it.

## Interaction with the E-stop latch and the watchdog

- **E-stop, loop open, watchdog miss:** unchanged. All three drop RUN, and RUN pulls U1's UVLO under 2.5 V. UVLO holds
  the gate off on either version, and the -2 does not retry while UVLO is low. U8 (bank A) opens as before. Nothing in
  the E-stop path relies on U1's fault latch.
- **What does change: a bus fault no longer stays off.** With the -1, a U1 fault (overload past the timer, or a short
  upstream of the ports) leaves bank B off until a person cycles the E-stop and presses reset (gen.py: "LM5069-1
  latches on a fault. Clear: E-stop cycle, then reset."). With the -2, U1 re-energises the bus by itself about every
  63 ms. If the fault is intermittent (a pinched wire, a connector that shorts with movement), the bus comes back when
  it clears, with no human in the loop.
- **The drives on that bus:** RobStride drives come up disabled and move only on an Enable command, so a bus that comes
  back does not by itself move a joint.
- **The software must not treat "VBUS collapsed" as "latched off until reset".** A software latch would put software in
  a path the hardware handles today.
- **Port breakers and the 12 V buck feed (U7, already an LM5069-2):** unaffected.

## Conclusion

**Safe as a temporary fit, with the heatsink fan running.** The E-stop, the loop and the watchdog still turn bank B off
through UVLO, and nothing in the safety path relies on U1's latch. The FETs stay inside SOA and thermal limits through
continuous retries into a hard short: comfortably at typical values, by 19 % at the worst tolerance corner with fan air,
and by only 5 % without it.

No value change makes the -2 behave like the -1:
- A larger C_T lengthens the off time, but also the fault time and the energy per pulse (SOA gets worse).
- A lower power limit would cut the pulse energy, but R_PWR already sits 6 mV over the LM5069's 5 mV power-limit floor,
  so it can't go much lower and stay accurate.

For the finished robot, fit the LM5069-1 when it is back in stock (Mouser: 583 due 24-May-2027). While the -2 is in:
- a U1 fault retries about every 63 ms until the E-stop is pressed, so press it on any bus fault;
- don't run the bus with the fan off.
