//! (rt) The operator's enable, as the control thread runs it each tick, and the hold of every enabled joint. Pure over
//! the rings and snapshots, so the parts that need no bus are tested on any OS; the sim suite runs the rest on `vcan`.
//!
//! An enable names a set of joints. Every named joint's preflight runs first, over its bus's slow requests; in the tick
//! the last one passes, every enable sequence starts from its proof; once every drive is in Run and MIT mode the joints
//! are enabled and held. Any refusal before an Enable may have gone refuses the whole enable with nothing to stop; any
//! failure after stops every limb the enable named (`safety`'s duties to the runtime: one preflight per enable, no slow
//! request while enabling, a failure after an Enable is planned stops the limb). The runtime never enables on its own.

use can::{CommandBatch, LimbState, MAX_DRIVES, SlowRequest, SlowResult, Snapshot, StopReason};
use robstride::{
    Drive, MitCommand, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians, encode,
};
use rtrb::{Consumer, Producer};
use safety::{EnableFailure, Enabling, Next, Preflight, PreflightPassed, Refusal, Seen, Step};
use skeleton::LimbName;

use crate::dispatch::StopLatch;
use crate::request::Scope;
use crate::roster::{JointSet, Roster};

/// The operator's enable of a set of joints, answered by one [`EnableReply`] under `tag`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Enable {
    /// The requester's tag, echoed in the reply.
    pub tag: u64,
    /// The joints, from [`Runtime::joints`](crate::Runtime::joints) on Linux or [`Roster::set`].
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

/// Why an enable didn't happen. A joint is named by its index in the roster.
#[derive(Clone, Copy, Debug, PartialEq, thiserror::Error)]
pub enum EnableRefused {
    /// It named no joint.
    #[error("no joint named")]
    Empty,
    /// Another enable is still running.
    #[error("another enable is running")]
    Busy,
    /// A named joint is already enabled.
    #[error("joint {joint} is already enabled")]
    AlreadyEnabled {
        /// The joint.
        joint: usize,
    },
    /// A named joint's preflight refused it, or its skeleton entry did before anything was sent. Nothing was enabled.
    #[error("joint {joint}: {refusal:?}")]
    Preflight {
        /// The joint.
        joint: usize,
        /// Why.
        refusal: Refusal,
    },
    /// A named joint's enable sequence failed. `stopped` when an Enable of this enable may have gone out, so every
    /// limb it named was stopped.
    #[error("joint {joint}: {failure:?} (limbs stopped: {stopped})")]
    Sequence {
        /// The joint.
        joint: usize,
        /// Why.
        failure: EnableFailure,
        /// Whether the named limbs were stopped.
        stopped: bool,
    },
    /// A named joint's bus thread has ended.
    #[error("joint {joint}'s bus thread has ended")]
    BusEnded {
        /// The joint.
        joint: usize,
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

/// What the enabler did this tick, beyond its reply.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Counts {
    /// Slow results that answered no preflight running.
    pub(crate) stray_results: u64,
    /// Limbs stopped because a drive of an enabled limb that this host never enabled left Reset (`host.mode`).
    pub(crate) mode_stops: u64,
    /// Enabled joints dropped from hold because their limb stopped.
    pub(crate) holds_ended: u64,
}

/// The control thread's enables and holds.
pub(crate) struct Enabler {
    /// The enable running, with its tag.
    run: Option<(u64, JointSet)>,
    /// Every roster joint's phase, by index; made once, at start.
    phases: Vec<Phase>,
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

impl Enabler {
    pub(crate) fn new(roster: &Roster) -> Self {
        Self {
            run: None,
            phases: (0..roster.len()).map(|_| Phase::Off).collect(),
        }
    }

    /// Take a new enable at `now_ns`: refused at once if another runs, it names nothing, a joint is already enabled or
    /// its skeleton entry can't pass preflight; otherwise every named joint's preflight starts.
    pub(crate) fn take(
        &mut self,
        roster: &Roster,
        enable: Enable,
        slow: &mut [SlowEnds],
        now_ns: u64,
    ) -> Option<EnableReply> {
        let refuse = |why| {
            Some(EnableReply {
                tag: enable.tag,
                outcome: Err(why),
            })
        };
        if self.run.is_some() {
            return refuse(EnableRefused::Busy);
        }
        if enable.joints.is_empty() {
            return refuse(EnableRefused::Empty);
        }
        for joint in enable.joints.iter() {
            let Some(entry) = roster.joint(joint) else {
                return refuse(EnableRefused::Empty);
            };
            if matches!(self.phases.get(joint), Some(Phase::Enabled(_))) {
                return refuse(EnableRefused::AlreadyEnabled { joint });
            }
            if let Err(refusal) = entry.target {
                return refuse(EnableRefused::Preflight { joint, refusal });
            }
        }
        for joint in enable.joints.iter() {
            let (Some(entry), Some(phase)) = (roster.joint(joint), self.phases.get_mut(joint))
            else {
                continue;
            };
            let (Ok(target), Some((_, at_slot)), Some(ends)) = (
                entry.target,
                entry.at,
                entry.at.and_then(|(bus, _)| slow.get_mut(bus)),
            ) else {
                continue;
            };
            let first_tag = ends.next_tag;
            ends.next_tag = ends.next_tag.wrapping_add(Preflight::TAGS);
            *phase = Phase::Preflight {
                preflight: Preflight::start(target, at_slot, first_tag, now_ns),
                first_tag,
            };
        }
        self.run = Some((enable.tag, enable.joints));
        None
    }

