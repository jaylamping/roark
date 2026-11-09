//! Preflight's refusals, one table per rule (PLAN item 6 drive layer and Preflight row; safety.md section 6.1). Each row
//! runs the whole preflight against a drive that answers every request truthfully except the one the row changes.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{DriveView, SendOutcome, SlowKind, SlowOutcome, SlowRefusal};
use common::{joint, quiet, seen, skeleton, status};
use robstride::{
    Amps, CanTimeout, Damper, Mode, NewtonMeters, Param, ParamOutcome, ParamValue, RadPerSec,
    StatusFault, StatusFaults, Uid, Volts,
};
use safety::{CapKind, Exchange, Preflight, Refusal, RuleId, Step, Target, Unanswered};

/// The fixture's UID for `arm_joint_one`.
const UID: Uid = Uid([0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef]);

fn exchange_of(kind: SlowKind) -> Exchange {
    match kind {
        SlowKind::GetId => Exchange::Identity,
        SlowKind::Write(w) => Exchange::Write(w.param()),
        SlowKind::Read(p) => Exchange::Read(p),
    }
}

/// How the drive in a row behaves.
struct Drive {
    /// The answer to one exchange, in place of the truth.
    answer: Option<(Exchange, SlowOutcome)>,
    /// The status every write's answer carries; `None` for a drive whose statuses never come.
    status: Option<(Mode, StatusFaults)>,
    /// The view before preflight begins.
    before: DriveView,
}

impl Drive {
    fn honest() -> Self {
        Self {
            answer: None,
            status: Some((Mode::Reset, StatusFaults::default())),
            before: quiet(),
        }
    }

    fn answering(exchange: Exchange, outcome: SlowOutcome) -> Self {
        Self {
            answer: Some((exchange, outcome)),
            ..Self::honest()
        }
    }

    fn reading(param: Param, value: ParamValue) -> Self {
        Self::answering(
            Exchange::Read(param),
            SlowOutcome::Read(ParamOutcome::Read(value)),
        )
    }
}

/// Run preflight for joint `n` of the fixture against `drive`: the verdict, and every write submitted.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; the fixture's first joint has every cap"
)]
fn run(n: usize, drive: &Drive) -> (Result<(), Refusal>, Vec<(Param, ParamValue)>) {
    let skeleton = skeleton();
    let target = match Target::new(&joint(&skeleton, n), &skeleton.power) {
        Ok(target) => target,
        Err(refusal) => return (Err(refusal), Vec::new()),
    };
    let mut now = 1_000;
    let mut preflight = Preflight::start(target, now);
    let mut view = drive.before;
    let mut written = Vec::new();
    for _ in 0..32 {
        now += 4_000_000;
        let kind = match preflight.poll(&view, now) {
            Step::Submit(kind) => kind,
            Step::Passed(passed) => {
                assert_eq!(passed.drive(), target.drive());
                assert_eq!(preflight.poll(&view, now), Step::Spent, "proof given once");
                return (Ok(()), written);
            }
            Step::Refused(refusal) => return (Err(refusal), written),
            step @ (Step::Wait | Step::Spent) => return (Err(refusal_for(&step)), written),
        };
        assert_eq!(
            preflight.poll(&view, now),
            Step::Wait,
            "one request at a time"
        );
        let truth = match kind {
            SlowKind::GetId => SlowOutcome::Identity(UID),
            SlowKind::Write(w) => {
                written.push((w.param(), w.value()));
                SlowOutcome::WriteAnswered
            }
            SlowKind::Read(param) => SlowOutcome::Read(ParamOutcome::Read(match param {
                Param::CanTimeout => ParamValue::CanTimeout(CanTimeout::RUNTIME),
                Param::Damper => ParamValue::Damper(Damper::ProtectionOn),
                Param::Vbus => ParamValue::Volts(Volts::new(24.0).unwrap()),
                _ => written.iter().find(|(p, _)| *p == param).unwrap().1,
            })),
        };
        let outcome = match drive.answer {
            Some((exchange, outcome)) if exchange == exchange_of(kind) => outcome,
            Some(_) | None => truth,
        };
        if let (SlowKind::Write(_), Some((mode, faults))) = (kind, drive.status) {
            view = DriveView {
                fault_seen: view.fault_seen || !faults.is_empty(),
                ..seen(status(mode, faults, now + 500_000))
            };
        }
        preflight.answered(outcome);
    }
    (Err(Refusal::NoStatus), written)
}

