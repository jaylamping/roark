//! Control's orders to a bus without a socket: a stop names its scope, an order naming a limb the bus doesn't have
//! stops the whole bus, and a re-arm is answered under its tag (step 7 design, D2: control asks for stops by order,
//! never with Disables in a batch).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{LimbState, MAX_DRIVES, Order, RearmRefused, Rearmed, SendKind, StopReason};
use common::{MS, PERIOD, batch, deadline, hold, limb, run_tick, running, status, two_limbs};
use robstride::Mode;

/// Guards: safety - control's stop orders stop the scope they name at the next tick's plan: one limb alone, or every
/// limb; an order naming a limb the bus doesn't have can't be aimed, so it stops every limb as `host.hang` would a bad
/// batch, and no command goes to either limb that tick (PLAN.md item 6: a stop names its scope; `host.hang`).
#[test]
fn stop_orders_stop_the_scope_they_name_and_a_bad_one_stops_the_bus() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopLimb(0), 2 * PERIOD), None);
    let holds = |tick| batch(tick, &[Some(hold(101)), Some(hold(102))]);
    let sent = run_tick(
        &mut bus,
        2,
        Some(&holds(2)),
        &[(MS, status(102, Mode::Run))],
    );
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Command)]);
    let snap = bus.end(deadline(2));
    assert!(matches!(
        limb(&snap, 0),
        (LimbState::Stopping { .. }, Some(StopReason::LimbRequested))
    ));
    assert_eq!(limb(&snap, 1), (LimbState::Active, None));

    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopAll, 2 * PERIOD), None);
    let sent = run_tick(&mut bus, 2, Some(&holds(2)), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    for l in 0..2 {
        assert!(matches!(
            limb(&snap, l),
            (LimbState::Stopping { .. }, Some(StopReason::Requested))
        ));
    }

    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(bus.order(Order::StopLimb(MAX_DRIVES), 2 * PERIOD), None);
    let sent = run_tick(&mut bus, 2, Some(&holds(2)), &[]);
    assert_eq!(sent, [(0, SendKind::Disable), (1, SendKind::Disable)]);
    let snap = bus.end(deadline(2));
    let bad = StopReason::BadOrder { limb: MAX_DRIVES };
    for l in 0..2 {
        assert!(matches!(
            limb(&snap, l),
            (LimbState::Stopping { .. }, Some(reason)) if reason == bad
        ));
    }
}

/// Guards: safety - a re-arm order is the operator's clear: it is answered once, under its tag, with the re-arm's own
/// outcome, refused while the limb runs and taken once the limb's stop has ended with every drive confirmed in Reset
/// (PLAN.md item 6: a latched stop clears only by an operator clear).
#[test]
fn a_rearm_order_is_answered_under_its_tag_with_the_rearms_outcome() {
    let mut bus = two_limbs();
    running(&mut bus);
    assert_eq!(
        bus.order(Order::Rearm { tag: 7, limb: 0 }, 2 * PERIOD),
        Some(Rearmed {
            tag: 7,
            limb: 0,
            outcome: Err(RearmRefused::NotStopped(0)),
        })
    );
    assert_eq!(bus.order(Order::StopLimb(0), 2 * PERIOD), None);
    // Drive 101 confirms Reset at once; its limb is stopped once its reporting off has gone after the silence.
    let mut tick = 2;
    loop {
        let replies = [(MS, status(101, Mode::Reset)), (MS, status(102, Mode::Run))];
        let _ = run_tick(
            &mut bus,
            tick,
            Some(&batch(tick, &[None, Some(hold(102))])),
            &replies,
        );
        let snap = bus.end(deadline(tick));
        if limb(&snap, 0).0 == LimbState::Stopped {
            break;
        }
        tick += 1;
        assert!(tick < 100, "the stop ends inside its window");
    }
    tick += 1;
    assert_eq!(
        bus.order(Order::Rearm { tag: 8, limb: 0 }, tick * PERIOD),
        Some(Rearmed {
            tag: 8,
            limb: 0,
            outcome: Ok(()),
        })
    );
    let _ = run_tick(
        &mut bus,
        tick,
        Some(&batch(tick, &[None, Some(hold(102))])),
        &[],
    );
    let snap = bus.end(deadline(tick));
    assert_eq!(limb(&snap, 0), (LimbState::Idle, None));
    assert_eq!(snap.limb(0).map(|l| l.generation), Some(1));
}
