//! Preflight (PLAN item 6, drive layer and the Preflight row): before every enable, each named drive is asked who it is,
//! has `canTimeout` and its three caps written, and has every one of them read back with the damper and VBUS, one slow
//! request at a time. Only a pass makes a [`PreflightPassed`], which the enable sequence takes, so an enable without a
//! preflight doesn't compile (rust.md section 3).
//!
//! A write is answered by a plain status that names no register (`robstride` `param_write`), so a write proves nothing
//! until its read-back. Every unknown fails closed: a request not answered, an answer of the wrong kind, a value the
//! skeleton leaves null.

use can::{DriveView, SendOutcome, SlowKind, SlowOutcome, SlowRefusal};
use robstride::{
    CanTimeout, Damper, Drive, Mode, Param, ParamOutcome, ParamValue, StatusFaults, Uid, Volts,
    Write,
};
use skeleton::{Joint, Power, Window};

use crate::rule::RuleId;

/// The exchanges, in order: identity first, every write, then every read-back.
const EXCHANGES: [Exchange; 11] = [
    Exchange::Identity,
    Exchange::Write(Param::CanTimeout),
    Exchange::Write(Param::LimitTorque),
    Exchange::Write(Param::LimitCur),
    Exchange::Write(Param::LimitSpd),
    Exchange::Read(Param::CanTimeout),
    Exchange::Read(Param::LimitTorque),
    Exchange::Read(Param::LimitCur),
    Exchange::Read(Param::LimitSpd),
    Exchange::Read(Param::Damper),
    Exchange::Read(Param::Vbus),
];

/// One of preflight's slow requests.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Exchange {
    /// Get-ID (type 0), for the UID.
    Identity,
    /// A write of this register.
    Write(Param),
    /// A read of this register.
    Read(Param),
}

impl Exchange {
    /// The rule a failed exchange falls under.
    const fn rule(self) -> RuleId {
        match self {
            Self::Identity => RuleId::HostIdentity,
            Self::Write(param) | Self::Read(param) => match param {
                Param::CanTimeout => RuleId::DriveCanTimeout,
                Param::LimitTorque | Param::LimitCur | Param::LimitSpd => RuleId::DriveCaps,
                Param::Damper => RuleId::DriveDamper,
                _ => RuleId::HostPreflight,
            },
        }
    }
}

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

/// How a request went unanswered.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Unanswered {
    /// No reply within its window.
    TimedOut,
    /// The socket didn't take it.
    NotSent(SendOutcome),
    /// The bus layer refused it.
    Refused(SlowRefusal),
    /// The drive answered a read with "can't read it".
    ReadRefused,
    /// An answer of another kind, or a value of another type, than the request asks for.
    WrongAnswer,
}

/// Why preflight refused a drive. Each names what was measured and what was expected (safety.md section 5);
/// [`Refusal::message`] says it for the operator, with the joint.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Refusal {
    /// The skeleton has no value for this cap: null is not permission (PLAN item 1).
    CapUnset(CapKind),
    /// The skeleton's cap is outside what the drive's model can be set to.
    CapOutOfRange(CapKind),
    /// The joint has no bus: it is offline and can't be enabled.
    Unwired,
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
        param: Param,
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
    /// A status since preflight began carried fault bits.
    Faults {
        /// The bits.
        bits: StatusFaults,
    },
    /// A fault was seen since start or the limb's last clear (fault bits clear only by power-cycling the drive, then a
    /// clear).
    FaultSeen,
    /// The drive was already in Run: something other than this host's enable sequence put it there.
    AlreadyRunning,
    /// No status came back during preflight, so its faults and mode are unknown.
    NoStatus,
}

