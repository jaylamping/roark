//! One bus's tick as plain values: what to send, what each frame read means, and the snapshot at the end. No socket,
//! no clock: the shell passes the monotonic time in (testing.md rule 6).
//!
//! Correlation (PLAN.md item 3): one command per drive per tick. A status read after a command the socket took is that
//! drive's fresh status; it answers the tick if read by the collect deadline. The shell empties the socket before it
//! sends, so what it reads afterwards came after the backlog: a frame landing in the microseconds between the drain and
//! the write still counts as after the send, which is evidence of the drive at that moment. Which command a status
//! answers can't be proven (no sequence numbers): it is evidence the drive is there and of its state then, never an
//! acknowledgement.

use robstride::encode::{self, Reporting};
use robstride::{
    DecodeError, DeviceId, EchoKind, Frame, Inbound, Mode, Param, ParamValue, RunMode, Status,
    decode,
};
use telemetry::{Direction, FrameRecord};

use crate::error_frame::{BusError, classify, controller_passive};
use crate::types::{
    BusState, CommandBatch, ConfigError, Counters, Drain, DriveView, MAX_DRIVES, Observed, Send,
    SendKind, SendList, SendOutcome, Snapshot, StopOutcome, StopReason, Timing,
};

/// A command the socket took, waiting for its status.
#[derive(Clone, Copy, Debug)]
struct Outstanding {
    tick: u64,
    deadline_ns: u64,
    /// A stop's Disable: a Reset status after it confirms the stop.
    stop_disable: bool,
    /// Whether a missing status counts as unanswered. Not for Enable or Disable: the drive may be slow or silent then
    /// (PLAN.md item 2 Silence windows).
    counts_missed: bool,
    reply: Reply,
    counted: bool,
}

/// Whether an outstanding command has had its status yet.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Reply {
    Waiting,
    OnTime,
    Late,
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
    /// When this stop's Disable was confirmed.
    confirmed_ns: Option<u64>,
    /// Whether this stop's reporting-off was taken by the socket.
    reporting_off_sent: bool,
}

