//! Helpers shared by the sim suite's test files: drives, commands, a session, and playing control's side of the rings.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusDrive, LimbState, Snapshot, StopReason};
use robstride::{
    DeviceId, Drive, Frame, MitCommand, Model, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec,
    Radians, encode,
};
use telemetry::{BusInfo, SessionInfo, SkeletonRef, Stage, TimestampSource};

/// Slow enough that the test thread, playing control, makes every tick on a loaded machine.
pub(crate) const HZ: u64 = 100;

#[expect(
    clippy::unwrap_used,
    reason = "test helper: IDs here are constants in range"
)]
pub(crate) fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

/// Drive `n` in limb `limb`.
pub(crate) fn drive(n: u8, limb: usize) -> BusDrive {
    BusDrive {
        device: id(n),
        limb,
    }
}

/// Every limb's state and stop.
pub(crate) fn limbs(snap: &Snapshot) -> Vec<(LimbState, Option<StopReason>)> {
    snap.limbs().map(|(_, l)| (l.state, l.stop)).collect()
}

/// A schedule that starts two periods from now, as the runtime's does.
pub(crate) fn soon() -> Instant {
    Instant::now() + Duration::from_nanos(2 * 1_000_000_000 / HZ)
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a hold command is in range"
)]
pub(crate) fn hold(n: u8) -> Frame {
    let command = MitCommand {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(5.0).unwrap(),
        kd: NmSecPerRad::new(0.5).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(Drive::new(id(n), Model::Rs03), &command).unwrap()
}

/// A session on the one bus `bus`.
pub(crate) fn info(bus: &str) -> SessionInfo {
    SessionInfo {
        git_revision: "test".to_owned(),
        operator: "sim-suite".to_owned(),
        stage: Stage::Vcan,
        skeleton: SkeletonRef {
            path: "inline".to_owned(),
            sha256: "00".repeat(32),
        },
        buses: vec![BusInfo {
            name: bus.to_owned(),
            bitrate: 1_000_000,
            timestamps: TimestampSource::Software,
            receive_filters: Vec::new(),
            error_filter: u32::MAX,
            adapter_firmware: None,
        }],
    }
}

/// The snapshot for the next tick, waiting at most a second.
pub(crate) fn next_snapshot(
    snapshots: &mut rtrb::Consumer<Snapshot>,
    end: Instant,
) -> Option<Snapshot> {
    while Instant::now() < end {
        if let Ok(s) = snapshots.pop() {
            return Some(s);
        }
        std::thread::yield_now();
    }
    None
}

/// Sets both stop flags when dropped, including while a failed assertion unwinds.
pub(crate) struct Shutdown<'a>(pub(crate) &'a AtomicBool, pub(crate) Arc<AtomicBool>);

impl Drop for Shutdown<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
        self.1.store(true, Ordering::Release);
    }
}
