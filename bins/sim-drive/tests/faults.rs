//! Injected faults (PLAN item 4 Fault injection): what each one does to the simulated drive's answers, when a scheduled
//! one fires, and the record of every injection, so a test can prove each stop rule against it (step 7 design D6).

mod common;

use std::time::{Duration, Instant};

use common::{ask, host, id, mode_of, ms, neutral, replies, rs03};
use robstride::{
    CanTimeout, Celsius, Damper, Inbound, Mode, Model, Param, ParamOutcome, ParamValue,
    StatusFault, StatusFaults, Uid, Volts, Write, encode,
};
use sim_drive::{
    FAULT_PLAN, Fault, FaultRefused, INJECTED_LOG, Injected, MAX_LATE, MAX_TEMPERATURE_C, SimDrive,
    Trigger,
};

/// Drive 7, enabled and in Run by `t + 11 ms`, with every reply so far taken.
fn running() -> (SimDrive, Instant) {
    running_from(Instant::now())
}

/// Drive 7, enabled at `t` and in Run by `t + 11 ms`, with every reply so far taken.
fn running_from(t: Instant) -> (SimDrive, Instant) {
    let mut sim = SimDrive::new(rs03(7), Uid([7; 8]), 11);
    sim.receive(t, host(encode::enable(id(7))));
    let up = t + ms(11);
    assert_eq!(
        replies(&mut sim, up)
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Run)]
    );
    (sim, up)
}

/// An MIT target of `position` with a stiff enough gain to move the joint.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the values are in the RS03's ranges"
)]
fn mit_to(position: f64) -> robstride::Frame {
    let command = robstride::MitCommand {
        position: robstride::Radians::new(position).unwrap(),
        velocity: robstride::RadPerSec::new(0.0).unwrap(),
        kp: robstride::NmPerRad::new(10.0).unwrap(),
        kd: robstride::NmSecPerRad::new(1.0).unwrap(),
        torque: robstride::NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(rs03(7), &command).unwrap()
}

/// The position in the first status.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the drive is an RS03 and answers with a status"
)]
fn position_of(inbound: &[Inbound]) -> f64 {
    inbound
        .iter()
        .find_map(|i| match i {
            Inbound::Status(s) => Some(s.feedback(Model::Rs03).unwrap().position.get()),
            _ => None,
        })
        .unwrap()
}

/// What a status says: its mode, its fault bits and its temperature.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the drive is an RS03, whose scales are settled"
)]
fn status_of(inbound: &[Inbound]) -> Vec<(Mode, StatusFaults, f64)> {
    inbound
        .iter()
        .filter_map(|i| match i {
            Inbound::Status(s) => Some((
                s.header.mode,
                s.header.faults,
                s.feedback(Model::Rs03).unwrap().temperature.get(),
            )),
            _ => None,
        })
        .collect()
}

fn read(sim: &mut SimDrive, at: Instant, param: Param) -> Vec<Inbound> {
    ask(sim, at, encode::param_read(id(7), param))
}

fn value(param: Param, v: ParamValue) -> Vec<Inbound> {
    vec![Inbound::Param {
        device: id(7),
        param,
        outcome: ParamOutcome::Read(v),
    }]
}

