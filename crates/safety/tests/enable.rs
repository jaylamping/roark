//! The enable sequence for one drive (PLAN item 2, "Enable one drive"), stepped tick by tick against the views a
//! snapshot would show.

mod common;

use can::SlowKind;
use can::{DriveView, LimbState, LimbView, Observed, StopReason};
use common::{BUS0, IDLE, echoed, joint, on, quiet, seen, shown, skeleton, status};
use robstride::{
    CanTimeout, Damper, EchoKind, Mode, Param, ParamOutcome, ParamValue, Reporting, RunMode,
    StatusFault, StatusFaults, Uid, Volts, Write, encode,
};
use safety::{
    DriveAddress, EnableFailure, Enabling, Next, Preflight, PreflightPassed, RUN_WITHIN_NS, RuleId,
    Step, Target,
};

/// The default tick (`can::Timing`'s at PLAN item 3's 250 Hz).
const PERIOD: u64 = can::Timing::at_hz(250).period_ns;

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
        match preflight.poll(shown(&view), now) {
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
    let _ = enabling.step(shown(&quiet()), 0, t0);
    let _ = enabling.step(shown(&echo), 1, t0 + PERIOD);
    let _ = enabling.step(shown(&echo), 2, t0 + 2 * PERIOD);
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
    assert_eq!(enabling.step(shown(&run), 3, mit_at), mit_write());
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

/// `view` with `fresh` as the drive's fresh status, whatever its latest is.
fn fresh_was(view: DriveView, fresh: Observed) -> DriveView {
    DriveView {
        fresh_ns: Some(fresh.read_ns),
        fresh_status: Some(fresh),
        ..view
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
        enabling.step(shown(&view), 100, t0),
        Next::Send(encode::active_reporting(id, Reporting::Off))
    );
    assert!(!enabling.enable_planned());
    let stale = echoed(view, EchoKind::Reporting(Reporting::Off), t0 - 1);
    assert_eq!(
        enabling.step(shown(&stale), 101, t0 + PERIOD),
        Next::Wait,
        "an older echo"
    );
    let other = echoed(view, EchoKind::Enable, t0 + PERIOD);
    assert_eq!(
        enabling.step(shown(&other), 101, t0 + PERIOD),
        Next::Wait,
        "another frame's echo"
    );
    let echo = echoed(view, EchoKind::Reporting(Reporting::Off), t0 + PERIOD + 10);
    assert_eq!(
        enabling.step(shown(&echo), 102, t0 + 2 * PERIOD),
        Next::Wait,
        "the echo's tick"
    );
    assert_eq!(
        enabling.step(shown(&echo), 102, t0 + 2 * PERIOD),
        Next::Wait,
        "that tick again"
    );
    let enable_at = t0 + 3 * PERIOD;
    assert_eq!(
        enabling.step(shown(&echo), 103, enable_at),
        Next::Send(encode::enable(id)),
        "one tick after the echo"
    );
    assert!(enabling.enable_planned());
    let before = with_status(echo, Mode::Run, enable_at - 1);
    assert_eq!(
        enabling.step(shown(&before), 104, enable_at + PERIOD),
        Next::Wait,
        "a Run from before"
    );
    let reset = with_status(echo, Mode::Reset, enable_at + 1);
    assert_eq!(
        enabling.step(shown(&reset), 105, enable_at + 2 * PERIOD),
        Next::Wait
    );
    let not_fresh = fresh_was(
        with_status(echo, Mode::Run, enable_at + 2),
        status(Mode::Run, StatusFaults::default(), enable_at - 1),
    );
    assert_eq!(
        enabling.step(shown(&not_fresh), 105, enable_at + 2 * PERIOD),
        Next::Wait,
        "a Run that answers nothing since the Enable"
    );
    let run = with_status(echo, Mode::Run, enable_at + 2);
    let mit_at = enable_at + 3 * PERIOD;
    assert_eq!(
        enabling.step(shown(&run), 106, mit_at),
        Next::Send(encode::param_write(&Write::mit_mode(drive)))
    );
    assert_eq!(
        enabling.step(shown(&run), 107, mit_at + PERIOD),
        Next::Wait,
        "the MIT write not yet read back"
    );
    let early = echoed(run, MIT, mit_at - 1);
    assert_eq!(
        enabling.step(shown(&early), 108, mit_at + 2 * PERIOD),
        Next::Wait,
        "an MIT echo from before"
    );
    let mit = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&mit), 109, mit_at + 3 * PERIOD),
        Next::Wait,
        "the echo alone: the frame reached the controller, not the drive"
    );
    let answered = echoed(with_status(run, Mode::Run, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&answered), 110, mit_at + 4 * PERIOD),
        Next::Enabled
    );
    assert!(enabling.enable_planned());
    assert_eq!(
        enabling.step(shown(&answered), 111, mit_at + 5 * PERIOD),
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
        slow.step(shown(&reset), 3, enable_at + RUN_WITHIN_NS),
        Next::Wait,
        "at 50 ms"
    );
    let (mut on_time, _) = to_enable(t0);
    let run = with_status(echo, Mode::Run, enable_at + RUN_WITHIN_NS);
    assert_eq!(
        on_time.step(shown(&run), 3, enable_at + RUN_WITHIN_NS),
        mit_write()
    );
    let failed = Next::Failed(EnableFailure::NoRun {
        last: Some(Mode::Reset),
    });
    assert_eq!(
        slow.step(shown(&reset), 4, enable_at + RUN_WITHIN_NS + 1),
        failed
    );
    assert_eq!(
        slow.step(shown(&run), 5, enable_at + RUN_WITHIN_NS + PERIOD),
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
        late.step(shown(&late_run), 3, enable_at + RUN_WITHIN_NS + 1),
        Next::Failed(too_late)
    );
    assert_eq!(
        too_late.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after its Enable \
         answered it in Run"
    );

    let mut deaf = Enabling::new(passed(), t0);
    let _ = deaf.step(shown(&quiet()), 0, t0);
    assert_eq!(
        deaf.step(shown(&quiet()), 1, t0 + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        deaf.step(shown(&quiet()), 2, t0 + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoEcho)
    );
    assert!(!deaf.enable_planned(), "nothing to stop");
    let mut slow_echo = Enabling::new(passed(), t0);
    let _ = slow_echo.step(shown(&quiet()), 0, t0);
    let late_echo = echoed(
        quiet(),
        EchoKind::Reporting(Reporting::Off),
        t0 + RUN_WITHIN_NS + 1,
    );
    assert_eq!(
        slow_echo.step(shown(&late_echo), 1, t0 + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoEcho),
        "an echo read after its window"
    );
    assert_eq!(EnableFailure::NoEcho.rule(), RuleId::HostBus);

    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut faulted, _) = to_enable(t0);
    let fault = seen(status(Mode::Reset, over, enable_at + 1));
    assert_eq!(
        faulted.step(shown(&fault), 3, enable_at + PERIOD),
        Next::Failed(EnableFailure::Faults { bits: over })
    );
    assert!(faulted.enable_planned());
    let mut latched = Enabling::new(passed(), t0);
    let fault_seen = DriveView {
        fault_seen: true,
        ..quiet()
    };
    assert_eq!(
        latched.step(shown(&fault_seen), 0, t0),
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
    assert_eq!(
        deaf.step(shown(&run), 4, mit_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        deaf.step(shown(&run), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoModeEcho)
    );
    assert!(deaf.enable_planned(), "so the limb is stopped");

    let (mut late, run, mit_at) = to_mit(t0);
    let late_echo = echoed(run, MIT, mit_at + RUN_WITHIN_NS + 1);
    assert_eq!(
        late.step(shown(&late_echo), 4, mit_at + RUN_WITHIN_NS + 1),
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
        on_time.step(shown(&echo), 4, mit_at + RUN_WITHIN_NS),
        Next::Enabled,
        "at 50 ms"
    );
    assert_eq!(EnableFailure::NoModeEcho.rule(), RuleId::HostBus);

    // Echoed, but the drive answered in Reset, or not at all.
    let (mut dropped, run, mit_at) = to_mit(t0);
    let reset = echoed(with_status(run, Mode::Reset, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        dropped.step(shown(&reset), 4, mit_at + PERIOD),
        Next::Failed(EnableFailure::LeftRun {
            last: Some(Mode::Reset)
        })
    );
    assert!(dropped.enable_planned());
    // A Reset seen after the write that isn't the fresh status: the drive left Run, and the sequence ends at once.
    let (mut seen_left, run, mit_at) = to_mit(t0);
    let left_run = DriveView {
        fresh_status: None,
        ..with_status(run, Mode::Reset, mit_at + 20)
    };
    assert_eq!(
        seen_left.step(shown(&left_run), 4, mit_at + PERIOD),
        Next::Failed(EnableFailure::LeftRun {
            last: Some(Mode::Reset)
        })
    );
    let (mut silent, run, mit_at) = to_mit(t0);
    let echo_only = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        silent.step(shown(&echo_only), 4, mit_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        silent.step(shown(&echo_only), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::LeftRun { last: None })
    );
    assert_eq!(
        EnableFailure::LeftRun { last: None }.rule(),
        RuleId::HostMode
    );
}

/// Guards: safety - `host.mode`: a status answers one frame, and only the fresh one: a later status that contradicts a
/// fresh Run takes it back, a later duplicate or report that agrees leaves it, a later Run doesn't stand in for a fresh
/// Reset, and the Run that answered the Enable never also answers the `run_mode` = MIT write, however the ticks fall
/// (PLAN item 2, Enable one drive).
#[test]
fn a_status_answers_one_frame_until_a_later_one_contradicts_it() {
    let t0 = 100 * PERIOD;
    let enable_at = t0 + 2 * PERIOD;

    // A fresh Reset, then a Run that answers nothing: no Run answered the Enable.
    let (mut enabling, echo) = to_enable(t0);
    let reset_then_run = fresh_was(
        with_status(echo, Mode::Run, enable_at + 2),
        status(Mode::Reset, StatusFaults::default(), enable_at + 1),
    );
    assert_eq!(
        enabling.step(shown(&reset_then_run), 3, enable_at + PERIOD),
        Next::Wait
    );
    assert_eq!(
        enabling.step(shown(&reset_then_run), 4, enable_at + RUN_WITHIN_NS + 1),
        Next::Failed(EnableFailure::NoRun {
            last: Some(Mode::Run)
        })
    );

    // A fresh Run, then a Reset that answers nothing: the Run is no longer the drive's word.
    let (mut enabling, echo) = to_enable(t0);
    let run_then_reset = fresh_was(
        with_status(echo, Mode::Reset, enable_at + 2),
        status(Mode::Run, StatusFaults::default(), enable_at + 1),
    );
    assert_eq!(
        enabling.step(shown(&run_then_reset), 3, enable_at + PERIOD),
        Next::Wait
    );

    // A fresh Run, then a duplicate Run: the answer stands, and the sequence goes on to the write.
    let (mut enabling, echo) = to_enable(t0);
    let run_then_run = fresh_was(
        with_status(echo, Mode::Run, enable_at + 2),
        status(Mode::Run, StatusFaults::default(), enable_at + 1),
    );
    assert_eq!(
        enabling.step(shown(&run_then_run), 3, enable_at + PERIOD),
        mit_write()
    );

    // The write's answer, then a duplicate Run read after it: still enabled, not a failure after 50 ms.
    let (mut enabling, echo, mit_at) = to_mit(t0);
    let answered = echoed(
        fresh_was(
            with_status(echo, Mode::Run, mit_at + 20),
            status(Mode::Run, StatusFaults::default(), mit_at + 10),
        ),
        MIT,
        mit_at + 5,
    );
    assert_eq!(
        enabling.step(shown(&answered), 5, mit_at + PERIOD),
        Next::Enabled
    );

    // The Enable's Run read at the very moment the MIT write is planned, then the write's echo and no further status.
    let (mut enabling, echo) = to_enable(t0);
    let mit_at = enable_at + PERIOD;
    let run = with_status(echo, Mode::Run, mit_at);
    assert_eq!(enabling.step(shown(&run), 3, mit_at), mit_write());
    let only_echo = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&only_echo), 4, mit_at + PERIOD),
        Next::Wait,
        "the Enable's answer doesn't answer the write"
    );
    let left = EnableFailure::LeftRun {
        last: Some(Mode::Run),
    };
    assert_eq!(
        enabling.step(shown(&only_echo), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Failed(left)
    );
    assert!(enabling.enable_planned());
    assert_eq!(
        left.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after the run_mode = \
         MIT write answered it in Run"
    );
}

