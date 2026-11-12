//! (rt) The control thread on Linux, on the bus threads' schedule: once a tick, a margin after the buses' collect
//! deadline, it takes each bus's newest snapshot and re-arm answers, steps the operator's enable and holds every enabled
//! joint into the next tick's batches, turns the operator's stops (and any its enables and holds asked) and then clears
//! into each bus's orders, and publishes the batches. A batch with nothing in it still tells its bus control is alive
//! (`can::CommandBatch::new`). It enables only what an operator's enable names (PLAN item 3: the runtime never enables
//! on its own).

use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

use can::{CommandBatch, Rearmed, Snapshot, Timing};
use rtrb::{Consumer, Producer};
use safety::{Cause, RuleId};

use crate::clock::{Schedule, mono_now, passed, sleep_period};
use crate::dispatch::{BusOrders, Told, orders, reply};
use crate::enable::{Buses, Counts, Enable, EnableRefused, EnableReply, Enabler, SlowEnds};
use crate::events::Events;
use crate::identity::{Identity, IdentityRefused, IdentityReply, IdentityRequest};
use crate::latch::StopLatch;
use crate::plan::BusPlan;
use crate::request::{Clear, ClearAt, ClearRefused, Reply, Scope, route_clear};
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
    /// The operator's scans and set-IDs, one at a time, and their replies.
    pub(crate) identity: Consumer<IdentityRequest>,
    pub(crate) identity_replies: Producer<IdentityReply>,
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
    /// Counted up by each pass that made progress ([`progressing`]); what the binary feeds systemd's watchdog from.
    pub(crate) progress: Arc<AtomicU64>,
}

