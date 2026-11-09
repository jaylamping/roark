//! Limbs on one bus: each runs and stops on its own, the check before every send stops a limb on what the drain just
//! read, and an operator's clear re-arms a stopped limb (PLAN.md item 6).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusDrive, BusError, BusTick, ConfigError, DRIVE_TIMEOUT_NS, ENABLE_TO_RUN_NS, EchoSeen,
    LimbState, MAX_DRIVES, NoSuchLimb, RearmRefused, SendKind, SendOutcome, Snapshot, StopOutcome,
    StopReason, Timing,
};
use common::{
    MS, PERIOD, at, batch, deadline, error_frame, hold, id, record, run_tick, status, status_frame,
    two_limbs,
};
use robstride::{EchoKind, Mode, StatusFault, StatusFaults, encode};
use telemetry::Direction;

#[expect(clippy::unwrap_used, reason = "test helper: the limbs asked for exist")]
fn limb(snap: &Snapshot, limb: usize) -> (LimbState, Option<StopReason>) {
    let l = snap.limb(limb).unwrap();
    (l.state, l.stop)
}

/// Both drives enabled at tick 0 and answering in Run, then held at tick 1 with both answering.
fn running(bus: &mut BusTick) {
    let enable = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    run_tick(
        bus,
        0,
        Some(&enable),
        &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    run_tick(
        bus,
        1,
        Some(&batch(1, &[Some(hold(101)), Some(hold(102))])),
        &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(1));
}

/// Guards: safety - a limb stop stops only that limb: its drives get Disable and its frames in control's batch are
/// dropped and counted, while the bus's other limb keeps its commands (PLAN.md item 6: a stop names its scope).
#[test]
fn a_limb_stop_leaves_the_other_limb_running() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.stop_limb(MAX_DRIVES), Err(NoSuchLimb(MAX_DRIVES)));
    assert_eq!(bus.stop_limb(0), Ok(()));
    let sent = run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[Some(hold(101)), Some(hold(102))])),
        &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(2));
    assert!(matches!(
        limb(&snap, 0),
        (LimbState::Stopping { .. }, Some(StopReason::LimbRequested))
    ));
    assert_eq!(limb(&snap, 1), (LimbState::Active, None));
    assert_eq!(snap.counters.refused_frames, 1);
    assert_eq!(at(&snap, 0).stop, StopOutcome::Confirmed);
    // A stop of the whole bus stops every limb.
    bus.request_stop();
    let sent = run_tick(&mut bus, 3, Some(&batch(3, &[None, Some(hold(102))])), &[]);
    assert_eq!(sent, [(1, SendKind::Disable)]);
    let snap = bus.end(deadline(3));
    assert!(matches!(
        limb(&snap, 1),
        (LimbState::Stopping { .. }, Some(StopReason::Requested))
    ));
}

/// Guards: safety - what the drain reads before the send is checked before the send: a fault bit, or Reset after the
/// drive was seen in Run (even with a Run status read after it), stops that drive's limb on that same tick, so no
/// command goes to it, while the other limb's command still goes out. An idle limb is checked too: a faulted drive
/// never gets its Enable (PLAN.md item 6 Faults row and States; safety.md section 3: every check before transmit).
#[test]
fn a_fault_or_reset_read_before_the_send_stops_its_limb_at_once() {
    let faulted = status_frame(
        101,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    let faulted = record(faulted.id(), faulted.data(), Direction::TxOther);
    let rows = [
        (
            "fault bit",
            vec![faulted],
            StopReason::DriveFault { slot: 0 },
        ),
        (
            "reset after run",
            vec![status(101, Mode::Reset)],
            StopReason::DriveMode { slot: 0 },
        ),
        (
            "reset, then run again",
            vec![status(101, Mode::Reset), status(101, Mode::Run)],
            StopReason::DriveMode { slot: 0 },
        ),
    ];
    for (name, drained, reason) in rows {
        let mut bus = two_limbs();
        running(&mut bus);
        // Read in tick 2's drain, after tick 1's collect.
        for frame in &drained {
            bus.on_frame(2 * PERIOD - MS, frame);
        }
        let sent = run_tick(
            &mut bus,
            2,
            Some(&batch(2, &[Some(hold(101)), Some(hold(102))])),
            &[],
        );
        assert_eq!(
            sent,
            [(0, SendKind::Disable), (1, SendKind::Command)],
            "{name}"
        );
        let snap = bus.end(deadline(2));
        assert!(
            matches!(limb(&snap, 0), (LimbState::Stopping { .. }, Some(r)) if r == reason),
            "{name}: {snap:?}"
        );
        assert_eq!(limb(&snap, 1), (LimbState::Active, None), "{name}");
    }

    // An idle limb: the fault read before its first Enable.
    let mut bus = two_limbs();
    bus.on_frame(0, &faulted);
    let enable = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    let sent = run_tick(&mut bus, 0, Some(&enable), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(0));
    assert!(matches!(
        limb(&snap, 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveFault { slot: 0 })
        )
    ));
}

