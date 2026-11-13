#![expect(
    clippy::panic,
    clippy::wildcard_enum_match_arm,
    reason = "a test fails by panicking, and the bus's answers match only the kinds a job may ask"
)]

use can::{SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult};
use robstride::{DeviceId, Uid};
use rtrb::{Consumer, Producer, RingBuffer};

use super::{
    Answer, Identity, IdentityAsk, IdentityDone, IdentityRefused, IdentityReply, IdentityRequest,
    SLOT,
};
use crate::enable::{SLOW_RING, SlowEnds};

/// The bus's ends of one bus's slow rings.
struct BusSide {
    requests: Consumer<SlowRequest>,
    results: Producer<SlowResult>,
}

fn rig(buses: usize) -> (Vec<SlowEnds>, Vec<BusSide>) {
    (0..buses)
        .map(|_| {
            let (requests, bus_requests) = RingBuffer::new(SLOW_RING);
            let (bus_results, results) = RingBuffer::new(SLOW_RING);
            (
                SlowEnds::new(requests, results),
                BusSide {
                    requests: bus_requests,
                    results: bus_results,
                },
            )
        })
        .unzip()
}

fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

const A: Uid = Uid([1; 8]);
const B: Uid = Uid([2; 8]);

fn found(uid: Uid) -> SlowOutcome {
    SlowOutcome::Found { uid, other: None }
}

fn set_id(old: u8, new: u8) -> IdentityAsk {
    IdentityAsk::SetId {
        old: id(old),
        new: id(new),
    }
}

/// Run `ask` on bus 0 of one, the bus answering each request with `answer`: every request asked, in order, and the
/// reply.
fn run(
    ask: IdentityAsk,
    mut answer: impl FnMut(SlowKind) -> SlowOutcome,
) -> (Vec<SlowKind>, IdentityReply) {
    let (mut slow, mut buses) = rig(1);
    let mut identity = Identity::default();
    let request = IdentityRequest {
        tag: 9,
        bus: 0,
        ask,
    };
    assert_eq!(identity.take(request, &[false], false), Ok(()));
    let mut asked = Vec::new();
    for _ in 0..1_000 {
        let mut stray = 0;
        let reply = identity.tick(&mut slow, &[false], 0, &mut stray);
        assert_eq!(stray, 0);
        if let Some(reply) = reply {
            assert!(
                buses[0].requests.pop().is_err(),
                "nothing asked after the reply"
            );
            return (asked, reply);
        }
        if let Ok(r) = buses[0].requests.pop() {
            assert_eq!(r.slot, SLOT);
            asked.push(r.kind);
            let result = SlowResult {
                tag: r.tag,
                slot: r.slot,
                outcome: answer(r.kind),
            };
            buses[0].results.push(result).unwrap();
        }
    }
    panic!("the job never ended");
}

fn probe(n: u8) -> SlowKind {
    SlowKind::Probe(id(n))
}

fn the_set_id(old: u8, new: u8) -> SlowKind {
    SlowKind::SetId {
        old: id(old),
        new: id(new),
    }
}

/// Guards: protocol - a scan probes every ID from 1 to 127 once, in order, one at a time, and lists what answered at
/// each: one drive, two sharing an ID, nothing, or unsure once a probe's window couldn't be trusted three times; a
/// probe whose window couldn't be trusted, that wasn't sent, or that the bus refused for control's silence is asked again (PLAN item 3, Scan and identity: a scan
/// lists every ID answering on a bus and each drive's UID; RS03 manual §4.1.1 type 0).
#[test]
fn a_scan_probes_every_id_and_lists_what_answered() {
    let (mut retried, mut unsent) = (false, false);
    let (asked, reply) = run(IdentityAsk::Scan, |kind| match kind {
        SlowKind::Probe(n) if n == id(11) => found(A),
        SlowKind::Probe(n) if n == id(50) => SlowOutcome::Found {
            uid: A,
            other: Some(B),
        },
        SlowKind::Probe(n) if n == id(60) => SlowOutcome::Unsure,
        SlowKind::Probe(n) if n == id(127) && !retried => {
            retried = true;
            SlowOutcome::Refused(SlowRefusal::ControlSilent)
        }
        SlowKind::Probe(n) if n == id(126) && !unsent => {
            unsent = true;
            SlowOutcome::NotSent(can::Unsent::Expired)
        }
        SlowKind::Probe(n) if n == id(127) => found(B),
        _ => SlowOutcome::TimedOut,
    });
    let mut expected: Vec<SlowKind> = (1..=127).map(probe).collect();
    // ID 60 asked three times, 126 and 127 twice.
    expected.splice(60..60, [probe(60), probe(60)]);
    expected.push(probe(127));
    expected.splice(127..127, [probe(126)]);
    assert_eq!(asked, expected);
    let Ok(IdentityDone::Scanned(table)) = reply.outcome else {
        panic!("{reply:?}");
    };
    assert_eq!((reply.tag, reply.bus), (9, 0));
    assert_eq!(
        table.heard().collect::<Vec<_>>(),
        [
            (id(11), Answer::One(A)),
            (id(50), Answer::Several { uid: A, other: B }),
            (id(60), Answer::Unsure),
            (id(127), Answer::One(B)),
        ]
    );
}

