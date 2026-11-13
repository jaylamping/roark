Meshes (element size mm: global / seats and ring outside / screw shanks), all second-order, direct sparse solver:

| Mesh | Sizes | Nodes | Reaction +Y case N | Reaction +X case N | Solve + readback s |
| --- | --- | --- | --- | --- | --- |
| c | 3.5 / 1.4 / 1.0 | 73,496 | -299.87 on the face, -0.124 on the plug | -299.85 on the face, -0.150 on the plug | 54, 64 |
| m | 2.5 / 1.0 / 0.7 | 145,831 | -299.87 on the face, -0.124 on the plug | -299.85 on the face, -0.150 on the plug | 148, 170 |
| f | 2.1 / 0.85 / 1.2 | 164,616 | -299.88 on the face, -0.124 on the plug | -299.85 on the face, -0.149 on the plug | 189, 234 |

Screw loads from the study (mid shank, a plane fitted to the stress over the section, times the area), N:

| Mesh | Case | X 31 Z 0 | X 31 Z 7 | X -31 Z 0 | X -31 Z 7 | Sum | Hand |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c | +Y tension | 74.7 | 74.5 | 74.8 | 74.5 | 298.5 | 75.0 each, 300 in all |
| c | +X tension | 18.9 | 18.6 | 15.8 | 16.4 | 69.8 | 24 each first guess; 75.7 in all from the contact angles |
| c | +X shear along X | -2.2 | -2.2 | 15.1 | 15.3 | 26.1 | 37.5 each first guess; 17.5 in all from the contact angles |
| m | +Y tension | 74.8 | 74.4 | 74.9 | 74.2 | 298.3 | 75.0 each, 300 in all |
| m | +X tension | 18.9 | 18.9 | 14.2 | 15.3 | 67.4 | 24 each first guess; 75.7 in all from the contact angles |
| m | +X shear along X | -2.2 | -2.2 | 15.5 | 15.4 | 26.4 | 37.5 each first guess; 17.5 in all from the contact angles |
| f | +Y tension | 75.0 | 74.3 | 74.9 | 74.4 | 298.6 | 75.0 each, 300 in all |
| f | +X tension | 19.1 | 19.0 | 15.7 | 17.4 | 71.2 | 24 each first guess; 75.7 in all from the contact angles |
| f | +X shear along X | -2.2 | -2.2 | 15.2 | 15.1 | 25.8 | 37.5 each first guess; 17.5 in all from the contact angles |

Factors on mesh f, for each way the layers could be stacked (value MPa, factor, where). Excluded: plastic within 1 mm of a bonded steel face (under the screw heads, round the insert ends) and within 3 mm of the fixed face; their largest values are in the last column.

| Case | Half | Layers along | von Mises / 45 | Tension across layers / 22.5 | Shear between layers / 13 | Largest excluded von Mises (steel bond, fixed face) |
| --- | --- | --- | --- | --- | --- | --- |
| +Y | upper | Z | 3.87, **11.6**, (28.66, 27.5, 6.81) | 0.65, **34.8**, (-20.67, 15.35, 7.1) | 1.36, **9.6**, (-20.5, 16.64, 0.02) | 4.37, no fixed face in this half |
| +Y | upper | Y | 3.87, **11.6**, (28.66, 27.5, 6.81) | 1.36, **16.6**, (-28.13, 30.25, 7.87) | 1.36, **9.6**, (27.15, 28.93, -0.16) | 4.37, no fixed face in this half |
| +Y | upper | X | 3.87, **11.6**, (28.66, 27.5, 6.81) | 2.51, **9.0**, (0.0, 32.0, 3.59) | 1.36, **9.6**, (27.15, 28.93, -0.16) | 4.37, no fixed face in this half |
| +Y | lower | Z | 3.48, **12.9**, (29.34, -7.6, 5.89) | 1.08, **20.9**, (-32.95, -7.57, 7.42) | 0.65, **20.0**, (29.84, -7.74, 1.63) | 4.11, 1.7 |
| +Y | lower | Y | 3.48, **12.9**, (29.34, -7.6, 5.89) | 3.95, **5.7**, (29.84, -7.74, 1.63) | 0.75, **17.2**, (28.24, -4.77, 8.22) | 4.11, 1.7 |
| +Y | lower | X | 3.48, **12.9**, (29.34, -7.6, 5.89) | 1.03, **21.9**, (-29.34, -0.4, -2.7) | 0.76, **17.2**, (-32.96, -7.6, -0.39) | 4.11, 1.7 |
| +X | upper | Z | 5.44, **8.3**, (-28.58, 27.3, -0.2) | 1.25, **18.1**, (-33.34, 27.5, 6.81) | 1.29, **10.1**, (-28.78, 27.38, 5.37) | 6.23, no fixed face in this half |
| +X | upper | Y | 5.44, **8.3**, (-28.58, 27.3, -0.2) | 4.52, **5.0**, (-33.34, 27.5, 6.81) | 2.65, **4.9**, (-32.2, 27.48, -1.21) | 6.23, no fixed face in this half |
| +X | upper | X | 5.44, **8.3**, (-28.58, 27.3, -0.2) | 1.29, **17.4**, (4.76, 32.0, 8.25) | 2.66, **4.9**, (-32.2, 27.48, -1.21) | 6.23, no fixed face in this half |
| +X | lower | Z | 5.93, **7.6**, (19.6, -14.7, 7.1) | 1.26, **17.8**, (29.04, -7.6, -0.39) | 2.22, **5.8**, (24.59, -9.75, -0.07) | 4.16, 6.36 |
| +X | lower | Y | 5.93, **7.6**, (19.6, -14.7, 7.1) | 4.19, **5.4**, (-32.95, -7.57, 7.42) | 2.89, **4.5**, (18.7, -15.83, -0.1) | 4.16, 6.36 |
| +X | lower | X | 5.93, **7.6**, (19.6, -14.7, 7.1) | 3.67, **6.1**, (23.63, -10.23, -0.1) | 2.89, **4.5**, (18.7, -15.83, -0.1) | 4.16, 6.36 |

