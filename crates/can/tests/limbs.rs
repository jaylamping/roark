//! Limbs on one bus: each runs and stops on its own, the check before every send stops a limb on what the drain just
//! read, and an operator's clear re-arms a stopped limb (PLAN.md item 6, step 7 design D1 and D2).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusDrive, BusError, BusTick, ConfigError, DRIVE_TIMEOUT_NS, EchoSeen, LimbState, MAX_DRIVES,
    RearmRefused, SendKind, SendOutcome, Snapshot, StopOutcome, StopReason, Timing,
};
use common::{
    MS, PERIOD, at, batch, deadline, error_frame, hold, id, record, run_tick, status, status_frame,
};
use robstride::{EchoKind, Mode, StatusFault, encode};
use telemetry::Direction;

/// Drive 101 in limb 0 and drive 102 in limb 1, at 250 Hz.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: two drives in two limbs fit"
)]
fn two_limbs() -> BusTick {
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
    bus.stop_limb(0);
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
        (LimbState::Stopping { .. }, Some(StopReason::Requested))
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
/// drive was seen in Run, stops that drive's limb on that same tick, so no command goes to it, while the other limb's
/// command still goes out (PLAN.md item 6 Faults row and States; safety.md section 3: every check before transmit).
#[test]
fn a_fault_or_reset_read_before_the_send_stops_its_limb_at_once() {
    let faulted = status_frame(
        101,
        Mode::Run,
        [StatusFault::Overcurrent].into_iter().collect(),
    );
    let rows = [
        (
            "fault bit",
            record(faulted.id(), faulted.data(), Direction::TxOther),
            StopReason::DriveFault { slot: 0 },
        ),
        (
            "reset after run",
            status(101, Mode::Reset),
            StopReason::DriveMode { slot: 0 },
        ),
    ];
    for (name, drained, reason) in rows {
        let mut bus = two_limbs();
        running(&mut bus);
        // Read in tick 2's drain, after tick 1's collect.
        bus.on_frame(2 * PERIOD - MS, &drained);
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
        assert!(sent.contains(&(0, SendKind::Disable)), "tick {tick}");
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
    bus.sent(0, SendOutcome::Sent);
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
