//! Preflight (PLAN item 6, drive layer and the Preflight row): before every enable, each named drive is asked who it is,
//! has `canTimeout` and its three caps written, and has every one of them read back with the damper and VBUS, one slow
//! request at a time. Only a pass makes a [`PreflightPassed`], which the enable sequence takes, so an enable without a
//! preflight doesn't compile (rust.md section 3).
//!
//! A write is answered by a plain status that names no register (`robstride` `param_write`), so a write proves nothing
//! until its read-back. Every unknown fails closed: a request not answered in time, or an answer of the wrong kind. A
//! null cap, `direction`, `zero_rad` or `hard_rad` in the skeleton is not one: it lowers the caps written
//! ([`skeleton::Joint::caps`], PLAN item 1). A null UID skips the UID check until a UID is written.
//!
//! Preflight is stepped with what its drive's bus last showed ([`Seen`]): a view of any other drive, by ID or by bus,
//! or from another slot than its requests go to, refuses, and so does a limb that isn't idle, or that stopped or was
//! cleared since preflight began.
//!
//! Times here (`now_ns`, `read_ns`, `at_ns`) are nanoseconds on the runtime's monotonic epoch, the clock the bus layer
//! stamps its views with (`telemetry::Epoch`); a bare `u64` like the bus layer's own, so they compare with its fields
//! as is.

use can::{DriveView, LimbState, ModeSeen, SlowKind, SlowOutcome, SlowRequest, SlowResult};
use robstride::{
    CanTimeout, Damper, Drive, Mode, Param, ParamOutcome, ParamValue, Uid, Volts, Write,
};
use skeleton::{Joint, Power, Window};

use crate::refusal::{CapKind, Refusal, Unanswered};
use crate::rule::RuleId;
use crate::seen::{DriveAddress, Seen};

/// How long preflight waits for one request's result before refusing. A bus sends at most one slow request a tick, in
/// the slack of a tick that wasn't held, and gives each its result by the next tick's start, so a full bus
/// (`can::MAX_DRIVES` drives, each asking one at a time) answers every drive's request within `MAX_DRIVES` trusted
/// ticks: under 100 ms even at the slowest rate `can::Timing::check` allows. A request that a run of held ticks keeps
/// queued ends in `can::Unsent::Expired` after `can::Timing::slow_queue_ticks`, also well inside this wait. A second is
/// far past both and bounds a result control's ring dropped (`slow_results_dropped`), or one control handed over late.
pub const ANSWER_WITHIN_NS: u64 = 1_000_000_000;

/// Whether a request submitted at `at_ns` has had longer than [`ANSWER_WITHIN_NS`] by `now_ns`.
const fn overdue(at_ns: u64, now_ns: u64) -> bool {
    now_ns.saturating_sub(at_ns) > ANSWER_WITHIN_NS
}

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

