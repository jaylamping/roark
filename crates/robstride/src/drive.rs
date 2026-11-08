//! The drive's side of the protocol, for `sim-drive` (PLAN item 4) and tests: a host command read in full, and the
//! frames a drive sends built.
//!
//! A drive frame is a [`DriveFrame`], never a [`Frame`](crate::Frame). Only [`encode`](crate::encode) makes a `Frame`,
//! and the bus layer transmits only `Frame`s, so code that sends to the robot's drives can't send one of these: the
//! transmit allowlist (PLAN item 2) is held by the types, whichever crates a build compiles together.

use crate::DecodeError;
use crate::decode::{Echo, EchoKind, Feedback, Inbound, Mode, StatusFaults, decode};
use crate::encode::{MitCommand, Reporting, kind};
use crate::frame::{Frame, HOST_ID, IDENTITY_MARKER, parts};
use crate::model::{Drive, MitRange, Model, UnvouchedModel};
use crate::param::{Param, ParamValue, encode_value};
use crate::units::{DeviceId, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians, Uid};

/// A frame a drive sends. Built only by this module; the host's transmit path takes [`Frame`](crate::Frame) instead.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DriveFrame {
    id: u32,
    data: [u8; 8],
}

impl DriveFrame {
    /// The 29-bit extended ID.
    #[must_use]
    pub const fn id(&self) -> u32 {
        self.id
    }

    /// The 8 data bytes.
    #[must_use]
    pub const fn data(&self) -> [u8; 8] {
        self.data
    }

    const fn from(frame: Frame) -> Self {
        Self {
            id: frame.id(),
            data: frame.data(),
        }
    }
}

/// A host frame as the drive it targets reads it.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HostFrame {
    /// The drive the frame is for.
    pub target: DeviceId,
    /// What it asks.
    pub command: Command,
}

/// What a host frame asks of its drive.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Command {
    /// Type 0 (§4.1.1): answer with the MCU UID.
    GetId,
    /// Type 1 (§4.1.2): one MIT command, as codes; [`MitCodes::command`] gives SI with the drive's model.
    Mit(MitCodes),
    /// Type 3 (§4.1.3).
    Enable,
    /// Type 4 (§4.1.4), fault-clear byte unset.
    Disable,
    /// Type 4 with byte 0 = 1. The host never sends one.
    FaultClear,
    /// Type 4 with `00 C4` (§4.1.4).
    VersionQuery,
    /// Type 6 (§4.1.5).
    SetZero,
    /// Type 7 (§4.1.5).
    SetId {
        /// The ID to take.
        new: DeviceId,
    },
    /// Type 17 (§4.1.6).
    ParamRead(Param),
    /// Type 18 (§4.1.7), one of the writes the host builds.
    ParamWrite {
        /// The register.
        param: Param,
        /// The value.
        value: ParamValue,
    },
    /// Type 24 (§4.1.11).
    Reporting(Reporting),
}

/// The five 16-bit codes of an MIT command (§4.1.2): torque from ID bits 23..8, the rest big-endian in the data.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MitCodes {
    position: u16,
    velocity: u16,
    kp: u16,
    kd: u16,
    torque: u16,
}

impl MitCodes {
    /// The command in SI with `model`'s MIT scales.
    ///
    /// # Errors
    /// [`UnvouchedModel`] for a model whose scales aren't settled.
    pub fn command(self, model: Model) -> Result<MitCommand, UnvouchedModel> {
        let s = model.mit_scales()?;
        Ok(MitCommand {
            position: Radians(s.position.value(self.position)),
            velocity: RadPerSec(s.velocity.value(self.velocity)),
            kp: NmPerRad(s.kp.value(self.kp)),
            kd: NmSecPerRad(s.kd.value(self.kd)),
            torque: NewtonMeters(s.torque.value(self.torque)),
        })
    }
}

