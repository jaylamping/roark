LEFT ARM V1 MASTER LAYOUT - draft skeleton, 2026-11-05. No print/load/motion release.
Open LEFT_ARM_LAYOUT.SLDASM. All components fixed, no mates. STEP coordinates: mm, Y up, X lateral.
Left arm is on +X (node 39), the counterpart of the right arm on -X.
Shoulder (P1 L01, roll RS03, spacer, P2 L04B, yaw RS02) uses the existing left source-to-STEP transform unchanged.
Draft, not derived: elbow axis parallel to X, elbow RS02 output +X, RS00 output toward wrist, origin 134.2 mm below elbow
(exported arm offset 94.2 plus RS00_OFFSET 40), links 215/195/90 measured along the yaw axis from Y 424.86.
Torso is simplified: no Pi, compute shelf or layout block.
P1/P2 are imported STEP bodies with no feature tree. Rebuild scripts are in scripts/.
Numbers: mass_torque.json, component_boxes_mm.json. Inputs and sources: inputs/INPUT_MANIFEST.json.