impl Refusal {
    /// The rule it falls under.
    #[must_use]
    pub const fn rule(&self) -> RuleId {
        match self {
            Self::CapUnset(_) | Self::CapOutOfRange(_) | Self::Cap { .. } => RuleId::DriveCaps,
            Self::CanTimeout { .. } => RuleId::DriveCanTimeout,
            Self::DamperOff => RuleId::DriveDamper,
            Self::Uid { .. } => RuleId::HostIdentity,
            Self::NoAnswer { exchange, .. } => exchange.rule(),
            Self::Unwired
            | Self::Vbus { .. }
            | Self::Faults { .. }
            | Self::FaultSeen
            | Self::AlreadyRunning
            | Self::NoStatus => RuleId::HostPreflight,
        }
    }

    /// The operator's line: the rule, the joint, what was measured and what was expected.
    #[must_use]
    pub fn message(&self, joint: &str) -> String {
        let what = match self {
            Self::CapUnset(cap) => format!("{} is null in the skeleton", cap.field()),
            Self::CapOutOfRange(cap) => {
                format!(
                    "{} is outside what its drive model can be set to",
                    cap.field()
                )
            }
            Self::Unwired => "has no bus in the skeleton".to_owned(),
            Self::NoAnswer { exchange, how } => {
                format!("{exchange:?} got no usable answer: {how:?}")
            }
            Self::Uid { read, expected } => format!("UID reads {read:?}, expected {expected:?}"),
            Self::CanTimeout { read } => format!(
                "canTimeout reads {}, expected {}",
                read.ticks(),
                CanTimeout::RUNTIME.ticks()
            ),
            Self::Cap {
                param,
                written,
                read,
            } => format!("{param:?} reads {read:?}, written {written:?}"),
            Self::DamperOff => "damper reads 1 (protection off), expected 0".to_owned(),
            Self::Vbus { read, window } => format!(
                "VBUS reads {:.2} V, expected {:.2} to {:.2} V",
                read.get(),
                window.lower.get(),
                window.upper.get()
            ),
            Self::Faults { bits } => format!("reports faults {bits:?}, expected none"),
            Self::FaultSeen => "had a fault since the last clear".to_owned(),
            Self::AlreadyRunning => "is already in Run, expected Reset".to_owned(),
            Self::NoStatus => "sent no status during preflight".to_owned(),
        };
        format!("refused ({}): {joint} {what}", self.rule())
    }

    /// What the operator does about it (safety.md section 5).
    #[must_use]
    pub const fn remedy(&self) -> &'static str {
        match self {
            Self::CapUnset(_) | Self::CapOutOfRange(_) | Self::Unwired => {
                "Agree the value with the hardware side and put it in the skeleton"
            }
            Self::NoAnswer { .. } | Self::NoStatus => {
                "Check the drive's power and cable, then run preflight again"
            }
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
            Self::AlreadyRunning => {
                "Find what enabled it; power-cycle the drive, then run preflight again"
            }
        }
    }
}

/// What preflight checks one drive against, from the skeleton, built once at startup.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Target {
    drive: Drive,
    uid: Option<Uid>,
    /// `canTimeout`, `limit_torque`, `limit_cur`, `limit_spd`, in [`EXCHANGES`] order.
    writes: [Write; 4],
    vbus: Window<Volts>,
}

