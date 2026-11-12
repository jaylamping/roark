# Upper arm R1c delta review: outcome (2026-11-12)

Packet: `PACKET.md`, pinned commit 0d8f841. Reviewers:
- **Opus 5.5**: on holly-pc, a read-only subagent, 16 min of work.
- **Fable**: an independent reviewer, from a clean clone at 8342bf5, arranged by the coordinator.

Both verdicts: print as a fit article only. No 515 N proof load until the joint issues are closed.

**R1c is not released for printing.** Its 3MFs stay in git. An R1d arm revision follows.

| # | Finding | Who | Verified on holly-pc | Decision |
| --- | --- | --- | --- | --- |
| 1 | `hub_r1c.py` put the arm's line-to-line contact faces in the hub, so the arm's load flank was never reported. | Opus | **Confirmed.** 4,724 of 4,809 load-flank nodes went to the hub. Now the bodies are split by node index (arm 0-440,736, hub to 682,466, then bolts; 0 sampled nodes contradict it). Arm load flank at STOP_0 (ridge6c): vm 0.81 peak, 1.36 / 2.11 at 0.5 / 1 mm at θ 144. Opus: 1.08 at θ 215 on a single node. | Accepted. Fixed in `hub_r1c.py`; all figures to be re-reported. |
| 2 | The 0.5 mm average is taken around each region's peak node, not as the worst average anywhere. One node per sphere at the ridge. Signed layer stress cancels in the average. No interlayer shear check. | Fable, Opus | **Confirmed.** HS cases mesh at 1.8-2.0 mm, with a control only on the bore (G90, 1.2) or the stop face (STOP). The ridge is 1-2 elements thick. | Accepted. Worst average over each region, a mesh control of 0.35 mm or less on the ridge, groove and collar foot, a second mesh size, and an interlayer shear criterion. |
| 3 | The axial fit is over-constrained: load flank, end face (Y 302) and floor (Y 296) are all line-to-line, and the crush ribs aren't modelled. A small gap leaves the ridge carrying nothing until the lugs deflect (bolts 770 MPa). The 0.3 mm play limit is untied to any analysis. | Fable, Opus | **Confirmed.** Three nominal axial contacts. The lug holes are r 1.7 against the r 1.5 bolts in the model. | Accepted. One axial datum, the end face on the disc. The floor gets 0.3 clearance. Real crush ribs on the load flank. Gap-sensitivity solves. The play limit follows from those results. |
| 4 | The ridge6 G90 outlier may be the ridge-not-engaged state, i.e. bistable contact. "Each case solved twice" is true of ridge6b, not of the released ridge6c / 6e. | Fable | Plausible. ridge6 and ridge6b differ only in the 45°-side groove round. | Accepted. ridge6 re-run unchanged, and released geometry solved twice. The post-processor now flags lugs over 50 N or bolts over 200 MPa. |
| 5 | The mating hub is our mirror (r 25 fill in the solved model, stepped run-outs), not the real fd0cef8 hub. | Fable | Confirmed. ridge6d (r 23 fill) has solved and is reading back. | Accepted. Real hub STL from fd0cef8 for the closing path and clearances; r 23 in the FEA hub. |
| 6 | Clearances below print capability on supported faces: tip 0.2 at the crown, floor ring 0.06 to the hub's R0.4, droop on the flank. Support reaches within 0.1 mm of the load flank. | Fable, Opus | Plausible. Opus traced the support paths in the sliced G-code. | Accepted. Tip relieved to r 34.8, floor ring dropped (the floor gets clearance instead), support blocker on the load-flank band. |
| 7 | Evidence: points that start inside are lumped together in the close-path check, the checks ran on ridge6 rather than the released halves, HALFK31 ran on the ridge6 master, and the 0.10 fill clearance has no artefact. | Fable, Opus | Confirmed. | Accepted. Every check re-run on the released R1d geometry, with signed overlaps reported separately. |
| 8 | Bench notes: the 515 N proof goes straight in without steps, a keep-clear warning or a post-load split and inspect. No torque for the seam and lug screws. The fin undersides are missing from the cleaning list. The cable could be pinched by the hub. The hub is captive. | Fable, Opus | Confirmed. | Accepted. Rewrite for R1d. |
| 9 | STOP_124 was not run. | Opus | Confirmed. | Accepted. Added for R1d. |
| 10 | Collar foot: 0.3 ledge, re-entrant (stop layer 1.29). Ring ends abrupt. | Opus | Confirmed. | Blend the ledge in R1d. The ring goes. |
| 11 | Stale text: `hub_seat` post() note, `r1c_fins` docstring, groove comment. `ARM_SEAT_RIBS` defaults to 1. | Fable, Opus | Confirmed. | Fix. |
| 12 | R1 findings: #10 (fit faces now include the ridge flanks and fins) and #11 (cable) are affected; #2 is open until STOP_124. | Fable, Opus | Agreed. None is invalidated. | Carried into R1d. |
| - | ridge6d "stopped after meshing" | Opus | **Rejected.** Both solves finished (solver code 0, 1016 s and 1193 s). They were still reading back at review time. | - |
