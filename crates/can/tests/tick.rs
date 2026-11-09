//! The bus tick without a socket: frames in and out as values, time stepped by hand (testing.md rule 6). Replies,
//! freshness, faults, batch checks and configuration; the stop path is in `stop.rs`.

mod common;

use can::{
    BusError, BusTick, CommandBatch, ConfigError, DRIVE_TIMEOUT_NS, LimbState, MAX_DRIVES,
    SendKind, SendOutcome, StopOutcome, StopReason, Timing, TimingError, classify,
};
use common::{
    MS, PERIOD, at, batch, bus, deadline, drive, error_frame, hold, id, one_limb, record,
    report_frame, run_tick, state_of, status, status_frame, stop_of,
};
use robstride::encode::{self, Reporting};
use robstride::{Mode, Param, StatusFault, Write};
use telemetry::Direction;

/// Guards: protocol - a status read after a drive's submitted command is its fresh answer; before, it's not
/// (PLAN.md item 3, can.md section 2 "liveness comes from replies to commands").
#[test]
fn a_status_after_the_send_is_fresh_and_one_before_it_is_not() {
    let mut bus = bus();
    let b = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    // Drive 102's status was queued before the send (drained first), drive 101's arrives after it.
    bus.on_frame(0, &status(102, Mode::Reset));
    run_tick(&mut bus, 0, Some(&b), &[(MS, status(101, Mode::Run))]);
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

    // An active report (type 24) after a command is seen but answers nothing: liveness comes from replies.
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[None, Some(encode::enable(id(102)))])),
        &[(MS, report(102))],
    );
    let d12 = at(&bus.end(deadline(1)), 1);
    assert_eq!((d12.answered, d12.fresh_ns), (false, None));
    assert_eq!(d12.observed.map(|o| o.read_ns), Some(PERIOD + MS));
}

/// Drive `n`'s active report as `vcan` delivers it.
fn report(n: u8) -> telemetry::FrameRecord {
    let f = report_frame(n, robstride::StatusFaults::default());
    record(f.id(), f.data(), Direction::TxOther)
}

/// Guards: protocol - a send the socket never took (queue full, write failed, window passed) opens no status window: a
/// status after it can't refresh liveness, and a stop's refused Disable can't be confirmed (transmit outcomes feed
/// back, can.md section 2).
#[test]
fn a_send_the_socket_did_not_take_cannot_be_answered() {
    let rows = [
        (SendOutcome::QueueFull, (1, 0)),
        (SendOutcome::Failed, (1, 0)),
        (SendOutcome::Expired, (0, 1)),
    ];
    for (outcome, (dropped, expired)) in rows {
        let mut bus = bus();
        let b = batch(
            0,
            &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
        );
        let list = bus.begin(0, 0, 0, Some(&b));
        assert_eq!(list.len(), 2);
        bus.sent(0, SendOutcome::Sent, 0);
        bus.sent(1, outcome, 0);
        bus.on_frame(MS, &status(101, Mode::Run));
        bus.on_frame(MS, &status(102, Mode::Run));
        let snap = bus.end(deadline(0));
        assert!(at(&snap, 0).answered, "{outcome:?}");
        assert_eq!(
            (at(&snap, 1).answered, at(&snap, 1).fresh_ns),
            (false, None),
            "{outcome:?}"
        );
        let c = snap.counters;
        assert_eq!(
            (c.tx_dropped, c.tx_expired, c.unsolicited),
            (dropped, expired, 1),
            "{outcome:?}"
        );
        // A stop's Disable the socket didn't take stays never sent, and a Reset read after it confirms nothing.
        bus.request_stop();
        let list = bus.begin(1, PERIOD, PERIOD, None);
        assert_eq!(list.len(), 2);
        bus.sent(0, SendOutcome::Sent, PERIOD);
        bus.sent(1, outcome, PERIOD);
        bus.on_frame(PERIOD + MS, &status(101, Mode::Reset));
        bus.on_frame(PERIOD + MS, &status(102, Mode::Reset));
        let snap = bus.end(deadline(1));
        assert_eq!(
            (at(&snap, 0).stop, at(&snap, 1).stop),
            (StopOutcome::Confirmed, StopOutcome::NeverSent),
            "{outcome:?}"
        );
    }
}

