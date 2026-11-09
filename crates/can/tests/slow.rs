//! Slow requests: parameter reads, allowlisted writes and get-ID, one in flight per bus, sent in the slack after the
//! collect deadline only when the reply fits before the next tick starts (PLAN.md item 3: parameter traffic only in the slack).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{
    BusTick, ConfigError, DRIVE_TIMEOUT_NS, LimbState, RearmRefused, SLOW_SLOTS, SendOutcome,
    SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult, StopReason, Timing, TimingError,
    Unsent,
};
use common::{
    MS, PERIOD, at, batch, bus, deadline, drive, error_frame, id, one_limb, record, run_tick,
    status, status_frame, stop_of, two_limbs,
};
use robstride::drive as wire;
use robstride::{
    CanTimeout, Mode, Param, ParamOutcome, ParamValue, RunMode, StatusFault, StatusFaults, Uid,
    Write, encode,
};
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
/// queued wait their turn in order (PLAN.md item 3: parameter traffic only in the slack; can.md section 2; crates/can/README.md, slow requests).
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
/// (can.md section 2; crates/can/README.md, slow requests: slow requests ride in the slack: one result, never retried).
#[test]
fn a_slow_request_is_reported_once_and_never_retried() {
    let mut bus = bus();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 0, Param::CanTimeout)), Ok(()));
    assert_eq!(bus.submit(read(2, 0, Param::RunMode)), Ok(()));
    assert_eq!(
        bus.slow_send(deadline(0)),
        Some(encode::param_read(id(101), Param::CanTimeout))
    );
    bus.slow_sent(SendOutcome::QueueFull, deadline(0));
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 1,
            slot: 0,
            outcome: SlowOutcome::NotSent(Unsent::QueueFull),
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
/// status, which answers only the write: it isn't a duplicate or unsolicited command reply, it proves nothing about the
/// value, and a fault it shows is latched like any status's. A slow frame's echo doesn't replace the drive's last echo (PLAN.md item 6: preflight reads every write back).
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
    let get_id = encode::get_id(id(102));
    assert_eq!(bus.slow_send(deadline(0)), Some(get_id));
    bus.slow_sent(SendOutcome::Sent, deadline(0));
    // Its echo isn't the drive's last echo: that is kept for the tick's own frames.
    bus.on_frame(
        deadline(0) + MS / 8,
        &record(get_id.id(), get_id.data(), Direction::TxEcho),
    );
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
    // The answer shows a fault: it answers the write, and the fault is latched all the same.
    bus.on_frame(2 * PERIOD - MS, &faulted(101, Mode::Reset));
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 8,
            slot: 0,
            outcome: SlowOutcome::WriteAnswered,
        })
    );
    assert_eq!(
        bus.submit(read(9, 0, Param::CanTimeout)),
        Err(SlowRefusal::LimbStopped)
    );
    run_tick(&mut bus, 2, Some(&batch(2, &[])), &[]);
    let snap = bus.end(deadline(2));
    assert_eq!((snap.counters.unsolicited, snap.counters.duplicate), (0, 0));
    assert_eq!(snap.counters.echoes, 1);
    assert_eq!(at(&snap, 1).last_echo, None);
    assert_eq!(stop_of(&snap), Some(StopReason::DriveFault { slot: 0 }));
}

/// Guards: safety - slow requests never keep a drive alive past a stop or a silent control thread: one for a drive in
/// a stopping or stopped limb, or while control is silent (even with every limb idle, as during preflight), or on a
/// failed bus, is refused, and one already queued is cancelled before it goes, while the bus's other limb is served
/// (PLAN.md item 6: a stop latches; `canTimeout` counts from any frame).
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

/// Guards: protocol - a slow request names a drive the bus owns, a write is built for that drive and is never one only
/// control's batch sends, and the queue is bounded: past `SLOW_SLOTS` (counting results not yet taken) it refuses, and taking a result frees a slot (can.md
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
    // The enable sequence's write: its echo would pass for the sequence's own.
    assert_eq!(
        bus.submit(SlowRequest {
            tag: 3,
            slot: 0,
            kind: SlowKind::Write(Write::mit_mode(drive(101))),
        }),
        Err(SlowRefusal::BatchOnly)
    );
    for tag in 0..u32::try_from(SLOW_SLOTS).unwrap_or(u32::MAX) {
        assert_eq!(bus.submit(read(tag, 0, Param::CanTimeout)), Ok(()));
    }
    assert_eq!(bus.slow_room(), 0);
    assert_eq!(
        bus.submit(read(99, 0, Param::CanTimeout)),
        Err(SlowRefusal::QueueFull)
    );
    assert_eq!(
        bus.slow_send(deadline(0)),
        Some(encode::param_read(id(101), Param::CanTimeout))
    );
    bus.slow_sent(SendOutcome::Failed, deadline(0));
    assert_eq!(bus.slow_room(), 0, "a result not yet taken holds its slot");
    assert_eq!(
        bus.take_slow_result(),
        Some(SlowResult {
            tag: 0,
            slot: 0,
            outcome: SlowOutcome::NotSent(Unsent::Failed),
        })
    );
    assert_eq!(bus.slow_room(), 1);
}

