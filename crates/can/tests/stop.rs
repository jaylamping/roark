//! The stop path without a socket: what a stop sends, what confirms it, and when it is over (PLAN.md item 2 Stop, item 3).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusError, BusTick, CommandBatch, Drain, LimbState, Send, SendKind, SendOutcome, StopOutcome,
    StopReason,
};
use common::{
    MS, PERIOD, at, batch, bus, deadline, error_frame, hold, id, run_tick, state_of, status,
    stop_of,
};
use robstride::{Mode, encode};
use telemetry::FrameRecord;

/// Guards: safety - a hung control thread lets the drives time out: only a fresh batch is sent, and two ticks without
/// one stop the bus (PLAN.md item 3).
#[test]
fn a_stale_batch_is_never_sent_and_two_silent_ticks_stop_the_bus() {
    let mut bus = bus();
    let enable = batch(
        0,
        &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
    );
    run_tick(&mut bus, 0, Some(&enable), &[]);
    let _ = bus.end(PERIOD * 6 / 10);

    // Tick 1 is handed a batch for tick 0 that hasn't expired: nothing goes out.
    let mut old_tick = CommandBatch::new(0, 10 * PERIOD);
    assert!(old_tick.set(0, hold(101)));
    assert_eq!(run_tick(&mut bus, 1, Some(&old_tick), &[]), []);
    assert_eq!(bus.end(deadline(1)).counters.stale_ticks, 1);
    // Tick 2 is handed a batch for tick 2 that has already expired: nothing goes out, and the bus has now gone two
    // ticks without a fresh batch, so it stops: Disable to each drive (reporting off waits out the silence).
    let mut expired = CommandBatch::new(2, 2 * PERIOD);
    assert!(expired.set(0, hold(101)));
    let sent = run_tick(&mut bus, 2, Some(&expired), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    assert_eq!(snap.counters.stale_ticks, 2);
    assert!(matches!(state_of(&snap), LimbState::Stopping { .. }));
    assert_eq!(stop_of(&snap), Some(StopReason::ControlSilent));
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
            &[Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
        )),
        &[],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    bus.request_stop();
    // Drive 101 answers its Disable in Reset; drive 102 sends a late Run status.
    run_tick(
        &mut bus,
        1,
        None,
        &[(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))],
    );
    let snap = bus.end(PERIOD + PERIOD * 6 / 10);
    assert_eq!(at(&snap, 0).stop, StopOutcome::Confirmed);
    assert_eq!(at(&snap, 1).stop, StopOutcome::Sent);
    // Next tick only the unconfirmed drive gets Disable again.
    assert_eq!(run_tick(&mut bus, 2, None, &[]), [(1, SendKind::Disable)]);
    let _ = bus.end(2 * PERIOD + PERIOD * 6 / 10);
    // 100 ms after the stop began, it's over, with drive 102 recorded as unconfirmed.
    let mut tick = 3;
    let snap = loop {
        run_tick(&mut bus, tick, None, &[]);
        let snap = bus.end(tick * PERIOD + PERIOD * 6 / 10);
        if state_of(&snap) == LimbState::Stopped || tick > 40 {
            break snap;
        }
        tick += 1;
    };
    assert_eq!(state_of(&snap), LimbState::Stopped);
    assert!(
        tick * PERIOD >= 100 * MS,
        "stopped no earlier than 100 ms after the stop"
    );
    assert_eq!(at(&snap, 1).stop, StopOutcome::Sent);
    // Disables that went unanswered aren't missed replies (PLAN.md item 2 Silence windows).
    assert_eq!(snap.counters.unanswered, 0);
    // Stopped is latched: batches are refused.
    assert_eq!(
        run_tick(
            &mut bus,
            tick + 1,
            Some(&batch(tick + 1, &[Some(hold(101)), None])),
            &[]
        ),
        []
    );
}

