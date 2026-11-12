//! The control thread's tests: the run's end and the watchdog's progress count, with the test playing every bus.

use rtrb::RingBuffer;
use skeleton::LimbName;

use super::*;
use crate::clock::mono_now;

/// A snapshot of `tick`, every limb idle.
fn snapshot(tick: u64) -> Snapshot {
    let mut limbs = [None; can::MAX_DRIVES];
    limbs[0] = Some(can::LimbView {
        state: can::LimbState::Idle,
        stop: None,
        generation: 0,
    });
    Snapshot::from_parts(
        tick,
        None,
        can::Counters::default(),
        limbs,
        [None; can::MAX_DRIVES],
    )
}

/// A bus thread's ends of its rings.
type BusThread = (
    Consumer<CommandBatch>,
    Producer<Snapshot>,
    Consumer<can::Order>,
    Producer<Rearmed>,
);

/// Control's links to the test robot's buses, as the runtime makes them, with the far ends kept by the test.
struct Harness {
    plans: Vec<BusPlan>,
    timing: Timing,
    schedule: Schedule,
    links: ControlLinks,
    /// The bus threads' ends: dropping one is that thread ending.
    threads: Vec<BusThread>,
    end: Arc<AtomicBool>,
    finished: Arc<AtomicBool>,
    progress: Arc<AtomicU64>,
    clears: Producer<Clear>,
    replies: Consumer<Reply>,
}

fn harness() -> Harness {
    let skeleton = skeleton::parse(include_str!("../../tests/skeleton.yaml")).unwrap();
    let plans = crate::plan(&skeleton).unwrap();
    let timing = Timing::at_hz(250);
    let schedule = Schedule::new(mono_now(), timing.period_ns).unwrap();
    let mut buses = Vec::new();
    let mut orders = Vec::new();
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
    let progress = Arc::new(AtomicU64::new(0));
    let (clears, clears_rx) = RingBuffer::new(4);
    let (replies_tx, replies) = RingBuffer::new(4);
    let links = ControlLinks {
        buses,
        orders,
        stops: Arc::new(StopLatch::default()),
        clears: clears_rx,
        replies: replies_tx,
        roster: Roster::new(&skeleton, &plans).unwrap(),
        slow: Vec::new(),
        enables: RingBuffer::new(1).1,
        enable_replies: RingBuffer::new(1).0,
        health: telemetry::Health::default(),
        views: None,
        end: Arc::clone(&end),
        finished: Arc::clone(&finished),
        progress: Arc::clone(&progress),
    };
    Harness {
        plans,
        timing,
        schedule,
        links,
        threads,
        end,
        finished,
        progress,
        clears,
        replies,
    }
}

/// Play every bus once: take each batch control has handed it and, for a bus in `answering`, publish that batch's
/// tick's snapshot, as a bus does after that tick's collect. Returns the newest batch tick taken from each bus.
fn serve(threads: &mut [BusThread], answering: &[bool]) -> Vec<Option<u64>> {
    threads
        .iter_mut()
        .zip(answering)
        .map(|((commands, snapshots, _, _), on)| {
            let mut newest = None;
            while let Ok(batch) = commands.pop() {
                if *on {
                    // Control takes one a pass and a batch comes once a pass, so the ring never fills.
                    snapshots.push(snapshot(batch.tick)).unwrap();
                }
                newest = Some(batch.tick);
            }
            newest
        })
        .collect()
}

/// Guards: safety - systemd's watchdog is fed only while the control loop and every bus make progress (PLAN item 3;
/// `progressing`): the count rises while every bus publishes each tick, stops for as long as one bus publishes nothing
/// though all its limbs show idle (a bus takes up a first Enable or a stop's Disables before a snapshot shows them),
/// and rises again once it publishes. Counted in control's passes, not in time.
#[test]
fn the_progress_count_stops_while_any_bus_is_behind() {
    let Harness {
        plans,
        timing,
        schedule,
        links,
        mut threads,
        end,
        progress,
        ..
    } = harness();
    let control = std::thread::spawn({
        let plans = plans.clone();
        move || run(&plans, &schedule, 0, timing, links)
    });
    // A limit on every wait (rust.md section 4): far past what control needs on a loaded machine.
    let deadline = mono_now() + std::time::Duration::from_secs(20);
    let wait = |what: &str| {
        assert!(mono_now() < deadline, "{what}");
        std::thread::yield_now();
    };

    while progress.load(Ordering::Acquire) < 10 {
        serve(&mut threads, &[true, true]);
        wait("every bus on time, and the count never rose");
    }
    // can1 stops publishing. Its last snapshot is of the newest batch it answered, tick `last`: no pass after `last`
    // counts. Control's batch for `last + 3` comes from pass `last + 2`, after pass `last` has counted or not.
    let mut last = serve(&mut threads, &[true, true])[1];
    while last.is_none() {
        last = serve(&mut threads, &[true, true])[1];
        wait("can1 never got a batch");
    }
    let last = last.unwrap_or_default();
    let mut can0 = 0;
    while can0 < last + 3 {
        can0 = serve(&mut threads, &[true, false])[0].unwrap_or(can0);
        wait("control stopped handing can0 batches");
    }
    let frozen = progress.load(Ordering::Acquire);
    while can0 < last + 13 {
        can0 = serve(&mut threads, &[true, false])[0].unwrap_or(can0);
        wait("control stopped handing can0 batches");
    }
    assert_eq!(
        progress.load(Ordering::Acquire),
        frozen,
        "ten passes with can1 behind"
    );
    while progress.load(Ordering::Acquire) < frozen + 10 {
        serve(&mut threads, &[true, true]);
        wait("can1 caught up, and the count never rose again");
    }
    end.store(true, Ordering::Release);
    drop(threads);
    control.join().unwrap();
}

/// Guards: safety - a bus thread that ends before the run does (a socket or clock error) ends the whole run: control
/// sets the end, so every other bus stops its limbs, names the bus that ended, refuses the clears that come in while
/// the run ends, and says it has finished, which is what wakes the binary to end the runtime and exit with failure
/// (PLAN item 3: the runtime never runs blind).
#[test]
fn a_bus_that_ends_on_its_own_ends_the_run() {
    let Harness {
        plans,
        timing,
        schedule,
        links,
        mut threads,
        end,
        finished,
        mut clears,
        mut replies,
        ..
    } = harness();
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