/// Guards: protocol - the transport faults shape what goes on the bus and nothing else: a silent drive answers nothing,
/// a late one answers after the delay, dropped replies are lost and duplicated ones come twice, each for exactly the
/// count injected; a duplicate's second copy is a frame like any other, so a drive gone silent doesn't send it (PLAN
/// item 4: silent drive, late, dropped and duplicated frames).
#[test]
fn transport_faults_shape_the_replies() {
    let count = |sim: &mut SimDrive, at: Instant| ask(sim, at, neutral(7)).len();

    let (mut sim, t) = running();
    sim.inject(t, Fault::Silent).unwrap();
    assert_eq!(count(&mut sim, t), 0);
    assert_eq!(
        replies(&mut sim, t + ms(100)).len(),
        0,
        "nothing later either"
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Late(ms(3))).unwrap();
    assert_eq!(count(&mut sim, t), 0);
    assert_eq!(
        replies(
            &mut sim,
            (t + ms(3)).checked_sub(Duration::from_micros(1)).unwrap()
        )
        .len(),
        0
    );
    assert_eq!(replies(&mut sim, t + ms(3)).len(), 1);

    let (mut sim, t) = running();
    sim.inject(t, Fault::Drop(2)).unwrap();
    assert_eq!(
        [count(&mut sim, t), count(&mut sim, t), count(&mut sim, t)],
        [0, 0, 1]
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Duplicate(1)).unwrap();
    assert_eq!([count(&mut sim, t), count(&mut sim, t)], [2, 1]);

    let (mut sim, t) = running();
    sim.inject(t, Fault::Duplicate(1)).unwrap();
    sim.receive(t, host(neutral(7)));
    assert!(sim.pop_due(t).is_some(), "the first copy");
    sim.inject(t, Fault::Silent).unwrap();
    assert_eq!(replies(&mut sim, t + ms(10)).len(), 0, "no second copy");
}

/// Guards: safety - the drive-state faults show in every status from then on: fault bits, a mode the host didn't ask
/// for (the drive stays in it), and the temperature (PLAN item 4: fault
/// bits, wrong mode; item 6 Faults, States and Temperature rows).
#[test]
fn state_faults_show_in_every_status() {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut sim, t) = running();
    sim.inject(t, Fault::FaultBits(over)).unwrap();
    sim.inject(t, Fault::Temperature(Celsius::new(61.0).unwrap()))
        .unwrap();
    assert_eq!(
        status_of(&ask(&mut sim, t, neutral(7))),
        [(Mode::Run, over, 61.0)]
    );
    assert_eq!(
        status_of(&ask(&mut sim, t + ms(1), neutral(7))),
        [(Mode::Run, over, 61.0)]
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Mode(Mode::Reset)).unwrap();
    assert_eq!(
        status_of(&ask(&mut sim, t, neutral(7))),
        [(Mode::Reset, StatusFaults::default(), 25.0)]
    );
    assert_eq!(
        ask(&mut sim, t + ms(1), neutral(7))
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Reset)],
        "it stays where the fault put it"
    );
}

/// Guards: safety - the faults preflight must catch: a register that reads out of window (VBUS, the damper), a write
/// the drive answers but doesn't keep (the read-back shows the old value), and a reboot mid-run that puts every
/// register back to its default; the joint's position register reads where the joint is unless a value is injected
/// (PLAN item 4: VBUS out of range, read-back mismatch, reboot mid-run; item 6 drive layer).
#[test]
fn register_faults_are_what_preflight_reads_back() {
    let (mut sim, t) = running();
    let low = ParamValue::Volts(Volts::new(17.5).unwrap());
    sim.inject(t, Fault::Param(Param::Vbus, low)).unwrap();
    sim.inject(
        t,
        Fault::Param(Param::Damper, ParamValue::Damper(Damper::ProtectionOff)),
    )
    .unwrap();
    assert_eq!(read(&mut sim, t, Param::Vbus), value(Param::Vbus, low));
    assert_eq!(
        read(&mut sim, t, Param::Damper),
        value(Param::Damper, ParamValue::Damper(Damper::ProtectionOff))
    );

    sim.inject(t, Fault::IgnoreWrites(Param::CanTimeout))
        .unwrap();
    let answered = ask(
        &mut sim,
        t,
        encode::param_write(&Write::can_timeout(rs03(7))),
    );
    assert_eq!(
        answered.iter().map(mode_of).collect::<Vec<_>>(),
        [Some(Mode::Run)]
    );
    assert_eq!(
        read(&mut sim, t, Param::CanTimeout),
        value(Param::CanTimeout, ParamValue::CanTimeout(CanTimeout::OFF))
    );

    // The joint's position reads as it is now; an injected value holds instead.
    let (mut sim, t) = running();
    let _ = ask(&mut sim, t, mit_to(1.0));
    let moved = position_of(&ask(&mut sim, t + ms(100), mit_to(1.0)));
    assert!(moved > 0.1, "{moved}");
    let read_back = match read(&mut sim, t + ms(100), Param::MechPos).as_slice() {
        [
            Inbound::Param {
                outcome: ParamOutcome::Read(ParamValue::Radians(p)),
                ..
            },
        ] => Some(p.get()),
        _ => None,
    }
    .unwrap();
    assert!((read_back - moved).abs() < 1e-3, "{read_back} {moved}");
    let stuck = ParamValue::Radians(robstride::Radians::new(-2.0).unwrap());
    sim.inject(t + ms(100), Fault::Param(Param::MechPos, stuck))
        .unwrap();
    assert_eq!(
        read(&mut sim, t + ms(200), Param::MechPos),
        value(Param::MechPos, stuck)
    );

    // A reboot: Reset, and the written register back to its default.
    let (mut sim, t) = running();
    ask(
        &mut sim,
        t,
        encode::param_write(&Write::can_timeout(rs03(7))),
    );
    sim.inject(t, Fault::Reboot).unwrap();
    assert_eq!(
        ask(&mut sim, t, neutral(7))
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Reset)]
    );
    assert_eq!(
        read(&mut sim, t, Param::CanTimeout),
        value(Param::CanTimeout, ParamValue::CanTimeout(CanTimeout::OFF))
    );
}

