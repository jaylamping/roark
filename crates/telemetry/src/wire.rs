//! The messages as they are in the file: JSON, each channel's JSON Schema generated from these types and stored in the
//! file (logging.md section 3). Readers (tests, tools) parse them with these same types.
//!
//! Every time is a [`Stamp`] of whole seconds and nanoseconds, never one integer of nanoseconds: a JSON reader that
//! parses numbers as doubles (JavaScript, so Foxglove) loses the last digits of a nanosecond Unix time.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::batch::{Direction, FrameRecord, TickBatch};
use crate::event::{EventKind, Level};
use crate::session::SessionInfo;

/// A time: seconds and nanoseconds since the Unix epoch for wall-clock times, since the session's
/// [`Epoch`](crate::Epoch) for monotonic ones. Foxglove's JSON time shape.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Stamp {
    /// Whole seconds.
    pub sec: u64,
    /// Nanoseconds past `sec`, 0 to 999,999,999.
    pub nsec: u32,
}

impl Stamp {
    /// A stamp from nanoseconds.
    #[must_use]
    pub fn from_ns(ns: u64) -> Self {
        Self {
            sec: ns / 1_000_000_000,
            nsec: u32::try_from(ns % 1_000_000_000).unwrap_or(0),
        }
    }
}

/// One frame inside a [`Frames`] message.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Frame {
    /// The raw 29-bit or 11-bit ID.
    pub id: u32,
    /// A 29-bit ID.
    pub extended: bool,
    /// An error frame.
    pub error: bool,
    /// A remote frame.
    pub remote: bool,
    /// The data, as long as the frame's length.
    pub data: Vec<u8>,
    /// The kernel's receive timestamp (wall clock).
    pub stamp: Stamp,
    /// Where it came from.
    pub direction: Direction,
}

impl From<&FrameRecord> for Frame {
    fn from(f: &FrameRecord) -> Self {
        Self {
            id: f.id,
            extended: f.extended,
            error: f.error,
            remote: f.remote,
            data: f.payload().to_vec(),
            stamp: Stamp::from_ns(f.stamp_ns),
            direction: f.direction,
        }
    }
}

/// `/can/<bus>/frames`: one bus's tick, every frame in order (logging.md section 8.2).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[schemars(rename = "roark.can.Frames")]
pub struct Frames {
    /// The tick number.
    pub tick: u64,
    /// The tick's start, monotonic clock.
    pub monotonic: Stamp,
    /// The wall clock when the tick woke.
    pub wall: Stamp,
    /// False while the bus was unhealthy.
    pub valid: bool,
    /// The socket's overflow counter (`SO_RXQ_OVFL`).
    pub kernel_drops: u32,
    /// Frames that arrived after the tick's batch was full, so aren't here.
    pub omitted: u32,
    /// The frames.
    pub frames: Vec<Frame>,
}

impl From<&TickBatch> for Frames {
    fn from(b: &TickBatch) -> Self {
        Self {
            tick: b.tick,
            monotonic: Stamp::from_ns(b.mono_ns),
            wall: Stamp::from_ns(b.wall_ns),
            valid: b.valid,
            kernel_drops: b.kernel_drops,
            omitted: b.omitted(),
            frames: b.frames().iter().map(Frame::from).collect(),
        }
    }
}

/// `/recorder/gap`: batches a bus dropped because the recorder's ring was full (logging.md section 8.4). Written where
/// the hole is.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[schemars(rename = "roark.recorder.Gap")]
pub struct Gap {
    /// The bus.
    pub bus: String,
    /// Batches lost.
    pub batches: u64,
    /// Frames in them.
    pub frames: u64,
    /// The first lost tick.
    pub first_tick: u64,
    /// The last lost tick.
    pub last_tick: u64,
}

/// `/clock`, once a second: the two clocks read together, so monotonic times map to wall-clock times even when NTP
/// steps the wall clock (logging.md section 8.3).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[schemars(rename = "roark.Clock")]
pub struct Clock {
    /// The monotonic clock.
    pub monotonic: Stamp,
    /// The wall clock.
    pub wall: Stamp,
}

/// `/event`: one of control's events (safety.md section 8; logging.md sections 2 and 2a).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[schemars(rename = "roark.Event")]
pub struct Event {
    /// When, on the session's monotonic clock.
    pub monotonic: Stamp,
    /// When, on the wall clock: the monotonic time mapped through the recorder's newest reading of the two clocks
    /// together (taken each drain; `/clock` records one a second).
    pub wall: Stamp,
    /// Its level.
    pub level: Level,
    /// What happened.
    pub kind: EventKind,
    /// The limb.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limb: Option<String>,
    /// The joint.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub joint: Option<String>,
    /// The bus.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bus: Option<String>,
    /// The safety rule behind it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rule: Option<String>,
    /// Why, in a word, when the rule alone doesn't say.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    /// The request's tag.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tag: Option<u64>,
}

/// The events' totals in the end marker.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct EventTotals {
    /// Events written.
    pub written: u64,
    /// Events dropped because the ring was full.
    pub lost: u64,
}

/// A bus's totals in the end marker.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct BusTotals {
    /// The bus.
    pub name: String,
    /// Batches written.
    pub batches: u64,
    /// Frames written.
    pub frames: u64,
    /// Batches dropped because the ring was full.
    pub batches_lost: u64,
    /// Frames in them.
    pub frames_lost: u64,
    /// Frames past a batch's capacity.
    pub frames_omitted: u64,
}

/// The file's first message: which session and file this is, and everything needed to read it alone.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Header {
    /// The session ID: its UTC start.
    pub session: String,
    /// The file's number in the session.
    pub file: u32,
    /// What the session was started with.
    #[serde(flatten)]
    pub info: SessionInfo,
}

/// The file's last message. A file without one was cut off.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct End {
    /// Per bus, in the session's bus order.
    pub buses: Vec<BusTotals>,
    /// Control's events.
    #[serde(default)]
    pub events: EventTotals,
}

/// `/session`: the header first and the end marker last.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case")]
#[schemars(rename = "roark.Session")]
pub enum SessionRecord {
    /// The first message.
    Header(Header),
    /// The last message.
    End(End),
}
