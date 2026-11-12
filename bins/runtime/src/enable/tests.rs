//! The enabler over hand-built snapshots: what it sends, holds, stops and answers, pass by pass.

use can::{
    BusDrive, Counters, DriveView, LimbState, LimbView, MAX_DRIVES, ModeSeen, StopOutcome,
    StopReason,
};
use robstride::{DeviceId, Mode, Model, encode};
use rtrb::RingBuffer;
use skeleton::LimbName;

use super::hold::slack;
use super::*;
use crate::plan::BusPlan;

struct Rig {
    roster: Roster,
    plans: Vec<BusPlan>,
    slow: Vec<SlowEnds>,
    snapshots: Vec<Option<Snapshot>>,
    batches: Vec<CommandBatch>,
    ended: Vec<bool>,
    stops: StopLatch,
    counts: Counts,
}

impl Rig {
    fn new() -> Self {
        let skeleton = skeleton::parse(include_str!("../../tests/skeleton.yaml")).unwrap();
        let plans = crate::plan(&skeleton).unwrap();
        let roster = Roster::new(&skeleton, &plans).unwrap();
        let slow = plans
            .iter()
            .map(|_| {
                let (requests, _) = RingBuffer::new(SLOW_RING);
                let (_, results) = RingBuffer::new(SLOW_RING);
                SlowEnds::new(requests, results)
            })
            .collect();
        let mut rig = Self {
            roster,
            slow,
            snapshots: vec![None; plans.len()],
            batches: vec![CommandBatch::new(1, u64::MAX); plans.len()],
            ended: vec![false; plans.len()],
            stops: StopLatch::default(),
            counts: Counts::default(),
            plans,
        };
        for bus in 0..rig.plans.len() {
            rig.show(bus, &[], &[], 0);
        }
        rig
    }

    fn joint(&self, name: &str) -> usize {
        self.roster.set([name]).unwrap().iter().next().unwrap()
    }

    /// Bus `bus`'s snapshot: every limb idle but those in `limbs`; every drive in Reset but those in `out`, by joint
    /// name, seen out of Reset; `foreign` other hosts' frames.
    fn show(&mut self, bus: usize, limbs: &[(LimbName, LimbState)], out: &[&str], foreign: u64) {
        let plan = &self.plans[bus];
        let mut limb_views = [None; MAX_DRIVES];
        for (i, name) in plan.limbs.iter().enumerate() {
            let state = limbs
                .iter()
                .find(|(l, _)| l == name)
                .map_or(LimbState::Idle, |(_, s)| *s);
            let stop = (!state.takes_commands()).then_some(StopReason::LimbRequested);
            limb_views[i] = Some(LimbView {
                state,
                stop,
                generation: 0,
            });
        }
        let mut drives = [None; MAX_DRIVES];
        for (slot, (BusDrive { device, limb }, name)) in
            plan.drives.iter().zip(&plan.joints).enumerate()
        {
            drives[slot] = Some(DriveView {
                device: *device,
                limb: *limb,
                observed: None,
                mode: None,
                out_of_reset: out.contains(&name.as_str()).then_some(ModeSeen {
                    mode: Mode::Run,
                    read_ns: 1,
                }),
                fresh_ns: None,
                fresh_status: None,
                answered: false,
                fault_seen: false,
                misses: 0,
                last_echo: None,
                stop: StopOutcome::None,
                reporting_off_sent: false,
            });
        }
        let counters = Counters {
            foreign_host: foreign,
            ..Counters::default()
        };
        self.snapshots[bus] = Some(Snapshot::from_parts(1, None, counters, limb_views, drives));
    }