/// Guards: safety - a Disable the drive loses changes nothing: no reply, the drive stays in Run, and `canTimeout` keeps
/// counting from the last frame it did take, so the drive's own timeout still backs up a stop whose Disables are lost;
/// for exactly the count injected, then the next Disable works (PLAN item 2 Stop: a stop records sent, confirmed or
/// unconfirmed per drive; item 6 drive layer).
#[test]
fn a_lost_disable_leaves_the_drive_running() {
    let (mut sim, t) = running();
    sim.inject(t, Fault::IgnoreDisables(1)).unwrap();
    assert_eq!(ask(&mut sim, t, encode::disable(id(7))), []);
    assert_eq!(
        ask(&mut sim, t, neutral(7))
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Run)]
    );
    assert_eq!(
        ask(&mut sim, t, encode::disable(id(7)))
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Reset)]
    );

    // canTimeout 50 ms from the last command at `t`; lost Disables at 20 and 40 ms don't restart it.
    let (mut sim, t) = running();
    let _ = ask(
        &mut sim,
        t,
        encode::param_write(&Write::can_timeout(rs03(7))),
    );
    sim.inject(t, Fault::IgnoreDisables(2)).unwrap();
    assert_eq!(ask(&mut sim, t + ms(20), encode::disable(id(7))), []);
    assert_eq!(ask(&mut sim, t + ms(40), encode::disable(id(7))), []);
    assert_eq!(
        status_of(&ask(&mut sim, t + ms(51), neutral(7))),
        [(Mode::Reset, StatusFaults::default(), 25.0)],
        "timed out 50 ms after the last frame it took"
    );
}

