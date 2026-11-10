# Printed parts: requirements, pre-print gate and print log

**Status:** proposed, 2026-11-09.

Every printed structural part of the robot goes through three files, kept in `cad/` beside the CAD
([cad.md](cad.md) has the folders and names):

| File | Where | Written | Read by |
|---|---|---|---|
| Requirements spec | `cad/<region>/<link>_requirements.md` | before the first CAD of a link, agreed by Joey | the design thread, the gate, reviewers |
| Gate report | `cad/prints/<region>/<part>_gate.md` | by `tools/cad/gate.py`, before a 3MF is printed or reviewed | Joey, reviewers, CI |
| Print log | `cad/prints/<region>/<link>_prints.md` | after each print, by the design thread | the next design pass, the gate |

All three are markdown with a TOML block between `+++` lines at the top: people read the markdown, tools read the TOML.
They hold no code and no tool-specific state, so another tool can read the same files later.

**Why:** on the left arm (2026-11-05 to 11-09) most rework came from three places. Requirements arrived after CAD had
started (the 5 kg sweep, the hand bay, clean outer skin), and each forced a redo. Checks were bolted on one at a time, each
after a miss reached Joey (spikes, slivers, notches, infill reset to 15%, a 1 mm interference). And what a real print taught
us (mass, fit, surface) lived only in chat photos that the next thread can't see.

## 1. Requirements spec

One spec per **link** (a structural unit: upper arm, forearm, a torso box, a shell panel set), for both sides. A right-hand
part is the mirror of the left only where the spec says so: actuators are not mirror images, so connector reliefs, bolt-circle
clocking and cable exits are checked again.

**When:** before the first CAD of the link. Joey agrees it (`status = "agreed"`, `agreed = "Joey <date>"`) before layout
freeze, review gate 1. A requirement that arrives later goes into the spec first, with its date, and the design thread says
which parts it reopens.

**Every requirement carries its source:** Joey and the date he said it, a measured value (who, what tool), a vendor document,
or a design decision with its commit. An open number says `TBD` and who is getting it. Values live here once; READMEs and
review packets link to the spec instead of copying it.

The spec holds:

1. **Load cases and pass marks** (`[[load_case]]`): what the load is, where it acts, the pose or sweep, and the bulk and
   layer safety factors it must reach. The gate checks each one against the evidence (section 2).
2. **Motion:** joint ranges and hard stops, and what the stop must carry.
3. **Mass and CoM budget.**
4. **Interfaces** (`interfaces = [...]`): actuator faces, bolt circles, pilots, bearings, inserts, connector reliefs, and the
   parts it bolts to.
5. **Harness:** the cable path through the link, entry and exit holes, service loops, bend radii.
6. **Print rules** (`[print]`): material, colour, plate, settings the 3MF must carry, orientation rules, support allowed on
   visible faces (normally none).
7. **Room to leave** for known future features, and which of them are not constraints yet.
8. **Printed parts** (`[[part]]`): the parts the gate runs on (section 3).

Template (the seeded specs [upper_arm_requirements.md](../cad/upper-arm/upper_arm_requirements.md) and
[forearm_requirements.md](../cad/forearm/forearm_requirements.md) are worked examples):

```toml
+++
link = "upper_arm"
region = "upper-arm"                 # region folder; prints and reports go to prints/<region>/
sides = ["left", "right"]
status = "draft"                     # draft | agreed
agreed = ""                          # "Joey 2026-11-10" once agreed
evidence = "reviews/upper-arm/<YYYYMMDD>_<topic>/evidence.json"   # default for every part; a part may name its own
interfaces = ["RS02 yaw output", "RS02 elbow housing", "6808-2RS"]  # words the gate matches print-log lessons against

[[load_case]]
id = "G90"
what = "Arm straight and horizontal, 5 kg at the hand, plus self-weight (Joey 2026-11-07)"
bulk_sf = 2.0                        # pass marks the FEA must reach
layer_sf = 1.25
# parts = ["..."]                    # only these parts; default all

[print]
material = "PETG"
colour = "white"
plate = "Cool Plate Super Tack"
visible_support_mm2 = 0
settings = { layer_height = "0.2", support_type = "tree(auto)" }   # Bambu Studio project keys and values
preset = ["layer_height"]            # settings whose value is the system preset's, so Bambu Studio doesn't flag them

[[part]]
name = "upper_arm_shell_front_left"  # file stem; the 3MF is prints/<region>/<name>.3mf
export = "exports/upper-arm/upper_arm_shell_front_left.stl"
up = [0, 0, 1]                       # print direction, in export coordinates
hidden_by = ["exports/upper-arm/upper_arm_shell_back_left.stl"]    # assembled parts that can hide a face
mates = ["exports/upper-arm/vendor_robstride_rs02_elbow_left.stl"] # mating meshes, same coordinates, for interference
settings = { sparse_infill_density = "50%", wall_loops = "4" }     # adds to or overrides [print].settings
# visible_support_mm2 = 5, visible_support_reason = "..."           # only with a reason
+++
```

## 2. Evidence file

The results the gate can't compute itself: FEA and the assembly checks. A JSON file in the review packet that produced them
(`cad/reviews/<region>/<YYYYMMDD>_<topic>/evidence.json`, so it is pinned with the packet), written by the script that ran
the study:

```json
{
  "sources": {"exports/upper-arm/upper_arm_shell_front_left.stl": "<sha256 of the export the study used>"},
  "fea": [
    {"case": "G90", "part": "upper_arm_shell_front_left", "bulk_sf": 3.10, "layer_sf": 7.0, "converged": true,
     "note": "el 2.0 vs 1.6 within 2 %"}
  ],
  "access": [
    {"part": "upper_arm_shell_front_left", "insertion_clear": true, "screws_reachable": true,
     "method": "ray check, 2.5 mm hex straight then 25 deg ball-end", "notes": ""}
  ]
}
```

