//! Preflight's refusals from what the drive's bus shows of it and its limb (PLAN item 6 Preflight row; safety.md
//! section 6.1).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    DriveView, LimbState, LimbView, ModeSeen, SlowKind, SlowOutcome, SlowRequest, StopReason,
};
use common::preflight::{Drive, SLOT, UID, answer, run};
use common::{BUS0, IDLE, heard, joint, on, quiet, seen, shown, skeleton, status};
use robstride::{Mode, StatusFault, StatusFaults};
use safety::{DriveAddress, Preflight, Refusal, RuleId, Step, Target};

/// Guards: safety - `host.preflight`: no fault bits, and the drive not already in Run or Calibration, in every status
/// or version reply since preflight began; a drive that sends no status, or a joint with no bus, is refused (PLAN item 6
/// Preflight row).
#[test]
fn preflight_refuses_a_fault_or_a_drive_not_in_reset() {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let with = |status| Drive {
        status,
        ..Drive::honest()
    };
    for (drive, expected) in [
        // A fault in a status during preflight is named by its bits (the bus latches `fault_seen` with it).
        (
            with(Some((Mode::Reset, over))),
            Err(Refusal::Faults { bits: over }),
        ),
        (
            with(Some((Mode::Run, StatusFaults::default()))),
            Err(Refusal::NotReset { mode: Mode::Run }),
        ),
        (
            with(Some((Mode::Calibration, StatusFaults::default()))),
            Err(Refusal::NotReset {
                mode: Mode::Calibration,
            }),
        ),
        (with(None), Err(Refusal::NoStatus)),
        (
            Drive {
                before: DriveView {
                    fault_seen: true,
                    ..quiet()
                },
                ..Drive::honest()
            },
            Err(Refusal::FaultSeen),
        ),
        // A status from before preflight began says nothing about the drive now: its Run doesn't count, and its
        // fault counts only through the latch.
        (
            Drive {
                before: seen(status(Mode::Run, StatusFaults::default(), 500)),
                ..Drive::honest()
            },
            Ok(()),
        ),
        (
            Drive {
                before: seen(status(Mode::Reset, over, 500)),
                ..Drive::honest()
            },
            Err(Refusal::FaultSeen),
        ),
    ] {
        assert_eq!(run(0, &drive).0, expected);
    }
    assert_eq!(run(2, &Drive::honest()).0, Err(Refusal::Unwired), "no bus");
    // The latest status's bits are named even with the latch set, as the bus sets it.
    let skeleton = skeleton();
    let mut preflight = Preflight::start(
        Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap(),
        SLOT,
        1,
        1_000,
    );
    let faulted = seen(status(Mode::Reset, over, 2_000));
    assert_eq!(
        preflight.poll(shown(&faulted).seen(), 3_000),
        Step::Refused(Refusal::Faults { bits: over })
    );
    assert_eq!(
        Refusal::NotReset { mode: Mode::Run }.remedy(),
        "Find what put it in that mode; power-cycle the drive, then run preflight again",
        "no clear: the limb stays idle, and a clear of an idle limb is refused"
    );
    for refusal in [
        Refusal::Faults { bits: over },
        Refusal::FaultSeen,
        Refusal::NotReset { mode: Mode::Run },
        Refusal::NoStatus,
        Refusal::Unwired,
    ] {
        assert_eq!(refusal.rule(), RuleId::HostPreflight);
    }
}

/// Guards: safety - `host.preflight`: a version reply carries the status header too, so one out of Reset since
/// preflight began refuses whatever the last status says, a later one in Reset doesn't hide a status out of it, and one
/// from before preflight began says nothing (PLAN item 6 Preflight row: the drive in Reset).
#[test]
fn a_version_reply_out_of_reset_refuses() {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let reset = status(Mode::Reset, StatusFaults::default(), 2_000);
    let calibration = status(Mode::Calibration, StatusFaults::default(), 2_000);
    let header = |mode, read_ns| Some(ModeSeen { mode, read_ns });
    let get_id = SlowRequest {
        tag: 1,
        slot: SLOT,
        kind: SlowKind::GetId,
    };
    for (view, expected) in [
        (
            DriveView {
                mode: header(Mode::Calibration, 2_500),
                ..heard(reset)
            },
            Step::Refused(Refusal::NotReset {
                mode: Mode::Calibration,
            }),
        ),
        (
            DriveView {
                mode: header(Mode::Reset, 2_500),
                ..heard(calibration)
            },
            Step::Refused(Refusal::NotReset {
                mode: Mode::Calibration,
            }),
        ),
        (
            DriveView {
                mode: header(Mode::Run, 500),
                ..quiet()
            },
            Step::Submit(get_id),
        ),
    ] {
        let mut preflight = Preflight::start(target, SLOT, 1, 1_000);
        assert_eq!(
            preflight.poll(shown(&view).seen(), 3_000),
            expected,
            "{view:?}"
        );
    }
}

