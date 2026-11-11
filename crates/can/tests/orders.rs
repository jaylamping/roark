//! Control's orders to a bus without a socket, where they add to `stop_limb`, `request_stop` and `rearm` (whose own
//! tests are in limbs.rs and rearm.rs): a stop order naming a limb the bus doesn't have stops the whole bus, a re-arm
//! is answered under its tag, and a clear never undoes a stop ordered before it.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{LimbState, MAX_DRIVES, Order, RearmRefused, Rearmed, SendKind, StopReason};
use common::{MS, PERIOD, batch, deadline, hold, limb, run_tick, running, status, two_limbs};
use robstride::Mode;

/// Guards: safety - `host.hang`: a stop order naming a limb the bus doesn't have can't be aimed, so it stops every
/// limb at the next plan, with no command to either, and is counted even when an earlier whole-bus stop already
/// names the stop (PLAN.md item 6 Hang row: a malformed order from control is treated as a bad batch).
#[test]
fn a_stop_order_for_a_limb_the_bus_lacks_stops_the_bus_and_is_counted() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopLimb(MAX_DRIVES), 2 * PERIOD), None);
    let holds = batch(2, &[Some(hold(101)), Some(hold(102))]);
    let sent = run_tick(&mut bus, 2, Some(&holds), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    let bad = StopReason::BadOrder { limb: MAX_DRIVES };
    for l in 0..2 {
        assert!(matches!(
            limb(&snap, l),
            (LimbState::Stopping { .. }, Some(reason)) if reason == bad
        ));
    }
    assert_eq!(snap.counters.bad_orders, 1);

    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopAll, 2 * PERIOD), None);
    assert_eq!(bus.order(Order::StopLimb(MAX_DRIVES), 2 * PERIOD), None);
    let _ = run_tick(&mut bus, 2, Some(&holds), &[]);
    let snap = bus.end(deadline(2));
    assert_eq!(
        limb(&snap, 0).1,
        Some(StopReason::Requested),
        "the first stop's reason stands"
    );
    assert_eq!(snap.counters.bad_orders, 1);
}

/// Two limbs running, then limb 0 stopped by order with drive 101 confirming Reset; the bus and the tick after the
/// stop ended.
fn limb_0_stopped() -> (can::BusTick, u64) {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopLimb(0), 2 * PERIOD), None);
    // Drive 101 confirms Reset at once; its limb is stopped once its reporting off has gone after the silence.
    let mut tick = 2;
    loop {
        let replies = [(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))];
        let holds = batch(tick, &[None, Some(hold(102))]);
        let _ = run_tick(&mut bus, tick, Some(&holds), &replies);
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped {
            return (bus, tick + 1);
        }
        tick += 1;
        assert!(tick < 100, "the stop ends inside its window");
    }
}

/// Guards: safety - the operator's clear by order: answered once, under its tag, with the re-arm's own outcome;
/// refused while a stop of the limb or the bus ordered before it waits for the plan, so a clear never undoes a stop
/// ordered before it; taken once the limb's stop has ended with its drive confirmed in Reset, and a stop ordered after
/// it stops the limb again (PLAN.md item 6: a latched stop clears only by an operator clear).
#[test]
fn a_rearm_order_is_answered_under_its_tag_and_never_undoes_an_earlier_stop() {
    let rearm = |tag| Order::Rearm { tag, limb: 0 };
    let answer = |tag, outcome| {
        Some(Rearmed {
            tag,
            limb: 0,
            outcome,
        })
    };
    for stop in [Order::StopLimb(0), Order::StopAll] {
        let (mut bus, tick) = limb_0_stopped();
        let now = tick * PERIOD;
        assert_eq!(bus.order(stop, now), None);
        assert_eq!(
            bus.order(rearm(7), now),
            answer(7, Err(RearmRefused::StopPending(0))),
            "{stop:?}"
        );
    }
    let (mut bus, tick) = limb_0_stopped();
    let now = tick * PERIOD;
    assert_eq!(bus.order(rearm(8), now), answer(8, Ok(())));
    assert_eq!(bus.order(Order::StopLimb(0), now), None);
    let holds = batch(tick, &[None, Some(hold(102))]);
    let sent = run_tick(&mut bus, tick, Some(&holds), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(tick));
    assert!(matches!(
        limb(&snap, 0),
        (LimbState::Stopping { .. }, Some(StopReason::LimbRequested))
    ));
    assert_eq!(snap.limb(0).map(|l| l.generation), Some(1));
}
