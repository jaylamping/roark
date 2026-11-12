//! Helpers shared by the sim suite's test files: drives, commands, a session, and playing control's side of the rings.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusDrive, LimbState, Snapshot, StopReason, Timing};
use robstride::{
    DeviceId, Drive, Frame, MitCommand, Model, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec,
    Radians, encode,
};
use telemetry::{SessionInfo, SkeletonRef, Stage};

/// Slow enough that the test thread, playing control, makes every tick on a loaded machine.
pub(crate) const HZ: u64 = 100;

/// The tick at `HZ`, with the send window stretched to the collect deadline: these tests check the loop, its recording
/// and what it does on a drive's word, not the wake budget, so a test thread that wakes a few milliseconds late on a
/// loaded runner is not a late wake (the tick tests cover that).
pub(crate) fn timing() -> Timing {
    let at_hz = Timing::at_hz(HZ);
    Timing {
        send_window_ns: at_hz.collect_ns,
        ..at_hz
    }
}

/// A bus interface as a skeleton describes one. The bus layer takes `vcan` as it is; the driver is one no real interface
/// has, so a test that forgot `ensure_vcan` is still refused on a real bus.
pub(crate) fn interface() -> can::InterfaceSpec {
    can::InterfaceSpec {
        bitrate_bps: 1_000_000,
        sample_point: 0.75,
        driver: "sim_only".to_owned(),
    }
}

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

/// A schedule that starts two periods from now, so the test thread is ready before tick 0.
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
        buses: vec![can::bus_info(bus, 1_000_000)],
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
