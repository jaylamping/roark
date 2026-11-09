//! Preflight (PLAN item 6, drive layer and the Preflight row): before every enable, each named drive is asked who it is,
//! has `canTimeout` and its three caps written, and has every one of them read back with the damper and VBUS, one slow
//! request at a time. Only a pass makes a [`PreflightPassed`], which the enable sequence takes, so an enable without a
//! preflight doesn't compile (rust.md section 3).
//!
//! A write is answered by a plain status that names no register (`robstride` `param_write`), so a write proves nothing
//! until its read-back. Every unknown fails closed: a request not answered in time, an answer of the wrong kind, a value
//! the skeleton leaves null.

use can::{DriveView, SlowKind, SlowOutcome};
use robstride::{
    Amps, CanTimeout, Damper, Drive, Mode, NewtonMeters, Param, ParamOutcome, ParamValue,
    RadPerSec, Uid, Volts, Write,
};
use skeleton::{Joint, Power, Window};

use crate::refusal::{CapKind, JointFact, Refusal, Unanswered};
use crate::rule::RuleId;

/// How long preflight waits for one request's result before refusing. A bus serves one slow request a tick, so at
/// 250 Hz a full bus (`can::MAX_DRIVES` drives, each asking one at a time) answers every drive's request within 8 ticks;
/// a second is far past that and bounds only a result the bus dropped.
pub const ANSWER_WITHIN_NS: u64 = 1_000_000_000;

/// The registers preflight writes or reads.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Register {
    /// `canTimeout` 0x7028.
    CanTimeout,
    /// `limit_torque` 0x700B.
    LimitTorque,
    /// `limit_cur` 0x7018.
    LimitCur,
    /// `limit_spd` 0x7017.
    LimitSpd,
    /// `damper` 0x702A, read only.
    Damper,
    /// `VBUS` 0x701C, read only.
    Vbus,
}

impl Register {
    /// The drive's register.
    #[must_use]
    pub const fn param(self) -> Param {
        match self {
            Self::CanTimeout => Param::CanTimeout,
            Self::LimitTorque => Param::LimitTorque,
            Self::LimitCur => Param::LimitCur,
            Self::LimitSpd => Param::LimitSpd,
            Self::Damper => Param::Damper,
            Self::Vbus => Param::Vbus,
        }
    }

    /// The register's name in the manual, for the operator.
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::CanTimeout => "canTimeout",
            Self::LimitTorque => "limit_torque",
            Self::LimitCur => "limit_cur",
            Self::LimitSpd => "limit_spd",
            Self::Damper => "damper",
            Self::Vbus => "VBUS",
        }
    }

    /// The rule the register serves.
    const fn rule(self) -> RuleId {
        match self {
            Self::CanTimeout => RuleId::DriveCanTimeout,
            Self::LimitTorque | Self::LimitCur | Self::LimitSpd => RuleId::DriveCaps,
            Self::Damper => RuleId::DriveDamper,
            Self::Vbus => RuleId::HostPreflight,
        }
    }
}

/// The exchanges, in order: identity first, every write, then every read-back.
const EXCHANGES: [Exchange; 11] = [
    Exchange::Identity,
    Exchange::Write(Register::CanTimeout),
    Exchange::Write(Register::LimitTorque),
    Exchange::Write(Register::LimitCur),
    Exchange::Write(Register::LimitSpd),
    Exchange::Read(Register::CanTimeout),
    Exchange::Read(Register::LimitTorque),
    Exchange::Read(Register::LimitCur),
    Exchange::Read(Register::LimitSpd),
    Exchange::Read(Register::Damper),
    Exchange::Read(Register::Vbus),
];

/// One of preflight's slow requests.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Exchange {
    /// Get-ID (type 0), for the UID.
    Identity,
    /// A write of this register.
    Write(Register),
    /// A read of this register.
    Read(Register),
}

impl Exchange {
    /// The rule a failed exchange falls under.
    pub(crate) const fn rule(self) -> RuleId {
        match self {
            Self::Identity => RuleId::HostIdentity,
            Self::Write(register) | Self::Read(register) => register.rule(),
        }
    }

    /// What it asked, for the operator.
    pub(crate) fn describe(self) -> String {
        match self {
            Self::Identity => "get-ID".to_owned(),
            Self::Write(register) => format!("the write of {}", register.name()),
            Self::Read(register) => format!("the read of {}", register.name()),
        }
    }
}

