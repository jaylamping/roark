//! RobStride actuator facts and, later, the codec: typed frames to bytes and back.
//!
//! For now this crate holds only what the skeleton loader needs: the SI unit types every crate shares at the codec edge,
//! the device ID type, and the per-model table transcribed from the vendor manuals. The frame codec lands here with PLAN
//! item 2 and the codec step of "Start here".
//!
//! Must never: do I/O, allocate, read the clock or panic on input (rust.md section 7, can.md section 1).
//! Talks to: nothing. `skeleton`, and later `can`, `sim-drive` and `robot-cli`, depend on it.
//!
//! Manuals: `hardware/docs/robstride/` in marengo, RS00/RS02/RS04 revision 260713 and RS03 revision 261013. Citations below
//! use the manuals' own section numbers.
#![no_std]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod model;
mod units;

pub use model::{Model, ModelRanges, UnknownModel};
pub use units::{Amps, DeviceId, InvalidDeviceId, NewtonMeters, RadPerSec, Radians, Volts};
