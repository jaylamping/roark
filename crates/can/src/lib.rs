#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod error_frame;
mod tick;
mod types;

pub use error_frame::{BusError, classify};
pub use tick::BusTick;
pub use types::{
    BusState, CommandBatch, ConfigError, Counters, DRIVE_TIMEOUT_NS, Drain, DriveView, MAX_DRIVES,
    MAX_SENDS, Observed, Send, SendKind, SendList, SendOutcome, Snapshot, StopOutcome, StopReason,
    Timing,
};