/// Guards: safety - only a command expires with the send window: a Disable goes out late rather than not at all, whether
/// control's batch or a stop planned it, and so does a stop's reporting off (can.md section 2 Every frame has a
/// deadline).
#[test]
fn a_disable_never_expires_whoever_planned_it() {
    let mut bus = bus();
    let b = batch(
        0,
        &[
            Some(encode::enable(id(101))),
            Some(encode::disable(id(102))),
        ],
    );
    let list = bus.begin(0, 0, 0, Some(&b));
    let expiry: Vec<_> = list.iter().map(|s| (s.kind, s.expires)).collect();
    assert_eq!(
        expiry,
        [(SendKind::Command, true), (SendKind::Command, false)]
    );
    for index in 0..list.len() {
        bus.sent(index, SendOutcome::Sent, 0);
    }
    bus.on_frame(MS, &status(101, Mode::Reset));
    bus.on_frame(MS, &status(102, Mode::Reset));
    let _ = bus.end(deadline(0));
    // A stop: Disables now; reporting off once each confirmed drive's silence is over.
    bus.request_stop();
    let list = bus.begin(1, PERIOD, PERIOD, None);
    assert!(
        list.iter()
            .all(|s| s.kind == SendKind::Disable && !s.expires)
    );
    for index in 0..list.len() {
        bus.sent(index, SendOutcome::Sent, PERIOD);
    }
    bus.on_frame(PERIOD + MS, &status(101, Mode::Reset));
    let _ = bus.end(deadline(1));
    let later = 15 * PERIOD;
    let list = bus.begin(15, later, later, None);
    let sends: Vec<_> = list.iter().map(|s| (s.slot, s.kind, s.expires)).collect();
    assert_eq!(
        sends,
        [
            (1, SendKind::Disable, false),
            (0, SendKind::ReportingOff, false)
        ]
    );
}

/// Guards: protocol - one status per command: a second is a duplicate, and a status after the collect deadline is a
/// late answer; neither is a fresh reply for this tick (PLAN.md item 3).
#[test]
fn duplicates_and_late_answers_are_counted() {
    let mut bus = bus();
    let b = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    let deadline = PERIOD * 6 / 10;
    run_tick(
        &mut bus,
        0,
        Some(&b),
        &[
            (MS, status(101, Mode::Run)),
            (MS + 1, status(101, Mode::Run)),
        ],
    );
    bus.on_frame(deadline + 1, &status(102, Mode::Run));
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
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
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
        Some(&batch(2, &[Some(encode::enable(id(101))), None])),
        &[(1_400_000, status(101, Mode::Run))],
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
        102,
        Mode::Run,
        [StatusFault::Overtemperature].into_iter().collect(),
    );
    // Unsolicited: no command was sent to drive 102.
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
        &[(MS, status(102, Mode::Run))],
    );
    assert!(at(&bus.end(PERIOD + PERIOD * 6 / 10), 1).fault_seen);
    // An active report (type 24) carries fault bits too.
    let report = report_frame(101, [StatusFault::Undervoltage].into_iter().collect());
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
    // Drive 101's version reply (§4.1.4) in a status header with a fault bit set.
    let faulted = status_frame(
        101,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    let version = record(
        faulted.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    );
    // Type-21 reports from drive 102 (§4.1.8): warnings only, then a fault byte.
    let warning_only = record(0x1500_66FD, [0, 0, 0, 0, 1, 0, 0, 0], Direction::TxOther);
    let fault = record(0x1500_66FD, [1, 0, 0, 0, 0, 0, 0, 0], Direction::TxOther);
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
            state_of(&bus.end(tick * PERIOD + PERIOD * 6 / 10)),
            LimbState::Idle
        );
    }
}

/// Guards: safety - motion with expired feedback is never sent: an MIT frame for a drive whose last fresh status is
/// older than 12 ms is refused and stops that drive's limb (PLAN.md item 3 and item 6 Silence row).
#[test]
fn motion_with_expired_feedback_stops_instead_of_sending() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
        &[(MS, status(101, Mode::Run))],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    // MIT at tick 1 is fine: feedback is 3 ms old.
    assert_eq!(
        run_tick(&mut bus, 1, Some(&batch(1, &[Some(hold(101)), None])), &[]),
        [(0, SendKind::Command)]
    );
    let _ = bus.end(PERIOD + PERIOD * 6 / 10);
    // No answer since: at tick 4 (16 ms) the feedback is 15 ms old.
    for tick in 2..4 {
        run_tick(&mut bus, tick, Some(&batch(tick, &[None, None])), &[]);
        let _ = bus.end(tick * PERIOD + PERIOD * 6 / 10);
    }
    let sent = run_tick(&mut bus, 4, Some(&batch(4, &[Some(hold(101)), None])), &[]);
    assert!(
        sent.iter().all(|(_, kind)| *kind != SendKind::Command),
        "{sent:?}"
    );
    assert_eq!(
        stop_of(&bus.end(4 * PERIOD + PERIOD * 6 / 10)),
        Some(StopReason::ExpiredFeedback { slot: 0 })
    );
}

