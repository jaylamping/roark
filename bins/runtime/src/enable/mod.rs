//! (rt) The operator's enable, as the control thread runs it each tick, and the hold of every enabled joint. Pure over
//! the rings and snapshots: unit tested over hand-built snapshots, and run end to end by the sim suite on `vcan`.
//!
//! An enable names a set of joints. Every named joint's preflight runs first, over its bus's slow requests; in the tick
//! the last one passes, every enable sequence starts from its proof; each joint is held from the tick its own drive is
//! in Run and MIT mode, and the enable is answered once every one is. Any refusal before an Enable may have gone refuses
//! the whole enable with nothing to stop; any failure after stops every limb the enable named (`safety`'s duties to the
//! runtime: one preflight per enable, no slow request while enabling, a failure after an Enable is planned stops the
//! limb). A limb over several buses is one limb throughout: a part of it stopped on any bus fails the enable and ends
//! its holds everywhere. The runtime never enables on its own.

mod hold;
mod preflight;
mod reply;
#[cfg(test)]
mod tests;

use can::{CommandBatch, Snapshot};
use robstride::Drive;
use safety::{
    ANSWER_WITHIN_NS, Cause, EnableFailure, Enabling, Next, Preflight, PreflightPassed, Refusal,
    RuleId, Seen,
};
use skeleton::LimbName;

use crate::latch::StopLatch;
use crate::request::Scope;
use crate::roster::{JointSet, Roster, RosterJoint};

use hold::{LimbVerdict, halted, limb_on};
pub(crate) use preflight::{SLOW_RING, SlowEnds};
use preflight::{drain_stray, step_preflight};
pub use reply::{Enable, EnableRefused, EnableReply};

/// Where one joint is.
#[derive(Debug)]
enum Phase {
    Off,
    Preflight {
        preflight: Preflight,
        first_tag: u32,
    },
    Passed(PreflightPassed),
    Enabling(Enabling),
    /// Enabled and held.
    Enabled(Drive),
}

/// What the enabler did, counted over the run.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Counts {
    /// Slow results that answered no preflight running.
    pub(crate) stray_results: u64,
    /// Limbs stopped under `host.mode`'s limb-mate clause, a held limb's or the enable running's: one per limb each
    /// time, however long the stop takes to show.
    pub(crate) mode_stops: u64,
    /// Enabled joints no longer held, one per joint each time: their limb stopped on some bus (then cleared, perhaps),
    /// `host.mode`'s limb-mate clause stopped it, or their enable failed.
    pub(crate) holds_ended: u64,
}

/// The control thread's enables and holds.
pub(crate) struct Enabler {
    /// The enable running, with its tag.
    run: Option<(u64, JointSet)>,
    /// Every roster joint's phase, by index; made once, at start.
    phases: Vec<Phase>,
    /// Each bus's count of other hosts' frames as the enable running began, by plan index; made once, at start.
    foreign: Vec<u64>,
    /// When the enable running began.
    started_ns: u64,
}

/// One tick's view of the buses, for [`Enabler::tick`].
pub(crate) struct Buses<'a> {
    /// Each bus's newest snapshot, by plan index.
    pub(crate) snapshots: &'a [Option<Snapshot>],
    /// Each bus's slow rings, by plan index.
    pub(crate) slow: &'a mut [SlowEnds],
    /// The next tick's batch for each bus, by plan index.
    pub(crate) batches: &'a mut [CommandBatch],
    /// Whether each bus thread has ended, by plan index.
    pub(crate) ended: &'a [bool],
}

/// Where one joint of the enable running is, after its step.
#[derive(Clone, Copy, Debug)]
enum Progress {
    /// Its preflight or its sequence is still running.
    Running,
    /// Its preflight passed; its sequence waits for every other joint's proof.
    Passed,
    /// It is enabled, and held.
    Enabled,
}

