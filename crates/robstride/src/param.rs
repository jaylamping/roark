//! The drive parameter table (manual §4.1.13), read with type 17 (§4.1.6) and written with type 18 (§4.1.7).
//!
//! The table is the same in the RS00, RS02, RS03 and RS04 manuals: same indexes, names and value types; only the ranges
//! differ by model. Index and value are little-endian. Every register can be read and decodes to a typed value. Only
//! [`Write`] builds a write, and it builds just the ones the host needs (PLAN items 2 and 6): `run_mode` MIT, `spd_ref`, the
//! three limits and `canTimeout`. There is no way to write `zero_sta` 0x7029, `damper` 0x702A or `add_offset` 0x702B.

use core::time::Duration;

use crate::encode::EncodeError;
use crate::model::Model;
use crate::units::{Amps, NewtonMeters, RadPerSec, RadPerSecSq, Radians, Volts};

/// One register of the §4.1.13 table, named as the manual names it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Param {
    /// 0x7005 `run_mode`, u8: 0 MIT ("operation"), 1 position (PP), 2 velocity, 3 current, 5 position (CSP).
    RunMode,
    /// 0x7006 `iq_ref`, f32 A: the current-mode Iq command.
    IqRef,
    /// 0x700A `spd_ref`, f32 rad/s: the velocity-mode speed command.
    SpdRef,
    /// 0x700B `limit_torque`, f32 N·m.
    LimitTorque,
    /// 0x7010 `cur_kp`, f32: current-loop Kp.
    CurKp,
    /// 0x7011 `cur_ki`, f32: current-loop Ki.
    CurKi,
    /// 0x7014 `cur_filt_gain`, f32, 0 to 1.
    CurFiltGain,
    /// 0x7016 `loc_ref`, f32 rad: the position-mode angle command.
    LocRef,
    /// 0x7017 `limit_spd`, f32 rad/s: the CSP speed limit.
    LimitSpd,
    /// 0x7018 `limit_cur`, f32 A: the velocity and position mode current limit.
    LimitCur,
    /// 0x7019 `mechPos`, f32 rad, read-only: the output's mechanical angle.
    MechPos,
    /// 0x701A `iqf`, f32 A, read-only: filtered Iq.
    Iqf,
    /// 0x701B `mechVel`, f32 rad/s, read-only: the output's speed.
    MechVel,
    /// 0x701C `VBUS`, f32 V, read-only: bus voltage.
    Vbus,
    /// 0x701E `loc_kp`, f32: position-loop Kp.
    LocKp,
    /// 0x701F `spd_kp`, f32: speed-loop Kp.
    SpdKp,
    /// 0x7020 `spd_ki`, f32: speed-loop Ki.
    SpdKi,
    /// 0x7021 `spd_filt_gain`, f32: speed filter gain.
    SpdFiltGain,
    /// 0x7022 `acc_rad`, f32 rad/s²: velocity-mode acceleration.
    AccRad,
    /// 0x7024 `vel_max`, f32 rad/s: PP-mode speed.
    VelMax,
    /// 0x7025 `acc_set`, f32 rad/s²: PP-mode acceleration.
    AccSet,
    /// 0x7026 `EPScan_time`, u16: the active-report interval; 1 is 10 ms and each step adds 5 ms.
    EpScanTime,
    /// 0x7028 `canTimeout`, u32: the CAN timeout in 50 µs steps (20000 is 1 s), 0 off.
    CanTimeout,
    /// 0x7029 `zero_sta`, u8: the power-on position window, 0 for 0 to 2π, 1 for −π to π. Never written (PLAN item 2).
    ZeroSta,
    /// 0x702A `damper`, u8 switch. Never written (PLAN item 6).
    Damper,
    /// 0x702B `add_offset`, f32 rad: zero offset. Never written (PLAN item 2).
    AddOffset,
    /// 0x702C `alveolous_open`, u8 switch: cogging compensation.
    CoggingCompensation,
    /// 0x702D `iq_test`, u8 switch: motor initialization calibration.
    IqTest,
    /// 0x702E `dcc_set`, f32 rad/s²: PP-mode deceleration.
    DccSet,
}

/// A register's value type on the wire (§4.1.13 "Type").
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ParamType {
    /// One byte, in data byte 4.
    U8,
    /// Two bytes, in data bytes 4 and 5.
    U16,
    /// Four bytes, in data bytes 4 to 7.
    U32,
    /// An IEEE 754 single, in data bytes 4 to 7.
    F32,
}

