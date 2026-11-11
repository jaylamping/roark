//! Drive views as the bus layer publishes them. A test describes the view it wants as a `DriveView` and its limb's as
//! a `LimbView`; [`replay`] feeds a `can::BusTick` the sends and frames that make them and hands back its snapshot, so
//! preflight and the enable sequence are only ever shown what a snapshot can hold, through `Seen::of`. A view no
//! sequence of frames makes fails the test that asks for it.

use can::{
    BusDrive, BusTick, CommandBatch, Direction, DriveView, EchoSeen, FrameRecord, LimbState,
    LimbView, ModeSeen, Observed, SendKind, SendOutcome, Snapshot, StopReason, Timing,
};
use robstride::drive::DriveFrame;
use robstride::{
    Celsius, DeviceId, Drive, EchoKind, Feedback, Frame, Mode, Model, NewtonMeters, Param,
    ParamValue, RadPerSec, Radians, Reporting, RunMode, StatusFaults, Write, encode,
};

/// The bus's rate: PLAN item 3's 250 Hz.
const TIMING: Timing = Timing::at_hz(250);

/// What feeds the tick, at one time.
enum Event {
    /// A tick whose batch carries this frame to the drive, taken by the socket.
    Send(Frame),
    /// A frame read from the socket.
    Read(FrameRecord),
    /// A tick that starts stopping the limb for this reason.
    Stop(StopReason),
}

/// `BusTick` and the next tick number.
struct Rig {
    bus: BusTick,
    tick: u64,
    slot: usize,
    limb: usize,
}

impl Rig {
    /// One tick at `now_ns`, its batch carrying `frame` to the drive if any. The socket takes the batch's frame and
    /// refuses a stop's Disables and reporting off, so no stop opens a reply of its own.
    fn tick(&mut self, now_ns: u64, frame: Option<Frame>) {
        let mut batch = CommandBatch::new(self.tick, now_ns + TIMING.period_ns);
        if let Some(frame) = frame {
            assert!(batch.set(self.slot, frame), "the drive's slot");
        }
        let list = self.bus.begin(self.tick, now_ns, now_ns, Some(&batch));
        for (index, send) in list.iter().enumerate() {
            let outcome = if send.kind == SendKind::Command {
                SendOutcome::Sent
            } else {
                SendOutcome::QueueFull
            };
            self.bus.sent(index, outcome, now_ns);
        }
        let _ = self.bus.end(now_ns);
        self.tick += 1;
    }

    /// Stop the limb for `reason` in a tick at `now_ns`: asked for, or another drive's fault read just before it.
    #[expect(clippy::panic, reason = "test helper; a row asks only for these stops")]
    fn stop(&mut self, reason: StopReason, now_ns: u64) {
        match reason {
            StopReason::Requested => self.bus.request_stop(),
            StopReason::LimbRequested => {
                assert_eq!(self.bus.stop_limb(self.limb), Ok(()), "the drive's limb");
            }
            StopReason::DriveFault { slot } if slot != self.slot => {
                self.bus.on_frame(now_ns, &fault_record(filler(slot)));
            }
            other => panic!("no replay for a stop by {other:?}"),
        }
        self.tick(now_ns, None);
    }
}

/// The drive in slot `n` that isn't the one shown: of the same limb, sent nothing.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; a bus has at most 16 slots"
)]
fn filler(n: usize) -> DeviceId {
    DeviceId::new(120 + u64::try_from(n).unwrap()).unwrap()
}

/// A drive frame as `vcan` delivers it: another local sender's.
fn read(id: u32, data: [u8; 8], direction: Direction) -> FrameRecord {
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

/// A status from `device` in `mode` with `faults`, at rest: the feedback every row's statuses carry.
fn resting(device: DeviceId, mode: Mode, faults: StatusFaults) -> DriveFrame {
    let feedback = Feedback {
        position: Radians::new(0.0).unwrap_or_else(|| unreachable_frame("zero")),
        velocity: RadPerSec::new(0.0).unwrap_or_else(|| unreachable_frame("zero")),
        torque: NewtonMeters::new(0.0).unwrap_or_else(|| unreachable_frame("zero")),
        temperature: Celsius::new(25.0).unwrap_or_else(|| unreachable_frame("25 C")),
    };
    robstride::drive::status(Drive::new(device, Model::Rs03), mode, faults, &feedback)
        .unwrap_or_else(|_| unreachable_frame("a resting status"))
}

fn status_record(observed: &Observed) -> FrameRecord {
    let header = observed.status.header;
    let frame = resting(header.device, header.mode, header.faults);
    read(frame.id(), frame.data(), Direction::TxOther)
}

/// A version reply from `device` in `mode`: a status's ID and the version bytes, as `crates/can/tests/fresh.rs`.
fn version_record(device: DeviceId, mode: Mode) -> FrameRecord {
    let frame = resting(device, mode, StatusFaults::default());
    read(
        frame.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    )
}

/// A fault report from `device` with a fault byte set (type 21).
fn fault_record(device: DeviceId) -> FrameRecord {
    let id = 0x1500_00FD | (u32::from(device.get()) << 8);
    read(id, [1, 0, 0, 0, 0, 0, 0, 0], Direction::TxOther)
}

/// This host's frame of `kind` to `device`, as the socket reads it back.
#[expect(
    clippy::panic,
    reason = "test helper; a batch carries only these kinds"
)]
fn echo_record(device: DeviceId, kind: EchoKind) -> FrameRecord {
    let frame = match kind {
        EchoKind::Enable => encode::enable(device),
        EchoKind::Disable => encode::disable(device),
        EchoKind::Reporting(Reporting::Off) => encode::active_reporting(device, Reporting::Off),
        EchoKind::ParamWrite {
            param: Param::RunMode,
            value: ParamValue::RunMode(RunMode::Mit),
        } => mit_mode(device),
        other => panic!("no batch carries an echo of {other:?}"),
    };
    read(frame.id(), frame.data(), Direction::TxEcho)
}

