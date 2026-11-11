//! (rt) The bus thread's side of control's orders on Linux: every order in the ring taken at each tick's start, before
//! the drain, and each re-arm's one answer handed back. A full answer ring drops the answer and counts it; the snapshots still show the limb.

use rtrb::{Consumer, Producer};

use crate::clock::{Clock, mono_now};
use crate::order::{Order, Rearmed};
use crate::tick::BusTick;
use crate::types::RearmRefused;

/// Take every order in the ring, at most its capacity, and hand each re-arm's answer back; a full ring drops the
/// answer and counts it. Returns whether a re-arm made a limb idle again.
pub(crate) fn take(
    clock: &Clock,
    tick: &mut BusTick,
    orders: &mut Consumer<Order>,
    rearmed: &mut Producer<Rearmed>,
) -> bool {
    let mut cleared = false;
    for _ in 0..orders.buffer().capacity() {
        let Ok(order) = orders.pop() else {
            break;
        };
        if let Some(answer) = tick.order(order, clock.ns(mono_now())) {
            cleared |= answer.outcome.is_ok();
            if rearmed.push(answer).is_err() {
                tick.rearm_dropped();
            }
        }
    }
    cleared
}

/// The thread is ending: every re-arm still in the ring gets its one answer, a refusal (`Ended`); a stop left there is
/// taken as any order is, so one naming a limb the bus doesn't have is counted, but no tick follows to plan it. A
/// dropped answer counts in the tick's counters, which `BusExit::counters` carries: no snapshot comes after these.
pub(crate) fn end(
    tick: &mut BusTick,
    orders: &mut Consumer<Order>,
    rearmed: &mut Producer<Rearmed>,
) {
    for _ in 0..orders.buffer().capacity() {
        let Ok(order) = orders.pop() else {
            break;
        };
        match order {
            Order::Rearm { tag, limb } => {
                let answer = Rearmed {
                    tag,
                    limb,
                    outcome: Err(RearmRefused::Ended),
                };
                if rearmed.push(answer).is_err() {
                    tick.rearm_dropped();
                }
            }
            // A stop takes no time (`now_ns` is a re-arm's alone) and answers nothing.
            Order::StopLimb(_) | Order::StopAll => {
                let _ = tick.order(order, 0);
            }
        }
    }
}