/// Guards: protocol - frames that aren't this bus's drives are counted, not mistaken for them: another bus's drive,
/// another program sending host frames (our host byte, another host byte, or a type we never send), undecodable frames
/// (PLAN.md item 3 "only the realtime process transmits").
#[test]
fn foreign_frames_are_counted() {
    let mut bus = bus();
    let other_bus = status(104, Mode::Run);
    let foreign_host = encode::enable(id(101));
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
            // Enable to drive 101 from host 0xFE, and a type-22 save: both only another sender makes.
            (MS, record(0x0300_FE65, [0; 8], Direction::Rx)),
            (MS, record(0x1600_FD65, [0; 8], Direction::Rx)),
        ],
    );
    let c = bus.end(PERIOD * 6 / 10).counters;
    assert_eq!((c.unexpected, c.foreign_host, c.undecodable), (1, 3, 1));
}

/// Guards: number - the drive table is fixed-size; a bus with more drives than it holds is refused at startup, never
/// truncated (rust.md section 6).
#[test]
fn too_many_drives_is_refused() {
    let ids: Vec<_> = (101..=100 + u8::try_from(MAX_DRIVES + 1).unwrap_or(u8::MAX))
        .map(id)
        .collect();
    assert_eq!(
        BusTick::new(&one_limb(&ids), Timing::at_hz(250)).err(),
        Some(ConfigError::TooManyDrives(MAX_DRIVES + 1))
    );
    // A full table holds every drive, in slot order.
    let mut full = BusTick::new(&one_limb(&ids[..MAX_DRIVES]), Timing::at_hz(250)).unwrap();
    let held: Vec<_> = full.end(0).drives().map(|d| d.device).collect();
    assert_eq!(held, ids[..MAX_DRIVES]);
    // A drive listed twice is refused: its second slot could never be answered.
    assert_eq!(
        BusTick::new(&one_limb(&[id(101), id(102), id(101)]), Timing::at_hz(250)).err(),
        Some(ConfigError::DuplicateDrive(id(101)))
    );
}

/// Guards: protocol - `unanswered` counts every command without a status by the collect deadline, whenever the late
/// status is read; a status after a drive has answered and with no new command is unsolicited, not a duplicate
/// (PLAN.md item 3).
#[test]
fn reply_counters_follow_the_deadline_not_the_read_order() {
    let mut bus = bus();
    let enable = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    run_tick(
        &mut bus,
        0,
        Some(&enable),
        &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    // MIT to both: drive 101 on time, drive 102 just after the deadline but before the tick ends.
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(hold(101)), Some(hold(102))])),
        &[(MS, status(101, Mode::Run))],
    );
    bus.on_frame(deadline(1) + 1, &status(102, Mode::Run));
    let c = bus.end(deadline(1) + 1).counters;
    assert_eq!(
        (c.unanswered, c.late, c.duplicate, c.unsolicited),
        (1, 1, 0, 0)
    );
    // Tick 2 commands nothing; drive 101 still reports.
    run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[None, None])),
        &[(MS, status(101, Mode::Run))],
    );
    let c = bus.end(deadline(2)).counters;
    assert_eq!((c.duplicate, c.unsolicited), (0, 1));
}

