#![doc = include_str!("../README.md")]

mod error_frame;
mod tick;
mod types;

pub use error_frame::{BusError, classify};
pub use tick::BusTick;
pub use types::{
    BusState, CommandBatch, Counters, DriveView, MAX_DRIVES, MAX_SENDS, Observed, Send, SendKind,
    SendList, SendOutcome, Snapshot, StopOutcome, StopReason, Timing, TooManyDrives,
};
