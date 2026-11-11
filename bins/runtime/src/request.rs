//! The operator's requests, their answers, and which buses each goes to. Pure, so it is tested on any OS; what control
//! does with them each tick is in `dispatch`.

use can::RearmRefused;
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

/// The answer to a [`Clear`]: one per bus the limb is on, or one with no bus when it is on none.
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
    /// The run is ending; every limb is being stopped.
    #[error("the run is ending")]
    Ending,
}

/// What a stop asks of one bus.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BusStop {
    /// Every limb on it (`can::Order::StopAll`).
    All,
    /// One limb, as that bus's index for it (`can::Order::StopLimb`).
    Limb(usize),
}

/// One bus a stop goes to, and what it asks of it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct StopAt {
    /// The bus, as its index in the plan.
    pub bus: usize,
    /// The stop.
    pub stop: BusStop,
}

/// What a stop of `scope` asks of each bus in `plans`, in bus order: at most one per bus.
pub fn route_stop(plans: &[BusPlan], scope: Scope) -> impl Iterator<Item = StopAt> + '_ {
    plans.iter().enumerate().filter_map(move |(bus, p)| {
        let stop = match scope {
            Scope::Robot => BusStop::All,
            Scope::Limb(limb) => BusStop::Limb(p.limb_index(limb)?),
        };
        Some(StopAt { bus, stop })
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
        let at = |bus, stop| StopAt { bus, stop };
        let stop = |scope| route_stop(&plans, scope).collect::<Vec<_>>();
        assert_eq!(
            stop(Scope::Robot),
            [at(0, BusStop::All), at(1, BusStop::All)]
        );
        // The right arm is limb 0 on can0 and limb 1 on can1.
        assert_eq!(
            stop(Scope::Limb(LimbName::RightArm)),
            [at(0, BusStop::Limb(0)), at(1, BusStop::Limb(1))]
        );
        assert_eq!(
            stop(Scope::Limb(LimbName::Waist)),
            [at(0, BusStop::Limb(1))]
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
}
