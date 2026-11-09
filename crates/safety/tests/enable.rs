//! The enable sequence for one drive (PLAN item 2, "Enable one drive"), stepped tick by tick against the views a
//! snapshot would show.

mod common;

use can::DriveView;
use can::SlowKind;
use common::{echoed, joint, quiet, seen, skeleton, status};
use robstride::{
    CanTimeout, Damper, EchoKind, Mode, Param, ParamOutcome, ParamValue, Reporting, RunMode,
    StatusFault, StatusFaults, Uid, Volts, Write, encode,
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
                preflight.answered(outcome, now);
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

/// The echo of the `run_mode` = MIT write.
const MIT: EchoKind = EchoKind::ParamWrite {
    param: Param::RunMode,
    value: ParamValue::RunMode(RunMode::Mit),
};

/// [`to_enable`] carried on: a Run read just after the Enable, and the MIT write planned in the tick after it, at the
/// returned time; and that Run's view.
fn to_mit(t0: u64) -> (Enabling, DriveView, u64) {
    let (mut enabling, echo) = to_enable(t0);
    let enable_at = t0 + 2 * PERIOD;
    let run = with_status(echo, Mode::Run, enable_at + 1);
    let mit_at = enable_at + PERIOD;
    assert_eq!(enabling.step(&run, 3, mit_at), mit_write());
    (enabling, run, mit_at)
}

/// The `run_mode` = MIT write to the fixture's first joint.
fn mit_write() -> Next {
    let drive = robstride::Drive::new(joint(&skeleton(), 0).id, robstride::Model::Rs03);
    Next::Send(encode::param_write(&Write::mit_mode(drive)))
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
    let not_fresh = DriveView {
        fresh_ns: Some(enable_at - 1),
        ..with_status(echo, Mode::Run, enable_at + 2)
    };
    assert_eq!(
        enabling.step(&not_fresh, 105, enable_at + 2 * PERIOD),
        Next::Wait,
        "a Run that answers nothing since the Enable"
    );
    let run = with_status(echo, Mode::Run, enable_at + 2);
    let mit_at = enable_at + 3 * PERIOD;
    assert_eq!(
        enabling.step(&run, 106, mit_at),
        Next::Send(encode::param_write(&Write::mit_mode(drive)))
    );
    assert_eq!(
        enabling.step(&run, 107, mit_at + PERIOD),
        Next::Wait,
        "the MIT write not yet read back"
    );
    let early = echoed(run, MIT, mit_at - 1);
    assert_eq!(
        enabling.step(&early, 108, mit_at + 2 * PERIOD),
        Next::Wait,
        "an MIT echo from before"
    );
    let mit = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(&mit, 109, mit_at + 3 * PERIOD),
        Next::Wait,
        "the echo alone: the frame reached the controller, not the drive"
    );
    let answered = echoed(with_status(run, Mode::Run, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        enabling.step(&answered, 110, mit_at + 4 * PERIOD),
        Next::Enabled
    );
    assert!(enabling.enable_planned());
    assert_eq!(
        enabling.step(&answered, 111, mit_at + 5 * PERIOD),
        Next::Enabled,
        "it stays enabled"
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
    assert_eq!(
        on_time.step(&run, 3, enable_at + RUN_WITHIN_NS),
        mit_write()
    );
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
    // A Run read after its window, however the ticks fall, is too late.
    let (mut late, _) = to_enable(t0);
    let late_run = with_status(echo, Mode::Run, enable_at + RUN_WITHIN_NS + 1);
    let too_late = EnableFailure::NoRun {
        last: Some(Mode::Run),
    };
    assert_eq!(
        late.step(&late_run, 3, enable_at + RUN_WITHIN_NS + 1),
        Next::Failed(too_late)
    );
    assert_eq!(
        too_late.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after its Enable \
         answered it in Run"
    );

    let mut deaf = Enabling::new(passed(), t0);
    let _ = deaf.step(&quiet(), 0, t0);
    assert_eq!(deaf.step(&quiet(), 1, t0 + RUN_WITHIN_NS), Next::Wait);
    assert_eq!(
        deaf.step(&quiet(), 2, t0 + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoEcho)
    );
    assert!(!deaf.enable_planned(), "nothing to stop");
    let mut slow_echo = Enabling::new(passed(), t0);
    let _ = slow_echo.step(&quiet(), 0, t0);
    let late_echo = echoed(
        quiet(),
        EchoKind::Reporting(Reporting::Off),
        t0 + RUN_WITHIN_NS + 1,
    );
    assert_eq!(
        slow_echo.step(&late_echo, 1, t0 + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoEcho),
        "an echo read after its window"
    );
    assert_eq!(EnableFailure::NoEcho.rule(), RuleId::HostBus);

    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut faulted, _) = to_enable(t0);
    let fault = seen(status(Mode::Reset, over, enable_at + 1));
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

/// Guards: safety - `host.bus` and `host.mode`: a drive whose `run_mode` = MIT write isn't read back within 50 ms of
/// being planned, or isn't answered by a fresh Run status in that time, is never handed to control: the drive may not
/// be in MIT mode, or has left Run; since its Enable went out the limb is stopped.
#[test]
fn the_enable_sequence_gives_up_without_the_mit_write_echo() {
    let t0 = 100 * PERIOD;
    let (mut deaf, run, mit_at) = to_mit(t0);
    assert_eq!(deaf.step(&run, 4, mit_at + RUN_WITHIN_NS), Next::Wait);
    assert_eq!(
        deaf.step(&run, 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoModeEcho)
    );
    assert!(deaf.enable_planned(), "so the limb is stopped");

    let (mut late, run, mit_at) = to_mit(t0);
    let late_echo = echoed(run, MIT, mit_at + RUN_WITHIN_NS + 1);
    assert_eq!(
        late.step(&late_echo, 4, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoModeEcho),
        "an echo read after its window"
    );
    let (mut on_time, run, mit_at) = to_mit(t0);
    let echo = echoed(
        with_status(run, Mode::Run, mit_at + RUN_WITHIN_NS),
        MIT,
        mit_at + RUN_WITHIN_NS,
    );
    assert_eq!(
        on_time.step(&echo, 4, mit_at + RUN_WITHIN_NS),
        Next::Enabled,
        "at 50 ms"
    );
    assert_eq!(EnableFailure::NoModeEcho.rule(), RuleId::HostBus);

    // Echoed, but the drive answered in Reset, or not at all.
    let (mut dropped, run, mit_at) = to_mit(t0);
    let reset = echoed(with_status(run, Mode::Reset, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        dropped.step(&reset, 4, mit_at + PERIOD),
        Next::Failed(EnableFailure::LeftRun {
            last: Some(Mode::Reset)
        })
    );
    assert!(dropped.enable_planned());
    let (mut silent, run, mit_at) = to_mit(t0);
    let echo_only = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        silent.step(&echo_only, 4, mit_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        silent.step(&echo_only, 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::LeftRun { last: None })
    );
    assert_eq!(
        EnableFailure::LeftRun { last: None }.rule(),
        RuleId::HostMode
    );
}

/// Guards: safety - `host.mode`: a status answers one frame, and only while it is the drive's latest and the fresh one:
/// a later status hides a fresh Run, a later Run doesn't stand in for a fresh Reset, and the Run that answered the
/// Enable never also answers the `run_mode` = MIT write, however the ticks fall (PLAN item 2, Enable one drive).
#[test]
fn a_status_answers_one_frame_while_it_is_the_latest() {
    let t0 = 100 * PERIOD;
    let enable_at = t0 + 2 * PERIOD;

    // A fresh Reset, then a Run that answers nothing: no Run answered the Enable.
    let (mut enabling, echo) = to_enable(t0);
    let reset_then_run = DriveView {
        fresh_ns: Some(enable_at + 1),
        ..with_status(echo, Mode::Run, enable_at + 2)
    };
    assert_eq!(
        enabling.step(&reset_then_run, 3, enable_at + PERIOD),
        Next::Wait
    );
    assert_eq!(
        enabling.step(&reset_then_run, 4, enable_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoRun {
            last: Some(Mode::Run)
        })
    );

    // A fresh Run, then a Reset that answers nothing: the Run is no longer the drive's word.
    let (mut enabling, echo) = to_enable(t0);
    let run_then_reset = DriveView {
        fresh_ns: Some(enable_at + 1),
        ..with_status(echo, Mode::Reset, enable_at + 2)
    };
    assert_eq!(
        enabling.step(&run_then_reset, 3, enable_at + PERIOD),
        Next::Wait
    );

    // The Enable's Run read at the very moment the MIT write is planned, then the write's echo and no further status.
    let (mut enabling, echo) = to_enable(t0);
    let mit_at = enable_at + PERIOD;
    let run = with_status(echo, Mode::Run, mit_at);
    assert_eq!(enabling.step(&run, 3, mit_at), mit_write());
    let only_echo = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(&only_echo, 4, mit_at + PERIOD),
        Next::Wait,
        "the Enable's answer doesn't answer the write"
    );
    let left = EnableFailure::LeftRun {
        last: Some(Mode::Run),
    };
    assert_eq!(
        enabling.step(&only_echo, 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(left)
    );
    assert!(enabling.enable_planned());
    assert_eq!(
        left.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after the run_mode = \
         MIT write answered it in Run"
    );
}

/// Guards: safety - the sequence that hands a drive to control checks it is stepped with that drive's view; another
/// drive's ends it as a runtime bug, after the Enable with the limb to stop (PLAN item 2, Enable one drive).
#[test]
fn the_enable_sequence_refuses_another_drives_view() {
    let t0 = 100 * PERIOD;
    let (mut enabling, echo) = to_enable(t0);
    let other = common::id(102);
    let wrong = DriveView {
        device: other,
        ..echo
    };
    let failure = EnableFailure::WrongView { view: other };
    assert_eq!(
        enabling.step(&wrong, 3, t0 + 3 * PERIOD),
        Next::Failed(failure)
    );
    assert!(enabling.enable_planned());
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one was stepped with drive 102's view"
    );
}
