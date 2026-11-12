//! Slow requests: parameter reads, allowlisted writes and get-ID, for preflight and the once-a-second reads, and a scan's
//! probes and the set-ID, which go only while every limb on the bus is idle. Each waits
//! in one of [`SLOW_SLOTS`], is cancelled or expired as a slack opens ([`BusTick::open_slack`]), goes alone in the slack
//! after the collect deadline ([`BusTick::slow_send`]), is answered or timed out by the next tick's start, and ends in
//! one [`SlowResult`]. Which requests are refused, what answers each kind and what a write's answer proves are in
//! crates/can/README.md, Slow requests; the rule is conventions/can.md section 2.

use robstride::{DeviceId, EchoKind, Frame, Param, ParamOutcome, Uid, Write, encode};

use crate::batch::batch_may_carry;
use crate::tick::{BusTick, Reply};
use crate::types::{LimbState, SendOutcome};

/// Slow requests a bus holds at once, queued, in flight or with a result not yet taken.
pub const SLOW_SLOTS: usize = 8;

/// A slow request for the drive in `slot`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SlowRequest {
    /// The requester's own tag, handed back with the result.
    pub tag: u32,
    /// The drive's slot on this bus. A probe or set-ID names its IDs in its kind and doesn't read it; its result hands
    /// it back all the same.
    pub slot: usize,
    /// What to ask.
    pub kind: SlowKind,
}

/// What a slow request asks.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SlowKind {
    /// Read one register (type 17), answered by the reply naming it.
    Read(Param),
    /// One of the codec's allowlisted writes (type 18), built for the slot's drive.
    Write(Write),
    /// The drive's MCU UID (type 0).
    GetId,
    /// A type 0 to `id`, which needn't be in the bus's drive table: one step of a scan (PLAN item 3, Scan and identity).
    /// Every type-0 reply from `id` read before the next tick's start answers it ([`SlowOutcome::Found`]); none is
    /// [`SlowOutcome::TimedOut`]: no drive answers at that ID.
    Probe(DeviceId),
    /// Type 7: give the drive at `old` the ID `new`. PLAN item 2 allows it only from the set-ID command with exactly
    /// one drive answering on the bus; the requester proves that with a scan, the bus only that every limb is idle.
    /// Answered like a probe of `new`: the drive answers with its type-0 frame (manual §4.1.5, "Answer motor broadcast
    /// frame"), from its new ID since the change is "effective immediately". The requester probes both IDs after to
    /// see what took.
    SetId {
        /// The drive's ID now.
        old: DeviceId,
        /// The ID to give it.
        new: DeviceId,
    },
}

/// What became of a slow request.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SlowResult {
    /// The request's tag.
    pub tag: u32,
    /// The request's slot.
    pub slot: usize,
    /// Its outcome.
    pub outcome: SlowOutcome,
}

/// How a slow request ended.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SlowOutcome {
    /// The read's reply: the register's value or the drive's refusal.
    Read(ParamOutcome),
    /// The drive's UID.
    Identity(Uid),
    /// A probe's or set-ID's answers, every type-0 reply from its ID read before the next tick's start: the first UID,
    /// and another if a second drive with a different UID answered on the same ID.
    Found {
        /// The first answer's UID.
        uid: Uid,
        /// The first UID that differs from `uid`, if any: two drives share the ID.
        other: Option<Uid>,
    },
    /// The drive sent a status after the write. That says nothing about the value: read it back.
    WriteAnswered,
    /// Sent, but no reply was read by the next tick's start.
    TimedOut,
    /// Not sent: it expired queued, or the socket didn't take it. [`Unsent`] says which, and where it is counted.
    NotSent(Unsent),
    /// Never sent.
    Refused(SlowRefusal),
}

/// Why a slow request wasn't sent.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Unsent {
    /// Past its time, from either of two places. Still queued
    /// [`Timing::slow_queue_ticks`](crate::Timing::slow_queue_ticks) ticks after the tick it was submitted in, with no
    /// slack in them that let it go, it expires as a slack opens and never reaches the socket ([`BusTick::open_slack`],
    /// counted in `slow_expired`). Or the shell reports its frame expired instead of writing it ([`BusTick::slow_sent`]
    /// with [`SendOutcome::Expired`], counted in `tx_expired`); the Linux shell never does, since a slow frame has no
    /// send window.
    Expired,
    /// The adapter's queue was full (counted in `tx_dropped`).
    QueueFull,
    /// The write failed, and the bus with it (counted in `tx_dropped`).
    Failed,
}