/// Guards: safety - motion on expired feedback stops only that drive's limb: the other limb's command still goes out
/// (PLAN.md item 6 Silence row; a stop names its scope).
#[test]
fn expired_feedback_stops_only_its_limb() {
    let mut bus = two_limbs();
    running(&mut bus);
    // Drive 101 is left alone, so it misses nothing, until its last status is past the feedback limit.
    let mut tick = 2;
    while tick * PERIOD - (PERIOD + MS) <= bus.timing().feedback_limit_ns {
        run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    let sent = run_tick(
        &mut bus,
        tick,
        Some(&batch(tick, &[Some(hold(101)), Some(hold(102))])),
        &[],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(tick));
    assert!(matches!(
        limb(&snap, 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::ExpiredFeedback { slot: 0 })
        )
    ));
    assert_eq!(limb(&snap, 1), (LimbState::Active, None));
}

/// Guards: safety - replies missed while a drive is between its Enable and its first Run status aren't counted for
/// [`ENABLE_TO_RUN_NS`]; after a Disable they aren't counted for `stop_confirm_ns`, nor at all once a Reset confirms
/// the drive off, even after another Disable; a Run status doesn't confirm it; once Run is seen after an Enable they count again (PLAN.md item 2 Silence windows; item 6 Silence row:
/// a silent disabled drive is offline, not a fault).
#[test]
fn misses_in_the_enable_and_post_disable_windows_are_not_counted() {
    // The enable sequence's run_mode write needs no fresh feedback, so it can go unanswered in either window.
    let write = encode::param_write(&robstride::Write::mit_mode(common::drive(101)));
    let misses = u64::from(two_limbs().timing().silence_misses);

    // Between the Enable and the first Run status: counted only from the first send at least 50 ms after the Enable.
    let mut bus = two_limbs();
    // Drive 102 enabled and answering, so the helper's holds to it go out.
    run_tick(
        &mut bus,
        0,
        Some(&batch(
            0,
            &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
        )),
        &[(MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    let first_counted = ENABLE_TO_RUN_NS.div_ceil(PERIOD);
    let stopped_at = silent_until_stopped(&mut bus, 1, first_counted, misses, write);
    assert_eq!(stopped_at, first_counted + misses);

    // After a Disable from control that Reset confirms: never counted, well past the post-Disable silence.
    let mut bus = two_limbs();
    running(&mut bus);
    run_tick(
        &mut bus,
        2,
        Some(&batch(
            2,
            &[Some(encode::disable(id(101))), Some(hold(102))],
        )),
        &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(2));
    // Disabled again at tick 3, unanswered: still offline, so still never counted.
    let quiet_until = 3 + 2 * bus.timing().stop_confirm_ns / PERIOD + misses;
    for tick in 3..quiet_until {
        let to_101 = if tick == 3 {
            encode::disable(id(101))
        } else {
            write
        };
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[Some(to_101), Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        assert_eq!(
            sent,
            [(0, SendKind::Command), (1, SendKind::Command)],
            "tick {tick}"
        );
        let snap = bus.end(deadline(tick));
        assert_eq!(at(&snap, 0).misses, 0, "tick {tick}");
    }

    // Enabled again and seen in Run: its misses count from the next send.
    let tick = quiet_until;
    run_tick(
        &mut bus,
        tick,
        Some(&batch(
            tick,
            &[Some(encode::enable(id(101))), Some(hold(102))],
        )),
        &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(tick));
    let stopped_at = silent_until_stopped(&mut bus, tick + 1, tick + 1, misses, hold(101));
    assert_eq!(stopped_at, tick + 1 + misses);

    // A Disable with no Reset read after it (lost, answered still in Run, then silent): counted again from the first
    // send `stop_confirm_ns` after it, and a Disable sent again doesn't restart that window.
    let mut bus = two_limbs();
    running(&mut bus);
    for tick in 2..4 {
        run_tick(
            &mut bus,
            tick,
            Some(&batch(
                tick,
                &[Some(encode::disable(id(101))), Some(hold(102))],
            )),
            &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
        );
        let _ = bus.end(deadline(tick));
    }
    let first_counted = 2 + bus.timing().stop_confirm_ns.div_ceil(PERIOD);
    let stopped_at = silent_until_stopped(&mut bus, 4, first_counted, misses, write);
    assert_eq!(stopped_at, first_counted + misses);
}

/// Sends `frame` to drive 101 every tick from `from`, never answered, with drive 102 held and answering, until drive
/// 101's limb stops; checks each tick's miss count against misses counted from tick `first_counted`. Returns the tick
/// whose send was the stop's Disable.
fn silent_until_stopped(
    bus: &mut BusTick,
    from: u64,
    first_counted: u64,
    misses: u64,
    frame: robstride::Frame,
) -> u64 {
    let mut tick = from;
    loop {
        let sent = run_tick(
            bus,
            tick,
            Some(&batch(tick, &[Some(frame), Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        if sent.first() == Some(&(0, SendKind::Disable)) {
            let snap = bus.end(deadline(tick));
            assert!(matches!(
                limb(&snap, 0),
                (
                    LimbState::Stopping { .. },
                    Some(StopReason::DriveSilent { slot: 0 })
                )
            ));
            return tick;
        }
        assert!(
            tick <= first_counted + misses,
            "never stopped by tick {tick}"
        );
        let snap = bus.end(deadline(tick));
        let counted = (tick + 1).saturating_sub(first_counted).min(misses);
        assert_eq!(u64::from(at(&snap, 0).misses), counted, "tick {tick}");
        tick += 1;
    }
}

/// Guards: safety - a drive that leaves `silence_misses` commands in a row unanswered stops its limb before the next
/// send; fewer don't, and an answer resets the count (PLAN.md item 6 Silence row: three missed replies).
#[test]
fn missed_replies_in_a_row_stop_the_limb() {
    let mut bus = two_limbs();
    running(&mut bus);
    let misses = bus.timing().silence_misses;
    // Drive 101 misses one short of the limit, answers once, then stops answering; drive 102 answers every tick.
    let mut tick = 2;
    let answered_at = tick + u64::from(misses) - 1;
    let last = answered_at + u64::from(misses);
    while tick <= last {
        let answers: &[(u64, _)] = if tick == answered_at {
            &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))]
        } else {
            &[(MS, status(102, Mode::Run))]
        };
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[Some(hold(101)), Some(hold(102))])),
            answers,
        );
        assert_eq!(
            sent,
            [(0, SendKind::Command), (1, SendKind::Command)],
            "tick {tick}"
        );
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    let sent = run_tick(
        &mut bus,
        tick,
        Some(&batch(tick, &[Some(hold(101)), Some(hold(102))])),
        &[],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(tick));
    assert!(matches!(
        limb(&snap, 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveSilent { slot: 0 })
        )
    ));
    assert_eq!(at(&snap, 0).misses, misses);

    // Answers that come after the collect deadline are misses too: they never reset the count.
    let mut bus = two_limbs();
    running(&mut bus);
    let late = PERIOD * 8 / 10;
    for tick in 2..2 + u64::from(misses) {
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[Some(hold(101)), Some(hold(102))])),
            &[(late, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
        );
        assert_eq!(
            sent,
            [(0, SendKind::Command), (1, SendKind::Command)],
            "tick {tick}"
        );
        let _ = bus.end(tick * PERIOD + late);
    }
    let tick = 2 + u64::from(misses);
    let sent = run_tick(
        &mut bus,
        tick,
        Some(&batch(tick, &[Some(hold(101)), Some(hold(102))])),
        &[],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(tick));
    assert_eq!(snap.counters.late, u64::from(misses));
    assert!(matches!(
        limb(&snap, 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveSilent { slot: 0 })
        )
    ));
}

