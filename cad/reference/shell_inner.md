# Body shell chest, inner surface (reference)

`shell_inner.step` is the inside face of the Rev B chest shell, in **torso frame coordinates** (the same frame as
[torso_frame.step](torso_frame.md): X lateral with +X the robot's left, Y up, Z forward). It is built by
[shell_inner.py](../scripts/shell/shell_inner.py) from the `shell_section_*.csv` files. Those are the outer-surface section
curves of the eight chest panels, copied from marengo `hardware/designs/body-shell/manufacturing/sections/` at
`77bbf495f4d350fad37cab98914421d57dc7eb99`. Use it for clearance checks. It is not native CAD.

The model has two lofted surfaces, both closed round the torso:

| Surface | Frame Y |
|---|---|
| lower | 149 to 315 |
| upper | 315 to 543 |

## Coordinate mapping

The CSVs are in the robot frame: x forward, y left, z up from the floor. The torso frame is:

- X = y
- Y = z - 810
- Z = x

The 810 comes from the shell generator (`scene.js`). The pelvis bottom is 740 from the floor and the waist extension is 70.
The frame occupies 155 to 495 above the pelvis bottom, and the frame widening FW defaults to 38, which is this frame.
`frame_clearance.py` places the frame boxes with the same constants.

**Confidence:** high for the constants. The mapping was not checked against a measured shell, because no shell is printed
yet beyond the fit kit.

## Simplifications

- **Inner surface.** Each constant-height outer section is offset 2.4 mm inward (the wall) in its own plane, and the
  sections are then lofted. This is close to a true normal offset where the wall is near vertical, and slightly off where
  it slopes.
- **Panels joined.** The four panels at each height are merged into one closed ring. Seams, flanges, hardpoints and mounts
  are not modelled.
- **No openings.** The shoulder collar opening (r 60 round the pitch axis) is not cut, so the surface runs straight across
  it.
- **Fewer upper sections.** Every second upper section is used: 41 of 80.
