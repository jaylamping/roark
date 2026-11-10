//! Helpers shared by sim-drive's test files: frames to and from one simulated drive, with time passed in.

use std::time::{Duration, Instant};

use robstride::drive::{self, HostFrame};
use robstride::{DeviceId, Drive, Frame, Inbound, Mode, Model, decode, encode};
use sim_drive::SimDrive;

#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
pub(crate) fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

pub(crate) fn ms(n: u64) -> Duration {
    Duration::from_millis(n)
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
pub(crate) fn host(frame: Frame) -> HostFrame {
    drive::command(frame.id(), &frame.data()).unwrap().unwrap()
}

/// Every frame due by `now`, decoded as the host reads it.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
pub(crate) fn replies(sim: &mut SimDrive, now: Instant) -> Vec<Inbound> {
    std::iter::from_fn(|| sim.pop_due(now))
        .map(|f| decode(f.id(), &f.data()).unwrap())
        .collect()
}

pub(crate) fn mode_of(inbound: &Inbound) -> Option<Mode> {
    match inbound {
        Inbound::Status(s) | Inbound::Report(s) => Some(s.header.mode),
        _ => None,
    }
}

/// Send `frame` at `now` and return what is due straight away.
pub(crate) fn ask(sim: &mut SimDrive, now: Instant, frame: Frame) -> Vec<Inbound> {
    sim.receive(now, host(frame));
    replies(sim, now)
}

pub(crate) fn rs03(n: u8) -> Drive {
    Drive::new(id(n), Model::Rs03)
}

/// A neutral MIT command to drive `n`: it changes nothing, and its status reply shows the mode.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
pub(crate) fn neutral(n: u8) -> Frame {
    let zero = robstride::MitCommand {
        position: robstride::Radians::new(0.0).unwrap(),
        velocity: robstride::RadPerSec::new(0.0).unwrap(),
        kp: robstride::NmPerRad::new(0.0).unwrap(),
        kd: robstride::NmSecPerRad::new(0.0).unwrap(),
        torque: robstride::NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(rs03(n), &zero).unwrap()
}