/// Guards: number - a slow reply window that fills the whole slack between the collect deadline and the next tick
/// (the shell sends only after the deadline, so nothing could go), or is zero, is refused at startup; one a nanosecond
/// shorter is not (PLAN.md item 3: parameter traffic only in the slack).
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
            slack,
            Some(TimingError::SlowReply {
                slow_reply_ns: slack,
                collect_ns: base.collect_ns,
                period_ns: base.period_ns,
            }),
        ),
        (slack - 1, None),
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

/// Drive `n`'s status in `mode` showing an overcurrent fault.
fn faulted(n: u8, mode: Mode) -> telemetry::FrameRecord {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let f = status_frame(n, mode, over);
    record(f.id(), f.data(), Direction::TxOther)
}

/// Guards: safety - a slow frame is a send, so the slack refuses what the veto would stop at the next send: a fault
/// read in the collect on any drive of the limb, or a stop asked for and not yet taken, refuses the request at once;
/// and a write goes only to a drive of an idle limb with no command of that tick unanswered, so its status answer can't
/// pass for a command's reply (can.md section 2; crates/can/README.md, slow requests: check before every send).
#[test]
fn the_slack_refuses_what_the_veto_would_stop_and_writes_to_a_running_limb() {
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    bus.on_frame(deadline(0) - MS, &faulted(101, Mode::Reset));
    assert_eq!(
        bus.submit(read(1, 0, Param::Vbus)),
        Err(SlowRefusal::LimbStopped)
    );
    assert_eq!(bus.submit(read(2, 1, Param::Vbus)), Ok(()));

    // The veto stops the whole limb, so a fault on one drive refuses its limb-mate's request too.
    let mut bus = common::bus();
    quiet_tick(&mut bus, 0);
    bus.on_frame(deadline(0) - MS, &faulted(101, Mode::Reset));
    assert_eq!(
        bus.submit(read(1, 1, Param::Vbus)),
        Err(SlowRefusal::LimbStopped)
    );

    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.stop_limb(1), Ok(()));
    assert_eq!(
        bus.submit(read(3, 1, Param::Vbus)),
        Err(SlowRefusal::LimbStopped),
        "asked for, not yet taken"
    );

    // Limb 0 running, limb 1 idle.
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    run_tick(
        &mut bus,
        1,
        Some(&batch(1, &[Some(encode::enable(id(101)))])),
        &[(MS, status(101, Mode::Run))],
    );
    let _ = bus.end(deadline(1));
    let write = |tag, n: u8| SlowRequest {
        tag,
        slot: usize::from(n - 101),
        kind: SlowKind::Write(Write::can_timeout(drive(n))),
    };
    assert_eq!(bus.submit(write(4, 101)), Err(SlowRefusal::LimbNotIdle));
    assert_eq!(bus.submit(read(5, 0, Param::Vbus)), Ok(()), "a read may go");
    assert_eq!(bus.submit(write(6, 102)), Ok(()));

    // An idle limb's drive with a batch Disable still unanswered: a late reply could pass for the write's answer.
    let mut bus = two_limbs();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[None, Some(encode::disable(id(102)))])),
        &[],
    );
    let _ = bus.end(deadline(0));
    assert_eq!(
        bus.submit(write(7, 102)),
        Err(SlowRefusal::CommandUnanswered)
    );
    assert_eq!(bus.submit(read(8, 1, Param::Vbus)), Ok(()), "a read may go");
    // Only the tick's own command: by the next tick its reply is late or lost, and a lost one doesn't hold writes off.
    // The cost, accepted: a reply more than a tick late can pass for this write's answer, so the read-back proves the value.
    quiet_tick(&mut bus, 1);
    assert_eq!(bus.submit(write(9, 102)), Ok(()));

    // Answered in its tick: the write may go at once.
    let mut bus = two_limbs();
    run_tick(
        &mut bus,
        0,
        Some(&batch(0, &[None, Some(encode::disable(id(102)))])),
        &[(MS, status(102, Mode::Reset))],
    );
    let _ = bus.end(deadline(0));
    assert_eq!(bus.submit(write(10, 102)), Ok(()));
}

