//! Running a whole preflight against a drive that answers every request truthfully except the one a row changes.

use can::{DriveView, SlowKind, SlowOutcome, SlowRequest, SlowResult};
use robstride::{
    CanTimeout, Damper, Mode, Param, ParamOutcome, ParamValue, StatusFaults, Uid, Volts,
};
use safety::{Exchange, Preflight, Refusal, Register, Step, Target};

use super::{joint, quiet, seen, shown, skeleton, status};

/// The default tick (`can::Timing`'s at PLAN item 3's 250 Hz): the bus sends at most one slow request a tick.
pub(crate) const PERIOD: u64 = can::Timing::at_hz(250).period_ns;

/// The slot the rows' drives are in on their bus.
pub(crate) const SLOT: usize = 0;

/// The fixture's UID for `arm_joint_one`.
pub(crate) const UID: Uid = Uid([0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef]);

#[expect(
    clippy::panic,
    reason = "test helper; preflight asks only its own registers"
)]
pub(crate) fn register(param: Param) -> Register {
    [
        Register::CanTimeout,
        Register::LimitTorque,
        Register::LimitCur,
        Register::LimitSpd,
        Register::Damper,
        Register::Vbus,
    ]
    .into_iter()
    .find(|r| r.param() == param)
    .unwrap_or_else(|| panic!("{param:?} isn't preflight's"))
}

fn exchange_of(kind: SlowKind) -> Exchange {
    match kind {
        SlowKind::GetId => Exchange::Identity,
        SlowKind::Write(w) => Exchange::Write(register(w.param())),
        SlowKind::Read(p) => Exchange::Read(register(p)),
    }
}

/// How the drive in a row behaves.
pub(crate) struct Drive {
    /// The answer to one exchange, in place of the truth.
    pub(crate) answer: Option<(Exchange, SlowOutcome)>,
    /// The status every write's answer carries; `None` for a drive whose statuses never come.
    pub(crate) status: Option<(Mode, StatusFaults)>,
    /// The view before preflight begins.
    pub(crate) before: DriveView,
}

impl Drive {
    pub(crate) fn honest() -> Self {
        Self {
            answer: None,
            status: Some((Mode::Reset, StatusFaults::default())),
            before: quiet(),
        }
    }

    pub(crate) fn answering(exchange: Exchange, outcome: SlowOutcome) -> Self {
        Self {
            answer: Some((exchange, outcome)),
            ..Self::honest()
        }
    }

    pub(crate) fn reading(param: Param, value: ParamValue) -> Self {
        Self::answering(
            Exchange::Read(register(param)),
            SlowOutcome::Read(ParamOutcome::Read(value)),
        )
    }
}

/// Run preflight for joint `n` of the fixture against `drive`: the verdict, and every write submitted.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the fixture's first joint has every cap"
)]
pub(crate) fn run(n: usize, drive: &Drive) -> (Result<(), Refusal>, Vec<(Param, ParamValue)>) {
    let skeleton = skeleton();
    let target = match Target::new(&joint(&skeleton, n), &skeleton.power) {
        Ok(target) => target,
        Err(refusal) => return (Err(refusal), Vec::new()),
    };
    let mut now = 1_000;
    let mut preflight = Preflight::start(target, SLOT, 1, now);
    let mut view = drive.before;
    let mut written = Vec::new();
    for _ in 0..32 {
        now += PERIOD;
        // The row's views are drive 101's; joint `n`'s drive may have another ID.
        view.device = target.drive().id();
        let request = match preflight.poll(shown(&view), now) {
            Step::Submit(request) => request,
            Step::Passed(passed) => {
                assert_eq!(passed.drive(), target.drive());
                assert_eq!(
                    preflight.poll(shown(&view), now),
                    Step::Spent,
                    "proof given once"
                );
                return (Ok(()), written);
            }
            Step::Refused(refusal) => return (Err(refusal), written),
            step @ (Step::Wait | Step::Spent) => return (Err(refusal_for(&step)), written),
        };
        assert_eq!(
            preflight.poll(shown(&view), now),
            Step::Wait,
            "one request at a time"
        );
        assert_eq!(request.slot, SLOT, "its drive's slot");
        let kind = request.kind;
        let truth = match kind {
            SlowKind::GetId => SlowOutcome::Identity(UID),
            SlowKind::Write(w) => {
                written.push((w.param(), w.value()));
                SlowOutcome::WriteAnswered
            }
            SlowKind::Read(param) => SlowOutcome::Read(ParamOutcome::Read(match param {
                Param::CanTimeout => ParamValue::CanTimeout(CanTimeout::RUNTIME),
                Param::Damper => ParamValue::Damper(Damper::ProtectionOn),
                Param::Vbus => ParamValue::Volts(Volts::new(24.0).unwrap()),
                _ => written.iter().find(|(p, _)| *p == param).unwrap().1,
            })),
        };
        let outcome = match drive.answer {
            Some((exchange, outcome)) if exchange == exchange_of(kind) => outcome,
            Some(_) | None => truth,
        };
        if let (SlowKind::Write(_), Some((mode, faults))) = (kind, drive.status) {
            view = DriveView {
                fault_seen: view.fault_seen || !faults.is_empty(),
                ..seen(status(mode, faults, now + 500_000))
            };
        }
        preflight.answered(answer(request, outcome), now);
    }
    unreachable_end()
}

#[expect(
    clippy::panic,
    reason = "test helper; a preflight that never ends fails the test"
)]
fn unreachable_end() -> ! {
    panic!("preflight never ended")
}

#[expect(
    clippy::panic,
    reason = "test helper; a stuck preflight fails the test"
)]
fn refusal_for(step: &Step) -> Refusal {
    panic!("preflight stuck at {step:?}")
}

pub(crate) fn volts(v: f64) -> ParamValue {
    ParamValue::Volts(Volts::new(v).unwrap_or_else(|| refusal_volts(v)))
}

#[expect(clippy::panic, reason = "test helper; the rows' voltages are finite")]
fn refusal_volts(v: f64) -> Volts {
    panic!("{v} isn't a voltage")
}

/// The result of `request`, as the bus hands it back.
pub(crate) const fn answer(request: SlowRequest, outcome: SlowOutcome) -> SlowResult {
    SlowResult {
        tag: request.tag,
        slot: request.slot,
        outcome,
    }
}