/// How the enable running failed.
#[derive(Clone, Copy, Debug)]
enum Failed {
    Preflight {
        joint: usize,
        refusal: Refusal,
    },
    Sequence {
        joint: usize,
        failure: EnableFailure,
    },
    Ended {
        joint: usize,
    },
    Foreign {
        bus: usize,
    },
    Mode {
        limb: LimbName,
    },
    Unseen {
        joint: usize,
    },
}

impl Enabler {
    /// The enabler for `roster`, whose joints are on `buses` buses.
    pub(crate) fn new(roster: &Roster, buses: usize) -> Self {
        Self {
            run: None,
            phases: (0..roster.len()).map(|_| Phase::Off).collect(),
            foreign: vec![0; buses],
            started_ns: 0,
        }
    }

    /// Take a new enable at `now_ns`: refused at once if another runs, the recording has failed, it names nothing or a
    /// joint the roster doesn't have, a joint already enabled or of a limb held on any bus, or one whose skeleton entry
    /// can't pass preflight;
    /// otherwise every named joint's preflight starts.
    pub(crate) fn take(
        &mut self,
        roster: &Roster,
        enable: Enable,
        buses: &mut Buses<'_>,
        logging_failed: bool,
        now_ns: u64,
    ) -> Option<EnableReply> {
        if let Err(why) = self.check(roster, enable, logging_failed) {
            return Some(EnableReply {
                tag: enable.tag,
                outcome: Err(why),
            });
        }
        for (bus, seen) in self.foreign.iter_mut().enumerate() {
            *seen = foreign_host(buses.snapshots, bus);
        }
        for joint in enable.joints.iter() {
            let (Some(entry), Some(phase)) = (roster.joint(joint), self.phases.get_mut(joint))
            else {
                continue;
            };
            let (Ok(target), Some((bus, slot))) = (entry.target, entry.slot()) else {
                continue;
            };
            let Some(ends) = buses.slow.get_mut(bus) else {
                continue;
            };
            let first_tag = ends.next_tag;
            ends.next_tag = ends.next_tag.wrapping_add(Preflight::TAGS);
            *phase = Phase::Preflight {
                preflight: Preflight::start(target, slot, first_tag, now_ns),
                first_tag,
            };
        }
        self.run = Some((enable.tag, enable.joints));
        self.started_ns = now_ns;
        None
    }

    /// Why `enable` is refused before anything is sent, if it is.
    fn check(
        &self,
        roster: &Roster,
        enable: Enable,
        logging_failed: bool,
    ) -> Result<(), EnableRefused> {
        if self.run.is_some() {
            return Err(EnableRefused::Busy);
        }
        if logging_failed {
            return Err(EnableRefused::Logging);
        }
        if enable.joints.is_empty() {
            return Err(EnableRefused::Empty);
        }
        // A joint already enabled is named as such, whichever other joint of its limb comes first.
        if let Some(joint) = enable
            .joints
            .iter()
            .find(|j| matches!(self.phases.get(*j), Some(Phase::Enabled(_))))
        {
            return Err(EnableRefused::AlreadyEnabled { joint });
        }
        for joint in enable.joints.iter() {
            let Some(entry) = roster.joint(joint) else {
                return Err(EnableRefused::UnknownJoint { joint });
            };
            // A limb held on any bus is enabled: preflight's own check reads only the joint's bus, where another part
            // of the limb may be idle.
            if self.limb_held(roster, entry.limb) {
                return Err(EnableRefused::Preflight {
                    joint,
                    refusal: Refusal::LimbActive,
                });
            }
            if let Err(refusal) = entry.target {
                return Err(EnableRefused::Preflight { joint, refusal });
            }
            // `Target::new` refuses a joint with no bus, and the plan puts every joint with one on it.
            if entry.at.is_none() {
                return Err(EnableRefused::Preflight {
                    joint,
                    refusal: Refusal::Unwired,
                });
            }
        }
        Ok(())
    }

    /// Whether any joint of `limb`, on any bus, is enabled.
    fn limb_held(&self, roster: &Roster, limb: LimbName) -> bool {
        self.phases.iter().enumerate().any(|(j, phase)| {
            matches!(phase, Phase::Enabled(_)) && roster.joint(j).is_some_and(|e| e.limb == limb)
        })
    }

