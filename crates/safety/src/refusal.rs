//! Why preflight refused a drive, and what the operator reads about it (safety.md section 5): the rule, the joint, what
//! was measured, what was expected, and what to do.

use can::{SlowRefusal, StopReason, Unsent};
use robstride::{CanTimeout, Mode, Model, ParamValue, StatusFaults, Uid, Volts};
use skeleton::Window;

use crate::preflight::{Exchange, Register};
use crate::rule::RuleId;
use crate::seen::DriveAddress;

/// A cap the skeleton gives each joint.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CapKind {
    /// `torque_cap_nm`, written to `limit_torque`.
    Torque,
    /// `current_cap_a`, written to `limit_cur`.
    Current,
    /// `speed_cap_rad_s`, written to `limit_spd`.
    Speed,
}

impl CapKind {
    /// The skeleton field.
    #[must_use]
    pub const fn field(self) -> &'static str {
        match self {
            Self::Torque => "torque_cap_nm",
            Self::Current => "current_cap_a",
            Self::Speed => "speed_cap_rad_s",
        }
    }
}

/// A joint fact the skeleton holds only once it is verified on the hardware (PLAN item 1).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum JointFact {
    /// `direction`, set after the sign check.
    Direction,
    /// `zero_rad`, set after referencing (PLAN item 1, Zero convention).
    Zero,
    /// `hard_rad`, the joint's hard limits inside its physical stops.
    HardLimits,
}

impl JointFact {
    /// The skeleton field.
    #[must_use]
    pub const fn field(self) -> &'static str {
        match self {
            Self::Direction => "direction",
            Self::Zero => "zero_rad",
            Self::HardLimits => "hard_rad",
        }
    }
}

/// How a request went unanswered.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Unanswered {
    /// No result within its window: the bus timed it out, or no result came back within
    /// [`crate::ANSWER_WITHIN_NS`].
    TimedOut,
    /// A result came, but control handed it over after [`crate::ANSWER_WITHIN_NS`]: the runtime fell behind.
    Late,
    /// The bus didn't send it: the socket didn't take it, or it expired queued.
    NotSent(Unsent),
    /// The bus layer refused it.
    Refused(SlowRefusal),
    /// The drive answered a read with "can't read it".
    ReadRefused,
    /// An answer of another kind, or a value of another type, than the request asks for.
    WrongAnswer,
}

/// Why preflight refused a drive. Each names what was measured and what was expected; [`Refusal::message`] says it for
/// the operator, with the joint, and [`Refusal::remedy`] what to do.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Refusal {
    /// The skeleton has no value for this cap: null is not permission (PLAN item 1).
    CapUnset(CapKind),
    /// The skeleton's cap is outside what the drive's model can be set to (0 to `max`).
    CapOutOfRange {
        /// The cap.
        cap: CapKind,
        /// The skeleton's value.
        value: f64,
        /// The model's highest.
        max: f64,
    },
    /// The skeleton has no verified value for this fact: unverified is null, and null refuses enable (tenets, fail
    /// closed).
    FactUnset(JointFact),
    /// The joint has no bus: it is offline and can't be enabled.
    Unwired,
    /// The joint's drive model has no settled MIT scales, so control can't command it.
    UnvouchedModel(Model),
    /// Preflight was handed another drive's view, by ID or by bus: a runtime bug.
    WrongView {
        /// The view's drive.
        view: DriveAddress,
        /// Preflight's drive.
        drive: DriveAddress,
    },
    /// The drive's limb is enabled: preflight writes only to a drive of an idle limb, and the bus refuses the rest.
    LimbActive,
    /// The drive's limb is stopping or stopped, or was cleared, since preflight began: the checks so far may predate
    /// the stop and say nothing about the drive after it.
    LimbStopped {
        /// Why the limb stopped, if the snapshot still says.
        stop: Option<StopReason>,
    },
    /// A request got no usable answer.
    NoAnswer {
        /// The request.
        exchange: Exchange,
        /// What happened instead.
        how: Unanswered,
    },
    /// The drive's UID isn't the skeleton's.
    Uid {
        /// What it said.
        read: Uid,
        /// What the skeleton says.
        expected: Uid,
    },
    /// `canTimeout` read back other than 1000.
    CanTimeout {
        /// What it read.
        read: CanTimeout,
    },
    /// A cap read back other than written.
    Cap {
        /// The register.
        register: Register,
        /// What was written.
        written: ParamValue,
        /// What it read.
        read: ParamValue,
    },
    /// The damper reads 1: the anti-backdrive protection is off.
    DamperOff,
    /// VBUS outside the skeleton's window.
    Vbus {
        /// What it read.
        read: Volts,
        /// The window.
        window: Window<Volts>,
    },
    /// The latest status since preflight began carried fault bits.
    Faults {
        /// The bits.
        bits: StatusFaults,
    },
    /// A fault was seen since start or the limb's last clear, and the latest status shows none (fault bits clear only
    /// by power-cycling the drive, then a clear).
    FaultSeen,
    /// A status or status header (a version reply's included) since preflight began shows a mode other than Reset: Run
    /// or Calibration, put there by something other than this host's enable sequence.
    NotReset {
        /// The mode it reports.
        mode: Mode,
    },
    /// No status came back during preflight, so its faults and mode are unknown.
    NoStatus,
}

