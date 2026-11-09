# Upper-arm clamshell, draft 3: gate results

Pinned commit: 492db8beb2c64a8b87c844e9d95bae77f773d765

Parts: [front half](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/upper_arm_shell_front_left.SLDPRT), [back half](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/upper_arm_shell_back_left.SLDPRT),
[elbow ring](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/upper_arm_elbow_ring_left.SLDPRT), [hub](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/upper_arm_hub_left.SLDPRT),
[loop clip](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/upper_arm_loop_clip_left.SLDPRT). Design notes: [cad/upper-arm/README.md](https://github.com/jaylamping/roark/blob/492db8beb2c64a8b87c844e9d95bae77f773d765/cad/upper-arm/README.md).

- `sheet.png`: the picture sheet (parts, print orientations, visible holes).
- `gate_summary.json`: mesh gate and support-on-visible-face check, rerun on the exports at the pinned commit with
  `cad/scripts/arm/ua_gate_run.py`. All five parts pass the mesh gate. Visible support: none on the upper half, ring and hub
  (the faces it flags are inside the closed arm), 0.4 mm² on the back half, and the clip prints with support off.
- `fea_seam.json`: the FEA results from marengo (`ua_fea.py`, bonded one-body model). The pitch sweep passes. The lateral
  case does not: SF 1.17 bulk and 0.93 layer on the back half at (166.4, 240, ±22.5), the corner where the ring's end
  meets the skirt trim.

Still open: the corner fix and a contact FEA of the ring, the 2 mm post-root fillet, and the two-reviewer gate.