/// Guards: protocol - an injected fault reaches what the drive hasn't sent yet: a Silent or a Mode(Reset) injected
/// between an Enable and its Run reply stops that reply, fault bits injected then show in it, a Late delays a reply
/// already waiting, and a reboot lets out only what the transport faults in effect let go before it (PLAN item 4: the
/// injected fault is what the bus sees from then on).
#[test]
fn faults_reach_replies_not_yet_sent() {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    // Seed 3's enable takes some milliseconds, so nothing is due at the Enable itself.
    let enabling = || {
        let mut sim = SimDrive::new(rs03(7), Uid([7; 8]), 3);
        let t = Instant::now();
        assert_eq!(ask(&mut sim, t, encode::enable(id(7))), [], "a delay");
        (sim, t)
    };
    for (fault, expected) in [
        (Fault::Silent, vec![]),
        (Fault::Mode(Mode::Reset), vec![]),
        (Fault::FaultBits(over), vec![(Mode::Run, over, 25.0)]),
    ] {
        let (mut sim, t) = enabling();
        sim.inject(t, fault).unwrap();
        assert_eq!(
            status_of(&replies(&mut sim, t + ms(20))),
            expected,
            "{fault:?}"
        );
    }

    // A reply queued before the Late, not yet sent, goes out late too.
    let (mut sim, t) = running();
    sim.receive(t, host(neutral(7)));
    sim.inject(t, Fault::Late(ms(5))).unwrap();
    assert_eq!(replies(&mut sim, t + ms(4)).len(), 0);
    assert_eq!(replies(&mut sim, t + ms(5)).len(), 1);

    // A reboot lets out what was due before it, as far as the faults in effect let it go, whether or not the host read
    // in between, and loses the rest; what it let out went before the power went, so a fault injected after it
    // doesn't reach it.
    for (fault, reboot_after, expected) in [
        (None, ms(1), 1),
        (Some(Fault::Silent), ms(1), 0),
        (Some(Fault::Drop(1)), ms(1), 0),
        (Some(Fault::Late(ms(5))), ms(1), 0),
        (Some(Fault::Late(ms(5))), ms(5), 1),
        (Some(Fault::Duplicate(1)), ms(1), 2),
    ] {
        for read_first in [false, true] {
            let (mut sim, t) = running();
            if let Some(fault) = fault {
                sim.inject(t, fault).unwrap();
            }
            sim.receive(t, host(neutral(7)));
            let read = if read_first {
                replies(&mut sim, t).len()
            } else {
                0
            };
            sim.inject(t + reboot_after, Fault::Reboot).unwrap();
            sim.inject(t + reboot_after, Fault::Silent).unwrap();
            assert_eq!(
                read + replies(&mut sim, t + ms(10)).len(),
                expected,
                "{fault:?}, reboot after {reboot_after:?}, read first: {read_first}"
            );
        }
    }
}