    fn buses(&mut self) -> Buses<'_> {
        Buses {
            snapshots: &self.snapshots,
            slow: &mut self.slow,
            batches: &mut self.batches,
            ended: &self.ended,
        }
    }

    fn take(&mut self, enabler: &mut Enabler, tag: u64, names: &[&str]) -> Option<EnableReply> {
        let joints = self.roster.set(names.iter().copied()).unwrap();
        let roster = self.roster.clone();
        enabler.take(&roster, Enable { tag, joints }, &mut self.buses(), false, 0)
    }

    fn tick(&mut self, enabler: &mut Enabler) -> Option<EnableReply> {
        self.tick_at(enabler, 0)
    }

    fn tick_at(&mut self, enabler: &mut Enabler, now_ns: u64) -> Option<EnableReply> {
        for b in &mut self.batches {
            *b = CommandBatch::new(1, u64::MAX);
        }
        let roster = self.roster.clone();
        let stops = core::mem::take(&mut self.stops);
        let mut counts = self.counts;
        let reply = enabler.tick(&roster, &mut self.buses(), &stops, 1, now_ns, &mut counts);
        self.counts = counts;
        self.stops = stops;
        reply
    }

    /// The limbs asked to stop since the last call, each with its cause.
    fn stopped(&self) -> Vec<(Scope, Option<Why>)> {
        self.stops.take().scopes().collect()
    }

    /// Bus `bus`'s batch with a slack hold for each joint named.
    fn held(&self, bus: usize, names: &[&str]) -> CommandBatch {
        let mut batch = CommandBatch::new(1, u64::MAX);
        for name in names {
            let entry = self.roster.joint(self.joint(name)).unwrap();
            let (b, slot) = entry.slot().unwrap();
            assert_eq!(b, bus);
            let drive = Drive::new(self.plans[b].drives[slot].device, Model::Rs03);
            assert!(batch.set(slot, encode::mit(drive, &slack()).unwrap()));
        }
        batch
    }
}

/// The left arm's two joints as if their sequences had finished, with the arm Active on can1.
fn enabled(rig: &mut Rig, enabler: &mut Enabler, names: &[&str]) {
    for name in names {
        let j = rig.joint(name);
        let (bus, slot) = rig.roster.joint(j).unwrap().slot().unwrap();
        enabler.phases[j] =
            Phase::Enabled(Drive::new(rig.plans[bus].drives[slot].device, Model::Rs03));
    }
}

/// Guards: safety - an enable is refused before anything is sent when it names nothing or an index the roster doesn't
/// have, a joint with no bus, a joint already enabled or of a limb held on another bus, while the recording has failed
/// (`host.logging`), or while another enable runs; one that can pass starts a preflight per named joint, each with its
/// own block of slow-request tags on its bus (PLAN item 6: enable runs preflight first).
#[test]
fn an_enable_is_refused_before_anything_is_sent_unless_every_joint_can_pass() {
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    let refused = |tag, why| {
        Some(EnableReply {
            tag,
            outcome: Err(why),
        })
    };
    assert_eq!(
        rig.take(&mut enabler, 1, &[]),
        refused(1, EnableRefused::Empty)
    );
    let mut beyond = JointSet::default();
    beyond.insert(rig.roster.len());
    let roster = rig.roster.clone();
    assert_eq!(
        enabler.take(
            &roster,
            Enable {
                tag: 2,
                joints: beyond
            },
            &mut rig.buses(),
            false,
            0
        ),
        refused(
            2,
            EnableRefused::UnknownJoint {
                joint: rig.roster.len()
            }
        )
    );
    // The leg's joint has no bus.
    let leg = rig.joint("leg_a_one");
    assert_eq!(
        rig.take(&mut enabler, 4, &["leg_a_one"]),
        refused(
            4,
            EnableRefused::Preflight {
                joint: leg,
                refusal: Refusal::Unwired
            }
        )
    );
    let joints = rig.roster.set(["arm_a_one"]).unwrap();
    assert_eq!(
        enabler.take(
            &roster,
            Enable { tag: 5, joints },
            &mut rig.buses(),
            true,
            0
        ),
        refused(5, EnableRefused::Logging)
    );
    enabled(&mut rig, &mut enabler, &["arm_a_two"]);
    let a_two = rig.joint("arm_a_two");
    assert_eq!(
        rig.take(&mut enabler, 6, &["arm_a_one", "arm_a_two"]),
        refused(6, EnableRefused::AlreadyEnabled { joint: a_two })
    );
    enabler.phases[a_two] = Phase::Off;
    // The right arm held on can0: a joint of it on can1, where its part is idle, is refused as preflight would refuse
    // it on can0.
    enabled(&mut rig, &mut enabler, &["arm_b_one"]);
    let b_three = rig.joint("arm_b_three");
    assert_eq!(
        rig.take(&mut enabler, 6, &["arm_b_three"]),
        refused(
            6,
            EnableRefused::Preflight {
                joint: b_three,
                refusal: Refusal::LimbActive
            }
        )
    );
    enabler.phases[rig.joint("arm_b_one")] = Phase::Off;
    assert!(enabler.run.is_none());
    assert!(rig.slow.iter().all(|s| s.next_tag == 0));
    // The left arm can pass: its preflights start, on can1, with tags in separate blocks.
    assert_eq!(rig.take(&mut enabler, 7, &["arm_a_one", "arm_a_two"]), None);
    let tags: Vec<u32> = ["arm_a_one", "arm_a_two"]
        .iter()
        .map(|name| match enabler.phases[rig.joint(name)] {
            Phase::Preflight { first_tag, .. } => first_tag,
            Phase::Off | Phase::Passed(_) | Phase::Enabling(_) | Phase::Enabled(_) => u32::MAX,
        })
        .collect();
    assert_eq!(tags, [0, Preflight::TAGS]);
    assert_eq!(rig.slow[1].next_tag, 2 * Preflight::TAGS);
    assert_eq!(
        rig.take(&mut enabler, 8, &["waist_one"]),
        refused(8, EnableRefused::Busy)
    );
    // The run ends: the enable running is answered, and nothing is left running.
    assert_eq!(enabler.end(), refused(7, EnableRefused::Ending));
    assert!(enabler.phases.iter().all(|p| matches!(p, Phase::Off)));
}

