//! Slow requests: parameter reads, allowlisted writes and get-ID, one in flight per bus, sent in the slack after the
//! collect deadline only when the reply fits before the next tick's send (step 7 design D3).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusDrive, BusTick, ConfigError, SLOW_SLOTS, SendOutcome, SlowKind, SlowOutcome, SlowRefusal,
    SlowRequest, SlowResult, Timing, TimingError,
};
use common::{
    MS, PERIOD, batch, bus, deadline, drive, error_frame, id, one_limb, record, run_tick, status,
};
use robstride::drive as wire;
use robstride::{CanTimeout, Mode, Param, ParamOutcome, ParamValue, RunMode, Uid, Write, encode};
use telemetry::Direction;

const TIMEOUT: ParamValue = ParamValue::CanTimeout(CanTimeout::RUNTIME);

fn read(tag: u32, slot: usize, param: Param) -> SlowRequest {
    SlowRequest {
        tag,
        slot,
        kind: SlowKind::Read(param),
    }
}

/// Drive `n`'s answer to a read of `param`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the values fit their registers"
)]
fn param_reply(n: u8, param: Param, value: ParamValue) -> telemetry::FrameRecord {
    let f = wire::param_value(id(n), param, value).unwrap();
    record(f.id(), f.data(), Direction::TxOther)
}

/// Drive 101 in limb 0 and drive 102 in limb 1, at 250 Hz.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: two drives in two limbs fit"
)]
fn two_limbs() -> BusTick {
    let drives = [
        BusDrive {
            device: id(101),
            limb: 0,
        },
        BusDrive {
            device: id(102),
            limb: 1,
        },
    ];
    BusTick::new(&drives, Timing::at_hz(250)).unwrap()
}

/// Tick `tick` with control alive (an empty batch) and nothing sent, ended at its collect deadline.
fn quiet_tick(bus: &mut BusTick, tick: u64) {
    run_tick(bus, tick, Some(&batch(tick, &[])), &[]);
    let _ = bus.end(deadline(tick));
}

/// The last moment a slow request may go in tick `tick`: its reply window ends at the next tick's start.
fn last_chance(bus: &BusTick, tick: u64) -> u64 {
    (tick + 1) * PERIOD - bus.timing().slow_reply_ns
}

/// Guards: protocol - one slow exchange in flight per bus, sent only after the collect deadline and only while its reply
/// fits before the next tick's send; a read is answered only by its drive's reply naming its register, and the others
/// queued wait their turn in order (step 7 design D3: budget and matching).
#[test]
fn a_read_goes_alone_in_the_slack_and_only_its_register_answers_it() {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 0, Param::CanTimeout)), Ok(()));
    assert_eq!(bus.submit(read(2, 1, Param::RunMode)), Ok(()));
    assert_eq!(bus.slow_room(), SLOW_SLOTS - 2);
    assert_eq!(
        bus.slow_send(deadline(0) - 1),
        None,
        "inside the collect window"
    );
    assert_eq!(
        bus.slow_send(last_chance(&bus, 0) + 1),
        None,
        "its reply wouldn't fit"
    );
    assert_eq!(
        bus.slow_send(last_chance(&bus, 0)),
        Some(encode::param_read(id(101), Param::CanTimeout))
    );
    bus.slow_sent(SendOutcome::Sent, deadline(0));
    assert_eq!(bus.slow_send(deadline(0)), None, "one in flight");
    // Read in the next drain: another register, another drive, then the answer.
    bus.on_frame(
        PERIOD - MS / 2,
        &param_reply(101, Param::RunMode, ParamValue::RunMode(RunMode::Mit)),
    );
    bus.on_frame(
        PERIOD - MS / 2,
        &param_reply(102, Param::CanTimeout, TIMEOUT),
    );
    assert_eq!(bus.take_slow_result(), None);
    bus.on_frame(
        PERIOD - MS / 4,
        &param_reply(101, Param::CanTimeout, TIMEOUT),
    );
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 1,
            slot: 0,
            outcome: SlowOutcome::Read(ParamOutcome::Read(TIMEOUT)),
        })
    );
    assert_eq!(bus.take_slow_result(), None);
    run_tick(&mut bus, 1, Some(&batch(1, &[])), &[]);
    let snap = bus.end(deadline(1));
    assert_eq!(
        snap.counters.unsolicited, 2,
        "the two replies that answered nothing"
    );
    assert_eq!(
        bus.slow_send(deadline(1)),
        Some(encode::param_read(id(102), Param::RunMode))
    );
}