/// Guards: protocol - timed faults land at their own times, in time order, however late the drive is stepped (even
/// first stepped after them): a Mode
/// fault holds the joint where it was then, a Mode(Run) starts `canTimeout` counting then, and two faults due at once
/// apply oldest first, as their record shows (logging.md section 3: the record matches what was applied).
#[test]
fn timed_faults_land_in_time_order() {
    let (mut sim, t) = running();
    assert_eq!(sim.schedule(Trigger::At(t + ms(20)), Fault::Reboot), Ok(()));
    assert_eq!(sim.schedule(Trigger::At(t + ms(10)), Fault::Silent), Ok(()));
    // Stepped once, past both: silent at 10 ms, then the reboot at 20 ms clears it.
    assert_eq!(
        ask(&mut sim, t + ms(30), neutral(7))
            .iter()
            .map(mode_of)
            .collect::<Vec<_>>(),
        [Some(Mode::Reset)]
    );
    let record: Vec<_> = std::iter::from_fn(|| sim.take_injected())
        .map(|i| (i.at, i.fault))
        .collect();
    assert_eq!(
        record,
        [(t + ms(10), Fault::Silent), (t + ms(20), Fault::Reboot)]
    );

    // The joint moving toward a target stops when the drive drops to Reset at 10 ms, not when it is next stepped.
    let target = mit_to(1.0);
    let start = Instant::now();
    let (mut late, t) = running_from(start);
    let (mut on_time, _) = running_from(start);
    for sim in [&mut late, &mut on_time] {
        let _ = ask(sim, t, target);
    }
    assert_eq!(
        late.schedule(Trigger::At(t + ms(10)), Fault::Mode(Mode::Reset)),
        Ok(())
    );
    on_time
        .inject(t + ms(10), Fault::Mode(Mode::Reset))
        .unwrap();
    let position = |sim: &mut SimDrive| position_of(&ask(sim, t + ms(200), neutral(7)));
    let held = position(&mut on_time);
    assert!(held > 0.01, "it moved first: {held}");
    assert!((position(&mut late) - held).abs() < 1e-3, "{held}");

    // Scheduled on a drive not yet stepped, faults still land at their own times, not at its first step: canTimeout
    // written at `t` and Run at 10 ms, so by the first step at 70 ms it has timed out.
    let mut sim = SimDrive::new(rs03(7), Uid([7; 8]), 11);
    let t = Instant::now();
    let runtime = Fault::Param(
        Param::CanTimeout,
        ParamValue::CanTimeout(CanTimeout::RUNTIME),
    );
    assert_eq!(sim.schedule(Trigger::At(t), runtime), Ok(()));
    assert_eq!(
        sim.schedule(Trigger::At(t + ms(10)), Fault::Mode(Mode::Run)),
        Ok(())
    );
    assert_eq!(
        status_of(&ask(&mut sim, t + ms(70), neutral(7))),
        [(Mode::Reset, StatusFaults::default(), 25.0)],
        "timed out at 60 ms"
    );
    let record: Vec<_> = std::iter::from_fn(|| sim.take_injected())
        .map(|i| (i.at, i.fault))
        .collect();
    assert_eq!(record, [(t, runtime), (t + ms(10), Fault::Mode(Mode::Run))]);

    // A drive in Reset, canTimeout written and reporting on at `t`, put in Run by a fault: it times out 50 ms after
    // that, not at once. The reports show the mode without a command restarting the count.
    let timing_out = |fault_at| {
        let mut sim = SimDrive::new(rs03(7), Uid([7; 8]), 11);
        let t = Instant::now();
        let _ = ask(
            &mut sim,
            t,
            encode::param_write(&Write::can_timeout(rs03(7))),
        );
        let _ = ask(
            &mut sim,
            t,
            encode::active_reporting(id(7), robstride::Reporting::On),
        );
        assert_eq!(
            sim.schedule(Trigger::At(t + fault_at), Fault::Mode(Mode::Run)),
            Ok(())
        );
        (sim, t)
    };
    let (mut sim, t) = timing_out(ms(100));
    let modes: Vec<_> = replies(&mut sim, t + ms(160)).iter().map(mode_of).collect();
    let (run, reset) = (Some(Mode::Run), Some(Mode::Reset));
    assert_eq!(
        modes,
        [
            reset, reset, reset, reset, reset, reset, reset, reset, reset, run, run, run, run, run,
            reset, reset
        ],
        "reports at 10 to 160 ms"
    );
    // Stepped once over more reports than the outbox holds, the fault and the timeout still land at their own times.
    let (mut sim, t) = timing_out(ms(900));
    let end = t + ms(1200);
    let _ = replies(&mut sim, end);
    assert_eq!(sim.take_injected().map(|i| i.at), Some(t + ms(900)));
    assert_eq!(
        status_of(&ask(&mut sim, end, neutral(7))),
        [(Mode::Reset, StatusFaults::default(), 25.0)],
        "timed out at 950 ms"
    );
}

/// Guards: protocol - a fault the drive can't honour is refused and not recorded: a `Late` past `MAX_LATE`, a
/// temperature a status can't carry, a register value of the wrong type, `OnMit(0)`, a time the drive is already past;
/// and writes ignored for any number
/// of registers, or one register twice, all hold (logging.md section 3: what is recorded is what took effect).
#[test]
fn faults_the_drive_cant_honour_are_refused() {
    let (mut sim, t) = running();
    let rows = [
        (
            Fault::Late(MAX_LATE + Duration::from_micros(1)),
            FaultRefused::TooLate,
        ),
        (
            Fault::Temperature(Celsius::new(-0.1).unwrap()),
            FaultRefused::Temperature,
        ),
        (
            Fault::Temperature(Celsius::new(MAX_TEMPERATURE_C + 0.1).unwrap()),
            FaultRefused::Temperature,
        ),
        (
            Fault::Param(Param::Vbus, ParamValue::Damper(Damper::ProtectionOff)),
            FaultRefused::WrongType(Param::Vbus),
        ),
    ];
    for (fault, refused) in rows {
        assert_eq!(sim.inject(t, fault), Err(refused), "{fault:?}");
        assert_eq!(
            sim.schedule(Trigger::At(t), fault),
            Err(refused),
            "{fault:?}"
        );
    }
    assert_eq!(
        sim.schedule(Trigger::OnMit(0), Fault::Silent),
        Err(FaultRefused::OnMitZero)
    );
    let before = t.checked_sub(Duration::from_micros(1)).unwrap();
    assert_eq!(
        sim.schedule(Trigger::At(before), Fault::Silent),
        Err(FaultRefused::Past)
    );
    assert_eq!(sim.inject(before, Fault::Silent), Err(FaultRefused::Past));
    assert_eq!(sim.inject(t, Fault::Late(MAX_LATE)), Ok(()), "at the limit");
    assert_eq!(
        sim.take_injected().map(|i| i.fault),
        Some(Fault::Late(MAX_LATE))
    );
    assert_eq!(sim.take_injected(), None, "nothing refused was recorded");

    let (mut sim, t) = running();
    let params = [
        Param::LimitTorque,
        Param::LimitSpd,
        Param::LimitCur,
        Param::EpScanTime,
        Param::LimitTorque,
        Param::CanTimeout,
    ];
    for param in params {
        sim.inject(t, Fault::IgnoreWrites(param)).unwrap();
    }
    let _ = ask(
        &mut sim,
        t,
        encode::param_write(&Write::can_timeout(rs03(7))),
    );
    assert_eq!(
        read(&mut sim, t, Param::CanTimeout),
        value(Param::CanTimeout, ParamValue::CanTimeout(CanTimeout::OFF)),
        "the sixth ignored register holds too"
    );
}