/// What preflight checks one drive against, from the skeleton, built once at startup.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Target {
    drive: Drive,
    uid: Option<Uid>,
    can_timeout: Write,
    torque: Write,
    current: Write,
    speed: Write,
    vbus: Window<Volts>,
}

impl Target {
    /// The checks for `joint`'s drive under `power`.
    ///
    /// # Errors
    /// [`Refusal::Unwired`] for a joint with no bus, [`Refusal::CapUnset`] for a null cap, [`Refusal::FactUnset`] for a
    /// null direction or zero, [`Refusal::CapOutOfRange`] for a cap its model can't take.
    pub fn new(joint: &Joint, power: &Power) -> Result<Self, Refusal> {
        if joint.bus.is_none() {
            return Err(Refusal::Unwired);
        }
        let drive = Drive::new(joint.id, joint.actuator);
        let ranges = drive.model().ranges();
        let torque: NewtonMeters = joint
            .torque_cap_nm
            .ok_or(Refusal::CapUnset(CapKind::Torque))?;
        let current: Amps = joint
            .current_cap_a
            .ok_or(Refusal::CapUnset(CapKind::Current))?;
        let speed: RadPerSec = joint
            .speed_cap_rad_s
            .ok_or(Refusal::CapUnset(CapKind::Speed))?;
        if joint.direction.is_none() {
            return Err(Refusal::FactUnset(JointFact::Direction));
        }
        if joint.zero_rad.is_none() {
            return Err(Refusal::FactUnset(JointFact::Zero));
        }
        let out = |cap, value: f64, max: f64| Refusal::CapOutOfRange { cap, value, max };
        Ok(Self {
            drive,
            uid: joint.uid,
            can_timeout: Write::can_timeout(drive),
            torque: Write::limit_torque(drive, torque)
                .map_err(|_| out(CapKind::Torque, torque.get(), ranges.torque_max.get()))?,
            current: Write::limit_cur(drive, current)
                .map_err(|_| out(CapKind::Current, current.get(), ranges.current_max.get()))?,
            speed: Write::limit_spd(drive, speed)
                .map_err(|_| out(CapKind::Speed, speed.get(), ranges.speed_max.get()))?,
            vbus: power.vbus_v,
        })
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    const fn write(&self, register: Register) -> Option<Write> {
        match register {
            Register::CanTimeout => Some(self.can_timeout),
            Register::LimitTorque => Some(self.torque),
            Register::LimitCur => Some(self.current),
            Register::LimitSpd => Some(self.speed),
            Register::Damper | Register::Vbus => None,
        }
    }
}

/// Proof that one drive passed preflight. Only [`Preflight`] makes one, once, and the enable sequence takes it by value,
/// so one preflight enables at most once. It is fresh only while nothing has happened to the drive since: the runtime
/// starts the enable sequence in the tick it gets the proof, and drops the proof on any drive event first.
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

    /// When the last check passed, monotonic, for the event log.
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
    /// The next exchange, and when it was submitted if it is in flight.
    Asking {
        next: usize,
        submitted_ns: Option<u64>,
    },
    Refused(Refusal),
    Spent,
}

