#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

#[cfg(target_os = "linux")]
mod clock;
#[cfg(target_os = "linux")]
mod control;
// The control thread is its only user; its tests run everywhere.
#[cfg(any(target_os = "linux", test))]
mod dispatch;
// Run by the control thread alone, which is Linux only: so are its tests.
#[cfg(target_os = "linux")]
mod enable;
mod plan;
mod request;
mod roster;
#[cfg(target_os = "linux")]
mod start;

#[cfg(target_os = "linux")]
pub use control::{ControlExit, View};
#[cfg(target_os = "linux")]
pub use enable::{Enable, EnableRefused, EnableReply};
pub use plan::{BusPlan, PlanError, offline, plan};
pub use request::{
    BusStop, Clear, ClearAt, ClearRefused, Reply, Scope, StopAt, route_clear, route_stop,
};
pub use roster::{JointSet, MAX_JOINTS, Roster, RosterJoint, TooManyJoints, UnknownJoint};
#[cfg(target_os = "linux")]
pub use start::{BusEnd, EndError, Runtime, RuntimeConfig, RuntimeExit, StartError, StartInfo};
