//! The caps a joint is enabled at (PLAN item 1, Null is not a number; Commissioning caps).

use robstride::{Amps, Model, NewtonMeters, RadPerSec};
use skeleton::{Caps, Joint};

const FIXTURE: &str = "\
schema: 1
name: caps_robot
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
      - name: set
        actuator: rs03
        bus: bus0
        id: 11
        uid: null
        direction: -1
        zero_rad: 3.0
        reference_pose: null
        hard_rad: [-0.5, 1.5]
        soft_rad: null
        torque_cap_nm: 10.0
        current_cap_a: 12.0
        speed_cap_rad_s: 1.0
  right_arm:
    joints: []
  waist:
    joints: []
  left_leg:
    joints: []
  right_leg:
    joints: []
";

/// Guards: safety - `drive.caps`: a commissioned joint is enabled at its own caps, and an uncommissioned one (any cap,
/// `direction`, `zero_rad` or `hard_rad` null) at its model's commissioning caps for all three, or its own where lower,
/// cap by cap; the rows pin each model's commissioning caps to [PLAN, Open with
/// Joey](https://github.com/jaylamping/roark/blob/main/PLAN.md#open-with-joey) 11 (PLAN item 1).
#[test]
fn a_joint_is_enabled_at_its_own_caps_only_once_commissioned() {
    let set = skeleton::parse(FIXTURE).unwrap().limbs[0].joints[0].clone();
    let nm = |v| NewtonMeters::new(v).unwrap();
    let amps = |v| Amps::new(v).unwrap();
    let rad_s = |v| RadPerSec::new(v).unwrap();
    assert_eq!(
        set.caps(),
        Caps {
            torque: nm(10.0),
            current: amps(12.0),
            speed: rad_s(1.0)
        }
    );
    let bare = Joint {
        direction: None,
        zero_rad: None,
        hard_rad: None,
        torque_cap_nm: None,
        current_cap_a: None,
        speed_cap_rad_s: None,
        ..set.clone()
    };
    for (model, torque, current) in [
        (Model::Rs00, 0.7, 0.8),
        (Model::Rs02, 0.7, 0.8),
        (Model::Rs03, 3.0, 2.15),
        (Model::Rs04, 6.0, 4.5),
    ] {
        let caps = Joint {
            actuator: model,
            ..bare.clone()
        }
        .caps();
        // A share of a range isn't exact in binary, so the pinned decimals are compared to within rounding.
        assert!(
            (caps.torque.get() - torque).abs() < 1e-9
                && (caps.current.get() - current).abs() < 1e-9
                && caps.speed == rad_s(0.5),
            "{model:?}: {caps:?}"
        );
    }
    let commissioning = bare.caps();
    let edits: [fn(&mut Joint); 6] = [
        |j| j.direction = None,
        |j| j.zero_rad = None,
        |j| j.hard_rad = None,
        |j| j.torque_cap_nm = None,
        |j| j.current_cap_a = None,
        |j| j.speed_cap_rad_s = None,
    ];
    for (i, edit) in edits.iter().enumerate() {
        let mut joint = set.clone();
        edit(&mut joint);
        assert_eq!(
            joint.caps(),
            commissioning,
            "edit {i}: all three drop, not only a null one"
        );
    }
    // Its own where lower, cap by cap: an uncommissioned joint never runs above what the skeleton agreed.
    let mixed = Joint {
        direction: None,
        torque_cap_nm: Some(nm(1.0)),
        current_cap_a: Some(amps(12.0)),
        speed_cap_rad_s: None,
        ..set.clone()
    };
    assert_eq!(
        mixed.caps(),
        Caps {
            torque: nm(1.0),
            current: commissioning.current,
            speed: commissioning.speed
        }
    );
    let low = Joint {
        direction: None,
        torque_cap_nm: Some(nm(1.0)),
        current_cap_a: Some(amps(1.0)),
        speed_cap_rad_s: Some(rad_s(0.25)),
        ..set
    };
    assert_eq!(
        low.caps(),
        Caps {
            torque: nm(1.0),
            current: amps(1.0),
            speed: rad_s(0.25)
        }
    );
}