    /// End the enable running, if any, because the run is ending.
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
    /// joint. Gives the enable's reply once it ends.
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
                while ends.results.pop().is_ok() {
                    counts.stray_results += 1;
                }
            }
            return None;
        };
        self.route_results(roster, joints, buses.slow, now_ns, counts);
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
        let (Some((bus, slot)), Some(bus_name)) = (entry.at, entry.bus.as_ref()) else {
            return Err(unwired);
        };
        if buses.ended.get(bus).copied().unwrap_or(true) {
            return Err(Failed::Ended { joint });
        }
        let seen = buses
            .snapshots
            .get(bus)
            .and_then(Option::as_ref)
            .and_then(|s| Seen::of(bus_name, s, slot));
        // A limb on several buses is one limb: a part stopped on another bus refuses the enable before its Enable, and
        // after it reaches every bus, so this joint's sequence fails on its own bus's stop.
        if let Some(stop) = halted(roster, buses.snapshots, entry.limb) {
            match phase {
                Phase::Preflight { .. } | Phase::Passed(_) | Phase::Off => {
                    return Err(Failed::Preflight {
                        joint,
                        refusal: Refusal::LimbStopped { stop },
                    });
                }
                Phase::Enabling(_) | Phase::Enabled(_) => stops.ask(Scope::Limb(entry.limb)),
            }
        }
        match phase {
            Phase::Off => Err(unwired),
            Phase::Passed(_) => Ok(Progress::Passed),
            Phase::Enabled(_) => Ok(Progress::Enabled),
            Phase::Preflight { preflight, .. } => {
                let Some(seen) = seen else {
                    return Ok(Progress::Running);
                };
                match preflight.poll(seen, now_ns) {
                    Step::Submit(request) => {
                        // A ring of a request per slot: one preflight has one in flight, so it always has room.
                        let pushed = buses
                            .slow
                            .get_mut(bus)
                            .is_some_and(|ends| ends.requests.push(request).is_ok());
                        if pushed {
                            Ok(Progress::Running)
                        } else {
                            Err(Failed::Preflight {
                                joint,
                                refusal: Refusal::NoStatus,
                            })
                        }
                    }
                    Step::Wait => Ok(Progress::Running),
                    Step::Passed(proof) => {
                        *phase = Phase::Passed(proof);
                        Ok(Progress::Passed)
                    }
                    Step::Refused(refusal) => Err(Failed::Preflight { joint, refusal }),
                    // Only a preflight that already passed says so: never one still running here.
                    Step::Spent => Err(Failed::Preflight {
                        joint,
                        refusal: Refusal::NoStatus,
                    }),
                }
            }
            Phase::Enabling(enabling) => {
                let Some(seen) = seen else {
                    return Ok(Progress::Running);
                };
                match enabling.step(seen, next, now_ns) {
                    Next::Send(frame) => {
                        // The plan keeps every slot in range; a frame that can't go stops its limb, and the sequence
                        // then fails on the stop.
                        if !buses
                            .batches
                            .get_mut(bus)
                            .is_some_and(|b| b.set(slot, frame))
                        {
                            stops.ask(Scope::Limb(entry.limb));
                        }
                        Ok(Progress::Running)
                    }
                    Next::Wait => Ok(Progress::Running),
                    Next::Enabled => {
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
                        .and_then(|e| e.at)
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
        let stop = joints.iter().any(|j| match self.phases.get(j) {
            Some(Phase::Enabling(e)) => e.enable_planned(),
            Some(Phase::Enabled(_)) => true,
            _ => false,
        });
        for joint in joints.iter() {
            if let Some(phase) = self.phases.get_mut(joint) {
                *phase = Phase::Off;
            }
            if stop && let Some(entry) = roster.joint(joint) {
                stops.ask(Scope::Limb(entry.limb));
            }
        }
        self.run = None;
        let why = match failure {
            Failed::Preflight { joint, refusal } => EnableRefused::Preflight { joint, refusal },
            Failed::Sequence { joint, failure } => EnableRefused::Sequence {
                joint,
                failure,
                stopped: stop,
            },
            Failed::Ended { joint } => EnableRefused::BusEnded { joint },
        };
        EnableReply {
            tag,
            outcome: Err(why),
        }
    }

    /// Hold every enabled joint whose limb still takes commands; drop the rest. A drive of a held limb that this host
    /// never enabled, seen out of Reset, stops the limb (`host.mode`: something else put it in Run, PLAN item 6).
    fn hold(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        counts: &mut Counts,
    ) {
        let running = self.run.map(|(_, joints)| joints).unwrap_or_default();
        for joint in 0..self.phases.len() {
            let Some(Phase::Enabled(drive)) = self.phases.get(joint) else {
                continue;
            };
            let drive = *drive;
            let (Some(entry), Some(phase)) = (roster.joint(joint), self.phases.get_mut(joint))
            else {
                continue;
            };
            let Some((bus, slot)) = entry.at else {
                continue;
            };
            let snapshot = buses.snapshots.get(bus).and_then(Option::as_ref);
            let limb = snapshot
                .and_then(|s| s.drive(slot))
                .and_then(|v| snapshot.and_then(|s| s.limb(v.limb)));
            // An Enable makes its limb Active; a limb seen any other way was stopped (or stopped and cleared) since. A part
            // of it stopped on another bus stops it everywhere: the bus that stopped it reaches only its own part.
            let elsewhere = halted(roster, buses.snapshots, entry.limb).is_some();
            if elsewhere {
                stops.ask(Scope::Limb(entry.limb));
            }
            let takes = !elsewhere && limb.is_some_and(|l| l.state == LimbState::Active);
            if running.contains(joint) && takes {
                // Still in the enable running: the sequence owns its slot until the enable is answered.
                continue;
            }
            if !takes {
                *phase = Phase::Off;
                counts.holds_ended += 1;
                continue;
            }
            match encode::mit(drive, &slack()) {
                Ok(frame)
                    if buses
                        .batches
                        .get_mut(bus)
                        .is_some_and(|b| b.set(slot, frame)) => {}
                // The plan keeps every slot in range; a hold that can't go stops its limb.
                // A model without MIT scales never passes preflight; stop rather than hold blind.
                Ok(_) | Err(_) => stops.ask(Scope::Limb(entry.limb)),
            }
            if mate_left_reset(roster, &self.phases, snapshot, bus, entry.limb) {
                counts.mode_stops += 1;
                stops.ask(Scope::Limb(entry.limb));
            }
        }
    }
}

/// Why `limb` is stopping or stopped on some bus, if it is on any: the newest snapshot of every bus it is on.
#[expect(
    clippy::option_option,
    reason = "outer: whether some part is stopped; inner: whether its snapshot still says why"
)]
fn halted(
    roster: &Roster,
    snapshots: &[Option<Snapshot>],
    limb: LimbName,
) -> Option<Option<StopReason>> {
    (0..roster.len())
        .filter_map(|j| roster.joint(j))
        .filter(|e| e.limb == limb)
        .filter_map(|e| {
            let (bus, slot) = e.at?;
            let snapshot = snapshots.get(bus)?.as_ref()?;
            snapshot.limb(snapshot.drive(slot)?.limb)
        })
        .find(|l| !l.state.takes_commands())
        .map(|l| l.stop)
}

/// Whether a drive of `limb` on `bus` that this host hasn't enabled was seen out of Reset.
fn mate_left_reset(
    roster: &Roster,
    phases: &[Phase],
    snapshot: Option<&Snapshot>,
    bus: usize,
    limb: LimbName,
) -> bool {
    let Some(snapshot) = snapshot else {
        return false;
    };
    roster.on(bus, limb).any(|mate| {
        !matches!(
            phases.get(mate),
            Some(Phase::Enabled(_) | Phase::Enabling(_))
        ) && roster
            .joint(mate)
            .and_then(|e| e.at)
            .and_then(|(_, slot)| snapshot.drive(slot))
            .is_some_and(|v| v.out_of_reset.is_some())
    })
}

/// Where one joint of the enable running is, after its step.
#[derive(Clone, Copy, Debug)]
enum Progress {
    /// Its preflight or its sequence is still running.
    Running,
    /// Its preflight passed; its sequence waits for every other joint's proof.
    Passed,
    /// It is enabled.
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
}

/// The hold every enabled drive gets until real control modes and their gains exist: zero gains and zero torque, so the
/// drive is in Run and watched by every rule but holds nothing.
#[expect(
    clippy::unwrap_used,
    reason = "zero is in range for every unit type; checked by the test below"
)]
fn slack() -> MitCommand {
    MitCommand {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(0.0).unwrap(),
        kd: NmSecPerRad::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    }
}

