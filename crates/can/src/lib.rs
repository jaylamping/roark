#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod batch;
#[cfg(target_os = "linux")]
mod bus;
#[cfg(target_os = "linux")]
mod bus_orders;
mod by_id;
#[cfg(target_os = "linux")]
mod clock;
mod error_frame;
#[cfg(any(target_os = "linux", test))]
mod exit_wait;
mod order;
mod read;
#[cfg(target_os = "linux")]
mod slack;
mod slow;
mod stop;
#[cfg(target_os = "linux")]
#[expect(
    unsafe_code,
    reason = "recvmsg for the frame's flags, timestamp and drop count (rust.md section 10)"
)]
mod sys;
mod tick;
mod timing;
mod types;

#[cfg(target_os = "linux")]
pub use bus::{BusConfig, BusExit, BusLinks, BusRunError, Spawned, bus_info, spawn};

pub use error_frame::{BusError, classify};
pub use order::{Order, Rearmed};
pub use slow::{SLOW_SLOTS, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult, Unsent};
/// The frame record [`BusTick::on_frame`] reads, so a caller feeding a tick by hand needs no `telemetry` of its own.
pub use telemetry::{Direction, FrameRecord};
pub use tick::BusTick;
pub use timing::{DRIVE_TIMEOUT_NS, ENABLE_TO_RUN_NS, Timing, TimingError};
pub use types::{
    BusDrive, CommandBatch, ConfigError, Counters, Drain, DriveView, EchoSeen, LimbState, LimbView,
    MAX_DRIVES, MAX_SENDS, ModeSeen, NoSuchLimb, Observed, RearmRefused, Send, SendKind, SendList,
    SendOutcome, Snapshot, StopOutcome, StopReason,
};