/// Guards: safety - a thread that wakes past its send window stops an active bus at once instead of sending motion, and
/// sends the Disables on that same tick: a late Disable is still the right one. An idle bus has nothing to stop: the
/// missed deadline is counted, and of its batch only the Disables and reporting off go out, late as they are (can.md
/// section 2), while the rest is held (PLAN.md item 3).
#[test]
fn a_late_wake_stops_the_bus() {
    let mut bus = bus();
    // Idle, tick 0 woken 2 ms late with an Enable to one drive and a Disable to the other: the Disable goes, the
    // Enable is held, and the bus stays idle.
    let mixed = batch(
        0,
        &[
            Some(encode::enable(id(101))),
            Some(encode::disable(id(102))),
        ],
    );
    assert_eq!(
        bus.begin(0, 2 * MS, 0, Some(&mixed))
            .iter()
            .collect::<Vec<_>>(),
        [Send {
            slot: 1,
            kind: SendKind::Command,
            frame: encode::disable(id(102)),
            expires: false,
        }]
    );
    let snap = bus.end(deadline(0));
    let c = snap.counters;
    assert_eq!(
        (
            state_of(&snap),
            stop_of(&snap),
            c.missed_deadlines,
            c.held_batches,
            c.stale_ticks
        ),
        (LimbState::Idle, None, 1, 1, 0)
    );
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
        &[],
    );
    let _ = bus.end(PERIOD * 6 / 10);
    // Tick 5 was due at 20 ms; the thread wakes at 33 ms with a fresh batch enabling the other drive.
    let mut fresh = CommandBatch::new(5, 40 * MS);
    assert!(fresh.set(1, encode::enable(id(102))));
    let list = bus.begin(5, 33 * MS, 5 * PERIOD, Some(&fresh));
    let disable = |slot, n| Send {
        slot,
        kind: SendKind::Disable,
        frame: encode::disable(id(n)),
        expires: false,
    };
    assert_eq!(
        list.iter().collect::<Vec<_>>(),
        [disable(0, 101), disable(1, 102)]
    );
    let snap = bus.end(34 * MS);
    assert_eq!(stop_of(&snap), Some(StopReason::LateWake));
    // The idle tick's and this one's.
    assert_eq!(snap.counters.missed_deadlines, 2);
}