impl Target {
    /// The checks for `joint`'s drive under `power`.
    ///
    /// # Errors
    /// [`Refusal::Unwired`] for a joint with no bus, [`Refusal::CapUnset`] for a null cap, [`Refusal::CapOutOfRange`]
    /// for one its model can't take.
    pub fn new(joint: &Joint, power: &Power) -> Result<Self, Refusal> {
        if joint.bus.is_none() {
            return Err(Refusal::Unwired);
        }
        let drive = Drive::new(joint.id, joint.actuator);
        let torque = joint
            .torque_cap_nm
            .ok_or(Refusal::CapUnset(CapKind::Torque))?;
        let current = joint
            .current_cap_a
            .ok_or(Refusal::CapUnset(CapKind::Current))?;
        let speed = joint
            .speed_cap_rad_s
            .ok_or(Refusal::CapUnset(CapKind::Speed))?;
        let writes = [
            Write::can_timeout(drive),
            Write::limit_torque(drive, torque)
                .map_err(|_| Refusal::CapOutOfRange(CapKind::Torque))?,
            Write::limit_cur(drive, current)
                .map_err(|_| Refusal::CapOutOfRange(CapKind::Current))?,
            Write::limit_spd(drive, speed).map_err(|_| Refusal::CapOutOfRange(CapKind::Speed))?,
        ];
        Ok(Self {
            drive,
            uid: joint.uid,
            writes,
            vbus: power.vbus_v,
        })
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    fn write(&self, param: Param) -> Option<Write> {
        self.writes.iter().copied().find(|w| w.param() == param)
    }
}

/// Proof that one drive passed preflight. Only [`Preflight`] makes one, and the enable sequence takes it by value, so
/// it enables at most once.
#[derive(Debug, PartialEq, Eq)]
pub struct PreflightPassed {
    drive: Drive,
    at_ns: u64,
}

impl PreflightPassed {
    /// The drive that passed.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    /// When the last check passed, monotonic.
    #[must_use]
    pub const fn at_ns(&self) -> u64 {
        self.at_ns
    }
}

/// What preflight wants next.
#[derive(Debug, PartialEq)]
pub enum Step {
    /// Submit this slow request to the drive's bus, then report its result to [`Preflight::answered`].
    Submit(SlowKind),
    /// A request is in flight.
    Wait,
    /// Every check passed. Given once.
    Passed(PreflightPassed),
    /// A check failed; nothing more is asked of the drive.
    Refused(Refusal),
    /// Passed, and the proof was already given.
    Spent,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum State {
    /// The next exchange, and whether it is in flight.
    Asking {
        next: usize,
        in_flight: bool,
    },
    Refused(Refusal),
    Spent,
}

/// One drive's preflight, run by the control thread over the drive's bus's slow requests.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Preflight {
    target: Target,
    started_ns: u64,
    state: State,
}

impl Preflight {
    /// Begin preflight at `now_ns`: a status read before this proves nothing about the drive now.
    #[must_use]
    pub const fn start(target: Target, now_ns: u64) -> Self {
        Self {
            target,
            started_ns: now_ns,
            state: State::Asking {
                next: 0,
                in_flight: false,
            },
        }
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.target.drive
    }

    /// The next step, given the drive's latest view and the time. A fault or Run seen at any point refuses at once.
    pub fn poll(&mut self, view: &DriveView, now_ns: u64) -> Step {
        if let State::Asking { .. } = self.state
            && let Some(refusal) = self.status_refusal(view)
        {
            self.state = State::Refused(refusal);
        }
        match self.state {
            State::Asking { next, in_flight } => match EXCHANGES.get(next) {
                Some(_) if in_flight => Step::Wait,
                Some(&exchange) => match self.kind(exchange) {
                    Some(kind) => {
                        self.state = State::Asking {
                            next,
                            in_flight: true,
                        };
                        Step::Submit(kind)
                    }
                    None => self.refuse(Refusal::NoAnswer {
                        exchange,
                        how: Unanswered::WrongAnswer,
                    }),
                },
                None if self.fresh(view) => {
                    self.state = State::Spent;
                    Step::Passed(PreflightPassed {
                        drive: self.target.drive,
                        at_ns: now_ns,
                    })
                }
                None => self.refuse(Refusal::NoStatus),
            },
            State::Refused(refusal) => Step::Refused(refusal),
            State::Spent => Step::Spent,
        }
    }

    /// The result of the request in flight. A result with none in flight is ignored.
    pub fn answered(&mut self, outcome: SlowOutcome) {
        let State::Asking {
            next,
            in_flight: true,
        } = self.state
        else {
            return;
        };
        let Some(&exchange) = EXCHANGES.get(next) else {
            return;
        };
        self.state = match self.check(exchange, outcome) {
            Ok(()) => State::Asking {
                next: next + 1,
                in_flight: false,
            },
            Err(refusal) => State::Refused(refusal),
        };
    }

