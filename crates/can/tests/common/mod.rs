//! Helpers shared by the tick's test files: a two-drive bus at 250 Hz, frames as `vcan` delivers them, and one tick run
//! by hand.

use can::{
    BusDrive, BusTick, CommandBatch, LimbState, SendKind, SendOutcome, Snapshot, StopReason, Timing,
};
use robstride::drive::{self, DriveFrame};
use robstride::{
    DeviceId, Drive, Feedback, Frame, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, StatusFaults, encode,
};
use telemetry::{Direction, FrameRecord};

pub(crate) const MS: u64 = 1_000_000;
pub(crate) const PERIOD: u64 = 4 * MS;

#[expect(
    clippy::unwrap_used,
    reason = "test helper: IDs here are constants in range"
)]
pub(crate) fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

pub(crate) fn drive(n: u8) -> Drive {
    Drive::new(id(n), Model::Rs03)
}

/// A bus of two drives in one limb at 250 Hz. The IDs are arbitrary, outside the skeleton's (testing.md rule 3).
#[expect(clippy::unwrap_used, reason = "test helper: two drives fit")]
pub(crate) fn bus() -> BusTick {
    BusTick::new(&one_limb(&[id(101), id(102)]), Timing::at_hz(250)).unwrap()
}

/// `devices` all in limb 0.
pub(crate) fn one_limb(devices: &[DeviceId]) -> Vec<BusDrive> {
    devices
        .iter()
        .map(|&device| BusDrive { device, limb: 0 })
        .collect()
}

/// Limb 0's state, on a bus whose drives are all in limb 0.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: limb 0 exists on every test bus"
)]
pub(crate) fn state_of(snap: &Snapshot) -> LimbState {
    snap.limb(0).unwrap().state
}

/// Limb 0's stop, on a bus whose drives are all in limb 0.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: limb 0 exists on every test bus"
)]
pub(crate) fn stop_of(snap: &Snapshot) -> Option<StopReason> {
    snap.limb(0).unwrap().stop
}

pub(crate) fn record(id: u32, data: [u8; 8], direction: Direction) -> FrameRecord {
    FrameRecord {
        id,
        extended: true,
        error: false,
        remote: false,
        len: 8,
        data,
        stamp_ns: 0,
        direction,
    }
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a resting status is in range"
)]
pub(crate) fn status_frame(n: u8, mode: Mode, faults: StatusFaults) -> DriveFrame {
    let at_rest = Feedback {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
        temperature: robstride::Celsius::new(25.0).unwrap(),
    };
    drive::status(drive(n), mode, faults, &at_rest).unwrap()
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a resting report is in range"
)]
pub(crate) fn report_frame(n: u8, faults: StatusFaults) -> DriveFrame {
    let at_rest = Feedback {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
        temperature: robstride::Celsius::new(25.0).unwrap(),
    };
    drive::report(drive(n), Mode::Run, faults, &at_rest).unwrap()
}

/// Drive `n`'s status as `vcan` delivers it: another local sender's frame.
pub(crate) fn status(n: u8, mode: Mode) -> FrameRecord {
    let f = status_frame(n, mode, StatusFaults::default());
    record(f.id(), f.data(), Direction::TxOther)
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a hold command is in range"
)]
pub(crate) fn hold(n: u8) -> Frame {
    let command = MitCommand {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(10.0).unwrap(),
        kd: NmSecPerRad::new(1.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(drive(n), &command).unwrap()
}

/// Slot `slot`'s view in a snapshot.
#[expect(clippy::unwrap_used, reason = "test helper: the slots asked for exist")]
pub(crate) fn at(snap: &can::Snapshot, slot: usize) -> can::DriveView {
    *snap.drive(slot).unwrap()
}

/// A batch for `tick` with `frames` in drive order, valid for one period.
pub(crate) fn batch(tick: u64, frames: &[Option<Frame>]) -> CommandBatch {
    let mut b = CommandBatch::new(tick, (tick + 1) * PERIOD);
    for (slot, frame) in frames.iter().enumerate() {
        if let Some(frame) = frame {
            assert!(b.set(slot, *frame), "slot {slot} in range");
        }
    }
    b
}

/// Run one tick at its scheduled start: begin, report every send as taken by the socket, feed
/// `replies` as read at the given offsets. Returns what was sent, as (slot, kind); the caller ends the tick.
pub(crate) fn run_tick(
    bus: &mut BusTick,
    tick: u64,
    batch: Option<&CommandBatch>,
    replies: &[(u64, FrameRecord)],
) -> Vec<(usize, SendKind)> {
    let start = tick * PERIOD;
    let list = bus.begin(tick, start, start, batch);
    let sent: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
    for (index, _) in list.iter().enumerate() {
        bus.sent(index, SendOutcome::Sent, start);
    }
    for (offset, frame) in replies {
        bus.on_frame(start + offset, frame);
    }
    sent
}

/// Tick `tick`'s collect deadline.
pub(crate) fn deadline(tick: u64) -> u64 {
    tick * PERIOD + PERIOD * 6 / 10
}

/// An error frame with class bits `class` and controller byte `crtl` (linux/can/error.h).
pub(crate) fn error_frame(class: u32, crtl: u8) -> FrameRecord {
    let mut f = record(class, [0, crtl, 0, 0, 0, 0, 0, 0], Direction::Rx);
    f.error = true;
    f
}

/// Drive 101 in limb 0 and drive 102 in limb 1, at 250 Hz.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: two drives in two limbs fit"
)]
pub(crate) fn two_limbs() -> BusTick {
    let drives = [
        BusDrive {
            device: id(101),
            limb: 0,
        },
        BusDrive {
            device: id(102),
            limb: 1,
        },
    ];
    BusTick::new(&drives, Timing::at_hz(250)).unwrap()
}
