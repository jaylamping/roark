//! The operator's requests through the in-process queue, and how control turns them into each bus's orders. Pure, so
//! it is tested on any OS; the control thread (Linux) carries the orders to the rings.

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

/// A request to the runtime. Enable and plans come with the control step that runs them (PLAN step 7, 4b-2); until then
/// the runtime never enables anything.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Request {
    /// Stop, always accepted (PLAN item 3a). A limb with no joint on any bus has nothing to stop.
    Stop(Scope),
    /// The operator's clear of one stopped limb: one [`Reply`] per bus the limb is on, under `tag`, or one refusal
    /// when it is on none.
    Clear {
        /// The requester's tag, echoed in each reply.
        tag: u64,
        /// The limb.
        limb: LimbName,
    },
}

/// The answer to a [`Request::Clear`], one per bus the limb is on.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Reply {
    /// The request's tag.
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
    /// The bus's order ring was full; nothing was asked of it. Ask again.
    #[error("the bus's order ring was full")]
    Busy,
}

/// One order for the bus at `bus`, the index in the plan.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Routed {
    /// The bus.
    pub bus: usize,
    /// The order.
    pub order: Order,
}

/// The orders `request` asks of each bus in `plans`, in bus order: at most one per bus.
pub fn route(plans: &[BusPlan], request: Request) -> impl Iterator<Item = Routed> + '_ {
    plans.iter().enumerate().filter_map(move |(bus, p)| {
        let order = match request {
            Request::Stop(Scope::Robot) => Order::StopAll,
            Request::Stop(Scope::Limb(limb)) => Order::StopLimb(p.limb_index(limb)?),
            Request::Clear { tag, limb } => Order::Rearm {
                tag,
                limb: p.limb_index(limb)?,
            },
        };
        Some(Routed { bus, order })
    })
}

/// The reply for the bus at `bus`'s answer to a re-arm `route` made; `None` for a limb index the plan doesn't have, which
/// only a bug can give.
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

#[cfg(test)]
mod tests {
    use can::BusDrive;
    use robstride::DeviceId;

    use super::*;

    fn bus(name: &str, limbs: &[LimbName]) -> BusPlan {
        BusPlan {
            name: name.to_owned(),
            bitrate_bps: 1_000_000,
            drives: (0..limbs.len())
                .map(|limb| BusDrive {
                    device: DeviceId::new(u64::try_from(limb + 1).unwrap()).unwrap(),
                    limb,
                })
                .collect(),
            joints: Vec::new(),
            limbs: limbs.to_vec(),
        }
    }

    /// Guards: safety - a stop or clear reaches exactly the buses and limb indices of the limb it names, a robot stop
    /// every bus, and a limb on no bus none, so an operator's stop never misses a bus the limb is on and never touches a
    /// limb it didn't name (PLAN item 6: a stop names its scope; tenet 1).
    #[test]
    fn requests_reach_the_named_limb_on_every_bus_it_is_on_and_nothing_else() {
        let plans = [
            bus("can0", &[LimbName::RightArm, LimbName::Waist]),
            bus("can1", &[LimbName::LeftArm]),
            bus("can2", &[LimbName::LeftLeg, LimbName::RightArm]),
        ];
        let routed = |r| route(&plans, r).collect::<Vec<_>>();
        assert_eq!(
            routed(Request::Stop(Scope::Robot)),
            (0..3)
                .map(|bus| Routed {
                    bus,
                    order: Order::StopAll
                })
                .collect::<Vec<_>>()
        );
        assert_eq!(
            routed(Request::Stop(Scope::Limb(LimbName::RightArm))),
            [
                Routed {
                    bus: 0,
                    order: Order::StopLimb(0)
                },
                Routed {
                    bus: 2,
                    order: Order::StopLimb(1)
                },
            ]
        );
        assert_eq!(
            routed(Request::Clear {
                tag: 4,
                limb: LimbName::Waist
            }),
            [Routed {
                bus: 0,
                order: Order::Rearm { tag: 4, limb: 1 }
            }]
        );
        assert_eq!(routed(Request::Stop(Scope::Limb(LimbName::RightLeg))), []);
    }

    /// Guards: safety - a bus's re-arm answer comes back under the requester's tag and the skeleton limb it stands
    /// for, with the bus's refusal kept, so the operator learns which bus refused a clear and why.
    #[test]
    fn a_bus_answer_names_the_skeleton_limb_and_keeps_the_refusal() {
        let plans = [bus("can0", &[LimbName::RightArm, LimbName::Waist])];
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
        assert_eq!(reply(&plans, 0, Rearmed { limb: 2, ..answer }), None);
        assert_eq!(reply(&plans, 1, answer), None);
    }
}
