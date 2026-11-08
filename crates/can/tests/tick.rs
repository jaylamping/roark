//! The bus tick without a socket: frames in and out as values, time stepped by hand (testing.md rule 6).

use can::{
    BusError, BusState, BusTick, CommandBatch, MAX_DRIVES, SendKind, SendOutcome, StopOutcome,
    StopReason, Timing,
};
use robstride::drive::{self, DriveFrame};
use robstride::{
    DeviceId, Drive, Feedback, Frame, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, StatusFault, StatusFaults, encode,
};
use telemetry::{Direction, FrameRecord};

const MS: u64 = 1_000_000;
const PERIOD: u64 = 4 * MS;

#[expect(
    clippy::unwrap_used,
    reason = "test helper: IDs here are constants in range"
)]
fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

fn drive(n: u8) -> Drive {
    Drive::new(id(n), Model::Rs03)
}

/// A bus with drives 11 and 12 at 250 Hz.
#[expect(clippy::unwrap_used, reason = "test helper: two drives fit")]
fn bus() -> BusTick {
    BusTick::new(&[id(11), id(12)], Timing::at_hz(250)).unwrap()
}

fn record(id: u32, data: [u8; 8], direction: Direction) -> FrameRecord {
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
fn status_frame(n: u8, mode: Mode, faults: StatusFaults) -> DriveFrame {
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
fn report_frame(n: u8, faults: StatusFaults) -> DriveFrame {
    let at_rest = Feedback {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
        temperature: robstride::Celsius::new(25.0).unwrap(),
    };
    drive::report(drive(n), Mode::Run, faults, &at_rest).unwrap()
}

/// Drive `n`'s status as `vcan` delivers it: another local sender's frame.
fn status(n: u8, mode: Mode) -> FrameRecord {
    let f = status_frame(n, mode, StatusFaults::default());
    record(f.id(), f.data(), Direction::TxOther)
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a hold command is in range"
)]
fn hold(n: u8) -> Frame {
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
fn at(snap: &can::Snapshot, slot: usize) -> can::DriveView {
    *snap.drive(slot).unwrap()
}

/// A batch for `tick` with `frames` in drive order, valid for one period.
fn batch(tick: u64, frames: &[Option<Frame>]) -> CommandBatch {
    let mut b = CommandBatch::new(tick, (tick + 1) * PERIOD);
    for (slot, frame) in frames.iter().enumerate() {
        if let Some(frame) = frame {
            assert!(b.set(slot, *frame), "slot {slot} in range");
        }
    }
    b
}

/// Run one tick at its scheduled start: begin, report every send as taken by the socket, feed
/// `replies` as read at the given offsets, and end at the collect deadline. Returns what was sent, as (slot, kind).
fn run_tick(
    bus: &mut BusTick,
    tick: u64,
    batch: Option<&CommandBatch>,
    replies: &[(u64, FrameRecord)],
) -> Vec<(usize, SendKind)> {
    let start = tick * PERIOD;
    let list = bus.begin(tick, start, start, batch);
    let sent: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
    for (index, _) in list.iter().enumerate() {
        bus.sent(index, SendOutcome::Sent);
    }
    for (offset, frame) in replies {
        bus.on_frame(start + offset, frame);
    }
    sent
}

/// Guards: protocol - a status read after a drive's submitted command is its fresh answer; before, it's not
/// (PLAN.md item 3, can.md section 2 "liveness comes from replies to commands").
#[test]
fn a_status_after_the_send_is_fresh_and_one_before_it_is_not() {
    let mut bus = bus();
    let b = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    // Drive 12's status was queued before the send (drained first), drive 11's arrives after it.
    bus.on_frame(0, &status(12, Mode::Reset));
    run_tick(&mut bus, 0, Some(&b), &[(MS, status(11, Mode::Run))]);
    let snap = bus.end(PERIOD * 6 / 10);

    let d11 = at(&snap, 0);
    assert_eq!((d11.answered, d11.fresh_ns), (true, Some(MS)));
    assert_eq!(d11.observed.map(|o| o.status.header.mode), Some(Mode::Run));
    let d12 = at(&snap, 1);
    assert_eq!((d12.answered, d12.fresh_ns), (false, None));
    assert_eq!(
        d12.observed.map(|o| o.status.header.mode),
        Some(Mode::Reset),
        "seen, but not an answer"
    );
    assert_eq!(snap.counters.unanswered, 1);
}

/// Guards: protocol - a status for a command the socket never took can't refresh liveness (transmit outcomes feed
/// back, can.md section 2).
#[test]
fn a_command_that_was_not_sent_cannot_be_answered() {
    let mut bus = bus();
    let b = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    let list = bus.begin(0, 0, 0, Some(&b));
    assert_eq!(list.len(), 2);
    bus.sent(0, SendOutcome::Sent);
    bus.sent(1, SendOutcome::QueueFull);
    bus.on_frame(MS, &status(11, Mode::Run));
    bus.on_frame(MS, &status(12, Mode::Run));
    let snap = bus.end(PERIOD * 6 / 10);

    assert!(at(&snap, 0).answered);
    assert_eq!(at(&snap, 1).fresh_ns, None);
    assert_eq!(
        (snap.counters.tx_dropped, snap.counters.unsolicited),
        (1, 1)
    );
}

/// Guards: protocol - one status per command: a second is a duplicate, and a status after the collect deadline is a
/// late answer; neither is a fresh reply for this tick (PLAN.md item 3).
#[test]
fn duplicates_and_late_answers_are_counted() {
    let mut bus = bus();
    let b = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    let deadline = PERIOD * 6 / 10;
    run_tick(
        &mut bus,
        0,
        Some(&b),
        &[(MS, status(11, Mode::Run)), (MS + 1, status(11, Mode::Run))],
    );
    bus.on_frame(deadline + 1, &status(12, Mode::Run));
    let snap = bus.end(deadline + 1);

    assert_eq!(snap.counters.duplicate, 1);
    assert_eq!(snap.counters.late, 1);
    assert!(!at(&snap, 1).answered, "after the deadline");
    assert_eq!(
        at(&snap, 1).fresh_ns,
        Some(deadline + 1),
        "still fresh evidence the drive is there"
    );
}

/// Guards: protocol - a reply delayed past the next command can't be told from the new one's answer (no sequence
/// numbers); it counts as the drive being alive and reporting its state then, never as more (busloop design, Sol and
/// Astra).
#[test]
fn a_reply_delayed_across_ticks_is_freshness_not_acknowledgement() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(11))), None])),
        &[],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    // The enable's Run reply comes 9.4 ms later, after tick 2's command went out.
    run_tick(&mut bus, 1, Some(&batch(1, &[None, None])), &[]);
    let snap1 = bus.end(PERIOD + PERIOD * 6 / 10);
    assert!(!at(&snap1, 0).answered);
    run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[Some(encode::enable(id(11))), None])),
        &[(1_400_000, status(11, Mode::Run))],
    );
    let snap2 = bus.end(2 * PERIOD + PERIOD * 6 / 10);
    assert!(at(&snap2, 0).answered);
    assert_eq!(at(&snap2, 0).fresh_ns, Some(2 * PERIOD + 1_400_000));
}