/// What a register's value means, which picks its [`ParamValue`] variant and its [`ParamType`].
#[derive(Clone, Copy)]
enum Class {
    RunMode,
    ZeroSta,
    Switch,
    ReportTicks,
    CanTimeout,
    Amps,
    RadPerSec,
    NewtonMeters,
    Radians,
    RadPerSecSq,
    Volts,
    Gain,
}

impl Param {
    /// Every register, in table order.
    pub const ALL: [Self; 29] = [
        Self::RunMode,
        Self::IqRef,
        Self::SpdRef,
        Self::LimitTorque,
        Self::CurKp,
        Self::CurKi,
        Self::CurFiltGain,
        Self::LocRef,
        Self::LimitSpd,
        Self::LimitCur,
        Self::MechPos,
        Self::Iqf,
        Self::MechVel,
        Self::Vbus,
        Self::LocKp,
        Self::SpdKp,
        Self::SpdKi,
        Self::SpdFiltGain,
        Self::AccRad,
        Self::VelMax,
        Self::AccSet,
        Self::EpScanTime,
        Self::CanTimeout,
        Self::ZeroSta,
        Self::Damper,
        Self::AddOffset,
        Self::CoggingCompensation,
        Self::IqTest,
        Self::DccSet,
    ];

    /// The register's index, 0x70xx.
    #[must_use]
    pub const fn index(self) -> u16 {
        match self {
            Self::RunMode => 0x7005,
            Self::IqRef => 0x7006,
            Self::SpdRef => 0x700A,
            Self::LimitTorque => 0x700B,
            Self::CurKp => 0x7010,
            Self::CurKi => 0x7011,
            Self::CurFiltGain => 0x7014,
            Self::LocRef => 0x7016,
            Self::LimitSpd => 0x7017,
            Self::LimitCur => 0x7018,
            Self::MechPos => 0x7019,
            Self::Iqf => 0x701A,
            Self::MechVel => 0x701B,
            Self::Vbus => 0x701C,
            Self::LocKp => 0x701E,
            Self::SpdKp => 0x701F,
            Self::SpdKi => 0x7020,
            Self::SpdFiltGain => 0x7021,
            Self::AccRad => 0x7022,
            Self::VelMax => 0x7024,
            Self::AccSet => 0x7025,
            Self::EpScanTime => 0x7026,
            Self::CanTimeout => 0x7028,
            Self::ZeroSta => 0x7029,
            Self::Damper => 0x702A,
            Self::AddOffset => 0x702B,
            Self::CoggingCompensation => 0x702C,
            Self::IqTest => 0x702D,
            Self::DccSet => 0x702E,
        }
    }

    /// The register's value type on the wire.
    #[must_use]
    pub const fn value_type(self) -> ParamType {
        match self.class() {
            Class::RunMode | Class::ZeroSta | Class::Switch => ParamType::U8,
            Class::ReportTicks => ParamType::U16,
            Class::CanTimeout => ParamType::U32,
            Class::Amps
            | Class::RadPerSec
            | Class::NewtonMeters
            | Class::Radians
            | Class::RadPerSecSq
            | Class::Volts
            | Class::Gain => ParamType::F32,
        }
    }

    /// The register with this index, if the table has one.
    pub(crate) fn from_index(index: u16) -> Option<Self> {
        Self::ALL.into_iter().find(|p| p.index() == index)
    }

    const fn class(self) -> Class {
        match self {
            Self::RunMode => Class::RunMode,
            Self::ZeroSta => Class::ZeroSta,
            Self::Damper | Self::CoggingCompensation | Self::IqTest => Class::Switch,
            Self::EpScanTime => Class::ReportTicks,
            Self::CanTimeout => Class::CanTimeout,
            Self::IqRef | Self::LimitCur | Self::Iqf => Class::Amps,
            Self::SpdRef | Self::LimitSpd | Self::MechVel | Self::VelMax => Class::RadPerSec,
            Self::LimitTorque => Class::NewtonMeters,
            Self::LocRef | Self::MechPos | Self::AddOffset => Class::Radians,
            Self::AccRad | Self::AccSet | Self::DccSet => Class::RadPerSecSq,
            Self::Vbus => Class::Volts,
            Self::CurKp
            | Self::CurKi
            | Self::CurFiltGain
            | Self::LocKp
            | Self::SpdKp
            | Self::SpdKi
            | Self::SpdFiltGain => Class::Gain,
        }
    }
}

