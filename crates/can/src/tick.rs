//! One bus's tick as plain values: what to send, what each frame read means, and the snapshot at the end. No socket,
//! no clock: the shell passes the monotonic time in (testing.md rule 6).
//!
//! Correlation (PLAN.md item 3): one command per drive per tick. A status read after a command the socket took is that
//! drive's fresh status; it answers the tick if read by the collect deadline. The shell empties the socket before it
//! sends, so what it reads afterwards came after the backlog: a frame landing in the microseconds between the drain and
//! the write still counts as after the send, which is evidence of the drive at that moment. Which command a status
//! answers can't be proven (no sequence numbers): it is evidence the drive is there and of its state then, never an
//! acknowledgement.
//!
//! The drives on a bus belong to limbs. Each limb runs and stops on its own; a stop of the whole bus (a late wake, a
//! backlog, control gone silent, a bad batch, a failed bus) stops every limb. Frames in are read in `read.rs`, limb stops
//! are planned in `stop.rs`.

use robstride::encode::Reporting;
use robstride::{DeviceId, EchoKind, Frame, Inbound, Param, ParamValue, RunMode, decode};

use crate::error_frame::BusError;
use crate::types::{
    BusDrive, CommandBatch, ConfigError, Counters, Drain, DriveView, EchoSeen, LimbState, LimbView,
    MAX_DRIVES, NoSuchLimb, Observed, Send, SendKind, SendList, SendOutcome, Snapshot, StopOutcome,
    StopReason, Timing,
};

/// A command the socket took, waiting for its status.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Outstanding {
    pub(crate) tick: u64,
    pub(crate) deadline_ns: u64,
    /// A stop's Disable: a Reset status after it confirms the stop.
    pub(crate) stop_disable: bool,
    /// Whether a missing status counts as unanswered. Not for Enable or Disable, nor for anything sent between an
    /// Enable and the drive's first Run status, or within `Timing::stop_confirm_ns` (100 ms) after a Disable: the drive
    /// may be slow or silent then (PLAN.md item 2 Silence windows).
    pub(crate) counts_missed: bool,
    pub(crate) reply: Reply,
    pub(crate) counted: bool,
}

/// Whether an outstanding command has had its status yet.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Reply {
    Waiting,
    OnTime,
    Late,
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct DriveState {
    pub(crate) device: DeviceId,
    pub(crate) limb: usize,
    pub(crate) observed: Option<Observed>,
    pub(crate) fresh_ns: Option<u64>,
    pub(crate) outstanding: Option<Outstanding>,
    pub(crate) answered: bool,
    pub(crate) fault_seen: bool,
    pub(crate) misses: u32,
    pub(crate) phase: Phase,
    /// When the socket last took a Disable to it.
    pub(crate) disabled_ns: Option<u64>,
    /// When the socket last took a frame to it, as the shell read the clock after the write.
    pub(crate) last_sent_ns: Option<u64>,
    pub(crate) last_echo: Option<EchoSeen>,
    pub(crate) stop: StopOutcome,
    /// When this stop's Disable was confirmed.
    pub(crate) confirmed_ns: Option<u64>,
    /// Whether this stop's reporting-off was taken by the socket.
    pub(crate) reporting_off_sent: bool,
}

/// Where a drive is between this host's Enable and Disable.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Phase {
    /// No Enable taken by the socket since the last Disable.
    Off,
    /// An Enable was taken; no Run status since.
    Enabling,
    /// It reported Run after that Enable.
    Running,
    /// It reported another mode after running, without a Disable from this host: its limb stops before the next send.
    /// Latched when the status is read, so a later status can't hide it.
    LeftRun,
}

/// One limb's run state on this bus.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Limb {
    pub(crate) state: LimbState,
    pub(crate) stop: Option<StopReason>,
    pub(crate) generation: u32,
    /// A stop asked for this limb alone, taken at the next tick's start.
    pub(crate) pending: Option<StopReason>,
}

