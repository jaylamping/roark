//! The RobStride codec: typed frames to bytes and back, the per-model tables transcribed from the vendor manuals, and the
//! SI unit types every crate shares at the codec edge.
//!
//! Must never: do I/O, allocate, read the clock or panic on input (rust.md section 7, can.md section 1).
//! Talks to: nothing. `skeleton`, and later `can`, `sim-drive` and `robot-cli`, depend on it.
//!
//! Manuals: `hardware/docs/robstride/` in marengo, RS00/RS02/RS04 revision 260713 and RS03 revision 261013. Citations below
//! use the manuals' own section numbers, which are the same in all four.
//!
//! # Protocol rules
//!
//! - **Frames:** CAN 2.0B extended, 1 Mbit/s, always 8 data bytes (§4). The 29-bit ID layout is in [`frame`](crate::Frame)
//!   and nowhere else.
//! - **Byte order:** MIT fields and status codes big-endian (§4.1.2); parameter index and value little-endian (§4.1.6).
//! - **Addresses:** the host is 0xFD ([`HOST_ID`]). A host frame carries the host in ID bits 15..8 and the target drive in
//!   bits 7..0; a drive's reply carries the drive in bits 15..8 and the host in bits 7..0. Type-0 replies use 0xFE in
//!   bits 7..0 instead (§4.1.1). Type 1 has no host field: its bits 23..8 are the torque code.
//! - **Reserved bits:** zero on transmit; ignored on receive.
//! - **Matching a reply:** by bus, device ID and communication type, then against the drive the skeleton expects (its UID
//!   once commissioned). Never by device ID alone (can.md section 1). This crate gives the device and type; the bus layer
//!   knows the bus.
//! - **Strict both ways:** encode refuses an out-of-range value and never clamps; decode returns a typed frame or a typed
//!   error for any input.
#![no_std]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod decode;
pub mod encode;
mod frame;
mod model;
mod units;

pub use decode::{
    DecodeError, Echo, EchoKind, Feedback, Header, Inbound, Mode, ParamOutcome, Status,
    StatusFault, StatusFaults, decode,
};
pub use encode::{EncodeError, MitCommand, MitField, Reporting};
pub use frame::{Frame, HOST_ID};
pub use model::{MitRange, MitScales, Model, ModelRanges, UnknownModel, UnvouchedModel};
pub use units::{
    Amps, Celsius, DeviceId, InvalidDeviceId, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec,
    Radians, Uid, Volts,
};
