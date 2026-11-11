//! The enable sequence for one drive (PLAN item 2, "Enable one drive"), stepped tick by tick against the views a
//! snapshot would show: its steps and the replies each waits for.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::DriveView;
use common::enable::{
    ECHO_NS, MIT, PERIOD, fresh_was, mit_write, passed, passed_for, superseded, to_enable, to_mit,
    with_status,
};
use common::{echoed, joint, quiet, seen, shown, skeleton, status};
use robstride::{EchoKind, Mode, Reporting, StatusFault, StatusFaults, Write, encode};
use safety::{EnableFailure, Enabling, Next, RUN_WITHIN_NS, RuleId};
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
        enabling.step(shown(&view).seen(), 100, t0),
        Next::Send(encode::active_reporting(id, Reporting::Off))
    );
    let stale = echoed(view, EchoKind::Reporting(Reporting::Off), t0 - 1);
    assert_eq!(
        enabling.step(shown(&stale).seen(), 101, t0 + PERIOD),
        Next::Wait,
        "an older echo"
    );
    let other = echoed(view, EchoKind::Enable, t0 + PERIOD);
    assert_eq!(
        enabling.step(shown(&other).seen(), 101, t0 + PERIOD),
        Next::Wait,
        "another frame's echo"
    );
    let echo = echoed(view, EchoKind::Reporting(Reporting::Off), t0 + PERIOD + 10);
    assert_eq!(
        enabling.step(shown(&echo).seen(), 102, t0 + 2 * PERIOD),
        Next::Wait,
        "the echo's tick"
    );
    assert_eq!(
        enabling.step(shown(&echo).seen(), 102, t0 + 2 * PERIOD),
        Next::Wait,
        "that tick again"
    );
    let enable_at = t0 + 3 * PERIOD;
    assert_eq!(
        enabling.step(shown(&echo).seen(), 103, enable_at),
        Next::Send(encode::enable(id)),
        "one tick after the echo"
    );
    let sent = echoed(view, EchoKind::Enable, enable_at + 1);
    let before = with_status(sent, Mode::Run, enable_at - 1);
    assert_eq!(
        enabling.step(shown(&before).seen(), 104, enable_at + PERIOD),
        Next::Wait,
        "a Run from before"
    );
    let reset = with_status(sent, Mode::Reset, enable_at + 1);
    assert_eq!(
        enabling.step(shown(&reset).seen(), 105, enable_at + 2 * PERIOD),
        Next::Wait
    );
    let not_fresh = fresh_was(
        with_status(sent, Mode::Run, enable_at + 2),
        status(Mode::Run, StatusFaults::default(), enable_at - 1),
    );
    assert_eq!(
        enabling.step(shown(&not_fresh).seen(), 105, enable_at + 2 * PERIOD),
        Next::Wait,
        "a Run that answers nothing since the Enable"
    );
    let run = with_status(sent, Mode::Run, enable_at + 2);
    let mit_at = enable_at + 3 * PERIOD;
    assert_eq!(
        enabling.step(shown(&run).seen(), 106, mit_at),
        Next::Send(encode::param_write(&Write::mit_mode(drive)))
    );
    assert_eq!(
        enabling.step(shown(&run).seen(), 107, mit_at + PERIOD),
        Next::Wait,
        "the MIT write not yet read back"
    );
    let early = echoed(run, MIT, mit_at - 1);
    assert_eq!(
        enabling.step(shown(&early).seen(), 108, mit_at + 2 * PERIOD),
        Next::Wait,
        "an MIT echo from before"
    );
    let mit = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&mit).seen(), 109, mit_at + 3 * PERIOD),
        Next::Wait,
        "the echo alone: the frame reached the controller, not the drive"
    );
    let answered = echoed(with_status(run, Mode::Run, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&answered).seen(), 110, mit_at + 4 * PERIOD),
        Next::Enabled
    );
    assert_eq!(
        enabling.step(shown(&answered).seen(), 111, mit_at + 5 * PERIOD),
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
        slow.step(shown(&reset).seen(), 3, enable_at + RUN_WITHIN_NS),
        Next::Wait,
        "at 50 ms"
    );
    let (mut on_time, _) = to_enable(t0);
    let run = with_status(echo, Mode::Run, enable_at + RUN_WITHIN_NS);
    assert_eq!(
        on_time.step(shown(&run).seen(), 3, enable_at + RUN_WITHIN_NS),
        mit_write()
    );
    let failed = Next::Stop(EnableFailure::NoRun {
        last: Some(Mode::Reset),
    });
    assert_eq!(
        slow.step(shown(&reset).seen(), 4, enable_at + RUN_WITHIN_NS + 1),
        failed
    );
    assert_eq!(
        slow.step(shown(&run).seen(), 5, enable_at + RUN_WITHIN_NS + PERIOD),
        failed,
        "it stays given up"
    );
    assert_eq!(EnableFailure::NoRun { last: None }.rule(), RuleId::HostMode);
    // A Run read after its window, however the ticks fall, is too late.
    let (mut late, _) = to_enable(t0);
    let late_run = with_status(echo, Mode::Run, enable_at + RUN_WITHIN_NS + 1);
    let too_late = EnableFailure::NoRun {
        last: Some(Mode::Run),
    };
    assert_eq!(
        late.step(shown(&late_run).seen(), 3, enable_at + RUN_WITHIN_NS + 1),
        Next::Stop(too_late)
    );
    assert_eq!(
        too_late.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after its Enable \
         answered it in Run"
    );

    let mut deaf = Enabling::new(passed(), t0);
    let _ = deaf.step(shown(&quiet()).seen(), 0, t0);
    assert_eq!(
        deaf.step(shown(&quiet()).seen(), 1, t0 + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        deaf.step(shown(&quiet()).seen(), 2, t0 + RUN_WITHIN_NS + 1),
        Next::Refused(EnableFailure::NoEcho)
    );
    let mut slow_echo = Enabling::new(passed(), t0);
    let _ = slow_echo.step(shown(&quiet()).seen(), 0, t0);
    let late_echo = echoed(
        quiet(),
        EchoKind::Reporting(Reporting::Off),
        t0 + RUN_WITHIN_NS + 1,
    );
    assert_eq!(
        slow_echo.step(shown(&late_echo).seen(), 1, t0 + RUN_WITHIN_NS + 1),
        Next::Refused(EnableFailure::NoEcho),
        "an echo read after its window"
    );
    assert_eq!(EnableFailure::NoEcho.rule(), RuleId::HostBus);

    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut faulted, _) = to_enable(t0);
    let fault = seen(status(Mode::Reset, over, enable_at + 1));
    assert_eq!(
        faulted.step(shown(&fault).seen(), 3, enable_at + PERIOD),
        Next::Stop(EnableFailure::Faults { bits: over })
    );
    let mut latched = Enabling::new(passed(), t0);
    let fault_seen = DriveView {
        fault_seen: true,
        ..quiet()
    };
    assert_eq!(
        latched.step(shown(&fault_seen).seen(), 0, t0),
        Next::Refused(EnableFailure::Faults {
            bits: StatusFaults::default()
        })
    );
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
        deaf.step(shown(&run).seen(), 4, mit_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        deaf.step(shown(&run).seen(), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::NoModeEcho)
    );

    let (mut late, run, mit_at) = to_mit(t0);
    let late_echo = echoed(run, MIT, mit_at + RUN_WITHIN_NS + 1);
    assert_eq!(
        late.step(shown(&late_echo).seen(), 4, mit_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::NoModeEcho),
        "an echo read after its window"
    );
    let (mut on_time, run, mit_at) = to_mit(t0);
    let echo = echoed(
        with_status(run, Mode::Run, mit_at + RUN_WITHIN_NS),
        MIT,
        mit_at + RUN_WITHIN_NS,
    );
    assert_eq!(
        on_time.step(shown(&echo).seen(), 4, mit_at + RUN_WITHIN_NS),
        Next::Enabled,
        "at 50 ms"
    );
    assert_eq!(EnableFailure::NoModeEcho.rule(), RuleId::HostBus);

    // Echoed, but the drive answered in Reset, or not at all.
    let (mut dropped, run, mit_at) = to_mit(t0);
    let reset = echoed(with_status(run, Mode::Reset, mit_at + 20), MIT, mit_at + 10);
    assert_eq!(
        dropped.step(shown(&reset).seen(), 4, mit_at + PERIOD),
        Next::Stop(EnableFailure::LeftRun {
            last: Some(Mode::Reset)
        })
    );
    // A Reset seen after the write that isn't the fresh status: the drive left Run, and the sequence ends at once.
    let (mut seen_left, run, mit_at) = to_mit(t0);
    let left_run = superseded(
        with_status(run, Mode::Reset, mit_at + 20),
        t0 + 2 * PERIOD + ECHO_NS + 1,
    );
    assert_eq!(
        seen_left.step(shown(&left_run).seen(), 4, mit_at + PERIOD),
        Next::Stop(EnableFailure::LeftRun {
            last: Some(Mode::Reset)
        })
    );
    let (mut silent, run, mit_at) = to_mit(t0);
    let echo_only = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        silent.step(shown(&echo_only).seen(), 4, mit_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        silent.step(shown(&echo_only).seen(), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::LeftRun { last: None })
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

    // A fresh Reset, then a Run that answers nothing: the bus drops the fresh Reset, and no Run answered the Enable.
    let (mut enabling, echo) = to_enable(t0);
    let reset_then_run = superseded(with_status(echo, Mode::Run, enable_at + 2), enable_at + 1);
    assert_eq!(
        enabling.step(shown(&reset_then_run).seen(), 3, enable_at + PERIOD),
        Next::Wait
    );
    assert_eq!(
        enabling.step(
            shown(&reset_then_run).seen(),
            4,
            enable_at + RUN_WITHIN_NS + 1
        ),
        Next::Stop(EnableFailure::NoRun {
            last: Some(Mode::Run)
        })
    );

    // A fresh Run, then a Reset that answers nothing: the bus drops the fresh Run, no longer the drive's word.
    let (mut enabling, echo) = to_enable(t0);
    let run_then_reset = superseded(with_status(echo, Mode::Reset, enable_at + 2), enable_at + 1);
    assert_eq!(
        enabling.step(shown(&run_then_reset).seen(), 3, enable_at + PERIOD),
        Next::Wait
    );

    // A fresh Run, then a duplicate Run: the answer stands, and the sequence goes on to the write.
    let (mut enabling, echo) = to_enable(t0);
    let run_then_run = fresh_was(
        with_status(echo, Mode::Run, enable_at + 2),
        status(Mode::Run, StatusFaults::default(), enable_at + 1),
    );
    assert_eq!(
        enabling.step(shown(&run_then_run).seen(), 3, enable_at + PERIOD),
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
        enabling.step(shown(&answered).seen(), 5, mit_at + PERIOD),
        Next::Enabled
    );

    // The Enable's Run read at the very moment the MIT write is planned, then the write's echo and no further status.
    let (mut enabling, echo) = to_enable(t0);
    let mit_at = enable_at + PERIOD;
    let run = with_status(echo, Mode::Run, mit_at);
    assert_eq!(enabling.step(shown(&run).seen(), 3, mit_at), mit_write());
    let only_echo = echoed(run, MIT, mit_at + 10);
    assert_eq!(
        enabling.step(shown(&only_echo).seen(), 4, mit_at + PERIOD),
        Next::Wait,
        "the Enable's answer doesn't answer the write"
    );
    let left = EnableFailure::LeftRun {
        last: Some(Mode::Run),
    };
    assert_eq!(
        enabling.step(shown(&only_echo).seen(), 5, mit_at + RUN_WITHIN_NS + 1),
        Next::Stop(left)
    );
    assert_eq!(
        left.message("arm_joint_one"),
        "enable failed (host.mode): arm_joint_one reported Run, but no status read in the 50 ms after the run_mode = \
         MIT write answered it in Run"
    );
}

