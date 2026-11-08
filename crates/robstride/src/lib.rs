#![doc = include_str!("../README.md")]
#![no_std]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod decode;
pub mod drive;
pub mod encode;
mod frame;
mod model;
mod param;
mod units;

pub use decode::{
    DecodeError, Echo, EchoKind, Feedback, Header, Inbound, Mode, ParamOutcome, Status,
    StatusFault, StatusFaults, decode,
};
pub use encode::{EncodeError, MitCommand, MitField, Reporting};
pub use frame::{Frame, HOST_ID};
pub use model::{Drive, MitRange, MitScales, Model, ModelRanges, UnknownModel, UnvouchedModel};
pub use param::{
    CanTimeout, Damper, Param, ParamType, ParamValue, ReportInterval, RunMode, Write, ZeroSta,
};
pub use units::{
    Amps, Celsius, DeviceId, Gain, InvalidDeviceId, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec,
    RadPerSecSq, Radians, Uid, Volts,
};