/// `run_mode` 0x7005 (§4.1.13). Value 4 isn't listed and is refused on read.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RunMode {
    /// 0: MIT, which the manual calls "operation mode". The only mode the host writes.
    Mit,
    /// 1: position mode (PP).
    Position,
    /// 2: velocity mode.
    Velocity,
    /// 3: current mode.
    Current,
    /// 5: position mode (CSP).
    Csp,
}

impl RunMode {
    const fn from_byte(byte: u8) -> Option<Self> {
        match byte {
            0 => Some(Self::Mit),
            1 => Some(Self::Position),
            2 => Some(Self::Velocity),
            3 => Some(Self::Current),
            5 => Some(Self::Csp),
            _ => None,
        }
    }
}

/// `zero_sta` 0x7029: the window the drive reports position in after power-on (§4.1.13, §4.2.2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ZeroSta {
    /// 0, the default: 0 to 2π.
    ZeroToTwoPi,
    /// 1: −π to π.
    MinusPiToPi,
}

/// `canTimeout` 0x7028: how long the drive waits without a frame before it drops to reset, in 50 µs steps (§4.1.13:
/// "20000 is 1s"). 0 turns it off, the drive's default.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CanTimeout(u32);

impl CanTimeout {
    /// 0: no timeout.
    pub const OFF: Self = Self(0);

    /// A timeout of `ticks` × 50 µs.
    #[must_use]
    pub const fn from_ticks(ticks: u32) -> Self {
        Self(ticks)
    }

    /// The register value, in 50 µs steps.
    #[must_use]
    pub const fn ticks(self) -> u32 {
        self.0
    }

    /// The timeout as a span; zero means off.
    #[must_use]
    pub fn duration(self) -> Duration {
        Duration::from_micros(u64::from(self.0) * 50)
    }
}

/// A register's value, in SI where the register has a unit.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ParamValue {
    /// `run_mode`.
    RunMode(RunMode),
    /// `zero_sta`.
    ZeroSta(ZeroSta),
    /// A u8 switch (`damper`, `alveolous_open`, `iq_test`): 0 off, 1 on.
    Switch(bool),
    /// `EPScan_time`: 1 is 10 ms, each step adds 5 ms.
    ReportTicks(u16),
    /// `canTimeout`.
    CanTimeout(CanTimeout),
    /// A current.
    Amps(Amps),
    /// An angular velocity.
    RadPerSec(RadPerSec),
    /// A torque.
    NewtonMeters(NewtonMeters),
    /// An angle.
    Radians(Radians),
    /// An angular acceleration.
    RadPerSecSq(RadPerSecSq),
    /// A voltage.
    Volts(Volts),
    /// A loop gain or filter gain, in the drive's own units, which the manual doesn't give.
    Gain(f64),
}

/// The value data bytes 4 to 7 carry for `param`, or `None` if they aren't one: a 1- or 2-byte value with its unused bytes
/// set, an enum value the manual doesn't list, or a float that isn't finite.
pub(crate) fn decode_value(param: Param, bytes: [u8; 4]) -> Option<ParamValue> {
    let one_byte = match bytes {
        [b, 0, 0, 0] => Some(b),
        _ => None,
    };
    let float = f64::from(f32::from_le_bytes(bytes));
    let float = float.is_finite().then_some(float);
    Some(match param.class() {
        Class::RunMode => ParamValue::RunMode(RunMode::from_byte(one_byte?)?),
        Class::ZeroSta => ParamValue::ZeroSta(match one_byte? {
            0 => ZeroSta::ZeroToTwoPi,
            1 => ZeroSta::MinusPiToPi,
            _ => return None,
        }),
        Class::Switch => ParamValue::Switch(match one_byte? {
            0 => false,
            1 => true,
            _ => return None,
        }),
        Class::ReportTicks => match bytes {
            [b0, b1, 0, 0] => ParamValue::ReportTicks(u16::from_le_bytes([b0, b1])),
            _ => return None,
        },
        Class::CanTimeout => ParamValue::CanTimeout(CanTimeout(u32::from_le_bytes(bytes))),
        Class::Amps => ParamValue::Amps(Amps(float?)),
        Class::RadPerSec => ParamValue::RadPerSec(RadPerSec(float?)),
        Class::NewtonMeters => ParamValue::NewtonMeters(NewtonMeters(float?)),
        Class::Radians => ParamValue::Radians(Radians(float?)),
        Class::RadPerSecSq => ParamValue::RadPerSecSq(RadPerSecSq(float?)),
        Class::Volts => ParamValue::Volts(Volts(float?)),
        Class::Gain => ParamValue::Gain(float?),
    })
}

