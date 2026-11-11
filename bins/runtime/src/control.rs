//! (rt) The control thread on Linux, on the bus threads' schedule: once a tick, a margin after the buses' collect
//! deadline, it takes each bus's newest snapshot and re-arm answers, turns the operator's stops and then clears into each
//! bus's orders, and publishes the next tick's batch. Hold only, with nothing enabled: every batch is empty, which still
//! tells each bus control is alive (`can::CommandBatch::new`). It never enables anything (PLAN item 3: the runtime never
//! enables on its own).

use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use can::{CommandBatch, Rearmed, Snapshot, Timing};
use rtrb::{Consumer, Producer};

use crate::clock::{Schedule, passed, sleep_period};
use crate::dispatch::{BusOrders, StopLatch, orders, reply};
use crate::plan::BusPlan;
use crate::request::{Clear, ClearRefused, Reply};

/// One bus's newest snapshot, for the runtime's readers.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct View {
    /// The bus, as its index in the plan.
    pub bus: usize,
    /// Its newest snapshot this tick.
    pub snapshot: Snapshot,
}

/// Control's ends of one bus's rings, but for its orders.
pub(crate) struct BusEnds {
    pub(crate) commands: Producer<CommandBatch>,
    pub(crate) snapshots: Consumer<Snapshot>,
    pub(crate) rearmed: Consumer<Rearmed>,
}

/// Everything the control thread runs with.
pub(crate) struct ControlLinks {
    pub(crate) buses: Vec<BusEnds>,
    /// Each bus's order ring, in plan order.
    pub(crate) orders: Vec<BusOrders>,
    /// The operator's stops, taken first each tick.
    pub(crate) stops: Arc<StopLatch>,
    pub(crate) clears: Consumer<Clear>,
    pub(crate) replies: Producer<Reply>,
    /// `None` when nobody reads the views.
    pub(crate) views: Option<Producer<View>>,
    /// The run's end, and every bus thread's exit flag: one flag, so no bus can be told to exit while control still
    /// runs as if it weren't. Set by the runtime to end the run, or by control when it can't go on.
    pub(crate) end: Arc<AtomicBool>,
    /// Set by control as it returns, so the runtime's owner learns of a run that ended on its own.
    pub(crate) finished: Arc<AtomicBool>,
}

/// What the control thread hands back when it ends.
#[derive(Debug, Default)]
pub struct ControlExit {
    /// Replies the runtime's ring couldn't take.
    pub replies_dropped: u64,
    /// Views the runtime's ring couldn't take.
    pub views_dropped: u64,
    /// Batches a bus's ring couldn't take.
    pub batches_dropped: u64,
    /// Stops a bus's full order ring didn't take at once; each was pushed again, ahead of anything else, until it did.
    pub stops_deferred: u64,
    /// Snapshots missing at a pass, one per running bus per pass: its newest wasn't this tick's, because control read
    /// before the bus published or the bus missed its tick.
    pub stale_ticks: u64,
    /// Ticks control slept through (a stall carried it past them); it runs the one in progress and counts these.
    pub skipped_ticks: u64,
    /// Passes that published the next tick's batches only after that tick had begun: the buses ran it without them.
    pub late_batches: u64,
    /// Clears refused because the run was ending.
    pub clears_ending: u64,
    /// The first bus thread that ended before the run did (a socket or clock error): control then ended the run.
    pub bus_ended: Option<usize>,
    /// The clock error that cost the thread its schedule, if any: it then ended the run and paced itself with relative
    /// sleeps until every bus had ended.
    pub error: Option<io::Error>,
}

/// When in each tick control runs: a quarter of the slack after the buses' collect deadline, so each bus has pushed
/// this tick's snapshot (it does so right after its collect) and the batch is out well before the next tick starts.
fn phase(timing: Timing) -> u64 {
    timing.collect_ns + timing.period_ns.saturating_sub(timing.collect_ns) / 4
}

