//! Frames the host sends: one function per frame, each returning the frame to queue, never sending it (can.md section 1).
//!
//! The builders here are types 0, 1, 3, 4, 6 and 24 from the transmit allowlist, plus type 7, which only the set-ID command
//! sends (PLAN item 2). The allowlist's parameter reads and writes (17, 18) have no builder in this module. There is no way to build a save (22), baud rate (23) or protocol (25) frame, or a Disable with the fault-clear byte
//! set.

use crate::frame::{Frame, HOST_ID};
use crate::model::{MitRange, Model, UnvouchedModel};
use crate::units::{DeviceId, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians};

/// Communication types (manual §4.1), host side.
pub(crate) mod kind {
    pub(crate) const GET_ID: u8 = 0;
    pub(crate) const MIT: u8 = 1;
    pub(crate) const STATUS: u8 = 2;
    pub(crate) const ENABLE: u8 = 3;
    pub(crate) const DISABLE: u8 = 4;
    pub(crate) const SET_ZERO: u8 = 6;
    pub(crate) const SET_ID: u8 = 7;
    pub(crate) const PARAM_READ: u8 = 17;
    pub(crate) const PARAM_WRITE: u8 = 18;
    pub(crate) const FAULT: u8 = 21;
    pub(crate) const SAVE: u8 = 22;
    pub(crate) const BAUD: u8 = 23;
    pub(crate) const REPORTING: u8 = 24;
    pub(crate) const PROTOCOL: u8 = 25;
}

/// Data bytes of a set-zero frame (§4.1.5: `Byte[0]=1`).
pub(crate) const SET_ZERO_DATA: [u8; 8] = [1, 0, 0, 0, 0, 0, 0, 0];

/// Data bytes of the version query, a type-4 frame (§4.1.4, "Version number read frame").
pub(crate) const VERSION_QUERY_DATA: [u8; 8] = [0, 0xC4, 0, 0, 0, 0, 0, 0];

/// Data bytes 0 to 5 of a type-24 frame; byte 6 is the switch (§4.1.11).
pub(crate) const REPORTING_PREFIX: [u8; 6] = [1, 2, 3, 4, 5, 6];

/// The active-reporting switch (§4.1.11). Reporting is off by default, but a drive keeps it on across host processes,
/// so the host turns it off at start and at exit (PLAN item 2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Reporting {
    /// `F_CMD` 00.
    Off,
    /// `F_CMD` 01: the drive reports type-24 frames every 10 ms by default.
    On,
}

impl Reporting {
    pub(crate) const fn byte(self) -> u8 {
        match self {
            Self::Off => 0,
            Self::On => 1,
        }
    }
}

/// One MIT-mode (operation control) command, in the drive's own coordinates: no joint sign, zero or gearing.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MitCommand {
    /// Target position.
    pub position: Radians,
    /// Target velocity.
    pub velocity: RadPerSec,
    /// Position gain.
    pub kp: NmPerRad,
    /// Velocity gain.
    pub kd: NmSecPerRad,
    /// Feed-forward torque.
    pub torque: NewtonMeters,
}

/// Which MIT field an [`EncodeError`] is about.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MitField {
    /// Target position.
    Position,
    /// Target velocity.
    Velocity,
    /// Position gain.
    Kp,
    /// Velocity gain.
    Kd,
    /// Feed-forward torque.
    Torque,
}

/// A command the codec refuses to encode. Encode never clamps (PLAN item 3).
#[derive(Clone, Copy, Debug, PartialEq, thiserror::Error)]
pub enum EncodeError {
    /// A field is outside the model's MIT range.
    #[error("MIT {field:?} {value} is outside {min} to {max}")]
    OutOfRange {
        /// The field.
        field: MitField,
        /// The value refused.
        value: f64,
        /// The lowest value the model accepts.
        min: f64,
        /// The highest value the model accepts.
        max: f64,
    },
    /// The model's MIT scales aren't settled.
    #[error("{0} MIT scales are not settled; no command is encoded for it")]
    UnvouchedModel(Model),
}

impl From<UnvouchedModel> for EncodeError {
    fn from(e: UnvouchedModel) -> Self {
        Self::UnvouchedModel(e.0)
    }
}

