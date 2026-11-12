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
                    limb: match scope {
                        Scope::Robot => None,
                        Scope::Limb(limb) => Some(limb.as_str()),
                    },
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
        let limb = match scope {
            Scope::Robot => None,
            Scope::Limb(limb) => Some(limb.as_str()),
        };
        self.record(Event {
            limb,
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

/// The kind of a stop of `scope`.
const fn kind(scope: Scope) -> EventKind {
    match scope {
        Scope::Robot => EventKind::RobotStopped,
        Scope::Limb(_) => EventKind::LimbStopped,
    }
}
