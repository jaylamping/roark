//! A scan's probes and the set-ID: type 0 to any ID and type 7, each alone in the slack like any slow request, and only
//! while every limb on the bus is idle (PLAN.md item 3, Scan and identity; item 2, transmit allowlist).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{BusTick, SendOutcome, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult};
use common::{MS, PERIOD, batch, bus, deadline, id, record, run_tick, status, two_limbs};
use robstride::drive as wire;
use robstride::{Mode, Param, Uid, encode};
use telemetry::Direction;

/// Tick `tick` with control alive (an empty batch) and nothing sent, ended at its collect deadline, its slack opened.
fn quiet_tick(bus: &mut BusTick, tick: u64) {
    run_tick(bus, tick, Some(&batch(tick, &[])), &[]);
    let _ = bus.end(deadline(tick));
    bus.open_slack();
}

fn request(tag: u32, kind: SlowKind) -> SlowRequest {
    SlowRequest { tag, slot: 0, kind }
}

/// Drive `n`'s type-0 frame with `uid`, as `vcan` delivers it.
fn identity(n: u8, uid: Uid) -> telemetry::FrameRecord {
    let f = wire::identity(id(n), uid);
    record(f.id(), f.data(), Direction::TxOther)
}

/// Guards: protocol - a probe is a type 0 to any ID, in the bus's table or not, and a set-ID a type 7 from the old ID
/// to the new; each is answered by the type-0 replies from its ID (the probe's, or the set-ID's new one) read before the
/// next tick's start, a second drive with another UID on that ID included, and nothing answering is a timeout (RS03
/// manual §4.1.1 type 0, §4.1.5 type 7 "effective immediately", answered by the type-0 broadcast frame).
#[test]
fn probes_and_set_id_are_answered_by_type_0_from_their_id() {
    let one = Uid([1; 8]);
    let two = Uid([2; 8]);
    // (what, the frame it sends, the replies read in the next drain, its result)
    let rows = [
        (
            "one drive at an ID outside the table",
            SlowKind::Probe(id(127)),
            encode::get_id(id(127)),
            vec![identity(126, two), identity(127, one), identity(127, one)],
            SlowOutcome::Found {
                uid: one,
                other: None,
            },
        ),
        (
            "a drive in the table",
            SlowKind::Probe(id(102)),
            encode::get_id(id(102)),
            vec![identity(102, one)],
            SlowOutcome::Found {
                uid: one,
                other: None,
            },
        ),
        (
            "two drives sharing an ID",
            SlowKind::Probe(id(50)),
            encode::get_id(id(50)),
            vec![identity(50, one), identity(50, two)],
            SlowOutcome::Found {
                uid: one,
                other: Some(two),
            },
        ),
        (
            "nothing at that ID",
            SlowKind::Probe(id(51)),
            encode::get_id(id(51)),
            vec![identity(52, one)],
            SlowOutcome::TimedOut,
        ),
        (
            "a set-ID, answered from the new ID",
            SlowKind::SetId {
                old: id(127),
                new: id(11),
            },
            encode::set_id(id(127), id(11)),
            vec![identity(11, one)],
            SlowOutcome::Found {
                uid: one,
                other: None,
            },
        ),
        (
            "a set-ID answered only from the old ID",
            SlowKind::SetId {
                old: id(127),
                new: id(11),
            },
            encode::set_id(id(127), id(11)),
            vec![identity(127, one)],
            SlowOutcome::TimedOut,
        ),
    ];
    for (what, kind, frame, replies, outcome) in rows {
        let mut bus = bus();
        quiet_tick(&mut bus, 0);
        assert_eq!(bus.submit(request(5, kind)), Ok(()), "{what}");
        assert_eq!(bus.slow_send(deadline(0)), Some(frame), "{what}");
        bus.slow_sent(SendOutcome::Sent, deadline(0));
        bus.on_frame(
            deadline(0) + MS / 8,
            &record(frame.id(), frame.data(), Direction::TxEcho),
        );
        for reply in &replies {
            bus.on_frame(PERIOD - MS / 2, reply);
        }
        assert_eq!(
            bus.take_slow_result(),
            None,
            "{what}: held to the window's end"
        );
        assert_eq!(bus.slow_send(deadline(0)), None, "{what}: still in flight");
        run_tick(&mut bus, 1, Some(&batch(1, &[])), &[]);
        let _ = bus.end(deadline(1));
        bus.open_slack();
        assert_eq!(
            bus.take_slow_result(),
            Some(SlowResult {
                tag: 5,
                slot: 0,
                outcome,
            }),
            "{what}"
        );
    }
}

/// Guards: safety - a probe or set-ID reaches whichever drive holds its ID, so it goes only while every limb on the bus
/// is idle: one is refused, and one queued is cancelled before it goes, while any limb is running, stopping, stopped or
/// has a stop asked, and a drive's read for an idle limb on the same bus is still served (PLAN.md item 3: set-ID only
/// while every limb on that bus is disabled; `canTimeout` counts from any frame, so nothing may feed a stopped drive).
#[test]
fn probes_and_set_id_go_only_while_every_limb_on_the_bus_is_idle() {
    let probe = SlowKind::Probe(id(127));
    let set_id = SlowKind::SetId {
        old: id(127),
        new: id(11),
    };

    // Limb 1 enabled: refused, and one queued while it was idle is cancelled as the next slack opens.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(request(1, probe)), Ok(()));
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[None, Some(encode::enable(id(102)))])),
        &[(MS, status(102, Mode::Run))],
    );
    let _ = bus.end(deadline(1));
    bus.open_slack();
    assert_eq!(
        bus.take_slow_result().map(|r| r.outcome),
        Some(SlowOutcome::Refused(SlowRefusal::BusNotIdle))
    );
    for kind in [probe, set_id] {
        assert_eq!(bus.submit(request(2, kind)), Err(SlowRefusal::BusNotIdle));
    }
    assert_eq!(
        bus.submit(SlowRequest {
            tag: 3,
            slot: 0,
            kind: SlowKind::Read(Param::CanTimeout),
        }),
        Ok(()),
        "limb 0 is idle"
    );
    assert_eq!(
        bus.slow_send(deadline(1)),
        Some(encode::param_read(id(101), Param::CanTimeout))
    );

    // A stop asked of one idle limb: refused from then on, through the stop and after it, until the re-arm.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.stop_limb(0), Ok(()));
    assert_eq!(bus.submit(request(1, set_id)), Err(SlowRefusal::BusNotIdle));
    let last = bus.timing().stop_max_ns().div_ceil(PERIOD) + 1;
    for tick in 1..=last {
        quiet_tick(&mut bus, tick);
        assert_eq!(
            bus.submit(request(2, probe)),
            Err(SlowRefusal::BusNotIdle),
            "tick {tick}"
        );
    }
}
