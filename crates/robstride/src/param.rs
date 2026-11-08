//! The drive parameter table (manual §4.1.13), read with type 17 (§4.1.6) and written with type 18 (§4.1.7).
//!
//! The table is the same in the RS00, RS02, RS03 and RS04 manuals: same indexes, names and value types; only the ranges
//! differ by model. Index and value are little-endian. Every register can be read and decodes to a typed value. Only
//! [`Write`] builds a write, and it builds just the ones the host needs (PLAN items 2 and 6): `run_mode` MIT, `spd_ref`, the
//! three limits and `canTimeout`. There is no way to write `zero_sta` 0x7029, `damper` 0x702A or `add_offset` 0x702B.

use core::time::Duration;

use crate::encode::EncodeError;
use crate::model::{Drive, Model};
use crate::units::{Amps, DeviceId, Gain, NewtonMeters, RadPerSec, RadPerSecSq, Radians, Volts};

/// The §4.1.13 table, one row per register: its name, index and what its value means. Every list of registers ([`Param`],
/// [`Param::ALL`], [`Param::index`], `from_index`, `class`) comes from these rows, so no list can miss one.
macro_rules! param_table {
    ($($(#[$doc:meta])* $name:ident = $index:literal, $class:ident;)*) => {
        /// One register of the §4.1.13 table, named as the manual names it.
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
        pub enum Param {
            $($(#[$doc])* $name,)*
        }

        impl Param {
            /// Every register, in table order.
            pub const ALL: [Self; [$(Self::$name),*].len()] = [$(Self::$name),*];

            /// The register's index, 0x70xx.
            #[must_use]
            pub const fn index(self) -> u16 {
                match self {
                    $(Self::$name => $index,)*
                }
            }

            /// The register with this index, if the table has one.
            pub(crate) const fn from_index(index: u16) -> Option<Self> {
                match index {
                    $($index => Some(Self::$name),)*
                    _ => None,
                }
            }

            const fn class(self) -> Class {
                match self {
                    $(Self::$name => Class::$class,)*
                }
            }
        }
    };
}

param_table! {
    /// 0x7005 `run_mode`, u8: 0 MIT ("operation"), 1 position (PP), 2 velocity, 3 current, 5 position (CSP).
    RunMode = 0x7005, RunMode;
    /// 0x7006 `iq_ref`, f32 A: the current-mode Iq command.
    IqRef = 0x7006, Amps;
    /// 0x700A `spd_ref`, f32 rad/s: the velocity-mode speed command.
    SpdRef = 0x700A, RadPerSec;
    /// 0x700B `limit_torque`, f32 N·m.
    LimitTorque = 0x700B, NewtonMeters;
    /// 0x7010 `cur_kp`, f32: current-loop Kp.
    CurKp = 0x7010, Gain;
    /// 0x7011 `cur_ki`, f32: current-loop Ki.
    CurKi = 0x7011, Gain;
    /// 0x7014 `cur_filt_gain`, f32, 0 to 1 in the manual (not checked on read).
    CurFiltGain = 0x7014, Gain;
    /// 0x7016 `loc_ref`, f32 rad: the position-mode angle command.
    LocRef = 0x7016, Radians;
    /// 0x7017 `limit_spd`, f32 rad/s: the CSP speed limit.
    LimitSpd = 0x7017, RadPerSec;
    /// 0x7018 `limit_cur`, f32 A: the velocity and position mode current limit.
    LimitCur = 0x7018, Amps;
    /// 0x7019 `mechPos`, f32 rad, read-only: the output's mechanical angle.
    MechPos = 0x7019, Radians;
    /// 0x701A `iqf`, f32 A, read-only: filtered Iq.
    Iqf = 0x701A, Amps;
    /// 0x701B `mechVel`, f32 rad/s, read-only: the output's speed.
    MechVel = 0x701B, RadPerSec;
    /// 0x701C `VBUS`, f32 V, read-only: bus voltage.
    Vbus = 0x701C, Volts;
    /// 0x701E `loc_kp`, f32: position-loop Kp.
    LocKp = 0x701E, Gain;
    /// 0x701F `spd_kp`, f32: speed-loop Kp.
    SpdKp = 0x701F, Gain;
    /// 0x7020 `spd_ki`, f32: speed-loop Ki.
    SpdKi = 0x7020, Gain;
    /// 0x7021 `spd_filt_gain`, f32: speed filter gain.
    SpdFiltGain = 0x7021, Gain;
    /// 0x7022 `acc_rad`, f32 rad/s²: velocity-mode acceleration.
    AccRad = 0x7022, RadPerSecSq;
    /// 0x7024 `vel_max`, f32 rad/s: PP-mode speed.
    VelMax = 0x7024, RadPerSec;
    /// 0x7025 `acc_set`, f32 rad/s²: PP-mode acceleration.
    AccSet = 0x7025, RadPerSecSq;
    /// 0x7026 `EPScan_time`, u16: the active-report interval; 1 is 10 ms and each step adds 5 ms.
    EpScanTime = 0x7026, ReportTicks;
    /// 0x7028 `canTimeout`, u32: the CAN timeout in 50 µs steps (20000 is 1 s), 0 off.
    CanTimeout = 0x7028, CanTimeout;
    /// 0x7029 `zero_sta`, u8: the power-on position window, 0 for 0 to 2π, 1 for −π to π. Never written (PLAN item 2).
    ZeroSta = 0x7029, ZeroSta;
    /// 0x702A `damper`, u8: 0 keeps the post-power-off anti-backdrive protection on. Never written (PLAN item 6).
    Damper = 0x702A, Damper;
    /// 0x702B `add_offset`, f32 rad: zero offset. Never written (PLAN item 2).
    AddOffset = 0x702B, Radians;
    /// 0x702C `alveolous_open`, u8 switch: cogging compensation.
    CoggingCompensation = 0x702C, Switch;
    /// 0x702D `iq_test`, u8 switch: motor initialization calibration.
    IqTest = 0x702D, Switch;
    /// 0x702E `dcc_set`, f32 rad/s²: PP-mode deceleration.
    DccSet = 0x702E, RadPerSecSq;
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
    Damper,
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
    /// The register's value type on the wire.
    #[must_use]
    pub const fn value_type(self) -> ParamType {
        match self.class() {
            Class::RunMode | Class::ZeroSta | Class::Damper | Class::Switch => ParamType::U8,
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

/// `damper` 0x702A (PLAN item 6): the post-power-off anti-backdrive protection. The register is a disable flag, so 0 is
/// protection on. Read only; preflight refuses enable unless it reads [`Damper::ProtectionOn`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Damper {
    /// 0, the drive's default: the protection is on.
    ProtectionOn,
    /// 1: the protection is off.
    ProtectionOff,
}

/// `EPScan_time` 0x7026: the active-report interval, in the drive's steps (1 is 10 ms, each step adds 5 ms).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ReportInterval(u16);

impl ReportInterval {
    /// An interval of `ticks` steps.
    #[must_use]
    pub const fn from_ticks(ticks: u16) -> Self {
        Self(ticks)
    }

    /// The register value.
    #[must_use]
    pub const fn ticks(self) -> u16 {
        self.0
    }

    /// The interval as a span, or `None` for 0, which the manual doesn't define.
    #[must_use]
    pub fn duration(self) -> Option<Duration> {
        let steps = u64::from(self.0.checked_sub(1)?);
        Some(Duration::from_millis(10 + 5 * steps))
    }
}

/// `canTimeout` 0x7028: how long the drive waits without a frame before it drops to reset, in 50 µs steps (§4.1.13:
/// "20000 is 1s"). 0 turns it off, the drive's default.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CanTimeout(u32);

impl CanTimeout {
    /// 0: no timeout. A drive reads this after a reboot; the host never writes it.
    pub const OFF: Self = Self(0);

    /// 1000, 50 ms: the one value the host writes and preflight accepts (PLAN item 6).
    pub const RUNTIME: Self = Self(1000);

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

    /// The timeout as a span, or `None` for [`CanTimeout::OFF`]: no timeout at all, never an immediate one.
    #[must_use]
    pub fn duration(self) -> Option<Duration> {
        (self.0 != 0).then(|| Duration::from_micros(u64::from(self.0) * 50))
    }
}

/// A register's value, in SI where the register has a unit.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ParamValue {
    /// `run_mode`.
    RunMode(RunMode),
    /// `zero_sta`.
    ZeroSta(ZeroSta),
    /// `damper`.
    Damper(Damper),
    /// A u8 switch (`cogging_compensation`, `iq_test`): 0 off, 1 on.
    Switch(bool),
    /// `EPScan_time`.
    ReportInterval(ReportInterval),
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
    /// A loop or filter gain.
    Gain(Gain),
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
        Class::Damper => ParamValue::Damper(match one_byte? {
            0 => Damper::ProtectionOn,
            1 => Damper::ProtectionOff,
            _ => return None,
        }),
        Class::Switch => ParamValue::Switch(match one_byte? {
            0 => false,
            1 => true,
            _ => return None,
        }),
        Class::ReportTicks => match bytes {
            [b0, b1, 0, 0] => {
                ParamValue::ReportInterval(ReportInterval(u16::from_le_bytes([b0, b1])))
            }
            _ => return None,
        },
        Class::CanTimeout => ParamValue::CanTimeout(CanTimeout(u32::from_le_bytes(bytes))),
        Class::Amps => ParamValue::Amps(Amps(float?)),
        Class::RadPerSec => ParamValue::RadPerSec(RadPerSec(float?)),
        Class::NewtonMeters => ParamValue::NewtonMeters(NewtonMeters(float?)),
        Class::Radians => ParamValue::Radians(Radians(float?)),
        Class::RadPerSecSq => ParamValue::RadPerSecSq(RadPerSecSq(float?)),
        Class::Volts => ParamValue::Volts(Volts(float?)),
        Class::Gain => ParamValue::Gain(Gain(float?)),
    })
}

/// A parameter write the host may send, to one drive. Its constructors are the only writes there are: `run_mode` MIT,
/// `canTimeout` 1000, `spd_ref` 0, and the three limits checked against the drive's model. A float value is held as the
/// drive will store it, rounded to f32, so it equals what a read-back of the register decodes to.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Write {
    target: DeviceId,
    body: Body,
}

impl Write {
    /// `run_mode` = 0, MIT: the last step of enabling a drive (PLAN item 2).
    #[must_use]
    pub const fn mit_mode(drive: Drive) -> Self {
        Self::to(drive, Body::MIT_MODE)
    }

    /// `canTimeout` = [`CanTimeout::RUNTIME`], 50 ms (PLAN item 6). No other timeout can be written, so the host can't
    /// turn the drive's host-loss timeout off.
    #[must_use]
    pub const fn can_timeout(drive: Drive) -> Self {
        Self::to(drive, Body::CAN_TIMEOUT)
    }

    /// `spd_ref` = 0, the Stop pre-step (PLAN, "`SpeedTarget` 0x700A = 0"). The host writes no other speed target: it only
    /// ever puts a drive in MIT mode, where `spd_ref` does nothing.
    #[must_use]
    pub const fn speed_target_zero(drive: Drive) -> Self {
        Self::to(drive, Body::SPEED_TARGET_ZERO)
    }

    /// `limit_torque`, 0 to the drive's torque cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_torque(drive: Drive, torque: NewtonMeters) -> Result<Self, EncodeError> {
        Body::cap(Cap::Torque, drive.model(), torque.get()).map(|body| Self::to(drive, body))
    }

    /// `limit_spd`, 0 to the drive's speed cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_spd(drive: Drive, speed: RadPerSec) -> Result<Self, EncodeError> {
        Body::cap(Cap::Speed, drive.model(), speed.get()).map(|body| Self::to(drive, body))
    }

    /// `limit_cur`, 0 to the drive's current cap.
    ///
    /// # Errors
    /// [`EncodeError::ParamOutOfRange`] outside that.
    pub fn limit_cur(drive: Drive, current: Amps) -> Result<Self, EncodeError> {
        Body::cap(Cap::Current, drive.model(), current.get()).map(|body| Self::to(drive, body))
    }

    const fn to(drive: Drive, body: Body) -> Self {
        Self {
            target: drive.id(),
            body,
        }
    }

    /// The drive it is for.
    #[must_use]
    pub const fn target(&self) -> DeviceId {
        self.target
    }

    /// The register written.
    #[must_use]
    pub const fn param(&self) -> Param {
        self.body.param
    }

    /// The value written, as a read-back decodes it.
    #[must_use]
    pub const fn value(&self) -> ParamValue {
        self.body.value
    }

    /// Data bytes 4 to 7.
    pub(crate) const fn bytes(&self) -> [u8; 4] {
        self.body.bytes
    }
}

