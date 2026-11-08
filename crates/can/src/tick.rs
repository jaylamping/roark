//! One bus's tick as plain values: what to send, what each frame read means, and the snapshot at the end. No socket,
//! no clock: the shell passes the monotonic time in (testing.md rule 6).
//!
//! Correlation (PLAN.md item 3): one command per drive per tick. A status read after a command the socket took is that
//! drive's fresh status; it answers the tick if read by the collect deadline. The shell drains the socket before it
//! sends, so a frame read after the send arrived after it. Which command a status answers can't be proven (no sequence
//! numbers): it is evidence the drive is there and of its state then, never an acknowledgement.

use robstride::encode::{self, Reporting};
use robstride::{DeviceId, EchoKind, Frame, Inbound, Mode, Status, decode};
use telemetry::{Direction, FrameRecord};

use crate::error_frame::{BusError, classify};
use crate::types::{
    BusState, CommandBatch, Counters, DriveView, MAX_DRIVES, Observed, Send, SendKind, SendList,
    SendOutcome, Snapshot, StopOutcome, StopReason, Timing, TooManyDrives,
};

/// A command the socket took, waiting for its status.
#[derive(Clone, Copy, Debug)]
struct Outstanding {
    tick: u64,
    deadline_ns: u64,
    disable: bool,
    matched: bool,
    counted: bool,
}

#[derive(Clone, Copy, Debug)]
struct DriveState {
    device: DeviceId,
    observed: Option<Observed>,
    fresh_ns: Option<u64>,
    outstanding: Option<Outstanding>,
    answered: bool,
    fault_seen: bool,
    stop: StopOutcome,
}

/// One bus's drives and the tick logic over them.
#[derive(Debug)]
pub struct BusTick {
    timing: Timing,
    drives: [Option<DriveState>; MAX_DRIVES],
    state: BusState,
    stop: Option<StopReason>,
    pending_stop: Option<StopReason>,
    reporting_off_due: bool,
    counters: Counters,
    silent: u32,
    tick: u64,
    scheduled_ns: u64,
    sends: SendList,
}

impl BusTick {
    /// The drives this bus owns, in slot order (the skeleton's order).
    ///
    /// # Errors
    /// [`TooManyDrives`] past [`MAX_DRIVES`].
    pub fn new(devices: &[DeviceId], timing: Timing) -> Result<Self, TooManyDrives> {
        if devices.len() > MAX_DRIVES {
            return Err(TooManyDrives(devices.len()));
        }
        let mut drives = [None; MAX_DRIVES];
        for (slot, &device) in drives.iter_mut().zip(devices) {
            *slot = Some(DriveState {
                device,
                observed: None,
                fresh_ns: None,
                outstanding: None,
                answered: false,
                fault_seen: false,
                stop: StopOutcome::None,
            });
        }
        Ok(Self {
            timing,
            drives,
            state: BusState::Idle,
            stop: None,
            pending_stop: None,
            reporting_off_due: false,
            counters: Counters::default(),
            silent: 0,
            tick: 0,
            scheduled_ns: 0,
            sends: SendList::EMPTY,
        })
    }

    /// The tick's timing.
    #[must_use]
    pub fn timing(&self) -> Timing {
        self.timing
    }

    /// Stop at the start of the next tick: Disable to every drive, then reporting off.
    pub fn request_stop(&mut self) {
        self.pending_stop.get_or_insert(StopReason::Requested);
    }

    /// More frames were queued before the send than the shell may read: stop at this tick's start, since what the bus
    /// said can't be known in time.
    pub fn backlog(&mut self) {
        self.pending_stop = Some(StopReason::Backlog);
    }

    /// The socket failed with `error` (interface down or gone): latch stopped. There is no bus to send a stop on; the
    /// drives time out on their own (`canTimeout`).
    pub fn lost_bus(&mut self, error: BusError) {
        self.latch(StopReason::Bus(error));
    }

    /// The socket's overflow counter, the last value the shell saw (`SO_RXQ_OVFL` comes only on frames queued after a
    /// drop, so a frame without it is no news).
    pub fn note_kernel_drops(&mut self, count: u32) {
        self.counters.kernel_drops = count;
    }

    /// Start tick `tick`, scheduled at `scheduled_ns`, woken at `now_ns`, with the newest batch from control. Call after
    /// draining the socket. Returns the frames to send, in order; report each with [`Self::sent`].
    pub fn begin(
        &mut self,
        tick: u64,
        now_ns: u64,
        scheduled_ns: u64,
        batch: Option<&CommandBatch>,
    ) -> SendList {
        self.tick = tick;
        self.scheduled_ns = scheduled_ns;
        self.sends = SendList::EMPTY;
        for d in self.drives.iter_mut().flatten() {
            d.answered = false;
        }
        if now_ns > scheduled_ns.saturating_add(self.timing.send_window_ns) {
            self.counters.missed_deadlines += 1;
            self.begin_stop(StopReason::LateWake, now_ns);
        }
        if let Some(reason) = self.pending_stop.take() {
            self.begin_stop(reason, now_ns);
        }
        match self.state {
            BusState::Stopped | BusState::Stopping { .. } => {
                if batch.is_some() {
                    self.counters.refused_batches += 1;
                }
                self.plan_stop(now_ns);
            }
            BusState::Idle | BusState::Active => self.plan_batch(tick, now_ns, batch),
        }
        self.sends
    }

