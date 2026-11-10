//! Ticks the bus can't trust, without a socket: a late wake, ticks a stall slept through, a backlog in the drain. What
//! each stops, what an idle limb still sends and holds, and what its reads may confirm (PLAN.md item 3).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{CommandBatch, Drain, LimbState, Send, SendKind, SendOutcome, StopOutcome, StopReason};
use common::{
    MS, PERIOD, at, batch, bus, deadline, hold, id, limb, run_tick, state_of, status, stop_of,
    two_limbs,
};
use robstride::Mode;
use robstride::encode::{self, Reporting};

/// Guards: safety - a thread that wakes past its send window stops an active limb at once instead of sending motion, and
/// sends the Disables on that same tick: a late Disable is still the right one. The missed deadline is counted. A late
/// tick's stop keeps the reason that came first: a requested stop, then a backlog in its drain. Only the active limbs
/// stop: an idle limb on the same bus holds (PLAN.md item 3; can.md section 2, a stop names its scope).
#[test]
fn a_late_wake_stops_the_bus() {
    let mut bus = bus();
    let late_enable = batch(0, &[Some(encode::enable(id(101))), None]);
    run_tick(&mut bus, 0, Some(&late_enable), &[]);
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
    assert_eq!(snap.counters.missed_deadlines, 1);

    // On a late tick, a stop asked for before it keeps its own reason, and so does a backlog in its drain.
    for (requested, reason) in [(true, StopReason::Requested), (false, StopReason::Backlog)] {
        let mut bus = common::bus();
        run_tick(&mut bus, 0, Some(&late_enable), &[]);
        let _ = bus.end(deadline(0));
        if requested {
            bus.request_stop();
        } else {
            bus.drained(Drain::Backlog);
        }
        let _ = bus.begin(1, PERIOD + 2 * MS, PERIOD, None);
        assert_eq!(stop_of(&bus.end(deadline(1))), Some(reason));
    }

    // With one limb active and one idle, a late wake stops only the active one: the idle one holds its Enable.
    let mut bus = two_limbs();
    run_tick(
        &mut bus,
        0,
        Some(&late_enable),
        &[(MS, status(101, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    let both = batch(1, &[Some(hold(101)), Some(encode::enable(id(102)))]);
    assert_eq!(
        bus.begin(1, PERIOD + 2 * MS, PERIOD, Some(&both))
            .iter()
            .collect::<Vec<_>>(),
        [disable(0, 101)]
    );
    let snap = bus.end(deadline(1));
    assert!(matches!(
        limb(&snap, 0),
        (LimbState::Stopping { .. }, Some(StopReason::LateWake))
    ));
    assert_eq!(
        (limb(&snap, 1), snap.counters.held_batches),
        ((LimbState::Idle, None), 1)
    );
}

/// Guards: safety - a late wake, ticks a stall slept through, or a drain backlog doesn't stop an idle limb, but on that
/// tick only its batch's Disables and reporting off go out, late as they are (can.md section 2), and the rest is held,
/// so nothing is enabled on a tick whose reads can't be trusted; the missed deadlines are counted. A wake so late that
/// the batch has expired still sends them, counting the batch stale rather than held (PLAN.md item 3).
#[test]
fn an_idle_bus_holds_all_but_disables_and_reporting_off_on_an_untrusted_tick() {
    let off = encode::active_reporting(id(102), Reporting::Off);
    let disable = encode::disable(id(102));
    // (name, ticks skipped, woken at, drain, the frame that still goes, missed deadlines, held, stale)
    let rows = [
        ("late wake", 0, 2 * MS, Drain::Emptied, disable, 1, 1, 0),
        (
            "late wake past the batch's expiry",
            0,
            PERIOD + MS,
            Drain::Emptied,
            disable,
            1,
            0,
            1,
        ),
        ("stall", 2, 0, Drain::Emptied, disable, 2, 1, 0),
        ("backlog", 0, 0, Drain::Backlog, off, 0, 1, 0),
        ("backlog left queued", 0, 0, Drain::Unemptied, off, 0, 1, 0),
    ];
    for (name, skipped, woke, drain, kept, missed, held, stale) in rows {
        let mut bus = bus();
        bus.skipped(skipped);
        bus.drained(drain);
        let b = batch(0, &[Some(encode::enable(id(101))), Some(kept)]);
        assert_eq!(
            bus.begin(0, woke, 0, Some(&b)).iter().collect::<Vec<_>>(),
            [Send {
                slot: 1,
                kind: SendKind::Command,
                frame: kept,
                expires: false,
            }],
            "{name}"
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
            (LimbState::Idle, None, missed, held, stale),
            "{name}"
        );
    }
}

/// Guards: safety - an idle limb's held tick checks its batch against the freshness its drain stamped, holds any motion
/// in it unsent without stopping, then clears that freshness; a status read after the tick's sends counts again unless
/// the drain left frames queued. So motion on a later tick, before such a status, is refused as expired feedback
/// rather than sent on a status whose real age the tick can't bound (PLAN.md item 3, item 6 Silence row;
/// units-and-frames.md section 5).
#[test]
fn a_held_tick_clears_the_freshness_its_drain_stamped() {
    // (row, woken at, drain, whether drive 102's Reset read after the held Disable counts)
    let rows = [
        ("late wake", PERIOD + 2 * MS, Drain::Emptied, true),
        ("backlog", PERIOD, Drain::Backlog, true),
        ("backlog left queued", PERIOD, Drain::Unemptied, false),
    ];
    for (name, woke, drain, counts) in rows {
        let mut bus = bus();
        // Idle: control disables both drives at tick 0; drive 101's Reset is read only in tick 1's drain.
        let disable = [
            Some(encode::disable(id(101))),
            Some(encode::disable(id(102))),
        ];
        run_tick(&mut bus, 0, Some(&batch(0, &disable)), &[]);
        let _ = bus.end(deadline(0));
        bus.on_frame(woke, &status(101, Mode::Reset));
        bus.drained(drain);
        // The held tick's batch moves drive 101 on that status and disables drive 102: the motion passes its check
        // and is held, not sent, and the limb doesn't stop; the Disable goes, and 102's Reset is read after it.
        let held = batch(1, &[Some(hold(101)), Some(encode::disable(id(102)))]);
        let list = bus.begin(1, woke, PERIOD, Some(&held));
        let sent: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
        assert_eq!(sent, [(1, SendKind::Command)], "{name}");
        bus.sent(0, SendOutcome::Sent, woke);
        bus.on_frame(deadline(1), &status(102, Mode::Reset));
        let snap = bus.end(deadline(1));
        assert_eq!(
            (state_of(&snap), stop_of(&snap), snap.counters.held_batches),
            (LimbState::Idle, None, 1),
            "{name}"
        );
        let fresh_102 = counts.then_some(deadline(1));
        let (a, b) = (at(&snap, 0), at(&snap, 1));
        assert_eq!(
            (a.fresh_ns, a.fresh_status.is_some()),
            (None, false),
            "{name}"
        );
        assert_eq!(
            (b.fresh_ns, b.fresh_status.map(|f| f.read_ns)),
            (fresh_102, fresh_102),
            "{name}"
        );
        // Tick 2, on time: drive 101's status is 4 ms old or less by read time, but motion on it stops the limb.
        let sent = run_tick(&mut bus, 2, Some(&batch(2, &[Some(hold(101)), None])), &[]);
        assert_eq!(
            sent,
            [(0, SendKind::Disable), (1, SendKind::Disable)],
            "{name}"
        );
        assert_eq!(
            stop_of(&bus.end(deadline(2))),
            Some(StopReason::ExpiredFeedback { slot: 0 }),
            "{name}"
        );
    }
}

/// Guards: safety - ticks a stalled thread slept through are each a missed deadline and stop an active limb as a late
/// wake would, Disables on the next tick it runs; none skipped is no news (PLAN.md item 3: missed deadlines are counted,
/// never skipped silently). An idle limb's hold on a stall is in the hold table above.
#[test]
fn skipped_ticks_are_missed_deadlines_and_stop_the_bus() {
    let mut bus = bus();
    let enable = batch(0, &[Some(encode::enable(id(101))), None]);
    run_tick(&mut bus, 0, Some(&enable), &[(MS, status(101, Mode::Run))]);
    let _ = bus.end(deadline(0));
    bus.skipped(0);
    let sent = run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(hold(101)), None])),
        &[(MS, status(101, Mode::Run))],
    );
    assert_eq!(sent, [(0, SendKind::Command)]);
    let snap = bus.end(deadline(1));
    assert_eq!(
        (state_of(&snap), snap.counters.missed_deadlines),
        (LimbState::Active, 0)
    );
    // The thread wakes after tick 1 to find ticks 2 to 4 already past: tick 5 runs on time, as a stop.
    bus.skipped(3);
    let sent = run_tick(&mut bus, 5, Some(&batch(5, &[None, None])), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(5));
    assert_eq!(
        (stop_of(&snap), snap.counters.missed_deadlines),
        (Some(StopReason::LateWake), 3)
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
/// orders the reads again: a Reset after the send confirms (PLAN.md item 3).
#[test]
fn an_emptied_backlog_stops_but_orders_the_reads_again() {
    let mut bus = bus();
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
