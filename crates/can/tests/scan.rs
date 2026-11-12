//! A scan's probes and the set-ID: type 0 to any ID and type 7, each alone in the slack like any slow request, and only
//! while every limb on the bus is idle (PLAN.md item 3, Scan and identity; item 2, transmit allowlist).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusError, BusTick, Drain, RearmRefused, SendOutcome, SlowKind, SlowOutcome, SlowRefusal,
    SlowRequest, SlowResult,
};
use common::{
    MS, PERIOD, batch, bus, deadline, error_frame, id, record, run_tick, status, two_limbs,
};
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

/// A probe of `n` and the frame it sends.
fn probe(n: u8) -> (SlowKind, robstride::Frame) {
    (SlowKind::Probe(id(n)), encode::get_id(id(n)))
}

/// A set-ID from `old` to `new` and the frame it sends.
fn set_id(old: u8, new: u8) -> (SlowKind, robstride::Frame) {
    (
        SlowKind::SetId {
            old: id(old),
            new: id(new),
        },
        encode::set_id(id(old), id(new)),
    )
}

/// How a probe's window closes, besides the frames read in it.
#[derive(Clone, Copy, Debug)]
enum Close {
    /// The drain before the next tick went this way.
    Drain(Drain),
    /// The socket failed in the window.
    Failed,
    /// A frame read in the window carried a new overflow count.
    KernelDrop,
    /// A frame read in the window carried the overflow count already seen.
    SameDrops,
}

/// Send `kind`, expecting `frame`, read `replies` in the window, close it as `close` says, and start the next tick: the
/// request's result.
fn window(
    kind: SlowKind,
    frame: robstride::Frame,
    replies: &[telemetry::FrameRecord],
    close: Close,
    what: &str,
) -> Option<SlowResult> {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(request(5, kind)), Ok(()), "{what}");
    assert_eq!(bus.slow_send(deadline(0)), Some(frame), "{what}");
    bus.slow_sent(SendOutcome::Sent, deadline(0));
    bus.on_frame(
        deadline(0) + MS / 8,
        &record(frame.id(), frame.data(), Direction::TxEcho),
    );
    for reply in replies {
        bus.on_frame(PERIOD - MS / 2, reply);
    }
    assert_eq!(
        bus.take_slow_result(),
        None,
        "{what}: held to the window's end"
    );
    assert_eq!(bus.slow_send(deadline(0)), None, "{what}: still in flight");
    match close {
        Close::Drain(drain) => bus.drained(drain),
        Close::Failed => bus.lost_bus(BusError::InterfaceGone),
        Close::KernelDrop => bus.note_kernel_drops(1),
        Close::SameDrops => bus.note_kernel_drops(0),
    }
    run_tick(&mut bus, 1, Some(&batch(1, &[])), &[]);
    let _ = bus.end(deadline(1));
    bus.open_slack();
    bus.take_slow_result()
}

/// One row of the window table: what, the request and the frame it sends, the frames read in its window, how the
/// window closes, its result.
type Row = (
    &'static str,
    (SlowKind, robstride::Frame),
    Vec<telemetry::FrameRecord>,
    Close,
    SlowOutcome,
);

/// The rows of `probes_and_set_id_are_answered_by_type_0_from_their_id`.
fn rows() -> Vec<Row> {
    let found = |uid| SlowOutcome::Found { uid, other: None };
    let one = Uid([1; 8]);
    let two = Uid([2; 8]);
    vec![
        (
            "one drive at an ID outside the table",
            probe(127),
            vec![identity(126, two), identity(127, one), identity(127, one)],
            Close::Drain(Drain::Emptied),
            found(one),
        ),
        (
            "a drive in the table",
            probe(102),
            vec![identity(102, one)],
            Close::Drain(Drain::Emptied),
            found(one),
        ),
        (
            "two drives sharing an ID",
            probe(50),
            vec![identity(50, one), identity(50, two)],
            Close::Drain(Drain::Emptied),
            SlowOutcome::Found {
                uid: one,
                other: Some(two),
            },
        ),
        (
            "nothing at that ID",
            probe(51),
            vec![identity(52, one)],
            Close::Drain(Drain::Emptied),
            SlowOutcome::TimedOut,
        ),
        (
            "a set-ID, answered from the new ID",
            set_id(127, 11),
            vec![identity(11, one)],
            Close::Drain(Drain::Emptied),
            found(one),
        ),
        (
            "a set-ID answered only from the old ID",
            set_id(127, 11),
            vec![identity(127, one)],
            Close::Drain(Drain::Emptied),
            SlowOutcome::TimedOut,
        ),
    ]
    .into_iter()
    .chain(untrusted_rows())
    .collect()
}

