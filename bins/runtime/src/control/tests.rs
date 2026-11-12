//! The control thread's tests.

use rtrb::RingBuffer;
use skeleton::LimbName;

use super::*;
use crate::clock::mono_now;

/// Guards: safety - a bus thread that ends before the run does (a socket or clock error) ends the whole run: control
/// sets the end, so every other bus stops its limbs, names the bus that ended, refuses the clears that come in while
/// the run ends, and says it has finished, which is what wakes the binary to end the runtime and exit with failure
/// (PLAN item 3: the runtime never runs blind).
#[test]
fn a_bus_that_ends_on_its_own_ends_the_run() {
    let skeleton = skeleton::parse(include_str!("../../tests/skeleton.yaml")).unwrap();
    let plans = crate::plan(&skeleton).unwrap();
    let timing = Timing::at_hz(250);
    let schedule = Schedule::new(mono_now(), timing.period_ns).unwrap();
    let mut buses = Vec::new();
    let mut orders = Vec::new();
    // The bus threads' ends: dropping one is that thread ending.
    let mut threads = Vec::new();
    for _ in &plans {
        let (commands, commands_rx) = RingBuffer::new(4);
        let (snapshots_tx, snapshots) = RingBuffer::<Snapshot>::new(8);
        let (orders_tx, orders_rx) = RingBuffer::new(16);
        let (rearmed_tx, rearmed) = RingBuffer::<Rearmed>::new(16);
        buses.push(BusEnds {
            commands,
            snapshots,
            rearmed,
        });
        orders.push(BusOrders::new(orders_tx));
        threads.push((commands_rx, snapshots_tx, orders_rx, rearmed_tx));
    }
    let end = Arc::new(AtomicBool::new(false));
    let finished = Arc::new(AtomicBool::new(false));
    let (mut clears, clears_rx) = RingBuffer::new(4);
    let (replies_tx, mut replies) = RingBuffer::new(4);
    let roster = Roster::new(&skeleton, &plans).unwrap();
    let links = ControlLinks {
        buses,
        orders,
        stops: Arc::new(StopLatch::default()),
        clears: clears_rx,
        replies: replies_tx,
        events: Events::new(None, &roster),
        roster,
        slow: Vec::new(),
        enables: RingBuffer::new(1).1,
        enable_replies: RingBuffer::new(1).0,
        health: telemetry::Health::default(),
        views: None,
        end: Arc::clone(&end),
        finished: Arc::clone(&finished),
    };
    let control = std::thread::spawn({
        let plans = plans.clone();
        move || run(&plans, &schedule, 0, timing, links)
    });
    // can1 ends on its own; control ends the run for it.
    drop(threads.pop());
    // A limit on every wait (rust.md section 4): far past the few ticks control needs.
    let deadline = mono_now() + std::time::Duration::from_secs(10);
    while !end.load(Ordering::Acquire) {
        assert!(mono_now() < deadline, "control never ended the run");
        std::thread::yield_now();
    }
    // A clear while the run ends is refused, not lost.
    assert!(
        clears
            .push(Clear {
                tag: 5,
                limb: LimbName::RightArm
            })
            .is_ok()
    );
    // One refusal per bus the right arm is on.
    let mut got = Vec::new();
    while got.len() < 2 {
        assert!(mono_now() < deadline, "the clear wasn't refused: {got:?}");
        if let Ok(r) = replies.pop() {
            got.push(r);
        }
        std::thread::yield_now();
    }
    assert_eq!(
        got,
        [0, 1].map(|bus| Reply {
            tag: 5,
            limb: LimbName::RightArm,
            bus: Some(bus),
            outcome: Err(ClearRefused::Ending)
        })
    );
    assert!(!finished.load(Ordering::Acquire));
    // can0 ends as asked; control finishes.
    drop(threads);
    let exit = control.join().unwrap();
    assert_eq!(exit.bus_ended, Some(1));
    assert_eq!(exit.clears_ending, 1);
    assert!(exit.error.is_none());
    assert!(finished.load(Ordering::Acquire));
}

/// A step of the run's end, as control takes it.
#[derive(Clone, Copy, Debug)]
enum Step {
    /// The owner ends the run.
    Owner,
    /// Control ends it under this rule.
    Control(RuleId),
    /// A pass records the end.
    Pass,
}

/// A robot stop's rule and reason, as recorded.
type Recorded = (Option<&'static str>, Option<&'static str>);

/// Guards: safety - the run's end is recorded as one robot stop per cause that ended it: `host.bus` for a bus thread
/// that ended, `host.hang` for a lost clock, `shutdown` for the owner's end, both when the owner had ended the run
/// before control saw it, each once, and never a shutdown the owner didn't ask, even when control ends the run again
/// after it already ended (safety.md section 8).
#[test]
fn the_run_ends_recorded_under_each_cause_that_ended_it() {
    use Step::{Control, Owner, Pass};
    let skeleton = skeleton::parse(include_str!("../../tests/skeleton.yaml")).unwrap();
    let plans = crate::plan(&skeleton).unwrap();
    let roster = Roster::new(&skeleton, &plans).unwrap();
    let bus = Control(RuleId::HostBus);
    let clock = Control(RuleId::HostHang);
    let hang = (Some(RuleId::HostHang.as_str()), None);
    let bus_rule = (Some(RuleId::HostBus.as_str()), None);
    let shutdown = (None, Some("shutdown"));
    let cases: [(&[Step], &[Recorded]); 9] = [
        (&[bus, Pass, Pass], &[bus_rule]),
        (&[clock, Pass], &[hang]),
        (&[Owner, Pass, Pass], &[shutdown]),
        (&[Owner, bus, Pass], &[shutdown, bus_rule]),
        (&[Owner, clock, Pass], &[shutdown, hang]),
        // Control ends the run again once a pass has seen its end: no owner asked a shutdown.
        (&[bus, Pass, clock, Pass], &[bus_rule, hang]),
        // The owner's shutdown, already recorded, isn't recorded again.
        (&[Owner, Pass, clock, Pass], &[shutdown, hang]),
        // An owner's end after control's own changes nothing and isn't recorded.
        (&[bus, Owner, Pass], &[bus_rule]),
        (&[bus, Pass, Owner, Pass], &[bus_rule]),
    ];
    for (steps, expected) in cases {
        let mut recorded = crate::events::TestRecording::new("end", &plans);
        let mut events = recorded.events(&roster);
        let stops = StopLatch::default();
        let end = AtomicBool::new(false);
        let mut exit = ControlExit::default();
        let mut seen = false;
        for step in steps {
            match *step {
                Owner => end.store(true, Ordering::Release),
                Control(rule) => {
                    if rule == RuleId::HostBus {
                        exit.bus_ended = Some(1);
                    } else {
                        exit.error = Some(io::Error::other("clock"));
                    }
                    end_run(&end, &stops, Cause::Rule(rule), seen);
                }
                Pass => record_end(&stops, &mut events, &exit, &mut seen),
            }
        }
        drop(events);
        let got: Vec<_> = recorded
            .close()
            .into_iter()
            .map(|e| {
                assert_eq!(e.kind, telemetry::EventKind::RobotStopped);
                (e.rule, e.reason)
            })
            .collect();
        let got: Vec<_> = got
            .iter()
            .map(|(rule, reason)| (rule.as_deref(), reason.as_deref()))
            .collect();
        assert_eq!(got, expected, "{steps:?}");
        assert!(
            end.load(Ordering::Acquire),
            "every end sets the flag: {steps:?}"
        );
    }
}