/// Guards: safety - `host.bus`: the Enable is planned inside the reporting off's 50 ms window or not at all: a stall of
/// the bus or of control that holds the tick after the echo back past it ends the sequence before any Enable, so no
/// Enable goes on a proof that much older; at 50 ms it still goes (PLAN item 2, Enable one drive).
#[test]
fn the_enable_sequence_gives_up_on_a_stall_before_its_enable() {
    let t0 = 100 * PERIOD;
    let echo = echoed(quiet(), EchoKind::Reporting(Reporting::Off), t0 + 10);
    let enable = Next::Send(encode::enable(joint(&skeleton(), 0).id));
    for (tick, at, expected) in [
        (2, t0 + RUN_WITHIN_NS, enable),
        (
            2,
            t0 + RUN_WITHIN_NS + 1,
            Next::Refused(EnableFailure::Stalled),
        ),
        // No later tick at all by then.
        (
            1,
            t0 + RUN_WITHIN_NS + 1,
            Next::Refused(EnableFailure::Stalled),
        ),
    ] {
        let mut enabling = Enabling::new(passed(), t0);
        let _ = enabling.step(shown(&quiet()).seen(), 0, t0);
        assert_eq!(
            enabling.step(shown(&echo).seen(), 1, t0 + PERIOD),
            Next::Wait
        );
        assert_eq!(
            enabling.step(shown(&echo).seen(), tick, at),
            expected,
            "tick {tick} at {at}"
        );
    }
    assert_eq!(EnableFailure::Stalled.rule(), RuleId::HostBus);
    assert_eq!(
        EnableFailure::Stalled.message("arm_joint_one"),
        "enable failed (host.bus): arm_joint_one had its reporting off read back, but no tick came within 50 ms of it \
         to plan the Enable, expected the next tick"
    );
}