/// Guards: safety - fault bits reach the snapshot from any frame a drive sends, answer or not (PLAN.md item 6 Faults
/// row).
#[test]
fn a_fault_is_seen_even_when_the_frame_is_not_an_answer() {
    let mut bus = bus();
    let faulted = status_frame(
        12,
        Mode::Run,
        [StatusFault::Overtemperature].into_iter().collect(),
    );
    // Unsolicited: no command was sent to drive 12.
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[None, None])),
        &[(MS, record(faulted.id(), faulted.data(), Direction::TxOther))],
    );
    let snap = bus.end(PERIOD * 6 / 10);
    assert!(at(&snap, 1).fault_seen);
    // Sticky: a clean status later doesn't clear it.
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[None, None])),
        &[(MS, status(12, Mode::Run))],
    );
    assert!(at(&bus.end(PERIOD + PERIOD * 6 / 10), 1).fault_seen);
    // An active report (type 24) carries fault bits too.
    let report = report_frame(11, [StatusFault::Undervoltage].into_iter().collect());
    run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[None, None])),
        &[(MS, record(report.id(), report.data(), Direction::TxOther))],
    );
    assert!(at(&bus.end(2 * PERIOD + PERIOD * 6 / 10), 0).fault_seen);
}

/// Guards: safety - a hung control thread lets the drives time out: only a fresh batch is sent, and two ticks without
/// one stop the bus (PLAN.md item 3).
#[test]
fn a_stale_batch_is_never_sent_and_two_silent_ticks_stop_the_bus() {
    let mut bus = bus();
    let enable = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    run_tick(&mut bus, 0, Some(&enable), &[]);
    let _ = bus.end(PERIOD * 6 / 10);

    // Tick 1 is handed tick 0's batch again: nothing goes out.
    assert_eq!(run_tick(&mut bus, 1, Some(&enable), &[]), []);
    assert_eq!(bus.end(PERIOD + PERIOD * 6 / 10).counters.stale_ticks, 1);
    // Tick 2: still nothing fresh, so the bus stops: Disable to each drive, then reporting off.
    let sent = run_tick(&mut bus, 2, None, &[]);
    assert_eq!(
        sent,
        [
            (0, SendKind::Disable),
            (1, SendKind::Disable),
            (0, SendKind::ReportingOff),
            (1, SendKind::ReportingOff)
        ]
    );
    let snap = bus.end(2 * PERIOD + PERIOD * 6 / 10);
    assert!(matches!(snap.state, BusState::Stopping { .. }));
    assert_eq!(snap.stop, Some(StopReason::ControlSilent));
}

