//! (rt) The control thread on Linux, on the bus threads' schedule: once a tick, a margin after the buses' collect
//! deadline, it takes each bus's newest snapshot and re-arm answers, steps the operator's enable and holds every enabled
//! joint into the next tick's batches, turns the operator's stops (and any its enables and holds asked) and then clears
//! into each bus's orders, and publishes the batches. A batch with nothing in it still tells its bus control is alive
//! (`can::CommandBatch::new`). It enables only what an operator's enable names (PLAN item 3: the runtime never enables
//! on its own).

use std::cell::RefCell;
use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use can::{CommandBatch, Rearmed, Snapshot, Timing};
use rtrb::{Consumer, Producer};

use crate::clock::{Schedule, mono_now, passed, sleep_period};
use crate::dispatch::{BusOrders, StopLatch, orders, reply};
use crate::enable::{Buses, Counts, Enable, EnableRefused, EnableReply, Enabler, SlowEnds};
use crate::events::Events;
use crate::plan::BusPlan;
use crate::request::{Clear, ClearAt, ClearRefused, Reply, route_clear};
use crate::roster::Roster;

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
    /// Every joint, as enables name them.
    pub(crate) roster: Roster,
    /// Each bus's slow-request rings, in plan order: preflight's reads.
    pub(crate) slow: Vec<SlowEnds>,
    pub(crate) enables: Consumer<Enable>,
    pub(crate) enable_replies: Producer<EnableReply>,
    /// The recording's health: a failed recording refuses every new enable (PLAN item 6 `host.logging`).
    pub(crate) health: telemetry::Health,
    /// Control's events, into the session's recording.
    pub(crate) events: Events,
    /// `None` when nobody reads the views.
    pub(crate) views: Option<Producer<View>>,
    /// The run's end, and every bus thread's exit flag: one flag for both, so the buses and control learn of an end
    /// from the same store (control reads it per bus and again before the orders). Set by the runtime to end the run,
    /// or by control when it can't go on.
    pub(crate) end: Arc<AtomicBool>,
    /// Set by control as it returns, so the runtime's owner learns of a run that ended on its own.
    pub(crate) finished: Arc<AtomicBool>,
}