/// Which status field a [`DriveError::OutOfRange`] is about.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StatusField {
    /// Position.
    Position,
    /// Velocity.
    Velocity,
    /// Torque.
    Torque,
    /// Temperature, sent in tenths of a degree.
    Temperature,
}

/// A drive frame the codec refuses to build. It never clamps (PLAN item 3).
#[derive(Clone, Copy, Debug, PartialEq, thiserror::Error)]
pub enum DriveError {
    /// A status field outside what the frame can carry.
    #[error("status {field:?} {value} is outside {min} to {max}")]
    OutOfRange {
        /// The field.
        field: StatusField,
        /// The value refused.
        value: f64,
        /// The lowest value the frame carries.
        min: f64,
        /// The highest value the frame carries.
        max: f64,
    },
    /// The model's MIT scales aren't settled, so its status can't be encoded.
    #[error("{0} MIT scales are not settled; no status is encoded for it")]
    UnvouchedModel(Model),
    /// A value that isn't of the register's type, or a float that doesn't fit an f32.
    #[error("the value given isn't one {param:?} holds")]
    WrongValue {
        /// The register.
        param: Param,
    },
}

/// The command a host frame carries, or `None` for a frame that isn't one (a drive's reply, another drive's report).
///
/// # Errors
/// What [`decode`] refuses, the same frames for the same reasons.
pub fn command(id: u32, data: &[u8]) -> Result<Option<HostFrame>, DecodeError> {
    let Inbound::Echo(Echo { kind, target }) = decode(id, data)? else {
        return Ok(None);
    };
    let command = match kind {
        EchoKind::GetId => Command::GetId,
        EchoKind::Mit => Command::Mit(mit_codes(id, data)?),
        EchoKind::Enable => Command::Enable,
        EchoKind::Disable => Command::Disable,
        EchoKind::FaultClear => Command::FaultClear,
        EchoKind::VersionQuery => Command::VersionQuery,
        EchoKind::SetZero => Command::SetZero,
        EchoKind::SetId { new } => Command::SetId { new },
        EchoKind::ParamRead(param) => Command::ParamRead(param),
        EchoKind::ParamWrite { param, value } => Command::ParamWrite { param, value },
        EchoKind::Reporting(switch) => Command::Reporting(switch),
    };
    Ok(Some(HostFrame { target, command }))
}

fn mit_codes(id: u32, data: &[u8]) -> Result<MitCodes, DecodeError> {
    let p = parts(id).ok_or(DecodeError::IdTooWide(id))?;
    let [p0, p1, v0, v1, kp0, kp1, kd0, kd1]: [u8; 8] =
        data.try_into().map_err(|_| DecodeError::BadLength {
            len: data.len(),
            id,
        })?;
    Ok(MitCodes {
        position: u16::from_be_bytes([p0, p1]),
        velocity: u16::from_be_bytes([v0, v1]),
        kp: u16::from_be_bytes([kp0, kp1]),
        kd: u16::from_be_bytes([kd0, kd1]),
        torque: u16::from_be_bytes([p.area_hi, p.area_lo]),
    })
}

/// Type 2 (§4.1.2): `drive`'s answer to a command, with its mode, fault bits and feedback in its model's scales.
///
/// # Errors
/// [`DriveError::OutOfRange`] for a field the frame can't carry, or [`DriveError::UnvouchedModel`].
pub fn status(
    drive: Drive,
    mode: Mode,
    faults: StatusFaults,
    feedback: &Feedback,
) -> Result<DriveFrame, DriveError> {
    pose(kind::STATUS, drive, mode, faults, feedback)
}

/// Type 24 (§4.1.11): an active report, the same layout as [`status`].
///
/// # Errors
/// As [`status`].
pub fn report(
    drive: Drive,
    mode: Mode,
    faults: StatusFaults,
    feedback: &Feedback,
) -> Result<DriveFrame, DriveError> {
    pose(kind::REPORTING, drive, mode, faults, feedback)
}