/// Run until every bus thread has ended, after the runtime or control itself ended the run.
pub(crate) fn run(
    plans: &[BusPlan],
    schedule: &Schedule,
    epoch_ns: impl Fn(std::time::Instant) -> u64,
    timing: Timing,
    mut links: ControlLinks,
) -> ControlExit {
    let mut exit = ControlExit::default();
    let phase = phase(timing);
    let mut n = schedule.next(phase);
    loop {
        if exit.error.is_none() {
            if let Err(e) = schedule.sleep_until(schedule.at(n, phase)) {
                // No clock to keep the schedule: end the run. The buses stop their drives on their own schedule.
                exit.error = Some(e);
                links.end.store(true, Ordering::Release);
            } else {
                let current = schedule.current(phase);
                if current > n {
                    exit.skipped_ticks += current - n;
                    n = current;
                }
            }
        } else {
            sleep_period(timing.period_ns);
        }
        // Once set, each bus stops every limb and ends once a snapshot with every limb at rest is taken, which the
        // reads below do.
        read(plans, n, &mut links, &mut exit);
        if links.buses.iter().all(|b| b.snapshots.is_abandoned()) {
            // A bus may have answered a clear between its last read and its end.
            read(plans, n, &mut links, &mut exit);
            refuse_clears(&mut links, &mut exit);
            links.finished.store(true, Ordering::Release);
            return exit;
        }
        // Read again: an end asked during the reads stops the orders and batches at once.
        if links.end.load(Ordering::Acquire) {
            refuse_clears(&mut links, &mut exit);
        } else {
            let replies = &mut links.replies;
            let clears = &mut links.clears;
            let mut budget = clears.buffer().capacity();
            exit.stops_deferred += orders(
                plans,
                &mut links.orders,
                &links.stops,
                || {
                    budget = budget.checked_sub(1)?;
                    clears.pop().ok()
                },
                |r| push_reply(replies, r, &mut exit.replies_dropped),
            );
            let next = n.saturating_add(1);
            let expires = epoch_ns(schedule.at(next, timing.send_window_ns));
            for ends in &mut links.buses {
                if ends
                    .commands
                    .push(CommandBatch::new(next, expires))
                    .is_err()
                {
                    exit.batches_dropped += 1;
                }
            }
            if exit.error.is_none() && passed(schedule.at(next, 0)) {
                exit.late_batches += 1;
            }
        }
        n = n.saturating_add(1);
    }
}

/// Every clear still queued, refused: the run is ending.
fn refuse_clears(links: &mut ControlLinks, exit: &mut ControlExit) {
    for _ in 0..links.clears.buffer().capacity() {
        let Ok(clear) = links.clears.pop() else {
            break;
        };
        exit.clears_ending += 1;
        let r = Reply {
            tag: clear.tag,
            limb: clear.limb,
            bus: None,
            outcome: Err(ClearRefused::Ending),
        };
        push_reply(&mut links.replies, r, &mut exit.replies_dropped);
    }
}

/// Each bus's newest snapshot and re-arm answers, handed on; a bus that ended before the run did ends the run.
fn read(plans: &[BusPlan], n: u64, links: &mut ControlLinks, exit: &mut ControlExit) {
    for (bus, ends) in links.buses.iter_mut().enumerate() {
        let mut newest = None;
        for _ in 0..ends.snapshots.buffer().capacity() {
            let Ok(s) = ends.snapshots.pop() else { break };
            newest = Some(s);
        }
        let ended = ends.snapshots.is_abandoned();
        // Read now, not once a pass: an end asked during this pass makes every bus exit, which isn't a bus failing.
        let ending = links.end.load(Ordering::Acquire);
        if !ending && !ended && exit.error.is_none() && newest.is_none_or(|s| s.tick != n) {
            exit.stale_ticks += 1;
        }
        if let (Some(snapshot), Some(views)) = (newest, &mut links.views)
            && views.push(View { bus, snapshot }).is_err()
        {
            exit.views_dropped += 1;
        }
        for _ in 0..ends.rearmed.buffer().capacity() {
            let Ok(answer) = ends.rearmed.pop() else {
                break;
            };
            if let Some(r) = reply(plans, bus, answer) {
                push_reply(&mut links.replies, r, &mut exit.replies_dropped);
            }
        }
        if ended && !ending {
            exit.bus_ended.get_or_insert(bus);
            links.end.store(true, Ordering::Release);
        }
    }
}

fn push_reply(replies: &mut Producer<Reply>, r: Reply, dropped: &mut u64) {
    if replies.push(r).is_err() {
        *dropped += 1;
    }
}

#[cfg(test)]
mod tests {
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
        let plans =
            crate::plan(&skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap()).unwrap();
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
        let links = ControlLinks {
            buses,
            orders,
            stops: Arc::new(StopLatch::default()),
            clears: clears_rx,
            replies: replies_tx,
            views: None,
            end: Arc::clone(&end),
            finished: Arc::clone(&finished),
        };
        let control = std::thread::spawn({
            let plans = plans.clone();
            move || run(&plans, &schedule, |_| 0, timing, links)
        });
        // can1 ends on its own; control ends the run for it.
        drop(threads.pop());
        while !end.load(Ordering::Acquire) {
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
        let reply = loop {
            if let Ok(r) = replies.pop() {
                break r;
            }
            std::thread::yield_now();
        };
        assert_eq!(
            reply,
            Reply {
                tag: 5,
                limb: LimbName::RightArm,
                bus: None,
                outcome: Err(ClearRefused::Ending)
            }
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
}