/// Guards: safety - control going silent stops an active bus after two consecutive ticks without a fresh batch, a
/// missing batch counting like a stale one; a fresh batch in between starts the count again (PLAN.md item 3).
#[test]
fn only_consecutive_silent_ticks_stop_the_bus() {
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
        &[(MS, status(101, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    // Silent, fresh, silent: never two in a row.
    for (tick, fresh) in [(1, false), (2, true), (3, false)] {
        let b = batch(tick, &[]);
        assert_eq!(run_tick(&mut bus, tick, fresh.then_some(&b), &[]), []);
        assert_eq!(
            state_of(&bus.end(deadline(tick))),
            LimbState::Active,
            "tick {tick}"
        );
    }
    assert_eq!(
        run_tick(&mut bus, 4, None, &[]),
        [(0, SendKind::Disable), (1, SendKind::Disable)]
    );
    assert_eq!(
        stop_of(&bus.end(deadline(4))),
        Some(StopReason::ControlSilent)
    );
}

/// Guards: safety - ticks a stalled thread slept through are each a missed deadline and stop an active bus as a late
/// wake would, Disables on the next tick it runs; an idle bus counts them and, as for a late wake, holds that tick's
/// commands; none skipped is no news (PLAN.md item 3: missed deadlines are counted, never skipped silently).
#[test]
fn skipped_ticks_are_missed_deadlines_and_stop_the_bus() {
    let mut bus = bus();
    run_tick(&mut bus, 0, None, &[]);
    let _ = bus.end(deadline(0));
    // Idle: counted, nothing to stop, and the Enable held for that tick only.
    bus.skipped(2);
    let enable = |tick| batch(tick, &[Some(encode::enable(id(101))), None]);
    assert_eq!(run_tick(&mut bus, 3, Some(&enable(3)), &[]), []);
    let snap = bus.end(deadline(3));
    assert_eq!(
        (
            state_of(&snap),
            stop_of(&snap),
            snap.counters.missed_deadlines,
            snap.counters.held_batches
        ),
        (LimbState::Idle, None, 2, 1)
    );
    bus.skipped(0);
    let sent = run_tick(&mut bus, 4, Some(&enable(4)), &[]);
    assert_eq!(sent, [(0, SendKind::Command)]);
    let snap = bus.end(deadline(4));
    assert_eq!(
        (state_of(&snap), snap.counters.missed_deadlines),
        (LimbState::Active, 2)
    );
    // The thread wakes after tick 4 to find ticks 5 to 7 already past: tick 8 runs on time, as a stop.
    bus.skipped(3);
    let sent = run_tick(&mut bus, 8, Some(&batch(8, &[None, None])), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(8));
    assert_eq!(
        (stop_of(&snap), snap.counters.missed_deadlines),
        (Some(StopReason::LateWake), 5)
    );
}

/// Guards: safety - bus-off is latched on the first error frame and nothing later clears it (PLAN.md item 3, item 6
/// Bus-off row).
#[test]
fn bus_off_latches_stopped() {
    let mut bus = bus();
    // An error frame: CAN_ERR_FLAG with the bus-off class bit (linux/can/error.h CAN_ERR_BUSOFF 0x40).
    let off = error_frame(0x40, 0);
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(101))), None])),
        &[(MS, off)],
    );
    let snap = bus.end(PERIOD * 6 / 10);
    assert_eq!(state_of(&snap), LimbState::Stopped);
    assert_eq!(stop_of(&snap), Some(StopReason::Bus(BusError::BusOff)));
    // Nothing could be sent on it: every drive is recorded as never sent, left to time out.
    assert!(
        snap.drives().all(|d| d.stop == StopOutcome::NeverSent),
        "{snap:?}"
    );
    assert_eq!(
        (snap.bus_error, snap.healthy),
        (Some(BusError::BusOff), false)
    );
    // The adapter comes back and drives answer; the bus stays stopped and sends nothing.
    assert_eq!(
        run_tick(
            &mut bus,
            1,
            Some(&batch(1, &[Some(encode::enable(id(101))), None])),
            &[(MS, status(101, Mode::Run))]
        ),
        []
    );
    assert_eq!(
        state_of(&bus.end(PERIOD + PERIOD * 6 / 10)),
        LimbState::Stopped
    );

    // Any socket failure latches, whatever its error: a socket that can't send can't stop the drives either.
    for error in [BusError::TxTimeout, BusError::Other(0x08)] {
        let mut bus = common::bus();
        bus.lost_bus(error);
        let snap = bus.end(0);
        assert_eq!(
            (state_of(&snap), snap.bus_error),
            (LimbState::Stopped, Some(error))
        );
    }
}

/// Enable both drives at tick 0 and stop at tick 1; returns the stop's first sends.
fn enabled_then_stopped(bus: &mut BusTick) -> Vec<(usize, SendKind)> {
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
    bus.request_stop();
    let list = bus.begin(1, PERIOD, PERIOD, None);
    for (i, _) in list.iter().enumerate() {
        bus.sent(i, SendOutcome::Sent, PERIOD);
    }
    list.iter().map(|s| (s.slot, s.kind)).collect()
}

/// Guards: safety - a Reset read after the stop's Disable confirms it even when an earlier Run status, still in flight,
/// was read first (PLAN.md item 2 Stop: enable replies take up to 10.3 ms, past a 4 ms period).
#[test]
fn a_reset_behind_an_earlier_status_still_confirms() {
    let mut bus = bus();
    enabled_then_stopped(&mut bus);
    bus.on_frame(PERIOD + MS, &status(101, Mode::Run));
    bus.on_frame(PERIOD + 2 * MS, &status(101, Mode::Reset));
    assert_eq!(at(&bus.end(deadline(1)), 0).stop, StopOutcome::Confirmed);
}

