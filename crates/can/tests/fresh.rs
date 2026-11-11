//! A drive's fresh answer in the snapshot: a later status in another mode supersedes it (PLAN.md item 3 snapshot
//! contract). Whether a duplicate keeps it is in `tick.rs`.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::ModeSeen;
use common::{
    MS, PERIOD, at, batch, bus, deadline, hold, id, record, run_tick, status, status_frame,
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
