//! Frames the host reads: replies and reports from drives, and its own frames echoed back (loopback with
//! `RECV_OWN_MSGS`, can.md section 2). Any ID and any bytes give a typed frame or a typed error; nothing here panics.
//!
//! Reserved ID bits are ignored on receive. A frame is checked against what the manual says its bytes are, and refused if
//! they say something else, so a foreign or corrupt frame never reads as one of ours.

use crate::encode::{REPORTING_PREFIX, Reporting, SET_ZERO_DATA, VERSION_QUERY_DATA, kind};
use crate::frame::{HOST_ID, IDENTITY_MARKER, parts};
use crate::model::{Model, UnvouchedModel};
use crate::units::{Celsius, DeviceId, NewtonMeters, RadPerSec, Radians, Uid};

/// A frame read from the bus.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Inbound {
    /// Type-0 reply (§4.1.1): a drive's ID and MCU UID.
    Identity {
        /// The drive that answered.
        device: DeviceId,
        /// Its MCU unique identifier.
        uid: Uid,
    },
    /// Type-2 reply (§4.1.2) to a command: MIT, enable, disable, set zero or parameter write.
    Status(Status),
    /// Type-24 report (§4.1.11), sent on its own while active reporting is on. Same layout as [`Inbound::Status`].
    Report(Status),
    /// Type-2 reply starting `00 C4 56` (§4.1.4): the firmware version. Not a pose.
    Version {
        /// The drive's mode and fault bits.
        header: Header,
        /// Bytes 3 to 6, most significant first.
        version: [u8; 4],
    },
    /// Type-21 fault report (§4.1.8).
    Fault {
        /// The drive that reported.
        device: DeviceId,
        /// Bytes 0 to 3, raw: the manual names the bits but not the byte order. Non-zero means faulted.
        faults: [u8; 4],
        /// Bytes 4 to 7, raw.
        warnings: [u8; 4],
    },
    /// Type-17 reply (§4.1.6, §4.1.14) to a parameter read.
    Param {
        /// The drive that answered.
        device: DeviceId,
        /// The parameter index, 0x70xx.
        index: u16,
        /// The value bytes, or the drive's refusal.
        outcome: ParamOutcome,
    },
    /// One of the host's own frames, read back.
    Echo(Echo),
}

/// The status header carried in the ID of type-2 and type-24 frames (§4.1.2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Header {
    /// The drive that sent the frame.
    pub device: DeviceId,
    /// Its mode, ID bits 23..22.
    pub mode: Mode,
    /// Its fault bits, ID bits 21..16.
    pub faults: StatusFaults,
}

/// A drive's mode (§4.1.2, ID bits 23..22). Value 3 is undefined and refused.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// 0: reset. The drive boots into it and is not driving the motor.
    Reset,
    /// 1: calibration.
    Calibration,
    /// 2: running ("Motor mode").
    Run,
}

/// One status fault bit (§4.1.2, ID bits 21..16).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StatusFault {
    /// Bit 16.
    Undervoltage,
    /// Bit 17: three-phase overcurrent.
    Overcurrent,
    /// Bit 18.
    Overtemperature,
    /// Bit 19: magnetic encoder fault.
    Encoder,
    /// Bit 20: stall ("gridlock") overload.
    StallOverload,
    /// Bit 21: not calibrated.
    Uncalibrated,
}

impl StatusFault {
    /// Every fault bit, lowest first.
    pub const ALL: [Self; 6] = [
        Self::Undervoltage,
        Self::Overcurrent,
        Self::Overtemperature,
        Self::Encoder,
        Self::StallOverload,
        Self::Uncalibrated,
    ];

    /// The flag's bit within ID bits 21..16 (bit 16 is 1).
    const fn mask(self) -> u8 {
        match self {
            Self::Undervoltage => 1 << 0,
            Self::Overcurrent => 1 << 1,
            Self::Overtemperature => 1 << 2,
            Self::Encoder => 1 << 3,
            Self::StallOverload => 1 << 4,
            Self::Uncalibrated => 1 << 5,
        }
    }
}

/// The set of fault bits a status frame carried.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct StatusFaults(u8);

impl StatusFaults {
    /// Whether `fault` is set.
    #[must_use]
    pub const fn contains(self, fault: StatusFault) -> bool {
        self.0 & fault.mask() != 0
    }

    /// Whether no fault is set.
    #[must_use]
    pub const fn is_empty(self) -> bool {
        self.0 == 0
    }
}

impl FromIterator<StatusFault> for StatusFaults {
    fn from_iter<I: IntoIterator<Item = StatusFault>>(faults: I) -> Self {
        Self(faults.into_iter().fold(0, |bits, f| bits | f.mask()))
    }
}