/// Guards: safety - each drive's active reporting off goes out once its post-Disable silence is over (drives drop every
/// frame in it), is planned again until the socket takes it, and the stop ends early only when every drive is
/// confirmed and has it (PLAN.md item 2 Stop and Exit: "reporting persists across host processes otherwise").
#[test]
fn reporting_off_waits_out_the_silence_and_is_retried_until_sent() {
    let mut bus = bus();
    assert_eq!(
        enabled_then_stopped(&mut bus),
        [(0, SendKind::Disable), (1, SendKind::Disable)]
    );
    bus.on_frame(PERIOD + MS, &status(101, Mode::Reset));
    bus.on_frame(PERIOD + MS, &status(102, Mode::Reset));
    assert!(
        matches!(state_of(&bus.end(deadline(1))), LimbState::Stopping { .. }),
        "confirmed, reporting still on"
    );
    // Inside the 50 ms silence after the confirmations (read at 5 ms) nothing more is sent.
    let mut tick = 2;
    while tick * PERIOD < 55 * MS {
        assert_eq!(run_tick(&mut bus, tick, None, &[]), [], "tick {tick}");
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    // The first tick past it plans reporting off for both; the socket takes only drive 101's.
    let list = bus.begin(tick, tick * PERIOD, tick * PERIOD, None);
    let kinds: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
    assert_eq!(
        kinds,
        [(0, SendKind::ReportingOff), (1, SendKind::ReportingOff)]
    );
    bus.sent(0, SendOutcome::Sent, tick * PERIOD);
    bus.sent(1, SendOutcome::QueueFull, tick * PERIOD);
    assert!(matches!(
        state_of(&bus.end(deadline(tick))),
        LimbState::Stopping { .. }
    ));
    // Next tick: only drive 102's again; once taken, the stop is over before its 100 ms.
    tick += 1;
    assert_eq!(
        run_tick(&mut bus, tick, None, &[]),
        [(1, SendKind::ReportingOff)]
    );
    let snap = bus.end(deadline(tick));
    assert_eq!(state_of(&snap), LimbState::Stopped);
    assert!(deadline(tick) < PERIOD + 100 * MS);
    assert!(
        snap.drives()
            .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent)
    );
}

/// Guards: safety - reporting off goes to a drive only once the silence after its own confirmation is over; a drive that
/// never confirms is still getting a Disable every tick, so it never leaves its silence and gets none (PLAN.md item 2
/// Silence windows: a drive drops every frame in it).
#[test]
fn reporting_off_follows_each_drives_own_confirmation() {
    let mut bus = bus();
    enabled_then_stopped(&mut bus);
    let _ = bus.end(deadline(1));
    let silence = bus.timing().disable_silence_ns;
    // Drive 101 confirms late, read 1 ms into tick 6; drive 102 never answers.
    let confirmed_ns = 6 * PERIOD + MS;
    let mut off_sent = false;
    let mut tick = 2;
    let snap = loop {
        let replies = if tick == 6 {
            vec![(MS, status(101, Mode::Reset))]
        } else {
            vec![]
        };
        let sent = run_tick(&mut bus, tick, None, &replies);
        let snap = bus.end(deadline(tick));
        if state_of(&snap) == LimbState::Stopped {
            assert_eq!(sent, [], "tick {tick}: the stop window is over");
            break snap;
        }
        let mut expected = vec![];
        if tick <= 6 {
            expected.push((0, SendKind::Disable));
        }
        expected.push((1, SendKind::Disable));
        if tick > 6 && !off_sent && tick * PERIOD >= confirmed_ns + silence {
            expected.push((0, SendKind::ReportingOff));
            off_sent = true;
        }
        assert_eq!(sent, expected, "tick {tick}");
        tick += 1;
    };
    assert!(
        off_sent,
        "drive 101's reporting off went out inside the stop window"
    );
    assert_eq!(
        (at(&snap, 0).stop, at(&snap, 0).reporting_off_sent),
        (StopOutcome::Confirmed, true)
    );
    assert_eq!(
        (at(&snap, 1).stop, at(&snap, 1).reporting_off_sent),
        (StopOutcome::Sent, false)
    );
}

