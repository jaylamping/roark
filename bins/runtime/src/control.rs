//! (rt) The control thread on Linux, on the bus threads' schedule: once a tick, after the buses' collect deadline, it
//! takes each bus's newest snapshot and re-arm answers, turns the operator's requests into each bus's orders, and
//! publishes the next tick's batch. Hold only, with nothing enabled: every batch is empty, which still tells each bus
//! control is alive (`can::CommandBatch::new`). It never enables anything (PLAN item 2: the runtime never enables on
//! its own).

use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use can::{CommandBatch, MAX_DRIVES, Order, Rearmed, Snapshot, Timing};
use rtrb::{Consumer, Producer};
use telemetry::Epoch;

use crate::clock::Schedule;
use crate::plan::BusPlan;
use crate::request::{ClearRefused, Reply, Request, Routed, reply, route};

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
    pub(crate) orders: Producer<Order>,
    pub(crate) rearmed: Consumer<Rearmed>,
}

/// Everything the control thread runs with.
pub(crate) struct ControlLinks {
    pub(crate) buses: Vec<BusEnds>,
    pub(crate) requests: Consumer<Request>,
    pub(crate) replies: Producer<Reply>,
    pub(crate) views: Producer<View>,
    /// Set by the runtime to end the run.
    pub(crate) end: Arc<AtomicBool>,
    /// Every bus thread's exit flag: set once the run ends.
    pub(crate) bus_exit: Arc<AtomicBool>,
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
    /// Stops pushed a tick or more late because a bus's order ring was full.
    pub stops_deferred: u64,
    /// The clock error that cost the thread its schedule, if any: it then asked every bus to exit and ran unscheduled
    /// until they had.
    pub error: Option<io::Error>,
}

/// Stops a bus's full order ring didn't take yet: pushed again each tick, before anything else for that bus.
#[derive(Clone, Copy, Default)]
struct Deferred {
    all: bool,
    limbs: [bool; MAX_DRIVES],
}

impl Deferred {
    fn any(&self) -> bool {
        self.all || self.limbs.contains(&true)
    }

    fn add(&mut self, order: Order) {
        match order {
            Order::StopAll => self.all = true,
            Order::StopLimb(limb) => {
                if let Some(l) = self.limbs.get_mut(limb) {
                    *l = true;
                }
            }
            Order::Rearm { .. } => {}
        }
    }

    /// Push what's waiting; false when the ring is still full.
    fn flush(&mut self, orders: &mut Producer<Order>) -> bool {
        if self.all {
            if orders.push(Order::StopAll).is_err() {
                return false;
            }
            self.all = false;
        }
        for (limb, waiting) in self.limbs.iter_mut().enumerate() {
            if *waiting {
                if orders.push(Order::StopLimb(limb)).is_err() {
                    return false;
                }
                *waiting = false;
            }
        }
        true
    }
}

/// Run until every bus thread has ended after the runtime asked to end.
pub(crate) fn run(
    plans: &[BusPlan],
    schedule: &Schedule,
    epoch: Epoch,
    timing: Timing,
    mut links: ControlLinks,
) -> ControlExit {
    let mut exit = ControlExit::default();
    let mut deferred = vec![Deferred::default(); links.buses.len()];
    // After the buses' collect deadline, so this tick's snapshots are out, and well before the next tick starts.
    let phase = timing.collect_ns;
    let mut n = schedule.next(phase);
    loop {
        if exit.error.is_none()
            && let Err(e) = schedule.sleep_until(schedule.at(n, phase))
        {
            // No clock to keep the schedule: end the run. The buses stop their drives on their own schedule.
            exit.error = Some(e);
            links.end.store(true, Ordering::Release);
        }
        let ending = links.end.load(Ordering::Acquire);
        if ending {
            // Each bus stops every limb and ends once a snapshot with every limb stopped is taken, which the views
            // below do.
            links.bus_exit.store(true, Ordering::Release);
        }
        for (bus, ends) in links.buses.iter_mut().enumerate() {
            let mut newest = None;
            for _ in 0..ends.snapshots.buffer().capacity() {
                let Ok(s) = ends.snapshots.pop() else { break };
                newest = Some(s);
            }
            if let Some(snapshot) = newest
                && links.views.push(View { bus, snapshot }).is_err()
            {
                exit.views_dropped += 1;
            }
            for _ in 0..ends.rearmed.buffer().capacity() {
                let Ok(answer) = ends.rearmed.pop() else {
                    break;
                };
                if let Some(r) = reply(plans, bus, answer)
                    && links.replies.push(r).is_err()
                {
                    exit.replies_dropped += 1;
                }
            }
        }
        if links.buses.iter().all(|b| b.snapshots.is_abandoned()) {
            return exit;
        }
        if !ending {
            for (ends, waiting) in links.buses.iter_mut().zip(&mut deferred) {
                if waiting.any() && !waiting.flush(&mut ends.orders) {
                    exit.stops_deferred += 1;
                }
            }
            for _ in 0..links.requests.buffer().capacity() {
                let Ok(request) = links.requests.pop() else {
                    break;
                };
                take(plans, request, &mut links, &mut deferred, &mut exit);
            }
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
        n = if exit.error.is_some() {
            n.saturating_add(1)
        } else {
            n.saturating_add(1).max(schedule.next(phase))
        };
    }
}

/// One request: its orders to each bus, or the reply that refuses it.
fn take(
    plans: &[BusPlan],
    request: Request,
    links: &mut ControlLinks,
    deferred: &mut [Deferred],
    exit: &mut ControlExit,
) {
    let mut routed_any = false;
    for Routed { bus, order } in route(plans, request) {
        routed_any = true;
        let (Some(ends), Some(waiting)) = (links.buses.get_mut(bus), deferred.get_mut(bus)) else {
            continue;
        };
        match order {
            Order::StopAll | Order::StopLimb(_) => {
                if waiting.any() || ends.orders.push(order).is_err() {
                    waiting.add(order);
                }
            }
            Order::Rearm { tag, .. } => {
                // A clear behind a stop still waiting would reach the bus first: refused, so a clear never jumps a stop.
                if waiting.any() || ends.orders.push(order).is_err() {
                    let refused = Reply {
                        tag,
                        limb: match request {
                            Request::Clear { limb, .. } => limb,
                            Request::Stop(_) => continue,
                        },
                        bus: Some(bus),
                        outcome: Err(ClearRefused::Busy),
                    };
                    if links.replies.push(refused).is_err() {
                        exit.replies_dropped += 1;
                    }
                }
            }
        }
    }
    if let (false, Request::Clear { tag, limb }) = (routed_any, request) {
        let refused = Reply {
            tag,
            limb,
            bus: None,
            outcome: Err(ClearRefused::Offline),
        };
        if links.replies.push(refused).is_err() {
            exit.replies_dropped += 1;
        }
    }
}
