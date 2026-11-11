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
use telemetry::Epoch;

use crate::clock::{Schedule, sleep_period};
use crate::dispatch::{BusOrders, Stopped};
use crate::plan::BusPlan;
use crate::request::{
    Clear, ClearAt, ClearRefused, Reply, Routed, StopLatch, reply, route_clear, route_stop,
};

/// One bus's newest snapshot, for the runtime's readers.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct View {
    /// The bus, as its index in the plan.
    pub bus: usize,
    /// Its newest snapshot this tick.
    pub snapshot: Snapshot,
}

/// Control's ends of one bus's rings.
pub(crate) struct BusEnds {
    pub(crate) commands: Producer<CommandBatch>,
    pub(crate) snapshots: Consumer<Snapshot>,
    pub(crate) orders: BusOrders,
    pub(crate) rearmed: Consumer<Rearmed>,
}

/// Everything the control thread runs with.
pub(crate) struct ControlLinks {
    pub(crate) buses: Vec<BusEnds>,
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
    /// Passes in which a running bus's newest snapshot wasn't this tick's: control read before the bus published, or
    /// the bus missed its tick.
    pub stale_ticks: u64,
    /// Ticks control slept through (a stall carried it past them); it runs the one in progress and counts these.
    pub skipped_ticks: u64,
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
    epoch: Epoch,
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
        let ending = links.end.load(Ordering::Acquire);
        read(plans, n, ending, &mut links, &mut exit);
        if links.buses.iter().all(|b| b.snapshots.is_abandoned()) {
            links.finished.store(true, Ordering::Release);
            return exit;
        }
        if !ending {
            orders(plans, &mut links, &mut exit);
            for ends in &mut links.buses {
                let next = n.saturating_add(1);
                let expires = epoch.ns(schedule.at(next, timing.send_window_ns));
                if ends
                    .commands
                    .push(CommandBatch::new(next, expires))
                    .is_err()
                {
                    exit.batches_dropped += 1;
                }
            }
        }
        n = n.saturating_add(1);
    }
}

/// Each bus's newest snapshot and re-arm answers, handed on; a bus that ended before the run did ends the run.
fn read(plans: &[BusPlan], n: u64, ending: bool, links: &mut ControlLinks, exit: &mut ControlExit) {
    for (bus, ends) in links.buses.iter_mut().enumerate() {
        let mut newest = None;
        for _ in 0..ends.snapshots.buffer().capacity() {
            let Ok(s) = ends.snapshots.pop() else { break };
            newest = Some(s);
        }
        let ended = ends.snapshots.is_abandoned();
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
                push_reply(&mut links.replies, r, exit);
            }
        }
        if ended && !ending {
            exit.bus_ended.get_or_insert(bus);
            links.end.store(true, Ordering::Release);
        }
    }
}

/// The operator's orders for each bus: stops still waiting first, then the stops asked since the last tick, then the
/// clears, so no clear reaches a bus before a stop asked before it.
fn orders(plans: &[BusPlan], links: &mut ControlLinks, exit: &mut ControlExit) {
    for ends in &mut links.buses {
        ends.orders.flush();
    }
    for scope in links.stops.take().scopes() {
        for Routed { bus, order } in route_stop(plans, scope) {
            if let Some(ends) = links.buses.get_mut(bus)
                && ends.orders.stop(order) == Stopped::Deferred
            {
                exit.stops_deferred += 1;
            }
        }
    }
    for _ in 0..links.clears.buffer().capacity() {
        let Ok(clear) = links.clears.pop() else {
            break;
        };
        let mut routed_any = false;
        for ClearAt { bus, limb } in route_clear(plans, clear.limb) {
            routed_any = true;
            let Some(ends) = links.buses.get_mut(bus) else {
                continue;
            };
            if let Err(refused) = ends.orders.clear(clear.tag, limb) {
                let r = Reply {
                    tag: clear.tag,
                    limb: clear.limb,
                    bus: Some(bus),
                    outcome: Err(refused),
                };
                push_reply(&mut links.replies, r, exit);
            }
        }
        if !routed_any {
            let r = Reply {
                tag: clear.tag,
                limb: clear.limb,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            };
            push_reply(&mut links.replies, r, exit);
        }
    }
}

fn push_reply(replies: &mut Producer<Reply>, r: Reply, exit: &mut ControlExit) {
    if replies.push(r).is_err() {
        exit.replies_dropped += 1;
    }
}
