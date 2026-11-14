# Superseded upper-arm print files (do not print)

Not released. Files here that are NOT current for the R1g6 / R1h hub-end set (2026-11-14):

| File | Status | Use instead |
| --- | --- | --- |
| `upper_arm_organic_lug_plates_{A,B}_r1g.3mf / .gcode` | **Removed** from this folder (renamed). Older commits hold versions with a Dia 3.8 plate hole (0b75a69 and before); never print those. | `upper_arm_organic_lug_plates_{A,B}_r1h_d34.3mf / .gcode`: Dia 3.4 hole, 0.9 strip (68c5356 content). A plate whose hole takes a Dia 3.8 drill shank is the old file (BENCH_TESTS 2b step 2). |
| `upper_arm_organic_back_r1g.3mf / .gcode` | **Superseded** by the R1h back half (the harness tie bridge). | `upper_arm_organic_back_r1h.3mf / .gcode` |
| `upper_arm_organic_back.*`, `upper_arm_organic_front.*`, `*_r1c.*` | **Superseded** (R1, R1c). | the R1h back and R1g front halves |

Current hub-end set (with the shoulder thread's hub):
- the back half `..._back_r1h` and the front half `..._front_r1g`;
- the hub-end coupon `..._{back,front}_r1g_coupon`;
- the shim rings `..._shim_rings_{A,B,C}_r1g`;
- the lug plates `..._lug_plates_{A,B}_r1h_d34`;
- the yaw lever `..._coupon_yaw_lever`.
