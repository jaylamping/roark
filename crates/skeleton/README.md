# skeleton

Loads and checks `config/skeleton.yaml`, the one file that says what the robot is (tenet 2).

## What it does

The file is parsed once, at startup, into checked types (`Skeleton`, with its `Bus`es, `Limb`s and `Joint`s); nothing
downstream sees raw YAML or re-checks it. Every problem in the file is reported at once, each naming its line, limb, joint
and field. The rules are PLAN item 1, "Loader refuses", and skeleton.md sections 4 and 5.

`None` in a loaded value means it isn't known yet (a joint's UID before commissioning, a direction not yet verified). It
loads fine and refuses only the motion that needs it, never the enable: a joint with a null cap, `direction`, `zero_rad`
or `hard_rad` runs at its model's commissioning caps, or its own where lower (`Joint::caps`;
the values are [PLAN, Open with Joey](https://github.com/jaylamping/roark/blob/main/PLAN.md#open-with-joey) 11). The
current budget counts each joint at the current cap it is enabled at.

## Must never

Write the skeleton, read any other file about the hardware (CAD, URDF, legacy config), or give a safety value a default.
Unknown is `None`; downstream, a `None` cap, `direction`, `zero_rad` or `hard_rad` lowers a joint to its commissioning
caps, a `None` UID skips the UID check, and any `None` refuses the motion that needs it.

## Talks to

`robstride` for the actuator models, their ranges and the unit types (a cap above the model's range is refused). Read
by every binary that needs the robot's shape: `runtime` and `sim-drive` today, `robot-cli` later. See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

`load` reads and checks a file; `parse` checks text. Either gives the whole `Skeleton` or every problem in it, never a
partly checked one. `read` is `load`'s read alone, for a caller that hashes exactly the text it then parses.

```rust
/// A small skeleton: two drives wired on one bus, one joint not wired yet, and the other limbs empty.
const ROBOT: &str = "\
schema: 1
name: example
power:
  source: bench_24v
  vbus_v: [22.0, 26.0]
  current_budget_a: 25.0
buses:
  bus0:
    bitrate_bps: 1000000
    sample_point: 0.75
    adapter_serial: null
limbs:
  left_arm:
    joints:
      - name: shoulder
        actuator: rs03
        bus: bus0
        id: 11
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: null
        speed_cap_rad_s: null
      - name: elbow
        actuator: rs03
        bus: bus0
        id: 12
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: null
        speed_cap_rad_s: null
      - name: wrist
        actuator: rs03
        bus: null
        id: 13
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: null
        speed_cap_rad_s: null
  right_arm:
    joints: []
  waist:
    joints: []
  left_leg:
    joints: []
  right_leg:
    joints: []
";

fn main() -> Result<(), skeleton::LoadError> {
    let robot = skeleton::parse(ROBOT)?;

    // The drives on one bus, by name and ID: what a bus thread or sim-drive needs. The wrist isn't wired, so it
    // isn't on any bus.
    let on_bus0: Vec<(&str, u8)> = robot
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|bus| bus.as_str() == "bus0"))
        .map(|joint| (joint.name.as_str(), joint.id.get()))
        .collect();
    assert_eq!(on_bus0, [("shoulder", 11), ("elbow", 12)]);

    // A bad file is refused whole, each problem naming where it is: here two drives share an ID on one bus.
    match skeleton::parse(&ROBOT.replace("id: 12", "id: 11")) {
        Err(skeleton::LoadError::Invalid(problems)) => {
            let paths: Vec<&str> = problems.iter().map(|p| p.path.as_str()).collect();
            assert_eq!(paths, ["limbs.left_arm.elbow.id"]);
        }
        other => panic!("two drives with one ID must be refused, got {other:?}"),
    }
    Ok(())
}
```