/// Guards: safety - a batch is checked whole before any of it is sent: a frame aimed at another drive, a frame in a
/// slot with no drive, or a frame a batch may not carry (Set Zero, set-ID, parameter reads and other writes, reporting
/// on, queries: each needs sequencing a tick can't give, PLAN.md item 2) sends nothing and stops the bus with the exact
/// reason; motion to a drive never heard from stops that drive's limb, here the bus's only one (PLAN.md item 3, item 6
/// Silence row).
#[test]
fn a_bad_batch_sends_nothing_and_names_the_slot() {
    let rows = [
        (
            "wrong target in slot 1",
            [
                Some(encode::enable(id(101))),
                Some(encode::enable(id(101))),
                None,
            ],
            StopReason::BadBatch { slot: 1 },
        ),
        (
            "slot 2 has no drive",
            [
                Some(encode::enable(id(101))),
                None,
                Some(encode::enable(id(103))),
            ],
            StopReason::BadBatch { slot: 2 },
        ),
        (
            "motion to a drive never heard",
            [Some(hold(101)), None, None],
            StopReason::ExpiredFeedback { slot: 0 },
        ),
    ];
    let not_for_a_batch = [
        ("set zero", encode::set_zero(id(101))),
        ("set id", encode::set_id(id(101), id(104))),
        (
            "parameter read",
            encode::param_read(id(101), Param::RunMode),
        ),
        (
            "timeout write",
            encode::param_write(&Write::can_timeout(drive(101))),
        ),
        (
            "speed target write",
            encode::param_write(&Write::speed_target_zero(drive(101))),
        ),
        (
            "reporting on",
            encode::active_reporting(id(101), Reporting::On),
        ),
        ("version query", encode::version_query(id(101))),
        ("get id", encode::get_id(id(101))),
    ]
    .map(|(name, frame)| {
        (
            name,
            [Some(frame), None, None],
            StopReason::BadBatch { slot: 0 },
        )
    });
    let rows = rows.into_iter().chain(not_for_a_batch);
    for (name, frames, reason) in rows {
        let mut bus = bus();
        let sent = run_tick(&mut bus, 0, Some(&batch(0, &frames)), &[]);
        assert!(
            sent.iter().all(|(_, kind)| *kind != SendKind::Command),
            "{name}: {sent:?}"
        );
        assert_eq!(stop_of(&bus.end(deadline(0))), Some(reason), "{name}");
    }
}

/// Guards: protocol - the enable sequence's own frames go out in a batch: active reporting off before the Enable, and
/// `run_mode` = MIT once the drive is in Run (PLAN.md item 2 Enable one drive).
#[test]
fn a_batch_carries_the_enable_sequence() {
    let mut bus = bus();
    let b = batch(
        0,
        &[
            Some(encode::active_reporting(id(101), Reporting::Off)),
            Some(encode::param_write(&Write::mit_mode(drive(102)))),
        ],
    );
    let sent = run_tick(&mut bus, 0, Some(&b), &[]);
    assert_eq!(sent, [(0, SendKind::Command), (1, SendKind::Command)]);
    assert_eq!(stop_of(&bus.end(deadline(0))), None);
}

/// Guards: number - feedback exactly three periods old still carries motion; one nanosecond more stops (PLAN.md item 3:
/// three periods, 12 ms at 250 Hz).
#[test]
fn the_feedback_limit_is_three_periods_inclusive() {
    for (age, sends) in [(3 * PERIOD, true), (3 * PERIOD + 1, false)] {
        let mut bus = bus();
        let enable = batch(0, &[Some(encode::enable(id(101))), None]);
        run_tick(&mut bus, 0, Some(&enable), &[(0, status(101, Mode::Run))]);
        let _ = bus.end(deadline(0));
        // Tick 3 begins `age` after the status, read at 0.
        let mut hold_batch = CommandBatch::new(3, age + PERIOD);
        assert!(hold_batch.set(0, hold(101)));
        let list = bus.begin(3, age, age, Some(&hold_batch));
        let commands = list.iter().filter(|s| s.kind == SendKind::Command).count();
        assert_eq!(commands == 1, sends, "age {age}");
    }
}

