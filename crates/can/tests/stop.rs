//! The stop path without a socket: what a stop sends, what confirms it, and when it is over (PLAN.md item 2 Stop, item 3).
//! Ticks the bus can't trust are in `untrusted.rs`.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusError, BusTick, CommandBatch, LimbState, SendKind, SendOutcome, StopOutcome, StopReason,
    Timing,
};
use common::{
    MS, PERIOD, at, batch, bus, deadline, error_frame, hold, id, run_tick, state_of, status,
    stop_of,
};
use robstride::Mode;
use robstride::encode;

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

/// Guards: safety - bus-off is latched on the first error frame, and so is any socket failure passed to `lost_bus`;
/// nothing later clears it (PLAN.md item 3, item 6 Bus-off row).
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

    // Any socket failure latches, whatever its error: a socket that can't send can't stop the drives either. On an
    // active bus it ends the run at once, and nothing more is sent.
    for error in [
        BusError::TxTimeout,
        BusError::Other(0x08),
        BusError::InterfaceGone,
        BusError::Socket(5),
    ] {
        let mut bus = common::bus();
        bus.lost_bus(error);
        let snap = bus.end(0);
        assert_eq!(
            (state_of(&snap), snap.bus_error),
            (LimbState::Stopped, Some(error))
        );
        let mut bus = common::bus();
        let enable = batch(0, &[Some(encode::enable(id(101))), None]);
        run_tick(&mut bus, 0, Some(&enable), &[(MS, status(101, Mode::Run))]);
        assert_eq!(state_of(&bus.end(deadline(0))), LimbState::Active);
        bus.lost_bus(error);
        let enable = batch(1, &[Some(encode::enable(id(101))), None]);
        assert_eq!(run_tick(&mut bus, 1, Some(&enable), &[]), [], "{error:?}");
        let snap = bus.end(deadline(1));
        assert_eq!(
            (state_of(&snap), stop_of(&snap), snap.bus_error),
            (
                LimbState::Stopped,
                Some(StopReason::Bus(error)),
                Some(error)
            ),
            "{error:?}"
        );
        assert!(
            snap.drives().all(|d| d.stop == StopOutcome::NeverSent),
            "{snap:?}"
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

/// Guards: safety - a bus error during a stop is kept for the safety layer even though the stop's reason stays what
/// started it (PLAN.md item 6 Bus-off row: bus-off or a socket failure faults every active run).
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

/// What the socket does with a drive's reporting off in a row of `the_stop_ends_by_its_bound_whenever_drives_confirm`.
#[derive(Clone, Copy, Debug)]
enum Takes {
    /// Takes it at once.
    Always,
    /// Refuses it once (queue full), then takes it.
    SecondTry,
    /// Refuses it every time.
    Never,
}

/// One drive's stop in a row: the tick of its last Disable, the ticks its reporting off was planned, and its outcome.
type DriveStop = (u64, Vec<u64>, StopOutcome, bool);

/// A row: its name, each Reset read as (slot, read at), how the socket takes each drive's reporting off, the tick the
/// limb is stopped in, and each drive's stop.
type Row = (
    &'static str,
    Vec<(usize, u64)>,
    [Takes; 2],
    u64,
    [DriveStop; 2],
);

/// Guards: safety - a stop's end is bounded whenever its drives confirm (rust.md section 4: a limit on everything).
/// Disables go to each unconfirmed drive for the 100 ms window; a Reset read by the reply allowance (the window plus a
/// period) confirms, one read later doesn't and its drive gets no reporting off; each confirmed drive's reporting off
/// is planned every tick from 50 ms after its confirmation until the socket takes it, every Disable ahead of it; the
/// stop ends once every drive confirmed and took it, else once the allowance has closed and no confirmed drive's
/// reporting off is unsent, and at the latest 162 ms after it began, a reporting off never taken recorded unsent
/// (PLAN.md item 2 Stop and Exit: reporting persists across host processes otherwise; Silence windows).
#[test]
#[expect(
    clippy::too_many_lines,
    reason = "one table, one row per confirmation time and socket behaviour"
)]
fn the_stop_ends_by_its_bound_whenever_drives_confirm() {
    use StopOutcome::{Confirmed, Sent};
    // The stop begins at tick 1, 4 ms: Disables at ticks 1 to 25 (to 96 ms, under 4 + 100), confirmations read
    // before 108 ms (tick 27's start), the bound at 166 ms (tick 41's collect deadline).
    let timing = Timing::at_hz(250);
    assert_eq!(
        (timing.stop_replies_ns(), timing.stop_max_ns()),
        (104 * MS, 162 * MS)
    );
    // A read at a tick's start is in its drain, before the send; any other after it.
    let rows: [Row; 8] = [
        (
            "both confirmed at once: reporting off once the silence is over, then stopped",
            vec![(0, 5 * MS), (1, 5 * MS)],
            [Takes::Always, Takes::Always],
            14,
            [
                (1, vec![14], Confirmed, true),
                (1, vec![14], Confirmed, true),
            ],
        ),
        (
            "a reporting off refused once goes again the next tick",
            vec![(0, 5 * MS), (1, 5 * MS)],
            [Takes::Always, Takes::SecondTry],
            15,
            [
                (1, vec![14], Confirmed, true),
                (1, vec![14, 15], Confirmed, true),
            ],
        ),
        (
            "confirmed in the window's last tick",
            vec![(1, 5 * MS), (0, 101 * MS)],
            [Takes::Always, Takes::Always],
            38,
            [
                (25, vec![38], Confirmed, true),
                (1, vec![14], Confirmed, true),
            ],
        ),
        (
            "the last Disable's Reset, read in the next tick's drain, inside the allowance",
            vec![(1, 5 * MS), (0, 104 * MS)],
            [Takes::Always, Takes::Always],
            39,
            [
                (25, vec![39], Confirmed, true),
                (1, vec![14], Confirmed, true),
            ],
        ),
        (
            "a Reset read as the allowance closes confirms nothing",
            vec![(1, 5 * MS), (0, 108 * MS)],
            [Takes::Always, Takes::Always],
            27,
            [(25, vec![], Sent, false), (1, vec![14], Confirmed, true)],
        ),
        (
            "two drives confirm late, one after the other",
            vec![(1, 101 * MS), (0, 104 * MS)],
            [Takes::Always, Takes::Always],
            39,
            [
                (25, vec![39], Confirmed, true),
                (25, vec![38], Confirmed, true),
            ],
        ),
        (
            "a Reset read long after the allowance doesn't hold the stop open",
            vec![(1, 104 * MS), (0, 157 * MS)],
            [Takes::Always, Takes::Always],
            39,
            [(25, vec![], Sent, false), (25, vec![39], Confirmed, true)],
        ),
        (
            "the last drive that can confirm, its reporting off never taken: two tries, stopped at the bound",
            vec![(1, 5 * MS), (0, deadline(26))],
            [Takes::Never, Takes::Always],
            41,
            [
                (25, vec![40, 41], Confirmed, false),
                (1, vec![14], Confirmed, true),
            ],
        ),
    ];
    for (name, resets, takes, stopped_in, expected) in rows {
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
        let mut disables = [0; 2];
        let mut offs: [Vec<u64>; 2] = [vec![], vec![]];
        let mut tick = 1;
        let snap = loop {
            assert!(tick < 100, "{name}: the stop never ended");
            let start = tick * PERIOD;
            let reset = |&(slot, at): &(usize, u64)| {
                (at, status(101 + u8::try_from(slot).unwrap(), Mode::Reset))
            };
            let tick_of = |at: u64| at / PERIOD == tick;
            for (at, frame) in resets
                .iter()
                .filter(|(_, at)| tick_of(*at) && *at == start)
                .map(reset)
            {
                bus.on_frame(at, &frame);
            }
            let list = bus.begin(tick, start, start, None);
            let mut off_seen = false;
            for (index, send) in list.iter().enumerate() {
                assert_ne!(send.kind, SendKind::Command, "{name}: tick {tick}");
                let outcome = match send.kind {
                    SendKind::Disable => {
                        assert!(
                            !off_seen,
                            "{name}: tick {tick}: a Disable after a reporting off"
                        );
                        disables[send.slot] = tick;
                        SendOutcome::Sent
                    }
                    SendKind::ReportingOff => {
                        off_seen = true;
                        offs[send.slot].push(tick);
                        match takes[send.slot] {
                            Takes::Always => SendOutcome::Sent,
                            Takes::SecondTry if offs[send.slot].len() > 1 => SendOutcome::Sent,
                            Takes::SecondTry | Takes::Never => SendOutcome::QueueFull,
                        }
                    }
                    SendKind::Command => SendOutcome::Sent,
                };
                bus.sent(index, outcome, start);
            }
            for (at, frame) in resets
                .iter()
                .filter(|(_, at)| tick_of(*at) && *at != start)
                .map(reset)
            {
                bus.on_frame(at, &frame);
            }
            let snap = bus.end(deadline(tick));
            if state_of(&snap) == LimbState::Stopped {
                break snap;
            }
            tick += 1;
        };
        let got: Vec<DriveStop> = (0..2)
            .map(|slot| {
                let d = at(&snap, slot);
                (
                    disables[slot],
                    offs[slot].clone(),
                    d.stop,
                    d.reporting_off_sent,
                )
            })
            .collect();
        assert_eq!((snap.tick, got), (stopped_in, expected.to_vec()), "{name}");
    }
}