fn mit_mode(device: DeviceId) -> Frame {
    encode::param_write(&Write::mit_mode(Drive::new(device, Model::Rs03)))
}

#[expect(clippy::panic, reason = "test helper; the rows' frames encode")]
fn unreachable_frame(what: &str) -> ! {
    panic!("{what} didn't encode")
}

/// The snapshot a bus with `view`'s drive in slot `slot` publishes after the sends and frames that make `view` and
/// `limb`; its other slots hold other drives of the same limb, which nothing is sent to (one of them faults for a limb
/// stopped by another drive's fault). The view's fields the safety layer reads (device, limb, `observed`, `mode`,
/// `fresh_ns`, `fresh_status`, `fault_seen`, `last_echo`, and `out_of_reset` as below) and the limb's must come out as
/// asked; what else the frames set (the bus's own bookkeeping) is whatever they make it.
///
/// - The fresh status is the first status read after a command the socket took: the limb's Enable if the limb is
///   active, else the `run_mode` = MIT write a batch may carry, sent at the status's read time (or as a stopping limb
///   began stopping, if that is earlier). A later status in `observed` follows it; a status with no fresh one is read
///   with nothing outstanding. A `fresh_ns` with no `fresh_status` is a fresh status superseded by a later frame in
///   another mode: the last status, or a version reply.
/// - `mode` other than the last status's comes from a version reply read at its time, after that status.
/// - `out_of_reset`, when the view sets it, must come out as asked; a version reply in that mode is read at its time,
///   first, unless a frame above shows it. A view that leaves it `None` takes whatever the frames latch.
/// - `fault_seen` with no fault bits in a status read comes from a fault report, read last, so no send follows it.
/// - An active limb with no fresh status had its Enable sent after the last frame; a stopping limb's stop began at its
///   `since_ns` and a stopped one's after the last frame; a limb at generation `n` was stopped and cleared `n` times
///   before anything else. A stop's Disables are refused by the socket, so they open no reply.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the replayed slot holds the drive"
)]
pub(crate) fn replay(view: &DriveView, limb: &LimbView, slot: usize) -> Snapshot {
    let (mut rig, start) = cleared(view, limb, slot);
    let (events, last) = events(view, limb, start);
    for (at, _, event) in events {
        match event {
            Event::Send(frame) => rig.tick(at, Some(frame)),
            Event::Read(record) => rig.bus.on_frame(at, &record),
            Event::Stop(reason) => rig.stop(reason, at),
        }
    }
    let end = if limb.state == LimbState::Stopped {
        last + TIMING.stop_replies_ns()
    } else {
        last
    };
    let snapshot = rig.bus.end(end);
    let made = snapshot.drive(slot).unwrap();
    assert_eq!(
        read_by_safety(made),
        read_by_safety(view),
        "no frames make this view"
    );
    if view.out_of_reset.is_some() {
        assert_eq!(
            made.out_of_reset, view.out_of_reset,
            "no frames make this latch"
        );
    }
    assert_eq!(
        snapshot.limb(view.limb),
        Some(limb),
        "no frames make this limb"
    );
    snapshot
}

/// The fields of a view the safety layer reads.
type Read = (
    DeviceId,
    usize,
    Option<Observed>,
    Option<ModeSeen>,
    Option<u64>,
    Option<Observed>,
    bool,
    Option<EchoSeen>,
);

const fn read_by_safety(view: &DriveView) -> Read {
    (
        view.device,
        view.limb,
        view.observed,
        view.mode,
        view.fresh_ns,
        view.fresh_status,
        view.fault_seen,
        view.last_echo,
    )
}

