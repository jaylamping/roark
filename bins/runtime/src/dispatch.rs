//! (rt) Control's end of one bus's order ring: stops never lost to a full ring, and clears that never jump a stop. Pure
//! over the ring, so it is tested on any OS with a ring of one slot.

use can::{MAX_DRIVES, Order};
use rtrb::Producer;

use crate::request::ClearRefused;

/// Stops a full order ring didn't take yet, pushed again before anything else for that bus.
#[derive(Clone, Copy, Debug, Default)]
struct Deferred {
    all: bool,
    limbs: [bool; MAX_DRIVES],
}

impl Deferred {
    fn any(&self) -> bool {
        self.all || self.limbs.contains(&true)
    }
}

/// One bus's order ring as control holds it.
pub(crate) struct BusOrders {
    ring: Producer<Order>,
    deferred: Deferred,
}

/// What became of a stop.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Stopped {
    /// In the ring.
    Sent,
    /// Kept, to be pushed again each tick until the ring takes it.
    Deferred,
}

impl BusOrders {
    pub(crate) fn new(ring: Producer<Order>) -> Self {
        Self {
            ring,
            deferred: Deferred::default(),
        }
    }

    /// Whether the bus thread has ended (its end of the ring is gone).
    pub(crate) fn ended(&self) -> bool {
        self.ring.is_abandoned()
    }

    /// Push the stops still waiting, in the order they would have gone; false when some still wait.
    pub(crate) fn flush(&mut self) -> bool {
        if self.deferred.all {
            if self.ring.push(Order::StopAll).is_err() {
                return false;
            }
            self.deferred.all = false;
        }
        for (limb, waiting) in self.deferred.limbs.iter_mut().enumerate() {
            if *waiting {
                if self.ring.push(Order::StopLimb(limb)).is_err() {
                    return false;
                }
                *waiting = false;
            }
        }
        true
    }

    /// Push a stop, or keep it when the ring is full or an earlier stop still waits (so none jumps another). A stop of a
    /// limb index past any bus's, which only a bug can give, is kept as a stop of the whole bus, as the bus would take it
    /// (`BadOrder`).
    pub(crate) fn stop(&mut self, order: Order) -> Stopped {
        if !self.deferred.any() && self.ring.push(order).is_ok() {
            return Stopped::Sent;
        }
        match order {
            Order::StopAll => self.deferred.all = true,
            Order::StopLimb(limb) => match self.deferred.limbs.get_mut(limb) {
                Some(waiting) => *waiting = true,
                // Out of the bus's range: it would stop every limb as a bad order, so keep that.
                None => self.deferred.all = true,
            },
            // Not a stop; `clear` carries re-arms.
            Order::Rearm { .. } => return Stopped::Sent,
        }
        Stopped::Deferred
    }

    /// Push a re-arm, or say why it wasn't: the bus has ended, a stop still waits (the clear would reach the bus
    /// first), or the ring is full. Sent, it is answered by the bus.
    pub(crate) fn clear(&mut self, tag: u64, limb: usize) -> Result<(), ClearRefused> {
        if self.ended() {
            return Err(ClearRefused::BusEnded);
        }
        if self.deferred.any() {
            return Err(ClearRefused::Busy);
        }
        self.ring
            .push(Order::Rearm { tag, limb })
            .map_err(|_| ClearRefused::Busy)
    }
}

#[cfg(test)]
mod tests {
    use rtrb::RingBuffer;

    use super::*;

    /// Guards: safety - a stop the bus's full order ring can't take is kept and pushed later, ahead of anything else
    /// and in its order, a clear is refused while it waits so it never reaches the bus before the stop, and a clear to an
    /// ended bus is refused rather than left unanswered (PLAN item 3a: stop is always accepted; step 7 design D2).
    #[test]
    fn a_stop_waits_for_room_and_no_clear_jumps_it() {
        let (ring, mut bus) = RingBuffer::new(1);
        let mut orders = BusOrders::new(ring);
        assert_eq!(orders.stop(Order::StopLimb(1)), Stopped::Sent);
        // The ring is full: the next stops wait, and a clear is refused behind them.
        assert_eq!(orders.stop(Order::StopAll), Stopped::Deferred);
        assert_eq!(orders.stop(Order::StopLimb(0)), Stopped::Deferred);
        assert_eq!(orders.clear(7, 0), Err(ClearRefused::Busy));
        assert!(!orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(1)));
        // Room for one: the robot stop goes first, the limb's still waits, and so does the clear.
        assert!(!orders.flush());
        assert_eq!(orders.clear(7, 0), Err(ClearRefused::Busy));
        assert_eq!(bus.pop(), Ok(Order::StopAll));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        // Nothing waits: a clear goes, and a stop behind it in a full ring waits as before.
        assert_eq!(orders.clear(7, 0), Ok(()));
        assert_eq!(orders.clear(8, 0), Err(ClearRefused::Busy));
        assert_eq!(orders.stop(Order::StopLimb(0)), Stopped::Deferred);
        assert_eq!(bus.pop(), Ok(Order::Rearm { tag: 7, limb: 0 }));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        // A stop of a limb the bus can't hold, kept, still stops the bus.
        assert_eq!(orders.stop(Order::StopLimb(0)), Stopped::Sent);
        assert_eq!(orders.stop(Order::StopLimb(MAX_DRIVES)), Stopped::Deferred);
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopAll));
        // The bus thread ends: a clear is refused for it.
        drop(bus);
        assert_eq!(orders.clear(9, 0), Err(ClearRefused::BusEnded));
    }
}