    /// End the enable running, if any, because the run is ending, which stops every limb: so is any joint of it whose
    /// Enable may have gone. Its joints already enabled keep their phase, though no further hold is sent, and each bus
    /// stops their limbs as the run ends; the rest are dropped.
    pub(crate) fn end(&mut self) -> Option<EnableReply> {
        let (tag, joints) = self.run.take()?;
        for joint in joints.iter() {
            if let Some(phase) = self.phases.get_mut(joint)
                && !matches!(phase, Phase::Enabled(_))
            {
                *phase = Phase::Off;
            }
        }
        Some(EnableReply {
            tag,
            outcome: Err(EnableRefused::Ending),
        })
    }

    /// One tick, at `now_ns`, building the batches for tick `next`: step the enable running and hold every enabled
    /// joint. Gives the enable's reply once it ends. A stop it asks goes into this pass's orders.
    pub(crate) fn tick(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        next: u64,
        now_ns: u64,
        counts: &mut Counts,
    ) -> Option<EnableReply> {
        let reply = self.step_run(roster, buses, stops, next, now_ns, counts);
        self.hold(roster, buses, stops, counts);
        reply
    }

    fn step_run(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        next: u64,
        now_ns: u64,
        counts: &mut Counts,
    ) -> Option<EnableReply> {
        let Some((tag, joints)) = self.run else {
            drain_stray(buses.slow, counts);
            return None;
        };
        self.route_results(roster, joints, buses.slow, now_ns, counts);
        if let Some(bus) = self.foreign_since(roster, joints, buses.snapshots) {
            return Some(self.fail(roster, tag, joints, Failed::Foreign { bus }, stops, counts));
        }
        let mut all_passed = true;
        let mut all_enabled = true;
        for joint in joints.iter() {
            match self.step_joint(roster, buses, stops, joint, next, now_ns) {
                Ok(Progress::Passed) => all_enabled = false,
                Ok(Progress::Enabled) => all_passed = false,
                Ok(Progress::Running) => {
                    all_passed = false;
                    all_enabled = false;
                }
                Err(failure) => {
                    return Some(self.fail(roster, tag, joints, failure, stops, counts));
                }
            }
        }
        // Every proof in hand: every sequence starts in this tick, from proofs no event has voided (each sequence
        // checks its own limb's generation, faults and mode at its first step).
        if all_passed {
            for joint in joints.iter() {
                if let Some(phase) = self.phases.get_mut(joint)
                    && let Phase::Passed(_) = phase
                    && let Phase::Passed(proof) = core::mem::replace(phase, Phase::Off)
                {
                    *phase = Phase::Enabling(Enabling::new(proof, now_ns));
                }
            }
            return None;
        }
        if all_enabled {
            self.run = None;
            return Some(EnableReply {
                tag,
                outcome: Ok(()),
            });
        }
        None
    }

    /// The first bus a named joint is on that has seen another host's frame since the enable began.
    fn foreign_since(
        &self,
        roster: &Roster,
        joints: JointSet,
        snapshots: &[Option<Snapshot>],
    ) -> Option<usize> {
        joints
            .iter()
            .filter_map(|j| roster.joint(j)?.slot().map(|(bus, _)| bus))
            .find(|bus| {
                foreign_host(snapshots, *bus) > self.foreign.get(*bus).copied().unwrap_or(u64::MAX)
            })
    }