/// One bus's drives and the tick logic over them.
#[derive(Debug)]
pub struct BusTick {
    timing: Timing,
    drives: [Option<DriveState>; MAX_DRIVES],
    state: BusState,
    stop: Option<StopReason>,
    pending_stop: Option<StopReason>,
    bus_error: Option<BusError>,
    error_passive: bool,
    /// Reads may predate this tick's sends: the last drain left frames queued, and none since has emptied the socket.
    unordered: bool,
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
    /// [`ConfigError::TooManyDrives`] past [`MAX_DRIVES`]; [`ConfigError::DuplicateDrive`] for a drive listed twice
    /// (every status would go to its first slot); [`ConfigError::Timing`] for timing that
    /// [`Timing::check`] refuses.
    pub fn new(devices: &[DeviceId], timing: Timing) -> Result<Self, ConfigError> {
        if devices.len() > MAX_DRIVES {
            return Err(ConfigError::TooManyDrives(devices.len()));
        }
        for (i, device) in devices.iter().enumerate() {
            if devices.iter().skip(i + 1).any(|d| d == device) {
                return Err(ConfigError::DuplicateDrive(*device));
            }
        }
        timing.check().map_err(ConfigError::Timing)?;
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
                confirmed_ns: None,
                reporting_off_sent: false,
            });
        }
        Ok(Self {
            timing,
            drives,
            state: BusState::Idle,
            stop: None,
            pending_stop: None,
            bus_error: None,
            error_passive: false,
            unordered: false,
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

    /// How this tick's drain ended: call it after the drain (its frames already fed to [`Self::on_frame`]), before
    /// [`Self::begin`]. A backlog stops an active or stopping bus at this tick's start. Reads stay unordered from a
    /// drain that left frames queued until a drain empties the socket.
    ///
    /// The frames of the drain itself are ordered unless an earlier drain left the socket unemptied: the socket is a
    /// queue, and the last drain emptied it before the last tick's sends, so whatever this drain reads came after them.
    /// Only what a drain leaves queued may predate the next sends, which is what `Unemptied` marks.
    pub fn drained(&mut self, drain: Drain) {
        match drain {
            Drain::Emptied => self.unordered = false,
            Drain::Backlog => {
                self.pending_stop.get_or_insert(StopReason::Backlog);
                self.unordered = false;
            }
            Drain::Unemptied => {
                self.pending_stop.get_or_insert(StopReason::Backlog);
                self.unordered = true;
            }
        }
    }

    /// The socket failed with `error` (interface down or gone): latch stopped. There is no bus to send a stop on; the
    /// drives time out on their own (`canTimeout`). An error that doesn't latch ([`BusError::latches`]) changes nothing
    /// here: it isn't a lost bus.
    pub fn lost_bus(&mut self, error: BusError) {
        if error.latches() {
            self.latch(error);
        }
    }

    /// The socket's overflow counter, the last value the shell saw (`SO_RXQ_OVFL` comes only on frames queued after a
    /// drop, so a frame without it is no news).
    pub fn note_kernel_drops(&mut self, count: u32) {
        self.counters.kernel_drops = count;
    }

    /// `count` ticks went by without running (the thread stalled past them): each a missed deadline, and the bus stops
    /// as for a late wake (PLAN.md item 3: missed deadlines are counted, never skipped silently).
    pub fn skipped(&mut self, count: u64, now_ns: u64) {
        if count > 0 {
            self.counters.missed_deadlines += count;
            self.begin_stop(StopReason::LateWake, now_ns);
        }
    }

    /// The last snapshot couldn't be handed to control (its ring was full): counted in the next one.
    pub fn snapshot_dropped(&mut self) {
        self.counters.snapshots_dropped += 1;
    }

    /// Start tick `tick`, scheduled at `scheduled_ns`, woken at `now_ns`, with the newest batch from control. Call after
    /// draining the socket and [`Self::drained`]. Returns the frames to send, in order; report each with [`Self::sent`].
    /// Each send says whether it expires ([`Send::expires`]): a command goes out only inside the send window, while a
    /// Disable or active reporting off goes out late too, whoever planned it, since late it is still the right frame.
    ///
    /// A wake past the send window is a missed deadline, counted in every state. It stops an active bus; an idle bus
    /// (nothing enabled since start) has nothing to stop, so it sends nothing that tick and carries on (PLAN.md item 3
    /// stops a late wake for its limbs' sake).
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
        // A stop asked for before this tick began came first, so it keeps its reason over a late wake.
        if let Some(reason) = self.pending_stop.take() {
            // A backlog on an idle bus stops nothing: no drive is enabled. Its reads stay unordered all the same.
            if reason != StopReason::Backlog || self.state != BusState::Idle {
                self.begin_stop(reason, now_ns);
            }
        }
        if now_ns > scheduled_ns.saturating_add(self.timing.send_window_ns) {
            self.counters.missed_deadlines += 1;
            match self.state {
                BusState::Active => self.begin_stop(StopReason::LateWake, now_ns),
                BusState::Idle => {
                    if batch.is_some() {
                        self.counters.stale_ticks += 1;
                    }
                    return self.sends;
                }
                BusState::Stopping { .. } | BusState::Stopped => {}
            }
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
                    self.stop_now(StopReason::ControlSilent, now_ns);
                }
            }
            return;
        };
        self.silent = 0;
        // Check the whole batch before sending any of it.
        for (slot, frame) in batch.frames().iter().enumerate() {
            let Some(frame) = frame else { continue };
            let Some(drive) = self.drives.get(slot).copied().flatten() else {
                self.stop_now(StopReason::BadBatch { slot }, now_ns);
                return;
            };
            let Some((kind, target)) = echo_of(frame) else {
                self.stop_now(StopReason::BadBatch { slot }, now_ns);
                return;
            };
            if target != drive.device || !batch_may_carry(kind) {
                self.stop_now(StopReason::BadBatch { slot }, now_ns);
                return;
            }
            let stale = drive
                .fresh_ns
                .is_none_or(|at| now_ns.saturating_sub(at) > self.timing.feedback_limit_ns);
            if matches!(kind, EchoKind::Mit) && stale {
                self.stop_now(StopReason::ExpiredFeedback { slot }, now_ns);
                return;
            }
        }
        for (slot, frame) in batch.frames().iter().enumerate() {
            if let Some(frame) = frame {
                let late_ok = matches!(
                    echo_of(frame),
                    Some((EchoKind::Disable | EchoKind::Reporting(Reporting::Off), _))
                );
                self.sends.push(Send {
                    slot,
                    kind: SendKind::Command,
                    frame: *frame,
                    expires: !late_ok,
                });
            }
        }
    }

    fn stop_now(&mut self, reason: StopReason, now_ns: u64) {
        self.begin_stop(reason, now_ns);
        self.plan_stop(now_ns);
    }

    /// While stopping: inside the confirm window, Disable to every drive not yet confirmed; and reporting off to each
    /// confirmed drive once the post-Disable silence after its confirmation is over (a drive drops every frame in it,
    /// PLAN.md item 2 Silence windows), until the socket takes it. A drive that never confirms is sent a Disable every
    /// tick of the window, so it never leaves its silence and gets no reporting off. Stopped once the window has passed
    /// and no confirmed drive still waits for its reporting off ([`Self::stop_over`]).
    fn plan_stop(&mut self, now_ns: u64) {
        let BusState::Stopping { since_ns } = self.state else {
            return;
        };
        if self.stop_over(since_ns, now_ns) {
            self.state = BusState::Stopped;
            return;
        }
        let confirming = now_ns.saturating_sub(since_ns) < self.timing.stop_confirm_ns;
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && confirming
                && d.stop != StopOutcome::Confirmed
            {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::Disable,
                    frame: encode::disable(d.device),
                    expires: false,
                });
            }
        }
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && !d.reporting_off_sent
                && d.confirmed_ns
                    .is_some_and(|at| now_ns >= at.saturating_add(self.timing.disable_silence_ns))
            {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::ReportingOff,
                    frame: encode::active_reporting(d.device, Reporting::Off),
                    expires: false,
                });
            }
        }
    }

    /// Whether a stop that began at `since_ns` is over at `now_ns`. Disables go out for the confirm window; a drive
    /// confirmed in it (or by a Reset read just after it) still gets its reporting off once its silence is over, so
    /// the stop runs on past the window while one waits, at most until the window, the silence and a period have
    /// passed: a drive confirmed at the window's end is then a tick past its silence.
    fn stop_over(&self, since_ns: u64, now_ns: u64) -> bool {
        let elapsed = now_ns.saturating_sub(since_ns);
        if elapsed < self.timing.stop_confirm_ns {
            return false;
        }
        let waiting = self
            .drives
            .iter()
            .flatten()
            .any(|d| d.confirmed_ns.is_some() && !d.reporting_off_sent);
        let cap = self
            .timing
            .stop_confirm_ns
            .saturating_add(self.timing.disable_silence_ns)
            .saturating_add(self.timing.period_ns);
        !waiting || elapsed >= cap
    }

    fn begin_stop(&mut self, reason: StopReason, now_ns: u64) {
        if matches!(self.state, BusState::Stopping { .. } | BusState::Stopped) {
            return;
        }
        self.stop = Some(reason);
        self.state = BusState::Stopping { since_ns: now_ns };
        for d in self.drives.iter_mut().flatten() {
            d.stop = StopOutcome::NeverSent;
            d.confirmed_ns = None;
            d.reporting_off_sent = false;
        }
    }

    /// A bus error that leaves nothing to send on: stopped now, whatever the bus was doing. The first such error is
    /// kept in every later snapshot.
    fn latch(&mut self, error: BusError) {
        self.bus_error.get_or_insert(error);
        if matches!(self.state, BusState::Idle | BusState::Active) {
            self.stop = Some(StopReason::Bus(error));
            for d in self.drives.iter_mut().flatten() {
                d.stop = StopOutcome::NeverSent;
            }
        }
        self.state = BusState::Stopped;
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
                EchoKind::Mit | EchoKind::Enable | EchoKind::Disable | EchoKind::ParamWrite { .. }
            )
        );
        let deadline_ns = self.scheduled_ns.saturating_add(self.timing.collect_ns);
        let tick = self.tick;
        let Some(d) = self.drives.get_mut(send.slot).and_then(Option::as_mut) else {
            return;
        };
        match send.kind {
            SendKind::Disable if d.stop == StopOutcome::NeverSent => d.stop = StopOutcome::Sent,
            SendKind::ReportingOff => d.reporting_off_sent = true,
            SendKind::Disable | SendKind::Command => {}
        }
        if expects_status {
            d.outstanding = Some(Outstanding {
                tick,
                deadline_ns,
                stop_disable: send.kind == SendKind::Disable,
                counts_missed: !matches!(kind, Some(EchoKind::Enable | EchoKind::Disable)),
                reply: Reply::Waiting,
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
                self.latch(error);
            }
            // The controller's state, read on its own: a frame can carry it beside a more severe flag (passive back
            // to warning together with an overflow), and warning after passive is a recovery.
            if let Some(passive) = controller_passive(frame.id, frame.data) {
                self.error_passive = passive;
            }
            return;
        }
        if !frame.extended || frame.remote {
            self.counters.undecodable += 1;
            return;
        }
        match decode(frame.id, frame.payload()) {
            // The codec names frames only another sender could have put on the bus.
            Err(
                DecodeError::OtherHost { .. }
                | DecodeError::ForeignType { .. }
                | DecodeError::ForeignWrite { .. },
            ) => self.counters.foreign_host += 1,
            Err(
                DecodeError::IdTooWide(_)
                | DecodeError::BadLength { .. }
                | DecodeError::UnknownType { .. }
                | DecodeError::BadDeviceId { .. }
                | DecodeError::ReservedMode { .. }
                | DecodeError::UnknownParam { .. }
                | DecodeError::BadParamValue { .. }
                | DecodeError::UnexpectedData { .. },
            ) => self.counters.undecodable += 1,
            Ok(Inbound::Echo(_)) => {
                if frame.direction == Direction::TxEcho {
                    self.counters.echoes += 1;
                } else {
                    self.counters.foreign_host += 1;
                }
            }
            Ok(Inbound::Status(status)) => self.on_status(read_ns, status, true),
            Ok(Inbound::Report(status)) => self.on_status(read_ns, status, false),
            Ok(Inbound::Fault { device, faults, .. }) => match self.slot_of(device) {
                // Warnings alone aren't a fault (the codec: non-zero fault bytes mean faulted).
                Some(d) => d.fault_seen |= faults != [0; 4],
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Version { header, .. }) => match self.slot_of(header.device) {
                Some(d) => d.fault_seen |= !header.faults.is_empty(),
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Identity { device, .. } | Inbound::Param { device, .. }) => {
                if self.slot_of(device).is_none() {
                    self.counters.unexpected += 1;
                }
            }
        }
    }

    fn on_status(&mut self, read_ns: u64, status: Status, answer: bool) {
        let device = status.header.device;
        let tick = self.tick;
        let unordered = self.unordered;
        let stopping = matches!(self.state, BusState::Stopping { .. });
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
        let Some(o) = d.outstanding.as_mut().filter(|_| !unordered) else {
            self.counters.unsolicited += 1;
            return;
        };
        if o.reply == Reply::Waiting {
            d.fresh_ns = Some(read_ns);
            if read_ns <= o.deadline_ns {
                o.reply = Reply::OnTime;
                d.answered = o.tick == tick;
            } else {
                o.reply = Reply::Late;
                self.counters.late += 1;
            }
        } else if o.tick == tick {
            self.counters.duplicate += 1;
        } else {
            self.counters.unsolicited += 1;
        }
        // Any Reset after the stop's Disable confirms it, even behind an earlier status still in flight. Once stopped,
        // nothing more is sent, so a confirmation then would record a reporting off that never comes.
        if stopping
            && o.stop_disable
            && status.header.mode == Mode::Reset
            && d.stop != StopOutcome::Confirmed
        {
            d.stop = StopOutcome::Confirmed;
            d.confirmed_ns = Some(read_ns);
        }
    }

    fn slot_of(&mut self, device: DeviceId) -> Option<&mut DriveState> {
        self.drives
            .iter_mut()
            .flatten()
            .find(|d| d.device == device)
    }

    /// End the tick at `now_ns` (the collect deadline): count commands not answered by the deadline and return the
    /// snapshot.
    pub fn end(&mut self, now_ns: u64) -> Snapshot {
        let tick = self.tick;
        for d in self.drives.iter_mut().flatten() {
            if let Some(o) = d.outstanding.as_mut()
                && o.tick == tick
                && o.counts_missed
                && o.reply != Reply::OnTime
                && !o.counted
            {
                o.counted = true;
                self.counters.unanswered += 1;
            }
        }
        if let BusState::Stopping { since_ns } = self.state {
            let all_done = self
                .drives
                .iter()
                .flatten()
                .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent);
            if all_done || self.stop_over(since_ns, now_ns) {
                self.state = BusState::Stopped;
            }
        }
        let healthy = self.bus_error.is_none() && !self.error_passive;
        let mut snap = Snapshot::new(
            tick,
            self.state,
            self.stop,
            self.bus_error,
            healthy,
            self.counters,
        );
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
                        reporting_off_sent: d.reporting_off_sent,
                    },
                );
            }
        }
        snap
    }
}