/// Guards: safety - a set-ID's type 7 goes only once probes have just shown exactly one drive at the old ID and nothing
/// at the new; otherwise it is refused with what answered and no type 7 is asked: none, two drives or unsure at the old
/// ID, anything or unsure at the new, or a probe the bus refused (PLAN item 2, transmit allowlist: type 7 only with
/// exactly one drive answering; a type 7 to a shared ID would move every drive on it).
#[test]
fn a_set_id_is_refused_unless_one_drive_is_at_the_old_id_and_none_at_the_new() {
    let two = SlowOutcome::Found {
        uid: A,
        other: Some(B),
    };
    let not_idle = SlowOutcome::Refused(SlowRefusal::BusNotIdle);
    let rows = [
        (
            "nothing at the old ID",
            SlowOutcome::TimedOut,
            SlowOutcome::TimedOut,
            IdentityRefused::NotOne(Answer::Silent),
        ),
        (
            "two drives at the old ID",
            two,
            SlowOutcome::TimedOut,
            IdentityRefused::NotOne(Answer::Several { uid: A, other: B }),
        ),
        (
            "unsure at the old ID",
            SlowOutcome::Unsure,
            SlowOutcome::TimedOut,
            IdentityRefused::NotOne(Answer::Unsure),
        ),
        (
            "a drive at the new ID",
            found(A),
            found(B),
            IdentityRefused::Taken(Answer::One(B)),
        ),
        (
            "unsure at the new ID",
            found(A),
            SlowOutcome::Unsure,
            IdentityRefused::Taken(Answer::Unsure),
        ),
        (
            "the bus refused the probe",
            not_idle,
            SlowOutcome::TimedOut,
            IdentityRefused::Bus(SlowRefusal::BusNotIdle),
        ),
    ];
    for (what, at_old, at_new, why) in rows {
        let (asked, reply) = run(set_id(127, 11), |kind| match kind {
            SlowKind::Probe(n) if n == id(127) => at_old,
            SlowKind::Probe(_) => at_new,
            _ => panic!("{what}: {kind:?} asked"),
        });
        assert!(!asked.contains(&the_set_id(127, 11)), "{what}: no type 7");
        assert_eq!(reply.outcome, Err(why), "{what}");
    }
}

/// Guards: safety - a set-ID's type 7 is asked exactly once, after which the new ID and then the old are probed; it is
/// done only when the old ID's UID answers at the new ID alone, and otherwise says the type 7 may have gone, with what
/// answered at each, including when its own window was unsure or the bus or run ended after it was asked; a type 7 the
/// bus refused or never sent is said not to have gone (RS03 manual §4.1.5 type 7; PLAN item 3: the ID is checked by
/// probes, and a type 7 is never sent twice).
#[test]
fn a_set_id_is_sent_once_and_confirmed_by_probes_of_both_ids() {
    let unconfirmed = |at_old, at_new| Err(IdentityRefused::Unconfirmed { at_old, at_new });
    let moved = Ok(IdentityDone::Moved { uid: A });
    // (what, the type 7's outcome, after it at the new ID, then at the old, the reply)
    let rows = vec![
        ("moved", found(A), found(A), SlowOutcome::TimedOut, moved),
        (
            "moved, its own window unsure",
            SlowOutcome::Unsure,
            found(A),
            SlowOutcome::TimedOut,
            moved,
        ),
        (
            "moved, nothing heard in its own window",
            SlowOutcome::TimedOut,
            found(A),
            SlowOutcome::TimedOut,
            moved,
        ),
        (
            "still at the old ID",
            SlowOutcome::TimedOut,
            SlowOutcome::TimedOut,
            found(A),
            unconfirmed(Answer::One(A), Answer::Silent),
        ),
        (
            "another UID at the new ID",
            found(B),
            found(B),
            SlowOutcome::TimedOut,
            unconfirmed(Answer::Silent, Answer::One(B)),
        ),
        (
            "at both",
            found(A),
            found(A),
            found(A),
            unconfirmed(Answer::One(A), Answer::One(A)),
        ),
        (
            "the probe after refused",
            found(A),
            SlowOutcome::Refused(SlowRefusal::BusNotIdle),
            found(A),
            unconfirmed(Answer::Unsure, Answer::Unsure),
        ),
        (
            "refused",
            SlowOutcome::Refused(SlowRefusal::BusNotIdle),
            found(A),
            found(A),
            Err(IdentityRefused::Bus(SlowRefusal::BusNotIdle)),
        ),
        (
            "not sent",
            SlowOutcome::NotSent(can::Unsent::QueueFull),
            found(A),
            found(A),
            Err(IdentityRefused::NotSent(can::Unsent::QueueFull)),
        ),
    ];
    for (what, sent, at_new, at_old, outcome) in rows {
        let mut after = false;
        let (asked, reply) = run(set_id(127, 11), |kind| match kind {
            SlowKind::Probe(n) if n == id(127) && !after => found(A),
            SlowKind::Probe(n) if n == id(11) && !after => SlowOutcome::TimedOut,
            SlowKind::SetId { .. } => {
                after = true;
                sent
            }
            SlowKind::Probe(n) if n == id(11) => at_new,
            SlowKind::Probe(_) => at_old,
            _ => panic!("{what}: {kind:?} asked"),
        });
        assert_eq!(reply.outcome, outcome, "{what}");
        let gone = !matches!(sent, SlowOutcome::Refused(_) | SlowOutcome::NotSent(_));
        let mut expected = vec![probe(127), probe(11), the_set_id(127, 11)];
        if gone && !matches!(at_new, SlowOutcome::Refused(_)) {
            expected.extend([probe(11), probe(127)]);
        } else if gone {
            expected.push(probe(11));
        }
        assert_eq!(asked, expected, "{what}");
    }
}