/// Guards: protocol - a scheduled fault fires exactly when its trigger says, on the nth MIT command (that command's
/// reply already shows it) or at a time, and every injection is recorded once with its time, drive and fault, so a
/// replay shows what was injected (logging.md section 3: injected faults recorded as injected). The plan and the
/// record are bounded, and what the record has no room for is counted.
#[test]
fn scheduled_faults_fire_on_their_trigger_and_are_recorded() {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut sim, t) = running();
    assert_eq!(
        sim.schedule(Trigger::OnMit(3), Fault::FaultBits(over)),
        Ok(())
    );
    assert_eq!(sim.schedule(Trigger::At(t + ms(20)), Fault::Silent), Ok(()));
    let faults_at =
        |sim: &mut SimDrive, at| status_of(&ask(sim, at, neutral(7))).first().map(|s| s.1);
    assert_eq!(faults_at(&mut sim, t), Some(StatusFaults::default()));
    assert_eq!(
        faults_at(&mut sim, t + ms(1)),
        Some(StatusFaults::default())
    );
    assert_eq!(sim.take_injected(), None);
    assert_eq!(
        faults_at(&mut sim, t + ms(2)),
        Some(over),
        "the third MIT's reply"
    );
    assert_eq!(
        sim.take_injected(),
        Some(Injected {
            at: t + ms(2),
            device: id(7),
            fault: Fault::FaultBits(over),
        })
    );
    assert_eq!(
        faults_at(
            &mut sim,
            (t + ms(20)).checked_sub(Duration::from_micros(1)).unwrap()
        ),
        Some(over)
    );
    assert_eq!(faults_at(&mut sim, t + ms(20)), None, "silent from 20 ms");
    assert_eq!(
        sim.take_injected(),
        Some(Injected {
            at: t + ms(20),
            device: id(7),
            fault: Fault::Silent,
        })
    );
    assert_eq!(sim.take_injected(), None);

    // Injected now: recorded too. The plan outlives the reboot.
    assert_eq!(sim.schedule(Trigger::At(t + ms(40)), Fault::Silent), Ok(()));
    sim.inject(t + ms(30), Fault::Reboot).unwrap();
    assert_eq!(sim.take_injected().map(|i| i.fault), Some(Fault::Reboot));
    assert_eq!(
        faults_at(&mut sim, t + ms(39)),
        Some(StatusFaults::default())
    );
    assert_eq!(faults_at(&mut sim, t + ms(40)), None, "silent from 40 ms");

    // A bounded plan.
    let (mut sim, _) = running();
    for n in 0..u32::try_from(FAULT_PLAN).unwrap_or(u32::MAX) {
        assert_eq!(sim.schedule(Trigger::OnMit(n + 1), Fault::Drop(1)), Ok(()));
    }
    assert_eq!(
        sim.schedule(Trigger::OnMit(99), Fault::Drop(1)),
        Err(FaultRefused::PlanFull)
    );

    // A bounded record: past INJECTED_LOG untaken, the oldest stay and the newest is counted lost.
    let (mut sim, t) = running();
    for n in 0..=INJECTED_LOG {
        let n = u32::try_from(n).unwrap();
        sim.inject(t, Fault::Drop(n)).unwrap();
    }
    assert_eq!(sim.injections_lost(), 1);
    let kept: Vec<_> = std::iter::from_fn(|| sim.take_injected())
        .map(|i| i.fault)
        .collect();
    let first: Vec<_> = (0..INJECTED_LOG)
        .map(|n| Fault::Drop(u32::try_from(n).unwrap()))
        .collect();
    assert_eq!(kept, first, "oldest first");
}