/// Whether control's batch may carry a frame of this kind: motion, Enable, Disable, and the enable sequence's active
/// reporting off and `run_mode` = MIT write (PLAN.md item 2 Enable one drive). Set Zero, set-ID, parameter reads and
/// other writes, reporting on and queries each need sequencing a per-tick batch can't give (PLAN.md item 2: Set Zero
/// only with the limb stopped, set-ID only with one drive answering); a set-ID would also leave the drive table on the
/// old ID.
fn batch_may_carry(kind: EchoKind) -> bool {
    matches!(
        kind,
        EchoKind::Mit
            | EchoKind::Enable
            | EchoKind::Disable
            | EchoKind::Reporting(Reporting::Off)
            | EchoKind::ParamWrite {
                param: Param::RunMode,
                value: ParamValue::RunMode(RunMode::Mit),
            }
    )
}

/// What a host frame is and whom it targets, read back through the codec (so the ID layout stays in `robstride`).
fn echo_of(frame: &Frame) -> Option<(EchoKind, DeviceId)> {
    match decode(frame.id(), &frame.data()) {
        Ok(Inbound::Echo(echo)) => Some((echo.kind, echo.target)),
        Ok(
            Inbound::Identity { .. }
            | Inbound::Status(_)
            | Inbound::Report(_)
            | Inbound::Fault { .. }
            | Inbound::Version { .. }
            | Inbound::Param { .. },
        )
        | Err(_) => None,
    }
}