/// Why a slow request isn't sent.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum SlowRefusal {
    /// No drive in that slot.
    #[error("no drive in that slot")]
    NoSuchSlot,
    /// A write built for another drive.
    #[error("the write is for another drive")]
    WrongTarget,
    /// A write only control's batch sends (the enable sequence's `run_mode` = MIT): its echo would pass for the
    /// sequence's own.
    #[error("that write goes only in control's batch")]
    BatchOnly,
    /// The drive's limb is stopping or stopped, or a drive of the limb shows what stops it at the next send.
    #[error("the drive's limb is stopping, stopped or due to stop")]
    LimbStopped,
    /// A write to a drive whose limb isn't idle: its status answer could pass for a command's reply.
    #[error("writes go only to drives of an idle limb")]
    LimbNotIdle,
    /// A write to a drive with a command of the tick still unanswered: a late reply could pass for the write's answer.
    #[error("a command to the drive is still unanswered")]
    CommandUnanswered,
    /// Control has sent no fresh batch for the silent-tick limit.
    #[error("control is silent")]
    ControlSilent,
    /// The bus has a latched error.
    #[error("the bus has failed")]
    BusFailed,
    /// A probe or set-ID while a limb on the bus isn't idle (running, stopping, stopped or due to stop, or a stop of
    /// it asked for): one goes only while nothing on the bus is enabled or being stopped.
    #[error("a limb on the bus isn't idle")]
    BusNotIdle,
    /// Every slot holds a request or a result not yet taken.
    #[error("the slow queue is full")]
    QueueFull,
    /// The bus thread ended before sending it.
    #[error("the bus thread ended")]
    Ended,
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct SlowEntry {
    seq: u64,
    /// The tick it was submitted in, for [`Timing::slow_queue_ticks`](crate::Timing::slow_queue_ticks).
    submitted_tick: u64,
    request: SlowRequest,
    state: SlowState,
}

#[derive(Clone, Copy, Debug)]
enum SlowState {
    Queued,
    /// Handed to the shell; [`BusTick::slow_sent`] says whether the socket took it.
    Sending,
    /// The socket took it; the reply is due by the next tick's start.
    Waiting,
    /// A probe or set-ID with an answer, still taking more until the next tick's start, when it ends `Found`.
    Heard {
        uid: Uid,
        other: Option<Uid>,
    },
    Done(SlowOutcome),
}

impl SlowState {
    /// Handed to the shell or taken by the socket, with no result yet: the one exchange a bus has in flight.
    const fn in_flight(self) -> bool {
        match self {
            Self::Sending | Self::Waiting | Self::Heard { .. } => true,
            Self::Queued | Self::Done(_) => false,
        }
    }

    /// What an exchange in flight ends as once its reply window is over: `Found` with what it heard, else timed out.
    const fn timed_out(self) -> SlowOutcome {
        match self {
            Self::Heard { uid, other } => SlowOutcome::Found { uid, other },
            Self::Queued | Self::Sending | Self::Waiting | Self::Done(_) => SlowOutcome::TimedOut,
        }
    }
}

impl BusTick {
    /// Queue a slow request.
    ///
    /// # Errors
    /// The [`SlowRefusal`] when it can't be queued; nothing is queued then.
    pub fn submit(&mut self, request: SlowRequest) -> Result<(), SlowRefusal> {
        self.slow_refusal(&request)?;
        let free = self
            .slow
            .iter_mut()
            .find(|e| e.is_none())
            .ok_or(SlowRefusal::QueueFull)?;
        *free = Some(SlowEntry {
            seq: self.slow_seq,
            submitted_tick: self.tick,
            request,
            state: SlowState::Queued,
        });
        self.slow_seq += 1;
        Ok(())
    }

    /// Free slots for [`Self::submit`].
    #[must_use]
    pub fn slow_room(&self) -> usize {
        self.slow.iter().filter(|e| e.is_none()).count()
    }