/// A type-2 or type-24 frame's fields, as the codes the drive sent. [`Status::feedback`] turns them into SI with the
/// drive's model.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Status {
    /// Mode and fault bits.
    pub header: Header,
    /// Position code, bytes 0 and 1.
    pub position: u16,
    /// Velocity code, bytes 2 and 3.
    pub velocity: u16,
    /// Torque code, bytes 4 and 5.
    pub torque: u16,
    /// Bytes 6 and 7: tenths of a degree (§4.1.2, "Temp(Celsius) *10").
    pub temperature: Celsius,
}

/// A status frame in SI, in the drive's own coordinates.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Feedback {
    /// Output position.
    pub position: Radians,
    /// Output velocity.
    pub velocity: RadPerSec,
    /// Output torque.
    pub torque: NewtonMeters,
    /// Drive temperature.
    pub temperature: Celsius,
}

impl Status {
    /// The status in SI with `model`'s MIT scales.
    ///
    /// # Errors
    /// [`UnvouchedModel`] for a model whose scales aren't settled: a wrong scale decodes silently to wrong values.
    pub fn feedback(&self, model: Model) -> Result<Feedback, UnvouchedModel> {
        let s = model.mit_scales()?;
        // Each value is inside its finite range, so `new` can't refuse it.
        Ok(Feedback {
            position: Radians(s.position.value(self.position)),
            velocity: RadPerSec(s.velocity.value(self.velocity)),
            torque: NewtonMeters(s.torque.value(self.torque)),
            temperature: self.temperature,
        })
    }
}

/// The value bytes of a type-17 reply, or the drive's refusal (§4.1.6: ID bits 23..16 are 00 on success, 01 on failure).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ParamOutcome {
    /// Bytes 4 to 7, low byte first. What they mean depends on the parameter.
    Read([u8; 4]),
    /// The drive couldn't read the parameter.
    Refused,
}

/// One of the host's own frames, read back. On real CAN the echo means the adapter's controller took the frame, not
/// that it went out on the wire (PLAN item 3).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Echo {
    /// What the frame was.
    pub kind: EchoKind,
    /// The drive it was sent to.
    pub target: DeviceId,
}

/// Which host frame an [`Echo`] is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EchoKind {
    /// Type 0.
    GetId,
    /// Type 1. Its ID carries no host field, so its sender can't be checked.
    Mit,
    /// Type 3.
    Enable,
    /// Type 4, fault-clear byte unset.
    Disable,
    /// Type 4 with byte 0 = 1. This codec never builds one, so seeing it means another sender is on the bus.
    FaultClear,
    /// Type 4 with `00 C4`.
    VersionQuery,
    /// Type 6.
    SetZero,
    /// Type 7.
    SetId {
        /// The ID the target was told to take.
        new: DeviceId,
    },
    /// Type 17.
    ParamRead,
    /// Type 18.
    ParamWrite,
    /// Type 24.
    Reporting(Reporting),
}

/// Why a frame can't be read.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum DecodeError {
    /// The ID doesn't fit in 29 bits, so it isn't an extended ID.
    #[error("ID {0:#X} is wider than 29 bits")]
    IdTooWide(u32),
    /// Every RobStride frame has 8 data bytes.
    #[error("{0} data bytes, expected 8")]
    BadLength(usize),
    /// Not a communication type in the manual.
    #[error("unknown communication type {0}")]
    UnknownType(u8),
    /// A save (22), baud rate (23) or protocol (25) frame: the host never sends one, so another sender is on the bus.
    #[error("communication type {0} is never sent by this host")]
    ForeignType(u8),
    /// The host field isn't this host's 0xFD.
    #[error("frame is for or from host {0:#04X}, not this host")]
    OtherHost(u8),
    /// A device ID outside 1 to 127.
    #[error("device ID {0} is outside 1 to 127")]
    BadDeviceId(u8),
    /// Status mode 3, which the manual doesn't define.
    #[error("status mode 3 is undefined")]
    ReservedMode,
    /// The data bytes aren't what the manual gives for this communication type.
    #[error("unexpected data for communication type {0}")]
    UnexpectedData(u8),
}

