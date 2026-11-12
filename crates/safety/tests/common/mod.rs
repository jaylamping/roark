//! Shared helpers: a small skeleton fixture (never the live skeleton, testing.md rule 3) and drive views as the bus
//! layer publishes them ([`bus::replay`]).

use std::sync::LazyLock;

use can::{DriveView, EchoSeen, LimbState, LimbView, ModeSeen, Observed, Snapshot, StopOutcome};
use robstride::{
    Celsius, DeviceId, EchoKind, Feedback, Inbound, Mode, NewtonMeters, RadPerSec, Radians,
    StatusFaults, decode, drive,
};
use safety::Seen;
use skeleton::{BusName, Joint, Skeleton};

pub(crate) mod bus;
pub(crate) mod enable;
pub(crate) mod preflight;

/// One arm on `bus0`, and `bus1` with no joints. `arm_joint_one` is fully set (direction, zero and hard limits too); `arm_joint_two` leaves its
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
    driver: mcp251xfd
    adapter_serial: null
  bus1:
    bitrate_bps: 1000000
    sample_point: 0.75
    driver: mcp251xfd
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
pub(crate) fn status(mode: Mode, faults: StatusFaults, read_ns: u64) -> Observed {
    status_of(id(101), mode, faults, read_ns)
}

/// [`status`], from drive `device`.
#[expect(clippy::unwrap_used, reason = "test helper; the feedback is in range")]
pub(crate) fn status_of(
    device: DeviceId,
    mode: Mode,
    faults: StatusFaults,
    read_ns: u64,
) -> Observed {
    let feedback = Feedback {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
        temperature: Celsius::new(25.0).unwrap(),
    };
    let frame = drive::status(
        robstride::Drive::new(device, robstride::Model::Rs03),
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
        mode: None,
        out_of_reset: None,
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

/// The drive of `observed` with it as its last status, fresh: the first after a command.
pub(crate) fn seen(observed: Observed) -> DriveView {
    DriveView {
        device: observed.status.header.device,
        observed: Some(observed),
        mode: Some(ModeSeen {
            mode: observed.status.header.mode,
            read_ns: observed.read_ns,
        }),
        fresh_ns: Some(observed.read_ns),
        fresh_status: Some(observed),
        fault_seen: !observed.status.header.faults.is_empty(),
        ..quiet()
    }
}

/// The drive of `observed` with it as its last status, read with no command outstanding: not fresh.
pub(crate) fn heard(observed: Observed) -> DriveView {
    DriveView {
        fresh_ns: None,
        fresh_status: None,
        ..seen(observed)
    }
}

/// `view` with an echo of `kind` read at `read_ns`.
pub(crate) fn echoed(view: DriveView, kind: EchoKind, read_ns: u64) -> DriveView {
    DriveView {
        last_echo: Some(EchoSeen { kind, read_ns }),
        ..view
    }
}

/// The fixture's bus `n`: `bus0` holds every wired joint, `bus1` none.
#[expect(clippy::unwrap_used, reason = "test helper; the fixture has two buses")]
pub(crate) fn bus(n: usize) -> BusName {
    skeleton().buses.get(n).unwrap().name.clone()
}

/// `bus0`, which the fixture's wired joints are on.
pub(crate) static BUS0: LazyLock<BusName> = LazyLock::new(|| bus(0));

/// A limb as a snapshot shows it before anything is enabled: idle, never stopped or cleared.
pub(crate) const IDLE: LimbView = LimbView {
    state: LimbState::Idle,
    stop: None,
    generation: 0,
};

/// A snapshot the bus layer published, with the name of the bus it came from and the slot of the drive a test shows.
pub(crate) struct Shown {
    bus: BusName,
    snapshot: Snapshot,
    slot: usize,
}

impl Shown {
    /// The drive as preflight and the enable sequence are stepped with it: [`Seen::of`] over the snapshot.
    #[expect(
        clippy::unwrap_used,
        reason = "test helper; the replayed slot holds the drive"
    )]
    pub(crate) fn seen(&self) -> Seen<'_> {
        Seen::of(&self.bus, &self.snapshot, self.slot).unwrap()
    }
}

/// `view` as `bus0`'s snapshot shows it, its limb idle.
pub(crate) fn shown(view: &DriveView) -> Shown {
    on(&BUS0, view, &IDLE)
}

/// `view` as the snapshot of the bus named `bus` shows it, its limb `limb`.
pub(crate) fn on(bus: &BusName, view: &DriveView, limb: &LimbView) -> Shown {
    in_slot(bus, view, limb, 0)
}

/// [`on`], with the drive in slot `slot` of its bus.
pub(crate) fn in_slot(bus: &BusName, view: &DriveView, limb: &LimbView, slot: usize) -> Shown {
    Shown {
        bus: bus.clone(),
        snapshot: bus::replay(view, limb, slot),
        slot,
    }
}