    fn plan_batch(&mut self, tick: u64, now_ns: u64, batch: Option<&CommandBatch>) {
        let fresh = batch.filter(|b| b.tick == tick && b.expires_ns > now_ns);
        let Some(batch) = fresh else {
            if batch.is_some() {
                self.counters.stale_ticks += 1;
            }
            if self.state == BusState::Active {
                self.silent += 1;
                if self.silent >= self.timing.silent_ticks {
                    self.begin_stop(StopReason::ControlSilent, now_ns);
                    self.plan_stop(now_ns);
                }
            }
            return;
        };
        self.silent = 0;
        // Check the whole batch before sending any of it.
        for (slot, frame) in batch.frames().iter().enumerate() {
            let Some(frame) = frame else { continue };
            let Some(drive) = self.drives.get(slot).copied().flatten() else {
                self.begin_stop(StopReason::BadBatch { slot }, now_ns);
                self.plan_stop(now_ns);
                return;
            };
            match echo_of(frame) {
                Some((kind, target)) if target == drive.device => {
                    let stale = drive
                        .fresh_ns
                        .is_none_or(|at| now_ns.saturating_sub(at) > self.timing.feedback_limit_ns);
                    if matches!(kind, EchoKind::Mit) && stale {
                        self.begin_stop(StopReason::ExpiredFeedback { slot }, now_ns);
                        self.plan_stop(now_ns);
                        return;
                    }
                }
                _ => {
                    self.begin_stop(StopReason::BadBatch { slot }, now_ns);
                    self.plan_stop(now_ns);
                    return;
                }
            }
        }
        for (slot, frame) in batch.frames().iter().enumerate() {
            if let Some(frame) = frame {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::Command,
                    frame: *frame,
                });
            }
        }
    }

    /// While stopping: Disable to every drive not yet confirmed, and reporting off once, after the Disables. Once the
    /// confirm window has passed, stopped.
    fn plan_stop(&mut self, now_ns: u64) {
        let BusState::Stopping { since_ns } = self.state else {
            return;
        };
        if now_ns.saturating_sub(since_ns) >= self.timing.stop_confirm_ns {
            self.state = BusState::Stopped;
            return;
        }
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && d.stop != StopOutcome::Confirmed
            {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::Disable,
                    frame: encode::disable(d.device),
                });
            }
        }
        if self.reporting_off_due {
            self.reporting_off_due = false;
            for (slot, d) in self.drives.iter().enumerate() {
                if let Some(d) = d {
                    self.sends.push(Send {
                        slot,
                        kind: SendKind::ReportingOff,
                        frame: encode::active_reporting(d.device, Reporting::Off),
                    });
                }
            }
        }
    }

    fn begin_stop(&mut self, reason: StopReason, now_ns: u64) {
        if matches!(self.state, BusState::Stopping { .. } | BusState::Stopped) {
            return;
        }
        self.stop = Some(reason);
        self.state = BusState::Stopping { since_ns: now_ns };
        self.reporting_off_due = true;
        for d in self.drives.iter_mut().flatten() {
            d.stop = StopOutcome::NeverSent;
        }
    }

    fn latch(&mut self, reason: StopReason) {
        if self.state != BusState::Stopped {
            if !matches!(self.state, BusState::Stopping { .. }) {
                self.stop = Some(reason);
            }
            self.state = BusState::Stopped;
        }
    }

    /// What became of send `index` of this tick's list. A command's status window opens only if the socket took it.
    pub fn sent(&mut self, index: usize, outcome: SendOutcome) {
        let Some(send) = self.sends.get(index) else {
            return;
        };
        match outcome {
            SendOutcome::Sent => {}
            SendOutcome::Expired => {
                self.counters.tx_expired += 1;
                return;
            }
            SendOutcome::QueueFull | SendOutcome::Failed => {
                self.counters.tx_dropped += 1;
                return;
            }
        }
        let kind = echo_of(&send.frame).map(|(kind, _)| kind);
        if matches!(kind, Some(EchoKind::Mit | EchoKind::Enable)) && self.state == BusState::Idle {
            self.state = BusState::Active;
        }
        let expects_status = matches!(
            kind,
            Some(
                EchoKind::Mit
                    | EchoKind::Enable
                    | EchoKind::Disable
                    | EchoKind::SetZero
                    | EchoKind::ParamWrite { .. }
            )
        );
        let deadline_ns = self.scheduled_ns.saturating_add(self.timing.collect_ns);
        let tick = self.tick;
        let Some(d) = self.drives.get_mut(send.slot).and_then(Option::as_mut) else {
            return;
        };
        if send.kind == SendKind::Disable && d.stop == StopOutcome::NeverSent {
            d.stop = StopOutcome::Sent;
        }
        if expects_status {
            d.outstanding = Some(Outstanding {
                tick,
                deadline_ns,
                disable: matches!(kind, Some(EchoKind::Disable)),
                matched: false,
                counted: false,
            });
        }
    }

    /// One frame read at `read_ns`, before the send (draining) or after it.
    pub fn on_frame(&mut self, read_ns: u64, frame: &FrameRecord) {
        if frame.error {
            self.counters.error_frames += 1;
            let error = classify(frame.id, &frame.data);
            if error.latches() {
                self.latch(StopReason::Bus(error));
            }
            return;
        }
        if !frame.extended || frame.remote {
            self.counters.undecodable += 1;
            return;
        }
        match decode(frame.id, frame.payload()) {
            Err(_) => self.counters.undecodable += 1,
            Ok(Inbound::Echo(_)) => {
                if frame.direction == Direction::TxEcho {
                    self.counters.echoes += 1;
                } else {
                    self.counters.foreign_host += 1;
                }
            }
            Ok(Inbound::Status(status)) => self.on_status(read_ns, status, true),
            Ok(Inbound::Report(status)) => self.on_status(read_ns, status, false),
            Ok(Inbound::Fault { device, .. }) => match self.slot_of(device) {
                Some(d) => d.fault_seen = true,
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Version { header, .. }) => {
                if self.slot_of(header.device).is_none() {
                    self.counters.unexpected += 1;
                }
            }
            Ok(Inbound::Identity { device, .. } | Inbound::Param { device, .. }) => {
                if self.slot_of(device).is_none() {
                    self.counters.unexpected += 1;
                }
            }
        }
    }

    fn on_status(&mut self, read_ns: u64, status: Status, answer: bool) {
        let device = status.header.device;
        let Some(d) = self
            .drives
            .iter_mut()
            .flatten()
            .find(|d| d.device == device)
        else {
            self.counters.unexpected += 1;
            return;
        };
        d.observed = Some(Observed { status, read_ns });
        if !status.header.faults.is_empty() {
            d.fault_seen = true;
        }
        if !answer {
            return;
        }
        match d.outstanding.as_mut() {
            // The shell drains before it sends, so anything read now came after the outstanding command went out.
            Some(o) if o.matched => self.counters.duplicate += 1,
            Some(o) => {
                o.matched = true;
                d.fresh_ns = Some(read_ns);
                if read_ns <= o.deadline_ns {
                    d.answered = o.tick == self.tick;
                } else {
                    self.counters.late += 1;
                }
                if o.disable && status.header.mode == Mode::Reset {
                    d.stop = StopOutcome::Confirmed;
                }
            }
            _ => self.counters.unsolicited += 1,
        }
    }

    fn slot_of(&mut self, device: DeviceId) -> Option<&mut DriveState> {
        self.drives
            .iter_mut()
            .flatten()
            .find(|d| d.device == device)
    }

    /// End the tick at `now_ns` (the collect deadline): count commands still unanswered and return the snapshot.
    pub fn end(&mut self, now_ns: u64) -> Snapshot {
        let tick = self.tick;
        for d in self.drives.iter_mut().flatten() {
            if let Some(o) = d.outstanding.as_mut()
                && o.tick == tick
                && !o.matched
                && !o.counted
            {
                o.counted = true;
                self.counters.unanswered += 1;
            }
        }
        if let BusState::Stopping { since_ns } = self.state {
            let all_confirmed = self
                .drives
                .iter()
                .flatten()
                .all(|d| d.stop == StopOutcome::Confirmed);
            if all_confirmed || now_ns.saturating_sub(since_ns) >= self.timing.stop_confirm_ns {
                self.state = BusState::Stopped;
            }
        }
        let mut snap = Snapshot::new(tick, self.state, self.stop, self.counters);
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d {
                snap.set(
                    slot,
                    DriveView {
                        device: d.device,
                        observed: d.observed,
                        fresh_ns: d.fresh_ns,
                        answered: d.answered,
                        fault_seen: d.fault_seen,
                        stop: d.stop,
                    },
                );
            }
        }
        snap
    }
}

/// What a host frame is and whom it targets, read back through the codec (so the ID layout stays in `robstride`).
fn echo_of(frame: &Frame) -> Option<(EchoKind, DeviceId)> {
    match decode(frame.id(), &frame.data()) {
        Ok(Inbound::Echo(echo)) => Some((echo.kind, echo.target)),
        _ => None,
    }
}
