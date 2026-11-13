# Skeleton conventions

**Status:** proposed for Joey's review, 2026-11-08.

`config/skeleton.yaml` is the one file that tells the software what the robot is (tenet 2). Its shape, the loader's checks,
the zero convention and the drive-to-joint conversion are specified in
[PLAN item 1](../PLAN.md#1-the-skeleton-yaml-tenets-1-and-2). This page is about **how the file is written, changed and
reviewed**, so the contract stays trustworthy as five limbs land in it.

## 1. Who owns what

| Part | Owner | How it changes |
|---|---|---|
| Schema (field names, types, checks) and loader | Software | A PR to the `skeleton` crate, with the schema version bumped if old files no longer load |
| Values (IDs, buses, limits, caps, directions, zeros) | Hardware side | A PR that touches **only** `config/skeleton.yaml`, plus a STATUS.md change-log line in marengo the same day |
| Proposed values from tools (limit teaching, commissioning) | Tool output | A diff a person turns into a hardware-side PR. The runtime never writes the file |

**Why:** if the software side "fixes" a limit to make a run pass, the file stops meaning "what the hardware can take". Keeping
values PRs separate from code PRs also makes them easy to review: the diff is only numbers, each with its reason.

## 2. Every value has a source

Each number that comes from somewhere specific carries a short YAML comment saying where:

```yaml
- name: left_elbow_pitch
  actuator: rs02
  bus: can1
  id: 14                       # STATUS.md (proposal)
  direction: null              # sign check not run yet
  zero_rad: null               # persistence test pending (PLAN item 1)
  hard_rad: [0.0, 2.164]       # printed stop at 124 deg, STATUS.md
  torque_cap_nm: 17.0          # printed stop design load, ELBOW_DUMMY_OUTPUT_TEST.md
```

- Sources are a doc name, a test name or a bench session, short enough to fit on the line.
- Comments say where the value came from, not what the field means. Field meanings live in the loader's doc comments.

**Why:** in six months nobody remembers why the elbow cap is 17. A source on the line answers it without archaeology, and
makes a reviewer ask the right question when a number changes: "did the source change too?"

## 3. Unknown is `null`

- A value nobody has measured or verified is `null`. Never a guess, a typical value or a copy from another joint.
- `null` in a required field loads fine and refuses the motion that needs it (PLAN item 1, "Null is not a number").
  That's the point: an unfinished joint is visibly unfinished, and can still be commissioned.
- Unbuilt limbs are present with their joints and `bus: null`. They show as offline (tenet 1).

**Why:** a plausible placeholder looks exactly like a real value. The legacy humanoid templates carried bus and ID numbers that
were never right, and people copied them.

## 4. Format

- **Plain YAML, no anchors, aliases or merge keys** (`&`, `*`, `<<`). Every joint is written out in full. **Why:** anchors
  save typing but make a joint's real values invisible at the place you read them, and the file is read far more than
  written.
- **Order:** limbs in the order `left_arm`, `right_arm`, `waist`, `left_leg`, `right_leg`; joints shoulder to hand (or hip to
  foot), the same order as the drive IDs.
- **Units in key names** (`_rad`, `_nm`, `_a`, `_rad_s`, `_v`, `_ms`, `_hz`) per [units-and-frames.md](units-and-frames.md).
- **Ranges as `[lower, upper]`** lists, never two separate keys that can drift apart.
- **One fact, one place.** Per-model data (MIT scales, the drive's own ranges) lives in the codec table from the manuals, not in
  the skeleton. Masses, centres of mass and friction live in `config/dynamics.yaml`. The skeleton never repeats them.
- **No environment overrides.** No `skeleton.bench.yaml`, no env vars that patch values. A bench setup that needs different
  values (the 24 V supply's VBUS window) is expressed as a field in the file (`power.source`), not a second file.
- The robot's name appears once, as `name:`.

## 5. Loader rules (for the `skeleton` crate)

- **Parse once, at startup, into checked types** ([rust.md section 3](rust.md#3-types-carry-meaning)). Nothing downstream sees
  raw YAML or re-checks it.
- **Unknown keys are an error.** **Why:** a misspelt `torque_cap_mn` would otherwise be
  silently ignored, leaving the cap `null` or, worse, defaulted.
- **No defaults for safety values.** Every field is written out, as `null` if unknown; a missing key is an error. Defaults exist only where
  PLAN names them (the soft-limit inset).
- **Every error names the limb, the joint and the field**, and the loader reports all errors at once rather than stopping at
  the first. **Why:** the hardware side fixes the file in one pass instead of one restart per typo.
- **The schema version is checked.** A file with a version the loader doesn't know is refused with a clear message.

## 6. Reviewing a skeleton PR

A reviewer (Joey, per PLAN's merge rule) checks:

1. The PR touches only `config/skeleton.yaml`.
2. Every changed value has a source comment, and the source says what the value says.
3. No `null` became a number without the test that verifies it (sign check, persistence test, rig test).
4. No limit got wider without a hardware reason.
5. CI's "skeleton loads" check is green.
6. STATUS.md in marengo has the matching change-log line.