/// Guards: protocol - every request gets exactly one result when the bus thread ends with it held: one in flight has
/// timed out, a queued one is refused (`Ended`, or `BusFailed` on a failed bus), and a result not yet taken is kept
/// (can.md section 2; crates/can/README.md, slow requests: slow requests ride in the slack; `BusLinks::results`).
#[test]
fn every_request_held_gets_its_result_when_the_thread_ends() {
    for (bus_failed, refusal) in [(false, SlowRefusal::Ended), (true, SlowRefusal::BusFailed)] {
        let mut bus = two_limbs();
        quiet_tick(&mut bus, 0);
        for tag in 1..=3 {
            assert_eq!(bus.submit(read(tag, 1, Param::Vbus)), Ok(()));
        }
        // Tag 1 answered and not taken, tag 2 in flight, tag 3 queued.
        assert_eq!(
            bus.slow_send(deadline(0)),
            Some(encode::param_read(id(102), Param::Vbus))
        );
        bus.slow_sent(SendOutcome::Sent, deadline(0));
        bus.on_frame(
            deadline(0) + MS / 4,
            &param_reply(
                102,
                Param::Vbus,
                ParamValue::Volts(robstride::Volts::new(24.0).unwrap()),
            ),
        );
        quiet_tick(&mut bus, 1);
        assert_eq!(
            bus.slow_send(deadline(1)),
            Some(encode::param_read(id(102), Param::Vbus))
        );
        bus.slow_sent(SendOutcome::Sent, deadline(1));
        if bus_failed {
            bus.on_frame(deadline(1) + 1, &error_frame(0x40, 0));
        }
        assert_eq!(bus.end_slow(), refusal);
        let results: Vec<_> = std::iter::from_fn(|| bus.take_slow_result())
            .map(|r| (r.tag, r.outcome))
            .collect();
        assert_eq!(
            results,
            [
                (
                    1,
                    SlowOutcome::Read(ParamOutcome::Read(ParamValue::Volts(
                        robstride::Volts::new(24.0).unwrap()
                    )))
                ),
                (2, SlowOutcome::TimedOut),
                (3, SlowOutcome::Refused(refusal)),
            ],
            "bus failed: {bus_failed}"
        );
        assert_eq!(bus.slow_room(), SLOW_SLOTS);
    }
}

/// Guards: safety - a slow frame the socket took counts as this host's last frame to the drive, so it holds a stopped
/// limb's re-arm off for the drive timeout after it like any send: the drive's `canTimeout` counts from any frame
/// (can.md section 2: re-arm only once each drive has been sent nothing past the drive timeout).
#[test]
fn a_slow_send_holds_off_the_rearm() {
    let mut bus = two_limbs();
    quiet_tick(&mut bus, 0);
    assert_eq!(bus.submit(read(1, 0, Param::Vbus)), Ok(()));
    let slow_at = deadline(0) + MS / 2;
    assert_eq!(
        bus.slow_send(slow_at),
        Some(encode::param_read(id(101), Param::Vbus))
    );
    bus.slow_sent(SendOutcome::Sent, slow_at);
    assert_eq!(bus.stop_limb(0), Ok(()));
    // Every Disable is refused by the socket, so the slow read stays the last frame the drive was sent.
    let mut tick = 1;
    loop {
        let start = tick * PERIOD;
        let list = bus.begin(tick, start, start, Some(&batch(tick, &[])));
        for (index, _) in list.iter().enumerate() {
            bus.sent(index, SendOutcome::QueueFull, start);
        }
        if state_of_limb(&bus.end(deadline(tick)), 0) == LimbState::Stopped {
            break;
        }
        tick += 1;
    }
    assert_eq!(
        bus.submit(read(2, 0, Param::Vbus)),
        Err(SlowRefusal::LimbStopped),
        "stopped, on a healthy bus"
    );
    let quiet = DRIVE_TIMEOUT_NS + PERIOD;
    assert_eq!(
        bus.rearm(0, slow_at + quiet - 1),
        Err(RearmRefused::DriveNotQuiet { slot: 0 })
    );
    assert_eq!(bus.rearm(0, slow_at + quiet), Ok(()));
}

fn state_of_limb(snap: &can::Snapshot, limb: usize) -> LimbState {
    snap.limb(limb).map_or(LimbState::Idle, |l| l.state)
}