/// Guards: protocol - one long step with reporting on keeps the reports the outbox can hold and counts the rest
/// dropped, exactly as many as a drive stepped every millisecond sends; a report the Set Zero blackout keeps off the bus
/// takes no room and isn't counted (can.md section 2: bounded queues, every drop counted).
#[test]
fn a_long_step_keeps_what_the_outbox_holds_and_counts_the_rest() {
    let span = 1200;
    let mut sent = Vec::new();
    for set_zero in [false, true] {
        let reporting = || {
            let (mut sim, t) = running();
            if set_zero {
                let _ = ask(&mut sim, t, encode::set_zero(id(7)));
            }
            let _ = ask(
                &mut sim,
                t,
                encode::active_reporting(id(7), robstride::Reporting::On),
            );
            (sim, t)
        };
        // Stepped every millisecond, its outbox never fills: everything it sends goes.
        let (mut often, t) = reporting();
        let reports: usize = (1..=span)
            .map(|n| replies(&mut often, t + ms(n)).len())
            .sum();
        assert_eq!(often.dropped(), 0, "set zero: {set_zero}");
        // Stepped once, it keeps the first 64 (the outbox) and counts the rest.
        let (mut once, t) = reporting();
        assert_eq!(
            (replies(&mut once, t + ms(span)).len(), once.dropped()),
            (64, u64::try_from(reports - 64).unwrap()),
            "set zero: {set_zero}"
        );
        sent.push(reports);
    }
    assert!(sent[1] < sent[0], "the blackout kept reports off: {sent:?}");
}

/// Guards: protocol - the record and the plan keep the order things happened in when a slot is freed and reused: an
/// injection recorded after one was taken comes after those still waiting at the same time, and a fault scheduled into
/// a freed slot fires after one scheduled before it for the same time (logging.md section 3).
#[test]
fn freed_slots_keep_the_order() {
    let (mut sim, t) = running();
    sim.inject(t, Fault::Drop(1)).unwrap();
    sim.inject(t, Fault::Drop(2)).unwrap();
    assert_eq!(sim.take_injected().map(|i| i.fault), Some(Fault::Drop(1)));
    sim.inject(t, Fault::Drop(3)).unwrap();
    let rest: Vec<_> = std::iter::from_fn(|| sim.take_injected())
        .map(|i| i.fault)
        .collect();
    assert_eq!(rest, [Fault::Drop(2), Fault::Drop(3)]);

    let (mut sim, t) = running();
    assert_eq!(sim.schedule(Trigger::At(t + ms(5)), Fault::Drop(1)), Ok(()));
    assert_eq!(
        sim.schedule(Trigger::At(t + ms(20)), Fault::Drop(2)),
        Ok(())
    );
    let _ = replies(&mut sim, t + ms(10));
    // The first slot is free again; the next fault takes it.
    assert_eq!(
        sim.schedule(Trigger::At(t + ms(20)), Fault::Drop(3)),
        Ok(())
    );
    let _ = replies(&mut sim, t + ms(30));
    let record: Vec<_> = std::iter::from_fn(|| sim.take_injected())
        .map(|i| (i.at, i.fault))
        .collect();
    assert_eq!(
        record,
        [
            (t + ms(5), Fault::Drop(1)),
            (t + ms(20), Fault::Drop(2)),
            (t + ms(20), Fault::Drop(3)),
        ]
    );
}