/// How many exchanges there are, as a tag count.
const fn exchange_count() -> u32 {
    let mut count: u32 = 0;
    let mut i = 0;
    while i < EXCHANGES.len() {
        count += 1;
        i += 1;
    }
    count
}

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
    address: DriveAddress,
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
    /// [`Refusal::Unwired`] for a joint with no bus, [`Refusal::UnvouchedModel`] for a model whose MIT scales aren't
    /// settled, [`Refusal::CapOutOfRange`] for a cap its model can't take.
    ///
    /// Null is not a refusal (PLAN item 1): the caps written are [`skeleton::Joint::caps`], a commissioned joint's own
    /// or, for an uncommissioned one, each the lower of its model's commissioning cap and its own.
    pub fn new(joint: &Joint, power: &Power) -> Result<Self, Refusal> {
        // The skeleton holds every bus name to the kernel's limit, so a name that doesn't fit an address is one no
        // parsed skeleton has: no bus this host can open, so the joint is offline.
        let address = joint
            .bus
            .as_ref()
            .and_then(|bus| DriveAddress::new(bus, joint.id))
            .ok_or(Refusal::Unwired)?;
        let drive = Drive::new(joint.id, joint.actuator);
        // Control can't command a model whose MIT frame isn't settled, so it isn't enabled (PLAN item 2).
        if drive.model().mit_scales().is_err() {
            return Err(Refusal::UnvouchedModel(drive.model()));
        }
        let ranges = drive.model().ranges();
        let skeleton::Caps {
            torque,
            current,
            speed,
        } = joint.caps();
        let out = |cap, value, max| Refusal::CapOutOfRange { cap, value, max };
        Ok(Self {
            drive,
            address,
            uid: joint.uid,
            can_timeout: Write::can_timeout(drive),
            torque: Write::limit_torque(drive, torque).map_err(|_| {
                out(
                    CapKind::Torque,
                    ParamValue::NewtonMeters(torque),
                    ParamValue::NewtonMeters(ranges.torque_max),
                )
            })?,
            current: Write::limit_cur(drive, current).map_err(|_| {
                out(
                    CapKind::Current,
                    ParamValue::Amps(current),
                    ParamValue::Amps(ranges.current_max),
                )
            })?,
            speed: Write::limit_spd(drive, speed).map_err(|_| {
                out(
                    CapKind::Speed,
                    ParamValue::RadPerSec(speed),
                    ParamValue::RadPerSec(ranges.speed_max),
                )
            })?,
            vbus: power.vbus_v,
        })
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    /// The drive's bus and ID.
    #[must_use]
    pub const fn address(&self) -> DriveAddress {
        self.address
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
/// so one preflight enables at most once. It proves the drive was right when it was made, and stays true only until an
/// event voids it: a stop, a fault, silence, a drop out of Run, a bus lost, a reboot or runtime restart, or a write to
/// the drive from anything else (an ordinary reply doesn't). Keeping it fresh is the runtime's duty, not a time limit
/// here: it runs preflight for every named drive of the enable first, and starts their enable sequences in the tick the
/// last proof comes (the bus refuses slow writes to a limb that isn't idle, so a drive enabled early would refuse its
/// limb-mates' preflights); it drops every proof or cancels every sequence on any such event, and runs preflight again
/// for every enable. It carries the drive's bus and ID and its limb's `generation`, so the enable sequence ends by
/// itself on the voiding events its snapshots show: a stop or clear of the limb, a fault, another drive's view (or its
/// own from another slot), and a mode other than Reset before its Enable.
#[derive(Debug, PartialEq, Eq)]
pub struct PreflightPassed {
    drive: Drive,
    address: DriveAddress,
    /// The drive's slot on its bus, as preflight was started with it.
    slot: usize,
    /// The limb's `generation` throughout: a clear since would void the proof.
    generation: u32,
    /// When preflight began: every status and version reply read since showed Reset up to the pass.
    started_ns: u64,
    at_ns: u64,
}

impl PreflightPassed {
    /// The drive that passed.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    /// Its bus and ID.
    #[must_use]
    pub const fn address(&self) -> DriveAddress {
        self.address
    }

    /// Its slot on its bus, as preflight was started with it.
    pub(crate) const fn slot(&self) -> usize {
        self.slot
    }

    /// Its limb's `generation` while preflight ran.
    pub(crate) const fn generation(&self) -> u32 {
        self.generation
    }

    /// When preflight began, on the bus's clock: every status and version reply read since showed Reset up to the
    /// pass, so a mode out of Reset read since is news the proof didn't check.
    pub(crate) const fn started_ns(&self) -> u64 {
        self.started_ns
    }

    /// The control thread's clock at the poll that passed, for the event log. Not the read time of anything it judged:
    /// control takes the snapshot before it reads the clock, so a frame the bus read in between is newer than the
    /// snapshot but older than this.
    #[must_use]
    pub const fn at_ns(&self) -> u64 {
        self.at_ns
    }
}

/// What preflight wants next.
#[derive(Debug, PartialEq)]
pub enum Step {
    /// Submit this slow request, as it is, to the drive's bus, then hand its result to [`Preflight::answered`].
    Submit(SlowRequest),
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
///
/// It issues its own requests, each for its drive's slot and with its own tag, and takes a result only for the request
/// in flight: one for another slot, or with another tag (an earlier, aborted preflight's, say), is ignored and counted
/// ([`Preflight::ignored`]). Ignoring fails closed without letting a stray result kill a fresh preflight: it never
/// answers a request, so the request in flight still needs its own result, or refuses as unanswered.
#[derive(Debug, PartialEq)]
pub struct Preflight {
    target: Target,
    /// The drive's slot on its bus.
    slot: usize,
    /// The tag of the first exchange; exchange `n` is tagged `first_tag + n`.
    first_tag: u32,
    /// Results handed over that answered no request in flight.
    ignored: u32,
    started_ns: u64,
    /// The limb's `generation` at the first poll.
    generation: Option<u32>,
    state: State,
}

impl Preflight {
    /// The tags one preflight puts on its requests: one per exchange.
    pub const TAGS: u32 = exchange_count();

    /// Begin preflight at `now_ns` for the drive in `slot` of its bus: a status read before this proves nothing about
    /// the drive now. Its requests take the [`Self::TAGS`] tags from `first_tag` on (wrapping), so `first_tag` must
    /// start a block no other request on the bus uses while this preflight runs: control moves its tag counter on by
    /// [`Self::TAGS`] for each preflight, and so tells an earlier preflight's results from this one's.
    #[must_use]
    pub const fn start(target: Target, slot: usize, first_tag: u32, now_ns: u64) -> Self {
        Self {
            target,
            slot,
            first_tag,
            ignored: 0,
            started_ns: now_ns,
            generation: None,
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

    /// Results handed to [`Self::answered`] that answered no request in flight: another slot's, another tag's, or one
    /// with nothing in flight. For the log; each was ignored.
    #[must_use]
    pub const fn ignored(&self) -> u32 {
        self.ignored
    }

    /// The next step, given what the drive's bus last showed of it and the time. A view of another drive (by ID or by
    /// bus) or from another slot than the one preflight was started with, a fault in the latest status or latched since the last clear, any mode but Reset in the latest status or
    /// status header (a version reply's included) or latched by the bus since preflight began, or a limb that isn't
    /// idle or that stopped or was cleared since the first poll, refuses at once; so does a request with no result
    /// within [`ANSWER_WITHIN_NS`].
    pub fn poll(&mut self, seen: Seen<'_>, now_ns: u64) -> Step {
        let view = seen.view;
        // Taken at the first poll, which is always while asking.
        let generation = *self.generation.get_or_insert(seen.limb.generation);
        if let State::Asking { .. } = self.state {
            // The drive's own faults and mode before the limb's state, so a stop the bus made for them is named by
            // its own rule.
            let refusal =
                if !self.target.address.is(seen.bus, view.device) || seen.slot != self.slot {
                    Some(Refusal::WrongView {
                        view: seen.address(),
                        view_slot: seen.slot,
                        drive: self.target.address,
                        slot: self.slot,
                    })
                } else if let Some(refusal) = self.status_refusal(view) {
                    Some(refusal)
                } else if !seen.limb.state.takes_commands() || seen.limb.generation != generation {
                    Some(Refusal::LimbStopped {
                        stop: seen.limb.stop,
                    })
                } else if seen.limb.state == LimbState::Active {
                    Some(Refusal::LimbActive)
                } else {
                    None
                };
            if let Some(refusal) = refusal {
                self.state = State::Refused(refusal);
            }
        }
        match self.state {
            State::Asking { next, submitted_ns } => match (EXCHANGES.get(next), submitted_ns) {
                (Some(&exchange), Some(at)) => {
                    if overdue(at, now_ns) {
                        self.refuse(Refusal::NoAnswer {
                            exchange,
                            how: Unanswered::TimedOut,
                        })
                    } else {
                        Step::Wait
                    }
                }
                (Some(&exchange), None) => match (self.kind(exchange), self.tag(next)) {
                    (Some(kind), Some(tag)) => {
                        self.state = State::Asking {
                            next,
                            submitted_ns: Some(now_ns),
                        };
                        Step::Submit(SlowRequest {
                            tag,
                            slot: self.slot,
                            kind,
                        })
                    }
                    (None, _) | (_, None) => self.refuse(Refusal::NoAnswer {
                        exchange,
                        how: Unanswered::WrongAnswer,
                    }),
                },
                (None, _) if self.fresh(view) => {
                    self.state = State::Spent;
                    Step::Passed(PreflightPassed {
                        drive: self.target.drive,
                        address: self.target.address,
                        slot: self.slot,
                        generation,
                        started_ns: self.started_ns,
                        at_ns: now_ns,
                    })
                }
                (None, _) => self.refuse(Refusal::NoStatus),
            },
            State::Refused(refusal) => Step::Refused(refusal),
            State::Spent => Step::Spent,
        }
    }

    /// A result from the drive's bus, handed over at `now_ns`. Only the result of the request in flight counts, by its
    /// slot and tag; any other is ignored and counted ([`Self::ignored`]). The result of the request in flight handed
    /// over after [`ANSWER_WITHIN_NS`] refuses as [`Unanswered::Late`]. The order of `answered` and [`poll`](Self::poll)
    /// in a tick doesn't change the verdict for the same `now_ns`: a request past its window is refused either way,
    /// named `Late` when its result is handed over first and `TimedOut` when the poll comes first.
    pub fn answered(&mut self, result: SlowResult, now_ns: u64) {
        let in_flight = match self.state {
            State::Asking {
                next,
                submitted_ns: Some(at),
            } => EXCHANGES
                .get(next)
                .copied()
                .zip(self.tag(next))
                .filter(|(_, tag)| result.slot == self.slot && result.tag == *tag)
                .map(|(exchange, _)| (next, at, exchange)),
            State::Asking {
                submitted_ns: None, ..
            }
            | State::Refused(_)
            | State::Spent => None,
        };
        let Some((next, at, exchange)) = in_flight else {
            self.ignored = self.ignored.saturating_add(1);
            return;
        };
        let checked = if overdue(at, now_ns) {
            Err(Refusal::NoAnswer {
                exchange,
                how: Unanswered::Late,
            })
        } else {
            self.check(exchange, result.outcome)
        };
        self.state = match checked {
            Ok(()) => State::Asking {
                next: next + 1,
                submitted_ns: None,
            },
            Err(refusal) => State::Refused(refusal),
        };
    }

    /// Exchange `next`'s tag, or `None` past the last exchange.
    fn tag(&self, next: usize) -> Option<u32> {
        u32::try_from(next)
            .ok()
            .filter(|n| *n < Self::TAGS)
            .map(|n| self.first_tag.wrapping_add(n))
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
    /// then a fault latched since the last clear, then any mode but Reset since preflight began ([`left_reset`]: Run,
    /// or Calibration, something other than this host's enable sequence put it there).
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
        left_reset(view, self.started_ns).map(|mode| Refusal::NotReset { mode })
    }

    fn check(&self, exchange: Exchange, outcome: SlowOutcome) -> Result<(), Refusal> {
        let no_answer = |how| Refusal::NoAnswer { exchange, how };
        match (exchange, outcome) {
            (_, SlowOutcome::TimedOut) => Err(no_answer(Unanswered::TimedOut)),
            (_, SlowOutcome::NotSent(sent)) => Err(no_answer(Unanswered::NotSent(sent))),
            (_, SlowOutcome::Refused(refusal)) => Err(no_answer(Unanswered::Refused(refusal))),
            (Exchange::Read(_), SlowOutcome::Read(ParamOutcome::Refused)) => {
                Err(no_answer(Unanswered::ReadRefused))
            }
            (Exchange::Identity, SlowOutcome::Identity(read)) => match self.target.uid {
                Some(expected) if expected != read => Err(Refusal::Uid { read, expected }),
                Some(_) | None => Ok(()),
            },
            (Exchange::Write(_), SlowOutcome::WriteAnswered) => Ok(()),
            (Exchange::Read(register), SlowOutcome::Read(ParamOutcome::Read(value))) => {
                self.read_back(register, value)
            }
            (
                Exchange::Identity | Exchange::Write(_) | Exchange::Read(_),
                SlowOutcome::Identity(_)
                | SlowOutcome::WriteAnswered
                | SlowOutcome::Read(_)
                | SlowOutcome::Found { .. }
                | SlowOutcome::Unsure,
            ) => Err(no_answer(Unanswered::WrongAnswer)),
        }
    }

    /// The read-back check of `register`; a value of another type than the register's is an answer of another kind.
    fn read_back(&self, register: Register, read: ParamValue) -> Result<(), Refusal> {
        let wrong_type = Refusal::NoAnswer {
            exchange: Exchange::Read(register),
            how: Unanswered::WrongAnswer,
        };
        let as_written = |written: Write| {
            if core::mem::discriminant(&read) != core::mem::discriminant(&written.value()) {
                Err(wrong_type)
            } else if read == written.value() {
                Ok(())
            } else {
                Err(Refusal::Cap {
                    register,
                    written: written.value(),
                    read,
                })
            }
        };
        match register {
            Register::CanTimeout => {
                let ParamValue::CanTimeout(read) = read else {
                    return Err(wrong_type);
                };
                if read == CanTimeout::RUNTIME {
                    Ok(())
                } else {
                    Err(Refusal::CanTimeout { read })
                }
            }
            Register::LimitTorque => as_written(self.target.torque),
            Register::LimitCur => as_written(self.target.current),
            Register::LimitSpd => as_written(self.target.speed),
            Register::Damper => {
                let ParamValue::Damper(damper) = read else {
                    return Err(wrong_type);
                };
                match damper {
                    Damper::ProtectionOn => Ok(()),
                    Damper::ProtectionOff => Err(Refusal::DamperOff),
                }
            }
            Register::Vbus => {
                let ParamValue::Volts(read) = read else {
                    return Err(wrong_type);
                };
                let window = self.target.vbus;
                if read.get() >= window.lower.get() && read.get() <= window.upper.get() {
                    Ok(())
                } else {
                    Err(Refusal::Vbus { read, window })
                }
            }
        }
    }
}

/// A mode other than Reset that the drive's bus has shown since `since_ns`, if any: in its latest status header (`mode`,
/// a version reply's included), in its last status (`observed`), or latched by the bus while this host hadn't enabled
/// the drive (`out_of_reset`), so a later Reset hides none of them, even one between two snapshots. Only what was read
/// since `since_ns`, when preflight began, counts: the latch stays until the limb's re-arm, which an idle limb can't
/// have, and an excursion before preflight began is one its own checks then saw end, in a status in Reset read since.
pub(crate) fn left_reset(view: &DriveView, since_ns: u64) -> Option<Mode> {
    modes_shown(view)
        .chain(view.out_of_reset)
        .filter(|m| m.read_ns >= since_ns)
        .map(|m| m.mode)
        .find(|mode| *mode != Mode::Reset)
}

/// The modes the drive's bus last showed, each with its read time: its latest status header (`mode`, a version reply's
/// included) and its last status (`observed`), which a later version reply doesn't replace. One can show a mode the
/// other has moved past in the same drain, so a check for a mode judges both.
pub(crate) fn modes_shown(view: &DriveView) -> impl Iterator<Item = ModeSeen> {
    let status = view.observed.map(|o| ModeSeen {
        mode: o.status.header.mode,
        read_ns: o.read_ns,
    });
    view.mode.into_iter().chain(status)
}
