//! The enable sequence for one drive (PLAN item 2, "Enable one drive"), stepped tick by tick against the views a
//! snapshot would show.

mod common;

use can::DriveView;
use can::SlowKind;
use common::{echoed, joint, quiet, seen, skeleton, status};
use robstride::{
    CanTimeout, Damper, EchoKind, Mode, Param, ParamOutcome, ParamValue, Reporting, StatusFault,
    StatusFaults, Uid, Volts, Write, encode,
};
use safety::{
    EnableFailure, Enabling, Next, Preflight, PreflightPassed, RUN_WITHIN_NS, RuleId, Step, Target,
};

const PERIOD: u64 = 4_000_000;

/// A preflight pass for the fixture's first joint, run against a truthful drive.
#[expect(
    clippy::unwrap_used,
    clippy::panic,
    reason = "test helper; the fixture's first joint passes"
)]
fn passed() -> PreflightPassed {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let mut preflight = Preflight::start(target, 0);
    let mut view = quiet();
    let mut written = Vec::new();
    for n in 1..32 {
        let now = n * PERIOD;
        match preflight.poll(&view, now) {
            Step::Submit(kind) => {
                let outcome = match kind {
                    SlowKind::GetId => can::SlowOutcome::Identity(Uid([
                        0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
                    ])),
                    SlowKind::Write(w) => {
                        written.push(w);
                        view = seen(status(Mode::Reset, StatusFaults::default(), now));
                        can::SlowOutcome::WriteAnswered
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
                preflight.answered(outcome);
            }
            Step::Passed(passed) => return passed,
            step => panic!("{step:?}"),
        }
    }
    panic!("preflight never passed")
}

/// The sequence for the fixture's first joint begun at `t0`, stepped through tick `t0`'s reporting off and the echo
/// read in the next tick, to the Enable planned at `t0 + 2 periods`; and that echo's view.
fn to_enable(t0: u64) -> (Enabling, DriveView) {
    let mut enabling = Enabling::new(passed(), t0);
    let echo = echoed(quiet(), EchoKind::Reporting(Reporting::Off), t0 + 10);
    let _ = enabling.step(&quiet(), 0, t0);
    let _ = enabling.step(&echo, 1, t0 + PERIOD);
    let _ = enabling.step(&echo, 2, t0 + 2 * PERIOD);
    assert!(enabling.enable_planned());
    (enabling, echo)
}

/// `echo` with a status in `mode` read at `read_ns`.
fn with_status(echo: DriveView, mode: Mode, read_ns: u64) -> DriveView {
    DriveView {
        last_echo: echo.last_echo,
        ..seen(status(mode, StatusFaults::default(), read_ns))
    }
}

/// Guards: protocol - the enable sequence runs PLAN item 2's steps in order, one per tick: reporting off, its echo
/// read back plus one tick, Enable, a Run status, then `run_mode` = MIT; only then is the drive enabled, so no MIT frame
/// goes before Run is seen. An echo or a Run read before its step was planned doesn't count.
#[test]
fn the_enable_sequence_runs_its_steps_in_order() {
    let id = joint(&skeleton(), 0).id;
    let drive = robstride::Drive::new(id, robstride::Model::Rs03);
    let t0 = 100 * PERIOD;
    let mut enabling = Enabling::new(passed(), t0);
    assert_eq!(enabling.drive(), drive);
    let view = quiet();
    assert_eq!(
        enabling.step(&view, 100, t0),
        Next::Send(encode::active_reporting(id, Reporting::Off))
    );
    assert!(!enabling.enable_planned());
    let stale = echoed(view, EchoKind::Reporting(Reporting::Off), t0 - 1);
    assert_eq!(
        enabling.step(&stale, 101, t0 + PERIOD),
        Next::Wait,
        "an older echo"
    );
    let other = echoed(view, EchoKind::Enable, t0 + PERIOD);
    assert_eq!(
        enabling.step(&other, 101, t0 + PERIOD),
        Next::Wait,
        "another frame's echo"
    );
    let echo = echoed(view, EchoKind::Reporting(Reporting::Off), t0 + PERIOD + 10);
    assert_eq!(
        enabling.step(&echo, 102, t0 + 2 * PERIOD),
        Next::Wait,
        "the echo's tick"
    );
    assert_eq!(
        enabling.step(&echo, 102, t0 + 2 * PERIOD),
        Next::Wait,
        "that tick again"
    );
    let enable_at = t0 + 3 * PERIOD;
    assert_eq!(
        enabling.step(&echo, 103, enable_at),
        Next::Send(encode::enable(id)),
        "one tick after the echo"
    );
    assert!(enabling.enable_planned());
    let before = with_status(echo, Mode::Run, enable_at - 1);
    assert_eq!(
        enabling.step(&before, 104, enable_at + PERIOD),
        Next::Wait,
        "a Run from before"
    );
    let reset = with_status(echo, Mode::Reset, enable_at + 1);
    assert_eq!(
        enabling.step(&reset, 105, enable_at + 2 * PERIOD),
        Next::Wait
    );
    let run = with_status(echo, Mode::Run, enable_at + 2);
    assert_eq!(
        enabling.step(&run, 106, enable_at + 3 * PERIOD),
        Next::Send(encode::param_write(&Write::mit_mode(drive)))
    );
    assert_eq!(
        enabling.step(&run, 107, enable_at + 4 * PERIOD),
        Next::Enabled
    );
}

/// Guards: safety - `host.mode` and `host.fault`: a drive that shows no Run status within 50 ms of its Enable being
/// planned, or a fault at any step, ends the sequence; after the Enable the limb must be stopped, before it only
/// refused. A reporting off never read back gives up within 50 ms too, before any Enable (PLAN item 2: refuse after
/// 50 ms).
#[test]
fn the_enable_sequence_gives_up_on_no_run_or_a_fault() {
    let t0 = 100 * PERIOD;
    let enable_at = t0 + 2 * PERIOD;
    let (mut slow, echo) = to_enable(t0);
    let reset = with_status(echo, Mode::Reset, enable_at + 1);
    assert_eq!(
        slow.step(&reset, 3, enable_at + RUN_WITHIN_NS),
        Next::Wait,
        "at 50 ms"
    );
    let (mut on_time, _) = to_enable(t0);
    let run = with_status(echo, Mode::Run, enable_at + RUN_WITHIN_NS);
    assert!(matches!(
        on_time.step(&run, 3, enable_at + RUN_WITHIN_NS),
        Next::Send(_)
    ));
    let failed = Next::Failed(EnableFailure::NoRun {
        last: Some(Mode::Reset),
    });
    assert_eq!(slow.step(&reset, 4, enable_at + RUN_WITHIN_NS + 1), failed);
    assert_eq!(
        slow.step(&run, 5, enable_at + RUN_WITHIN_NS + PERIOD),
        failed,
        "it stays given up"
    );
    assert!(slow.enable_planned(), "so the limb is stopped");
    assert_eq!(EnableFailure::NoRun { last: None }.rule(), RuleId::HostMode);

    let mut deaf = Enabling::new(passed(), t0);
    let _ = deaf.step(&quiet(), 0, t0);
    assert_eq!(deaf.step(&quiet(), 1, t0 + RUN_WITHIN_NS), Next::Wait);
    assert_eq!(
        deaf.step(&quiet(), 2, t0 + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoEcho)
    );
    assert!(!deaf.enable_planned(), "nothing to stop");

    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut faulted, _) = to_enable(t0);
    let fault = DriveView {
        fault_seen: false,
        ..seen(status(Mode::Reset, over, enable_at + 1))
    };
    assert_eq!(
        faulted.step(&fault, 3, enable_at + PERIOD),
        Next::Failed(EnableFailure::Faults { bits: over })
    );
    assert!(faulted.enable_planned());
    let mut latched = Enabling::new(passed(), t0);
    let fault_seen = DriveView {
        fault_seen: true,
        ..quiet()
    };
    assert_eq!(
        latched.step(&fault_seen, 0, t0),
        Next::Failed(EnableFailure::Faults {
            bits: StatusFaults::default()
        })
    );
    assert!(!latched.enable_planned());
    assert_eq!(
        EnableFailure::Faults { bits: over }.rule(),
        RuleId::HostFault
    );
}
