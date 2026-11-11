//! Preflight's exchanges with the drive, one table per rule (PLAN item 6 drive layer and Preflight row; safety.md
//! section 6.1). Each row runs the whole preflight against a drive that answers every request truthfully except the one
//! the row changes.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{SlowKind, SlowOutcome, SlowRefusal, SlowRequest, Unsent};
use common::preflight::{Drive, SLOT, UID, answer, register, run, volts};
use common::{joint, quiet, shown, skeleton};
use robstride::{
    Amps, CanTimeout, Damper, NewtonMeters, Param, ParamOutcome, ParamValue, RadPerSec, Uid, Volts,
};
use safety::{
    ANSWER_WITHIN_NS, CapKind, Exchange, Preflight, Refusal, Register, RuleId, Step, Target,
    Unanswered,
};

/// What the operator is told when control handed a result over late.
const LATE_REMEDY: &str = "The runtime fell behind handing over the answer: check its log and the Pi's load, then run preflight again";

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
            assert_eq!(
                refusal.message("arm_joint_one"),
                format!(
                    "refused (drive.can_timeout): arm_joint_one canTimeout reads {ticks}, expected 1000"
                )
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
                register: register(param),
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
            exchange: Exchange::Read(Register::LimitTorque),
            how: Unanswered::WrongAnswer
        })
    );

    let (verdict, written) = run(1, &Drive::honest());
    assert_eq!(verdict, Err(Refusal::CapUnset(CapKind::Torque)));
    assert_eq!(written, [], "nothing sent");

    for refusal in [
        Refusal::CapUnset(CapKind::Torque),
        Refusal::CapOutOfRange {
            cap: CapKind::Speed,
            value: 21.0,
            max: 20.0,
        },
        Refusal::Cap {
            register: Register::LimitCur,
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

/// Guards: safety - `host.preflight`: VBUS inside the skeleton's window, ends included, or preflight refuses (PLAN item 6
/// Preflight row).
#[test]
fn preflight_refuses_vbus_out_of_window() {
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
    let refusal = Refusal::Vbus {
        read: Volts::new(21.995).unwrap(),
        window,
    };
    assert_eq!(
        refusal.message("arm_joint_one"),
        "refused (host.preflight): arm_joint_one VBUS reads 21.995 V, expected 22 to 26 V",
        "every digit read, so a value just outside never prints as the bound"
    );
    assert_eq!(refusal.rule(), RuleId::HostPreflight);
}

/// Guards: safety - `host.identity`: once the skeleton has a drive's UID, preflight refuses a drive that answers with
/// another; before commissioning (UID null) any UID passes (PLAN item 3, Scan and identity).
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
    // The fixture's fourth joint has every cap but no UID yet: any UID passes.
    assert_eq!(run(3, &answer(other)).0, Ok(()));
    assert_eq!(
        Refusal::Uid {
            read: other,
            expected: UID
        }
        .rule(),
        RuleId::HostIdentity
    );
    assert_eq!(
        Refusal::Uid {
            read: other,
            expected: UID
        }
        .message("arm_joint_one"),
        "refused (host.identity): arm_joint_one UID reads 0x0909090909090909, expected 0x0123456789abcdef"
    );
}

/// Guards: safety - fail closed (safety.md section 3): a request that times out, isn't sent, is refused by the bus or
/// the drive, or gets an answer of another kind refuses preflight under the rule that request serves.
#[test]
fn a_request_without_a_usable_answer_refuses_under_its_rule() {
    let exchanges = [
        (Exchange::Identity, RuleId::HostIdentity),
        (
            Exchange::Write(Register::CanTimeout),
            RuleId::DriveCanTimeout,
        ),
        (Exchange::Write(Register::LimitTorque), RuleId::DriveCaps),
        (Exchange::Write(Register::LimitCur), RuleId::DriveCaps),
        (Exchange::Write(Register::LimitSpd), RuleId::DriveCaps),
        (
            Exchange::Read(Register::CanTimeout),
            RuleId::DriveCanTimeout,
        ),
        (Exchange::Read(Register::LimitTorque), RuleId::DriveCaps),
        (Exchange::Read(Register::LimitCur), RuleId::DriveCaps),
        (Exchange::Read(Register::LimitSpd), RuleId::DriveCaps),
        (Exchange::Read(Register::Damper), RuleId::DriveDamper),
        (Exchange::Read(Register::Vbus), RuleId::HostPreflight),
    ];
    let failures = [
        (SlowOutcome::TimedOut, Unanswered::TimedOut),
        (
            SlowOutcome::NotSent(Unsent::QueueFull),
            Unanswered::NotSent(Unsent::QueueFull),
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
    let read = Exchange::Read(Register::Vbus);
    let cant_read = SlowOutcome::Read(ParamOutcome::Refused);
    assert_eq!(
        run(0, &Drive::answering(read, cant_read)).0,
        Err(Refusal::NoAnswer {
            exchange: read,
            how: Unanswered::ReadRefused
        })
    );
    // "Can't read it" answering a write or get-ID is an answer of the wrong kind.
    for exchange in [Exchange::Identity, Exchange::Write(Register::LimitCur)] {
        assert_eq!(
            run(0, &Drive::answering(exchange, cant_read)).0,
            Err(Refusal::NoAnswer {
                exchange,
                how: Unanswered::WrongAnswer
            }),
            "{exchange:?}"
        );
    }
}

/// Guards: safety - fail closed (safety.md section 3): a request with no result within its window refuses preflight,
/// whatever the bus does with it, and an answer that comes after doesn't undo the refusal. Whether control polls or
/// hands the result over first in a tick changes only the name of a late refusal.
#[test]
fn a_request_with_no_result_in_time_refuses() {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let view = quiet();
    let get_id = SlowRequest {
        tag: 7,
        slot: SLOT,
        kind: SlowKind::GetId,
    };
    let identity = answer(get_id, SlowOutcome::Identity(UID));
    let mut preflight = Preflight::start(target, SLOT, 7, 1_000);
    assert_eq!(preflight.poll(shown(&view), 2_000), Step::Submit(get_id));
    assert_eq!(
        preflight.poll(shown(&view), 2_000 + ANSWER_WITHIN_NS),
        Step::Wait
    );
    let refused = Step::Refused(Refusal::NoAnswer {
        exchange: Exchange::Identity,
        how: Unanswered::TimedOut,
    });
    assert_eq!(
        preflight.poll(shown(&view), 2_001 + ANSWER_WITHIN_NS),
        refused
    );
    preflight.answered(identity, 2_001 + ANSWER_WITHIN_NS);
    assert_eq!(
        preflight.poll(shown(&view), 2_002 + ANSWER_WITHIN_NS),
        refused
    );

    // A result handed over late, with no poll in between, refuses as late (control fell behind); one at exactly 1 s
    // counts, whether control polls before handing it over or after.
    let mut late = Preflight::start(target, SLOT, 7, 1_000);
    assert_eq!(late.poll(shown(&view), 2_000), Step::Submit(get_id));
    late.answered(identity, 2_001 + ANSWER_WITHIN_NS);
    let handed_late = Refusal::NoAnswer {
        exchange: Exchange::Identity,
        how: Unanswered::Late,
    };
    assert_eq!(
        late.poll(shown(&view), 2_001 + ANSWER_WITHIN_NS),
        Step::Refused(handed_late)
    );
    assert_eq!(handed_late.remedy(), LATE_REMEDY);
    for poll_first in [false, true] {
        let mut on_time = Preflight::start(target, SLOT, 7, 1_000);
        assert_eq!(on_time.poll(shown(&view), 2_000), Step::Submit(get_id));
        if poll_first {
            assert_eq!(
                on_time.poll(shown(&view), 2_000 + ANSWER_WITHIN_NS),
                Step::Wait
            );
        }
        on_time.answered(identity, 2_000 + ANSWER_WITHIN_NS);
        assert!(
            matches!(
                on_time.poll(shown(&view), 2_000 + ANSWER_WITHIN_NS),
                Step::Submit(SlowRequest {
                    tag: 8,
                    kind: SlowKind::Write(_),
                    ..
                })
            ),
            "polled first: {poll_first}"
        );
    }
}

/// Guards: safety - fail closed (safety.md section 3): preflight takes a result only for the request it has in flight,
/// by its drive's slot and the request's tag. Another slot's result, an earlier aborted preflight's, or one of the
/// wrong tag never answers it, whatever its outcome, and is counted; the request still needs its own result, or
/// refuses as unanswered, and a stray result doesn't end a fresh preflight either.
#[test]
fn only_the_result_of_the_request_in_flight_answers_it() {
    let skeleton = skeleton();
    let target = Target::new(&joint(&skeleton, 0), &skeleton.power).unwrap();
    let view = quiet();
    let mut earlier = Preflight::start(target, SLOT, 1, 1_000);
    let stale = SlowRequest {
        tag: 1,
        slot: SLOT,
        kind: SlowKind::GetId,
    };
    assert_eq!(earlier.poll(shown(&view), 2_000), Step::Submit(stale));
    let first = 1 + Preflight::TAGS;
    let get_id = SlowRequest {
        tag: first,
        slot: SLOT,
        kind: SlowKind::GetId,
    };
    let strays = [
        answer(stale, SlowOutcome::Identity(UID)),
        answer(stale, SlowOutcome::Refused(SlowRefusal::LimbStopped)),
        answer(
            SlowRequest {
                slot: SLOT + 1,
                ..get_id
            },
            SlowOutcome::Identity(Uid([9; 8])),
        ),
        answer(
            SlowRequest {
                tag: first + 1,
                ..get_id
            },
            SlowOutcome::TimedOut,
        ),
    ];
    let mut fresh = Preflight::start(target, SLOT, first, 3_000);
    assert_eq!(fresh.poll(shown(&view), 4_000), Step::Submit(get_id));
    for stray in strays {
        fresh.answered(stray, 5_000);
        assert_eq!(fresh.poll(shown(&view), 5_000), Step::Wait, "{stray:?}");
    }
    let count = u32::try_from(strays.len()).unwrap();
    assert_eq!(fresh.ignored(), count);
    fresh.answered(answer(get_id, SlowOutcome::Identity(UID)), 6_000);
    assert!(matches!(
        fresh.poll(shown(&view), 6_000),
        Step::Submit(SlowRequest {
            slot: SLOT,
            kind: SlowKind::Write(_),
            tag,
        }) if tag == first + 1
    ));
    // Nothing in flight between the result and the next poll: a result then answers nothing.
    let mut idle = Preflight::start(target, SLOT, first, 3_000);
    idle.answered(answer(get_id, SlowOutcome::Identity(UID)), 3_500);
    assert_eq!(idle.ignored(), 1);
    assert_eq!(idle.poll(shown(&view), 4_000), Step::Submit(get_id));

    // Only strays: the request is unanswered.
    let mut unanswered = Preflight::start(target, SLOT, first, 3_000);
    assert_eq!(unanswered.poll(shown(&view), 4_000), Step::Submit(get_id));
    for stray in strays {
        unanswered.answered(stray, 5_000);
    }
    assert_eq!(
        unanswered.poll(shown(&view), 4_001 + ANSWER_WITHIN_NS),
        Step::Refused(Refusal::NoAnswer {
            exchange: Exchange::Identity,
            how: Unanswered::TimedOut,
        })
    );
}

/// Guards: safety - safety.md section 5: an unanswered request's line names the request and says in the operator's
/// words what happened instead, one phrase for each way a request goes unanswered.
#[test]
fn an_unanswered_requests_line_says_what_happened() {
    let exchange = Exchange::Read(Register::Vbus);
    for (how, said) in [
        (Unanswered::TimedOut, "no answer came in time"),
        (Unanswered::Late, "its answer was handed over late"),
        (
            Unanswered::NotSent(Unsent::QueueFull),
            "not sent, the adapter's queue was full",
        ),
        (
            Unanswered::NotSent(Unsent::Expired),
            "not sent, it expired queued",
        ),
        (
            Unanswered::NotSent(Unsent::Failed),
            "not sent, the bus failed",
        ),
        (
            Unanswered::Refused(SlowRefusal::LimbNotIdle),
            "refused by the bus: writes go only to drives of an idle limb",
        ),
        (Unanswered::ReadRefused, "the drive refused the read"),
        (Unanswered::WrongAnswer, "an answer of another kind came"),
    ] {
        assert_eq!(
            Refusal::NoAnswer { exchange, how }.message("arm_joint_one"),
            format!(
                "refused (host.preflight): arm_joint_one got no usable answer to the read of VBUS: {said}"
            )
        );
    }
}
