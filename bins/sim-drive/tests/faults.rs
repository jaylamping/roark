//! Injected faults (PLAN item 4 Fault injection): what each one does to the simulated drive's answers, when a scheduled
//! one fires, and the record of every injection, so a test can prove each stop rule against it (step 7 design D6).

mod common;

use std::time::{Duration, Instant};

use common::{ask, host, id, mode_of, ms, neutral, replies, rs03};
use robstride::{
    CanTimeout, Celsius, Damper, Inbound, Mode, Model, Param, ParamOutcome, ParamValue,
    StatusFault, StatusFaults, Uid, Volts, Write, encode,
};
use sim_drive::{FAULT_PLAN, Fault, Injected, SimDrive, Trigger};

/// Drive 7, enabled and in Run by `t + 11 ms`, with every reply so far taken.
fn running() -> (SimDrive, Instant) {
    let mut sim = SimDrive::new(rs03(7), Uid([7; 8]), 11);
    let t = Instant::now();
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
/// count injected (PLAN item 4: silent drive, late, dropped and duplicated frames).
#[test]
fn transport_faults_shape_the_replies() {
    let count = |sim: &mut SimDrive, at: Instant| ask(sim, at, neutral(7)).len();

    let (mut sim, t) = running();
    sim.inject(t, Fault::Silent);
    assert_eq!(count(&mut sim, t), 0);
    assert_eq!(
        replies(&mut sim, t + ms(100)).len(),
        0,
        "nothing later either"
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Late(ms(3)));
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
    sim.inject(t, Fault::Drop(2));
    assert_eq!(
        [count(&mut sim, t), count(&mut sim, t), count(&mut sim, t)],
        [0, 0, 1]
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Duplicate(1));
    assert_eq!([count(&mut sim, t), count(&mut sim, t)], [2, 1]);
}

/// Guards: safety - the drive-state faults show in every status from then on: fault bits, a mode the host didn't ask
/// for (the drive really is in it, so `canTimeout` and the plant follow), and the temperature (PLAN item 4: fault
/// bits, wrong mode; item 6 Faults, States and Temperature rows).
#[test]
fn state_faults_show_in_every_status() {
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (mut sim, t) = running();
    sim.inject(t, Fault::FaultBits(over));
    sim.inject(t, Fault::Temperature(Celsius::new(61.0).unwrap()));
    assert_eq!(
        status_of(&ask(&mut sim, t, neutral(7))),
        [(Mode::Run, over, 61.0)]
    );
    assert_eq!(
        status_of(&ask(&mut sim, t + ms(1), neutral(7))),
        [(Mode::Run, over, 61.0)]
    );

    let (mut sim, t) = running();
    sim.inject(t, Fault::Mode(Mode::Reset));
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
/// register back to its default (PLAN item 4: VBUS out of range, read-back mismatch, reboot mid-run; item 6 drive layer).
#[test]
fn register_faults_are_what_preflight_reads_back() {
    let (mut sim, t) = running();
    let low = ParamValue::Volts(Volts::new(17.5).unwrap());
    sim.inject(t, Fault::Param(Param::Vbus, low));
    sim.inject(
        t,
        Fault::Param(Param::Damper, ParamValue::Damper(Damper::ProtectionOff)),
    );
    assert_eq!(read(&mut sim, t, Param::Vbus), value(Param::Vbus, low));
    assert_eq!(
        read(&mut sim, t, Param::Damper),
        value(Param::Damper, ParamValue::Damper(Damper::ProtectionOff))
    );

    sim.inject(t, Fault::IgnoreWrites(Param::CanTimeout));
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

    // A reboot: Reset, and the written register back to its default.
    let (mut sim, t) = running();
    ask(
        &mut sim,
        t,
        encode::param_write(&Write::can_timeout(rs03(7))),
    );
    sim.inject(t, Fault::Reboot);
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

/// Guards: safety - a Disable the drive loses changes nothing: no reply, and the drive stays in Run, for exactly the
/// count injected; the next Disable works (PLAN item 2 Stop: a stop records sent, confirmed or unconfirmed per drive).
#[test]
fn a_lost_disable_leaves_the_drive_running() {
    let (mut sim, t) = running();
    sim.inject(t, Fault::IgnoreDisables(1));
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
}

/// Guards: protocol - a scheduled fault fires exactly when its trigger says, on the nth MIT command (that command's
/// reply already shows it) or at a time, and every injection is recorded once with its time, drive and fault, so a
/// replay shows what was injected (logging.md section 3: injected faults recorded as injected). The plan is bounded.
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

    // Injected now: recorded too.
    sim.inject(t + ms(30), Fault::Reboot);
    assert_eq!(sim.take_injected().map(|i| i.fault), Some(Fault::Reboot));

    // A bounded plan.
    let (mut sim, _) = running();
    for n in 0..u32::try_from(FAULT_PLAN).unwrap_or(u32::MAX) {
        assert_eq!(sim.schedule(Trigger::OnMit(n + 1), Fault::Drop(1)), Ok(()));
    }
    assert!(sim.schedule(Trigger::OnMit(99), Fault::Drop(1)).is_err());
}
