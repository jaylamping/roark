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
#[cfg(test)]
mod tests;

use can::{CommandBatch, MAX_DRIVES, SlowRequest, SlowResult, Snapshot};
use robstride::Drive;
use rtrb::{Consumer, Producer};
use safety::{EnableFailure, Enabling, Next, Preflight, PreflightPassed, Refusal, Seen, Step};

use crate::dispatch::StopLatch;
use crate::request::Scope;
use crate::roster::{JointSet, Roster, RosterJoint};

use hold::{halted, limb_on};

/// The operator's enable of a set of joints, answered by one [`EnableReply`] under `tag`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Enable {
    /// The requester's tag, echoed in the reply.
    pub tag: u64,
    /// The joints, from [`Runtime::joints`](crate::Runtime::joints) or [`Roster::set`].
    pub joints: JointSet,
}

/// The answer to an [`Enable`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EnableReply {
    /// The enable's tag.
    pub tag: u64,
    /// Enabled and held, or why not.
    pub outcome: Result<(), EnableRefused>,
}

/// Why an enable didn't happen. A joint is named by its index in the roster. Where `stopped` is false, nothing of the
/// enable was sent past preflight's reads and writes, and nothing was enabled.
#[derive(Clone, Copy, Debug, PartialEq, thiserror::Error)]
pub enum EnableRefused {
    /// It named no joint.
    #[error("no joint named")]
    Empty,
    /// It named an index the roster doesn't have.
    #[error("no joint {joint} in the roster")]
    UnknownJoint {
        /// The index.
        joint: usize,
    },
    /// Another enable is still running.
    #[error("another enable is running")]
    Busy,
    /// The session's recording has failed: no new enable while the log can't be written (PLAN item 6 `host.logging`).
    #[error("the recording has failed")]
    Logging,
    /// A named joint is already enabled.
    #[error("joint {joint} is already enabled")]
    AlreadyEnabled {
        /// The joint.
        joint: usize,
    },
    /// A named joint's preflight refused it, or its skeleton entry did before anything was sent, or its limb stopped on
    /// some bus before any Enable was planned. Nothing was enabled.
    #[error("joint {joint}: {refusal:?}")]
    Preflight {
        /// The joint.
        joint: usize,
        /// Why.
        refusal: Refusal,
    },
    /// A named joint's enable sequence failed, or its limb stopped on some bus once its Enable was planned.
    #[error("joint {joint}: {failure:?} (limbs stopped: {stopped})")]
    Sequence {
        /// The joint.
        joint: usize,
        /// Why.
        failure: EnableFailure,
        /// Whether an Enable of this enable may have gone out, so every limb it named was stopped.
        stopped: bool,
    },
    /// A named joint's bus thread has ended.
    #[error("joint {joint}'s bus thread has ended (limbs stopped: {stopped})")]
    BusEnded {
        /// The joint.
        joint: usize,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// Another host sent on a bus a named joint is on while the enable ran: its writes may have changed what preflight
    /// proved (PLAN item 3: only the realtime process transmits).
    #[error("another host sent on bus {bus} during the enable (limbs stopped: {stopped})")]
    ForeignHost {
        /// The bus, as its index in the plan.
        bus: usize,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// The run is ending.
    #[error("the run is ending")]
    Ending,
}

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

/// One bus's slow-request rings, as control holds them.
pub(crate) struct SlowEnds {
    pub(crate) requests: Producer<SlowRequest>,
    pub(crate) results: Consumer<SlowResult>,
    /// The next block of tags for a preflight on this bus.
    next_tag: u32,
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

/// What the enabler did, counted over the run.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Counts {
    /// Slow results that answered no preflight running.
    pub(crate) stray_results: u64,
    /// Held limbs stopped under `host.mode`'s limb-mate clause: one per stop, however long the stop takes to show.
    pub(crate) mode_stops: u64,
    /// Joints no longer held, one per joint each time: their limb stopped (or `host.mode` stopped it).
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
}

impl Enabler {
    /// The enabler for `roster`, whose joints are on `buses` buses.
    pub(crate) fn new(roster: &Roster, buses: usize) -> Self {
        Self {
            run: None,
            phases: (0..roster.len()).map(|_| Phase::Off).collect(),
            foreign: vec![0; buses],
        }
    }

    /// Take a new enable at `now_ns`: refused at once if another runs, the recording has failed, it names nothing or a
    /// joint the roster doesn't have, a joint already enabled or one whose skeleton entry can't pass preflight;
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
        for joint in enable.joints.iter() {
            let Some(entry) = roster.joint(joint) else {
                return Err(EnableRefused::UnknownJoint { joint });
            };
            if matches!(self.phases.get(joint), Some(Phase::Enabled(_))) {
                return Err(EnableRefused::AlreadyEnabled { joint });
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

    /// End the enable running, if any, because the run is ending. Its joints already enabled stay held until the bus
    /// stops their limbs.
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
            // Results for no preflight: drained and counted, so an old one never answers a new preflight's tag.
            for ends in buses.slow.iter_mut() {
                for _ in 0..ends.results.buffer().capacity() {
                    if ends.results.pop().is_err() {
                        break;
                    }
                    counts.stray_results += 1;
                }
            }
            return None;
        };
        self.route_results(roster, joints, buses.slow, now_ns, counts);
        if let Some(bus) = self.foreign_since(roster, joints, buses.snapshots) {
            return Some(self.fail(roster, tag, joints, Failed::Foreign { bus }, stops));
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
                Err(failure) => return Some(self.fail(roster, tag, joints, failure, stops)),
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
        // A limb is one limb over every bus it is on: a part stopped anywhere voids the proofs and ends the sequences.
        if let Some(stop) = halted(roster, buses.snapshots, entry.limb) {
            return Err(match phase {
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
            });
        }
        match phase {
            Phase::Off => Err(unwired),
            Phase::Passed(_) => Ok(Progress::Passed),
            Phase::Enabled(_) => {
                // Held: its limb must still be the Active one the Enable made, or it was stopped and cleared since.
                if limb_on(buses.snapshots, entry)
                    .is_some_and(|l| l.state == can::LimbState::Active)
                {
                    Ok(Progress::Enabled)
                } else {
                    Err(Failed::Sequence {
                        joint,
                        failure: EnableFailure::LimbStopped {
                            stop: limb_on(buses.snapshots, entry).and_then(|l| l.stop),
                            enable_planned: true,
                        },
                    })
                }
            }
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

    /// Each bus's slow results to the preflight whose slot and block of tags they carry; any other is counted and dropped.
    fn route_results(
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

    /// End the enable running with `failure`: stop every limb it named if any Enable of it may have gone out.
    fn fail(
        &mut self,
        roster: &Roster,
        tag: u64,
        joints: JointSet,
        failure: Failed,
        stops: &StopLatch,
    ) -> EnableReply {
        let stopped = joints.iter().any(|j| match self.phases.get(j) {
            Some(Phase::Enabling(e)) => e.enable_planned(),
            Some(Phase::Enabled(_)) => true,
            Some(Phase::Off | Phase::Preflight { .. } | Phase::Passed(_)) | None => false,
        });
        for joint in joints.iter() {
            if let Some(phase) = self.phases.get_mut(joint) {
                *phase = Phase::Off;
            }
            if stopped && let Some(entry) = roster.joint(joint) {
                stops.ask(Scope::Limb(entry.limb));
            }
        }
        self.run = None;
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
            Failed::Foreign { bus } => EnableRefused::ForeignHost { bus, stopped },
        };
        EnableReply {
            tag,
            outcome: Err(why),
        }
    }
}

/// One preflight, one tick on: its request onto its bus's ring, its proof once it passes, or its refusal.
fn step_preflight(
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
        stops.ask(Scope::Limb(entry.limb));
    }
}

/// Bus `bus`'s count of other hosts' frames, from its newest snapshot (0 before its first).
fn foreign_host(snapshots: &[Option<Snapshot>], bus: usize) -> u64 {
    snapshots
        .get(bus)
        .and_then(Option::as_ref)
        .map_or(0, |s| s.counters.foreign_host)
}

/// The slow rings' size: a request per slot a bus holds.
pub(crate) const SLOW_RING: usize = MAX_DRIVES;
