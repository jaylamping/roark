# Shoulder hub, left, rev E1: packet for the pre-print gate

Pinned commit: 8656e20953206e64c06298a9ca8514df166d7058

Not a passed gate. The requirements spec ([shoulder_requirements.md](../../../shoulder/shoulder_requirements.md)) is a draft,
and the gate report is written only by `tools/cad/gate.py` once the spec is agreed.

- **Design reviewed:** hub rev E1 as adopted,
  [shoulder_hub_left.STL](https://github.com/jaylamping/roark/blob/8656e20953206e64c06298a9ca8514df166d7058/cad/exports/shoulder/shoulder_hub_left.STL)
  (SHA-256 `638facef4a15a6ed8f9315f58ed556b567e72503f3a60d0bdfcbd1103de0080b`), the path the evidence file names.
- **Picture sheet:** [shoulder_hub_left_sheet.png](shoulder_hub_left_sheet.png), eight views including the bed side
  (`cad/scripts/shoulder/part_sheet.py`). The gate looks for it at `prints/shoulder/shoulder_hub_left_sheet.png`.
- **Evidence:** [evidence.json](evidence.json), written by `cad/scripts/shoulder/hub_evidence.py` from the runs in
  `hardware/shoulder/study-20261111/checks/A_HUB_LUGS.md` ("Rev E1 as adopted"). The hub-top case is recorded as
  converged (two meshes); the lug and elbow-stop cases pass their marks but are recorded as not converged, because they
  were not repeated on a second mesh for this shape.
- **Print file** (not in the repo until the gate passes): `cad/_wip/prints/shoulder/shoulder_hub_left_revE1.3mf`,
  SHA-256 `c384a067f1f3d5a9532ac16758862e919518f8ac2e4b7a91abf1b6615895fc5a`.

## Trial gate run (2026-11-15, holly-pc, in a scratch copy of `cad/`, no report kept)

Made on the first rev E1 candidate (SHA-256 `1392a808…a190`, 63,410 triangles) and its print file, before the seats and
the rounds changed; not repeated on the adopted shape.

`gate.main(['shoulder_hub_left'], cad=<scratch cad>)` with the spec as drafted, the export above as
`exports/shoulder/shoulder_hub_left.STL`, the staged 3MF (SHA-256 `aa4c7dd3…4a81`) and this sheet and evidence file.

| Check | Result |
|---|---|
| Requirements agreed | FAIL: the spec is a draft |
| Export, 3MF and picture sheet present | PASS |
| 3MF settings | PASS: 6 settings match, all flagged or preset |
| Evidence | FAIL on convergence only (all three results recorded as not converged); every figure clears its pass mark |
| Mesh | **did not finish**, see below. `mesh_check.integrity_file` alone: watertight, 0 non-manifold edges, 0 zero-area faces, one body |
| Support on visible faces, interference | not reached; need `hidden_by` and `mates` meshes |

**Memory failure in the mesh check, for the tool's owner.** `tools/cad/mesh_check.py`, `thickness()` (the ray step:
`RayMeshIntersector(m).intersects_location(c[s:s + 3000], -n[s:s + 3000], multiple_hits=False)`), called from `check()`
by `gate.mesh_checks`. Export: 63,410 triangles, 3,170,584 bytes. Python 3.12 venv with numpy, scipy, trimesh, rtree and
networkx; no embree. The process was run under a memory cap (`cad/scripts/shoulder/capped.py --mb N`):

- cap 6144 MB: `numpy._core._exceptions._ArrayMemoryError: Unable to allocate 92.4 MiB for an array with shape (12112414,)`
  in `trimesh/triangles.py` `points_to_barycentric`, peak 6124 MB;
- cap 14336 MB: the same error, `Unable to allocate 231. MiB for an array with shape (30245707,)`, peak 14128 MB.

So one chunk of 3000 rays reaches 12 to 30 million ray and triangle candidate pairs on this part. `mesh_check.py` was not changed.
