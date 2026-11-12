//! (rt) Control's events, handed to the recorder through its event ring (safety.md section 8: every stop, enable,
//! refused enable and clear is an event, never logged from the realtime thread). Built on Linux only, as the recorder
//! is; the control thread is its only user.

use safety::{Cause, RuleId};
use skeleton::LimbName;
use telemetry::{Event, EventKind, EventRecorder, Level};

use crate::enable::{Enable, EnableRefused, EnableReply};
use crate::latch::Stops;
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
            if causes.unknown() {
                self.record(Event {
                    limb: limb(scope),
                    reason: Some("unknown_cause"),
                    ..self.event(Level::Error, kind(scope))
                });
            }
        }
    }

    /// A stop of `scope`, for `cause`.
    fn stop(&mut self, scope: Scope, cause: Cause) {
        let (rule, reason) = match cause {
            Cause::Rule(rule) => (Some(rule.as_str()), None),
            Cause::Operator => (None, Some("operator")),
            Cause::Shutdown => (None, Some("shutdown")),
            Cause::Follows => (None, Some("follows_bus_stop")),
        };
        self.record(Event {
            limb: limb(scope),
            rule,
            reason,
            ..self.event(Level::Error, kind(scope))
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

    /// A refused enable with every field its refusal names (`EnableRefused::named`), a joint's limb filled in.
    fn refused(&self, why: EnableRefused) -> Event {
        let named = why.named();
        Event {
            joint: named.joint,
            limb: named
                .limb
                .map(LimbName::as_str)
                .or_else(|| named.joint.and_then(|j| self.limb(j))),
            bus: named.bus,
            rule: named.rule.map(RuleId::as_str),
            reason: Some(named.reason),
            ..self.event(Level::Error, EventKind::EnableRefused)
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

/// The limb a stop of `scope` names: none for the robot.
const fn limb(scope: Scope) -> Option<&'static str> {
    match scope {
        Scope::Robot => None,
        Scope::Limb(limb) => Some(limb.as_str()),
    }
}

/// The kind of a stop of `scope`.
const fn kind(scope: Scope) -> EventKind {
    match scope {
        Scope::Robot => EventKind::RobotStopped,
        Scope::Limb(_) => EventKind::LimbStopped,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::enable::EnableReply;

    /// The events in the session file at `dir`.
    fn written(dir: &std::path::Path) -> Vec<telemetry::wire::Event> {
        let bytes = std::fs::read(dir.join("0000.mcap")).unwrap();
        mcap::MessageStream::new(&bytes)
            .unwrap()
            .map(Result::unwrap)
            .filter(|m| m.channel.topic == "/event")
            .map(|m| serde_json::from_slice(&m.data).unwrap())
            .collect()
    }

    /// Guards: safety - a refused enable is recorded with every field its refusal names: a limb mate's limb, another
    /// host's bus, a joint with its limb, and the rule that refused each (safety.md section 8: every verdict other than
    /// `Allow` is an event with its joint and limb).
    #[test]
    fn a_refused_enable_is_recorded_with_what_its_refusal_names() {
        let skeleton = skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap();
        let plans = crate::plan(&skeleton).unwrap();
        let roster = Roster::new(&skeleton, &plans).unwrap();
        let root = std::env::temp_dir().join(format!("runtime-events-{}", std::process::id()));
        let info = telemetry::SessionInfo {
            git_revision: "test".to_owned(),
            operator: "test".to_owned(),
            stage: telemetry::Stage::Vcan,
            skeleton: telemetry::SkeletonRef {
                path: "skeleton.yaml".to_owned(),
                sha256: "00".repeat(32),
            },
            buses: plans
                .iter()
                .map(|p| can::bus_info(&p.name, p.bitrate_bps))
                .collect(),
        };
        let session = telemetry::Session::start(&root, info, 1).unwrap();
        let dir = session.dir().to_path_buf();
        let (mut recording, buses) = telemetry::Recording::new(session, 4);
        let mut events = Events::new(Some(recording.events(roster.names(), 16)), &roster);
        let leg = roster.set(["leg_a_one"]).unwrap().iter().next().unwrap();
        for (tag, why) in [
            (
                1,
                EnableRefused::LimbMate {
                    limb: LimbName::Waist,
                    stopped: true,
                },
            ),
            (
                2,
                EnableRefused::ForeignHost {
                    bus: 1,
                    stopped: true,
                },
            ),
            (
                3,
                EnableRefused::BusEnded {
                    joint: leg,
                    stopped: false,
                },
            ),
        ] {
            events.enable_reply(&EnableReply {
                tag,
                outcome: Err(why),
            });
        }
        recording.step(1, 2).unwrap();
        recording.close(buses, 3).unwrap();
        let got: Vec<_> = written(&dir)
            .into_iter()
            .map(|e| (e.kind, e.limb, e.joint, e.bus, e.rule, e.reason, e.tag))
            .collect();
        let _ = std::fs::remove_dir_all(&root);
        let s = |s: &str| Some(s.to_owned());
        let refused = EventKind::EnableRefused;
        assert_eq!(
            got,
            [
                (
                    refused,
                    s("waist"),
                    None,
                    None,
                    s("host.mode"),
                    s("limb_mate"),
                    Some(1)
                ),
                (
                    refused,
                    None,
                    None,
                    s(&plans[1].name),
                    s("host.preflight"),
                    s("foreign_host"),
                    Some(2)
                ),
                (
                    refused,
                    s("left_leg"),
                    s("leg_a_one"),
                    None,
                    s("host.bus"),
                    s("bus_ended"),
                    Some(3)
                ),
            ]
        );
    }
}