/// Guards: safety - `host.preflight`: at every step the sequence checks it is stepped with its own drive on its own
/// bus, and that the drive's limb hasn't stopped or been cleared since preflight. Another drive's view (another ID, or
/// the same ID on another bus) ends it as a runtime bug, and a stopped or cleared limb ends it even where the drive's
/// own replies would have enabled it; after the Enable, with the limb to stop (PLAN item 6 Preflight row).
#[test]
fn the_enable_sequence_ends_on_another_drives_view_or_a_stopped_limb() {
    let t0 = 100 * PERIOD;
    let ours = DriveAddress::new(&BUS0, common::id(101)).unwrap();

    let (mut enabling, echo) = to_enable(t0);
    let wrong = DriveView {
        device: common::id(102),
        ..echo
    };
    let failure = EnableFailure::WrongView {
        view: DriveAddress::new(&BUS0, common::id(102)).unwrap(),
        drive: ours,
    };
    assert_eq!(
        enabling.step(shown(&wrong), 3, t0 + 3 * PERIOD),
        Next::Failed(failure)
    );
    assert!(enabling.enable_planned());
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one was stepped with drive 102 on bus0's view, expected drive 101 \
         on bus0's"
    );

    // Drive 101 on another bus is another drive.
    let (mut enabling, echo) = to_enable(t0);
    let bus1 = common::bus(1);
    let elsewhere = on(&bus1, &echo, &IDLE);
    let failure = EnableFailure::WrongView {
        view: DriveAddress::new(&bus1, common::id(101)).unwrap(),
        drive: ours,
    };
    assert_eq!(
        enabling.step(elsewhere, 3, t0 + 3 * PERIOD),
        Next::Failed(failure)
    );
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one was stepped with drive 101 on bus1's view, expected drive 101 \
         on bus0's"
    );

    // The write echoed and answered in Run, but the limb began stopping: not enabled.
    let (mut enabling, run, mit_at) = to_mit(t0);
    let answered = echoed(with_status(run, Mode::Run, mit_at + 20), MIT, mit_at + 10);
    let stop = Some(StopReason::DriveFault { slot: 1 });
    let stopping = LimbView {
        state: LimbState::Stopping {
            since_ns: mit_at + 5,
        },
        stop,
        ..IDLE
    };
    let on_stopping = on(&BUS0, &answered, &stopping);
    let failure = EnableFailure::LimbStopped { stop };
    assert_eq!(
        enabling.step(on_stopping, 4, mit_at + PERIOD),
        Next::Failed(failure)
    );
    assert!(enabling.enable_planned(), "so the limb is stopped");
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one found its limb stopped or cleared since its preflight \
         (host.fault: DriveFault { slot: 1 }), expected it running"
    );

    // Stopped and cleared since preflight, before the Enable: idle again, but the proof is void.
    let mut enabling = Enabling::new(passed(), t0);
    let cleared = LimbView {
        generation: IDLE.generation + 1,
        ..IDLE
    };
    let view = quiet();
    let on_cleared = on(&BUS0, &view, &cleared);
    assert_eq!(
        enabling.step(on_cleared, 0, t0),
        Next::Failed(EnableFailure::LimbStopped { stop: None })
    );
    assert!(!enabling.enable_planned(), "nothing to stop");
}