/// The rows whose window can't be trusted, and the one that can despite a frame carrying an overflow count.
fn untrusted_rows() -> Vec<Row> {
    let found = |uid| SlowOutcome::Found { uid, other: None };
    let one = Uid([1; 8]);
    vec![
        (
            "an error frame in the window",
            probe(50),
            vec![identity(50, one), error_frame(0x04, 0x04)],
            Close::Drain(Drain::Emptied),
            SlowOutcome::Unsure,
        ),
        (
            "a set-ID whose window closes on a drain that left frames unread",
            set_id(127, 11),
            vec![identity(11, one)],
            Close::Drain(Drain::Unemptied),
            SlowOutcome::Unsure,
        ),
        (
            "an error frame alone in the window",
            probe(50),
            vec![error_frame(0x04, 0x04)],
            Close::Drain(Drain::Emptied),
            SlowOutcome::Unsure,
        ),
        (
            "nothing read, and frames left unread",
            probe(50),
            vec![],
            Close::Drain(Drain::Unemptied),
            SlowOutcome::Unsure,
        ),
        (
            "a backlog: an overflow comes with one",
            probe(50),
            vec![identity(50, one)],
            Close::Drain(Drain::Backlog),
            SlowOutcome::Unsure,
        ),
        (
            "a set-ID, nothing heard, the socket failed",
            set_id(127, 11),
            vec![],
            Close::Failed,
            SlowOutcome::Unsure,
        ),
        (
            "a frame with the same overflow count: no drop",
            probe(50),
            vec![identity(50, one)],
            Close::SameDrops,
            found(one),
        ),
        (
            "the socket failed in the window",
            probe(50),
            vec![identity(50, one)],
            Close::Failed,
            SlowOutcome::Unsure,
        ),
        (
            "a kernel drop in the window",
            probe(50),
            vec![identity(50, one)],
            Close::KernelDrop,
            SlowOutcome::Unsure,
        ),
    ]
}

/// Guards: protocol - a probe is a type 0 to any ID, in the bus's table or not, and a set-ID a type 7 from the old ID
/// to the new; each is answered by the type-0 replies from its ID (the probe's, or the set-ID's new one) read before the
/// next tick's start, a second drive with another UID on that ID included, and nothing answering is a timeout. A window
/// with an error frame in it (assumed, until the bench, to be how two drives on one ID collide) or a new kernel overflow
/// count, closed by a drain that read a backlog or left frames unread, or on a failed bus is unsure, never a count of
/// drives (RS03 manual §4.1.1 type 0, §4.1.5 type 7 "effective immediately", answered by the type-0 broadcast frame;
/// PLAN.md item 2: type 7 only with exactly one drive answering).
#[test]
fn probes_and_set_id_are_answered_by_type_0_from_their_id() {
    for (what, (kind, frame), replies, close, outcome) in rows() {
        assert_eq!(
            window(kind, frame, &replies, close, what),
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
/// is idle: one is refused while any limb is running, stopping, stopped or has a stop asked, until the re-arm makes every
/// limb idle again; one queued is cancelled before it goes once a limb runs or a stop is asked; and a drive's read for an
/// idle limb on the same bus is still served (PLAN.md item 3: set-ID only
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

    // A stop asked of one idle limb with a set-ID queued: that one is cancelled, and every other refused from then on,
    // through the stop and after it, until the re-arm.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(request(1, set_id)), Ok(()));
    assert_eq!(bus.stop_limb(0), Ok(()));
    assert_eq!(bus.submit(request(2, set_id)), Err(SlowRefusal::BusNotIdle));
    let last = bus.timing().stop_max_ns().div_ceil(PERIOD) + 1;
    for tick in 1..=last {
        quiet_tick(&mut bus, tick);
        if tick == 1 {
            assert_eq!(
                bus.take_slow_result().map(|r| r.outcome),
                Some(SlowOutcome::Refused(SlowRefusal::BusNotIdle))
            );
        }
        assert_eq!(
            bus.submit(request(3, probe)),
            Err(SlowRefusal::BusNotIdle),
            "tick {tick}"
        );
    }
    let quiet = (last + 1) * PERIOD + can::DRIVE_TIMEOUT_NS;
    assert_eq!(bus.rearm(0, quiet), Ok::<(), RearmRefused>(()));
    assert_eq!(
        bus.submit(request(4, probe)),
        Ok(()),
        "every limb idle again"
    );
}