#[expect(
    clippy::panic,
    reason = "test helper; a stuck preflight fails the test"
)]
fn refusal_for(step: &Step) -> Refusal {
    panic!("preflight stuck at {step:?}")
}

fn volts(v: f64) -> ParamValue {
    ParamValue::Volts(Volts::new(v).unwrap_or_else(|| refusal_volts(v)))
}

#[expect(clippy::panic, reason = "test helper; the rows' voltages are finite")]
fn refusal_volts(v: f64) -> Volts {
    panic!("{v} isn't a voltage")
}

/// Guards: safety - `drive.can_timeout`: preflight writes canTimeout 1000 and refuses unless it reads back exactly 1000
/// (PLAN item 6 drive layer: 0 is off, the right-arm drives read 600 today).
#[test]
fn can_timeout_must_read_back_exactly_1000() {
    for (ticks, refused) in [
        (0, true),
        (600, true),
        (999, true),
        (1000, false),
        (1001, true),
        (20_000, true),
    ] {
        let read = CanTimeout::from_ticks(ticks);
        let (verdict, written) = run(
            0,
            &Drive::reading(Param::CanTimeout, ParamValue::CanTimeout(read)),
        );
        let expected = if refused {
            Err(Refusal::CanTimeout { read })
        } else {
            Ok(())
        };
        assert_eq!(verdict, expected, "reads {ticks}");
        assert_eq!(
            written.first(),
            Some(&(
                Param::CanTimeout,
                ParamValue::CanTimeout(CanTimeout::RUNTIME)
            ))
        );
        if let Err(refusal) = verdict {
            assert_eq!(refusal.rule(), RuleId::DriveCanTimeout);
            assert!(
                refusal
                    .message("arm_joint_one")
                    .contains(&format!("canTimeout reads {ticks}, expected 1000")),
                "{}",
                refusal.message("arm_joint_one")
            );
        }
    }
}

/// Guards: safety - `drive.caps`: the skeleton's three caps are written and must read back as written; a null cap refuses
/// before anything is sent (PLAN item 6 drive layer; item 1, null is not permission).
#[test]
fn the_caps_are_written_from_the_skeleton_and_read_back_as_written() {
    let torque = |v| ParamValue::NewtonMeters(NewtonMeters::new(v).unwrap());
    let current = |v| ParamValue::Amps(Amps::new(v).unwrap());
    let speed = |v| ParamValue::RadPerSec(RadPerSec::new(v).unwrap());

    let (verdict, written) = run(0, &Drive::honest());
    assert_eq!(verdict, Ok(()));
    assert_eq!(
        written,
        [
            (
                Param::CanTimeout,
                ParamValue::CanTimeout(CanTimeout::RUNTIME)
            ),
            (Param::LimitTorque, torque(10.0)),
            (Param::LimitCur, current(12.0)),
            (Param::LimitSpd, speed(1.0)),
        ]
    );

    for (param, read, written) in [
        (Param::LimitTorque, torque(9.999), torque(10.0)),
        (Param::LimitTorque, torque(0.0), torque(10.0)),
        (Param::LimitCur, current(12.01), current(12.0)),
        (Param::LimitSpd, speed(2.0), speed(1.0)),
    ] {
        let (verdict, _) = run(0, &Drive::reading(param, read));
        assert_eq!(
            verdict,
            Err(Refusal::Cap {
                param,
                written,
                read
            }),
            "{param:?} reads {read:?}"
        );
    }
    // A value of another unit is no read-back at all.
    let (verdict, _) = run(0, &Drive::reading(Param::LimitTorque, current(10.0)));
    assert_eq!(
        verdict,
        Err(Refusal::NoAnswer {
            exchange: Exchange::Read(Param::LimitTorque),
            how: Unanswered::WrongAnswer
        })
    );

    let (verdict, written) = run(1, &Drive::honest());
    assert_eq!(verdict, Err(Refusal::CapUnset(CapKind::Torque)));
    assert_eq!(written, [], "nothing sent");
    for refusal in [
        Refusal::CapUnset(CapKind::Torque),
        Refusal::Cap {
            param: Param::LimitCur,
            written: current(12.0),
            read: current(1.0),
        },
    ] {
        assert_eq!(refusal.rule(), RuleId::DriveCaps);
    }
}

