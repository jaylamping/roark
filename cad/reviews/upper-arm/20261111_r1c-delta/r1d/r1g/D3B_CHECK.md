# Hub D3b candidate against R1g: checks (2026-11-13)

**Source.** Shoulder thread, commit 6b2fd93 on `claude/project-thread-90ef87`, read-only. Copied to
`cad/_wip/shoulder_hub_d3b_6b2fd93/`.

**Method.** All checks are by Y-plane section every 0.1 from Y 286 to 303 (`d3_check.py`), plus the closing path
(`close_path_r1c.py`). The halves are the R1g print halves (`cad/_wip/r1d_r1g_print/exports`). Everything ran under the 6 GB cap.

| # | Check | Result | Files |
| --- | --- | --- | --- |
| 1 | STL SHA-256 | **PASS**: b221df3d4bfcee6289281e568aef33c5625bdb8d5bf88b760e75e2013b3ec80e. The STL is watertight. | - |
| 2a | D3b against rev D (bc16e97) | **PASS**: only the lugs differ, at Y 288-295.6 (98 mm² per section across both lugs, plus the R1.2 / R0.8 roots up to Y 295.6), plus the local square spigot corner (Y 296-298.4, 1-2 mm² per section). Nothing differs above Y 298.7. | `d3b_fit.json`, `d3b_fit.txt` |
| 2b | Lug outer face (X offset 34.4) against our pocket (34.6) | **PASS**: 0.200 radial at Y 288-292. Opens to 0.26-0.49 at Y 292.5-294 (our wall's inner face is outside the pocket line there). | `d3b_fit.json` |
| 2c | Lug Z faces (Z 1.000 / 11.000) against our slots (CZ ± 5.5) | **PASS**: 0.486 front / 0.514 back over Y 288-294.5, which is the plate space. | `d3b_fit.json` |
| 2d | R1.2 Z roots (Y 294.80-296.00) and R0.8 outward root (X offset 34.40-35.20, Y 295.20-296.00) against our root relief (to X offset 35.2), floor (Y 295.75), web and wall | **PASS**: radial 0.69-0.79 at Y 294.5-295.5; Z gaps 0.69-1.71 through the relief. No contact with the webs (they sit outside \|Z - CZ\| 5.5). | `d3b_fit.json` |
| 3 | Square spigot corner (R0.4 removed over θ ± 10.9° at each lug) against our collar | **PASS**: smallest gap 0.022 (+X) / 0.024 (-X), at Y 296.0-297.9. That is the existing bore clearance (spigot r 35.8-35.85 against our bore r 35.9), as before (0.026-0.045). No interference. | `d3b_fit.json` |
| 4 | Closing path, both halves, on the real D3b + the 0.70 ring | **PASS**: final overlap max 0.041 / 0.039, along the line-to-line ridge flank only (Y 297.97-298.53), the same as on bc16e97. The 8 / 7 path hits are all on that flank (Y 297.97-298.54, r 34.84-35.77) at 0.05-0.22 before seated: faceting of the two line-to-line surfaces, the same as against our FEA hub. None at the lugs, pocket, webs or collar. | `close_path_d3b.json`, `close_path_d3b.txt` |
| 4b | Closing path against the four lug plates (0.45, Dia 4.4 hole, main face) | **PASS**: no hits along the path. Seated clearance 0.036 front / 0.064 back with 0.45 plates; a pick of about 0.49 / 0.51 closes it. | `close_path_plates.json`, `close_path_plates.txt` |
| 5 | Groove, R0.3 disc corner, disc face Y 302 | **PASS**: identical to rev D (no section difference above Y 298.7 apart from the square spigot corner's slivers up to Y 298.4). R1g assumes rev D there. | `d3b_fit.json` |

**Flat plate area per lug Z face below Y 294.8** (shoulder thread): -X lug 94.4 / 107.1 mm², +X lug 100.3 / 100.7 mm². Our plate
outline (X offset 18.96-34.2 × Y 288.2-294.6, less the Dia 4.4 hole) is about 98 - 15 = 83 mm² net. It sits inside the flat face
everywhere.
