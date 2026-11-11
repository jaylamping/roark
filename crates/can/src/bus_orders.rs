//! (rt) The bus thread's side of control's orders on Linux: every order in the ring taken each tick, and each re-arm's
//! one answer handed back. A full answer ring drops the answer and counts it; the snapshots still show the limb.

use rtrb::{Consumer, Producer};

use crate::clock::{Clock, mono_now};
use crate::order::{Order, Rearmed};
use crate::tick::BusTick;
use crate::types::RearmRefused;

/// Which orders a pass over the ring takes.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Take {
    /// Stops only, up to the first re-arm, which waits in the ring: at the tick's start, so a stop goes out in that
    /// tick's sends; and on a bus exiting, where a re-arm would undo the exit's stop and is answered `Ended` at the end.
    Stops,
    /// Every order, in the slack after the collect: a re-arm is judged on everything the drain and the collect read, and
    /// a frame read after it latches afresh and is checked before the next send.
    All,
}

/// Take orders from the ring as `take` says, at most its capacity, and hand each re-arm's answer back; a full ring
/// drops the answer and counts it. Returns whether a re-arm made a limb idle again.
pub(crate) fn take(
    clock: &Clock,
    tick: &mut BusTick,
    orders: &mut Consumer<Order>,
    rearmed: &mut Producer<Rearmed>,
    take: Take,
) -> bool {
    let mut cleared = false;
    for _ in 0..orders.buffer().capacity() {
        if take == Take::Stops && matches!(orders.peek(), Ok(Order::Rearm { .. })) {
            break;
        }
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

/// The thread is ending: every re-arm still in the ring gets its one answer, a refusal (`Ended`); a stop left there
/// isn't taken, as no tick follows to plan it. A dropped answer counts in the tick's counters, which `BusExit::counters`
/// carries: no snapshot comes after these.
pub(crate) fn end(
    tick: &mut BusTick,
    orders: &mut Consumer<Order>,
    rearmed: &mut Producer<Rearmed>,
) {
    for _ in 0..orders.buffer().capacity() {
        let Ok(order) = orders.pop() else {
            break;
        };
        if let Order::Rearm { tag, limb } = order {
            let answer = Rearmed {
                tag,
                limb,
                outcome: Err(RearmRefused::Ended),
            };
            if rearmed.push(answer).is_err() {
                tick.rearm_dropped();
            }
        }
    }
}