    /// Open the tick's slack, after [`Self::end`] and before anything else in it, so what it ends is handed back with
    /// the slack's first results and its slots are free for the slack's new requests. A queued request that may no
    /// longer go is cancelled ([`SlowOutcome::Refused`]); one still queued [`Timing::slow_queue_ticks`] ticks after the
    /// tick it was submitted in expires ([`Unsent::Expired`], counted in `slow_expired`).
    ///
    /// [`Timing::slow_queue_ticks`]: crate::Timing::slow_queue_ticks
    pub fn open_slack(&mut self) {
        for i in 0..SLOW_SLOTS {
            let Some(entry) = self.slow.get(i).copied().flatten() else {
                continue;
            };
            if !matches!(entry.state, SlowState::Queued) {
                continue;
            }
            if let Err(refusal) = self.slow_refusal(&entry.request) {
                self.finish_slow(i, SlowOutcome::Refused(refusal));
            } else if self.tick.saturating_sub(entry.submitted_tick) >= self.timing.slow_queue_ticks
            {
                self.counters.slow_expired += 1;
                self.finish_slow(i, SlowOutcome::NotSent(Unsent::Expired));
            }
        }
    }

    /// The slow frame to send now, at `now_ns`, if one may go: on a tick that wasn't held, after its collect deadline,
    /// with nothing in flight, and early enough for the reply to be read before the next tick starts; the oldest queued
    /// request goes. [`Self::open_slack`] has cancelled those that may no longer go; one found refused here all the
    /// same is cancelled and nothing goes. Report what the socket did with [`Self::slow_sent`].
    pub fn slow_send(&mut self, now_ns: u64) -> Option<Frame> {
        let in_flight = self.slow.iter().flatten().any(|e| e.state.in_flight());
        let after_collect = now_ns >= self.scheduled_ns.saturating_add(self.timing.collect_ns);
        let next_tick = self.scheduled_ns.saturating_add(self.timing.period_ns);
        if self.held
            || in_flight
            || !after_collect
            || now_ns.saturating_add(self.timing.slow_reply_ns) > next_tick
        {
            return None;
        }
        let (i, entry) = self
            .slow
            .iter()
            .enumerate()
            .filter_map(|(i, e)| e.map(|e| (i, e)))
            .filter(|(_, e)| matches!(e.state, SlowState::Queued))
            .min_by_key(|(_, e)| e.seq)?;
        if let Err(refusal) = self.slow_refusal(&entry.request) {
            self.finish_slow(i, SlowOutcome::Refused(refusal));
            return None;
        }
        let device = || {
            self.drives
                .get(entry.request.slot)
                .and_then(Option::as_ref)
                .map(|d| d.device)
        };
        let frame = match entry.request.kind {
            SlowKind::Read(param) => encode::param_read(device()?, param),
            SlowKind::Write(write) => encode::param_write(&write),
            SlowKind::GetId => encode::get_id(device()?),
            SlowKind::Probe(id) => encode::get_id(id),
            SlowKind::SetId { old, new } => encode::set_id(old, new),
        };
        if let Some(e) = self.slow.get_mut(i).and_then(Option::as_mut) {
            e.state = SlowState::Sending;
        }
        Some(frame)
    }

    /// What the socket did with the frame [`Self::slow_send`] returned, written at `sent_ns`. Not taken, it is reported
    /// and never retried.
    pub fn slow_sent(&mut self, outcome: SendOutcome, sent_ns: u64) {
        let Some(i) = self.slow_index(|e| matches!(e.state, SlowState::Sending)) else {
            return;
        };
        match outcome {
            SendOutcome::Sent => {
                // Every drive in the table the frame may have reached: a re-arm counts the drives' timeout from it. A
                // set-ID's drive answers on its new ID from then on, so a drive the table has there counts as reached.
                let reached = match self.slow.get(i).copied().flatten().map(|e| e.request) {
                    Some(SlowRequest {
                        kind: SlowKind::Read(_) | SlowKind::Write(_) | SlowKind::GetId,
                        slot,
                        ..
                    }) => self
                        .drives
                        .get(slot)
                        .and_then(Option::as_ref)
                        .map(|d| (d.device, None)),
                    Some(SlowRequest {
                        kind: SlowKind::Probe(id),
                        ..
                    }) => Some((id, None)),
                    Some(SlowRequest {
                        kind: SlowKind::SetId { old, new },
                        ..
                    }) => Some((old, Some(new))),
                    None => None,
                };
                if let Some((id, new)) = reached {
                    for d in self.drives.iter_mut().flatten() {
                        if d.device == id || Some(d.device) == new {
                            d.last_sent_ns = Some(sent_ns);
                        }
                    }
                }
                if let Some(e) = self.slow.get_mut(i).and_then(Option::as_mut) {
                    e.state = SlowState::Waiting;
                }
            }
            SendOutcome::Expired => {
                self.counters.tx_expired += 1;
                self.finish_slow(i, SlowOutcome::NotSent(Unsent::Expired));
            }
            SendOutcome::QueueFull => {
                self.counters.tx_dropped += 1;
                self.finish_slow(i, SlowOutcome::NotSent(Unsent::QueueFull));
            }
            SendOutcome::Failed => {
                self.counters.tx_dropped += 1;
                self.finish_slow(i, SlowOutcome::NotSent(Unsent::Failed));
            }
        }
    }

