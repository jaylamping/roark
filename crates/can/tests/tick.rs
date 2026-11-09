//! The bus tick without a socket: frames in and out as values, time stepped by hand (testing.md rule 6). Replies,
//! freshness, faults, batch checks and configuration; the stop path is in `stop.rs`.

mod common;

use can::{
    BusError, BusState, BusTick, CommandBatch, ConfigError, MAX_DRIVES, SendKind, SendOutcome,
    StopReason, Timing, classify,
};
use common::{
    MS, PERIOD, at, batch, bus, deadline, error_frame, hold, id, record, report_frame, run_tick,
    status, status_frame,
};
use robstride::{Mode, StatusFault, encode};
use telemetry::Direction;

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
    // An Enable's missing reply isn't counted: Run may take 10 ms (PLAN.md item 2 Silence windows).
    assert_eq!(snap.counters.unanswered, 0);
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

/// Guards: safety - a firmware-version reply and a type-21 fault report carry fault state too; a fault report with only
/// warnings is not a fault (robstride decode: non-zero fault bytes mean faulted; PLAN.md item 6 Faults row).
#[test]
fn version_replies_and_fault_reports_latch_faults() {
    let mut bus = bus();
    // Drive 11's version reply (§4.1.4) in a status header with a fault bit set.
    let faulted = status_frame(
        11,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    let version = record(
        faulted.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    );
    // Type-21 reports from drive 12 (§4.1.8): warnings only, then a fault byte.
    let warning_only = record(0x1500_0CFD, [0, 0, 0, 0, 1, 0, 0, 0], Direction::TxOther);
    let fault = record(0x1500_0CFD, [1, 0, 0, 0, 0, 0, 0, 0], Direction::TxOther);
    run_tick(&mut bus, 0, None, &[(MS, version), (MS, warning_only)]);
    let snap = bus.end(deadline(0));
    assert_eq!(
        (at(&snap, 0).fault_seen, at(&snap, 1).fault_seen),
        (true, false)
    );
    run_tick(&mut bus, 1, None, &[(MS, fault)]);
    assert!(at(&bus.end(deadline(1)), 1).fault_seen);
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

/// Guards: protocol - frames that aren't this bus's drives are counted, not mistaken for them: another bus's drive,
/// another program sending host frames (our host byte, another host byte, or a type we never send), undecodable frames
/// (PLAN.md item 3 "only the realtime process transmits").
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
            // Enable to drive 11 from host 0xFE, and a type-22 save: both only another sender makes.
            (MS, record(0x0300_FE0B, [0; 8], Direction::Rx)),
            (MS, record(0x1600_FD0B, [0; 8], Direction::Rx)),
        ],
    );
    let c = bus.end(PERIOD * 6 / 10).counters;
    assert_eq!((c.unexpected, c.foreign_host, c.undecodable), (1, 3, 1));
}

/// Guards: number - the drive table is fixed-size; a bus with more drives than it holds is refused at startup, never
/// truncated (rust.md section 6).
#[test]
fn too_many_drives_is_refused() {
    let ids: Vec<_> = (1..=u8::try_from(MAX_DRIVES + 1).unwrap_or(u8::MAX))
        .map(id)
        .collect();
    assert_eq!(
        BusTick::new(&ids, Timing::at_hz(250)).err(),
        Some(ConfigError::TooManyDrives(MAX_DRIVES + 1))
    );
    assert!(BusTick::new(&ids[..MAX_DRIVES], Timing::at_hz(250)).is_ok());
}

/// Guards: protocol - `unanswered` counts every command without a status by the collect deadline, whenever the late
/// status is read; a status after a drive has answered and with no new command is unsolicited, not a duplicate
/// (PLAN.md item 3).
#[test]
fn reply_counters_follow_the_deadline_not_the_read_order() {
    let mut bus = bus();
    let enable = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    run_tick(
        &mut bus,
        0,
        Some(&enable),
        &[(MS, status(11, Mode::Run)), (MS, status(12, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    // MIT to both: drive 11 on time, drive 12 just after the deadline but before the tick ends.
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(hold(11)), Some(hold(12))])),
        &[(MS, status(11, Mode::Run))],
    );
    bus.on_frame(deadline(1) + 1, &status(12, Mode::Run));
    let c = bus.end(deadline(1) + 1).counters;
    assert_eq!(
        (c.unanswered, c.late, c.duplicate, c.unsolicited),
        (1, 1, 0, 0)
    );
    // Tick 2 commands nothing; drive 11 still reports.
    run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[None, None])),
        &[(MS, status(11, Mode::Run))],
    );
    let c = bus.end(deadline(2)).counters;
    assert_eq!((c.duplicate, c.unsolicited), (0, 1));
}