Lowest factor over both load cases, per half and print direction:

| Half | Layers along | Yield | Across layers | Between layers |
| --- | --- | --- | --- | --- |
| upper | Z | 8.3 (+X) | 18.1 (+X) | 9.6 (+Y) |
| upper | Y | 8.3 (+X) | 5.0 (+X) | 4.9 (+X) |
| upper | X | 8.3 (+X) | 9.0 (+Y) | 4.9 (+X) |
| lower | Z | 7.6 (+X) | 17.8 (+X) | 5.8 (+X) |
| lower | Y | 7.6 (+X) | 5.4 (+X) | 4.5 (+X) |
| lower | X | 7.6 (+X) | 6.1 (+X) | 4.5 (+X) |

Convergence, layers along Z. The place of each peak on the finest mesh is followed through all meshes: the largest value within 1.5 mm of it, and the mean within 2 mm (with node count). Last step is between the two finest meshes.

| Case, half, measure | Where | Peak c | Peak m | Peak f | Last step | 2 mm mean c | 2 mm mean m | 2 mm mean f | Converged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +Y upper vm | (28.66, 27.5, 6.81) | 3.55 | 4.07 | 3.87 | 5 % | 2.53 (59) | 2.53 (58) | 2.45 (58) | peak yes, mean yes |
| +Y upper layer | (-20.67, 15.35, 7.1) | 0.27 | 0.25 | 0.65 | 160 % | -0.50 (66) | -0.58 (146) | -0.59 (227) | peak NO, mean yes |
| +Y upper shear | (-20.5, 16.64, 0.02) | 0.89 | 1.31 | 1.36 | 4 % | 0.33 (84) | 0.34 (190) | 0.32 (304) | peak yes, mean yes |
| +Y lower vm | (29.34, -7.6, 5.89) | 3.41 | 3.29 | 3.48 | 6 % | 1.46 (41) | 1.42 (52) | 1.36 (64) | peak NO, mean yes |
| +Y lower layer | (-32.95, -7.57, 7.42) | 1.03 | 1.06 | 1.08 | 2 % | 0.10 (25) | 0.03 (33) | 0.04 (34) | peak yes, mean yes |
| +Y lower shear | (29.84, -7.74, 1.63) | 0.79 | 0.75 | 0.65 | 13 % | 0.16 (48) | 0.15 (53) | 0.16 (61) | peak NO, mean yes |
| +X upper vm | (-28.58, 27.3, -0.2) | 4.97 | 5.30 | 5.44 | 3 % | 2.93 (57) | 2.90 (70) | 2.95 (57) | peak yes, mean yes |
| +X upper layer | (-33.34, 27.5, 6.81) | 1.22 | 1.20 | 1.25 | 4 % | 0.21 (40) | 0.23 (55) | 0.18 (48) | peak yes, mean yes |
| +X upper shear | (-28.78, 27.38, 5.37) | 1.06 | 1.18 | 1.29 | 9 % | 0.49 (69) | 0.49 (80) | 0.51 (70) | peak NO, mean yes |
| +X lower vm | (19.6, -14.7, 7.1) | 5.87 | 5.93 | 5.93 | 0 % | 5.07 (24) | 4.94 (50) | 4.82 (84) | peak yes, mean yes |
| +X lower layer | (29.04, -7.6, -0.39) | 1.34 | 1.06 | 1.26 | 19 % | -0.18 (34) | -0.17 (43) | -0.13 (51) | peak NO, mean yes |
| +X lower shear | (24.59, -9.75, -0.07) | 1.75 | 2.15 | 2.22 | 3 % | 0.57 (91) | 0.56 (171) | 0.56 (239) | peak yes, mean yes |

Support a second way: only the walls of the two M4 insert holes held (mesh sizes as m), layers along Z:

| Case | Half | von Mises | Tension across layers | Shear between layers | Screw tension sum N | Reaction N |
| --- | --- | --- | --- | --- | --- | --- |
| +Y | upper | 3.64, **12.3**, (28.49, 27.49, 6.83) | 0.53, **42.8**, (29.35, 15.08, 6.57) | 1.31, **9.9**, (-20.05, 17.36, 0.02) | 298.6 | [-0.0, -299.87, -0.0] |
| +Y | lower | 4.19, **10.7**, (26.73, -24.91, 2.89) | 1.67, **13.5**, (26.11, -23.2, 4.1) | 1.50, **8.7**, (-25.65, -24.93, 5.76) | 298.6 | [-0.0, -299.87, -0.0] |
| +X | upper | 6.51, **6.9**, (-28.68, 27.45, 7.19) | 1.30, **17.3**, (-33.34, 27.5, 6.81) | 1.46, **8.9**, (-28.5, 27.5, 8.54) | 99.2 | [-299.827, 0.089, -0.0] |
| +X | lower | 11.86, **3.8**, (26.73, -24.91, 2.89) | 5.41, **4.2**, (26.73, -24.91, 2.89) | 4.75, **2.7**, (23.34, -24.93, 6.22) | 99.2 | [-299.827, 0.089, -0.0] |
