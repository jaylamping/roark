//! (rt) Control's events, handed to the recorder through its event ring (safety.md section 8: every stop, enable,
//! refused enable and clear is an event, never logged from the realtime thread). Pure over the ring, so it is tested
//! on any OS where the recorder builds; the control thread (Linux) is its only user outside the tests.

use safety::{Cause, RuleId};
use skeleton::LimbName;
use telemetry::{Event, EventKind, EventRecorder, Level};

use crate::dispatch::Stops;
use crate::enable::{Enable, EnableRefused, EnableReply};
use crate::request::{ClearRefused, Reply, Scope};
use crate::roster::Roster;

/// Control's end of the event ring, the limb of each joint (by roster index), and the time of the pass its events are
/// stamped with.
pub(crate) struct Events {
    recorder: Option<EventRecorder>,
    limbs: Vec<LimbName>,
    now_ns: u64,
}

impl Events {
    /// Events into `recorder`, naming the limbs of `roster`'s joints; none recorded without one.
    pub(crate) fn new(recorder: Option<EventRecorder>, roster: &Roster) -> Self {
        Self {
            recorder,
            limbs: (0..roster.len())
                .filter_map(|j| roster.joint(j).map(|e| e.limb))
                .collect(),
            now_ns: 0,
        }
    }

    /// Stamp the events that follow with `now_ns`, on the session's monotonic clock.
    pub(crate) const fn at(&mut self, now_ns: u64) {
        self.now_ns = now_ns;
    }

    /// The stops taken from the latch: one event per scope and cause, a limb's kept even when the robot's stop covers
    /// it.
    pub(crate) fn stops(&mut self, stops: Stops) {
        for (scope, causes) in stops.asked() {
            for cause in causes.iter() {
                self.stop(scope, cause);
            }
        }
    }

    /// A stop of `scope`, for `cause`.
    pub(crate) fn stop(&mut self, scope: Scope, cause: Cause) {
        let (rule, reason) = match cause {
            Cause::Rule(rule) => (Some(rule.as_str()), None),
            Cause::Operator => (None, Some("operator")),
            Cause::Shutdown => (None, Some("shutdown")),
            Cause::Follows => (None, Some("follows_bus_stop")),
        };
        let (kind, limb) = match scope {
            Scope::Robot => (EventKind::RobotStopped, None),
            Scope::Limb(limb) => (EventKind::LimbStopped, Some(limb.as_str())),
        };
        self.record(Event {
            limb,
            rule,
            reason,
            ..self.event(Level::Error, kind)
        });
    }

    /// An enable that passed its checks and started: one event per joint it names.
    pub(crate) fn started(&mut self, enable: &Enable) {
        for joint in enable.joints.iter() {
            self.record(Event {
                joint: Some(joint),
                limb: self.limb(joint),
                tag: Some(enable.tag),
                ..self.event(Level::Info, EventKind::EnableStarted)
            });
        }
    }

    /// An enable's answer: every joint enabled, or refused, under its rule where one refused it.
    pub(crate) fn enable_reply(&mut self, reply: &EnableReply) {
        let event = match reply.outcome {
            Ok(()) => self.event(Level::Info, EventKind::EnableSucceeded),
            Err(why) => self.refused(why),
        };
        self.record(Event {
            tag: Some(reply.tag),
            ..event
        });
    }