    /// The oldest result not yet taken, freeing its slot.
    pub fn take_slow_result(&mut self) -> Option<SlowResult> {
        let (i, result) = self
            .slow
            .iter()
            .enumerate()
            .filter_map(|(i, e)| {
                let e = e.as_ref()?;
                let outcome = match e.state {
                    SlowState::Done(outcome) => outcome,
                    SlowState::Queued
                    | SlowState::Sending
                    | SlowState::Waiting
                    | SlowState::Heard { .. } => return None,
                };
                let result = SlowResult {
                    tag: e.request.tag,
                    slot: e.request.slot,
                    outcome,
                };
                Some((i, e.seq, result))
            })
            .min_by_key(|(_, seq, _)| *seq)
            .map(|(i, _, r)| (i, r))?;
        if let Some(e) = self.slow.get_mut(i) {
            *e = None;
        }
        Some(result)
    }

    /// The thread is ending: every request held ends now. One in flight has timed out; queued ones are refused with
    /// the returned reason ([`SlowRefusal::BusFailed`] on a failed bus, else [`SlowRefusal::Ended`]), which the shell
    /// gives the requests still in its ring too. Take the results with [`Self::take_slow_result`].
    pub fn end_slow(&mut self) -> SlowRefusal {
        let refusal = if self.bus_error.is_some() {
            SlowRefusal::BusFailed
        } else {
            SlowRefusal::Ended
        };
        for i in 0..SLOW_SLOTS {
            let outcome = match self.slow.get(i).copied().flatten().map(|e| e.state) {
                Some(SlowState::Queued) => SlowOutcome::Refused(refusal),
                Some(
                    state @ (SlowState::Sending | SlowState::Waiting | SlowState::Heard { .. }),
                ) => state.timed_out(),
                Some(SlowState::Done(_)) | None => continue,
            };
            self.finish_slow(i, outcome);
        }
        refusal
    }

    /// A slow result couldn't be handed to control (its ring was full): counted in the next snapshot, and, for one
    /// dropped after the last, in what the thread hands back when it ends (`BusExit::slow_results_dropped`).
    pub fn slow_result_dropped(&mut self) {
        self.counters.slow_results_dropped += 1;
    }

    /// At a tick's start: a slow request still unanswered has timed out, and a probe's or set-ID's answers are in.
    pub(crate) fn time_out_slow(&mut self) {
        if let Some(i) = self.slow_index(|e| e.state.in_flight()) {
            let outcome = self
                .slow
                .get(i)
                .copied()
                .flatten()
                .map_or(SlowOutcome::TimedOut, |e| e.state.timed_out());
            self.finish_slow(i, outcome);
        }
    }

    /// A type-0 reply from `device`: whether it answers the probe or set-ID in flight, a probe of `device` or a set-ID
    /// to `device`. It is held, with any other UID heard on that ID, until the next tick's start.
    pub(crate) fn slow_found_reply(&mut self, device: DeviceId, uid: Uid) -> bool {
        let Some(entry) = self.slow.iter_mut().flatten().find(|e| {
            matches!(e.state, SlowState::Waiting | SlowState::Heard { .. })
                && matches!(
                    e.request.kind,
                    SlowKind::Probe(id) | SlowKind::SetId { new: id, .. } if id == device
                )
        }) else {
            return false;
        };
        entry.state = match entry.state {
            SlowState::Heard {
                uid: first,
                other: None,
            } if first != uid => SlowState::Heard {
                uid: first,
                other: Some(uid),
            },
            heard @ SlowState::Heard { .. } => heard,
            SlowState::Queued | SlowState::Sending | SlowState::Waiting | SlowState::Done(_) => {
                SlowState::Heard { uid, other: None }
            }
        };
        true
    }

    /// A read reply from slot `slot`: whether it answers the read in flight.
    pub(crate) fn slow_read_reply(
        &mut self,
        slot: usize,
        param: Param,
        outcome: ParamOutcome,
    ) -> bool {
        self.answer_slow(
            slot,
            |kind| matches!(kind, SlowKind::Read(p) if p == param),
            SlowOutcome::Read(outcome),
        )
    }