/// Guards: safety - an idle bus (nothing enabled since start) isn't stopped for having no batches (PLAN.md item 3 stops
/// "its limbs", and none is running).
#[test]
fn an_idle_bus_sends_nothing_without_batches() {
    let mut bus = bus();
    for tick in 0..5 {
        assert_eq!(run_tick(&mut bus, tick, None, &[]), []);
        assert_eq!(
            bus.end(tick * PERIOD + PERIOD * 6 / 10).state,
            BusState::Idle
        );
    }
}

/// Guards: safety - a stop is confirmed only by a Reset-mode status read after a submitted Disable; an old Run reply
/// can't confirm it, and an unconfirmed drive gets Disable again (PLAN.md item 2 Stop).
#[test]
fn only_reset_after_disable_confirms_a_stop() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(
            0,
            &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
        )),
        &[],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    bus.request_stop();
    // Drive 11 answers its Disable in Reset; drive 12 sends a late Run status.
    run_tick(
        &mut bus,
        1,
        None,
        &[(MS, status(11, Mode::Reset)), (MS, status(12, Mode::Run))],
    );
    let snap = bus.end(PERIOD + PERIOD * 6 / 10);
    assert_eq!(at(&snap, 0).stop, StopOutcome::Confirmed);
    assert_eq!(at(&snap, 1).stop, StopOutcome::Sent);
    // Next tick only the unconfirmed drive gets Disable again.
    assert_eq!(run_tick(&mut bus, 2, None, &[]), [(1, SendKind::Disable)]);
    let _ = bus.end(2 * PERIOD + PERIOD * 6 / 10);
    // 100 ms after the stop began, it's over, with drive 12 recorded as unconfirmed.
    let mut tick = 3;
    let snap = loop {
        run_tick(&mut bus, tick, None, &[]);
        let snap = bus.end(tick * PERIOD + PERIOD * 6 / 10);
        if snap.state == BusState::Stopped || tick > 40 {
            break snap;
        }
        tick += 1;
    };
    assert_eq!(snap.state, BusState::Stopped);
    assert!(
        tick * PERIOD >= 100 * MS,
        "stopped no earlier than 100 ms after the stop"
    );
    assert_eq!(at(&snap, 1).stop, StopOutcome::Sent);
    // Stopped is latched: batches are refused.
    assert_eq!(
        run_tick(
            &mut bus,
            tick + 1,
            Some(&batch(tick + 1, &[Some(hold(11)), None])),
            &[]
        ),
        []
    );
}