/// Guards: safety - a scan or set-ID never runs beside an enable or another, names a bus the plan has and that is still
/// running, and takes only its own results: a preflight's result on its bus is counted stray and answers nothing; once
/// its type 7 is asked, a bus that ends or a run that ends says it may have gone, and before then that it didn't (PLAN
/// item 3: set-ID only while every limb on that bus is disabled, one drive at a time).
#[test]
fn a_scan_or_set_id_runs_alone_and_takes_only_its_own_results() {
    let request = |bus, ask| IdentityRequest { tag: 1, bus, ask };
    let mut identity = Identity::default();
    let scan = IdentityAsk::Scan;
    assert_eq!(
        identity.take(request(0, scan), &[false], true),
        Err(IdentityRefused::Busy)
    );
    assert_eq!(
        identity.take(request(1, scan), &[false], false),
        Err(IdentityRefused::NoBus)
    );
    assert_eq!(
        identity.take(request(0, scan), &[true], false),
        Err(IdentityRefused::BusEnded)
    );
    assert_eq!(
        identity.take(request(0, set_id(5, 5)), &[false], false),
        Err(IdentityRefused::SameId)
    );
    assert!(!identity.running());

    let (mut slow, mut buses) = rig(2);
    let ended = [false, false];
    assert_eq!(
        identity.take(request(1, set_id(127, 11)), &ended, false),
        Ok(())
    );
    assert_eq!(
        identity.take(request(0, scan), &ended, false),
        Err(IdentityRefused::Busy)
    );
    assert_eq!(identity.bus(), Some(1));
    let mut stray = 0;
    assert_eq!(identity.tick(&mut slow, &ended, 0, &mut stray), None);
    let Ok(asked) = buses[1].requests.pop() else {
        panic!("the probe of the old ID");
    };
    // A preflight's result, then one with the job's slot but an old tag: neither answers it.
    for (slot, tag) in [(0, asked.tag), (SLOT, asked.tag.wrapping_sub(1))] {
        let outcome = found(A);
        assert!(
            buses[1]
                .results
                .push(SlowResult { tag, slot, outcome })
                .is_ok()
        );
    }
    assert_eq!(identity.tick(&mut slow, &ended, 0, &mut stray), None);
    assert_eq!(stray, 2);
    assert!(
        buses[1].requests.pop().is_err(),
        "still waiting on its probe"
    );
    assert_eq!(
        identity.abandon(IdentityRefused::Ending).map(|r| r.outcome),
        Some(Err(IdentityRefused::Ending)),
        "no type 7 asked yet"
    );

    // Once the type 7 is asked, a bus that ends says it may have gone.
    assert_eq!(
        identity.take(request(1, set_id(127, 11)), &ended, false),
        Ok(())
    );
    for outcome in [found(A), SlowOutcome::TimedOut] {
        assert_eq!(identity.tick(&mut slow, &ended, 0, &mut stray), None);
        let Ok(r) = buses[1].requests.pop() else {
            panic!("a probe");
        };
        assert!(
            buses[1]
                .results
                .push(SlowResult {
                    tag: r.tag,
                    slot: r.slot,
                    outcome
                })
                .is_ok()
        );
    }
    assert_eq!(identity.tick(&mut slow, &ended, 0, &mut stray), None);
    assert_eq!(
        buses[1].requests.pop().map(|r| r.kind),
        Ok(the_set_id(127, 11))
    );
    assert_eq!(
        identity
            .tick(&mut slow, &[false, true], 0, &mut stray)
            .map(|r| r.outcome),
        Some(Err(IdentityRefused::Unconfirmed {
            at_old: Answer::Unsure,
            at_new: Answer::Unsure
        }))
    );
    assert!(!identity.running());
}

