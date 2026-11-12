//! (rt) What control does with the operator's stops and clears each tick, pure over the rings so it is tested on any OS:
//! the stop latch, control's end of each bus's order ring (stops never lost to a full ring, clears that never jump a
//! stop), and the answers back. The control thread (Linux) is its only user outside the tests.

use std::sync::atomic::{AtomicU32, Ordering};

use can::{MAX_DRIVES, Order, Rearmed};
use rtrb::Producer;
use safety::{Cause, RuleId};
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
/// latched since. Everything control should know of is told to `told`: each take of the latch that held stops, once,
/// as its stops are routed, and each clear refused where it can't go, once per bus, or once when its limb is on no bus.
/// Gives the stops deferred.
pub(crate) fn orders(
    plans: &[BusPlan],
    buses: &mut [BusOrders],
    stops: &StopLatch,
    mut next_clear: impl FnMut() -> Option<Clear>,
    mut told: impl FnMut(Told),
) -> u64 {
    let mut deferred = 0;
    for orders in buses.iter_mut() {
        orders.flush();
    }
    while let Some(clear) = next_clear() {
        // Taken after the clear was: a stop asked before it is in the latch by now.
        take_stops(plans, buses, stops, &mut told, &mut deferred);
        let mut routed_any = false;
        for ClearAt { bus, limb } in route_clear(plans, clear.limb) {
            routed_any = true;
            let Some(orders) = buses.get_mut(bus) else {
                continue;
            };
            if let Err(refused) = orders.clear(clear.tag, limb) {
                told(Told::Refused(Reply {
                    tag: clear.tag,
                    limb: clear.limb,
                    bus: Some(bus),
                    outcome: Err(refused),
                }));
            }
        }
        if !routed_any {
            told(Told::Refused(Reply {
                tag: clear.tag,
                limb: clear.limb,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            }));
        }
    }
    take_stops(plans, buses, stops, &mut told, &mut deferred);
    deferred
}

/// What [`orders`] tells control.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Told {
    /// The stops taken from the latch, before they are routed.
    Stopped(Stops),
    /// A clear refused.
    Refused(Reply),
}

/// Take the latch and route its stops to every bus, telling `told` of them first; counts each stop a full ring kept.
fn take_stops(
    plans: &[BusPlan],
    buses: &mut [BusOrders],
    stops: &StopLatch,
    told: &mut impl FnMut(Told),
    deferred: &mut u64,
) {
    let taken = stops.take();
    if taken.is_empty() {
        return;
    }
    told(Told::Stopped(taken));
    for scope in taken.scopes() {
        for StopAt { bus, stop } in route_stop(plans, scope) {
            if let Some(orders) = buses.get_mut(bus)
                && orders.stop(stop) == Stopped::Deferred
            {
                *deferred += 1;
            }
        }
    }
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

/// The causes a scope's stop was asked for, one bit each: the operator, shutdown, a stop carried from another bus, then
/// each rule by [`RuleId::index`]. Never 0 for a stop asked.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Causes(u32);

/// The bit of the first rule; the bits below are the causes that aren't rules.
const FIRST_RULE: usize = 3;
const _: () = assert!(
    FIRST_RULE + RuleId::ALL.len() <= 32,
    "a cause per bit of a u32"
);

impl Causes {
    /// The bit for `cause`.
    const fn bit(cause: Cause) -> u32 {
        let n = match cause {
            Cause::Operator => 0,
            Cause::Shutdown => 1,
            Cause::Follows => 2,
            Cause::Rule(rule) => FIRST_RULE + rule.index(),
        };
        1 << n
    }

    /// Whether no cause is set: no stop asked.
    pub(crate) const fn is_empty(self) -> bool {
        self.0 == 0
    }

    /// Each cause set, the ones that aren't rules first, then the rules in [`RuleId::ALL`] order.
    pub(crate) fn iter(self) -> impl Iterator<Item = Cause> {
        [Cause::Operator, Cause::Shutdown, Cause::Follows]
            .into_iter()
            .chain(RuleId::ALL.into_iter().map(Cause::Rule))
            .filter(move |c| self.0 & Self::bit(*c) != 0)
    }
}

/// The operator's stops and control's own, latched until control takes them once a pass: per scope, every cause it was
/// asked for. A scope's causes are its latch (any set is a stop), so asking is one atomic OR and taking one swap: a stop
/// is never taken without its cause, nor a cause without its stop. Asking never fails, waits or allocates, and a stop
/// asked again before control takes it is the same stop, so a burst of stops can't fill anything (PLAN item 3a: stop is
/// always accepted and jumps the queue: control takes stops before any clear).
#[derive(Debug, Default)]
pub(crate) struct StopLatch {
    /// The five limbs in [`LimbName::ALL`] order, then the robot.
    scopes: [AtomicU32; SCOPES],
}

/// The latch's scopes: the five limbs and the robot.
const SCOPES: usize = 6;
/// The robot's slot, after the limbs'.
const ROBOT: usize = 5;

/// A scope's slot in the latch.
const fn slot(scope: Scope) -> usize {
    match scope {
        Scope::Robot => ROBOT,
        Scope::Limb(LimbName::LeftArm) => 0,
        Scope::Limb(LimbName::RightArm) => 1,
        Scope::Limb(LimbName::Waist) => 2,
        Scope::Limb(LimbName::LeftLeg) => 3,
        Scope::Limb(LimbName::RightLeg) => 4,
    }
}

impl StopLatch {
    /// Ask for a stop of `scope`, for `cause`.
    pub(crate) fn ask(&self, scope: Scope, cause: Cause) {
        if let Some(causes) = self.scopes.get(slot(scope)) {
            causes.fetch_or(Causes::bit(cause), Ordering::AcqRel);
        }
    }

    /// Every stop asked since the last take, with its causes, clearing the latch.
    pub(crate) fn take(&self) -> Stops {
        let mut stops = Stops::default();
        for (causes, taken) in self.scopes.iter().zip(&mut stops.causes) {
            *taken = Causes(causes.swap(0, Ordering::AcqRel));
        }
        stops
    }
}

/// The stops taken from a [`StopLatch`] at once.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Stops {
    causes: [Causes; SCOPES],
}