/// Guards: safety - timing that breaks the tick's promises is refused at startup, never quietly replaced, one row per
/// rule and its boundary: a rate whose three periods reach the drives' 50 ms timeout (60 Hz) is refused and 61 Hz is not,
/// and a stop window must fit the post-Disable silence and a tick to send reporting off (safety.md: invalid
/// configuration is an error; PLAN.md item 3).
#[test]
fn timing_that_breaks_the_tick_is_refused() {
    let base = Timing::at_hz(250);
    let fits = base.disable_silence_ns + base.period_ns;
    let at_60 = Timing::at_hz(60);
    let rows = [
        ("no rate", Timing::at_hz(0), Some(TimingError::NoPeriod)),
        (
            "no send window",
            Timing {
                send_window_ns: 0,
                ..base
            },
            Some(TimingError::SendWindow {
                send_window_ns: 0,
                collect_ns: base.collect_ns,
            }),
        ),
        (
            "send window past collect",
            Timing {
                send_window_ns: base.collect_ns + 1,
                ..base
            },
            Some(TimingError::SendWindow {
                send_window_ns: base.collect_ns + 1,
                collect_ns: base.collect_ns,
            }),
        ),
        (
            "collect at the period",
            Timing {
                collect_ns: base.period_ns,
                ..base
            },
            Some(TimingError::Collect {
                collect_ns: base.period_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "feedback under a period",
            Timing {
                feedback_limit_ns: base.period_ns - 1,
                ..base
            },
            Some(TimingError::FeedbackLimit {
                feedback_limit_ns: base.period_ns - 1,
                period_ns: base.period_ns,
            }),
        ),
        (
            "60 Hz",
            at_60,
            Some(TimingError::FeedbackLimit {
                feedback_limit_ns: 50_000_001,
                period_ns: 16_666_667,
            }),
        ),
        ("61 Hz", Timing::at_hz(61), None),
        (
            "stop window too short",
            Timing {
                stop_confirm_ns: fits - 1,
                ..base
            },
            Some(TimingError::StopWindow {
                stop_confirm_ns: fits - 1,
                disable_silence_ns: base.disable_silence_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "stop window just fits",
            Timing {
                stop_confirm_ns: fits,
                ..base
            },
            None,
        ),
        ("250 Hz", base, None),
    ];
    for (name, timing, refused) in rows {
        assert_eq!(
            BusTick::new(&one_limb(&[id(101)]), timing).err(),
            refused.map(ConfigError::Timing),
            "{name}: {timing:?}"
        );
    }
}

/// Guards: safety - each silence count must be at least one and fire before the drives time out on their own: zero
/// would stop an active bus at its first tick or every limb at its first send, and a count that spans the drives'
/// timeout turns its rule off (safety.md section 4: no config value turns a protection off; PLAN.md items 3 and 6).
#[test]
fn silence_counts_must_fire_before_the_drive_timeout() {
    let base = Timing::at_hz(250);
    // The fewest periods that reach the drives' timeout.
    let span = u32::try_from(DRIVE_TIMEOUT_NS.div_ceil(base.period_ns)).unwrap_or(u32::MAX);
    let rows = [
        (
            "no silent ticks",
            Timing {
                silent_ticks: 0,
                ..base
            },
            Some(TimingError::SilentTicks {
                silent_ticks: 0,
                period_ns: base.period_ns,
            }),
        ),
        (
            "silent ticks reach the drive timeout",
            Timing {
                silent_ticks: span,
                ..base
            },
            Some(TimingError::SilentTicks {
                silent_ticks: span,
                period_ns: base.period_ns,
            }),
        ),
        (
            "silent ticks just inside the drive timeout",
            Timing {
                silent_ticks: span - 1,
                ..base
            },
            None,
        ),
        (
            "silent ticks exactly the drive timeout",
            Timing {
                silent_ticks: 10,
                ..Timing::at_hz(200)
            },
            Some(TimingError::SilentTicks {
                silent_ticks: 10,
                period_ns: 5 * MS,
            }),
        ),
        (
            "no silence misses",
            Timing {
                silence_misses: 0,
                ..base
            },
            Some(TimingError::SilenceMisses {
                silence_misses: 0,
                period_ns: base.period_ns,
            }),
        ),
        (
            "silence misses reach the drive timeout",
            Timing {
                silence_misses: span,
                ..base
            },
            Some(TimingError::SilenceMisses {
                silence_misses: span,
                period_ns: base.period_ns,
            }),
        ),
        (
            "silence misses just inside the drive timeout",
            Timing {
                silence_misses: span - 1,
                ..base
            },
            None,
        ),
    ];
    for (name, timing, refused) in rows {
        assert_eq!(
            BusTick::new(&one_limb(&[id(101)]), timing).err(),
            refused.map(ConfigError::Timing),
            "{name}: {timing:?}"
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
        (snap.healthy, state_of(&snap)),
        (false, LimbState::Idle),
        "passive doesn't stop the bus"
    );
    run_tick(&mut bus, 1, None, &[(MS, error_frame(0x04, 0x40))]);
    assert!(bus.end(deadline(1)).healthy);
    // Passive, then back to warning: a recovery, healthy again. Passive, then back to active in the same frame as an
    // overflow (which outranks it as the error): healthy too. An overflow alone says nothing about the state.
    let rows = [(0x08, true), (0x41, true), (0x01, false)];
    for (crtl, healthy) in rows {
        let mut bus = common::bus();
        run_tick(
            &mut bus,
            0,
            None,
            &[
                (MS, error_frame(0x04, 0x20)),
                (2 * MS, error_frame(0x04, crtl)),
            ],
        );
        assert_eq!(bus.end(deadline(0)).healthy, healthy, "crtl {crtl:#x}");
    }
}
