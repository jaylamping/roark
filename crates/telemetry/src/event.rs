//! (rt) Control's events: one lock-free ring from the control thread to the recorder, pushed when something happens
//! (safety.md section 8: every stop, enable, refused enable and clear is an event, handed over through a queue, never
//! logged from the realtime thread).

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use rtrb::{Consumer, Producer, RingBuffer};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Room for a burst: every limb stopped and every joint of an enable refused in one pass, many times over.
pub const RING_EVENTS: usize = 1024;

/// An event's level (logging.md section 2b).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Level {
    /// Something an operator or agent may want to know.
    Info,
    /// An operator or agent must look: a stop, a refused enable or clear.
    Error,
}

/// What happened: the closed list of event kinds, each `area.past_tense_verb` (logging.md section 2). Adding one is a
/// change to logging.md's list in the same PR.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub enum EventKind {
    /// Control stopped one limb, on every bus it is on.
    #[serde(rename = "limb.stopped")]
    LimbStopped,
    /// Control stopped the whole robot.
    #[serde(rename = "robot.stopped")]
    RobotStopped,
    /// An enable passed its checks and its joint's preflight started: one per joint it names.
    #[serde(rename = "enable.started")]
    EnableStarted,
    /// An enable ended with every joint it named enabled and held.
    #[serde(rename = "enable.succeeded")]
    EnableSucceeded,
    /// An enable was refused, before anything was sent or once its preflights or sequences failed.
    #[serde(rename = "enable.refused")]
    EnableRefused,
    /// A stopped limb was re-armed on one bus.
    #[serde(rename = "limb.cleared")]
    LimbCleared,
    /// A clear was refused, on one bus or for a limb on none.
    #[serde(rename = "clear.refused")]
    ClearRefused,
}

/// One event, as plain `Copy` data, so handing it over never allocates. Every name is a `'static` string from the
/// fixed vocabularies the event's source owns (limb names, rule IDs, reasons); a joint is its index in the joint table the ring
/// was made with, and a bus its index in the session's bus table, both written out by name in the file.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Event {
    /// When, on the session's monotonic clock ([`Epoch`](crate::Epoch)).
    pub mono_ns: u64,
    /// Its level.
    pub level: Level,
    /// What happened.
    pub kind: EventKind,
    /// The limb, if it concerns one.
    pub limb: Option<&'static str>,
    /// The joint, as its index in the ring's joint table, if it concerns one.
    pub joint: Option<usize>,
    /// The bus, as its index in the session's bus table, if it concerns one.
    pub bus: Option<usize>,
    /// The safety rule behind it, if one is (safety.md section 2).
    pub rule: Option<&'static str>,
    /// Why, in a word, when the rule alone doesn't say: a stop's `operator`, `shutdown` or `follows_bus_stop`, a
    /// refusal's variant (`already_enabled`, `preflight`), a refused clear's (`offline`, `busy`).
    pub reason: Option<&'static str>,
    /// The request's tag, if a request caused it.
    pub tag: Option<u64>,
}

/// What the control thread holds to hand over its events. [`Self::record`] never blocks, allocates or makes a system
/// call: when the recorder has fallen behind it drops the event and counts it, and the file's end marker says how
/// many were lost.
#[derive(Debug)]
pub struct EventRecorder {
    producer: Producer<Event>,
    lost: Arc<AtomicU64>,
}

impl EventRecorder {
    /// Hand over one event. Returns false if the ring was full and the event was dropped.
    pub fn record(&mut self, event: Event) -> bool {
        if self.producer.push(event).is_ok() {
            return true;
        }
        self.lost.fetch_add(1, Ordering::Relaxed);
        false
    }
}

/// The recorder's end of the event ring, and the joint names its events' indices refer to.
#[derive(Debug)]
pub(crate) struct EventDrain {
    pub(crate) consumer: Consumer<Event>,
    pub(crate) lost: Arc<AtomicU64>,
    pub(crate) joints: Vec<String>,
}

/// A ring of `capacity` events whose joints are `joints`, by index.
pub(crate) fn ring(joints: Vec<String>, capacity: usize) -> (EventRecorder, EventDrain) {
    let (producer, consumer) = RingBuffer::new(capacity);
    let lost = Arc::new(AtomicU64::new(0));
    (
        EventRecorder {
            producer,
            lost: Arc::clone(&lost),
        },
        EventDrain {
            consumer,
            lost,
            joints,
        },
    )
}