/// Guards: safety - `host.bus` and `host.mode`: the Run window runs from when the Enable is planned, however late its
/// echo is read, so the sequence never waits for Run longer than the bus does; a Run read in it counts, echo or not.
/// When it passes without Run, an Enable read back in it is a drive that never answered (`NoRun`), and one not read
/// back in it (dropped on a held tick or a full queue, or lost) is an Enable not seen to go out (`NoEnableEcho`); since
/// it may have gone out, the limb is stopped either way (PLAN item 2, Enable one drive; item 6 Bus and Mode rows).
#[test]
fn an_enable_not_read_back_is_told_from_a_drive_that_never_answered() {
    let t0 = 100 * PERIOD;
    let enable_at = t0 + 2 * PERIOD;
    let late_echo = echoed(quiet(), EchoKind::Enable, enable_at + 30_000_000);
    for (read_ns, expected) in [
        (enable_at + RUN_WITHIN_NS, mit_write()),
        (
            enable_at + RUN_WITHIN_NS + 1,
            Next::Stop(EnableFailure::NoRun {
                last: Some(Mode::Run),
            }),
        ),
    ] {
        let (mut enabling, _) = to_enable(t0);
        let run = with_status(late_echo, Mode::Run, read_ns);
        assert_eq!(
            enabling.step(shown(&run).seen(), 3, read_ns),
            expected,
            "Run read {} ns after the Enable, its echo 30 ms after it",
            read_ns - enable_at
        );
    }
    let unseen = echoed(quiet(), EchoKind::Reporting(Reporting::Off), t0 + 10);
    let (mut unseen_run, _) = to_enable(t0);
    assert_eq!(
        unseen_run.step(
            shown(&with_status(unseen, Mode::Run, enable_at + 1)).seen(),
            3,
            enable_at + PERIOD
        ),
        mit_write(),
        "a Run with the Enable not yet read back"
    );
    // Silent after a late echo: given up 50 ms after the Enable was planned, not after the echo.
    let (mut silent, _) = to_enable(t0);
    assert_eq!(
        silent.step(shown(&late_echo).seen(), 3, enable_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        silent.step(shown(&late_echo).seen(), 4, enable_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::NoRun { last: None })
    );

    let (mut dropped, _) = to_enable(t0);
    assert_eq!(
        dropped.step(shown(&unseen).seen(), 3, enable_at + RUN_WITHIN_NS),
        Next::Wait
    );
    assert_eq!(
        dropped.step(shown(&unseen).seen(), 4, enable_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::NoEnableEcho)
    );
    // An echo read after its window is no better.
    let (mut late, _) = to_enable(t0);
    let too_late = echoed(quiet(), EchoKind::Enable, enable_at + RUN_WITHIN_NS + 1);
    assert_eq!(
        late.step(shown(&too_late).seen(), 3, enable_at + RUN_WITHIN_NS + 1),
        Next::Stop(EnableFailure::NoEnableEcho)
    );
    assert_eq!(EnableFailure::NoEnableEcho.rule(), RuleId::HostBus);
    assert_eq!(
        EnableFailure::NoEnableEcho.message("arm_joint_one"),
        "enable failed (host.bus): arm_joint_one had its Enable not read back within 50 ms, so it may not have gone \
         out, expected its echo"
    );
}

/// Guards: safety - `host.bus`: a sequence's refusal speaks for its own drive only. In an enable of two drives of one
/// limb, the first may have planned its Enable when the second gives up before its own: the second is `Refused`, and
/// the public `enable_planned` says the first's Enable may have gone, so control stops the limb rather than return it
/// to idle (PLAN item 2, Enable one drive; item 6 States: a limb with anything enabled is stopped).
#[test]
fn a_refusal_speaks_for_its_own_drive_only() {
    let t0 = 100 * PERIOD;
    let (first, _) = to_enable(t0);
    let mut second = Enabling::new(passed_for(3), t0);
    let deaf = DriveView {
        device: joint(&skeleton(), 3).id,
        ..quiet()
    };
    let _ = second.step(shown(&deaf).seen(), 0, t0);
    assert_eq!(
        second.step(shown(&deaf).seen(), 1, t0 + RUN_WITHIN_NS + 1),
        Next::Refused(EnableFailure::NoEcho)
    );
    assert!(first.enable_planned(), "the first's Enable may have gone");
    assert!(!second.enable_planned(), "no Enable went to the second");
}
