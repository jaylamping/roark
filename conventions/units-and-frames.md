# Units, signs and frames

**Status:** proposed for Joey's review, 2026-11-08. Applies to code, config, logs, the `api`, the UI and docs.

A robot has three ways to be quietly wrong about a number: the wrong unit, the wrong sign, or the wrong frame. None of them
causes a compile error or a crash; all of them move a motor the wrong way. This page fixes one answer for each, so nobody has
to guess. The newtypes that enforce units in Rust are in [rust.md section 3](rust.md#3-types-carry-meaning).

## 1. One unit system: SI, radians

| Quantity | Unit in code, config, logs and `api` | Rust newtype |
|---|---|---|
| Angle, joint position | radians (rad) | `Radians` |
| Angular velocity | rad/s | `RadPerSec` |
| Torque | newton metres (N·m) | `NewtonMeters` |
| Current | amperes (A) | `Amps` |
| Voltage | volts (V) | `Volts` |
| Temperature | degrees Celsius (°C) | `Celsius` |
| Length | metres (m) | `Meters` |
| Mass | kilograms (kg) | `Kilograms` |
| Time span | seconds as `Duration` in Rust; `_s` or `_ms` suffix in config | `std::time::Duration` |
| Frequency | hertz (Hz) | plain `u32` with `_hz` name suffix |
| Power, energy | watts (W), joules (J) | `Watts`, `Joules` |

- **Degrees appear only on screen and in prose for people.** The UI may show degrees; it converts at the last moment and labels
  the unit. Config never takes degrees. **Why:** the elbow stop is 124°, which is 2.164 rad. One file in degrees and one in
  radians is a bug waiting for the day someone copies a number across.
- **Celsius, not kelvin,** because the drives report °C and every limit we have (pause at 60 °C, stop at 75 °C) is written in
  °C. This is the one deliberate exception to strict SI.
- **Milliseconds are fine in config when they read better** (`can_timeout_ms: 50`), as long as the key says so. Inside Rust
  every span is a `Duration`, so the unit can't be lost.
- **The drive's own encodings never leave the codec.** RobStride sends positions, velocities and torques as scaled integers
  (MIT mode `u16` ranges, parameter `f32`s with their own units). The `robstride` crate converts to the SI newtypes at the edge
  and nothing else ever sees a raw drive value. **Why:** the legacy RS03 velocity scale was wrong (±20 rad/s measured, not
  the manual's figure); one conversion point meant one fix.

### Unit suffixes where there's no type

In YAML keys, JSON fields, CSV columns, log field names and TypeScript properties, the unit goes in the name whenever the value
is a bare number: `position_rad`, `torque_nm`, `current_a`, `temp_c`, `vbus_v`, `period_ms`, `rate_hz`. **Why:** a newtype
protects Rust code, but a YAML file or a Grafana panel only has the name. In JS terms, it's the difference between `timeout:
50` and `timeoutMs: 50`.

## 2. Robot frame

- **REP-103:** X forward, Y left, Z up, right-handed. This matches the URDF generated from CAD
  ([STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md#left-arm-joints-urdf-can)).
- **Base frame** is the pelvis (`base_link`), with Z up when the robot stands upright. While the robot is stationary on its
  stand, `base_link` is fixed to the world.
- **Positive rotation follows the right-hand rule** about the joint axis as defined in the URDF.
- **Transforms are named `a_from_b`:** `base_from_shoulder` maps a point in the shoulder frame into the base frame, so they
  chain by reading right to left: `point_in_base = base_from_shoulder * point_in_shoulder`. Positions and velocities say which
  frame they're in (`hand_pos_in_base`). **Why:** a transform used backwards compiles and runs and puts the hand somewhere
  else. When the frames are in the name, a wrong chain looks wrong (`base_from_shoulder * point_in_elbow`). This is rerun's
  convention; Drake's monogram notation (`p_BoBcm_B`) does the same job but is harder to read for newcomers.
- **Left and right** always mean the **robot's** left and right, as if you were standing inside it. Never the viewer's.
  **Why:** the hardware project already hit this: the built arm on the bench is the robot's *right* arm.

## 3. Joint signs and zeros

The facts live elsewhere: what positive means for each joint is in
[STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md#left-arm-joints-urdf-can); the conversion
between drive and joint, the zero convention and the persistence test are in
[PLAN item 1](../PLAN.md#1-the-skeleton-yaml-tenets-1-and-2); each joint's `direction` and `zero_rad` are in
`config/skeleton.yaml`. This section is how code treats them.

- **Positive means the same thing on both sides of the body** (STATUS.md lists the meanings). For mirrored limbs the URDF
  axes and the skeleton's `direction` carry the difference. Code never contains "if right arm, flip the sign". **Why:** a
  side check in code is a second copy of a hardware fact (tenet 2) and the first thing to go wrong when a limb is added.
- **The conversion lives in exactly one function** in each direction (drive to joint, joint to drive), and every command and
  reading goes through it. **Why:** when a joint moves the wrong way there is one place to look, and one `Guards: safety`
  test covers it.
- **Unverified is `null`, never a guess.** A `direction` or `zero_rad` that hasn't been checked on the hardware stays `null`
  and the joint is refused at enable (PLAN item 1, "Null is not permission"). Nobody writes `1` "for now".
- **No wrapping in joint space.** Joint positions are continuous values inside the joint's limits; code never normalises them
  into ±π. **Why:** no joint on this robot turns a full revolution, so a jump across ±π means a lost zero or a decode bug, and
  wrapping it would hide exactly the failure we need to see.

## 4. Limits and caps

The values and the loader's checks are in [PLAN item 1](../PLAN.md#1-the-skeleton-yaml-tenets-1-and-2) and
[item 6](../PLAN.md#6-safety-the-three-layers-tenet-3). How to think about them:

- **Order, outside in:** hard stop (physical) → hard limit (skeleton) → soft limit (supervised or unattended inset) → commands.
  A command is clamped to the soft limit; crossing the hard limit is a fault.
- **A torque cap is the weakest-part number, not the actuator's rating.** If a printed stop is rated 17 N·m, that's the
  joint's cap even if the drive can do more. The skeleton comment next to each cap names the part or test that sets it.
- **Never widen a limit to make a run pass.** A limit change is a skeleton PR from the hardware side, with its reason
  ([skeleton.md](skeleton.md)).

## 5. Time and timestamps

- Stamps are `u64` **nanoseconds** since the Unix epoch in logs, MCAP and the `api` (`stamp_ns`). Inside the realtime loop,
  `Instant` on the monotonic clock ([architecture.md section 7](architecture.md#7-time)).
- CAN frames carry the **kernel RX timestamp**, not the time the user-space code got round to reading them.
- Durations in logs use the same suffix rule as everything else (`latency_us`, `age_ms`).

## 6. Identity

- **Joint names** are the skeleton's, `snake_case`, side first: `left_shoulder_pitch`, `right_elbow_pitch`. They are the only
  joint identifiers in code, logs, the `api` and the UI. No aliases ("elbow", "J4") anywhere. **Why:** the legacy stack had
  aliases that resolved differently depending on which arms were wired.
- **Limb names:** `left_arm`, `right_arm`, `left_leg`, `right_leg`, `waist`.
- **Buses** are named by the skeleton (`can0` to `can4`, `vcan0` to `vcan4` in sim). A joint is addressed by `(bus,
  device_id)` on the wire and by its name everywhere else.

## Checklist

- Every bare number in config, logs, CSV or JSON has a unit suffix.
- No degrees outside the UI's display layer and human-facing prose.
- No raw drive integers outside `robstride`.
- No side-specific sign flips in code; signs come from `direction` and the URDF.
- New joints follow `side_part_axis` naming and appear in the skeleton before anywhere else.

## Sources

- ROS REP-103 (SI units, Celsius, X forward / Y left / Z up): https://www.ros.org/reps/rep-0103.html and REP-105 (named
  frames): https://www.ros.org/reps/rep-0105.html
- rerun CODE_STYLE (units in names such as `duration_secs`, radians, `a_from_b` transforms):
  https://github.com/rerun-io/rerun/blob/main/CODE_STYLE.md
- Drake monogram notation: https://drake.mit.edu/doxygen_cxx/group__multibody__quantities.html
- TigerBeetle TIGER_STYLE (units last in names, `latency_ms_max`): https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md
- Cautionary: K-Scale's KOS actuator API takes degrees and percent torque, with units only in comments
  (https://github.com/kscalelabs/kos/blob/master/kos/proto/kos/actuator.proto); moteus works in output-shaft rotations
  (https://mjbots.github.io/moteus/protocol/registers/). Both are why vendor units stop at the codec here.
