//! Slow requests: parameter reads, allowlisted writes and get-ID, for preflight and the once-a-second reads. Each waits
//! in one of [`SLOW_SLOTS`], is cancelled or expired as a slack opens ([`BusTick::open_slack`]), goes alone in the slack
//! after the collect deadline ([`BusTick::slow_send`]), is answered or timed out by the next tick's start, and ends in
//! one [`SlowResult`]. Which requests are refused, what answers each kind and what a write's answer proves are in
//! crates/can/README.md, Slow requests; the rule is conventions/can.md section 2.

use robstride::{EchoKind, Frame, Param, ParamOutcome, Uid, Write, encode};

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
    /// The drive's slot on this bus.
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
    /// The drive sent a status after the write. That says nothing about the value: read it back.
    WriteAnswered,
    /// Sent, but no reply was read by the next tick's start.
    TimedOut,
    /// The socket didn't take it.
    NotSent(Unsent),
    /// Never sent.
    Refused(SlowRefusal),
}

/// Why the socket didn't take a slow frame.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Unsent {
    /// Past its time: still queued [`Timing::slow_queue_ticks`](crate::Timing::slow_queue_ticks) ticks after the tick
    /// it was submitted in, with no slack in them that let it go.
    Expired,
    /// The adapter's queue was full.
    QueueFull,
    /// The write failed, and the bus with it.
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
    Done(SlowOutcome),
}

impl SlowState {
    /// Handed to the shell or taken by the socket, with no result yet: the one exchange a bus has in flight.
    const fn in_flight(self) -> bool {
        match self {
            Self::Sending | Self::Waiting => true,
            Self::Queued | Self::Done(_) => false,
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
        let device = self
            .drives
            .get(entry.request.slot)
            .and_then(Option::as_ref)?
            .device;
        let frame = match entry.request.kind {
            SlowKind::Read(param) => encode::param_read(device, param),
            SlowKind::Write(write) => encode::param_write(&write),
            SlowKind::GetId => encode::get_id(device),
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
                let slot = self.slow.get(i).copied().flatten().map(|e| e.request.slot);
                if let Some(d) = slot
                    .and_then(|s| self.drives.get_mut(s))
                    .and_then(Option::as_mut)
                {
                    d.last_sent_ns = Some(sent_ns);
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
                    SlowState::Queued | SlowState::Sending | SlowState::Waiting => return None,
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
                Some(SlowState::Sending | SlowState::Waiting) => SlowOutcome::TimedOut,
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

    /// At a tick's start: a slow request still unanswered has timed out.
    pub(crate) fn time_out_slow(&mut self) {
        if let Some(i) = self.slow_index(|e| e.state.in_flight()) {
            self.finish_slow(i, SlowOutcome::TimedOut);
        }
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
        if self.pending_stop.is_some()
            || limb.pending.is_some()
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

    fn slow_index(&self, pick: impl Fn(&SlowEntry) -> bool) -> Option<usize> {
        self.slow.iter().position(|e| e.as_ref().is_some_and(&pick))
    }

    fn finish_slow(&mut self, i: usize, outcome: SlowOutcome) {
        if let Some(e) = self.slow.get_mut(i).and_then(Option::as_mut) {
            e.state = SlowState::Done(outcome);
        }
    }
}
