//! (rt) Each named joint's preflight, over its bus's slow-request rings: the rings, the routing of their results, and
//! one preflight's step.

use can::{MAX_DRIVES, SlowRequest, SlowResult};
use rtrb::{Consumer, Producer};
use safety::{Preflight, PreflightPassed, Refusal, Seen, Step};

use super::{Buses, Counts, Enabler, Failed, Phase};
use crate::roster::{JointSet, Roster, RosterJoint};

/// The slow rings' size: a request per slot a bus holds.
pub(crate) const SLOW_RING: usize = MAX_DRIVES;

/// One bus's slow-request rings, as control holds them.
pub(crate) struct SlowEnds {
    pub(crate) requests: Producer<SlowRequest>,
    pub(crate) results: Consumer<SlowResult>,
    /// The next block of tags for a preflight on this bus.
    pub(super) next_tag: u32,
}

impl SlowEnds {
    pub(crate) const fn new(
        requests: Producer<SlowRequest>,
        results: Consumer<SlowResult>,
    ) -> Self {
        Self {
            requests,
            results,
            next_tag: 0,
        }
    }
}

impl Enabler {
    /// Each bus's slow results to the preflight whose slot and block of tags they carry; any other is counted and dropped.
    pub(super) fn route_results(
        &mut self,
        roster: &Roster,
        joints: JointSet,
        slow: &mut [SlowEnds],
        now_ns: u64,
        counts: &mut Counts,
    ) {
        for (bus, ends) in slow.iter_mut().enumerate() {
            for _ in 0..ends.results.buffer().capacity() {
                let Ok(result) = ends.results.pop() else {
                    break;
                };
                let owner = joints.iter().find(|j| {
                    roster
                        .joint(*j)
                        .and_then(RosterJoint::slot)
                        .is_some_and(|(b, slot)| b == bus && slot == result.slot)
                        && matches!(self.phases.get(*j), Some(Phase::Preflight { first_tag, .. })
                            if result.tag.wrapping_sub(*first_tag) < Preflight::TAGS)
                });
                match owner.and_then(|j| self.phases.get_mut(j)) {
                    Some(Phase::Preflight { preflight, .. }) => preflight.answered(result, now_ns),
                    _ => counts.stray_results += 1,
                }
            }
        }
    }
}

/// Results for no preflight: drained and counted, so an old one never answers a new preflight's tag.
pub(super) fn drain_stray(slow: &mut [SlowEnds], counts: &mut Counts) {
    for ends in slow.iter_mut() {
        for _ in 0..ends.results.buffer().capacity() {
            if ends.results.pop().is_err() {
                break;
            }
            counts.stray_results += 1;
        }
    }
}

/// One preflight, one tick on: its request onto its bus's ring, its proof once it passes, or its refusal.
pub(super) fn step_preflight(
    preflight: &mut Preflight,
    seen: Seen<'_>,
    buses: &mut Buses<'_>,
    bus: usize,
    joint: usize,
    now_ns: u64,
) -> Result<Option<PreflightPassed>, Failed> {
    match preflight.poll(seen, now_ns) {
        Step::Submit(request) => {
            // A ring of a request per slot: one preflight has one in flight, so it always has room. A full ring is a bug
            // here; it refuses the enable rather than waits.
            let pushed = buses
                .slow
                .get_mut(bus)
                .is_some_and(|ends| ends.requests.push(request).is_ok());
            if pushed {
                Ok(None)
            } else {
                Err(Failed::Preflight {
                    joint,
                    refusal: Refusal::NoStatus,
                })
            }
        }
        Step::Wait => Ok(None),
        Step::Passed(proof) => Ok(Some(proof)),
        Step::Refused(refusal) => Err(Failed::Preflight { joint, refusal }),
        // Only a preflight that already passed says so: never one still running here.
        Step::Spent => Err(Failed::Preflight {
            joint,
            refusal: Refusal::NoStatus,
        }),
    }
}