impl Refusal {
    /// The rule it falls under.
    #[must_use]
    pub const fn rule(&self) -> RuleId {
        match self {
            Self::CapUnset(_) | Self::CapOutOfRange { .. } | Self::Cap { .. } => RuleId::DriveCaps,
            Self::CanTimeout { .. } => RuleId::DriveCanTimeout,
            Self::DamperOff => RuleId::DriveDamper,
            Self::Uid { .. } => RuleId::HostIdentity,
            Self::NoAnswer { exchange, .. } => exchange.rule(),
            Self::Unwired
            | Self::UnvouchedModel(_)
            | Self::WrongView { .. }
            | Self::LimbActive
            | Self::LimbStopped { .. }
            | Self::FactUnset(_)
            | Self::Vbus { .. }
            | Self::Faults { .. }
            | Self::FaultSeen
            | Self::NotReset { .. }
            | Self::NoStatus => RuleId::HostPreflight,
        }
    }

    /// The operator's line: the rule, the joint, what was measured and what was expected.
    #[must_use]
    pub fn message(&self, joint: &str) -> String {
        let what = match self {
            Self::CapUnset(cap) => format!(
                "{} is null in the skeleton, expected the agreed cap",
                cap.field()
            ),
            Self::CapOutOfRange { cap, value, max } => format!(
                "{} is {value} in the skeleton, expected 0 to {max} for its drive",
                cap.field()
            ),
            Self::FactUnset(fact) => {
                format!(
                    "{} is null in the skeleton, expected a verified value",
                    fact.field()
                )
            }
            Self::Unwired => "has no bus in the skeleton, expected its bus".to_owned(),
            Self::UnvouchedModel(model) => {
                format!(
                    "is a {model:?}, whose MIT scales aren't settled, expected a model they are for"
                )
            }
            Self::WrongView { view, drive } => {
                format!("was checked against {view}'s view, expected {drive}'s")
            }
            Self::LimbActive => "is in an enabled limb, expected the limb idle".to_owned(),
            Self::LimbStopped { stop } => format!(
                "found its limb stopped or cleared since preflight began{}, expected it idle throughout",
                stopped_by(*stop)
            ),
            Self::NoAnswer { exchange, how } => {
                format!(
                    "got no usable answer to {}: {}",
                    exchange.describe(),
                    how.describe()
                )
            }
            Self::Uid { read, expected } => {
                format!("UID reads {}, expected {}", hex(*read), hex(*expected))
            }
            Self::CanTimeout { read } => format!(
                "canTimeout reads {}, expected {}",
                read.ticks(),
                CanTimeout::RUNTIME.ticks()
            ),
            Self::Cap {
                register,
                written,
                read,
            } => format!(
                "{} reads {}, written {}",
                register.name(),
                amount(*read),
                amount(*written)
            ),
            Self::DamperOff => "damper reads 1 (protection off), expected 0".to_owned(),
            Self::Vbus { read, window } => format!(
                "VBUS reads {} V, expected {} to {} V",
                read.get(),
                window.lower.get(),
                window.upper.get()
            ),
            Self::Faults { bits } => format!("reports faults {bits:?}, expected none"),
            Self::FaultSeen => "had a fault since the last clear, expected none".to_owned(),
            Self::NotReset { mode } => format!("is in {mode:?}, expected Reset"),
            Self::NoStatus => {
                "sent no status during preflight, expected one with its mode and faults".to_owned()
            }
        };
        format!("refused ({}): {joint} {what}", self.rule())
    }

    /// What the operator does about it (safety.md section 5).
    #[must_use]
    pub const fn remedy(&self) -> &'static str {
        match self {
            Self::CapUnset(_) | Self::CapOutOfRange { .. } => {
                "Agree the cap with the hardware side and put it in the skeleton"
            }
            Self::FactUnset(JointFact::Direction) => {
                "Run the sign check with the hardware side and put the direction in the skeleton"
            }
            Self::FactUnset(JointFact::Zero) => {
                "Reference the joint with the hardware side and put zero_rad in the skeleton"
            }
            Self::FactUnset(JointFact::HardLimits) => {
                "Measure the joint's stops with the hardware side and put hard_rad in the skeleton"
            }
            Self::Unwired => "Wire the joint and give it its bus in the skeleton",
            Self::UnvouchedModel(_) => {
                "Settle the model's MIT scales on the bench (PLAN item 2) before enabling it"
            }
            Self::WrongView { .. } => "A runtime bug: stop and report it with the log",
            Self::LimbActive => {
                "A joint of the limb is enabled: disable the limb, then run every joint's preflight before enabling any"
            }
            Self::LimbStopped { .. } => {
                "Find why the limb stopped in the log, clear the limb, then run preflight again"
            }
            Self::NoAnswer { how, .. } => how.remedy(),
            Self::NoStatus => "Check the drive's power and cable, then run preflight again",
            Self::Uid { .. } => {
                "A different drive answers on this ID: check which drive is wired here before anything else"
            }
            Self::CanTimeout { .. } | Self::Cap { .. } => {
                "Run preflight again; if it reads wrong twice, the drive isn't keeping writes: stop and investigate"
            }
            Self::DamperOff => {
                "Set the damper back to 0 with the vendor tool; this stack never writes it"
            }
            Self::Vbus { .. } => "Check the supply voltage and wiring",
            Self::Faults { .. } | Self::FaultSeen => {
                "Find the fault's cause, power-cycle the drive, clear the limb, then run preflight again"
            }
            // The bus doesn't stop an idle limb for a drive out of Reset, so there is no stop to clear.
            Self::NotReset { .. } => {
                "Find what put it in that mode; power-cycle the drive, then run preflight again"
            }
        }
    }
}