/// The batch slots a bus holds, for the ring sizes.
pub(crate) const SLOW_RING: usize = MAX_DRIVES;

#[cfg(test)]
mod tests {
    use super::*;

    fn roster() -> Roster {
        let skeleton = skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap();
        let plans = crate::plan(&skeleton).unwrap();
        Roster::new(&skeleton, &plans).unwrap()
    }

    /// Guards: safety - an enable is refused before anything is sent when it names nothing, a joint whose skeleton
    /// entry can't pass preflight (a null fact or cap, no bus), or while another enable runs; one that can pass starts a
    /// preflight per named joint, each with its own block of slow-request tags on its bus (PLAN item 6: null refuses
    /// enable; enable runs preflight first).
    #[test]
    fn an_enable_is_refused_before_anything_is_sent_unless_every_joint_can_pass() {
        let roster = roster();
        let mut enabler = Enabler::new(&roster);
        let rings: Vec<_> = (0..2)
            .map(|_| {
                let (requests, _) = rtrb::RingBuffer::new(SLOW_RING);
                let (_, results) = rtrb::RingBuffer::new(SLOW_RING);
                SlowEnds::new(requests, results)
            })
            .collect();
        let mut slow = rings;
        let set = |names: &[&str]| roster.set(names.iter().copied()).unwrap();
        let reply = |tag, why| {
            Some(EnableReply {
                tag,
                outcome: Err(why),
            })
        };
        assert_eq!(
            enabler.take(
                &roster,
                Enable {
                    tag: 1,
                    joints: JointSet::default()
                },
                &mut slow,
                0
            ),
            reply(1, EnableRefused::Empty)
        );
        // The right arm's joints have null facts and caps; the leg's joint has no bus.
        let b_one = set(&["arm_b_one"]).iter().next().unwrap();
        assert!(matches!(
            enabler.take(&roster, Enable { tag: 2, joints: set(&["arm_a_one", "arm_b_one"]) }, &mut slow, 0),
            Some(EnableReply { tag: 2, outcome: Err(EnableRefused::Preflight { joint, .. }) }) if joint == b_one
        ));
        let leg = set(&["leg_a_one"]).iter().next().unwrap();
        assert_eq!(
            enabler.take(
                &roster,
                Enable {
                    tag: 3,
                    joints: set(&["leg_a_one"])
                },
                &mut slow,
                0
            ),
            reply(
                3,
                EnableRefused::Preflight {
                    joint: leg,
                    refusal: Refusal::Unwired
                }
            )
        );
        assert!(enabler.run.is_none());
        // The left arm can pass: its preflights start, on can1, with tags in separate blocks.
        assert_eq!(
            enabler.take(
                &roster,
                Enable {
                    tag: 4,
                    joints: set(&["arm_a_one", "arm_a_two"])
                },
                &mut slow,
                0
            ),
            None
        );
        let tags: Vec<u32> = set(&["arm_a_one", "arm_a_two"])
            .iter()
            .map(|j| match enabler.phases[j] {
                Phase::Preflight { first_tag, .. } => first_tag,
                Phase::Off | Phase::Passed(_) | Phase::Enabling(_) | Phase::Enabled(_) => u32::MAX,
            })
            .collect();
        assert_eq!(tags, [0, Preflight::TAGS]);
        assert_eq!(slow[1].next_tag, 2 * Preflight::TAGS);
        assert_eq!(
            enabler.take(
                &roster,
                Enable {
                    tag: 5,
                    joints: set(&["waist_one"])
                },
                &mut slow,
                0
            ),
            reply(5, EnableRefused::Busy)
        );
        // The run ends: the enable running is answered, and nothing is left running.
        assert_eq!(enabler.end(), reply(4, EnableRefused::Ending));
        assert!(enabler.phases.iter().all(|p| matches!(p, Phase::Off)));
    }

    /// Guards: safety - the hold every enabled drive gets is zero gains and zero torque, encodable for a model with
    /// settled MIT scales: in Run but commanding nothing, until real modes and gains exist.
    #[test]
    fn the_hold_commands_nothing() {
        let command = slack();
        assert_eq!(command.kp.get(), 0.0);
        assert_eq!(command.kd.get(), 0.0);
        assert_eq!(command.torque.get(), 0.0);
        let drive = Drive::new(
            robstride::DeviceId::new(11).unwrap(),
            robstride::Model::Rs03,
        );
        assert!(encode::mit(drive, &command).is_ok());
    }
}