/// What the control thread hands back when it ends.
#[derive(Debug, Default)]
pub struct ControlExit {
    /// Replies (to clears, enables, scans and set-IDs) the runtime's rings couldn't take.
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
    let mut identity = Identity::default();
    let mut counts = Counts::default();
    // Each bus's newest snapshot so far, whether its thread has ended, and its next batch, for the enables and holds:
    // made once here, overwritten each pass (no allocation on the loop).
    let mut newest: Vec<Option<Snapshot>> = vec![None; links.buses.len()];
    let mut ended = vec![false; links.buses.len()];
    let mut batches = vec![CommandBatch::new(0, 0); links.buses.len()];
    let phase = phase(timing);
    let mut n = schedule.next(phase);
    // Whether a pass has seen the run's end.
    let mut end_seen = false;
    loop {
        if exit.error.is_none() {
            if let Err(e) = schedule.sleep_until(schedule.at(n, phase)) {
                // No clock to keep the schedule: end the run, a broken control side (`host.hang`). The buses stop
                // their drives on their own schedule.
                exit.error = Some(e);
                end_run(
                    &links.end,
                    &links.stops,
                    Cause::Rule(RuleId::HostHang),
                    end_seen,
                );
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
        read(plans, n, &mut links, &mut newest, &mut exit, end_seen);
        for (bus, ends) in links.buses.iter().enumerate() {
            if let Some(e) = ended.get_mut(bus) {
                *e = ends.snapshots.is_abandoned();
            }
        }
        if ended.iter().all(|e| *e) {
            // A bus may have answered a clear between its last read and its end.
            read(plans, n, &mut links, &mut newest, &mut exit, end_seen);
            record_end(&links.stops, &mut links.events, &exit, &mut end_seen);
            refuse_all(plans, &mut enabler, &mut identity, &mut links, &mut exit);
            add(&mut exit, counts);
            links.finished.store(true, Ordering::Release);
            return exit;
        }
        // Read again: an end asked during the reads stops the enables, orders and batches at once.
        if links.end.load(Ordering::Acquire) {
            record_end(&links.stops, &mut links.events, &exit, &mut end_seen);
            refuse_all(plans, &mut enabler, &mut identity, &mut links, &mut exit);
        } else {
            let next = n.saturating_add(1);
            fresh_batches(&mut batches, next, timing, origin_ns);
            step_identity(
                &mut identity,
                &enabler,
                &mut links,
                &ended,
                &mut counts,
                &mut exit,
            );
            // Enables and holds first, so a stop they ask goes out in this pass's orders.
            let mut buses = Buses {
                snapshots: &newest,
                slow: &mut links.slow,
                batches: &mut batches,
                ended: &ended,
                lent: identity.bus(),
            };
            let mut step = EnableStep {
                identity: identity.running(),
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
            exit.stops_deferred += send_orders(plans, &mut links, &mut exit.replies_dropped);
            publish(&mut links.buses, &batches, &mut exit);
            if exit.error.is_none() && passed(schedule.at(next, 0)) {
                exit.late_batches += 1;
            }
            // Last, so a pass that hangs anywhere above counts nothing.
            if exit.error.is_none() && progressing(n, &newest) {
                links.progress.fetch_add(1, Ordering::Release);
            }
        }
        n = n.saturating_add(1);
    }
}

/// Each bus's batch for tick `next`, empty, expiring at the end of that tick's send window: the schedule's origin on the
/// session's epoch (`origin_ns`), plus the tick's offset and its send window.
fn fresh_batches(batches: &mut [CommandBatch], next: u64, timing: Timing, origin_ns: u64) {
    let expires = next
        .saturating_mul(timing.period_ns)
        .saturating_add(timing.send_window_ns)
        .saturating_add(origin_ns);
    for batch in batches {
        *batch = CommandBatch::new(next, expires);
    }
}

/// Whether a pass at tick `n` counts as progress for systemd's watchdog (PLAN item 3: fed only when the control loop
/// and every bus in an active run are making progress): every bus has published tick `n`'s snapshot. Every bus, not
/// only those whose last snapshot shows a limb enabled: a bus takes up a limb's first Enable or a stop's Disables
/// before any snapshot shows it, so a hang in that tick would look idle. The pass itself is the control loop's part: a
/// control thread that hangs counts nothing. This is the one statement of the rule; the docs point here.
fn progressing(n: u64, newest: &[Option<Snapshot>]) -> bool {
    newest.iter().all(|s| s.is_some_and(|s| s.tick >= n))
}

/// Push each bus its batch.
fn publish(buses: &mut [BusEnds], batches: &[CommandBatch], exit: &mut ControlExit) {
    for (ends, batch) in buses.iter_mut().zip(batches) {
        if ends.commands.push(*batch).is_err() {
            exit.batches_dropped += 1;
        }
    }
}

/// The enabler's part of a pass, with what it counts.
struct EnableStep<'a> {
    /// Whether a scan or set-ID is running: every enable is refused `Busy` until it ends.
    identity: bool,
    enabler: &'a mut Enabler,
    counts: &'a mut Counts,
    replies_dropped: &'a mut u64,
    events: &'a mut Events,
}

impl EnableStep<'_> {
    /// Take every enable queued (refused while a scan or set-ID runs), then step the enable running and hold every enabled joint into the next tick's
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
            if self.identity {
                let r = EnableReply {
                    tag: enable.tag,
                    outcome: Err(EnableRefused::Busy),
                };
                push_enable_reply(enable_replies, r, self.replies_dropped, self.events);
                continue;
            }
            match self
                .enabler
                .take(roster, enable, buses, health.failed(), now_ns)
            {
                Some(r) => push_enable_reply(enable_replies, r, self.replies_dropped, self.events),
                None => self.events.started(&enable),
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

/// This pass's orders for every bus: the stops latched and the clears queued, each stop and refused clear an event.
/// Gives the stops a full ring kept for later.
fn send_orders(plans: &[BusPlan], links: &mut ControlLinks, replies_dropped: &mut u64) -> u64 {
    let replies = &mut links.replies;
    let clears = &mut links.clears;
    let events = &mut links.events;
    let mut budget = clears.buffer().capacity();
    orders(
        plans,
        &mut links.orders,
        &links.stops,
        || {
            budget = budget.checked_sub(1)?;
            clears.pop().ok()
        },
        |told| match told {
            Told::Stopped(stops) => events.stops(stops),
            Told::Refused(r) => push_reply(replies, r, replies_dropped, events),
        },
    )
}

/// Control ends the run, the robot's stop asked under `cause`. When the flag was already set and no pass has seen the
/// end yet (`seen`), only the owner can have set it: its shutdown is asked too, since [`record_end`] then sees control's
/// cause and won't. Every store control makes is followed by [`record_end`] in the same pass, so a flag found set once a
/// pass has seen the end is control's own or an owner's end already recorded: nothing more to ask.
fn end_run(end: &AtomicBool, stops: &StopLatch, cause: Cause, seen: bool) {
    stops.ask(Scope::Robot, cause);
    if end.swap(true, Ordering::AcqRel) && !seen {
        stops.ask(Scope::Robot, Cause::Shutdown);
    }
}

/// While the run ends, every bus stops every limb on its own, so control routes no stop: it records the stops asked.
/// The end is the robot's stop, asked under its cause where control decided it ([`end_run`]: `host.hang` for a lost
/// clock, `host.bus` for a bus thread that ended) or, for an end the owner asked, as a shutdown on the first pass that
/// sees it. One take is written robot first, then each limb in [`LimbName::ALL`](skeleton::LimbName::ALL) order, each
/// scope's causes in bit order, all with the pass's stamp.
fn record_end(stops: &StopLatch, events: &mut Events, exit: &ControlExit, seen: &mut bool) {
    if !*seen {
        *seen = true;
        if exit.error.is_none() && exit.bus_ended.is_none() {
            stops.ask(Scope::Robot, Cause::Shutdown);
        }
    }
    let taken = stops.take();
    if !taken.is_empty() {
        events.stops(taken);
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

/// The scan or set-ID running, one tick on, or the next one queued taken up (refused at once while an enable runs).
/// Before the enables in a pass, so an enable taken in the same pass as one starts is refused.
fn step_identity(
    identity: &mut Identity,
    enabler: &Enabler,
    links: &mut ControlLinks,
    ended: &[bool],
    counts: &mut Counts,
    exit: &mut ControlExit,
) {
    let dropped = &mut exit.replies_dropped;
    for _ in 0..links.identity.buffer().capacity() {
        if identity.running() {
            break;
        }
        let Ok(request) = links.identity.pop() else {
            break;
        };
        if let Err(why) = identity.take(request, ended, enabler.running()) {
            let r = IdentityReply {
                tag: request.tag,
                bus: request.bus,
                outcome: Err(why),
            };
            push_identity_reply(&mut links.identity_replies, &r, dropped);
        }
    }
    if let Some(r) = identity.tick(&mut links.slow, ended, &mut counts.stray_results) {
        push_identity_reply(&mut links.identity_replies, &r, dropped);
    }
}

/// The run is ending: every clear, enable, scan and set-ID queued or running refused.
fn refuse_all(
    plans: &[BusPlan],
    enabler: &mut Enabler,
    identity: &mut Identity,
    links: &mut ControlLinks,
    exit: &mut ControlExit,
) {
    refuse_clears(plans, links, exit);
    refuse_enables(enabler, links, exit);
    refuse_identity(identity, links, exit);
}

/// The run is ending: the scan or set-ID running and every one queued refused `Ending` (one past its type 7 says so).
fn refuse_identity(identity: &mut Identity, links: &mut ControlLinks, exit: &mut ControlExit) {
    let dropped = &mut exit.replies_dropped;
    if let Some(r) = identity.abandon(IdentityRefused::Ending) {
        push_identity_reply(&mut links.identity_replies, &r, dropped);
    }
    for _ in 0..links.identity.buffer().capacity() {
        let Ok(request) = links.identity.pop() else {
            break;
        };
        let r = IdentityReply {
            tag: request.tag,
            bus: request.bus,
            outcome: Err(IdentityRefused::Ending),
        };
        push_identity_reply(&mut links.identity_replies, &r, dropped);
    }
}

/// A scan's or set-ID's answer, to its requester.
fn push_identity_reply(
    replies: &mut Producer<IdentityReply>,
    r: &IdentityReply,
    dropped: &mut u64,
) {
    if replies.push(*r).is_err() {
        *dropped += 1;
    }
}

/// The enabler's counts, into the exit.
const fn add(exit: &mut ControlExit, counts: Counts) {
    exit.stray_results += counts.stray_results;
    exit.mode_stops += counts.mode_stops;
    exit.holds_ended += counts.holds_ended;
}

/// Each bus's newest snapshot (kept in `latest`) and re-arm answers, handed on; a bus that ended before the run did ends
/// the run (`end_seen`: whether a pass has seen the end already).
fn read(
    plans: &[BusPlan],
    n: u64,
    links: &mut ControlLinks,
    latest: &mut [Option<Snapshot>],
    exit: &mut ControlExit,
    end_seen: bool,
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
            // A bus thread that ended stops the run (`host.bus`); the bus is named in the exit.
            end_run(
                &links.end,
                &links.stops,
                Cause::Rule(RuleId::HostBus),
                end_seen,
            );
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
mod tests;
