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

A print project is built from the STL export, not from SolidWorks: orientation, the 100 % infill modifiers, supports and
the Bambu Studio command line are in `cad/scripts/arm/organic_print.py` on branch `left-arm-organic-r1`, and the gate every
print passes is [part-lifecycle.md](../../../conventions/part-lifecycle.md). Slice with the CLI (`--slice 0 --export-3mf`),
which opens no window, and under `capped.py`.