/// A parameter write the host may send, checked against the model when it is built. Its value is held as the drive
/// will store it, rounded to f32, so it equals what a read-back of the register decodes to.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Write {
    param: Param,
    value: ParamValue,
    bytes: [u8; 4],
}

impl Write {
    /// `run_mode` = 0, MIT: the last step of enabling a drive (PLAN item 2).
    #[must_use]
    pub const fn mit_mode() -> Self {
        Self {
            param: Param::RunMode,
            value: ParamValue::RunMode(RunMode::Mit),
            bytes: [0; 4],
        }
    }

    /// `canTimeout` (PLAN item 6 writes 1000, 50 ms).
    #[must_use]
    pub const fn can_timeout(timeout: CanTimeout) -> Self {
        Self {
            param: Param::CanTimeout,
            value: ParamValue::CanTimeout(timeout),
            bytes: timeout.0.to_le_bytes(),
        }
    }

    /// `spd_ref`, within ± the model's speed cap ([`Model::ranges`]), which is no wider than the manual's `spd_ref` range.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn spd_ref(model: Model, speed: RadPerSec) -> Result<Self, EncodeError> {
        let max = model.ranges().speed_max.get();
        float(Param::SpdRef, speed.get(), -max, max, |v| {
            ParamValue::RadPerSec(RadPerSec(v))
        })
    }

    /// `limit_torque`, 0 to the model's torque cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_torque(model: Model, torque: NewtonMeters) -> Result<Self, EncodeError> {
        let max = model.ranges().torque_max.get();
        float(Param::LimitTorque, torque.get(), 0.0, max, |v| {
            ParamValue::NewtonMeters(NewtonMeters(v))
        })
    }

    /// `limit_spd`, 0 to the model's speed cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_spd(model: Model, speed: RadPerSec) -> Result<Self, EncodeError> {
        let max = model.ranges().speed_max.get();
        float(Param::LimitSpd, speed.get(), 0.0, max, |v| {
            ParamValue::RadPerSec(RadPerSec(v))
        })
    }

    /// `limit_cur`, 0 to the model's current cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_cur(model: Model, current: Amps) -> Result<Self, EncodeError> {
        let max = model.ranges().current_max.get();
        float(Param::LimitCur, current.get(), 0.0, max, |v| {
            ParamValue::Amps(Amps(v))
        })
    }

    /// The register written.
    #[must_use]
    pub const fn param(&self) -> Param {
        self.param
    }

    /// The value written, as a read-back decodes it.
    #[must_use]
    pub const fn value(&self) -> ParamValue {
        self.value
    }

    /// Data bytes 4 to 7.
    pub(crate) const fn bytes(&self) -> [u8; 4] {
        self.bytes
    }

    /// Whether a write of `value` to `param` is one [`Write`] could have built, ranges aside: the test a write read back
    /// from the bus must pass to be this host's.
    pub(crate) const fn could_build(param: Param, value: ParamValue) -> bool {
        matches!(
            (param, value),
            (Param::RunMode, ParamValue::RunMode(RunMode::Mit))
                | (Param::CanTimeout, ParamValue::CanTimeout(_))
                | (Param::SpdRef | Param::LimitSpd, ParamValue::RadPerSec(_))
                | (Param::LimitTorque, ParamValue::NewtonMeters(_))
                | (Param::LimitCur, ParamValue::Amps(_))
        )
    }
}

/// A float write, refused outside `min` to `max` and otherwise rounded to the nearest f32.
fn float(
    param: Param,
    value: f64,
    min: f64,
    max: f64,
    wrap: fn(f64) -> ParamValue,
) -> Result<Write, EncodeError> {
    if !value.is_finite() || !(min..=max).contains(&value) {
        return Err(EncodeError::ParamOutOfRange {
            param,
            value,
            min,
            max,
        });
    }
    // Every bound is an integer, so exact in f32, and rounding is monotone: a value inside the bounds stays inside them.
    #[expect(
        clippy::as_conversions,
        clippy::cast_possible_truncation,
        reason = "value is finite and within ±120 (the largest cap), so this only rounds it to the nearest f32"
    )]
    let single = value as f32;
    Ok(Write {
        param,
        value: wrap(f64::from(single)),
        bytes: single.to_le_bytes(),
    })
}