/// Guards: protocol - a slow request is never retried by the bus layer: one the socket doesn't take is reported not
/// sent, and one with no reply by the next tick's start is reported timed out, its late reply answering nothing
/// (step 7 design D3: deadline).
#[test]
fn a_slow_request_is_reported_once_and_never_retried() {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 0, Param::CanTimeout)), Ok(()));
    assert_eq!(bus.submit(read(2, 0, Param::RunMode)), Ok(()));
    assert!(bus.slow_send(deadline(0)).is_some());
    bus.slow_sent(SendOutcome::QueueFull, deadline(0));
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 1,
            slot: 0,
            outcome: SlowOutcome::NotSent(SendOutcome::QueueFull),
        })
    );
    assert_eq!(
        bus.slow_send(deadline(0)),
        Some(encode::param_read(id(101), Param::RunMode))
    );
    bus.slow_sent(SendOutcome::Sent, deadline(0));
    // No reply by tick 1's start.
    run_tick(&mut bus, 1, Some(&batch(1, &[])), &[]);
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 2,
            slot: 0,
            outcome: SlowOutcome::TimedOut,
        })
    );
    bus.on_frame(
        PERIOD + MS,
        &param_reply(101, Param::RunMode, ParamValue::RunMode(RunMode::Mit)),
    );
    let snap = bus.end(deadline(1));
    assert_eq!(snap.counters.unsolicited, 1);
    assert_eq!(snap.counters.tx_dropped, 1);
    assert_eq!(bus.slow_send(deadline(1)), None, "nothing left to send");
    assert_eq!(bus.take_slow_result(), None);
}

/// Guards: protocol - get-ID is answered by the drive's type-0 reply with its UID, and a write by its drive's next
/// status, which answers only the write: it isn't a duplicate or unsolicited command reply, and it proves nothing about
/// the value (step 7 design D3: a write is proven only by reading it back).
#[test]
fn get_id_and_a_write_are_answered_by_their_own_replies() {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    let uid = Uid([1, 2, 3, 4, 5, 6, 7, 8]);
    assert_eq!(
        bus.submit(SlowRequest {
            tag: 7,
            slot: 1,
            kind: SlowKind::GetId,
        }),
        Ok(())
    );
    assert_eq!(bus.slow_send(deadline(0)), Some(encode::get_id(id(102))));
    bus.slow_sent(SendOutcome::Sent, deadline(0));
    let reply = wire::identity(id(102), uid);
    bus.on_frame(
        PERIOD - MS,
        &record(reply.id(), reply.data(), Direction::TxOther),
    );
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 7,
            slot: 1,
            outcome: SlowOutcome::Identity(uid),
        })
    );

    quiet_tick(&mut bus, 1);
    let write = Write::can_timeout(drive(101));
    assert_eq!(
        bus.submit(SlowRequest {
            tag: 8,
            slot: 0,
            kind: SlowKind::Write(write),
        }),
        Ok(())
    );
    assert_eq!(
        bus.slow_send(deadline(1)),
        Some(encode::param_write(&write))
    );
    bus.slow_sent(SendOutcome::Sent, deadline(1));
    bus.on_frame(2 * PERIOD - MS, &status(101, Mode::Reset));
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 8,
            slot: 0,
            outcome: SlowOutcome::WriteAnswered,
        })
    );
    run_tick(&mut bus, 2, Some(&batch(2, &[])), &[]);
    let snap = bus.end(deadline(2));
    assert_eq!((snap.counters.unsolicited, snap.counters.duplicate), (0, 0));
}