    /// A get-ID reply from slot `slot`: whether it answers the get-ID in flight.
    pub(crate) fn slow_identity_reply(&mut self, slot: usize, uid: Uid) -> bool {
        self.answer_slow(
            slot,
            |kind| matches!(kind, SlowKind::GetId),
            SlowOutcome::Identity(uid),
        )
    }

    /// A status from slot `slot`: whether it answers the write in flight.
    pub(crate) fn slow_write_reply(&mut self, slot: usize) -> bool {
        self.answer_slow(
            slot,
            |kind| matches!(kind, SlowKind::Write(_)),
            SlowOutcome::WriteAnswered,
        )
    }

    fn answer_slow(
        &mut self,
        slot: usize,
        answers: impl Fn(SlowKind) -> bool,
        outcome: SlowOutcome,
    ) -> bool {
        let Some(i) = self.slow_index(|e| {
            matches!(e.state, SlowState::Waiting)
                && e.request.slot == slot
                && answers(e.request.kind)
        }) else {
            return false;
        };
        self.finish_slow(i, outcome);
        true
    }

    fn slow_refusal(&self, request: &SlowRequest) -> Result<(), SlowRefusal> {
        if let SlowKind::Probe(_) | SlowKind::SetId { .. } = request.kind {
            return self.bus_request_refusal();
        }
        let drive = self
            .drives
            .get(request.slot)
            .and_then(Option::as_ref)
            .ok_or(SlowRefusal::NoSuchSlot)?;
        if let SlowKind::Write(write) = request.kind {
            if write.target() != drive.device {
                return Err(SlowRefusal::WrongTarget);
            }
            // A write of a kind control's batch carries (the enable sequence's `run_mode` = MIT) would leave its echo
            // as the drive's `last_echo`, which keeps only those kinds for the enable sequence.
            if batch_may_carry(EchoKind::ParamWrite {
                param: write.param(),
                value: write.value(),
            }) {
                return Err(SlowRefusal::BatchOnly);
            }
        }
        if self.bus_error.is_some() {
            return Err(SlowRefusal::BusFailed);
        }
        let Some(limb) = self.limbs.get(drive.limb).and_then(Option::as_ref) else {
            return Err(SlowRefusal::LimbStopped);
        };
        // A stop asked for but not yet taken counts: it is taken at the next tick's start, before any send.
        if self.stop_pending(drive.limb)
            || !limb.state.takes_commands()
            || self.limb_stop_due(drive.limb).is_some()
        {
            return Err(SlowRefusal::LimbStopped);
        }
        if self.silent >= self.timing.silent_ticks {
            return Err(SlowRefusal::ControlSilent);
        }
        if let SlowKind::Write(_) = request.kind {
            if limb.state != LimbState::Idle {
                return Err(SlowRefusal::LimbNotIdle);
            }
            // An idle limb's batch may still carry a Disable or the run_mode write. Only this tick's: an earlier one's
            // reply is late or lost, and a lost one must not hold writes off for good.
            if drive
                .outstanding
                .is_some_and(|o| o.tick == self.tick && o.reply == Reply::Waiting)
            {
                return Err(SlowRefusal::CommandUnanswered);
            }
        }
        Ok(())
    }

    /// Why a probe or set-ID may not go now: the bus has failed, a limb on it isn't idle (or a stop of it is asked or
    /// due), or control is silent. Its frame may reach any drive on the bus, so every limb must be idle, not only one.
    fn bus_request_refusal(&self) -> Result<(), SlowRefusal> {
        if self.bus_error.is_some() {
            return Err(SlowRefusal::BusFailed);
        }
        for (i, limb) in self.limbs.iter().enumerate() {
            if let Some(limb) = limb
                && (limb.state != LimbState::Idle
                    || self.stop_pending(i)
                    || self.limb_stop_due(i).is_some())
            {
                return Err(SlowRefusal::BusNotIdle);
            }
        }
        if self.silent >= self.timing.silent_ticks {
            return Err(SlowRefusal::ControlSilent);
        }
        Ok(())
    }

    fn slow_index(&self, pick: impl Fn(&SlowEntry) -> bool) -> Option<usize> {
        self.slow.iter().position(|e| e.as_ref().is_some_and(&pick))
    }

    fn finish_slow(&mut self, i: usize, outcome: SlowOutcome) {
        if let Some(e) = self.slow.get_mut(i).and_then(Option::as_mut) {
            e.state = SlowState::Done(outcome);
        }
    }
}