/// Guards: safety - a drive confirmed late in the stop window still gets its reporting off once its silence is over:
/// Disables end with the window, and the stop runs on only while a confirmed drive waits for its reporting off
/// (PLAN.md item 2 Exit: reporting persists across host processes otherwise).
#[test]
fn a_drive_confirmed_late_still_gets_reporting_off() {
    let mut bus = bus();
    enabled_then_stopped(&mut bus);
    // Drive 102 confirms at once; drive 101 only in the window's last tick (stop at 4 ms, window 100 ms).
    bus.on_frame(PERIOD + MS, &status(102, Mode::Reset));
    let _ = bus.end(deadline(1));
    let last = (PERIOD + 100 * MS) / PERIOD - 1;
    let mut tick = 2;
    while tick <= last {
        let replies = if tick == last {
            vec![(MS, status(101, Mode::Reset))]
        } else {
            vec![]
        };
        run_tick(&mut bus, tick, None, &replies);
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    let confirmed_ns = last * PERIOD + MS;
    // Past the window: no more Disables, and drive 101's reporting off once its own silence is over.
    let mut off_at = None;
    let snap = loop {
        let sent = run_tick(&mut bus, tick, None, &[]);
        let snap = bus.end(deadline(tick));
        if !sent.is_empty() {
            assert_eq!(sent, [(0, SendKind::ReportingOff)], "tick {tick}");
            off_at = Some(tick * PERIOD);
        }
        if state_of(&snap) == LimbState::Stopped {
            break snap;
        }
        assert!(tick < 100, "the stop ends");
        tick += 1;
    };
    let off_at = off_at.expect("drive 101's reporting off went out");
    assert!(off_at >= confirmed_ns + 50 * MS && off_at < confirmed_ns + 50 * MS + PERIOD);
    assert!(
        snap.drives()
            .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent),
        "{snap:?}"
    );
}

/// Guards: safety - a bus error during a stop is kept for the safety layer even though the stop's reason stays what
/// started it (PLAN.md item 6: bus-off or a lost bus faults every active run).
#[test]
fn a_bus_error_during_a_stop_is_kept() {
    let mut bus = bus();
    enabled_then_stopped(&mut bus);
    bus.lost_bus(BusError::InterfaceGone);
    let snap = bus.end(deadline(1));
    assert_eq!(state_of(&snap), LimbState::Stopped);
    assert_eq!(stop_of(&snap), Some(StopReason::Requested));
    assert_eq!(
        (snap.bus_error, snap.healthy),
        (Some(BusError::InterfaceGone), false)
    );
    // A later error doesn't replace the first.
    bus.on_frame(PERIOD + 3 * MS, &error_frame(0x40, 0));
    assert_eq!(
        bus.end(deadline(1)).bus_error,
        Some(BusError::InterfaceGone)
    );
}

/// Guards: safety - a Disable control sends in a batch isn't a stop: its Reset reply records no stop outcome (PLAN.md
/// item 2 Stop records what each stop achieved).
#[test]
fn a_disable_from_control_is_not_a_stop() {
    let mut bus = bus();
    let enable = batch(0, &[Some(encode::enable(id(101))), None]);
    run_tick(&mut bus, 0, Some(&enable), &[(MS, status(101, Mode::Run))]);
    let _ = bus.end(deadline(0));
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(encode::disable(id(101))), None])),
        &[(MS, status(101, Mode::Reset))],
    );
    let snap = bus.end(deadline(1));
    assert_eq!(
        (stop_of(&snap), at(&snap, 0).stop),
        (None, StopOutcome::None)
    );
}

