#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

#[cfg(target_os = "linux")]
mod bus;
mod error_frame;
mod read;
mod stop;
#[cfg(target_os = "linux")]
#[expect(
    unsafe_code,
    reason = "recvmsg and poll for the frame's flags, timestamp and drop count (rust.md section 10)"
)]
mod sys;
mod tick;
mod types;

#[cfg(target_os = "linux")]
pub use bus::{BusConfig, BusExit, BusLinks, BusRunError, DRAIN_MAX, Spawned, spawn};

pub use error_frame::{BusError, classify};
pub use tick::BusTick;
pub use types::{
    BusDrive, CommandBatch, ConfigError, Counters, DRIVE_TIMEOUT_NS, Drain, DriveView, EchoSeen,
    LimbState, LimbView, MAX_DRIVES, MAX_SENDS, NoSuchLimb, Observed, RearmRefused, Send, SendKind,
    SendList, SendOutcome, Snapshot, StopOutcome, StopReason, Timing, TimingError,
};
