#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

#[cfg(target_os = "linux")]
mod clock;
#[cfg(target_os = "linux")]
mod control;
// The control thread is its only user; its tests run everywhere.
#[cfg(any(target_os = "linux", test))]
mod dispatch;
// The control thread is its only user; its tests run everywhere.
#[cfg(any(target_os = "linux", test))]
mod enable;
// The control thread and the runtime's stop are its users; its tests run everywhere.
#[cfg(any(target_os = "linux", test))]
mod latch;
// The control thread is its only user; the recorder it writes to is Linux's.
#[cfg(target_os = "linux")]
mod events;
mod plan;
mod request;
mod roster;
#[cfg(target_os = "linux")]
mod start;

#[cfg(target_os = "linux")]
pub use control::{ControlExit, View};
#[cfg(any(target_os = "linux", test))]
pub use enable::{Enable, EnableRefused, EnableReply};
pub use plan::{BusPlan, PlanError, offline, plan};
pub use request::{
    BusStop, Clear, ClearAt, ClearRefused, Reply, Scope, StopAt, route_clear, route_stop,
};
pub use roster::{JointSet, MAX_JOINTS, Roster, RosterJoint, TooManyJoints, UnknownJoint, Wire};
#[cfg(target_os = "linux")]
pub use start::{BusEnd, EndError, Runtime, RuntimeConfig, RuntimeExit, StartError, StartInfo};
