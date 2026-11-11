//! Preflight's refusals from the skeleton alone, before anything is sent (PLAN item 6 drive layer and Preflight row;
//! safety.md section 6.1).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use common::{joint, skeleton};
use robstride::{Amps, NewtonMeters, ParamValue, RadPerSec};
use safety::{CapKind, Refusal, RuleId, Target};
use skeleton::CommissioningCaps;

/// Guards: safety - `drive.caps`: a cap outside what the drive's model can be set to refuses before anything is sent,
/// naming the skeleton's value and the model's highest with their unit (RS03: 60 N·m, 43 A, 20 rad/s; the model's
/// highest passes).
#[test]
fn a_cap_the_model_cant_take_refuses_before_anything_is_sent() {
    let skeleton = skeleton();
    let rs03 = joint(&skeleton, 0);
    let target = |joint: &skeleton::Joint| Target::new(joint, &skeleton.power).map(|_| ());
    let at_max = skeleton::Joint {
        torque_cap_nm: NewtonMeters::new(60.0),
        current_cap_a: Amps::new(43.0),
        speed_cap_rad_s: RadPerSec::new(20.0),
        ..rs03.clone()
    };
    assert_eq!(target(&at_max), Ok(()));
    let nm = |v| ParamValue::NewtonMeters(NewtonMeters::new(v).unwrap());
    let amps = |v| ParamValue::Amps(Amps::new(v).unwrap());
    let rad_s = |v| ParamValue::RadPerSec(RadPerSec::new(v).unwrap());
    for (joint, cap, value, max) in [
        (
            skeleton::Joint {
                torque_cap_nm: NewtonMeters::new(60.5),
                ..rs03.clone()
            },
            CapKind::Torque,
            nm(60.5),
            nm(60.0),
        ),
        (
            skeleton::Joint {
                current_cap_a: Amps::new(43.5),
                ..rs03.clone()
            },
            CapKind::Current,
            amps(43.5),
            amps(43.0),
        ),
        (
            skeleton::Joint {
                speed_cap_rad_s: RadPerSec::new(20.5),
                ..rs03.clone()
            },
            CapKind::Speed,
            rad_s(20.5),
            rad_s(20.0),
        ),
        // Below the range too: a negative cap is no cap a drive can be set to.
        (
            skeleton::Joint {
                torque_cap_nm: NewtonMeters::new(-1.0),
                ..rs03.clone()
            },
            CapKind::Torque,
            nm(-1.0),
            nm(60.0),
        ),
    ] {
        assert_eq!(
            target(&joint),
            Err(Refusal::CapOutOfRange { cap, value, max }),
            "{cap:?}"
        );
    }
    for (cap, value, max, said) in [
        (
            CapKind::Torque,
            nm(60.5),
            nm(60.0),
            "torque_cap_nm is 60.5 N·m in the skeleton, expected 0 to 60 N·m",
        ),
        (
            CapKind::Speed,
            rad_s(20.5),
            rad_s(20.0),
            "speed_cap_rad_s is 20.5 rad/s in the skeleton, expected 0 to 20 rad/s",
        ),
    ] {
        assert_eq!(
            Refusal::CapOutOfRange { cap, value, max }.message("arm_joint_one"),
            format!("refused (drive.caps): arm_joint_one {said} for its drive"),
            "the value and the bound with their unit"
        );
    }
}

/// Guards: safety - `drive.caps`: null is not a refusal (PLAN item 1). A joint with a null `direction`, `zero_rad`,
/// `hard_rad` or cap is uncommissioned and gets its model's commissioning caps (5 % of the torque and current ranges,
/// 0.5 rad/s; RS03: 3 N·m, 2.15 A), or its own cap where that is lower; a commissioned joint keeps its own. A model
/// whose MIT scales aren't settled is still refused before anything is sent (item 2, the RS00's scales).
#[test]
fn an_uncommissioned_joint_runs_at_its_models_commissioning_caps() {
    let skeleton = skeleton();
    let set = joint(&skeleton, 0);
    let caps = |joint: &skeleton::Joint| {
        let target = Target::new(joint, &skeleton.power).unwrap();
        (target.commissioned(), target.caps().map(|w| w.value()))
    };
    let own = caps(&set);
    assert!(own.0);
    let floor = CommissioningCaps::of(robstride::Model::Rs03).unwrap();
    assert_eq!(
        (floor.torque.get(), floor.current.get(), floor.speed.get()),
        (3.0, 43.0 * 0.05, 0.5)
    );
    // As the drive stores them, rounded to f32: what a commissioned joint with these caps would write.
    let at_floor = (
        false,
        caps(&skeleton::Joint {
            torque_cap_nm: Some(floor.torque),
            current_cap_a: Some(floor.current),
            speed_cap_rad_s: Some(floor.speed),
            ..set.clone()
        })
        .1,
    );
    for uncommissioned in [
        skeleton::Joint {
            direction: None,
            ..set.clone()
        },
        skeleton::Joint {
            zero_rad: None,
            ..set.clone()
        },
        skeleton::Joint {
            hard_rad: None,
            ..set.clone()
        },
        skeleton::Joint {
            torque_cap_nm: None,
            current_cap_a: None,
            speed_cap_rad_s: None,
            direction: None,
            zero_rad: None,
            hard_rad: None,
            ..set.clone()
        },
    ] {
        assert_eq!(caps(&uncommissioned), at_floor, "{uncommissioned:?}");
    }
    // Its own cap where lower: an uncommissioned joint never runs above what the skeleton agreed.
    let low = skeleton::Joint {
        direction: None,
        torque_cap_nm: NewtonMeters::new(1.0),
        ..set.clone()
    };
    assert_eq!(
        caps(&low).1[0],
        ParamValue::NewtonMeters(NewtonMeters::new(1.0).unwrap())
    );
    let rs00 = skeleton::Joint {
        actuator: robstride::Model::Rs00,
        ..set.clone()
    };
    assert_eq!(
        Target::new(&rs00, &skeleton.power).map(|_| ()),
        Err(Refusal::UnvouchedModel(robstride::Model::Rs00))
    );
    assert_eq!(
        Refusal::UnvouchedModel(robstride::Model::Rs00).rule(),
        RuleId::HostPreflight
    );
}