/// Guards: safety - `drive.damper`: preflight refuses unless the damper reads 0, protection on (PLAN item 6 drive layer).
#[test]
fn the_damper_must_read_protection_on() {
    for (damper, expected) in [
        (Damper::ProtectionOn, Ok(())),
        (Damper::ProtectionOff, Err(Refusal::DamperOff)),
    ] {
        let (verdict, written) = run(
            0,
            &Drive::reading(Param::Damper, ParamValue::Damper(damper)),
        );
        assert_eq!(verdict, expected, "{damper:?}");
        assert!(
            written.iter().all(|(p, _)| *p != Param::Damper),
            "never written"
        );
    }
    assert_eq!(Refusal::DamperOff.rule(), RuleId::DriveDamper);
}

/// Guards: safety - `host.preflight`: VBUS inside the skeleton's window (ends included), no fault bits, and the drive
/// not already in Run, in every status since preflight began; a drive that sends no status, or a joint with no bus, is
/// refused (PLAN item 6 Preflight row).
#[test]
fn preflight_refuses_vbus_out_of_window_a_fault_and_a_running_drive() {
    let window = skeleton().power.vbus_v;
    for (v, refused) in [
        (21.99, true),
        (22.0, false),
        (24.0, false),
        (26.0, false),
        (26.01, true),
    ] {
        let (verdict, _) = run(0, &Drive::reading(Param::Vbus, volts(v)));
        let expected = if refused {
            Err(Refusal::Vbus {
                read: Volts::new(v).unwrap(),
                window,
            })
        } else {
            Ok(())
        };
        assert_eq!(verdict, expected, "{v} V");
    }

    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let with = |status| Drive {
        status,
        ..Drive::honest()
    };
    for (drive, expected) in [
        (with(Some((Mode::Reset, over))), Err(Refusal::FaultSeen)),
        (
            with(Some((Mode::Run, StatusFaults::default()))),
            Err(Refusal::AlreadyRunning),
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
        // A status from before preflight began says nothing about the drive now: neither its Run nor its faults count.
        (
            Drive {
                before: seen(status(Mode::Run, StatusFaults::default(), 500)),
                ..Drive::honest()
            },
            Ok(()),
        ),
    ] {
        assert_eq!(run(0, &drive).0, expected);
    }
    assert_eq!(run(2, &Drive::honest()).0, Err(Refusal::Unwired), "no bus");
    // A fault only in the latest status, with nothing latched yet, is named by its bits.
    let skeleton = skeleton();
    let mut preflight = Preflight::start(
        Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap(),
        1_000,
    );
    let faulted = DriveView {
        fault_seen: false,
        ..seen(status(Mode::Reset, over, 2_000))
    };
    assert_eq!(
        preflight.poll(&faulted, 3_000),
        Step::Refused(Refusal::Faults { bits: over })
    );
    for refusal in [
        Refusal::Faults { bits: over },
        Refusal::FaultSeen,
        Refusal::AlreadyRunning,
        Refusal::NoStatus,
        Refusal::Vbus {
            read: Volts::new(1.0).unwrap(),
            window,
        },
    ] {
        assert_eq!(refusal.rule(), RuleId::HostPreflight);
    }
}

/// Guards: safety - `host.identity`: once the skeleton has a drive's UID, preflight refuses a drive that answers with
/// another; before commissioning (UID null) any answer passes (PLAN item 3, Scan and identity).
#[test]
fn the_uid_must_match_once_commissioned() {
    let other = Uid([9; 8]);
    let answer = |uid| Drive::answering(Exchange::Identity, SlowOutcome::Identity(uid));
    assert_eq!(run(0, &answer(UID)).0, Ok(()));
    assert_eq!(
        run(0, &answer(other)).0,
        Err(Refusal::Uid {
            read: other,
            expected: UID
        })
    );
    // The fixture's second joint has no UID yet; it is refused for its null cap, not its UID.
    assert_eq!(
        run(1, &answer(other)).0,
        Err(Refusal::CapUnset(CapKind::Torque))
    );
    assert_eq!(
        Refusal::Uid {
            read: other,
            expected: UID
        }
        .rule(),
        RuleId::HostIdentity
    );
}

/// Guards: safety - fail closed (safety.md section 3): a request that times out, isn't sent, is refused by the bus or
/// the drive, or gets an answer of another kind refuses preflight under the rule that request serves.
#[test]
fn a_request_without_a_usable_answer_refuses_under_its_rule() {
    let exchanges = [
        (Exchange::Identity, RuleId::HostIdentity),
        (Exchange::Write(Param::CanTimeout), RuleId::DriveCanTimeout),
        (Exchange::Write(Param::LimitTorque), RuleId::DriveCaps),
        (Exchange::Write(Param::LimitCur), RuleId::DriveCaps),
        (Exchange::Write(Param::LimitSpd), RuleId::DriveCaps),
        (Exchange::Read(Param::CanTimeout), RuleId::DriveCanTimeout),
        (Exchange::Read(Param::LimitTorque), RuleId::DriveCaps),
        (Exchange::Read(Param::LimitCur), RuleId::DriveCaps),
        (Exchange::Read(Param::LimitSpd), RuleId::DriveCaps),
        (Exchange::Read(Param::Damper), RuleId::DriveDamper),
        (Exchange::Read(Param::Vbus), RuleId::HostPreflight),
    ];
    let failures = [
        (SlowOutcome::TimedOut, Unanswered::TimedOut),
        (
            SlowOutcome::NotSent(SendOutcome::QueueFull),
            Unanswered::NotSent(SendOutcome::QueueFull),
        ),
        (
            SlowOutcome::Refused(SlowRefusal::LimbStopped),
            Unanswered::Refused(SlowRefusal::LimbStopped),
        ),
    ];
    for (exchange, rule) in exchanges {
        for (outcome, how) in failures {
            let (verdict, _) = run(0, &Drive::answering(exchange, outcome));
            assert_eq!(
                verdict,
                Err(Refusal::NoAnswer { exchange, how }),
                "{exchange:?} {outcome:?}"
            );
            assert_eq!(verdict.err().map(|r| r.rule()), Some(rule), "{exchange:?}");
        }
        // An answer of another kind: a write answered with an identity, anything else with a write's status.
        let wrong = match exchange {
            Exchange::Write(_) => SlowOutcome::Identity(UID),
            Exchange::Identity | Exchange::Read(_) => SlowOutcome::WriteAnswered,
        };
        assert_eq!(
            run(0, &Drive::answering(exchange, wrong)).0,
            Err(Refusal::NoAnswer {
                exchange,
                how: Unanswered::WrongAnswer
            }),
            "{exchange:?}"
        );
    }
    let read = Exchange::Read(Param::Vbus);
    assert_eq!(
        run(
            0,
            &Drive::answering(read, SlowOutcome::Read(ParamOutcome::Refused))
        )
        .0,
        Err(Refusal::NoAnswer {
            exchange: read,
            how: Unanswered::ReadRefused
        })
    );
}
