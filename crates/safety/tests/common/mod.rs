//! Shared helpers: a small skeleton fixture (never the live skeleton, testing.md rule 3) and drive views as the bus
//! layer would publish them.

use can::{DriveView, EchoSeen, Observed, StopOutcome};
use robstride::{
    Celsius, DeviceId, EchoKind, Feedback, Inbound, Mode, NewtonMeters, RadPerSec, Radians,
    StatusFaults, decode, drive,
};
use skeleton::{Joint, Skeleton};

/// One arm on one bus. `arm_joint_one` is fully set (direction, zero and hard limits too); `arm_joint_two` leaves its
/// torque cap null; `arm_joint_three` has no bus yet; `arm_joint_four` has every cap, a direction, a zero and hard
/// limits, and no UID.
pub(crate) const FIXTURE: &str = "\
schema: 1
name: test_robot
power:
  source: bench_24v
  vbus_v: [22.0, 26.0]
  current_budget_a: 40.0
buses:
  bus0:
    bitrate_bps: 1000000
    sample_point: 0.75
    adapter_serial: null
limbs:
  left_arm:
    joints:
      - name: arm_joint_one
        actuator: rs03
        bus: bus0
        id: 101
        uid: \"0x0123456789abcdef\"
        direction: -1
        zero_rad: 2.0
        reference_pose: null
        hard_rad: [-0.5, 1.5]
        soft_rad: null
        torque_cap_nm: 10.0
        current_cap_a: 12.0
        speed_cap_rad_s: 1.0
      - name: arm_joint_two
        actuator: rs02
        bus: bus0
        id: 102
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: 10.0
        speed_cap_rad_s: 2.0
      - name: arm_joint_three
        actuator: rs02
        bus: null
        id: 103
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: 5.0
        current_cap_a: 10.0
        speed_cap_rad_s: 2.0
      - name: arm_joint_four
        actuator: rs02
        bus: bus0
        id: 104
        uid: null
        direction: 1
        zero_rad: 0.0
        reference_pose: null
        hard_rad: [0.5, 1.5]
        soft_rad: null
        torque_cap_nm: 5.0
        current_cap_a: 10.0
        speed_cap_rad_s: 2.0
  right_arm:
    joints: []
  waist:
    joints: []
  left_leg:
    joints: []
  right_leg:
    joints: []
";

#[expect(clippy::unwrap_used, reason = "test helper; the fixture is valid")]
pub(crate) fn skeleton() -> Skeleton {
    skeleton::parse(FIXTURE).unwrap()
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper; the fixture has four joints"
)]
pub(crate) fn joint(skeleton: &Skeleton, n: usize) -> Joint {
    skeleton
        .limbs
        .first()
        .unwrap()
        .joints
        .get(n)
        .unwrap()
        .clone()
}

#[expect(clippy::unwrap_used, reason = "test helper; the IDs are valid")]
pub(crate) fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

/// A status from drive 101 (an RS03) in `mode` with `faults`, read at `read_ns`.
#[expect(clippy::unwrap_used, reason = "test helper; the feedback is in range")]
pub(crate) fn status(mode: Mode, faults: StatusFaults, read_ns: u64) -> Observed {
    let feedback = Feedback {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
        temperature: Celsius::new(25.0).unwrap(),
    };
    let frame = drive::status(
        robstride::Drive::new(id(101), robstride::Model::Rs03),
        mode,
        faults,
        &feedback,
    )
    .unwrap();
    let Ok(Inbound::Status(status)) = decode(frame.id(), &frame.data()) else {
        unreachable_status()
    };
    Observed { status, read_ns }
}

#[expect(clippy::panic, reason = "test helper; a status always decodes as one")]
fn unreachable_status() -> ! {
    panic!("a status frame didn't decode as a status")
}

/// Drive 101 as a snapshot shows it: nothing seen yet.
pub(crate) fn quiet() -> DriveView {
    DriveView {
        device: id(101),
        limb: 0,
        observed: None,
        fresh_ns: None,
        fresh_status: None,
        answered: false,
        fault_seen: false,
        misses: 0,
        last_echo: None,
        stop: StopOutcome::None,
        reporting_off_sent: false,
    }
}

/// Drive 101 with its last status, fresh: the first after a command.
pub(crate) fn seen(observed: Observed) -> DriveView {
    DriveView {
        observed: Some(observed),
        fresh_ns: Some(observed.read_ns),
        fresh_status: Some(observed),
        fault_seen: !observed.status.header.faults.is_empty(),
        ..quiet()
    }
}

/// `view` with an echo of `kind` read at `read_ns`.
pub(crate) fn echoed(view: DriveView, kind: EchoKind, read_ns: u64) -> DriveView {
    DriveView {
        last_echo: Some(EchoSeen { kind, read_ns }),
        ..view
    }
}