/// Guards: safety - `host.preflight`: a drive that went out of Reset and back between two polls (in one snapshot, or
/// across snapshots control never read) is refused all the same, by the mode the bus latched while this host hadn't
/// enabled it; one latched before preflight began says nothing, since preflight's own statuses showed Reset after it
/// (PLAN item 6 Preflight row: the drive in Reset; another controller).
#[test]
fn a_drive_out_of_reset_and_back_between_polls_refuses() {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let back = heard(status(Mode::Reset, StatusFaults::default(), 2_500));
    let latched = |mode, read_ns| DriveView {
        out_of_reset: Some(ModeSeen { mode, read_ns }),
        ..back
    };
    let get_id = SlowRequest {
        tag: 1,
        slot: SLOT,
        kind: SlowKind::GetId,
    };
    for (view, expected) in [
        (
            latched(Mode::Run, 2_000),
            Step::Refused(Refusal::NotReset { mode: Mode::Run }),
        ),
        (
            latched(Mode::Calibration, 1_000),
            Step::Refused(Refusal::NotReset {
                mode: Mode::Calibration,
            }),
        ),
        (latched(Mode::Run, 999), Step::Submit(get_id)),
    ] {
        let mut preflight = Preflight::start(target, SLOT, 1, 1_000);
        assert_eq!(
            preflight.poll(shown(&view).seen(), 3_000),
            expected,
            "{view:?}"
        );
    }
}

/// Guards: safety - `host.preflight`: preflight checks at every poll that it is shown its own drive on its own bus,
/// and that the drive's limb is idle and hasn't stopped or been cleared since the first poll. Another drive's view
/// (another ID, or the same ID on another bus) is a runtime bug; an enabled limb, or one that stopped or was cleared
/// mid-preflight (idle again, but what was checked before may predate the stop), refuses too (PLAN item 6 Preflight
/// row).
#[test]
fn preflight_refuses_another_drives_view_or_a_limb_not_idle() {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let (view, bus1) = (quiet(), common::bus(1));
    let other = DriveView {
        device: common::id(102),
        ..view
    };
    let limb = |state, stop, generation| LimbView {
        state,
        stop,
        generation,
    };
    let stop = Some(StopReason::Requested);
    let limbs = [
        (limb(LimbState::Active, None, 0), Refusal::LimbActive),
        (
            limb(LimbState::Stopping { since_ns: 1_500 }, stop, 0),
            Refusal::LimbStopped { stop },
        ),
        (
            limb(LimbState::Idle, None, 1),
            Refusal::LimbStopped { stop: None },
        ),
    ];
    let wrong = |bus, n| Refusal::WrongView {
        view: DriveAddress::new(bus, common::id(n)).unwrap(),
        drive: target.address(),
    };
    let mut rows = vec![
        (shown(&other), wrong(&BUS0, 102)),
        (on(&bus1, &view, &IDLE), wrong(&bus1, 101)),
    ];
    for (limb, refusal) in &limbs {
        rows.push((on(&BUS0, &view, limb), *refusal));
    }
    for (seen, refusal) in rows {
        let mut preflight = Preflight::start(target, SLOT, 1, 1_000);
        let get_id = SlowRequest {
            tag: 1,
            slot: SLOT,
            kind: SlowKind::GetId,
        };
        assert_eq!(
            preflight.poll(shown(&view).seen(), 2_000),
            Step::Submit(get_id)
        );
        preflight.answered(answer(get_id, SlowOutcome::Identity(UID)), 3_000);
        assert_eq!(
            preflight.poll(seen.seen(), 3_000),
            Step::Refused(refusal),
            "{refusal:?}"
        );
        assert_eq!(refusal.rule(), RuleId::HostPreflight);
    }
    assert_eq!(
        wrong(&bus1, 101).message("arm_joint_one"),
        "refused (host.preflight): arm_joint_one was checked against drive 101 on bus1's view, expected drive 101 on \
         bus0's"
    );
    assert_eq!(
        Refusal::LimbStopped { stop: None }.message("arm_joint_one"),
        "refused (host.preflight): arm_joint_one found its limb stopped or cleared since preflight began, expected it \
         idle throughout"
    );
}