/// One second, as `safety::ANSWER_WITHIN_NS` counts it.
const SECOND: u64 = 1_000_000_000;

/// Guards: bug - a request whose result never comes (the bus's result ring was full) can't hold a scan or set-ID, and
/// every enable behind it, for ever: a second after it was asked a probe is asked again, three times at most before
/// its ID is unsure, and a type 7 counts as one that may have gone and is never asked again; a late result is stray
/// (architecture.md: every wait has a deadline; PR #68 review, J2).
#[test]
fn a_lost_result_is_given_up_after_a_second_and_a_type_7_is_never_asked_again() {
    let (mut slow, mut buses) = rig(1);
    let BusSide {
        mut requests,
        mut results,
    } = buses.remove(0);
    let mut identity = Identity::default();
    let request = IdentityRequest {
        tag: 9,
        bus: 0,
        ask: set_id(127, 11),
    };
    assert_eq!(identity.take(request, &[false], false), Ok(()));
    let mut stray = 0;
    let mut now = 0;
    // Tick once and take the request asked, if any.
    let mut pass = |identity: &mut Identity, now: u64, stray: &mut u64| {
        let reply = identity.tick(&mut slow, &[false], now, stray);
        (reply, requests.pop().ok())
    };
    // The old ID's probe is lost twice, and asked again only once a second has passed; the third is answered.
    let mut probes = Vec::new();
    for _ in 0..2 {
        let (reply, asked) = pass(&mut identity, now, &mut stray);
        assert_eq!((reply, asked.map(|r| r.kind)), (None, Some(probe(127))));
        probes.extend(asked);
        let (reply, asked) = pass(&mut identity, now + SECOND, &mut stray);
        assert_eq!((reply, asked), (None, None), "not overdue yet");
        now += SECOND + 1;
    }
    let (_, asked) = pass(&mut identity, now, &mut stray);
    let Some(third) = asked else {
        panic!("the third probe");
    };
    // The first probe's result, late: stray, and it answers nothing.
    let answer = |r: SlowRequest, outcome| SlowResult {
        tag: r.tag,
        slot: r.slot,
        outcome,
    };
    results
        .push(answer(probes[0], SlowOutcome::TimedOut))
        .unwrap();
    results.push(answer(third, found(A))).unwrap();
    let (reply, asked) = pass(&mut identity, now, &mut stray);
    assert_eq!((reply, asked.map(|r| r.kind)), (None, Some(probe(11))));
    assert_eq!(stray, 1);
    let Some(r) = asked else { panic!() };
    results.push(answer(r, SlowOutcome::TimedOut)).unwrap();
    // The type 7, asked once; its result never comes, so a second on the probes after it start.
    let (reply, asked) = pass(&mut identity, now, &mut stray);
    assert_eq!(
        (reply, asked.map(|r| r.kind)),
        (None, Some(the_set_id(127, 11)))
    );
    now += SECOND + 1;
    let (reply, asked) = pass(&mut identity, now, &mut stray);
    assert_eq!((reply, asked.map(|r| r.kind)), (None, Some(probe(11))));
    // Those are lost too, three times each: unconfirmed, both IDs unsure, and no second type 7.
    let mut kinds = Vec::new();
    let reply = loop {
        now += SECOND + 1;
        let (reply, asked) = pass(&mut identity, now, &mut stray);
        kinds.extend(asked.map(|r| r.kind));
        if let Some(reply) = reply {
            break reply;
        }
        assert!(kinds.len() < 10, "{kinds:?}");
    };
    assert_eq!(
        kinds,
        [probe(11), probe(11), probe(127), probe(127), probe(127)]
    );
    assert_eq!(
        reply.outcome,
        Err(IdentityRefused::Unconfirmed {
            at_old: Answer::Unsure,
            at_new: Answer::Unsure
        })
    );
    assert_eq!(reply.ask, set_id(127, 11));
    assert!(!identity.running());
}
