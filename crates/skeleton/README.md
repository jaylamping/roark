# skeleton

Loads and checks `config/skeleton.yaml`, the one file that says what the robot is (tenet 2).

## What it does

The file is parsed once, at startup, into checked types (`Skeleton`, with its `Bus`es, `Limb`s and `Joint`s); nothing
downstream sees raw YAML or re-checks it. Every problem in the file is reported at once, each naming its line, limb, joint
and field. The rules are PLAN item 1, "Loader refuses", and skeleton.md sections 4 and 5.

`None` in a loaded value means it isn't known yet (a joint's UID before commissioning, a direction not yet verified). It
loads fine and refuses enable downstream ("Null is not permission", PLAN item 1).

## Must never

Write the skeleton, read any other file about the hardware (CAD, URDF, legacy config), or give a safety value a default.
Unknown is `None`, and `None` refuses enable downstream.

## Talks to

`robstride` for the actuator models, their ranges and the unit types (a cap above the model's range is refused). Read
by every binary that needs the robot's shape: today `sim-drive`, later `runtime` and `robot-cli`. See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

`load` reads and checks a file; `parse` checks text. Either gives the whole `Skeleton` or every problem in it, never a
partly checked one.

```rust
use std::path::Path;

fn main() -> Result<(), skeleton::LoadError> {
    // Doc tests run from the crate's folder, so the repo's skeleton is two levels up.
    let robot = skeleton::load(Path::new("../../config/skeleton.yaml"))?;

    // The drives on one bus, by name and ID: what a bus thread or sim-drive needs.
    let on_can1: Vec<(&str, u8)> = robot
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|bus| bus.as_str() == "can1"))
        .map(|joint| (joint.name.as_str(), joint.id.get()))
        .collect();
    assert!(on_can1.contains(&("left_elbow_pitch", 14)));

    // A bad file is refused whole, each problem with its line.
    let refused = skeleton::parse("schema: 1\nname: robot\n");
    assert!(matches!(refused, Err(skeleton::LoadError::Invalid(problems)) if !problems.is_empty()));
    Ok(())
}
```