/// Guards: safety - only leaving Run after the drive was seen in Run is a mode change: a Reset still in flight when the
/// Enable goes out, or the Reset answering a Disable from control, doesn't stop the limb, and an Enable sent again to a
/// running drive doesn't hide a drop out of Run (PLAN.md item 6 States).
#[test]
fn only_leaving_run_after_running_is_a_mode_change() {
    // A Reset answer to the Enable, from a status already in flight, then Run.
    let mut bus = two_limbs();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
        &[(MS, status(101, Mode::Reset))],
    );
    let _ = bus.end(deadline(0));
    let sent = run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(hold(101)), None])),
        &[(MS, status(101, Mode::Run))],
    );
    assert_eq!(sent, [(0, SendKind::Command)]);
    let snap = bus.end(deadline(1));
    assert_eq!(limb(&snap, 0), (LimbState::Active, None));

    // Enabled again while running, then a drop to Reset.
    let mut bus = two_limbs();
    running(&mut bus);
    run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[Some(encode::enable(id(101))), Some(hold(102))])),
        &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(2));
    let sent = run_tick(&mut bus, 3, Some(&batch(3, &[None, Some(hold(102))])), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(3));
    assert!(matches!(
        limb(&snap, 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveMode { slot: 0 })
        )
    ));

    // A version reply carries the status header: its Reset after Run is a mode change too.
    let mut bus = two_limbs();
    running(&mut bus);
    let reset = status_frame(101, Mode::Reset, StatusFaults::default());
    let version = record(
        reset.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    );
    bus.on_frame(2 * PERIOD - MS, &version);
    let sent = run_tick(
        &mut bus,
        2,
        Some(&batch(2, &[Some(hold(101)), Some(hold(102))])),
        &[],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    assert!(matches!(
        limb(&bus.end(deadline(2)), 0),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveMode { slot: 0 })
        )
    ));

    // Disabled by control while running.
    let mut bus = two_limbs();
    running(&mut bus);
    run_tick(
        &mut bus,
        2,
        Some(&batch(
            2,
            &[Some(encode::disable(id(101))), Some(hold(102))],
        )),
        &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(2));
    let sent = run_tick(&mut bus, 3, Some(&batch(3, &[None, Some(hold(102))])), &[]);
    assert_eq!(sent, [(1, SendKind::Command)]);
    let snap = bus.end(deadline(3));
    assert_eq!(limb(&snap, 0), (LimbState::Active, None));
}