    /// A refused enable with every field its refusal carries: the joint and its limb, the limb, the bus, the rule
    /// (none for a request that was wrong or came at the wrong time, which no rule refused) and a word for it.
    fn refused(&self, why: EnableRefused) -> Event {
        let base = self.event(Level::Error, EventKind::EnableRefused);
        let of_joint = |joint, rule: Option<RuleId>, reason| Event {
            joint: Some(joint),
            limb: self.limb(joint),
            rule: rule.map(RuleId::as_str),
            reason: Some(reason),
            ..base
        };
        let alone = |rule: Option<RuleId>, reason| Event {
            rule: rule.map(RuleId::as_str),
            reason: Some(reason),
            ..base
        };
        match why {
            EnableRefused::Empty => alone(None, "empty"),
            EnableRefused::Busy => alone(None, "busy"),
            EnableRefused::Ending => alone(None, "ending"),
            EnableRefused::Logging => alone(Some(RuleId::HostLogging), "logging"),
            EnableRefused::UnknownJoint { joint } => Event {
                joint: Some(joint),
                ..alone(None, "unknown_joint")
            },
            EnableRefused::AlreadyEnabled { joint } => of_joint(joint, None, "already_enabled"),
            EnableRefused::Preflight { joint, refusal } => {
                of_joint(joint, Some(refusal.rule()), "preflight")
            }
            EnableRefused::Sequence { joint, failure, .. } => {
                of_joint(joint, Some(failure.rule()), "sequence")
            }
            EnableRefused::BusEnded { joint, .. } => {
                of_joint(joint, Some(RuleId::HostBus), "bus_ended")
            }
            // Preflight's no-status clause: a drive the bus shows nothing of can't be proved.
            EnableRefused::Unseen { joint, .. } => {
                of_joint(joint, Some(RuleId::HostPreflight), "unseen")
            }
            // Another host's writes may have changed what preflight proved.
            EnableRefused::ForeignHost { bus, .. } => Event {
                bus: Some(bus),
                ..alone(Some(RuleId::HostPreflight), "foreign_host")
            },
            EnableRefused::LimbMate { limb, .. } => Event {
                limb: Some(limb.as_str()),
                ..alone(Some(RuleId::HostMode), "limb_mate")
            },
        }
    }

    /// A clear's answer from one bus, or its refusal.
    pub(crate) fn clear_reply(&mut self, reply: &Reply) {
        let event = match reply.outcome {
            Ok(()) => self.event(Level::Info, EventKind::LimbCleared),
            Err(why) => Event {
                reason: Some(match why {
                    ClearRefused::Bus(_) => "bus_refused",
                    ClearRefused::Offline => "offline",
                    ClearRefused::Busy => "busy",
                    ClearRefused::BusEnded => "bus_ended",
                    ClearRefused::Ending => "ending",
                }),
                ..self.event(Level::Error, EventKind::ClearRefused)
            },
        };
        self.record(Event {
            limb: Some(reply.limb.as_str()),
            bus: reply.bus,
            tag: Some(reply.tag),
            ..event
        });
    }

    /// `joint`'s limb's name.
    fn limb(&self, joint: usize) -> Option<&'static str> {
        self.limbs.get(joint).map(|l| l.as_str())
    }

    const fn event(&self, level: Level, kind: EventKind) -> Event {
        Event {
            mono_ns: self.now_ns,
            level,
            kind,
            limb: None,
            joint: None,
            bus: None,
            rule: None,
            reason: None,
            tag: None,
        }
    }

    fn record(&mut self, event: Event) {
        if let Some(recorder) = &mut self.recorder {
            // A full ring drops the event; the recorder counts it in the file's end marker.
            let _ = recorder.record(event);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use safety::Refusal;

    /// Guards: safety - a refused enable's event carries every field its refusal names: a joint with its limb, a limb
    /// alone, a bus, and the rule that refused it, none for a request no rule refused (safety.md section 8: every
    /// verdict other than `Allow` is an event with its joint and limb).
    #[test]
    fn a_refused_enable_names_its_joint_limb_bus_and_rule() {
        let skeleton = skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap();
        let plans = crate::plan(&skeleton).unwrap();
        let roster = Roster::new(&skeleton, &plans).unwrap();
        let events = Events::new(None, &roster);
        let joint = roster.set(["leg_a_one"]).unwrap().iter().next().unwrap();
        let brief = |why| {
            let e = events.refused(why);
            (e.joint, e.limb, e.bus, e.rule, e.reason)
        };
        assert_eq!(
            brief(EnableRefused::Preflight {
                joint,
                refusal: Refusal::Unwired
            }),
            (
                Some(joint),
                Some("left_leg"),
                None,
                Some("host.preflight"),
                Some("preflight")
            )
        );
        assert_eq!(
            brief(EnableRefused::LimbMate {
                limb: LimbName::Waist,
                stopped: true
            }),
            (
                None,
                Some("waist"),
                None,
                Some("host.mode"),
                Some("limb_mate")
            )
        );
        assert_eq!(
            brief(EnableRefused::ForeignHost {
                bus: 1,
                stopped: false
            }),
            (
                None,
                None,
                Some(1),
                Some("host.preflight"),
                Some("foreign_host")
            )
        );
        assert_eq!(
            brief(EnableRefused::AlreadyEnabled { joint }),
            (
                Some(joint),
                Some("left_leg"),
                None,
                None,
                Some("already_enabled")
            )
        );
    }
}
