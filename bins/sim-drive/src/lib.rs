#![doc = include_str!("../README.md")]

mod fault;
mod plant;
mod sim;

pub use fault::{
    FAULT_PLAN, Fault, FaultRefused, INJECTED_LOG, Injected, MAX_LATE, MAX_TEMPERATURE_C, Trigger,
};
pub use sim::SimDrive;

#[cfg(target_os = "linux")]
mod bus;

#[cfg(target_os = "linux")]
pub use bus::{NotVcan, ServeError, ensure_vcan, serve};