/// One bus's drives, their limbs, and the tick logic over them.
#[derive(Debug)]
pub struct BusTick {
    pub(crate) timing: Timing,
    pub(crate) drives: [Option<DriveState>; MAX_DRIVES],
    pub(crate) limbs: [Option<Limb>; MAX_DRIVES],
    /// A stop of the whole bus, taken at the next tick's start.
    pub(crate) pending_stop: Option<StopReason>,
    pub(crate) bus_error: Option<BusError>,
    pub(crate) error_passive: bool,
    /// Reads may predate this tick's sends: the last drain left frames queued, and none since has emptied the socket.
    pub(crate) unordered: bool,
    pub(crate) counters: Counters,
    pub(crate) silent: u32,
    pub(crate) tick: u64,
    pub(crate) scheduled_ns: u64,
    pub(crate) sends: SendList,
}

impl BusTick {
    /// The drives this bus owns, in slot order (the skeleton's order), each with its limb.
    ///
    /// # Errors
    /// [`ConfigError::TooManyDrives`] past [`MAX_DRIVES`]; [`ConfigError::DuplicateDrive`] for a drive listed twice;
    /// [`ConfigError::LimbOutOfRange`] for a limb index past the table; [`ConfigError::Timing`] for timing that
    /// [`Timing::check`] refuses.
    pub fn new(drives: &[BusDrive], timing: Timing) -> Result<Self, ConfigError> {
        if drives.len() > MAX_DRIVES {
            return Err(ConfigError::TooManyDrives(drives.len()));
        }
        for (i, drive) in drives.iter().enumerate() {
            if drives.iter().skip(i + 1).any(|d| d.device == drive.device) {
                return Err(ConfigError::DuplicateDrive(drive.device));
            }
        }
        timing.check().map_err(ConfigError::Timing)?;
        let mut table = [None; MAX_DRIVES];
        let mut limbs = [None; MAX_DRIVES];
        for (slot, (entry, drive)) in table.iter_mut().zip(drives).enumerate() {
            let Some(limb) = limbs.get_mut(drive.limb) else {
                return Err(ConfigError::LimbOutOfRange {
                    slot,
                    limb: drive.limb,
                });
            };
            limb.get_or_insert(Limb {
                state: LimbState::Idle,
                stop: None,
                generation: 0,
                pending: None,
            });
            *entry = Some(DriveState {
                device: drive.device,
                limb: drive.limb,
                observed: None,
                fresh_ns: None,
                outstanding: None,
                answered: false,
                fault_seen: false,
                misses: 0,
                phase: Phase::Off,
                disabled_ns: None,
                last_sent_ns: None,
                last_echo: None,
                stop: StopOutcome::None,
                confirmed_ns: None,
                reporting_off_sent: false,
            });
        }
        Ok(Self {
            timing,
            drives: table,
            limbs,
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

    /// Stop the whole bus at the start of the next tick: Disable to every drive, then reporting off.
    pub fn request_stop(&mut self) {
        self.pending_stop.get_or_insert(StopReason::Requested);
    }

    /// Stop limb `limb` at the start of the next tick; the bus's other limbs keep running.
    ///
    /// # Errors
    /// [`NoSuchLimb`] when the limb isn't on this bus; nothing is stopped then, so the caller must stop the right
    /// scope itself.
    pub fn stop_limb(&mut self, limb: usize) -> Result<(), NoSuchLimb> {
        let l = self
            .limbs
            .get_mut(limb)
            .and_then(Option::as_mut)
            .ok_or(NoSuchLimb(limb))?;
        l.pending.get_or_insert(StopReason::Requested);
        Ok(())
    }

    /// How this tick's drain ended: call it after the drain (its frames already fed to [`Self::on_frame`]), before
    /// [`Self::begin`]. A backlog stops every active limb at this tick's start. Reads stay unordered from a drain that
    /// left frames queued until a drain empties the socket.
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

    /// The socket failed with `error` (interface down or gone, or any other socket error): every limb latches stopped.
    /// There is no bus to send a stop on; the drives time out on their own (`canTimeout`). An error that doesn't latch
    /// ([`BusError::latches`]) changes nothing here: it isn't a lost bus.
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

    /// `count` ticks went by without running (the thread stalled past them): each a missed deadline (PLAN.md item 3:
    /// missed deadlines are counted, never skipped silently). As for a late wake, every active limb stops, at the next
    /// `begin`; an idle limb has nothing to stop.
    pub fn skipped(&mut self, count: u64) {
        if count > 0 {
            self.counters.missed_deadlines += count;
            self.pending_stop.get_or_insert(StopReason::LateWake);
        }
    }

    /// Whether every limb is idle or stopped now, so nothing needs stopping (the shell's exit check, after the drain).
    #[must_use]
    pub fn settled(&self) -> bool {
        self.limbs.iter().flatten().all(|l| l.state.settled())
    }

    /// Whether the bus is healthy now: no latched bus error and not error-passive. The snapshot's `healthy` is this at
    /// `end`.
    #[must_use]
    pub fn healthy(&self) -> bool {
        self.bus_error.is_none() && !self.error_passive
    }

    /// The last snapshot couldn't be handed to control (its ring was full): counted in the next one.
    pub fn snapshot_dropped(&mut self) {
        self.counters.snapshots_dropped += 1;
    }

    /// Start tick `tick`, scheduled at `scheduled_ns`, woken at `now_ns`, with the newest batch from control. Call after
    /// draining the socket and [`Self::drained`]. Returns the frames to send, in order, stop frames first; report each
    /// with [`Self::sent`]. Each send says whether it expires ([`Send::expires`]): a command goes out only inside the
    /// send window, while a Disable or active reporting off goes out late too, whoever planned it.
    ///
    /// A stop asked for before the tick (the whole bus's or one limb's) is taken first, so it keeps its reason. A wake
    /// past the send window is a missed deadline, counted whatever the limbs are doing: every active limb stops, an idle
    /// one has nothing to stop, and no batch is sent that tick. Then, before anything is planned, a drive of an idle or
    /// active limb that the drain or an earlier read showed faulted, out of Run after running, or silent too long stops
    /// its limb, so no command (Enable included) reaches it this tick.
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
            self.stop_bus(reason, now_ns);
        }
        self.take_pending_limb_stops(now_ns);
        let late = now_ns > scheduled_ns.saturating_add(self.timing.send_window_ns);
        if late {
            self.counters.missed_deadlines += 1;
            self.stop_bus(StopReason::LateWake, now_ns);
        }
        self.veto(now_ns);
        let accepted = if late {
            if batch.is_some() {
                if self.any_running() {
                    self.counters.stale_ticks += 1;
                } else {
                    self.counters.refused_batches += 1;
                }
            }
            None
        } else if self.any_running() {
            self.check_batch(tick, now_ns, batch)
        } else {
            if batch.is_some() {
                self.counters.refused_batches += 1;
            }
            None
        };
        self.plan_stops(now_ns);
        if let Some(batch) = accepted {
            self.push_commands(&batch);
        }
        self.sends
    }

    /// Whether any limb is idle or active, so a batch could carry something.
    fn any_running(&self) -> bool {
        self.limbs
            .iter()
            .flatten()
            .any(|l| l.state.takes_commands())
    }

    /// The batch if it is fresh and sound. A frame aimed wrong, in a slot with no drive, or of a kind a batch may not
    /// carry is a bug upstream and stops the whole bus; motion on expired feedback stops that drive's limb.
    fn check_batch(
        &mut self,
        tick: u64,
        now_ns: u64,
        batch: Option<&CommandBatch>,
    ) -> Option<CommandBatch> {
        let fresh = batch.filter(|b| b.tick == tick && b.expires_ns > now_ns);
        let Some(batch) = fresh else {
            if batch.is_some() {
                self.counters.stale_ticks += 1;
            }
            let active = self
                .limbs
                .iter()
                .flatten()
                .any(|l| l.state == LimbState::Active);
            if active {
                self.silent += 1;
                if self.silent >= self.timing.silent_ticks {
                    self.stop_all(StopReason::ControlSilent, now_ns);
                }
            }
            return None;
        };
        self.silent = 0;
        // Check the whole batch before sending any of it.
        for (slot, frame) in batch.frames().iter().enumerate() {
            let Some(frame) = frame else { continue };
            let Some(drive) = self.drives.get(slot).copied().flatten() else {
                self.stop_all(StopReason::BadBatch { slot }, now_ns);
                return None;
            };
            let Some((kind, target)) = echo_of(frame) else {
                self.stop_all(StopReason::BadBatch { slot }, now_ns);
                return None;
            };
            if target != drive.device || !batch_may_carry(kind) {
                self.stop_all(StopReason::BadBatch { slot }, now_ns);
                return None;
            }
        }
        for (slot, frame) in batch.frames().iter().enumerate() {
            let (Some(frame), Some(drive)) = (frame, self.drives.get(slot).copied().flatten())
            else {
                continue;
            };
            let stale = drive
                .fresh_ns
                .is_none_or(|at| now_ns.saturating_sub(at) > self.timing.feedback_limit_ns);
            if matches!(echo_of(frame), Some((EchoKind::Mit, _))) && stale {
                self.stop_limb_now(drive.limb, StopReason::ExpiredFeedback { slot }, now_ns);
            }
        }
        Some(*batch)
    }

    /// The batch's frames for limbs still idle or active; those for a stopping or stopped limb are dropped and counted.
    fn push_commands(&mut self, batch: &CommandBatch) {
        for (slot, frame) in batch.frames().iter().enumerate() {
            let (Some(frame), Some(drive)) = (frame, self.drives.get(slot).copied().flatten())
            else {
                continue;
            };
            let running = self
                .limbs
                .get(drive.limb)
                .copied()
                .flatten()
                .is_some_and(|l| l.state.takes_commands());
            if !running {
                self.counters.refused_frames += 1;
                continue;
            }
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

    /// What became of send `index` of this tick's list, written at `sent_ns`. A command's status window opens only if
    /// the socket took it.
    pub fn sent(&mut self, index: usize, outcome: SendOutcome, sent_ns: u64) {
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
        let expects_status = matches!(
            kind,
            Some(
                EchoKind::Mit | EchoKind::Enable | EchoKind::Disable | EchoKind::ParamWrite { .. }
            )
        );
        let deadline_ns = self.scheduled_ns.saturating_add(self.timing.collect_ns);
        let tick = self.tick;
        let quiet_after_disable_ns = self.timing.stop_confirm_ns;
        let Some(d) = self.drives.get_mut(send.slot).and_then(Option::as_mut) else {
            return;
        };
        d.last_sent_ns = Some(sent_ns);
        let in_silence = d.phase == Phase::Enabling
            || d.disabled_ns
                .is_some_and(|at| sent_ns.saturating_sub(at) < quiet_after_disable_ns);
        if matches!(kind, Some(EchoKind::Enable)) {
            if d.phase == Phase::Off {
                d.phase = Phase::Enabling;
            }
        } else if matches!(kind, Some(EchoKind::Disable)) {
            // Disabled on purpose: its Reset reply is no surprise.
            d.phase = Phase::Off;
            d.disabled_ns = Some(sent_ns);
        }
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
                counts_missed: !in_silence
                    && !matches!(kind, Some(EchoKind::Enable | EchoKind::Disable)),
                reply: Reply::Waiting,
                counted: false,
            });
        }
        let limb = d.limb;
        if matches!(kind, Some(EchoKind::Mit | EchoKind::Enable))
            && let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut)
            && l.state == LimbState::Idle
        {
            l.state = LimbState::Active;
        }
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
                d.misses = d.misses.saturating_add(1);
                self.counters.unanswered += 1;
            }
        }
        self.settle_stops(now_ns);
        let healthy = self.healthy();
        let mut limbs = [None; MAX_DRIVES];
        for (view, limb) in limbs.iter_mut().zip(&self.limbs) {
            *view = limb.map(|l| LimbView {
                state: l.state,
                stop: l.stop,
                generation: l.generation,
            });
        }
        let mut snap = Snapshot::new(tick, self.bus_error, healthy, self.counters, &limbs);
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d {
                snap.set(
                    slot,
                    DriveView {
                        device: d.device,
                        limb: d.limb,
                        observed: d.observed,
                        fresh_ns: d.fresh_ns,
                        answered: d.answered,
                        fault_seen: d.fault_seen,
                        misses: d.misses,
                        last_echo: d.last_echo,
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
