# Shoulder hub, left, rev E1: packet for the pre-print gate

Pinned commit: 92cf1010d302f7062d9416299afc38c8690a0c99

Not a passed gate. The requirements spec ([shoulder_requirements.md](../../../shoulder/shoulder_requirements.md)) is a draft,
and the gate report is written only by `tools/cad/gate.py` once the spec is agreed.

- **Design reviewed:** the rev E1 candidate export,
  [shoulder_hub_left_revE1_candidate.STL](https://github.com/jaylamping/roark/blob/92cf1010d302f7062d9416299afc38c8690a0c99/cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL)
  (SHA-256 `1392a808ffab59eb052bf44a83f6eb2ebd02b79af58a322f63125824a091a190`). At adoption the same solid becomes
  `exports/shoulder/shoulder_hub_left.STL`, the path the evidence file names.
- **Picture sheet:** [shoulder_hub_left_sheet.png](shoulder_hub_left_sheet.png), eight views including the bed side
  (`cad/scripts/shoulder/part_sheet.py`). The gate looks for it at `prints/shoulder/shoulder_hub_left_sheet.png`.
- **Evidence:** [evidence.json](evidence.json), written by `cad/scripts/shoulder/hub_evidence.py` from the runs in
  `hardware/shoulder/study-20261111/checks/A_HUB_LUGS.md` ("Rev E1 candidate"). All three results are marked not
  converged, with the reason in each note: the hub-top run has no finer mesh, and the lug and elbow-stop runs were made
  on the first rev E1 shape and not repeated on this export.
