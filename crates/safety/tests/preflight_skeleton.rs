//! Preflight's refusals from the skeleton alone, before anything is sent (PLAN item 6 drive layer and Preflight row;
//! safety.md section 6.1).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use common::{joint, skeleton};
use robstride::{Amps, NewtonMeters, ParamValue, RadPerSec};
use safety::{CapKind, Refusal, RuleId, Target};

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

/// Guards: safety - `host.preflight`: a model whose MIT scales aren't settled is refused before anything is sent (PLAN
/// item 2, the RS00's scales); a joint with null facts or caps is not refused (item 1).
#[test]
fn an_unsettled_model_refuses_and_null_facts_or_caps_do_not() {
    let skeleton = skeleton();
    let set = joint(&skeleton, 0);
    let target = |joint: &skeleton::Joint| Target::new(joint, &skeleton.power).map(|_| ());
    let bare = skeleton::Joint {
        direction: None,
        zero_rad: None,
        hard_rad: None,
        torque_cap_nm: None,
        current_cap_a: None,
        speed_cap_rad_s: None,
        ..set.clone()
    };
    assert_eq!(target(&bare), Ok(()));
    let rs00 = skeleton::Joint {
        actuator: robstride::Model::Rs00,
        ..set.clone()
    };
    assert_eq!(
        target(&rs00),
        Err(Refusal::UnvouchedModel(robstride::Model::Rs00))
    );
    assert_eq!(
        Refusal::UnvouchedModel(robstride::Model::Rs00).rule(),
        RuleId::HostPreflight
    );
}
