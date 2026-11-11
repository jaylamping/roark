//! (rt) What control does with the operator's stops and clears each tick, pure over the rings so it is tested on any OS:
//! the stop latch, control's end of each bus's order ring (stops never lost to a full ring, clears that never jump a
//! stop), and the answers back. The control thread (Linux) is its only user outside the tests.

use std::sync::atomic::{AtomicU8, Ordering};

use can::{MAX_DRIVES, Order, Rearmed};
use rtrb::Producer;
use skeleton::LimbName;

use crate::plan::BusPlan;
use crate::request::{
    BusStop, Clear, ClearAt, ClearRefused, Reply, Scope, StopAt, route_clear, route_stop,
};

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

    /// Push the stops still waiting, the bus's own stop first, since it covers the rest; false when some still wait.
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
    pub(crate) fn stop(&mut self, stop: BusStop) -> Stopped {
        let order = match stop {
            BusStop::All => Order::StopAll,
            BusStop::Limb(limb) => Order::StopLimb(limb),
        };
        if !self.deferred.any() && self.ring.push(order).is_ok() {
            return Stopped::Sent;
        }
        match stop {
            BusStop::All => self.deferred.all = true,
            BusStop::Limb(limb) => match self.deferred.limbs.get_mut(limb) {
                Some(waiting) => *waiting = true,
                None => self.deferred.all = true,
            },
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

/// One tick's orders for every bus: the stops still waiting, then each clear from `next_clear` in turn, each after the
/// stops latched by the time it was taken, so no clear reaches a bus before a stop asked before it; then any stop
/// latched since. Each clear is refused through `refuse` where it can't go, once per bus, or once when its limb is on no
/// bus. Gives the stops deferred.
pub(crate) fn orders(
    plans: &[BusPlan],
    buses: &mut [BusOrders],
    stops: &StopLatch,
    mut next_clear: impl FnMut() -> Option<Clear>,
    mut refuse: impl FnMut(Reply),
) -> u64 {
    let mut deferred = 0;
    let mut take_stops = |buses: &mut [BusOrders]| {
        for scope in stops.take().scopes() {
            for StopAt { bus, stop } in route_stop(plans, scope) {
                if let Some(orders) = buses.get_mut(bus)
                    && orders.stop(stop) == Stopped::Deferred
                {
                    deferred += 1;
                }
            }
        }
    };
    for orders in buses.iter_mut() {
        orders.flush();
    }
    while let Some(clear) = next_clear() {
        // Taken after the clear was: a stop asked before it is in the latch by now.
        take_stops(buses);
        let mut routed_any = false;
        for ClearAt { bus, limb } in route_clear(plans, clear.limb) {
            routed_any = true;
            let Some(orders) = buses.get_mut(bus) else {
                continue;
            };
            if let Err(refused) = orders.clear(clear.tag, limb) {
                refuse(Reply {
                    tag: clear.tag,
                    limb: clear.limb,
                    bus: Some(bus),
                    outcome: Err(refused),
                });
            }
        }
        if !routed_any {
            refuse(Reply {
                tag: clear.tag,
                limb: clear.limb,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            });
        }
    }
    take_stops(buses);
    deferred
}

/// The reply for the bus at `bus`'s answer to a re-arm [`route_clear`](crate::route_clear) made; `None` for a limb index the plan doesn't
/// have, which only a bug can give.
#[must_use]
pub(crate) fn reply(plans: &[BusPlan], bus: usize, answer: Rearmed) -> Option<Reply> {
    let limb = *plans.get(bus)?.limbs.get(answer.limb)?;
    Some(Reply {
        tag: answer.tag,
        limb,
        bus: Some(bus),
        outcome: answer.outcome.map_err(ClearRefused::Bus),
    })
}

/// The operator's stops, latched until control takes them once a tick. Asking never fails, waits or allocates, and a
/// stop asked again before control takes it is the same stop, so a burst of stops can't fill anything (PLAN item 3a:
/// stop is always accepted and jumps the queue: control takes stops before any clear).
#[derive(Debug, Default)]
pub(crate) struct StopLatch(AtomicU8);

/// The robot bit, above the five limb bits.
const ROBOT: u8 = 1 << 5;

/// A limb's bit in the latch.
const fn limb_bit(limb: LimbName) -> u8 {
    match limb {
        LimbName::LeftArm => 1,
        LimbName::RightArm => 1 << 1,
        LimbName::Waist => 1 << 2,
        LimbName::LeftLeg => 1 << 3,
        LimbName::RightLeg => 1 << 4,
    }
}

impl StopLatch {
    /// Ask for a stop of `scope`.
    pub(crate) fn ask(&self, scope: Scope) {
        let bit = match scope {
            Scope::Robot => ROBOT,
            Scope::Limb(limb) => limb_bit(limb),
        };
        self.0.fetch_or(bit, Ordering::AcqRel);
    }

    /// Every stop asked since the last take, clearing the latch.
    pub(crate) fn take(&self) -> Stops {
        Stops(self.0.swap(0, Ordering::AcqRel))
    }
}

/// The stops taken from a [`StopLatch`] at once.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Stops(u8);

impl Stops {
    /// The scopes to stop: the robot alone when it was asked, since it covers every limb; otherwise each limb asked, in
    /// [`LimbName::ALL`] order.
    pub(crate) fn scopes(self) -> impl Iterator<Item = Scope> {
        let robot = self.0 & ROBOT != 0;
        robot.then_some(Scope::Robot).into_iter().chain(
            LimbName::ALL
                .into_iter()
                .filter(move |l| !robot && self.0 & limb_bit(*l) != 0)
                .map(Scope::Limb),
        )
    }
}

#[cfg(test)]
mod tests {
    use rtrb::{Consumer, RingBuffer};

    use super::*;
    use can::RearmRefused;

    fn plans() -> Vec<BusPlan> {
        crate::plan(&skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap()).unwrap()
    }

    /// Guards: safety - a stop the bus's full order ring can't take is kept and pushed later, ahead of anything else
    /// and the bus's own stop first, a clear is refused while it waits so it never reaches the bus before the stop, and
    /// a clear to an ended bus is refused rather than left unanswered (PLAN item 3a: stop is always accepted; step 7
    /// design D2).
    #[test]
    fn a_stop_waits_for_room_and_no_clear_jumps_it() {
        let (ring, mut bus) = RingBuffer::new(1);
        let mut orders = BusOrders::new(ring);
        assert_eq!(orders.stop(BusStop::Limb(1)), Stopped::Sent);
        // The ring is full: the next stops wait, and a clear is refused behind them.
        assert_eq!(orders.stop(BusStop::Limb(0)), Stopped::Deferred);
        assert_eq!(orders.stop(BusStop::All), Stopped::Deferred);
        assert_eq!(orders.clear(7, 0), Err(ClearRefused::Busy));
        assert!(!orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(1)));
        // Room for one: the bus's stop goes first, the limb's still waits, and so does the clear.
        assert!(!orders.flush());
        assert_eq!(orders.clear(7, 0), Err(ClearRefused::Busy));
        assert_eq!(bus.pop(), Ok(Order::StopAll));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        // Nothing waits: a clear goes, and a stop behind it in a full ring waits as before.
        assert_eq!(orders.clear(7, 0), Ok(()));
        assert_eq!(orders.clear(8, 0), Err(ClearRefused::Busy));
        assert_eq!(orders.stop(BusStop::Limb(0)), Stopped::Deferred);
        assert_eq!(bus.pop(), Ok(Order::Rearm { tag: 7, limb: 0 }));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        // A stop of a limb the bus can't hold, kept, still stops the bus.
        assert_eq!(orders.stop(BusStop::Limb(0)), Stopped::Sent);
        assert_eq!(orders.stop(BusStop::Limb(MAX_DRIVES)), Stopped::Deferred);
        assert_eq!(bus.pop(), Ok(Order::StopLimb(0)));
        assert!(orders.flush());
        assert_eq!(bus.pop(), Ok(Order::StopAll));
        // The bus thread ends: a clear is refused for it.
        drop(bus);
        assert_eq!(orders.clear(9, 0), Err(ClearRefused::BusEnded));
    }

    fn drain(ring: &mut Consumer<Order>) -> Vec<Order> {
        std::iter::from_fn(|| ring.pop().ok()).collect()
    }

    /// Guards: safety - a stop asked before a clear reaches every bus before that clear, even when it is asked after
    /// the tick's first look at the latch (between two clears), so the bus never re-arms a limb its operator had already
    /// asked to stop; a stop asked after the last clear still goes this tick; a clear of a limb on no bus is refused
    /// (PLAN item 3a: stop jumps the queue; step 7 design D2).
    #[test]
    fn a_stop_asked_before_a_clear_reaches_the_bus_first() {
        let plans = plans();
        let (rings, mut buses): (Vec<_>, Vec<_>) =
            (0..plans.len()).map(|_| RingBuffer::new(8)).unzip();
        let mut orders_of: Vec<BusOrders> = rings.into_iter().map(BusOrders::new).collect();
        let latch = StopLatch::default();
        // The operator: a clear of the left arm, then a stop of the right arm and a clear of it, then a clear of the
        // offline leg, then a stop of the waist after the last clear; control pops them in turn.
        let mut script = vec![
            (
                None,
                Clear {
                    tag: 1,
                    limb: LimbName::LeftArm,
                },
            ),
            (
                Some(Scope::Limb(LimbName::RightArm)),
                Clear {
                    tag: 2,
                    limb: LimbName::RightArm,
                },
            ),
            (
                None,
                Clear {
                    tag: 3,
                    limb: LimbName::LeftLeg,
                },
            ),
        ]
        .into_iter();
        let mut refused = Vec::new();
        let deferred = orders(
            &plans,
            &mut orders_of,
            &latch,
            || {
                let Some((stop, clear)) = script.next() else {
                    // Asked after the last clear was taken: the trailing take sends it this tick.
                    latch.ask(Scope::Limb(LimbName::Waist));
                    return None;
                };
                if let Some(scope) = stop {
                    latch.ask(scope);
                }
                Some(clear)
            },
            |r| refused.push(r),
        );
        assert_eq!(deferred, 0);
        // can0: the right arm (limb 0) stopped before its clear; the waist (limb 1) stopped after the clears.
        assert_eq!(
            drain(&mut buses[0]),
            [
                Order::StopLimb(0),
                Order::Rearm { tag: 2, limb: 0 },
                Order::StopLimb(1)
            ]
        );
        // can1: the left arm's clear came first; the right arm (limb 1) stopped before its clear.
        assert_eq!(
            drain(&mut buses[1]),
            [
                Order::Rearm { tag: 1, limb: 0 },
                Order::StopLimb(1),
                Order::Rearm { tag: 2, limb: 1 }
            ]
        );
        assert_eq!(
            refused,
            [Reply {
                tag: 3,
                limb: LimbName::LeftLeg,
                bus: None,
                outcome: Err(ClearRefused::Offline)
            }]
        );
        // A tick with no clears: a stop latched before it goes all the same.
        latch.ask(Scope::Limb(LimbName::LeftArm));
        assert_eq!(orders(&plans, &mut orders_of, &latch, || None, |_| {}), 0);
        assert_eq!(drain(&mut buses[0]), []);
        assert_eq!(drain(&mut buses[1]), [Order::StopLimb(0)]);
    }

    /// Guards: safety - a bus's re-arm answer comes back under the requester's tag and the skeleton limb it stands
    /// for, with the bus's refusal kept, so the operator learns which bus refused a clear and why.
    #[test]
    fn a_bus_answer_names_the_skeleton_limb_and_keeps_the_refusal() {
        let plans = plans();
        let answer = Rearmed {
            tag: 9,
            limb: 1,
            outcome: Err(RearmRefused::StopPending(1)),
        };
        assert_eq!(
            reply(&plans, 0, answer),
            Some(Reply {
                tag: 9,
                limb: LimbName::Waist,
                bus: Some(0),
                outcome: Err(ClearRefused::Bus(RearmRefused::StopPending(1))),
            })
        );
        assert_eq!(
            reply(&plans, 1, answer).map(|r| r.limb),
            Some(LimbName::RightArm)
        );
        assert_eq!(reply(&plans, 0, Rearmed { limb: 2, ..answer }), None);
        assert_eq!(reply(&plans, 2, answer), None);
    }

    /// Guards: safety - every stop asked before control takes the latch is taken, each limb once however often it was
    /// asked, and a robot stop covers every limb; nothing is left for the next take (PLAN item 3a: stop is always
    /// accepted).
    #[test]
    fn the_stop_latch_keeps_every_stop_asked_until_taken() {
        let latch = StopLatch::default();
        assert_eq!(latch.take().scopes().count(), 0);
        latch.ask(Scope::Limb(LimbName::Waist));
        latch.ask(Scope::Limb(LimbName::RightLeg));
        latch.ask(Scope::Limb(LimbName::Waist));
        latch.ask(Scope::Limb(LimbName::LeftArm));
        assert_eq!(
            latch.take().scopes().collect::<Vec<_>>(),
            [
                Scope::Limb(LimbName::LeftArm),
                Scope::Limb(LimbName::Waist),
                Scope::Limb(LimbName::RightLeg)
            ]
        );
        assert_eq!(latch.take(), Stops::default());
        latch.ask(Scope::Limb(LimbName::RightArm));
        latch.ask(Scope::Robot);
        assert_eq!(latch.take().scopes().collect::<Vec<_>>(), [Scope::Robot]);
        for limb in LimbName::ALL {
            latch.ask(Scope::Limb(limb));
        }
        assert_eq!(
            latch.take().scopes().collect::<Vec<_>>(),
            LimbName::ALL.map(Scope::Limb)
        );
    }
}