fn pose(
    kind: u8,
    drive: Drive,
    mode: Mode,
    faults: StatusFaults,
    feedback: &Feedback,
) -> Result<DriveFrame, DriveError> {
    let s = drive
        .model()
        .mit_scales()
        .map_err(|e| DriveError::UnvouchedModel(e.0))?;
    let [p0, p1] = code(s.position, feedback.position.get(), StatusField::Position)?.to_be_bytes();
    let [v0, v1] = code(s.velocity, feedback.velocity.get(), StatusField::Velocity)?.to_be_bytes();
    let [t0, t1] = code(s.torque, feedback.torque.get(), StatusField::Torque)?.to_be_bytes();
    let [c0, c1] = tenths(feedback.temperature.get())?.to_be_bytes();
    let mode = match mode {
        Mode::Reset => 0,
        Mode::Calibration => 1,
        Mode::Run => 2,
    };
    Ok(DriveFrame::from(Frame::new(
        kind,
        mode << 6 | faults.bits(),
        drive.id().get(),
        HOST_ID,
        [p0, p1, v0, v1, t0, t1, c0, c1],
    )))
}

fn code(range: MitRange, value: f64, field: StatusField) -> Result<u16, DriveError> {
    range.code(value).ok_or(DriveError::OutOfRange {
        field,
        value,
        min: range.min(),
        max: range.max(),
    })
}

/// §4.1.2 "Temp(Celsius) *10", rounded to the nearest tenth.
fn tenths(celsius: f64) -> Result<u16, DriveError> {
    let max = f64::from(u16::MAX) / 10.0;
    if !celsius.is_finite() || !(0.0..=max).contains(&celsius) {
        return Err(DriveError::OutOfRange {
            field: StatusField::Temperature,
            value: celsius,
            min: 0.0,
            max,
        });
    }
    #[expect(
        clippy::as_conversions,
        clippy::cast_possible_truncation,
        clippy::cast_sign_loss,
        reason = "range checked above: celsius * 10 + 0.5 is in [0.5, 65535.5], so this rounds into 0..=65535"
    )]
    let code = (celsius * 10.0 + 0.5) as u32;
    u16::try_from(code).map_err(|_| DriveError::OutOfRange {
        field: StatusField::Temperature,
        value: celsius,
        min: 0.0,
        max,
    })
}

/// Type 0 reply (§4.1.1): `device` and its MCU UID, addressed to 0xFE.
#[must_use]
pub const fn identity(device: DeviceId, uid: Uid) -> DriveFrame {
    DriveFrame::from(Frame::new(
        kind::GET_ID,
        0,
        device.get(),
        IDENTITY_MARKER,
        uid.0,
    ))
}

/// Type-17 reply (§4.1.6): `param` reads `value`.
///
/// # Errors
/// [`DriveError::WrongValue`] if `value` isn't of `param`'s type, or is a float that doesn't fit an f32.
pub fn param_value(
    device: DeviceId,
    param: Param,
    value: ParamValue,
) -> Result<DriveFrame, DriveError> {
    let [b4, b5, b6, b7] = encode_value(param, value).ok_or(DriveError::WrongValue { param })?;
    let [i0, i1] = param.index().to_le_bytes();
    Ok(DriveFrame::from(Frame::new(
        kind::PARAM_READ,
        0,
        device.get(),
        HOST_ID,
        [i0, i1, 0, 0, b4, b5, b6, b7],
    )))
}

/// Type-17 reply (§4.1.6) with ID bits 23..16 = 01: the read of `param` failed.
#[must_use]
pub const fn param_refused(device: DeviceId, param: Param) -> DriveFrame {
    let [i0, i1] = param.index().to_le_bytes();
    DriveFrame::from(Frame::new(
        kind::PARAM_READ,
        1,
        device.get(),
        HOST_ID,
        [i0, i1, 0, 0, 0, 0, 0, 0],
    ))
}