    /// One joint of the enable running, one tick on.
    fn step_joint(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        joint: usize,
        next: u64,
        now_ns: u64,
    ) -> Result<Progress, Failed> {
        // `take` started only joints wired to a bus the plan runs; anything else refuses rather than counts as done.
        let unwired = Failed::Preflight {
            joint,
            refusal: Refusal::Unwired,
        };
        self.mode_check(roster, buses.snapshots, joint)?;
        let (Some(entry), Some(phase)) = (roster.joint(joint), self.phases.get_mut(joint)) else {
            return Err(unwired);
        };
        let Some(wire) = entry.at.as_ref() else {
            return Err(unwired);
        };
        let (bus, slot, bus_name) = (wire.bus, wire.slot, &wire.name);
        if buses.ended.get(bus).copied().unwrap_or(true) {
            return Err(Failed::Ended { joint });
        }
        let seen = buses
            .snapshots
            .get(bus)
            .and_then(Option::as_ref)
            .and_then(|s| Seen::of(bus_name, s, slot));
        // A joint not yet in its bus's snapshot can't step, so none of its own deadlines run: this one bounds the wait.
        if seen.is_none() && now_ns.saturating_sub(self.started_ns) > ANSWER_WITHIN_NS {
            return Err(Failed::Unseen { joint });
        }
        // A limb is one limb over every bus it is on: a part stopped anywhere voids the proofs and ends the sequences.
        if let Some(stop) = halted(roster, buses.snapshots, entry.limb) {
            return Err(halted_failure(phase, joint, stop));
        }
        match phase {
            Phase::Off => Err(unwired),
            Phase::Passed(_) => Ok(Progress::Passed),
            Phase::Enabled(_) => still_active(buses.snapshots, entry, joint),
            Phase::Preflight { preflight, .. } => {
                let Some(seen) = seen else {
                    return Ok(Progress::Running);
                };
                match step_preflight(preflight, seen, buses, bus, joint, now_ns)? {
                    Some(proof) => {
                        *phase = Phase::Passed(proof);
                        Ok(Progress::Passed)
                    }
                    None => Ok(Progress::Running),
                }
            }
            Phase::Enabling(enabling) => {
                let Some(seen) = seen else {
                    return Ok(Progress::Running);
                };
                match enabling.step(seen, next, now_ns) {
                    Next::Send(frame) => {
                        place(buses, stops, entry, frame);
                        Ok(Progress::Running)
                    }
                    Next::Wait => Ok(Progress::Running),
                    Next::Enabled => {
                        // Held from this tick (`hold` sends its first command now), not from the enable's answer: a
                        // drive in Run left without commands for the slowest mate would go stale or time out.
                        *phase = Phase::Enabled(enabling.drive());
                        Ok(Progress::Enabled)
                    }
                    Next::Refused(failure) | Next::Stop(failure) => {
                        Err(Failed::Sequence { joint, failure })
                    }
                }
            }
        }
    }

    /// `host.mode`'s limb-mate clause for `joint`'s limb, once an Enable of it may have gone (the limb is then held).
    fn mode_check(
        &self,
        roster: &Roster,
        snapshots: &[Option<Snapshot>],
        joint: usize,
    ) -> Result<(), Failed> {
        let held = match self.phases.get(joint) {
            Some(Phase::Enabled(_)) => true,
            Some(Phase::Enabling(e)) => e.enable_planned(),
            Some(Phase::Off | Phase::Preflight { .. } | Phase::Passed(_)) | None => false,
        };
        match roster.joint(joint) {
            Some(entry)
                if held
                    && matches!(
                        self.verdict(roster, snapshots, entry.limb),
                        LimbVerdict::Mate(_)
                    ) =>
            {
                Err(Failed::Mode { limb: entry.limb })
            }
            Some(_) | None => Ok(()),
        }
    }

