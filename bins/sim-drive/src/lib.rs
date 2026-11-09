#![doc = include_str!("../README.md")]

mod fault;
mod plant;
mod sim;

pub use fault::{FAULT_PLAN, Fault, Injected, PlanFull, Trigger};
pub use plant::PLANT_DAMPING;
pub use sim::SimDrive;

#[cfg(target_os = "linux")]
mod bus;

#[cfg(target_os = "linux")]
pub use bus::{NotVcan, ServeError, ensure_vcan, serve};