/// Guards: safety - a joint is held from the tick its own drive is enabled, while its enable still waits on a mate,
/// so a drive in Run is never left uncommanded until the slowest mate's Run (PLAN item 2: 1.4 to 10.3 ms to Run; item 3:
/// feedback older than three periods stops the limb); the enable is answered once every joint is held.
#[test]
fn a_joint_is_held_from_its_own_run_while_its_enable_waits_for_a_mate() {
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    assert_eq!(rig.take(&mut enabler, 9, &["arm_a_one", "arm_a_two"]), None);
    rig.show(1, &[(LimbName::LeftArm, LimbState::Active)], &[], 0);
    // arm_a_one's drive is in Run while arm_a_two's isn't yet: arm_a_one is held. (The hold alone: the mate's own
    // step needs a passed preflight, which only a drive gives; the sim suite runs the whole enable.)
    enabled(&mut rig, &mut enabler, &["arm_a_one"]);
    let roster = rig.roster.clone();
    let stops = StopLatch::default();
    let mut counts = Counts::default();
    enabler.hold(&roster, &mut rig.buses(), &stops, &mut counts);
    assert_eq!(rig.batches[1], rig.held(1, &["arm_a_one"]));
    assert_eq!(counts, Counts::default());
    // Once it is enabled too, both are held and the enable is answered.
    enabled(&mut rig, &mut enabler, &["arm_a_two"]);
    assert_eq!(
        rig.tick(&mut enabler),
        Some(EnableReply {
            tag: 9,
            outcome: Ok(())
        })
    );
    assert_eq!(rig.batches[1], rig.held(1, &["arm_a_one", "arm_a_two"]));
    assert_eq!(rig.stopped(), []);
    assert_eq!(rig.counts, Counts::default());
}

/// Guards: safety - host.mode: a held limb over two buses stops as a whole when a drive of it this host never enabled,
/// on the other bus, is seen out of Reset, or that bus has no snapshot to show it; the stop is counted once and every
/// hold of the limb ends with it (PLAN item 6 host.mode row, #25).
#[test]
fn a_limb_mate_out_of_reset_on_another_bus_stops_the_whole_held_limb() {
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    // The right arm's first two joints are on can0 and held there; its third is on can1, never enabled.
    enabled(&mut rig, &mut enabler, &["arm_b_one", "arm_b_two"]);
    rig.show(0, &[(LimbName::RightArm, LimbState::Active)], &[], 0);
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.batches[0], rig.held(0, &["arm_b_one", "arm_b_two"]));
    assert_eq!(rig.stopped(), []);
    // Something else puts it in Run: the whole arm stops, once.
    rig.show(1, &[], &["arm_b_three"], 0);
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.batches[0], CommandBatch::new(1, u64::MAX));
    assert_eq!(
        rig.stopped(),
        [(
            Scope::Limb(LimbName::RightArm),
            Some(Why::Rule(RuleId::HostMode))
        )]
    );
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.stopped(), []);
    assert_eq!(
        rig.counts,
        Counts {
            stray_results: 0,
            mode_stops: 1,
            holds_ended: 2
        }
    );
    // A bus with nothing to show for the mate fails closed.
    enabled(&mut rig, &mut enabler, &["arm_b_one"]);
    rig.snapshots[1] = None;
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(
        rig.stopped(),
        [(
            Scope::Limb(LimbName::RightArm),
            Some(Why::Rule(RuleId::HostMode))
        )]
    );
}

