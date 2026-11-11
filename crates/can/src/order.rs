//! (rt) Control's orders to a bus besides the batch: stop one limb, stop the bus, or re-arm a stopped limb (the
//! operator's clear). Control asks for a stop this way, never with Disables in a batch (step 7 design, D2); the bus
//! takes each order before the next tick's plan, so a stop asked in tick n's slack goes out in tick n+1's sends.

use crate::tick::BusTick;
use crate::types::{RearmRefused, StopReason};

/// What control orders a bus to do to its limbs. A limb is named by its index on this bus, as in `BusDrive::limb`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Order {
    /// Stop one limb (`StopReason::LimbRequested`); the bus's other limbs keep running. A limb not on this bus is a
    /// bug upstream: the bus can't tell which limb was meant, so it stops every limb (`StopReason::BadOrder`), as a bad batch does.
    StopLimb(usize),
    /// Stop every limb on the bus (`StopReason::Requested`).
    StopAll,
    /// Re-arm a stopped limb: the operator's clear (`BusTick::rearm`). Answered by exactly one [`Rearmed`] with the
    /// same tag. Refused while a stop of the limb or the bus is still waiting for the next plan, so a clear never
    /// undoes a stop ordered before it; a limb not on this bus is refused (`NoSuchLimb`), nothing stopped.
    Rearm {
        /// Control's tag, echoed in the answer.
        tag: u64,
        /// The limb.
        limb: usize,
    },
}

/// The answer to an [`Order::Rearm`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rearmed {
    /// The order's tag.
    pub tag: u64,
    /// The limb it named.
    pub limb: usize,
    /// Whether the limb is idle again, with a new generation, or why not.
    pub outcome: Result<(), RearmRefused>,
}

impl BusTick {
    /// Take one of control's orders at `now_ns`, before [`Self::begin`]: a stop is planned at that `begin`, and a
    /// re-arm is done now and answered.
    pub fn order(&mut self, order: Order, now_ns: u64) -> Option<Rearmed> {
        match order {
            Order::StopLimb(limb) => {
                if self.stop_limb(limb).is_err() {
                    // Counted as well as stopped: an earlier whole-bus stop, or every limb already stopping, would
                    // otherwise leave no trace of it.
                    self.counters.bad_orders += 1;
                    self.pending_stop
                        .get_or_insert(StopReason::BadOrder { limb });
                }
                None
            }
            Order::StopAll => {
                self.request_stop();
                None
            }
            Order::Rearm { tag, limb } => {
                // A stop asked before the clear, of the limb or of the bus and not yet planned, wins: a clear never
                // undoes a stop it came after (push order).
                let limb_pending = self
                    .limbs
                    .get(limb)
                    .and_then(Option::as_ref)
                    .is_some_and(|l| l.pending.is_some());
                let outcome = if limb_pending || self.pending_stop.is_some() {
                    Err(RearmRefused::StopPending(limb))
                } else {
                    self.rearm(limb, now_ns)
                };
                Some(Rearmed { tag, limb, outcome })
            }
        }
    }
}