/// One drive's preflight, run by the control thread over the drive's bus's slow requests. Not `Copy` or `Clone`: a copy
/// could give a second proof.
#[derive(Debug, PartialEq)]
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
                submitted_ns: None,
            },
        }
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.target.drive
    }

    /// The next step, given the drive's latest view and the time. A fault in the latest status or latched since the
    /// last clear, or Run in the latest status since preflight began, refuses at once; so does a request with no
    /// result within [`ANSWER_WITHIN_NS`].
    pub fn poll(&mut self, view: &DriveView, now_ns: u64) -> Step {
        if let State::Asking { .. } = self.state
            && let Some(refusal) = self.status_refusal(view)
        {
            self.state = State::Refused(refusal);
        }
        match self.state {
            State::Asking { next, submitted_ns } => match (EXCHANGES.get(next), submitted_ns) {
                (Some(&exchange), Some(at)) => {
                    if now_ns.saturating_sub(at) > ANSWER_WITHIN_NS {
                        self.refuse(Refusal::NoAnswer {
                            exchange,
                            how: Unanswered::TimedOut,
                        })
                    } else {
                        Step::Wait
                    }
                }
                (Some(&exchange), None) => match self.kind(exchange) {
                    Some(kind) => {
                        self.state = State::Asking {
                            next,
                            submitted_ns: Some(now_ns),
                        };
                        Step::Submit(kind)
                    }
                    None => self.refuse(Refusal::NoAnswer {
                        exchange,
                        how: Unanswered::WrongAnswer,
                    }),
                },
                (None, _) if self.fresh(view) => {
                    self.state = State::Spent;
                    Step::Passed(PreflightPassed {
                        drive: self.target.drive,
                        at_ns: now_ns,
                    })
                }
                (None, _) => self.refuse(Refusal::NoStatus),
            },
            State::Refused(refusal) => Step::Refused(refusal),
            State::Spent => Step::Spent,
        }
    }

    /// The result of the request in flight. A result with none in flight is ignored.
    pub fn answered(&mut self, outcome: SlowOutcome) {
        let State::Asking {
            next,
            submitted_ns: Some(_),
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
                submitted_ns: None,
            },
            Err(refusal) => State::Refused(refusal),
        };
    }

    fn refuse(&mut self, refusal: Refusal) -> Step {
        self.state = State::Refused(refusal);
        Step::Refused(refusal)
    }

    const fn kind(&self, exchange: Exchange) -> Option<SlowKind> {
        match exchange {
            Exchange::Identity => Some(SlowKind::GetId),
            Exchange::Write(register) => match self.target.write(register) {
                Some(write) => Some(SlowKind::Write(write)),
                None => None,
            },
            Exchange::Read(register) => Some(SlowKind::Read(register.param())),
        }
    }

    /// Whether a status read since preflight began has come in.
    fn fresh(&self, view: &DriveView) -> bool {
        view.observed.is_some_and(|o| o.read_ns >= self.started_ns)
    }

    /// A refusal from what the drive's statuses show: the latest one's fault bits first, so the operator sees them,
    /// then a fault latched since the last clear, then Run.
    fn status_refusal(&self, view: &DriveView) -> Option<Refusal> {
        let latest = view.observed.filter(|o| o.read_ns >= self.started_ns);
        if let Some(o) = latest
            && !o.status.header.faults.is_empty()
        {
            return Some(Refusal::Faults {
                bits: o.status.header.faults,
            });
        }
        if view.fault_seen {
            return Some(Refusal::FaultSeen);
        }
        latest
            .is_some_and(|o| o.status.header.mode == Mode::Run)
            .then_some(Refusal::AlreadyRunning)
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
            (Exchange::Read(register), SlowOutcome::Read(ParamOutcome::Read(value))) => self
                .read_back(register, value)
                .unwrap_or(Err(no_answer(Unanswered::WrongAnswer))),
            (
                Exchange::Identity | Exchange::Write(_) | Exchange::Read(_),
                SlowOutcome::Identity(_) | SlowOutcome::WriteAnswered | SlowOutcome::Read(_),
            ) => Err(no_answer(Unanswered::WrongAnswer)),
        }
    }

    /// The read-back check, or `None` for a value of another type than the register's.
    fn read_back(&self, register: Register, read: ParamValue) -> Option<Result<(), Refusal>> {
        let as_written = |written: Write| {
            if core::mem::discriminant(&read) != core::mem::discriminant(&written.value()) {
                None
            } else if read == written.value() {
                Some(Ok(()))
            } else {
                Some(Err(Refusal::Cap {
                    register,
                    written: written.value(),
                    read,
                }))
            }
        };
        match register {
            Register::CanTimeout => {
                let ParamValue::CanTimeout(read) = read else {
                    return None;
                };
                Some(if read == CanTimeout::RUNTIME {
                    Ok(())
                } else {
                    Err(Refusal::CanTimeout { read })
                })
            }
            Register::LimitTorque => as_written(self.target.torque),
            Register::LimitCur => as_written(self.target.current),
            Register::LimitSpd => as_written(self.target.speed),
            Register::Damper => {
                let ParamValue::Damper(damper) = read else {
                    return None;
                };
                Some(match damper {
                    Damper::ProtectionOn => Ok(()),
                    Damper::ProtectionOff => Err(Refusal::DamperOff),
                })
            }
            Register::Vbus => {
                let ParamValue::Volts(read) = read else {
                    return None;
                };
                let window = self.target.vbus;
                Some(
                    if read.get() >= window.lower.get() && read.get() <= window.upper.get() {
                        Ok(())
                    } else {
                        Err(Refusal::Vbus { read, window })
                    },
                )
            }
        }
    }
}