/// Guards: safety - a held limb over two buses stopped on either bus stops on every bus: its holds end and a stop of
/// the whole limb is asked, since the bus that stopped it reaches only its own part, whether the held joints are on the
/// bus that stopped or on the other (PLAN item 6 host.fault: a fault stops the whole limb).
#[test]
fn a_held_limb_stopped_on_one_bus_is_stopped_on_every_bus() {
    // Held on can0, stopped on can1.
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    enabled(&mut rig, &mut enabler, &["arm_b_one", "arm_b_two"]);
    rig.show(0, &[(LimbName::RightArm, LimbState::Active)], &[], 0);
    rig.show(1, &[(LimbName::RightArm, LimbState::Stopped)], &[], 0);
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.batches[0], CommandBatch::new(1, u64::MAX));
    assert_eq!(
        rig.stopped(),
        [(Scope::Limb(LimbName::RightArm), Some(Why::Elsewhere))]
    );
    assert_eq!(rig.counts.holds_ended, 2);
    // Held on can0, stopped there (a fault, say): the part on can1, idle, is stopped too.
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    enabled(&mut rig, &mut enabler, &["arm_b_one", "arm_b_two"]);
    rig.show(
        0,
        &[(LimbName::RightArm, LimbState::Stopping { since_ns: 1 })],
        &[],
        0,
    );
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.batches[0], CommandBatch::new(1, u64::MAX));
    assert_eq!(
        rig.stopped(),
        [(Scope::Limb(LimbName::RightArm), Some(Why::Elsewhere))]
    );
    assert_eq!(rig.counts.holds_ended, 2);
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.stopped(), []);
    // Held, then stopped and cleared on its own bus between two passes: Idle, not Active, so no longer held, and
    // nothing to stop.
    enabled(&mut rig, &mut enabler, &["arm_a_one"]);
    rig.show(1, &[], &[], 0);
    assert_eq!(rig.tick(&mut enabler), None);
    assert_eq!(rig.batches[1], CommandBatch::new(1, u64::MAX));
    assert_eq!(rig.stopped(), []);
    assert_eq!(rig.counts.holds_ended, 3);
}

/// Guards: safety - an enable whose limb stops once a joint of it is enabled fails with every named limb stopped, never
/// answered Ok; one whose limb stops before any Enable, whose bus thread ends, or on whose bus another host sends, is
/// refused and stops nothing until an Enable may have gone, then stops every named limb (PLAN item 6: a failure after
/// an Enable stops the limb; item 3: only the realtime process transmits).
#[test]
fn an_enable_that_fails_stops_its_limbs_once_an_enable_may_have_gone() {
    let stopped_limb = |enable_planned| EnableFailure::LimbStopped {
        stop: Some(StopReason::LimbRequested),
        enable_planned,
    };
    let both = ["arm_a_one", "arm_a_two"];
    let a_one_of = |rig: &Rig| rig.joint("arm_a_one");

    // Enabled, then the limb stops before the mate is: Sequence, stopped.
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    assert_eq!(rig.take(&mut enabler, 1, &both), None);
    enabled(&mut rig, &mut enabler, &["arm_a_one"]);
    rig.show(1, &[(LimbName::LeftArm, LimbState::Stopped)], &[], 0);
    let joint = a_one_of(&rig);
    assert_eq!(
        rig.tick(&mut enabler),
        Some(EnableReply {
            tag: 1,
            outcome: Err(EnableRefused::Sequence {
                joint,
                failure: stopped_limb(true),
                stopped: true
            })
        })
    );
    assert_eq!(
        rig.stopped(),
        [(
            Scope::Limb(LimbName::LeftArm),
            Some(Why::Rule(RuleId::HostPreflight))
        )]
    );
    assert!(enabler.phases.iter().all(|p| matches!(p, Phase::Off)));

    // The limb stops while the preflights run: refused, nothing to stop.
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    assert_eq!(rig.take(&mut enabler, 2, &both), None);
    rig.show(1, &[(LimbName::LeftArm, LimbState::Stopped)], &[], 0);
    assert_eq!(
        rig.tick(&mut enabler),
        Some(EnableReply {
            tag: 2,
            outcome: Err(EnableRefused::Preflight {
                joint: a_one_of(&rig),
                refusal: Refusal::LimbStopped {
                    stop: Some(StopReason::LimbRequested)
                }
            })
        })
    );
    assert_eq!(rig.stopped(), []);

    // The bus thread ends: refused, nothing to stop; or, with a joint enabled, every named limb stopped.
    for (enabled_first, stopped) in [(false, false), (true, true)] {
        let mut rig = Rig::new();
        let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
        assert_eq!(rig.take(&mut enabler, 3, &both), None);
        if enabled_first {
            enabled(&mut rig, &mut enabler, &["arm_a_one"]);
            rig.show(1, &[(LimbName::LeftArm, LimbState::Active)], &[], 0);
        }
        rig.ended[1] = true;
        assert_eq!(
            rig.tick(&mut enabler),
            Some(EnableReply {
                tag: 3,
                outcome: Err(EnableRefused::BusEnded {
                    joint: a_one_of(&rig),
                    stopped
                })
            })
        );
        let expected: &[(Scope, Option<Why>)] = if stopped {
            &[(
                Scope::Limb(LimbName::LeftArm),
                Some(Why::Rule(RuleId::HostBus)),
            )]
        } else {
            &[]
        };
        assert_eq!(rig.stopped(), expected);
    }

    // Another host sends on can1 while the preflights run: refused.
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    rig.show(1, &[], &[], 4);
    assert_eq!(rig.take(&mut enabler, 4, &both), None);
    assert_eq!(rig.tick(&mut enabler), None);
    rig.show(1, &[], &[], 5);
    assert_eq!(
        rig.tick(&mut enabler),
        Some(EnableReply {
            tag: 4,
            outcome: Err(EnableRefused::ForeignHost {
                bus: 1,
                stopped: false
            })
        })
    );
    assert_eq!(rig.stopped(), []);
}