impl Unanswered {
    /// What happened, for the operator's line.
    fn describe(self) -> String {
        match self {
            Self::TimedOut => "no answer came in time".to_owned(),
            Self::Late => "its answer was handed over late".to_owned(),
            Self::NotSent(Unsent::QueueFull) => "not sent, the adapter's queue was full".to_owned(),
            Self::NotSent(Unsent::Expired) => "not sent, it expired queued".to_owned(),
            Self::NotSent(Unsent::Failed) => "not sent, the bus failed".to_owned(),
            Self::Refused(refusal) => format!("refused by the bus: {refusal}"),
            Self::ReadRefused => "the drive refused the read".to_owned(),
            Self::WrongAnswer => "an answer of another kind came".to_owned(),
        }
    }

    const fn remedy(self) -> &'static str {
        match self {
            Self::TimedOut => "Check the drive's power and cable, then run preflight again",
            Self::Late => {
                "The runtime fell behind handing over the answer: check its log and the Pi's load, then run preflight again"
            }
            Self::ReadRefused => {
                "The drive wouldn't read the register: check its firmware with the vendor tool, then run preflight again"
            }
            Self::WrongAnswer => {
                "Another frame answered in its place: check for a second drive or tool on the bus, then run preflight again"
            }
            Self::NotSent(Unsent::QueueFull) => {
                "The bus was too busy to send it: run preflight again"
            }
            Self::NotSent(Unsent::Expired) => {
                "The bus thread fell behind and never had time to send it: check the runtime's log and the Pi's load, then run preflight again"
            }
            Self::NotSent(Unsent::Failed) => {
                "The bus failed: check the adapter and cable, then restart the runtime"
            }
            Self::Refused(refusal) => match refusal {
                SlowRefusal::LimbStopped => {
                    "The limb is stopped: find why, clear the limb, then run preflight again"
                }
                SlowRefusal::LimbNotIdle => {
                    "A joint of the limb is enabled: disable the limb, then run every joint's preflight before enabling any"
                }
                SlowRefusal::CommandUnanswered => {
                    "A command to the drive was still waiting for its answer: run preflight again"
                }
                SlowRefusal::ControlSilent => {
                    "The control thread fell silent: find why in the runtime's log before anything else"
                }
                SlowRefusal::BusFailed | SlowRefusal::Ended => {
                    "The bus failed or its thread ended: check the adapter and cable, then restart the runtime"
                }
                SlowRefusal::QueueFull => "The bus was too busy: run preflight again",
                SlowRefusal::NoSuchSlot | SlowRefusal::WrongTarget | SlowRefusal::BatchOnly => {
                    "A runtime bug: stop and report it with the log"
                }
            },
        }
    }
}

/// What stopped a limb, for an operator's line: the rule behind the stop where it has one (safety.md section 2), or
/// that it was asked for; nothing when the snapshot no longer says.
pub(crate) fn stopped_by(stop: Option<StopReason>) -> String {
    match stop {
        Some(reason) => match RuleId::of_stop(reason) {
            Some(rule) => format!(" ({rule}: {reason:?})"),
            None => format!(" ({reason:?})"),
        },
        None => String::new(),
    }
}

/// A UID as the skeleton writes it: `0x` and 16 hex digits, bytes in the order the reply carries them.
fn hex(uid: Uid) -> String {
    format!("0x{:016x}", u64::from_be_bytes(uid.0))
}

/// A cap's value with its unit.
fn amount(value: ParamValue) -> String {
    match value {
        ParamValue::NewtonMeters(v) => format!("{} N·m", v.get()),
        ParamValue::Amps(v) => format!("{} A", v.get()),
        ParamValue::RadPerSec(v) => format!("{} rad/s", v.get()),
        ParamValue::RunMode(_)
        | ParamValue::ZeroSta(_)
        | ParamValue::Damper(_)
        | ParamValue::Switch(_)
        | ParamValue::ReportInterval(_)
        | ParamValue::CanTimeout(_)
        | ParamValue::Volts(_)
        | ParamValue::Radians(_)
        | ParamValue::RadPerSecSq(_)
        | ParamValue::Gain(_) => format!("{value:?}"),
    }
}