/// Guards: safety - motion with expired feedback is never sent: an MIT frame for a drive whose last fresh status is
/// older than 12 ms is refused and stops the bus (PLAN.md item 3 and item 6 Silence row).
#[test]
fn motion_with_expired_feedback_stops_instead_of_sending() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(11))), None])),
        &[(MS, status(11, Mode::Run))],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    // MIT at tick 1 is fine: feedback is 3 ms old.
    assert_eq!(
        run_tick(&mut bus, 1, Some(&batch(1, &[Some(hold(11)), None])), &[]),
        [(0, SendKind::Command)]
    );
    let _ = bus.end(PERIOD + PERIOD * 6 / 10);
    // No answer since: at tick 4 (16 ms) the feedback is 15 ms old.
    for tick in 2..4 {
        run_tick(&mut bus, tick, Some(&batch(tick, &[None, None])), &[]);
        let _ = bus.end(tick * PERIOD + PERIOD * 6 / 10);
    }
    let sent = run_tick(&mut bus, 4, Some(&batch(4, &[Some(hold(11)), None])), &[]);
    assert!(
        sent.iter().all(|(_, kind)| *kind != SendKind::Command),
        "{sent:?}"
    );
    assert_eq!(
        bus.end(4 * PERIOD + PERIOD * 6 / 10).stop,
        Some(StopReason::ExpiredFeedback { slot: 0 })
    );
}

/// Guards: safety - a thread that wakes past its send window stops at once instead of sending (PLAN.md item 3).
#[test]
fn a_late_wake_stops_the_bus() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(11))), None])),
        &[],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    // Tick 5 was due at 20 ms; the thread wakes at 33 ms with a fresh batch.
    let list = bus.begin(
        5,
        33 * MS,
        5 * PERIOD,
        Some(&batch(5, &[Some(hold(11)), None])),
    );
    assert!(list.iter().all(|s| s.kind != SendKind::Command));
    let snap = bus.end(34 * MS);
    assert_eq!(snap.stop, Some(StopReason::LateWake));
    assert_eq!(snap.counters.missed_deadlines, 1);
}

/// Guards: safety - bus-off is latched on the first error frame and nothing later clears it (PLAN.md item 3, item 6
/// Bus-off row).
#[test]
fn bus_off_latches_stopped() {
    let mut bus = bus();
    // An error frame: CAN_ERR_FLAG with the bus-off class bit (linux/can/error.h CAN_ERR_BUSOFF 0x40).
    let mut off = record(0x40, [0; 8], Direction::Rx);
    off.error = true;
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(11))), None])),
        &[(MS, off)],
    );
    let snap = bus.end(PERIOD * 6 / 10);
    assert_eq!(snap.state, BusState::Stopped);
    assert_eq!(snap.stop, Some(StopReason::Bus(BusError::BusOff)));
    // The adapter comes back and drives answer; the bus stays stopped and sends nothing.
    assert_eq!(
        run_tick(
            &mut bus,
            1,
            Some(&batch(1, &[Some(encode::enable(id(11))), None])),
            &[(MS, status(11, Mode::Run))]
        ),
        []
    );
    assert_eq!(bus.end(PERIOD + PERIOD * 6 / 10).state, BusState::Stopped);
}

/// Guards: protocol - frames that aren't this bus's drives are counted, not mistaken for them: another bus's drive,
/// another program sending host frames, undecodable frames (PLAN.md item 3 "only the realtime process transmits").
#[test]
fn foreign_frames_are_counted() {
    let mut bus = bus();
    let other_bus = status(21, Mode::Run);
    let foreign_host = encode::enable(id(11));
    run_tick(
        &mut bus,
        0,
        None,
        &[
            (MS, other_bus),
            (
                MS,
                record(foreign_host.id(), foreign_host.data(), Direction::TxOther),
            ),
            (MS, record(0x1F00_0000, [0; 8], Direction::Rx)),
        ],
    );
    let c = bus.end(PERIOD * 6 / 10).counters;
    assert_eq!((c.unexpected, c.foreign_host, c.undecodable), (1, 1, 1));
}

/// Guards: number - the drive table is fixed-size; a bus with more drives than it holds is refused at startup, never
/// truncated (rust.md section 6).
#[test]
fn too_many_drives_is_refused() {
    let ids: Vec<_> = (1..=u8::try_from(MAX_DRIVES + 1).unwrap_or(u8::MAX))
        .map(id)
        .collect();
    assert!(BusTick::new(&ids, Timing::at_hz(250)).is_err());
    assert!(BusTick::new(&ids[..MAX_DRIVES], Timing::at_hz(250)).is_ok());
}