/// The bus for `view` in slot `slot`, its limb stopped and cleared up to `limb`'s generation; and the time that took.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the bus and its clears are valid"
)]
fn cleared(view: &DriveView, limb: &LimbView, slot: usize) -> (Rig, u64) {
    let fault_slot = match limb.stop {
        Some(StopReason::DriveFault { slot: other }) if other != slot => Some(other),
        _ => None,
    };
    let drives: Vec<BusDrive> = (0..=slot.max(fault_slot.unwrap_or(0)))
        .map(|n| BusDrive {
            device: if n == slot { view.device } else { filler(n) },
            limb: view.limb,
        })
        .collect();
    let mut rig = Rig {
        bus: BusTick::new(&drives, TIMING).unwrap(),
        tick: 0,
        slot,
        limb: view.limb,
    };
    let mut start = 0;
    for _ in 0..limb.generation {
        rig.stop(StopReason::LimbRequested, start);
        start += TIMING.stop_replies_ns();
        let _ = rig.bus.end(start);
        rig.bus.rearm(view.limb, start).unwrap();
    }
    (rig, start)
}

/// The status read fresh: the view's, or one it no longer holds, superseded by the last status or a version reply in
/// another mode; the last status itself when that was read at the fresh time.
fn fresh(view: &DriveView) -> Option<Observed> {
    view.fresh_status.or_else(|| {
        let at = view.fresh_ns?;
        let observed = view.observed?;
        if observed.read_ns == at {
            return Some(observed);
        }
        let mode = if observed.status.header.mode == Mode::Run {
            Mode::Reset
        } else {
            Mode::Run
        };
        let other = resting(view.device, mode, StatusFaults::default());
        let Ok(robstride::Inbound::Status(status)) = robstride::decode(other.id(), &other.data())
        else {
            unreachable_frame("a status that decodes")
        };
        Some(Observed {
            status,
            read_ns: at,
        })
    })
}

/// What makes `view` and `limb` after `start`, in the order it is fed (time, then order within that time); and the
/// last time.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; a stopping or stopped limb has its stop"
)]
fn events(view: &DriveView, limb: &LimbView, start: u64) -> (Vec<(u64, u8, Event)>, u64) {
    let active = limb.state == LimbState::Active;
    let command = if active {
        encode::enable(view.device)
    } else {
        mit_mode(view.device)
    };
    let mut events = Vec::new();
    let mut last_status = None;
    let fresh = fresh(view);
    if let Some(fresh) = fresh {
        // Sent at the fresh status's read time, or when the limb began stopping if that came first: a stopping limb
        // takes no command.
        let sent = match limb.state {
            LimbState::Stopping { since_ns } => since_ns.min(fresh.read_ns),
            LimbState::Idle | LimbState::Active | LimbState::Stopped => fresh.read_ns,
        };
        events.push((sent, 0, Event::Send(command)));
        events.push((fresh.read_ns, 1, Event::Read(status_record(&fresh))));
        last_status = Some(fresh);
    }
    if let Some(observed) = view.observed
        && fresh != Some(observed)
    {
        events.push((observed.read_ns, 2, Event::Read(status_record(&observed))));
        last_status = Some(observed);
    }
    let header = last_status.map(|o| ModeSeen {
        mode: o.status.header.mode,
        read_ns: o.read_ns,
    });
    if let Some(mode) = view.mode
        && Some(mode) != header
    {
        let version = version_record(view.device, mode.mode);
        events.push((mode.read_ns, 3, Event::Read(version)));
    }
    // A latched mode out of Reset that no frame above shows was a version reply read before them at its time.
    if let Some(latched) = view.out_of_reset
        && Some(latched) != view.mode
        && Some(latched) != header
    {
        let version = version_record(view.device, latched.mode);
        events.push((latched.read_ns, 0, Event::Read(version)));
    }
    if let Some(echo) = view.last_echo {
        let record = echo_record(view.device, echo.kind);
        events.push((echo.read_ns, 1, Event::Read(record)));
    }
    if let LimbState::Stopping { since_ns } = limb.state {
        events.push((since_ns, 4, Event::Stop(limb.stop.unwrap())));
    }
    let last = events.iter().map(|(t, ..)| *t).max().unwrap_or(start);
    let faulted = [fresh, view.observed]
        .into_iter()
        .flatten()
        .any(|o| !o.status.header.faults.is_empty());
    if view.fault_seen && !faulted {
        events.push((last, 5, Event::Read(fault_record(view.device))));
    }
    if active && fresh.is_none() {
        events.push((last, 6, Event::Send(command)));
    }
    if limb.state == LimbState::Stopped {
        events.push((last, 7, Event::Stop(limb.stop.unwrap())));
    }
    events.sort_by_key(|(t, order, _)| (*t, *order));
    if let Some((first, ..)) = events.first() {
        assert!(*first >= start, "nothing is read before the limb's clears");
    }
    (events, last)
}