/// Guards: safety - a batch is checked whole before any of it is sent: a frame aimed at another drive, a frame in a
/// slot with no drive, or motion to a drive never heard from sends nothing and stops the bus with the exact reason
/// (PLAN.md item 3, item 6 Silence row).
#[test]
fn a_bad_batch_sends_nothing_and_names_the_slot() {
    let rows = [
        (
            "wrong target in slot 1",
            [
                Some(encode::enable(id(11))),
                Some(encode::enable(id(11))),
                None,
            ],
            StopReason::BadBatch { slot: 1 },
        ),
        (
            "slot 2 has no drive",
            [
                Some(encode::enable(id(11))),
                None,
                Some(encode::enable(id(13))),
            ],
            StopReason::BadBatch { slot: 2 },
        ),
        (
            "motion to a drive never heard",
            [Some(hold(11)), None, None],
            StopReason::ExpiredFeedback { slot: 0 },
        ),
    ];
    for (name, frames, reason) in rows {
        let mut bus = bus();
        let sent = run_tick(&mut bus, 0, Some(&batch(0, &frames)), &[]);
        assert!(
            sent.iter().all(|(_, kind)| *kind != SendKind::Command),
            "{name}: {sent:?}"
        );
        assert_eq!(bus.end(deadline(0)).stop, Some(reason), "{name}");
    }
}

/// Guards: number - feedback exactly three periods old still carries motion; one nanosecond more stops (PLAN.md item 3:
/// three periods, 12 ms at 250 Hz).
#[test]
fn the_feedback_limit_is_three_periods_inclusive() {
    for (age, sends) in [(3 * PERIOD, true), (3 * PERIOD + 1, false)] {
        let mut bus = bus();
        let enable = batch(0, &[Some(encode::enable(id(11))), None]);
        run_tick(&mut bus, 0, Some(&enable), &[(0, status(11, Mode::Run))]);
        let _ = bus.end(deadline(0));
        // Tick 3 begins `age` after the status, read at 0.
        let mut hold_batch = CommandBatch::new(3, age + PERIOD);
        assert!(hold_batch.set(0, hold(11)));
        let list = bus.begin(3, age, age, Some(&hold_batch));
        let commands = list.iter().filter(|s| s.kind == SendKind::Command).count();
        assert_eq!(commands == 1, sends, "age {age}");
    }
}

/// Guards: safety - timing that breaks the tick's promises is refused at startup, never quietly replaced: no rate, a rate
/// whose three periods pass the drives' 50 ms timeout, or a stop window shorter than the post-Disable silence
/// (safety.md: invalid configuration is an error; PLAN.md item 3).
#[test]
fn timing_that_breaks_the_tick_is_refused() {
    let short_stop = Timing {
        stop_confirm_ns: 10 * MS,
        ..Timing::at_hz(250)
    };
    let rows = [
        (Timing::at_hz(0), Some("the period is zero")),
        (
            Timing::at_hz(50),
            Some(
                "the feedback limit must be at least a period and under the drives' 50 ms timeout",
            ),
        ),
        (
            short_stop,
            Some("the stop window must outlast the post-Disable silence"),
        ),
        (Timing::at_hz(100), None),
        (Timing::at_hz(250), None),
    ];
    for (timing, refused) in rows {
        assert_eq!(
            BusTick::new(&[id(11)], timing).err(),
            refused.map(ConfigError::Timing),
            "{timing:?}"
        );
    }
}

/// Guards: protocol - error frames are read by severity from the kernel's bits, and error-passive marks the bus
/// unhealthy (the recording's `valid`) until the controller reports error-active again (linux/can/error.h; logging.md
/// section 8.2).
#[test]
fn error_frames_are_classified_and_passive_marks_the_bus_unhealthy() {
    let rows = [
        (0x40, 0x00, BusError::BusOff),
        (0x44, 0x10, BusError::BusOff),
        (0x04, 0x20, BusError::ErrorPassive),
        (0x04, 0x11, BusError::ErrorPassive),
        (0x04, 0x01, BusError::RxOverflow),
        (0x04, 0x08, BusError::ErrorWarning),
        (0x04, 0x40, BusError::ErrorActive),
        (0x01, 0x00, BusError::TxTimeout),
        (0x08, 0x00, BusError::Other(0x08)),
    ];
    for (class, crtl, expected) in rows {
        assert_eq!(
            classify(class, &[0, crtl, 0, 0, 0, 0, 0, 0]),
            expected,
            "class {class:#x} crtl {crtl:#x}"
        );
    }
    let mut bus = bus();
    run_tick(&mut bus, 0, None, &[(MS, error_frame(0x04, 0x20))]);
    let snap = bus.end(deadline(0));
    assert_eq!(
        (snap.healthy, snap.state),
        (false, BusState::Idle),
        "passive doesn't stop the bus"
    );
    run_tick(&mut bus, 1, None, &[(MS, error_frame(0x04, 0x40))]);
    assert!(bus.end(deadline(1)).healthy);
}