/// Guards: safety - a backlog stops the bus without hiding an earlier reason, and once a drain leaves frames queued the
/// statuses read answer and confirm nothing, since they may predate the Disables, until a drain empties the socket
/// (PLAN.md item 3).
#[test]
fn a_backlog_stops_and_its_unordered_reads_confirm_nothing() {
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
    bus.request_stop();
    bus.drained(Drain::Unemptied);
    // An old Reset status still queued from before the enable is read after the Disables.
    run_tick(&mut bus, 1, None, &[(MS, status(101, Mode::Reset))]);
    let snap = bus.end(deadline(1));
    assert_eq!(stop_of(&snap), Some(StopReason::Requested));
    assert_eq!(
        at(&snap, 0).stop,
        StopOutcome::Sent,
        "not confirmed by a frame that may predate the Disable"
    );
    assert_eq!(
        at(&snap, 0).observed.map(|o| o.status.header.mode),
        Some(Mode::Reset),
        "but still seen"
    );
    // The next tick's drain reads another queued Reset and again leaves frames: still unordered.
    bus.on_frame(2 * PERIOD, &status(101, Mode::Reset));
    bus.drained(Drain::Unemptied);
    run_tick(&mut bus, 2, None, &[(MS, status(101, Mode::Reset))]);
    assert_eq!(at(&bus.end(deadline(2)), 0).stop, StopOutcome::Sent);
    // The drain that empties the socket still read backlog, so its frames confirm nothing; what comes after the send
    // does: the re-sent Disable's Reset confirms.
    bus.on_frame(3 * PERIOD, &status(101, Mode::Reset));
    bus.drained(Drain::Emptied);
    assert_eq!(at(&bus.end(3 * PERIOD), 0).stop, StopOutcome::Sent);
    run_tick(&mut bus, 3, None, &[(MS, status(101, Mode::Reset))]);
    assert_eq!(at(&bus.end(deadline(3)), 0).stop, StopOutcome::Confirmed);
}

/// Guards: safety - a drain that read more than the shell may stops an active bus, but having emptied the socket it
/// orders the reads again: a Reset after the send confirms. On an idle bus nothing is enabled, so a backlog stops
/// nothing, but no Enable goes out on a tick whose reads can't be trusted (PLAN.md item 3).
#[test]
fn an_emptied_backlog_stops_but_orders_the_reads_again() {
    let mut bus = bus();
    bus.drained(Drain::Backlog);
    let enable = batch(0, &[Some(encode::enable(id(101))), None]);
    assert_eq!(run_tick(&mut bus, 0, Some(&enable), &[]), []);
    let snap = bus.end(deadline(0));
    assert_eq!(
        (state_of(&snap), snap.counters.held_batches),
        (LimbState::Idle, 1)
    );
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(encode::enable(id(101))), None])),
        &[(MS, status(101, Mode::Run))],
    );
    let _ = bus.end(deadline(1));
    bus.drained(Drain::Backlog);
    let sent = run_tick(&mut bus, 2, Some(&batch(2, &[Some(hold(101)), None])), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    assert_eq!(
        (stop_of(&snap), at(&snap, 0).stop),
        (Some(StopReason::Backlog), StopOutcome::Sent)
    );
    bus.drained(Drain::Backlog);
    run_tick(&mut bus, 3, None, &[(MS, status(101, Mode::Reset))]);
    assert_eq!(at(&bus.end(deadline(3)), 0).stop, StopOutcome::Confirmed);
}

/// Guards: safety - a stop asked for is never lost to a backlog: on an idle bus, whichever came first and whichever way
/// the drain ended, the requested stop is taken and no Enable goes out (PLAN.md item 6: a stop is always accepted).
#[test]
fn a_backlog_never_swallows_a_requested_stop() {
    for drain in [Drain::Backlog, Drain::Unemptied] {
        for stop_first in [false, true] {
            let mut bus = bus();
            if stop_first {
                bus.request_stop();
                bus.drained(drain);
            } else {
                bus.drained(drain);
                bus.request_stop();
            }
            let enable = batch(0, &[Some(encode::enable(id(101))), None]);
            assert_eq!(
                run_tick(&mut bus, 0, Some(&enable), &[]),
                [(0, SendKind::Disable), (1, SendKind::Disable)],
                "{drain:?}, stop first: {stop_first}"
            );
            assert_eq!(stop_of(&bus.end(deadline(0))), Some(StopReason::Requested));
        }
    }
}

