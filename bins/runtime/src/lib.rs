#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

#[cfg(target_os = "linux")]
mod clock;
#[cfg(target_os = "linux")]
mod control;
// The control thread is its only user; its tests run everywhere.
#[cfg(any(target_os = "linux", test))]
mod dispatch;
mod plan;
mod request;
#[cfg(target_os = "linux")]
mod start;

#[cfg(target_os = "linux")]
pub use control::{ControlExit, View};
pub use plan::{BusPlan, PlanError, offline, plan};
pub use request::{
    BusStop, Clear, ClearAt, ClearRefused, Reply, Scope, StopAt, route_clear, route_stop,
};
#[cfg(target_os = "linux")]
pub use start::{BusEnd, EndError, Runtime, RuntimeConfig, RuntimeExit, StartError, StartInfo};
