//! A drive's fresh answer in the snapshot: kept through a later status of the same mode, taken back by one in
//! another mode (PLAN.md item 3 snapshot contract).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use common::{MS, PERIOD, at, batch, bus, id, run_tick, status};
use robstride::Mode;
use robstride::encode;

/// Guards: protocol - a drive's fresh answer survives a later status of the same mode and is taken back by one of
/// another mode, which a following Run doesn't bring back; the age of the last fresh reply (`fresh_ns`) stays either
/// way (PLAN.md item 3 snapshot contract).
#[test]
fn a_later_status_in_another_mode_takes_the_fresh_answer_back() {
    let mut bus = bus();
    let b = batch(0, &[Some(encode::enable(id(101))), None]);
    run_tick(
        &mut bus,
        0,
        Some(&b),
        &[
            (MS, status(101, Mode::Run)),
            (MS + 1, status(101, Mode::Run)),
        ],
    );
    let kept = at(&bus.end(PERIOD * 6 / 10), 0);
    assert_eq!(
        kept.fresh_status.map(|o| (o.read_ns, o.status.header.mode)),
        Some((MS, Mode::Run))
    );

    let mut bus = self::bus();
    run_tick(
        &mut bus,
        0,
        Some(&b),
        &[
            (MS, status(101, Mode::Run)),
            (MS + 1, status(101, Mode::Reset)),
            (MS + 2, status(101, Mode::Run)),
        ],
    );
    let taken = at(&bus.end(PERIOD * 6 / 10), 0);
    assert_eq!(taken.fresh_status, None);
    assert_eq!(taken.fresh_ns, Some(MS));
    assert_eq!(
        taken.observed.map(|o| (o.read_ns, o.status.header.mode)),
        Some((MS + 2, Mode::Run))
    );
}
