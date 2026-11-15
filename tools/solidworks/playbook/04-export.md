# 4. Exports, promotion and committing CAD

The rules are [cad.md](../../../conventions/cad.md). This page is the order of operations and the traps.

## Exporting

```python
export(j.sw, d, r"J:\code\roark-wt\<session>\cad\exports\<region>\<part>.step")
export(j.sw, d, r"J:\code\roark-wt\<session>\cad\exports\<region>\<part>.stl")
```

`export()` sets the options for the export and puts back what the machine had, because they are per-user SolidWorks settings (written to the registry when SolidWorks closes, so a script that left them set would change the PC for everyone) and holly-pc's defaults differ from
Joey-PC's ([cad.md section 9](../../../conventions/cad.md#9-cad-workstation)): binary STL in mm, quality Fine, **kept in the
model frame**, STEP AP203.

Then check the file, not the return value:

| Check | How | Why |
| --- | --- | --- |
| STL is watertight, one body | `trimesh.load(path).is_watertight`, `len(mesh.split())` | an export of a part with a crumb body has two shells |
| STL volume equals the part's | `mesh.volume` against `volume(d)`, within 0.5 % | catches metres-for-millimetres and a wrong configuration |
| STL sits in the model frame | `mesh.bounds` against `bbox(d)`, within 0.1 mm (facets on a round part fall up to 0.08 mm inside the true box; on a lofted part `bbox(d)` is the box of the control points and can be millimetres larger than the solid, so compare against the sections you drew) | with toggle 71 off, SolidWorks shifts the STL to positive space and everything that reads it by coordinate is wrong |
| STEP is in mm | open the file and find the length unit: SolidWorks writes `SI_UNIT ( .MILLI., .METRE. )` with spaces, so search for `.MILLI.` on an `SI_UNIT` line, not the exact string | a part from an inch template exports in inches |

Record the export right after making it, from the worktree root:
`python tools/cad/record_export.py exports/<region>/<file> <region>/<part>.SLDPRT --config Default --settings "STEP AP203"`.

## From scratch to the design of record

1. Work in `cad/_wip/<topic>/` (gitignored). Simulation output goes in `cad/_sim/<region>/`.
2. A part is **promoted** into its region folder when it is chosen. Name it by
   [cad.md section 4](../../../conventions/cad.md#4-names): `<region>_<part>[_left|_right].SLDPRT`, lower case, no version
   suffix.
3. A part with no references (built by a script, standing alone) may be written straight to its region folder by the script.
   A file that other files reference is moved **inside SolidWorks** (Pack and Go), never with a file move. Pack and Go has
   not been scripted here: do it by script only after proving it on copies, or hand it up.
4. Before committing: take the writer lock, then

   ```bash
   python tools/cad/check_cad_layout.py          # the folder on disk
   python tools/cad/check_sw_refs.py --all       # every reference resolves to a staged or committed file
   python tools/check_file_sizes.py --staged
   ```

5. Commit at a gate, not on every save; one overwrite per part. Push to your branch and open a PR.

## Never

- Commit anything from `_wip/`, `_sim/`, `_archive/`, or a `.CWR`, `.STE`, `~$` or `Backup of` file.
- Add a `_v2`, `_revC`, `_final` or `(2)` copy to a region, export, print or drawing folder.
- Add a CAD file on a machine where `git lfs install` has not been run.
- Push over the LFS budget, or with `--no-verify`.

## Printing

Before a part is called printable, ask the STL: `python tools/solidworks/sheet.py part.stl --printable +y` (the direction that
points away from the bed; `sheet.printability(tris, up)` from a script). It answers with numbers: whether it fits the
256 mm bed, whether it is one watertight piece, the area lying on the bed, and the area that faces down more steeply
than 45 degrees and so needs support, with where the largest patch is. Quote those in the report in place of "prints
fine". `ok` means it fits, is one closed piece and touches the bed: it does not mean no supports, and it says nothing
about wall thickness or bridges.

**Choosing the print direction.** Strength across the layers is one of three things to weigh, not the only one. For
every direction you consider, put these side by side in one table before picking:

| What | From | Rule |
|---|---|---|
| Height | `height_mm`, `fits_bed` | Must fit the printer (256 mm cube) with a few mm to spare. A part within about 10 mm of the limit gets a brim, not a raft, and no tilt that raises it. |
| Support on faces that show | `overhang_mm2`, `worst_overhang_at` | Supported faces come off rough and are not sanded. Least support on outward faces wins; support that cannot be avoided goes on a mounting face or inside a fork or bore. |
| Strength | the factor for layers stacked along that direction ([05-fea.md](05-fea.md)) | Must reach the required factor. |

When the direction with the clean faces is short on strength, add material there (a thicker stem, a larger blend) and
solve again, before turning the part to a stronger direction that needs a raft and support under the whole form. A
direction that passes strength with thousands of mm2 of support under a visible face is not a pass: say so and give
the table. Upright (the long axis vertical) is usually the clean one, and is also the one that runs into the height
limit, so check both for it first.

To check a part against a reference (an earlier revision, a supplier's model, a scan), both in the same frame:
`python tools/solidworks/sheet.py part.stl ref.stl --diff` gives the volume and box differences and the largest gap between
the two surfaces, with where it is. A gap under about twice the `resolution_mm` it prints is no finding.
A print project is built from the STL export, not from SolidWorks: orientation, the 100 % infill modifiers, supports and
the Bambu Studio command line are in `cad/scripts/arm/organic_print.py` on branch `left-arm-organic-r1`, and the gate every
print passes is [part-lifecycle.md](../../../conventions/part-lifecycle.md). Slice with the CLI (`--slice 0 --export-3mf`),
which opens no window, and under `capped.py`.