/// Guards: safety - a limb is its drives, wherever they sit in the table: a fault on one drive Disables every drive of
/// its limb and no other, with limb numbers that aren't slot numbers (PLAN.md item 6: a stop names its scope).
#[test]
fn a_stop_reaches_every_drive_of_its_limb_and_no_other() {
    let drives = [(101, 1), (102, 1), (103, 0)].map(|(n, limb)| BusDrive {
        device: id(n),
        limb,
    });
    let mut bus = BusTick::new(&drives, Timing::at_hz(250)).unwrap();
    let enable = batch(0, &[101, 102, 103].map(|n| Some(encode::enable(id(n)))));
    let running = [101, 102, 103].map(|n| (MS, status(n, Mode::Run)));
    run_tick(&mut bus, 0, Some(&enable), &running);
    let _ = bus.end(deadline(0));
    let faulted = status_frame(
        101,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    bus.on_frame(
        PERIOD - MS,
        &record(faulted.id(), faulted.data(), Direction::TxOther),
    );
    let holds = batch(1, &[101, 102, 103].map(|n| Some(hold(n))));
    let sent = run_tick(&mut bus, 1, Some(&holds), &[]);
    assert_eq!(
        sent,
        [
            (0, SendKind::Disable),
            (1, SendKind::Disable),
            (2, SendKind::Command)
        ]
    );
    let snap = bus.end(deadline(1));
    assert!(matches!(
        limb(&snap, 1),
        (
            LimbState::Stopping { .. },
            Some(StopReason::DriveFault { slot: 0 })
        )
    ));
    assert_eq!(limb(&snap, 0), (LimbState::Active, None));
}

/// Guards: safety - only an operator's clear re-arms a stopped limb, and only once every drive in it is known
/// disabled: confirmed in Reset by the stop, or without a frame for longer than the drive timeout. A running or
/// stopping limb, a failed bus or an unknown limb is refused. A re-armed limb starts a new generation with no fault
/// history and can be enabled again (PLAN.md item 6: a latched stop clears only by an operator clear, then preflight).
#[test]
fn a_stopped_limb_is_rearmed_only_when_its_drives_are_known_disabled() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.rearm(0, 2 * PERIOD), Err(RearmRefused::NotStopped(0)));
    assert_eq!(bus.rearm(5, 2 * PERIOD), Err(RearmRefused::NoSuchLimb(5)));
    // Drive 101 faults and its limb stops; it never answers the Disables.
    let faulted = status_frame(
        101,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    bus.on_frame(
        2 * PERIOD - MS,
        &record(faulted.id(), faulted.data(), Direction::TxOther),
    );
    let mut tick = 2;
    let last_disable = loop {
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped {
            break (tick - 1) * PERIOD;
        }
        assert_eq!(
            sent,
            [(0, SendKind::Disable), (1, SendKind::Command)],
            "tick {tick}"
        );
        tick += 1;
    };
    let now = tick * PERIOD;
    assert_eq!(
        bus.rearm(0, now),
        Err(RearmRefused::DriveNotQuiet { slot: 0 })
    );
    // Limb 1 keeps running while drive 101 stays quiet past the drive timeout plus a period, after which it has
    // dropped to Reset on its own.
    let quiet = last_disable + DRIVE_TIMEOUT_NS + PERIOD;
    while tick * PERIOD < quiet {
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        assert_eq!(sent, [(1, SendKind::Command)], "tick {tick}");
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    assert_eq!(bus.rearm(0, quiet), Ok(()));
    let next = tick;
    let sent = run_tick(
        &mut bus,
        next,
        Some(&batch(
            next,
            &[Some(encode::enable(id(101))), Some(hold(102))],
        )),
        &[(MS, status(101, Mode::Run)), (MS, status(102, Mode::Run))],
    );
    assert_eq!(sent, [(0, SendKind::Command), (1, SendKind::Command)]);
    let snap = bus.end(deadline(next));
    assert_eq!(
        snap.limb(0).map(|l| (l.state, l.stop, l.generation)),
        Some((LimbState::Active, None, 1))
    );
    assert!(!at(&snap, 0).fault_seen);
    // A failed bus is never re-armed in place.
    bus.on_frame(next * PERIOD + 2 * MS, &error_frame(0x40, 0));
    let _ = bus.end(deadline(next));
    assert_eq!(
        bus.rearm(0, quiet + DRIVE_TIMEOUT_NS * 2),
        Err(RearmRefused::BusFailed(BusError::BusOff))
    );
}

/// Guards: protocol - the echo of this host's frame to a drive is kept per drive, so the enable sequence can wait on
/// that drive's reporting-off echo (PLAN.md item 2 Enable one drive: "wait for its echo plus one tick").
#[test]
fn each_drives_last_echo_is_kept() {
    let mut bus = two_limbs();
    let off = encode::active_reporting(id(102), robstride::encode::Reporting::Off);
    let list = bus.begin(0, 0, 0, Some(&batch(0, &[None, Some(off)])));
    assert_eq!(list.len(), 1);
    bus.sent(0, SendOutcome::Sent, 0);
    bus.on_frame(200_000, &record(off.id(), off.data(), Direction::TxEcho));
    let snap = bus.end(deadline(0));
    assert_eq!(at(&snap, 0).last_echo, None);
    assert_eq!(
        at(&snap, 1).last_echo,
        Some(EchoSeen {
            kind: EchoKind::Reporting(robstride::encode::Reporting::Off),
            read_ns: 200_000,
        })
    );
}

/// Guards: number - a drive's limb index is checked against the fixed limb table at startup, never truncated
/// (rust.md section 6).
#[test]
fn a_limb_past_the_table_is_refused() {
    let drives = [BusDrive {
        device: id(101),
        limb: MAX_DRIVES,
    }];
    assert_eq!(
        BusTick::new(&drives, Timing::at_hz(250)).err(),
        Some(ConfigError::LimbOutOfRange {
            slot: 0,
            limb: MAX_DRIVES
        })
    );
}

/// Guards: safety - the re-arm's quiet time counts from when the socket took the last frame, not from its tick's
/// scheduled start: a Disable written late (it never expires) holds the re-arm off for the drive timeout after the
/// write (can.md section 2: sent nothing for longer than the drive timeout).
#[test]
fn a_late_written_disable_holds_off_the_rearm() {
    let late = PERIOD + PERIOD / 2;
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.stop_limb(0), Ok(()));
    // Drive 101 never answers; each tick's Disable to it is written `late`.
    let mut tick = 2;
    let last_write = loop {
        let start = tick * PERIOD;
        let list = bus.begin(
            tick,
            start,
            start,
            Some(&batch(tick, &[None, Some(hold(102))])),
        );
        let mut disabled = false;
        for (index, send) in list.iter().enumerate() {
            let at = if send.slot == 0 { start + late } else { start };
            disabled |= send.slot == 0;
            bus.sent(index, SendOutcome::Sent, at);
        }
        bus.on_frame(start + MS, &status(102, Mode::Run));
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped && !disabled {
            break (tick - 1) * PERIOD + late;
        }
        tick += 1;
    };
    let quiet = DRIVE_TIMEOUT_NS + PERIOD;
    assert_eq!(
        bus.rearm(0, last_write - late + quiet),
        Err(RearmRefused::DriveNotQuiet { slot: 0 })
    );
    assert_eq!(
        bus.rearm(0, last_write + quiet - 1),
        Err(RearmRefused::DriveNotQuiet { slot: 0 })
    );
    assert_eq!(bus.rearm(0, last_write + quiet), Ok(()));
}