/// Reads one received frame.
///
/// # Errors
/// [`DecodeError`] naming what is wrong with the frame.
pub fn decode(id: u32, data: &[u8]) -> Result<Inbound, DecodeError> {
    let p = parts(id).ok_or(DecodeError::IdTooWide(id))?;
    let data: [u8; 8] = data
        .try_into()
        .map_err(|_| DecodeError::BadLength(data.len()))?;
    let drive_to_host = p.destination == HOST_ID;
    match p.kind {
        kind::GET_ID if p.destination == IDENTITY_MARKER => Ok(Inbound::Identity {
            device: device(p.area_lo)?,
            uid: Uid(data),
        }),
        kind::GET_ID => echo(&p, EchoKind::GetId, data == [0; 8]),
        kind::MIT => Ok(Inbound::Echo(Echo {
            kind: EchoKind::Mit,
            target: device(p.destination)?,
        })),
        kind::STATUS => {
            to_host(p.destination)?;
            let header = header(p.area_hi, p.area_lo)?;
            match data {
                // §4.1.4: the version reply's first three bytes. Byte 7 isn't described.
                [0x00, 0xC4, 0x56, v0, v1, v2, v3, _] => Ok(Inbound::Version {
                    header,
                    version: [v0, v1, v2, v3],
                }),
                _ => Ok(Inbound::Status(status(header, data))),
            }
        }
        kind::ENABLE => echo(&p, EchoKind::Enable, data == [0; 8]),
        kind::DISABLE => {
            let what = match data {
                [0, 0, 0, 0, 0, 0, 0, 0] => EchoKind::Disable,
                [1, 0, 0, 0, 0, 0, 0, 0] => EchoKind::FaultClear,
                VERSION_QUERY_DATA => EchoKind::VersionQuery,
                _ => return Err(DecodeError::UnexpectedData(kind::DISABLE)),
            };
            echo(&p, what, true)
        }
        kind::SET_ZERO => echo(&p, EchoKind::SetZero, data == SET_ZERO_DATA),
        kind::SET_ID => {
            let new = device(p.area_hi)?;
            echo(&p, EchoKind::SetId { new }, data == [0; 8])
        }
        kind::PARAM_READ if drive_to_host => {
            let [i0, i1, _, _, b4, b5, b6, b7] = data;
            let outcome = match p.area_hi {
                0 => ParamOutcome::Read([b4, b5, b6, b7]),
                1 => ParamOutcome::Refused,
                _ => return Err(DecodeError::UnexpectedData(kind::PARAM_READ)),
            };
            Ok(Inbound::Param {
                device: device(p.area_lo)?,
                index: u16::from_le_bytes([i0, i1]),
                outcome,
            })
        }
        kind::PARAM_READ => echo(&p, EchoKind::ParamRead, true),
        kind::PARAM_WRITE => echo(&p, EchoKind::ParamWrite, true),
        kind::FAULT => {
            to_host(p.destination)?;
            let [f0, f1, f2, f3, w0, w1, w2, w3] = data;
            Ok(Inbound::Fault {
                device: device(p.area_lo)?,
                faults: [f0, f1, f2, f3],
                warnings: [w0, w1, w2, w3],
            })
        }
        kind::REPORTING if drive_to_host => {
            Ok(Inbound::Report(status(header(p.area_hi, p.area_lo)?, data)))
        }
        kind::REPORTING => {
            let (prefix, rest) = data.split_at(REPORTING_PREFIX.len());
            let switch = match rest {
                [0, 0] => Reporting::Off,
                [1, 0] => Reporting::On,
                _ => return Err(DecodeError::UnexpectedData(kind::REPORTING)),
            };
            echo(&p, EchoKind::Reporting(switch), prefix == REPORTING_PREFIX)
        }
        kind::SAVE | kind::BAUD | kind::PROTOCOL => Err(DecodeError::ForeignType(p.kind)),
        other => Err(DecodeError::UnknownType(other)),
    }
}

/// A host frame read back: the host in data area bits 15..8, the target as destination, and data the manual allows.
fn echo(p: &crate::frame::Parts, kind: EchoKind, data_ok: bool) -> Result<Inbound, DecodeError> {
    if p.area_lo != HOST_ID {
        return Err(DecodeError::OtherHost(p.area_lo));
    }
    if !data_ok {
        return Err(DecodeError::UnexpectedData(p.kind));
    }
    Ok(Inbound::Echo(Echo {
        kind,
        target: device(p.destination)?,
    }))
}

const fn to_host(destination: u8) -> Result<(), DecodeError> {
    if destination == HOST_ID {
        Ok(())
    } else {
        Err(DecodeError::OtherHost(destination))
    }
}

fn device(id: u8) -> Result<DeviceId, DecodeError> {
    DeviceId::new(u64::from(id)).map_err(|_| DecodeError::BadDeviceId(id))
}

/// Mode from ID bits 23..22 and fault bits from 21..16 (`area_hi`), sender from bits 15..8 (`area_lo`).
fn header(area_hi: u8, area_lo: u8) -> Result<Header, DecodeError> {
    let mode = match area_hi >> 6 {
        0 => Mode::Reset,
        1 => Mode::Calibration,
        2 => Mode::Run,
        _ => return Err(DecodeError::ReservedMode),
    };
    Ok(Header {
        device: device(area_lo)?,
        mode,
        faults: StatusFaults(area_hi & 0x3F),
    })
}

fn status(header: Header, data: [u8; 8]) -> Status {
    let [p0, p1, v0, v1, t0, t1, c0, c1] = data;
    Status {
        header,
        position: u16::from_be_bytes([p0, p1]),
        velocity: u16::from_be_bytes([v0, v1]),
        torque: u16::from_be_bytes([t0, t1]),
        temperature: Celsius(f64::from(u16::from_be_bytes([c0, c1])) / 10.0),
    }
}