/// What a [`Write`] writes, whichever drive it goes to.
#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Body {
    param: Param,
    value: ParamValue,
    bytes: [u8; 4],
}

/// The three host-set limits.
#[derive(Clone, Copy)]
enum Cap {
    Torque,
    Speed,
    Current,
}

impl Body {
    const MIT_MODE: Self = Self {
        param: Param::RunMode,
        value: ParamValue::RunMode(RunMode::Mit),
        bytes: [0; 4],
    };
    const CAN_TIMEOUT: Self = Self {
        param: Param::CanTimeout,
        value: ParamValue::CanTimeout(CanTimeout::RUNTIME),
        bytes: CanTimeout::RUNTIME.0.to_le_bytes(),
    };
    const SPEED_TARGET_ZERO: Self = Self {
        param: Param::SpdRef,
        value: ParamValue::RadPerSec(RadPerSec(0.0)),
        bytes: [0; 4],
    };

    /// The value written, as a read-back decodes it.
    pub(crate) const fn value(self) -> ParamValue {
        self.value
    }

    /// A limit of `value`, refused outside 0 to the model's cap and otherwise rounded to the nearest f32.
    fn cap(cap: Cap, model: Model, value: f64) -> Result<Self, EncodeError> {
        let r = model.ranges();
        let (param, max, wrap): (Param, f64, fn(f64) -> ParamValue) = match cap {
            Cap::Torque => (Param::LimitTorque, r.torque_max.get(), |v| {
                ParamValue::NewtonMeters(NewtonMeters(v))
            }),
            Cap::Speed => (Param::LimitSpd, r.speed_max.get(), |v| {
                ParamValue::RadPerSec(RadPerSec(v))
            }),
            Cap::Current => (Param::LimitCur, r.current_max.get(), |v| {
                ParamValue::Amps(Amps(v))
            }),
        };
        if !value.is_finite() || !(0.0..=max).contains(&value) {
            return Err(EncodeError::ParamOutOfRange {
                param,
                value,
                min: 0.0,
                max,
            });
        }
        // Every bound is an integer, so exact in f32, and rounding is monotone: a value inside the bounds stays inside.
        #[expect(
            clippy::as_conversions,
            clippy::cast_possible_truncation,
            reason = "value is finite and within 0 to 120 (the largest cap), so this only rounds it to the nearest f32"
        )]
        // + 0.0 turns −0.0 into +0.0, so a reversed joint's zero is the same write as any other zero.
        let single = value as f32 + 0.0;
        Ok(Self {
            param,
            value: wrap(f64::from(single)),
            bytes: single.to_le_bytes(),
        })
    }

    /// How this host writes `param`, or `None` if it never does: a check that takes a write's value bytes and returns
    /// what was written, if this host could have sent them. The one list of what the host writes.
    ///
    /// A cap passes if some model's limit is exactly those bytes; which drive and model the target is, the bus layer
    /// checks by matching the echo against the frame it queued.
    pub(crate) fn writer(param: Param) -> Option<fn([u8; 4]) -> Option<Self>> {
        Some(match param {
            Param::RunMode => |b| Self::MIT_MODE.exactly(b),
            Param::CanTimeout => |b| Self::CAN_TIMEOUT.exactly(b),
            Param::SpdRef => |b| Self::SPEED_TARGET_ZERO.exactly(b),
            Param::LimitTorque => |b| Self::any_model(Cap::Torque, b),
            Param::LimitSpd => |b| Self::any_model(Cap::Speed, b),
            Param::LimitCur => |b| Self::any_model(Cap::Current, b),
            // Read-only, or never written by this host (PLAN items 2 and 6).
            Param::IqRef
            | Param::CurKp
            | Param::CurKi
            | Param::CurFiltGain
            | Param::LocRef
            | Param::MechPos
            | Param::Iqf
            | Param::MechVel
            | Param::Vbus
            | Param::LocKp
            | Param::SpdKp
            | Param::SpdKi
            | Param::SpdFiltGain
            | Param::AccRad
            | Param::VelMax
            | Param::AccSet
            | Param::EpScanTime
            | Param::ZeroSta
            | Param::Damper
            | Param::AddOffset
            | Param::CoggingCompensation
            | Param::IqTest
            | Param::DccSet => return None,
        })
    }

    /// This write, if it carries exactly `bytes`.
    fn exactly(self, bytes: [u8; 4]) -> Option<Self> {
        (self.bytes == bytes).then_some(self)
    }

    /// The limit some model accepts from the f32 in `bytes`, if it carries exactly `bytes`: −0.0, which the host never
    /// sends, fails here because the built limit holds +0.0.
    fn any_model(cap: Cap, bytes: [u8; 4]) -> Option<Self> {
        let value = f64::from(f32::from_le_bytes(bytes));
        Model::ALL
            .into_iter()
            .find_map(|model| Self::cap(cap, model, value).ok())
            .filter(|body| body.bytes == bytes)
    }
}