/// Guards: safety - host.mode - an enable whose joints are enabled while a limb-mate this host didn't enable leaves
/// Reset on another bus fails under host.mode with every named limb stopped, never answered Ok.
#[test]
fn an_enable_whose_limb_mate_leaves_reset_fails_with_its_limb_stopped() {
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    let right = rig.roster.set(["arm_b_one", "arm_b_two"]).unwrap();
    enabler.run = Some((5, right));
    enabled(&mut rig, &mut enabler, &["arm_b_one", "arm_b_two"]);
    rig.show(0, &[(LimbName::RightArm, LimbState::Active)], &[], 0);
    rig.show(1, &[], &["arm_b_three"], 0);
    assert_eq!(
        rig.tick(&mut enabler),
        Some(EnableReply {
            tag: 5,
            outcome: Err(EnableRefused::LimbMate {
                limb: LimbName::RightArm,
                stopped: true
            })
        })
    );
    assert_eq!(
        rig.stopped(),
        [(
            Scope::Limb(LimbName::RightArm),
            Some(Why::Rule(RuleId::HostMode))
        )]
    );
    assert_eq!(
        rig.counts,
        Counts {
            stray_results: 0,
            mode_stops: 1,
            holds_ended: 2
        }
    );
}

/// Guards: safety - an enable naming a joint its bus's snapshot never shows is refused once preflight's answer window
/// has passed, rather than running, and refusing every later enable as busy, for as long as the bus stays silent
/// (rust.md: put a limit on everything).
#[test]
fn an_enable_waits_for_an_unseen_joint_only_as_long_as_an_answer() {
    let mut rig = Rig::new();
    let mut enabler = Enabler::new(&rig.roster, rig.plans.len());
    rig.snapshots[1] = None;
    assert_eq!(rig.take(&mut enabler, 1, &["arm_a_one"]), None);
    assert_eq!(rig.tick_at(&mut enabler, ANSWER_WITHIN_NS), None);
    assert_eq!(
        rig.tick_at(&mut enabler, ANSWER_WITHIN_NS + 1),
        Some(EnableReply {
            tag: 1,
            outcome: Err(EnableRefused::Unseen {
                joint: rig.joint("arm_a_one"),
                stopped: false
            })
        })
    );
    assert_eq!(rig.stopped(), []);
    assert!(enabler.run.is_none());
}

/// Guards: safety - the hold every enabled drive gets is zero gains and zero torque, encodable for a model with
/// settled MIT scales: in Run but commanding nothing, until real modes and gains exist (Joey, 2026-11-11).
#[test]
fn the_hold_commands_nothing() {
    let command = slack();
    assert_eq!(command.kp.get(), 0.0);
    assert_eq!(command.kd.get(), 0.0);
    assert_eq!(command.torque.get(), 0.0);
    assert_eq!(command.velocity.get(), 0.0);
    let drive = Drive::new(DeviceId::new(11).unwrap(), Model::Rs03);
    assert!(encode::mit(drive, &command).is_ok());
}