    /// End the enable running with `failure`: stop every limb it named if any Enable of it may have gone out.
    fn fail(
        &mut self,
        roster: &Roster,
        tag: u64,
        joints: JointSet,
        failure: Failed,
        stops: &StopLatch,
        counts: &mut Counts,
    ) -> EnableReply {
        let stopped = joints.iter().any(|j| match self.phases.get(j) {
            Some(Phase::Enabling(e)) => e.enable_planned(),
            Some(Phase::Enabled(_)) => true,
            Some(Phase::Off | Phase::Preflight { .. } | Phase::Passed(_)) | None => false,
        });
        let why = match failure {
            Failed::Preflight { joint, refusal } if !stopped => {
                EnableRefused::Preflight { joint, refusal }
            }
            // A preflight refusal can't come once an Enable is planned (every proof is in hand by then); counted as the
            // sequence's, so the reply says the limbs were stopped.
            Failed::Preflight { joint, .. } => EnableRefused::Sequence {
                joint,
                failure: EnableFailure::LimbStopped {
                    stop: None,
                    enable_planned: true,
                },
                stopped,
            },
            Failed::Sequence { joint, failure } => EnableRefused::Sequence {
                joint,
                failure,
                stopped,
            },
            Failed::Ended { joint } => EnableRefused::BusEnded { joint, stopped },
            Failed::Mode { limb } => {
                counts.mode_stops += 1;
                EnableRefused::LimbMate { limb, stopped }
            }
            Failed::Foreign { bus } => EnableRefused::ForeignHost { bus, stopped },
            Failed::Unseen { joint } => EnableRefused::Unseen { joint, stopped },
        };
        // The stop goes under the refusal's rule, as its event names it. Every refusal built here has one
        // (`a_failed_enable_stops_its_limb_under_the_rule_its_refusal_names` checks each), so the fallback, a stop
        // carried for a cause recorded elsewhere, is never taken.
        let cause = why.named().rule.map_or(Cause::Follows, Cause::Rule);
        for joint in joints.iter() {
            if let Some(phase) = self.phases.get_mut(joint) {
                if let Phase::Enabled(_) = phase {
                    counts.holds_ended += 1;
                }
                *phase = Phase::Off;
            }
            if stopped && let Some(entry) = roster.joint(joint) {
                stops.ask(Scope::Limb(entry.limb), cause);
            }
        }
        self.run = None;
        EnableReply {
            tag,
            outcome: Err(why),
        }
    }
}

/// An enabled joint of the enable running: its limb must still be the Active one the Enable made, or it was stopped and
/// cleared since.
fn still_active(
    snapshots: &[Option<Snapshot>],
    entry: &RosterJoint,
    joint: usize,
) -> Result<Progress, Failed> {
    match limb_on(snapshots, entry) {
        Some(l) if l.state == can::LimbState::Active => Ok(Progress::Enabled),
        limb => Err(Failed::Sequence {
            joint,
            failure: EnableFailure::LimbStopped {
                stop: limb.and_then(|l| l.stop),
                enable_planned: true,
            },
        }),
    }
}

/// How a joint of the enable running fails when its limb is stopped on some bus: before any Enable of it, a refused
/// preflight; after, a sequence whose limb stopped.
fn halted_failure(phase: &Phase, joint: usize, stop: Option<can::StopReason>) -> Failed {
    match phase {
        Phase::Off | Phase::Preflight { .. } | Phase::Passed(_) => Failed::Preflight {
            joint,
            refusal: Refusal::LimbStopped { stop },
        },
        Phase::Enabling(enabling) => Failed::Sequence {
            joint,
            failure: EnableFailure::LimbStopped {
                stop,
                enable_planned: enabling.enable_planned(),
            },
        },
        Phase::Enabled(_) => Failed::Sequence {
            joint,
            failure: EnableFailure::LimbStopped {
                stop,
                enable_planned: true,
            },
        },
    }
}

/// `frame` into its joint's slot of the next batch. The plan keeps every slot in range; a frame that can't go stops its
/// limb.
fn place(buses: &mut Buses<'_>, stops: &StopLatch, entry: &RosterJoint, frame: robstride::Frame) {
    let placed = entry.slot().is_some_and(|(bus, slot)| {
        buses
            .batches
            .get_mut(bus)
            .is_some_and(|b| b.set(slot, frame))
    });
    if !placed {
        // The plan keeps every slot in range, so this is a runtime bug: a broken control side (`host.hang`).
        stops.ask(Scope::Limb(entry.limb), Cause::Rule(RuleId::HostHang));
    }
}

/// Bus `bus`'s count of other hosts' frames, from its newest snapshot (0 before its first).
fn foreign_host(snapshots: &[Option<Snapshot>], bus: usize) -> u64 {
    snapshots
        .get(bus)
        .and_then(Option::as_ref)
        .map_or(0, |s| s.counters.foreign_host)
}
