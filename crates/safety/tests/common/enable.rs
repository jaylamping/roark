//! The enable sequence's shared steps: a preflight pass, the sequence stepped to its Enable or its `run_mode` = MIT
//! write, and the views those steps read.

use can::{DriveView, Observed, SlowKind};
use robstride::{
    CanTimeout, Damper, EchoKind, Mode, Param, ParamOutcome, ParamValue, Reporting, RunMode,
    StatusFaults, Uid, Volts, Write, encode,
};
use safety::{Enabling, Next, Preflight, PreflightPassed, Step, Target};

use super::{echoed, joint, quiet, seen, shown, skeleton, status, status_of};

/// The default tick (`can::Timing`'s at PLAN item 3's 250 Hz).
pub(crate) const PERIOD: u64 = can::Timing::at_hz(250).period_ns;

/// When [`passed`]'s preflight begins.
pub(crate) const PREFLIGHT_AT: u64 = 1_000;

/// A preflight pass for the fixture's first joint: [`passed_for`] joint 0.
pub(crate) fn passed() -> PreflightPassed {
    passed_for(0)
}

/// A preflight pass for the fixture's joint `n`, begun at [`PREFLIGHT_AT`], run against a truthful drive.
#[expect(
    clippy::unwrap_used,
    clippy::panic,
    reason = "test helper; the fixture's first joint passes"
)]
pub(crate) fn passed_for(n: usize) -> PreflightPassed {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, n), &skeleton.power).unwrap();
    let device = target.drive().id();
    let mut preflight = Preflight::start(target, 0, 1, PREFLIGHT_AT);
    let mut view = DriveView { device, ..quiet() };
    let mut written = Vec::new();
    for n in 1..32 {
        let now = n * PERIOD;
        match preflight.poll(shown(&view).seen(), now) {
            Step::Submit(request) => {
                let outcome = match request.kind {
                    SlowKind::GetId => can::SlowOutcome::Identity(Uid([
                        0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
                    ])),
                    SlowKind::Write(w) => {
                        written.push(w);
                        view = seen(status_of(device, Mode::Reset, StatusFaults::default(), now));
                        can::SlowOutcome::WriteAnswered
                    }
                    SlowKind::Probe(_) | SlowKind::SetId { .. } => {
                        panic!("preflight asks only its own drive")
                    }
                    SlowKind::Read(p) => can::SlowOutcome::Read(ParamOutcome::Read(match p {
                        Param::CanTimeout => ParamValue::CanTimeout(CanTimeout::RUNTIME),
                        Param::Damper => ParamValue::Damper(Damper::ProtectionOn),
                        Param::Vbus => ParamValue::Volts(Volts::new(24.0).unwrap()),
                        _ => written
                            .iter()
                            .find(|w: &&Write| w.param() == p)
                            .unwrap()
                            .value(),
                    })),
                };
                preflight.answered(
                    can::SlowResult {
                        tag: request.tag,
                        slot: request.slot,
                        outcome,
                    },
                    now,
                );
            }
            Step::Passed(passed) => return passed,
            step => panic!("{step:?}"),
        }
    }
    panic!("preflight never passed")
}

/// The sequence for the fixture's first joint begun at `t0`, stepped through tick `t0`'s reporting off and the echo
/// read in the next tick, to the Enable planned at `t0 + 2 periods`; and the view of the Enable's echo, read
/// [`ECHO_NS`] after that.
pub(crate) fn to_enable(t0: u64) -> (Enabling, DriveView) {
    let mut enabling = Enabling::new(passed(), t0);
    let echo = echoed(quiet(), EchoKind::Reporting(Reporting::Off), t0 + 10);
    let _ = enabling.step(shown(&quiet()).seen(), 0, t0);
    let _ = enabling.step(shown(&echo).seen(), 1, t0 + PERIOD);
    let enable_at = t0 + 2 * PERIOD;
    assert_eq!(
        enabling.step(shown(&echo).seen(), 2, enable_at),
        Next::Send(encode::enable(joint(&skeleton(), 0).id))
    );
    (
        enabling,
        echoed(quiet(), EchoKind::Enable, enable_at + ECHO_NS),
    )
}

/// How long after the Enable is planned [`to_enable`]'s view reads its echo.
pub(crate) const ECHO_NS: u64 = 100_000;

/// The echo of the `run_mode` = MIT write.
pub(crate) const MIT: EchoKind = EchoKind::ParamWrite {
    param: Param::RunMode,
    value: ParamValue::RunMode(RunMode::Mit),
};

/// [`to_enable`] carried on: a Run read just after the Enable's echo, and the MIT write planned in the tick after it, at
/// the returned time; and that Run's view.
pub(crate) fn to_mit(t0: u64) -> (Enabling, DriveView, u64) {
    let (mut enabling, echo) = to_enable(t0);
    let enable_at = t0 + 2 * PERIOD;
    let run = with_status(echo, Mode::Run, enable_at + ECHO_NS + 1);
    let mit_at = enable_at + PERIOD;
    assert_eq!(enabling.step(shown(&run).seen(), 3, mit_at), mit_write());
    (enabling, run, mit_at)
}

/// The `run_mode` = MIT write to the fixture's first joint.
pub(crate) fn mit_write() -> Next {
    let drive = robstride::Drive::new(joint(&skeleton(), 0).id, robstride::Model::Rs03);
    Next::Send(encode::param_write(&Write::mit_mode(drive)))
}

/// `echo` with a status in `mode` read at `read_ns`.
pub(crate) fn with_status(echo: DriveView, mode: Mode, read_ns: u64) -> DriveView {
    DriveView {
        last_echo: echo.last_echo,
        ..seen(status(mode, StatusFaults::default(), read_ns))
    }
}

/// `view` with `fresh` as the drive's fresh status, and a later status in the same mode as its latest.
pub(crate) fn fresh_was(view: DriveView, fresh: Observed) -> DriveView {
    DriveView {
        fresh_ns: Some(fresh.read_ns),
        fresh_status: Some(fresh),
        ..view
    }
}

/// `view` with a fresh status read at `fresh_ns` that a later frame in another mode superseded: the bus keeps its time
/// and drops it.
pub(crate) fn superseded(view: DriveView, fresh_ns: u64) -> DriveView {
    DriveView {
        fresh_ns: Some(fresh_ns),
        fresh_status: None,
        ..view
    }
}