/// Run ticks from `from` with no batch, at most 100, until the bus is stopped: every Disable taken by the socket, every
/// reporting off given `outcome`, and each of `replies` (tick, offset, frame) read in its tick. Returns each reporting
/// off planned, as (tick, slot), and the snapshot that showed the bus stopped, if one did.
fn stop_until_stopped(
    bus: &mut BusTick,
    from: u64,
    replies: &[(u64, u64, FrameRecord)],
    outcome: SendOutcome,
) -> (Vec<(u64, usize)>, Option<can::Snapshot>) {
    let mut offs = vec![];
    for tick in from..from + 100 {
        let start = tick * PERIOD;
        let list = bus.begin(tick, start, start, None);
        for (index, send) in list.iter().enumerate() {
            if send.kind == SendKind::ReportingOff {
                offs.push((tick, send.slot));
                bus.sent(index, outcome, start);
            } else {
                bus.sent(index, SendOutcome::Sent, start);
            }
        }
        for (_, offset, frame) in replies.iter().filter(|(t, _, _)| *t == tick) {
            bus.on_frame(start + offset, frame);
        }
        let snap = bus.end(deadline(tick));
        if state_of(&snap) == LimbState::Stopped {
            return (offs, Some(snap));
        }
    }
    (offs, None)
}

/// Both drives enabled at tick 0, then a stop asked for and begun 0.1 ms into tick 1, off the tick's start; drive 102
/// confirms at once.
fn stopped_off_tick() -> BusTick {
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
    bus.request_stop();
    let list = bus.begin(1, PERIOD + MS / 10, PERIOD, None);
    for index in 0..list.len() {
        bus.sent(index, SendOutcome::Sent, PERIOD + MS / 10);
    }
    bus.on_frame(PERIOD + MS, &status(102, Mode::Reset));
    let _ = bus.end(deadline(1));
    bus
}

/// Guards: safety - a drive confirmed by a Reset read just after the stop window still gets its reporting off, even
/// when it falls due after the window, the silence and a period from the stop's start: the stop at 4.1 ms, drive 101's
/// Reset read at 106.1 ms (2 ms after the last Disable), its reporting off due at 156.1 ms and sent at tick 40, 160 ms
/// (PLAN.md item 2 Exit: reporting persists across host processes otherwise; replies take 1.4 to 10.3 ms).
#[test]
fn a_reset_read_after_the_window_still_gets_reporting_off() {
    let mut bus = stopped_off_tick();
    let reset = status(101, Mode::Reset);
    let (offs, snap) = stop_until_stopped(
        &mut bus,
        2,
        &[(26, 2 * MS + MS / 10, reset)],
        SendOutcome::Sent,
    );
    assert_eq!(offs, [(14, 1), (40, 0)]);
    let snap = snap.expect("the stop ends");
    assert!(
        snap.drives()
            .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent),
        "{snap:?}"
    );
}

/// Guards: safety - a reporting off the queue keeps refusing doesn't hold a stop open: once it has been tried and a
/// period has passed since it fell due, the bus is stopped, with the reporting off recorded as not sent (PLAN.md item
/// 2 Stop: a full queue drops the frame and counts it).
#[test]
fn a_reporting_off_never_taken_ends_the_stop() {
    let mut bus = stopped_off_tick();
    let reset = status(101, Mode::Reset);
    let (offs, snap) = stop_until_stopped(
        &mut bus,
        2,
        &[(26, 2 * MS + MS / 10, reset)],
        SendOutcome::QueueFull,
    );
    let snap = snap.expect("the stop ends");
    assert_eq!(
        offs.iter()
            .filter(|(_, slot)| *slot == 0)
            .map(|(t, _)| *t)
            .collect::<Vec<_>>(),
        [40],
        "tried once, inside its period"
    );
    assert_eq!(snap.tick, 40);
    assert!(snap.drives().all(|d| !d.reporting_off_sent), "{snap:?}");
}
