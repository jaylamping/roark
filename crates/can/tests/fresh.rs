//! A drive's fresh answer in the snapshot: a later status in another mode supersedes it (PLAN.md item 3 snapshot
//! contract). Whether a duplicate keeps it is in `tick.rs`.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{LimbState, ModeSeen, SendOutcome};
use common::{
    MS, PERIOD, at, batch, bus, deadline, hold, id, one_limb, record, run_tick, state_of, status,
    status_frame,
};
use robstride::encode;
use robstride::{Mode, StatusFaults};
use telemetry::Direction;

/// Guards: protocol - a status, or a version reply, in another mode after a drive's fresh Run supersedes it, and a Run
/// that follows doesn't bring it back; the age of the last fresh reply (`fresh_ns`) stays, and the next command's fresh
/// reply sets the fresh status again (PLAN.md item 3 snapshot contract).
#[test]
fn a_later_status_in_another_mode_supersedes_the_fresh_answer() {
    let reset = status_frame(101, Mode::Reset, StatusFaults::default());
    let version = record(
        reset.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    );
    for (name, other) in [
        ("status", status(101, Mode::Reset)),
        ("version reply", version),
    ] {
        let mut bus = bus();
        let b = batch(0, &[Some(encode::enable(id(101))), None]);
        run_tick(
            &mut bus,
            0,
            Some(&b),
            &[
                (MS, status(101, Mode::Run)),
                (MS + 1, other),
                (MS + 2, status(101, Mode::Run)),
            ],
        );
        let gone = at(&bus.end(deadline(0)), 0);
        assert_eq!(gone.fresh_status, None, "{name}");
        assert_eq!(gone.fresh_ns, Some(MS), "{name}");
        assert_eq!(
            gone.observed.map(|o| (o.read_ns, o.status.header.mode)),
            Some((MS + 2, Mode::Run)),
            "{name}"
        );

        let b = batch(1, &[Some(hold(101)), None]);
        run_tick(&mut bus, 1, Some(&b), &[(MS, status(101, Mode::Run))]);
        let back = at(&bus.end(deadline(1)), 0);
        assert_eq!(
            back.fresh_status.map(|o| o.read_ns),
            Some(PERIOD + MS),
            "{name}"
        );
    }
}

/// Guards: protocol - a version reply carries the status header too, so the drive's latest mode in the snapshot
/// (`mode`) is the version reply's when it is the last frame read, though `observed` keeps the last status: a drive
/// that shows it left Reset only in a version reply still shows it (PLAN.md item 6 Preflight row, the drive in Reset).
#[test]
fn a_version_reply_is_the_drives_latest_mode() {
    let calibration = status_frame(101, Mode::Calibration, StatusFaults::default());
    let version = record(
        calibration.id(),
        [0x00, 0xC4, 0x56, 1, 2, 3, 4, 0],
        Direction::TxOther,
    );
    let mut bus = bus();
    run_tick(
        &mut bus,
        0,
        None,
        &[(MS, status(101, Mode::Reset)), (MS + 1, version)],
    );
    let view = at(&bus.end(deadline(0)), 0);
    assert_eq!(
        view.mode,
        Some(ModeSeen {
            mode: Mode::Calibration,
            read_ns: MS + 1
        })
    );
    assert_eq!(
        view.observed.map(|o| (o.read_ns, o.status.header.mode)),
        Some((MS, Mode::Reset)),
        "a version reply carries no feedback to keep"
    );
}

/// Guards: safety - a drive this host hasn't enabled that shows any mode but Reset keeps it, with its read time, in
/// `out_of_reset` until its limb's re-arm, whether a Reset follows in the same drain or in the next: an excursion to Run
/// and back between two snapshots control reads, or across snapshots it skips, still shows. This host's own Enable and
/// the Run answering it never set it (PLAN item 6 Preflight row: the drive in Reset; another controller).
#[test]
fn a_mode_out_of_reset_before_this_hosts_enable_is_kept_until_the_rearm() {
    let latched = |mode, read_ns| Some(ModeSeen { mode, read_ns });
    let mut bus = bus();
    // Drive 101: Run then Reset in one drain. Drive 102: Run in one, Reset in the next.
    run_tick(
        &mut bus,
        0,
        None,
        &[
            (MS, status(101, Mode::Run)),
            (MS + 1, status(101, Mode::Reset)),
            (MS, status(102, Mode::Run)),
        ],
    );
    let _ = bus.end(deadline(0));
    run_tick(&mut bus, 1, None, &[(MS, status(102, Mode::Reset))]);
    let snap = bus.end(deadline(1));
    assert_eq!(at(&snap, 0).out_of_reset, latched(Mode::Run, MS));
    assert_eq!(at(&snap, 1).out_of_reset, latched(Mode::Run, MS));
    assert_eq!(
        at(&snap, 1).mode.map(|m| m.mode),
        Some(Mode::Reset),
        "the latest mode is Reset; the latch keeps the Run"
    );

    // Stopped and re-armed: the latch is cleared with the fault history. The socket takes none of the stop's
    // Disables, so the drives are quiet and the re-arm isn't held off.
    // The stop ends by `stop_max_ns` after tick 2's start.
    assert_eq!(bus.stop_limb(0), Ok(()));
    let stop_ends = 2 + bus.timing().stop_max_ns().div_ceil(PERIOD);
    let mut state = None;
    for tick in 2..=stop_ends {
        let start = tick * PERIOD;
        let list = bus.begin(tick, start, start, None);
        for index in 0..list.len() {
            bus.sent(index, SendOutcome::QueueFull, start);
        }
        state = Some(state_of(&bus.end(deadline(tick))));
    }
    assert_eq!(state, Some(LimbState::Stopped));
    assert_eq!(bus.rearm(0, deadline(stop_ends)), Ok(()));
    let snap = bus.end(deadline(stop_ends));
    assert_eq!(at(&snap, 0).out_of_reset, None);
    assert_eq!(at(&snap, 1).out_of_reset, None);

    // This host's own Enable, answered in Run: not latched.
    let mut bus = bus_of_one();
    let enable = batch(0, &[Some(encode::enable(id(101)))]);
    run_tick(&mut bus, 0, Some(&enable), &[(MS, status(101, Mode::Run))]);
    let snap = bus.end(deadline(0));
    assert_eq!(snap.limb(0).map(|l| l.state), Some(LimbState::Active));
    assert_eq!(at(&snap, 0).out_of_reset, None);
}

/// A bus of drive 101 alone, at 250 Hz.
#[expect(clippy::unwrap_used, reason = "test helper: one drive fits")]
fn bus_of_one() -> can::BusTick {
    can::BusTick::new(&one_limb(&[id(101)]), can::Timing::at_hz(250)).unwrap()
}