- `sources` lists every export the study used, with the hash of its real content (`gitlfs.content_sha256`, the LFS oid). If
  any of them has changed since, the evidence is stale and the gate fails. **Why:** numbers from an older geometry were
  reported as passes.
- `part` is a part name, or `"*"` for a result on the whole link model.
- `converged` is true only when the result held on a finer mesh (say within 5 %), and a peak at a load patch, fixture edge or
  sharp re-entrant corner has been excluded or fixed. A singular peak is not a result.
- `access`: the part can go in along its path in assembly order, and every screw head reaches its seat with a driver that
  fits, in that order. Record the method. **Why:** the RS00 had no way into the forearm, and its housing screws were
  unreachable (2026-11-07).

## 3. Pre-print gate

```bash
python tools/cad/gate.py upper_arm_shell_front_left   # one part
python tools/cad/gate.py --all                         # every part in every spec
```

It runs on Joey-PC (or anywhere with the LFS content and `pip install numpy scipy trimesh rtree`) and writes
`cad/prints/<region>/<part>_gate.md` with PASS or FAIL per check and the hash of every input it judged: the spec, export,
3MF, picture sheet, evidence file, the part's mesh-whitelist entry, and the `hidden_by` and `mates` meshes. It fails when:

| Check | Fails when | Added after |
|---|---|---|
| Requirements agreed | the spec is not `agreed` | three mid-design redos on the forearm |
| Files present | the export, the 3MF or the picture sheet (`<part>_sheet.png`, all sides including the bed side) is missing | defects missed by single-view checks |
| Mesh ([mesh_check.py](../tools/cad/mesh_check.py)) | not one watertight body; an unlisted vertex sharper than 150°, knife edge, wall under 0.6 mm over 0.5 mm², or surface step over 0.03 mm over 1 mm² | spikes, slivers, then notches reached Joey (2026-11-07) |
| Support on visible faces ([part_checks.py](../tools/cad/part_checks.py)) | support touches more visible outer area than the spec allows | rough upper-arm skin, trapped cavity support (2026-11-08) |
| Interference | a `mates` mesh overlaps the part by more than 0.05 mm | RS02 tab lip about 1 mm into the upper arm (2026-11-08) |
| 3MF settings | material or a spec setting differs, or a spec setting isn't flagged in `different_settings_to_system` (unless the spec lists it in `preset`) | infill reset to 15% on open (2026-11-07) |
| Evidence | a load case has no result, isn't converged or is under its pass mark; access isn't recorded; any source changed | stale or singular FEA reported as passes (2026-11-07) |

It warns (without failing) when a part has no `mates`, and for each print-log lesson that matches the part (section 4).

Mesh exceptions are reviewed spots, never a way to pass: they go in
[cad/manifests/mesh-whitelist.json](../cad/manifests/mesh-whitelist.json), keyed by part name, each with a reason, added only
after looking at the spot in a render and in the CAD. The format is the one `mesh_check.check` takes: `corners` and `folds`
(points), `thin` (boxes), `bodies`, `revolve`.

**A passing report is the condition for printing and for a review packet.** Commit it with the 3MF. `gate.py --verify` (in
[scripts/check.sh](../scripts/check.sh), so CI runs it) fails when a committed 3MF anywhere under `cad/prints/` has no report
beside it, its report did not pass, or any input the report records changed or went missing after the gate ran. It reads
only hashes, so it needs no LFS content. Text inputs are hashed with LF line ends, so a Windows checkout and CI agree.

## 4. Print log

One file per link, `cad/prints/<region>/<link>_prints.md`, one `[[print]]` entry per printed revision, newest first. After a
print, the design thread asks Joey for the weight on the scale and two or three photos (fit, outer skin, anything he filed,
cut or forced) and writes the entry; Joey never fills in the form. Photos go beside it as `<part>_<YYYYMMDD>_<what>.png`
(under 2 MB each).

```toml
[[print]]
part = "upper_arm_shell_front_left"
revision = "draft 3"
cad = "roark <commit>"               # the commit the 3MF was made from
date = "2026-11-10"
printer = "P2S, 0.4 mm high flow"
material = "PETG, white"
plate = "Cool Plate Super Tack"
settings = "4 walls, 50%, 100% modifiers on posts and seats, tree supports, seam face down"
mass_g = 0                           # weighed
mass_sliced_g = 0                    # Bambu Studio estimate
fit = ["RS02 seats by hand; tab lip clear by 0.4 mm (caliper)"]
surface = ["clean outer skin; support scars only inside"]
post_work = "none"                   # what Joey filed, cut, drilled or forced
action = "none"                      # the design change it caused
action_commit = ""
source = "Joey, chat 2026-11-10 14:02Z, photos below"

[[lesson]]                           # only what the next design should apply; the gate warns on matching parts
id = "rs02-housing-tab"
applies_to = ["rs02"]                # words matched against part names, region, interfaces, mates and material
text = "..."
allowance_mm = 1.0                   # optional
```

A `[[lesson]]` is written when a print taught something that applies beyond this part: an allowance a printed seat needs,
a vendor feature the model got wrong, a slicer estimate that runs high. **Why:** the next part is often designed in a new
thread, which starts from what is in the repo.

## 5. Where this sits in the review gates

| Gate | Needs |
|---|---|
| Spec agreed | Joey agrees the requirements spec |
| 1. Layout freeze | the spec is agreed; layout review against it |
| 2. Before print or promote | a passing gate report for each part; the review packet links them |
| 3. Before load-bearing or powered | the print-log entry for the printed parts, with weighed mass and fit notes |
