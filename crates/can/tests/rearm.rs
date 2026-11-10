//! The operator's re-arm of a stopped limb, without a socket: refused until every drive in it is known disabled, by a
//! confirmed Reset or a quiet past the drives' timeout (PLAN.md item 6: a latched stop clears only by an operator clear).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusError, DRIVE_TIMEOUT_NS, LimbState, RearmRefused, SendKind, SendOutcome, StopOutcome,
};
use common::{
    MS, PERIOD, at, batch, deadline, error_frame, hold, id, limb, record, run_tick, running,
    status, status_frame, two_limbs,
};
use robstride::{Mode, StatusFault, encode};
use telemetry::Direction;

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
    // Disables go out for the stop window; the stop ends when the reply allowance after it closes.
    let mut tick = 2;
    let mut last_disable = 0;
    loop {
        let sent = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &[(MS, status(102, Mode::Run))],
        );
        let snap = bus.end(deadline(tick));
        if sent.contains(&(0, SendKind::Disable)) {
            assert_eq!(
                sent,
                [(0, SendKind::Disable), (1, SendKind::Command)],
                "tick {tick}"
            );
            last_disable = tick * PERIOD;
        } else {
            assert_eq!(sent, [(1, SendKind::Command)], "tick {tick}");
        }
        if limb(&snap, 0).0 == LimbState::Stopped {
            break;
        }
        tick += 1;
    }
    tick += 1;
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
    let mut last_write = 0;
    loop {
        let start = tick * PERIOD;
        let list = bus.begin(
            tick,
            start,
            start,
            Some(&batch(tick, &[None, Some(hold(102))])),
        );
        for (index, send) in list.iter().enumerate() {
            let at = if send.slot == 0 { start + late } else { start };
            if send.slot == 0 {
                last_write = at;
            }
            bus.sent(index, SendOutcome::Sent, at);
        }
        bus.on_frame(start + MS, &status(102, Mode::Run));
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped {
            break;
        }
        tick += 1;
    }
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