/// Guards: safety - a limb whose drives all confirmed Reset re-arms as soon as it is stopped, with no wait: a confirmed
/// drive is known disabled (PLAN.md item 6: operator clear).
#[test]
fn a_confirmed_limb_rearms_at_once() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.stop_limb(0), Ok(()));
    let mut tick = 2;
    loop {
        run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
        );
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped {
            assert_eq!(at(&snap, 0).stop, StopOutcome::Confirmed);
            break;
        }
        tick += 1;
    }
    // Its reporting off went out this very tick.
    assert_eq!(bus.rearm(0, deadline(tick)), Ok(()));
}

/// Guards: protocol - a bad batch arriving in the tick its bus's last running limb stops has no limb left to stop, so it is
/// counted as refused rather than lost (logging.md section 4: nothing fails in silence).
#[test]
fn a_bad_batch_as_the_last_limb_stops_is_counted() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.stop_limb(0), Ok(()));
    assert_eq!(bus.stop_limb(1), Ok(()));
    // Slot 0 carries a frame for drive 102: aimed wrong.
    let sent = run_tick(&mut bus, 2, Some(&batch(2, &[Some(hold(102)), None])), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    assert_eq!(snap.counters.refused_batches, 1);
    assert_eq!(limb(&snap, 0).1, Some(StopReason::LimbRequested));
}
