#![doc = include_str!("../README.md")]

mod sim;

pub use sim::SimDrive;

#[cfg(target_os = "linux")]
mod bus;

#[cfg(target_os = "linux")]
pub use bus::{NotVcan, ServeError, ensure_vcan, serve};
