//! The stop path without a socket: what a stop sends, what confirms it, and when it is over (PLAN.md item 2 Stop, item 3).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{BusError, BusState, BusTick, SendKind, SendOutcome, StopOutcome, StopReason};
use common::{MS, PERIOD, at, batch, bus, deadline, error_frame, hold, id, run_tick, status};
use robstride::{Mode, encode};

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
    // Tick 2: still nothing fresh, so the bus stops: Disable to each drive (reporting off waits out the silence).
    let sent = run_tick(&mut bus, 2, None, &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(2 * PERIOD + PERIOD * 6 / 10);
    assert!(matches!(snap.state, BusState::Stopping { .. }));
    assert_eq!(snap.stop, Some(StopReason::ControlSilent));
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
    // Disables that went unanswered aren't missed replies (PLAN.md item 2 Silence windows).
    assert_eq!(snap.counters.unanswered, 0);
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

/// Guards: safety - a thread that wakes past its send window stops at once instead of sending motion, and sends the
/// Disables on that same tick: a late Disable is still the right one (PLAN.md item 3).
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
    let kinds: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
    assert_eq!(kinds, [(0, SendKind::Disable), (1, SendKind::Disable)]);
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
    let off = error_frame(0x40, 0);
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[Some(encode::enable(id(11))), None])),
        &[(MS, off)],
    );
    let snap = bus.end(PERIOD * 6 / 10);
    assert_eq!(snap.state, BusState::Stopped);
    assert_eq!(snap.stop, Some(StopReason::Bus(BusError::BusOff)));
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
            Some(&batch(1, &[Some(encode::enable(id(11))), None])),
            &[(MS, status(11, Mode::Run))]
        ),
        []
    );
    assert_eq!(bus.end(PERIOD + PERIOD * 6 / 10).state, BusState::Stopped);
}

/// Enable both drives at tick 0 and stop at tick 1; returns the stop's first sends.
fn enabled_then_stopped(bus: &mut BusTick) -> Vec<(usize, SendKind)> {
    let enable = batch(
        0,
        &[Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
    );
    run_tick(
        bus,
        0,
        Some(&enable),
        &[(MS, status(11, Mode::Run)), (MS, status(12, Mode::Run))],
    );
    let _ = bus.end(deadline(0));
    bus.request_stop();
    let list = bus.begin(1, PERIOD, PERIOD, None);
    for (i, _) in list.iter().enumerate() {
        bus.sent(i, SendOutcome::Sent);
    }
    list.iter().map(|s| (s.slot, s.kind)).collect()
}

/// Guards: safety - a Reset read after the stop's Disable confirms it even when an earlier Run status, still in flight,
/// was read first (PLAN.md item 2 Stop: enable replies take up to 10.3 ms, past a 4 ms period).
#[test]
fn a_reset_behind_an_earlier_status_still_confirms() {
    let mut bus = bus();
    enabled_then_stopped(&mut bus);
    bus.on_frame(PERIOD + MS, &status(11, Mode::Run));
    bus.on_frame(PERIOD + 2 * MS, &status(11, Mode::Reset));
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
    bus.on_frame(PERIOD + MS, &status(11, Mode::Reset));
    bus.on_frame(PERIOD + MS, &status(12, Mode::Reset));
    assert!(
        matches!(bus.end(deadline(1)).state, BusState::Stopping { .. }),
        "confirmed, reporting still on"
    );
    // Inside the 50 ms silence after the confirmations (read at 5 ms) nothing more is sent.
    let mut tick = 2;
    while tick * PERIOD < 55 * MS {
        assert_eq!(run_tick(&mut bus, tick, None, &[]), [], "tick {tick}");
        let _ = bus.end(deadline(tick));
        tick += 1;
    }
    // The first tick past it plans reporting off for both; the socket takes only drive 11's.
    let list = bus.begin(tick, tick * PERIOD, tick * PERIOD, None);
    let kinds: Vec<_> = list.iter().map(|s| (s.slot, s.kind)).collect();
    assert_eq!(
        kinds,
        [(0, SendKind::ReportingOff), (1, SendKind::ReportingOff)]
    );
    bus.sent(0, SendOutcome::Sent);
    bus.sent(1, SendOutcome::QueueFull);
    assert!(matches!(
        bus.end(deadline(tick)).state,
        BusState::Stopping { .. }
    ));
    // Next tick: only drive 12's again; once taken, the stop is over before its 100 ms.
    tick += 1;
    assert_eq!(
        run_tick(&mut bus, tick, None, &[]),
        [(1, SendKind::ReportingOff)]
    );
    let snap = bus.end(deadline(tick));
    assert_eq!(snap.state, BusState::Stopped);
    assert!(deadline(tick) < PERIOD + 100 * MS);
    assert!(
        snap.drives()
            .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent)
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
    assert_eq!(snap.state, BusState::Stopped);
    assert_eq!(snap.stop, Some(StopReason::Requested));
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
    let enable = batch(0, &[Some(encode::enable(id(11))), None]);
    run_tick(&mut bus, 0, Some(&enable), &[(MS, status(11, Mode::Run))]);
    let _ = bus.end(deadline(0));
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(encode::disable(id(11))), None])),
        &[(MS, status(11, Mode::Reset))],
    );
    let snap = bus.end(deadline(1));
    assert_eq!((snap.stop, at(&snap, 0).stop), (None, StopOutcome::None));
}

/// Guards: safety - a backlog stops the bus without hiding an earlier reason, and when the socket couldn't be emptied
/// the tick's statuses answer and confirm nothing, since they may predate its Disables (PLAN.md item 3).
#[test]
fn a_backlog_stops_and_its_unordered_reads_confirm_nothing() {
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
    bus.request_stop();
    bus.backlog(false);
    // An old Reset status still queued from before the enable is read after the Disables.
    run_tick(&mut bus, 1, None, &[(MS, status(11, Mode::Reset))]);
    let snap = bus.end(deadline(1));
    assert_eq!(snap.stop, Some(StopReason::Requested));
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
    // The next tick's reads are ordered again: the re-sent Disable's Reset confirms.
    run_tick(&mut bus, 2, None, &[(MS, status(11, Mode::Reset))]);
    assert_eq!(at(&bus.end(deadline(2)), 0).stop, StopOutcome::Confirmed);
}