/// What the control thread hands back when it ends.
#[derive(Debug, Default)]
pub struct ControlExit {
    /// Replies (to clears and enables) the runtime's rings couldn't take.
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
    /// Enables refused because the run was ending, the one running included.
    pub enables_ending: u64,
    /// Slow results that answered no preflight running: dropped.
    pub stray_results: u64,
    /// Limbs stopped under `host.mode`'s limb-mate clause: a drive of a held limb, or of the enable running, that this
    /// host didn't enable was seen out of Reset or not seen at all. One per limb each time.
    pub mode_stops: u64,
    /// Enabled joints no longer held: their limb stopped on some bus (then cleared, perhaps), `host.mode`'s limb-mate
    /// clause stopped it, or their enable failed.
    pub holds_ended: u64,
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
    origin_ns: u64,
    timing: Timing,
    mut links: ControlLinks,
) -> ControlExit {
    let mut exit = ControlExit::default();
    let mut enabler = Enabler::new(&links.roster, links.buses.len());
    let mut counts = Counts::default();
    // Each bus's newest snapshot so far, whether its thread has ended, and its next batch, for the enables and holds:
    // made once here, overwritten each pass (no allocation on the loop).
    let mut newest: Vec<Option<Snapshot>> = vec![None; links.buses.len()];
    let mut ended = vec![false; links.buses.len()];
    let mut batches = vec![CommandBatch::new(0, 0); links.buses.len()];
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
        // On the session's epoch, as the snapshots' times are: the preflights' and sequences' windows, and the events.
        let now_ns = origin_ns.saturating_add(since(schedule.at(0, 0)));
        links.events.at(now_ns);
        // Once set, each bus stops every limb and ends once a snapshot with every limb at rest is taken, which the
        // reads below do.
        read(plans, n, &mut links, &mut newest, &mut exit);
        for (bus, ends) in links.buses.iter().enumerate() {
            if let Some(e) = ended.get_mut(bus) {
                *e = ends.snapshots.is_abandoned();
            }
        }
        if ended.iter().all(|e| *e) {
            // A bus may have answered a clear between its last read and its end.
            read(plans, n, &mut links, &mut newest, &mut exit);
            refuse_clears(plans, &mut links, &mut exit);
            refuse_enables(&mut enabler, &mut links, &mut exit);
            add(&mut exit, counts);
            links.finished.store(true, Ordering::Release);
            return exit;
        }
        // Read again: an end asked during the reads stops the enables, orders and batches at once.
        if links.end.load(Ordering::Acquire) {
            refuse_clears(plans, &mut links, &mut exit);
            refuse_enables(&mut enabler, &mut links, &mut exit);
        } else {
            let next = n.saturating_add(1);
            // The schedule's origin on the session's epoch, plus the next tick's send window.
            let expires = next
                .saturating_mul(timing.period_ns)
                .saturating_add(timing.send_window_ns)
                .saturating_add(origin_ns);
            for batch in &mut batches {
                *batch = CommandBatch::new(next, expires);
            }
            // Enables and holds first, so a stop they ask goes out in this pass's orders.
            let mut buses = Buses {
                snapshots: &newest,
                slow: &mut links.slow,
                batches: &mut batches,
                ended: &ended,
            };
            let mut step = EnableStep {
                enabler: &mut enabler,
                counts: &mut counts,
                replies_dropped: &mut exit.replies_dropped,
                events: &mut links.events,
            };
            step.run(
                &links.roster,
                &mut links.enables,
                &mut links.enable_replies,
                &links.health,
                &links.stops,
                &mut buses,
                next,
                now_ns,
            );
            let replies = &mut links.replies;
            let clears = &mut links.clears;
            let mut budget = clears.buffer().capacity();
            // Both the refusals and the stops are events; one borrow, taken in turn.
            let events = RefCell::new(&mut links.events);
            let replies_dropped = &mut exit.replies_dropped;
            exit.stops_deferred += orders(
                plans,
                &mut links.orders,
                &links.stops,
                || {
                    budget = budget.checked_sub(1)?;
                    clears.pop().ok()
                },
                |r| push_reply(replies, r, replies_dropped, &mut events.borrow_mut()),
                |scope, why| events.borrow_mut().stop(scope, why),
            );
            for (ends, batch) in links.buses.iter_mut().zip(&batches) {
                if ends.commands.push(*batch).is_err() {
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

/// The enabler's part of a pass, with what it counts.
struct EnableStep<'a> {
    enabler: &'a mut Enabler,
    counts: &'a mut Counts,
    replies_dropped: &'a mut u64,
    events: &'a mut Events,
}

impl EnableStep<'_> {
    /// Take every enable queued, then step the enable running and hold every enabled joint into the next tick's
    /// batches, answering each enable that ends.
    #[expect(
        clippy::too_many_arguments,
        reason = "the pass's links, borrowed apart"
    )]
    fn run(
        &mut self,
        roster: &Roster,
        enables: &mut Consumer<Enable>,
        enable_replies: &mut Producer<EnableReply>,
        health: &telemetry::Health,
        stops: &StopLatch,
        buses: &mut Buses<'_>,
        next: u64,
        now_ns: u64,
    ) {
        for _ in 0..enables.buffer().capacity() {
            let Ok(enable) = enables.pop() else {
                break;
            };
            self.events.enable(&enable);
            if let Some(r) = self
                .enabler
                .take(roster, enable, buses, health.failed(), now_ns)
            {
                push_enable_reply(enable_replies, r, self.replies_dropped, self.events);
            }
        }
        if let Some(r) = self
            .enabler
            .tick(roster, buses, stops, next, now_ns, self.counts)
        {
            push_enable_reply(enable_replies, r, self.replies_dropped, self.events);
        }
    }
}