    fn refuse(&mut self, refusal: Refusal) -> Step {
        self.state = State::Refused(refusal);
        Step::Refused(refusal)
    }

    fn kind(&self, exchange: Exchange) -> Option<SlowKind> {
        match exchange {
            Exchange::Identity => Some(SlowKind::GetId),
            Exchange::Write(param) => self.target.write(param).map(SlowKind::Write),
            Exchange::Read(param) => Some(SlowKind::Read(param)),
        }
    }

    /// Whether a status read since preflight began has come in.
    fn fresh(&self, view: &DriveView) -> bool {
        view.observed.is_some_and(|o| o.read_ns >= self.started_ns)
    }

    fn status_refusal(&self, view: &DriveView) -> Option<Refusal> {
        if view.fault_seen {
            return Some(Refusal::FaultSeen);
        }
        let observed = view.observed.filter(|o| o.read_ns >= self.started_ns)?;
        let header = observed.status.header;
        if !header.faults.is_empty() {
            return Some(Refusal::Faults {
                bits: header.faults,
            });
        }
        (header.mode == Mode::Run).then_some(Refusal::AlreadyRunning)
    }

    fn check(&self, exchange: Exchange, outcome: SlowOutcome) -> Result<(), Refusal> {
        let no_answer = |how| Refusal::NoAnswer { exchange, how };
        match (exchange, outcome) {
            (_, SlowOutcome::TimedOut) => Err(no_answer(Unanswered::TimedOut)),
            (_, SlowOutcome::NotSent(sent)) => Err(no_answer(Unanswered::NotSent(sent))),
            (_, SlowOutcome::Refused(refusal)) => Err(no_answer(Unanswered::Refused(refusal))),
            (_, SlowOutcome::Read(ParamOutcome::Refused)) => {
                Err(no_answer(Unanswered::ReadRefused))
            }
            (Exchange::Identity, SlowOutcome::Identity(read)) => match self.target.uid {
                Some(expected) if expected != read => Err(Refusal::Uid { read, expected }),
                Some(_) | None => Ok(()),
            },
            (Exchange::Write(_), SlowOutcome::WriteAnswered) => Ok(()),
            (Exchange::Read(param), SlowOutcome::Read(ParamOutcome::Read(value))) => self
                .read_back(param, value)
                .unwrap_or(Err(no_answer(Unanswered::WrongAnswer))),
            (
                Exchange::Identity | Exchange::Write(_) | Exchange::Read(_),
                SlowOutcome::Identity(_) | SlowOutcome::WriteAnswered | SlowOutcome::Read(_),
            ) => Err(no_answer(Unanswered::WrongAnswer)),
        }
    }

    /// The read-back check, or `None` for a value of another type than the register's.
    fn read_back(&self, param: Param, value: ParamValue) -> Option<Result<(), Refusal>> {
        Some(match (param, value) {
            (Param::CanTimeout, ParamValue::CanTimeout(read)) => {
                if read == CanTimeout::RUNTIME {
                    Ok(())
                } else {
                    Err(Refusal::CanTimeout { read })
                }
            }
            (Param::LimitTorque | Param::LimitCur | Param::LimitSpd, read) => {
                let written = self.target.write(param)?.value();
                if core::mem::discriminant(&read) != core::mem::discriminant(&written) {
                    return None;
                }
                if read == written {
                    Ok(())
                } else {
                    Err(Refusal::Cap {
                        param,
                        written,
                        read,
                    })
                }
            }
            (Param::Damper, ParamValue::Damper(Damper::ProtectionOn)) => Ok(()),
            (Param::Damper, ParamValue::Damper(Damper::ProtectionOff)) => Err(Refusal::DamperOff),
            (Param::Vbus, ParamValue::Volts(read)) => {
                let window = self.target.vbus;
                if read.get() >= window.lower.get() && read.get() <= window.upper.get() {
                    Ok(())
                } else {
                    Err(Refusal::Vbus { read, window })
                }
            }
            _ => return None,
        })
    }
}
