//! The enable sequence for one drive (PLAN item 2, "Enable one drive"): what ends it whatever its step, from the views
//! a snapshot would show of the drive and its limb.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{DriveView, LimbState, LimbView, ModeSeen, StopReason};
use common::enable::{MIT, PERIOD, PREFLIGHT_AT, passed, to_enable, to_mit, with_status};
use common::{BUS0, IDLE, echoed, in_slot, joint, on, quiet, shown, skeleton};
use robstride::{EchoKind, Mode, Reporting, encode};
use safety::{DriveAddress, EnableFailure, Enabling, Next, RuleId};

/// Guards: safety - `host.preflight`: at every step the sequence checks it is stepped with its own drive on its own
/// bus, in its own slot, and that the drive's limb hasn't stopped or been cleared since preflight. Another drive's view
/// (another ID, or the same ID on another bus), or its own from another slot, ends it as a runtime bug, and a stopped
/// or cleared limb ends it even where the drive's own replies would have enabled it; after the Enable, with the limb to
/// stop (PLAN item 6 Preflight row).
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
        view_slot: 0,
        drive: ours,
        slot: 0,
    };
    assert_eq!(
        enabling.step(shown(&wrong).seen(), 3, t0 + 3 * PERIOD),
        Next::Stop(failure)
    );
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one was stepped with drive 102 on bus0's view in slot 0, expected \
         drive 101 on bus0's in slot 0"
    );

    // Drive 101 on another bus is another drive.
    let (mut enabling, echo) = to_enable(t0);
    let bus1 = common::bus(1);
    let elsewhere = on(&bus1, &echo, &IDLE);
    let failure = EnableFailure::WrongView {
        view: DriveAddress::new(&bus1, common::id(101)).unwrap(),
        view_slot: 0,
        drive: ours,
        slot: 0,
    };
    assert_eq!(
        enabling.step(elsewhere.seen(), 3, t0 + 3 * PERIOD),
        Next::Stop(failure)
    );
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one was stepped with drive 101 on bus1's view in slot 0, expected \
         drive 101 on bus0's in slot 0"
    );

    // Its own drive on its own bus, from another slot than its frames go to.
    let (mut enabling, echo) = to_enable(t0);
    let moved = in_slot(&BUS0, &echo, &IDLE, 1);
    assert_eq!(
        enabling.step(moved.seen(), 3, t0 + 3 * PERIOD),
        Next::Stop(EnableFailure::WrongView {
            view: ours,
            view_slot: 1,
            drive: ours,
            slot: 0,
        })
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
    let failure = EnableFailure::LimbStopped {
        stop,
        enable_planned: true,
    };
    assert_eq!(
        enabling.step(on_stopping.seen(), 4, mit_at + PERIOD),
        Next::Stop(failure)
    );
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
    let failure = EnableFailure::LimbStopped {
        stop: None,
        enable_planned: false,
    };
    assert_eq!(
        enabling.step(on_cleared.seen(), 0, t0),
        Next::Refused(failure)
    );
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one found its limb stopped or cleared since its preflight, expected \
         it idle throughout",
        "before its Enable the limb was idle, not running"
    );
}

/// Guards: safety - `host.preflight`: a drive seen out of Reset since its preflight began and before its Enable is
/// planned, in a status or a version reply, or latched by the bus though a later Reset hides it, ends the sequence
/// before any Enable: something else put it in that mode, and a drive already in Run would answer the Enable in Run.
/// That counts from when preflight began, so a status the bus read after the snapshot preflight passed on isn't
/// missed; one from before preflight began doesn't count, and after the Enable is planned a Run is its answer (PLAN item
/// 6 Preflight row: the drive in Reset; another controller).
#[test]
fn the_enable_sequence_refuses_a_drive_out_of_reset_before_its_enable() {
    let t0 = 100 * PERIOD;
    let echo = echoed(quiet(), EchoKind::Reporting(Reporting::Off), t0 + 10);
    let run = with_status(echo, Mode::Run, t0 + PERIOD);
    let version = DriveView {
        mode: Some(ModeSeen {
            mode: Mode::Calibration,
            read_ns: t0 + PERIOD + 1,
        }),
        fresh_status: None,
        ..with_status(echo, Mode::Reset, t0 + PERIOD)
    };
    // Run and back to Reset between two snapshots: the bus latched the Run.
    let back = DriveView {
        out_of_reset: Some(ModeSeen {
            mode: Mode::Run,
            read_ns: t0 + PERIOD,
        }),
        ..with_status(echo, Mode::Reset, t0 + PERIOD + 1)
    };
    for (view, mode) in [
        (run, Mode::Run),
        (version, Mode::Calibration),
        (back, Mode::Run),
    ] {
        // Seen as the echo comes, or in the tick the Enable would have been planned: either way, no Enable.
        for at_tick in [1, 2] {
            let mut enabling = Enabling::new(passed(), t0);
            let _ = enabling.step(shown(&quiet()).seen(), 0, t0);
            let first = if at_tick == 1 { &view } else { &echo };
            let _ = enabling.step(shown(first).seen(), 1, t0 + PERIOD);
            let failure = EnableFailure::NotReset { mode };
            assert_eq!(
                enabling.step(shown(&view).seen(), 2, t0 + 2 * PERIOD),
                Next::Refused(failure),
                "{mode:?} seen at tick {at_tick}"
            );
        }
    }
    let failure = EnableFailure::NotReset { mode: Mode::Run };
    assert_eq!(failure.rule(), RuleId::HostPreflight);
    assert_eq!(
        failure.message("arm_joint_one"),
        "enable failed (host.preflight): arm_joint_one reported Run since its preflight began, before its Enable, \
         expected Reset"
    );

    // What preflight checked runs from when it began, not from control's clock at its pass: a Run the bus read after
    // the snapshot that passed, though before that clock, is news; one read before preflight began is not.
    let proved_ns = passed().at_ns();
    let enable = Next::Send(encode::enable(joint(&skeleton(), 0).id));
    for (read_ns, expected) in [
        (PREFLIGHT_AT - 1, enable),
        (PREFLIGHT_AT, Next::Refused(failure)),
        (proved_ns - 1, Next::Refused(failure)),
    ] {
        let mut enabling = Enabling::new(passed(), t0);
        let run = with_status(echo, Mode::Run, read_ns);
        let _ = enabling.step(shown(&quiet()).seen(), 0, t0);
        let _ = enabling.step(shown(&run).seen(), 1, t0 + PERIOD);
        assert_eq!(
            enabling.step(shown(&run).seen(), 2, t0 + 2 * PERIOD),
            expected,
            "a Run read at {read_ns}"
        );
    }
}