/// Type 0 (§4.1.1): ask a drive for its MCU UID. Also how a scan finds which IDs answer.
#[must_use]
pub const fn get_id(target: DeviceId) -> Frame {
    host_frame(kind::GET_ID, 0, target, [0; 8])
}

/// Type 1 (§4.1.2): one MIT command. The torque code rides in the ID; the other four fields are big-endian in the data.
///
/// # Errors
/// [`EncodeError::OutOfRange`] naming the first field outside the model's range, or [`EncodeError::UnvouchedModel`].
pub fn mit(model: Model, target: DeviceId, command: &MitCommand) -> Result<Frame, EncodeError> {
    let s = model.mit_scales()?;
    let position = code(s.position, command.position.get(), MitField::Position)?;
    let velocity = code(s.velocity, command.velocity.get(), MitField::Velocity)?;
    let kp = code(s.kp, command.kp.get(), MitField::Kp)?;
    let kd = code(s.kd, command.kd.get(), MitField::Kd)?;
    let [torque_hi, torque_lo] =
        code(s.torque, command.torque.get(), MitField::Torque)?.to_be_bytes();
    let ([p0, p1], [v0, v1], [kp0, kp1], [kd0, kd1]) = (
        position.to_be_bytes(),
        velocity.to_be_bytes(),
        kp.to_be_bytes(),
        kd.to_be_bytes(),
    );
    Ok(Frame::new(
        kind::MIT,
        torque_hi,
        torque_lo,
        target.get(),
        [p0, p1, v0, v1, kp0, kp1, kd0, kd1],
    ))
}

fn code(range: MitRange, value: f64, field: MitField) -> Result<u16, EncodeError> {
    range.code(value).ok_or(EncodeError::OutOfRange {
        field,
        value,
        min: range.min(),
        max: range.max(),
    })
}

/// Type 3 (§4.1.3): enable. The drive answers with a type-2 status frame in Run mode.
#[must_use]
pub const fn enable(target: DeviceId) -> Frame {
    host_frame(kind::ENABLE, 0, target, [0; 8])
}

/// Type 4 (§4.1.4): disable, with the fault-clear byte unset. The codec has no fault-clear frame (PLAN item 2).
#[must_use]
pub const fn disable(target: DeviceId) -> Frame {
    host_frame(kind::DISABLE, 0, target, [0; 8])
}

/// Type 4 with `00 C4` (§4.1.4): ask for the firmware version. The reply is a type-2 frame starting `00 C4 56`.
#[must_use]
pub const fn version_query(target: DeviceId) -> Frame {
    host_frame(kind::DISABLE, 0, target, VERSION_QUERY_DATA)
}

/// Type 6 (§4.1.5): set the current position as the mechanical zero. Only with the limb stopped, and nothing that matters
/// to this drive for 800 ms after: it goes silent 511 to 614 ms later for 45 to 66 ms (PLAN item 2).
#[must_use]
pub const fn set_zero(target: DeviceId) -> Frame {
    host_frame(kind::SET_ZERO, 0, target, SET_ZERO_DATA)
}

/// Type 7 (§4.1.5, "Set motor `CAN_ID`"): give `target` the ID `new`, effective at once. Only from the set-ID command,
/// with exactly one drive answering on the bus (PLAN item 2).
#[must_use]
pub const fn set_id(target: DeviceId, new: DeviceId) -> Frame {
    host_frame(kind::SET_ID, new.get(), target, [0; 8])
}

/// Type 24 (§4.1.11): switch active reporting.
#[must_use]
pub const fn active_reporting(target: DeviceId, switch: Reporting) -> Frame {
    let [r0, r1, r2, r3, r4, r5] = REPORTING_PREFIX;
    host_frame(
        kind::REPORTING,
        0,
        target,
        [r0, r1, r2, r3, r4, r5, switch.byte(), 0],
    )
}

/// A frame with the host in data area bits 15..8 and the target as destination, the layout of every host frame but MIT.
const fn host_frame(kind: u8, area_hi: u8, target: DeviceId, data: [u8; 8]) -> Frame {
    Frame::new(kind, area_hi, HOST_ID, target.get(), data)
}