impl Stops {
    /// Whether no stop was taken.
    pub(crate) fn is_empty(&self) -> bool {
        self.causes.iter().all(|c| c.is_empty())
    }

    /// The scopes to stop: the robot alone when it was asked, since it covers every limb; otherwise each limb asked, in
    /// [`LimbName::ALL`] order.
    pub(crate) fn scopes(self) -> impl Iterator<Item = Scope> {
        let robot = !self.of(Scope::Robot).is_empty();
        robot.then_some(Scope::Robot).into_iter().chain(
            LimbName::ALL
                .into_iter()
                .map(Scope::Limb)
                .filter(move |s| !robot && !self.of(*s).is_empty()),
        )
    }

    /// Every scope asked, the robot first, with every cause it was asked for: a limb's causes are kept even when the
    /// robot's stop covers it.
    pub(crate) fn asked(self) -> impl Iterator<Item = (Scope, Causes)> {
        std::iter::once(Scope::Robot)
            .chain(LimbName::ALL.into_iter().map(Scope::Limb))
            .map(move |s| (s, self.of(s)))
            .filter(|(_, c)| !c.is_empty())
    }

    /// `scope`'s causes.
    fn of(self, scope: Scope) -> Causes {
        self.causes.get(slot(scope)).copied().unwrap_or_default()
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
        let mut taken = Vec::new();
        let deferred = orders(
            &plans,
            &mut orders_of,
            &latch,
            || {
                let Some((stop, clear)) = script.next() else {
                    // Asked after the last clear was taken: the trailing take sends it this tick.
                    latch.ask(Scope::Limb(LimbName::Waist), Cause::Operator);
                    return None;
                };
                if let Some(scope) = stop {
                    latch.ask(scope, Cause::Operator);
                }
                Some(clear)
            },
            |told| match told {
                Told::Refused(r) => refused.push(r),
                Told::Stopped(stops) => taken.extend(asked(stops)),
            },
        );
        assert_eq!(deferred, 0);
        // Each stop taken is told once, with its cause.
        assert_eq!(
            taken,
            [
                (Scope::Limb(LimbName::RightArm), vec![Cause::Operator]),
                (Scope::Limb(LimbName::Waist), vec![Cause::Operator])
            ]
        );
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
        latch.ask(Scope::Limb(LimbName::LeftArm), Cause::Operator);
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

    /// Every scope a take holds, with its causes.
    fn asked(stops: Stops) -> Vec<(Scope, Vec<Cause>)> {
        stops
            .asked()
            .map(|(scope, causes)| (scope, causes.iter().collect()))
            .collect()
    }

    /// Guards: safety - every stop asked before control takes the latch is taken, each scope once however often it was
    /// asked, with every cause it was asked for (a limb's kept under a robot stop that covers it), and a robot stop is
    /// routed alone since it covers every limb; nothing is left for the next take (PLAN item 3a: stop is always
    /// accepted; safety.md section 8: every stop is an event naming its rule).
    #[test]
    fn the_stop_latch_keeps_every_stop_and_every_cause_until_taken() {
        let latch = StopLatch::default();
        assert!(latch.take().is_empty());
        latch.ask(Scope::Limb(LimbName::Waist), Cause::Rule(RuleId::HostMode));
        latch.ask(Scope::Limb(LimbName::RightLeg), Cause::Follows);
        latch.ask(Scope::Limb(LimbName::Waist), Cause::Operator);
        latch.ask(Scope::Limb(LimbName::LeftArm), Cause::Operator);
        latch.ask(Scope::Limb(LimbName::LeftArm), Cause::Operator);
        let stops = latch.take();
        assert_eq!(
            stops.scopes().collect::<Vec<_>>(),
            [
                Scope::Limb(LimbName::LeftArm),
                Scope::Limb(LimbName::Waist),
                Scope::Limb(LimbName::RightLeg)
            ]
        );
        assert_eq!(
            asked(stops),
            [
                (Scope::Limb(LimbName::LeftArm), vec![Cause::Operator]),
                (
                    Scope::Limb(LimbName::Waist),
                    vec![Cause::Operator, Cause::Rule(RuleId::HostMode)]
                ),
                (Scope::Limb(LimbName::RightLeg), vec![Cause::Follows])
            ]
        );
        assert!(latch.take().is_empty());
        latch.ask(
            Scope::Limb(LimbName::RightArm),
            Cause::Rule(RuleId::HostMode),
        );
        latch.ask(Scope::Robot, Cause::Shutdown);
        let stops = latch.take();
        assert_eq!(stops.scopes().collect::<Vec<_>>(), [Scope::Robot]);
        assert_eq!(
            asked(stops),
            [
                (Scope::Robot, vec![Cause::Shutdown]),
                (
                    Scope::Limb(LimbName::RightArm),
                    vec![Cause::Rule(RuleId::HostMode)]
                )
            ]
        );
        assert!(latch.take().is_empty());
        // Every rule is kept as itself: ALL holds each at its index, and each round-trips the latch.
        for (i, rule) in RuleId::ALL.into_iter().enumerate() {
            assert_eq!(rule.index(), i, "{rule}");
        }
        for (limb, rule) in LimbName::ALL.into_iter().cycle().zip(RuleId::ALL) {
            latch.ask(Scope::Limb(limb), Cause::Rule(rule));
            assert_eq!(
                asked(latch.take()),
                [(Scope::Limb(limb), vec![Cause::Rule(rule)])]
            );
        }
    }

    /// Guards: safety - stops asked from other threads while control takes the latch are each taken, by the next take
    /// at the latest, under the cause they were asked for and never another's (safety.md section 8).
    #[test]
    fn stops_asked_during_a_take_keep_their_own_cause() {
        let latch = std::sync::Arc::new(StopLatch::default());
        let askers: Vec<_> = [
            (LimbName::LeftArm, Cause::Operator),
            (LimbName::Waist, Cause::Rule(RuleId::HostMode)),
        ]
        .into_iter()
        .map(|(limb, cause)| {
            let latch = std::sync::Arc::clone(&latch);
            std::thread::spawn(move || {
                for _ in 0..10_000 {
                    latch.ask(Scope::Limb(limb), cause);
                }
            })
        })
        .collect();
        let mut seen = Vec::new();
        while !askers.iter().all(std::thread::JoinHandle::is_finished) {
            seen.extend(asked(latch.take()));
        }
        for asker in askers {
            asker.join().unwrap();
        }
        seen.extend(asked(latch.take()));
        assert!(seen.contains(&(Scope::Limb(LimbName::LeftArm), vec![Cause::Operator])));
        assert!(seen.contains(&(
            Scope::Limb(LimbName::Waist),
            vec![Cause::Rule(RuleId::HostMode)]
        )));
        assert!(seen.iter().all(|s| matches!(
            s,
            (Scope::Limb(LimbName::LeftArm), c) if *c == [Cause::Operator]
        ) || matches!(
            s,
            (Scope::Limb(LimbName::Waist), c) if *c == [Cause::Rule(RuleId::HostMode)]
        )));
        assert!(latch.take().is_empty());
    }
}
