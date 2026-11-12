//! (rt) Control's events, handed to the recorder through its event ring (safety.md section 8: every stop, enable,
//! refused enable and clear is an event, never logged from the realtime thread). Pure over the ring, so it is tested
//! on any OS; the control thread (Linux) is its only user outside the tests.

use telemetry::{Event, EventRecorder, Level};

use crate::dispatch::Why;
use crate::enable::{Enable, EnableReply};
use crate::request::{ClearRefused, Reply, Scope};

/// Control's end of the event ring, and the time of the pass its events are stamped with.
pub(crate) struct Events {
    recorder: Option<EventRecorder>,
    now_ns: u64,
}

impl Events {
    /// Events into `recorder`; none recorded without one.
    pub(crate) const fn new(recorder: Option<EventRecorder>) -> Self {
        Self {
            recorder,
            now_ns: 0,
        }
    }

    /// Stamp the events that follow with `now_ns`, on the session's monotonic clock.
    pub(crate) const fn at(&mut self, now_ns: u64) {
        self.now_ns = now_ns;
    }

    /// A stop taken from the latch: of one limb or the robot, under its rule, the operator, or a stop already made on
    /// another of the limb's buses.
    pub(crate) fn stop(&mut self, scope: Scope, why: Option<Why>) {
        let (rule, reason) = match why {
            Some(Why::Rule(rule)) => (Some(rule.as_str()), None),
            Some(Why::Operator) => (None, Some("operator")),
            Some(Why::Elsewhere) => (None, Some("follows_bus_stop")),
            None => (None, Some("cause_not_kept")),
        };
        let limb = match scope {
            Scope::Robot => None,
            Scope::Limb(limb) => Some(limb.as_str()),
        };
        self.record(Event {
            limb,
            rule,
            reason,
            ..self.event(Level::Error, "stop")
        });
    }

    /// An enable taken: one event per joint it names.
    pub(crate) fn enable(&mut self, enable: &Enable) {
        for joint in enable.joints.iter() {
            self.record(Event {
                joint: Some(joint),
                tag: Some(enable.tag),
                ..self.event(Level::Info, "enable")
            });
        }
    }

    /// An enable's answer: enabled, or refused under its rule.
    pub(crate) fn enable_reply(&mut self, reply: &EnableReply) {
        let event = match reply.outcome {
            Ok(()) => self.event(Level::Info, "enabled"),
            Err(why) => Event {
                joint: why.joint(),
                rule: why.rule().map(safety::RuleId::as_str),
                reason: Some(why.reason()),
                ..self.event(Level::Error, "enable_refused")
            },
        };
        self.record(Event {
            tag: Some(reply.tag),
            ..event
        });
    }

    /// A clear's answer from one bus, or its refusal.
    pub(crate) fn clear_reply(&mut self, reply: &Reply) {
        let event = match reply.outcome {
            Ok(()) => self.event(Level::Info, "cleared"),
            Err(why) => Event {
                reason: Some(match why {
                    ClearRefused::Bus(_) => "bus_refused",
                    ClearRefused::Offline => "offline",
                    ClearRefused::Busy => "busy",
                    ClearRefused::BusEnded => "bus_ended",
                    ClearRefused::Ending => "ending",
                }),
                ..self.event(Level::Error, "clear_refused")
            },
        };
        self.record(Event {
            limb: Some(reply.limb.as_str()),
            bus: reply.bus,
            tag: Some(reply.tag),
            ..event
        });
    }

    const fn event(&self, level: Level, kind: &'static str) -> Event {
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
