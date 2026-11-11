//! The operator's requests and how control turns them into each bus's orders. Pure, so it is tested on any OS; the
//! control thread (Linux) carries the orders to the rings.

use std::sync::atomic::{AtomicU8, Ordering};

use can::{Order, RearmRefused, Rearmed};
use skeleton::LimbName;

use crate::plan::BusPlan;

/// What a stop covers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Scope {
    /// Every limb on every bus.
    Robot,
    /// One limb, on every bus it has joints on.
    Limb(LimbName),
}

/// The operator's clear of one stopped limb: one [`Reply`] per bus the limb is on, under `tag`, or one refusal when it
/// is on none. Enable and plans come with the control step that runs them (PLAN step 7, 4b-2); until then the runtime
/// never enables anything.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Clear {
    /// The requester's tag, echoed in each reply.
    pub tag: u64,
    /// The limb.
    pub limb: LimbName,
}

/// The answer to a [`Clear`], one per bus the limb is on.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Reply {
    /// The clear's tag.
    pub tag: u64,
    /// The limb.
    pub limb: LimbName,
    /// The bus, as its index in the runtime's plan; `None` when the refusal isn't any bus's.
    pub bus: Option<usize>,
    /// Whether the limb is idle again on that bus, with a new generation, or why not.
    pub outcome: Result<(), ClearRefused>,
}

/// Why a clear wasn't done.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ClearRefused {
    /// The bus refused the re-arm.
    #[error("the bus refused the re-arm: {0:?}")]
    Bus(RearmRefused),
    /// The limb has no joint on any bus.
    #[error("the limb has no joint on any bus")]
    Offline,
    /// A stop for the bus is still waiting for room in its order ring, so the clear would jump it, or the ring is full;
    /// nothing was asked of the bus. Ask again.
    #[error("the bus's order ring is full or a stop is still waiting for it")]
    Busy,
    /// The bus thread has ended; nothing on it can be cleared.
    #[error("the bus thread has ended")]
    BusEnded,
}

/// One order for the bus at `bus`, the index in the plan.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Routed {
    /// The bus.
    pub bus: usize,
    /// The order.
    pub order: Order,
}

/// The orders a stop of `scope` asks of each bus in `plans`, in bus order: at most one per bus.
pub fn route_stop(plans: &[BusPlan], scope: Scope) -> impl Iterator<Item = Routed> + '_ {
    plans.iter().enumerate().filter_map(move |(bus, p)| {
        let order = match scope {
            Scope::Robot => Order::StopAll,
            Scope::Limb(limb) => Order::StopLimb(p.limb_index(limb)?),
        };
        Some(Routed { bus, order })
    })
}

/// One bus a clear goes to, and that bus's index for the limb.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ClearAt {
    /// The bus, as its index in the plan.
    pub bus: usize,
    /// The limb, as that bus's index for it.
    pub limb: usize,
}

/// Each bus in `plans` that `limb` is on, in bus order: a clear re-arms it on every one.
pub fn route_clear(plans: &[BusPlan], limb: LimbName) -> impl Iterator<Item = ClearAt> + '_ {
    plans.iter().enumerate().filter_map(move |(bus, p)| {
        Some(ClearAt {
            bus,
            limb: p.limb_index(limb)?,
        })
    })
}

/// The reply for the bus at `bus`'s answer to a re-arm [`route_clear`] made; `None` for a limb index the plan doesn't
/// have, which only a bug can give.
#[must_use]
pub fn reply(plans: &[BusPlan], bus: usize, answer: Rearmed) -> Option<Reply> {
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
pub struct StopLatch(AtomicU8);

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
    pub fn ask(&self, scope: Scope) {
        let bit = match scope {
            Scope::Robot => ROBOT,
            Scope::Limb(limb) => limb_bit(limb),
        };
        self.0.fetch_or(bit, Ordering::AcqRel);
    }

    /// Every stop asked since the last take, clearing the latch.
    pub fn take(&self) -> Stops {
        Stops(self.0.swap(0, Ordering::AcqRel))
    }
}

/// The stops taken from a [`StopLatch`] at once.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Stops(u8);

impl Stops {
    /// The scopes to stop: the robot alone when it was asked, since it covers every limb; otherwise each limb asked, in
    /// [`LimbName::ALL`] order.
    pub fn scopes(self) -> impl Iterator<Item = Scope> {
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
    use super::*;

    /// The runtime's test robot's plan (`tests/skeleton.yaml`): can0 holds the right arm and the waist, can1 the left
    /// arm and the right arm's third joint; the left leg is offline and the right leg has no joints.
    fn plans() -> Vec<BusPlan> {
        crate::plan(&skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap()).unwrap()
    }

    /// Guards: safety - a stop or clear reaches exactly the buses and limb indices of the limb it names, a robot stop
    /// every bus, and a limb on no bus none, so an operator's stop never misses a bus the limb is on and never touches a
    /// limb it didn't name (PLAN item 6: a stop names its scope; tenet 1).
    #[test]
    fn requests_reach_the_named_limb_on_every_bus_it_is_on_and_nothing_else() {
        let plans = plans();
        let at = |bus, order| Routed { bus, order };
        let stop = |scope| route_stop(&plans, scope).collect::<Vec<_>>();
        assert_eq!(
            stop(Scope::Robot),
            [at(0, Order::StopAll), at(1, Order::StopAll)]
        );
        // The right arm is limb 0 on can0 and limb 1 on can1.
        assert_eq!(
            stop(Scope::Limb(LimbName::RightArm)),
            [at(0, Order::StopLimb(0)), at(1, Order::StopLimb(1))]
        );
        assert_eq!(
            stop(Scope::Limb(LimbName::Waist)),
            [at(0, Order::StopLimb(1))]
        );
        assert_eq!(stop(Scope::Limb(LimbName::LeftLeg)), []);
        assert_eq!(stop(Scope::Limb(LimbName::RightLeg)), []);
        let clear = |limb| route_clear(&plans, limb).collect::<Vec<_>>();
        assert_eq!(
            clear(LimbName::RightArm),
            [ClearAt { bus: 0, limb: 0 }, ClearAt { bus: 1, limb: 1 }]
        );
        assert_eq!(clear(LimbName::LeftArm), [ClearAt { bus: 1, limb: 0 }]);
        assert_eq!(clear(LimbName::LeftLeg), []);
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