/// Every clear still queued, refused as a clear is: `Ending` once per bus its limb is on, `Offline` when it is on none.
fn refuse_clears(plans: &[BusPlan], links: &mut ControlLinks, exit: &mut ControlExit) {
    for _ in 0..links.clears.buffer().capacity() {
        let Ok(clear) = links.clears.pop() else {
            break;
        };
        exit.clears_ending += 1;
        let mut routed_any = false;
        for ClearAt { bus, .. } in route_clear(plans, clear.limb) {
            routed_any = true;
            let r = Reply {
                tag: clear.tag,
                limb: clear.limb,
                bus: Some(bus),
                outcome: Err(ClearRefused::Ending),
            };
            push_reply(
                &mut links.replies,
                r,
                &mut exit.replies_dropped,
                &mut links.events,
            );
        }
        if !routed_any {
            let r = Reply {
                tag: clear.tag,
                limb: clear.limb,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            };
            push_reply(
                &mut links.replies,
                r,
                &mut exit.replies_dropped,
                &mut links.events,
            );
        }
    }
}

/// The enable running and every enable still queued, refused `Ending`.
fn refuse_enables(enabler: &mut Enabler, links: &mut ControlLinks, exit: &mut ControlExit) {
    if let Some(r) = enabler.end() {
        exit.enables_ending += 1;
        push_enable_reply(
            &mut links.enable_replies,
            r,
            &mut exit.replies_dropped,
            &mut links.events,
        );
    }
    for _ in 0..links.enables.buffer().capacity() {
        let Ok(enable) = links.enables.pop() else {
            break;
        };
        exit.enables_ending += 1;
        let r = EnableReply {
            tag: enable.tag,
            outcome: Err(EnableRefused::Ending),
        };
        push_enable_reply(
            &mut links.enable_replies,
            r,
            &mut exit.replies_dropped,
            &mut links.events,
        );
    }
}

/// Nanoseconds from `at` to now (0 before it).
fn since(at: std::time::Instant) -> u64 {
    u64::try_from(mono_now().saturating_duration_since(at).as_nanos()).unwrap_or(u64::MAX)
}

/// The enabler's counts, into the exit.
const fn add(exit: &mut ControlExit, counts: Counts) {
    exit.stray_results += counts.stray_results;
    exit.mode_stops += counts.mode_stops;
    exit.holds_ended += counts.holds_ended;
}

/// Each bus's newest snapshot (kept in `latest`) and re-arm answers, handed on; a bus that ended before the run did ends
/// the run.
fn read(
    plans: &[BusPlan],
    n: u64,
    links: &mut ControlLinks,
    latest: &mut [Option<Snapshot>],
    exit: &mut ControlExit,
) {
    for (bus, ends) in links.buses.iter_mut().enumerate() {
        let mut newest = None;
        for _ in 0..ends.snapshots.buffer().capacity() {
            let Ok(s) = ends.snapshots.pop() else { break };
            newest = Some(s);
        }
        if let (Some(s), Some(kept)) = (newest, latest.get_mut(bus)) {
            *kept = Some(s);
        }
        let ended = ends.snapshots.is_abandoned();
        // Read now, not once a pass: an end asked during this pass makes every bus exit, which isn't a bus failing.
        let ending = links.end.load(Ordering::Acquire);
        if !ending && !ended && exit.error.is_none() && newest.is_none_or(|s| s.tick < n) {
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
                push_reply(
                    &mut links.replies,
                    r,
                    &mut exit.replies_dropped,
                    &mut links.events,
                );
            }
        }
        if ended && !ending {
            exit.bus_ended.get_or_insert(bus);
            links.end.store(true, Ordering::Release);
        }
    }
}

/// A clear's answer, to its requester and the event log.
fn push_reply(replies: &mut Producer<Reply>, r: Reply, dropped: &mut u64, events: &mut Events) {
    events.clear_reply(&r);
    if replies.push(r).is_err() {
        *dropped += 1;
    }
}

/// An enable's answer, to its requester and the event log.
fn push_enable_reply(
    replies: &mut Producer<EnableReply>,
    r: EnableReply,
    dropped: &mut u64,
    events: &mut Events,
) {
    events.enable_reply(&r);
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
        let skeleton = skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap();
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
            events: Events::new(None),
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
}