/// Guards: safety - slow requests never keep a drive alive past a stop or a silent control thread: one for a drive in
/// a stopping or stopped limb, or while control is silent (even with every limb idle, as during preflight), or on a
/// failed bus, is refused, and one already queued is cancelled before it goes, while the bus's other limb is served
/// (step 7 design D3: keeping drives alive; canTimeout counts from any frame).
#[test]
fn a_stop_or_silent_control_refuses_and_cancels_slow_requests() {
    // Limb 0 stops: refused for it, served for limb 1, and its queued request cancelled.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 0, Param::CanTimeout)), Ok(()));
    assert_eq!(bus.stop_limb(0), Ok(()));
    quiet_tick(&mut bus, 1);
    assert_eq!(
        bus.submit(read(2, 0, Param::CanTimeout)),
        Err(SlowRefusal::LimbStopped)
    );
    assert_eq!(bus.submit(read(3, 1, Param::CanTimeout)), Ok(()));
    assert_eq!(
        bus.slow_send(deadline(1)),
        Some(encode::param_read(id(102), Param::CanTimeout))
    );
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 1,
            slot: 0,
            outcome: SlowOutcome::Refused(SlowRefusal::LimbStopped),
        })
    );

    // Control silent with every limb idle: refused, and a queued one cancelled.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 1, Param::CanTimeout)), Ok(()));
    let silent = u64::from(bus.timing().silent_ticks);
    for tick in 1..=silent {
        run_tick(&mut bus, tick, None, &[]);
        let _ = bus.end(deadline(tick));
    }
    assert_eq!(
        bus.submit(read(2, 1, Param::CanTimeout)),
        Err(SlowRefusal::ControlSilent)
    );
    assert_eq!(bus.slow_send(deadline(silent)), None);
    assert_eq!(
        bus.take_slow_result().map(|r| r.outcome),
        Some(SlowOutcome::Refused(SlowRefusal::ControlSilent))
    );
    // Control back: served again.
    quiet_tick(&mut bus, silent + 1);
    assert_eq!(bus.submit(read(3, 1, Param::CanTimeout)), Ok(()));

    // A failed bus: refused, and a queued one cancelled.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 1, Param::CanTimeout)), Ok(()));
    bus.on_frame(2 * MS, &error_frame(0x40, 0));
    assert_eq!(
        bus.submit(read(2, 1, Param::CanTimeout)),
        Err(SlowRefusal::BusFailed)
    );
    assert_eq!(bus.slow_send(deadline(0)), None);
    assert_eq!(
        bus.take_slow_result().map(|r| r.outcome),
        Some(SlowOutcome::Refused(SlowRefusal::BusFailed))
    );
}

/// Guards: protocol - a slow request names a drive the bus owns, a write is built for that drive, and the queue is
/// bounded: past `SLOW_SLOTS` (counting results not yet taken) it refuses, and taking a result frees a slot (can.md
/// section 2: bounded everything).
#[test]
fn slow_requests_name_a_drive_on_the_bus_and_the_queue_is_bounded() {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    assert_eq!(
        bus.submit(read(1, 5, Param::CanTimeout)),
        Err(SlowRefusal::NoSuchSlot)
    );
    assert_eq!(
        bus.submit(SlowRequest {
            tag: 2,
            slot: 0,
            kind: SlowKind::Write(Write::can_timeout(drive(102))),
        }),
        Err(SlowRefusal::WrongTarget)
    );
    for tag in 0..u32::try_from(SLOW_SLOTS).unwrap_or(u32::MAX) {
        assert_eq!(bus.submit(read(tag, 0, Param::CanTimeout)), Ok(()));
    }
    assert_eq!(bus.slow_room(), 0);
    assert_eq!(
        bus.submit(read(99, 0, Param::CanTimeout)),
        Err(SlowRefusal::QueueFull)
    );
    assert!(bus.slow_send(deadline(0)).is_some());
    bus.slow_sent(SendOutcome::Failed, deadline(0));
    assert_eq!(bus.slow_room(), 0, "a result not yet taken holds its slot");
    assert!(bus.take_slow_result().is_some());
    assert_eq!(bus.slow_room(), 1);
}

/// Guards: number - a slow reply window that can't fit between the collect deadline and the next tick, or is zero, is
/// refused at startup; one that just fits is not (step 7 design D3: budget).
#[test]
fn a_slow_reply_window_past_the_slack_is_refused() {
    let base = Timing::at_hz(250);
    let slack = base.period_ns - base.collect_ns;
    let rows = [
        (
            0,
            Some(TimingError::SlowReply {
                slow_reply_ns: 0,
                collect_ns: base.collect_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            slack + 1,
            Some(TimingError::SlowReply {
                slow_reply_ns: slack + 1,
                collect_ns: base.collect_ns,
                period_ns: base.period_ns,
            }),
        ),
        (slack, None),
    ];
    for (slow_reply_ns, refused) in rows {
        let timing = Timing {
            slow_reply_ns,
            ..base
        };
        assert_eq!(
            BusTick::new(&one_limb(&[id(101)]), timing).err(),
            refused.map(ConfigError::Timing),
            "{slow_reply_ns}"
        );
    }
}
