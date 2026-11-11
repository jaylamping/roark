#![doc = include_str!("../README.md")]

#[cfg(target_os = "linux")]
mod clock;
#[cfg(target_os = "linux")]
mod control;
pub mod plan;
pub mod request;
#[cfg(target_os = "linux")]
mod start;

#[cfg(target_os = "linux")]
pub use control::{ControlExit, View};
pub use plan::{BusPlan, PlanError, plan};
pub use request::{ClearRefused, Reply, Request, Routed, Scope, route};
#[cfg(target_os = "linux")]
pub use start::{BusEnd, Runtime, RuntimeConfig, RuntimeExit, StartError, StopError};
