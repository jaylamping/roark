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
use robstride::{
    DecodeError, DeviceId, EchoKind, Frame, Inbound, Mode, Param, ParamValue, RunMode, decode,
};

use crate::error_frame::BusError;
use crate::timing::{ENABLE_TO_RUN_NS, Timing};
use crate::types::{
    BusDrive, CommandBatch, ConfigError, Counters, Drain, DriveView, EchoSeen, LimbState, LimbView,
    MAX_DRIVES, NoSuchLimb, Observed, Send, SendKind, SendList, SendOutcome, Snapshot, StopOutcome,
    StopReason,
};

/// A command the socket took, waiting for its status.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Outstanding {
    pub(crate) tick: u64,
    pub(crate) deadline_ns: u64,
    /// A stop's Disable: a Reset status after it confirms the stop.
    pub(crate) stop_disable: bool,
    /// Whether a missing status counts as unanswered: not for an Enable or a Disable, and not inside PLAN.md item 2's
    /// Silence windows, which the drive's [`Phase`] holds (`Off`; `Disabled` until [`Timing::stop_confirm_ns`] has
    /// passed; `Enabling` until [`ENABLE_TO_RUN_NS`] has).
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
    pub(crate) fresh_status: Option<Observed>,
    pub(crate) outstanding: Option<Outstanding>,
    pub(crate) answered: bool,
    pub(crate) fault_seen: bool,
    pub(crate) misses: u32,
    pub(crate) phase: Phase,
    /// When the socket last took a frame to it, as the shell read the clock after the write.
    pub(crate) last_sent_ns: Option<u64>,
    pub(crate) last_echo: Option<EchoSeen>,
    pub(crate) stop: DriveStop,
}

/// Where the current or last stop is with one drive (PLAN.md item 2 Stop). One value, so a confirmation and its
/// reporting off are set and withdrawn together.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum DriveStop {
    /// No stop since start or the limb's last re-arm.
    None,
    /// A stop began and the socket has taken no Disable to the drive yet (or the bus was lost).
    NeverSent,
    /// The socket took a Disable; no Reset read inside the reply allowance stands for it (none came, or the drive
    /// showed another mode after it, [`DriveState::note_mode`]).
    Sent,
    /// A Reset read at `at_ns`, inside the stop's reply allowance ([`Timing::stop_replies_ns`]), confirmed it.
    Confirmed {
        /// When the confirming Reset was read.
        at_ns: u64,
        /// Its reporting off.
        off: Off,
    },
}

impl DriveStop {
    /// What the snapshot says of it.
    pub(crate) const fn outcome(self) -> StopOutcome {
        match self {
            Self::None => StopOutcome::None,
            Self::NeverSent => StopOutcome::NeverSent,
            Self::Sent => StopOutcome::Sent,
            Self::Confirmed { .. } => StopOutcome::Confirmed,
        }
    }

    pub(crate) const fn confirmed(self) -> bool {
        matches!(self, Self::Confirmed { .. })
    }
}

/// Where a stop's reporting off to one drive is. It is planned every tick from its due time until the socket takes it
/// or the stop ends ([`BusTick::stop_over`]), so whether it was tried doesn't matter, only whether it was taken.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Off {
    /// Not taken by the socket yet.
    Unsent,
    /// Taken by the socket.
    Sent,
}

impl DriveState {
    /// What a status header's mode says about the drive's run, from a status, a report or a version reply alike. Run
    /// after an Enable is the drive running, counted only from an ordered read while its limb is active; any other mode
    /// after running, without a Disable from this host, is latched as having left Run; Reset from an ordered read after a
    /// Disable confirms the drive off. A mode other than the fresh status's supersedes it (`fresh_status` goes), the
    /// age of the last fresh reply (`fresh_ns`) staying. Any mode but Reset withdraws a stop's confirmation, whatever
    /// the read order: frames from one drive are read in the order it sent them, so the drive left Reset after the
    /// status that confirmed it and isn't known disabled any more.
    pub(crate) fn note_mode(&mut self, mode: Mode, limb_active: bool, unordered: bool) {
        self.fresh_status = self.fresh_status.filter(|f| f.status.header.mode == mode);
        if mode != Mode::Reset && self.stop.confirmed() {
            self.stop = DriveStop::Sent;
        }
        match self.phase {
            Phase::Enabling { .. } if mode == Mode::Run && limb_active && !unordered => {
                self.phase = Phase::Running;
            }
            Phase::Running if mode != Mode::Run => self.phase = Phase::LeftRun,
            Phase::Disabled { .. } if mode == Mode::Reset && !unordered => self.phase = Phase::Off,
            Phase::Off
            | Phase::Disabled { .. }
            | Phase::Enabling { .. }
            | Phase::Running
            | Phase::LeftRun => {}
        }
    }
}

/// Where a drive is in this host's Enable and Disable: what its silence means.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Phase {
    /// Never enabled since start or the limb's last clear, or reported Reset after this host's Disable. A later Disable
    /// leaves it here; what that assumes of the read order is at [`BusTick::drained`].
    Off,
    /// A Disable was taken at `since_ns` while the drive was enabling or enabled, and no Reset has been read since. Its
    /// misses count again once [`Timing::stop_confirm_ns`] has passed (PLAN.md item 2 Silence windows).
    Disabled {
        /// When the socket took the Disable.
        since_ns: u64,
    },
    /// An Enable was taken at `since_ns`; no Run status since.
    Enabling {
        /// When the socket took the Enable.
        since_ns: u64,
    },
    /// It reported Run after that Enable.
    Running,
    /// It reported another mode after running, without a Disable from this host: its limb stops before the next send.
    /// Latched when the status is read, so a later status can't hide it.
    LeftRun,
}

impl Phase {
    /// The phase after the socket took a frame of `kind` at `sent_ns`, for PLAN.md item 2's Silence windows: an Enable
    /// to a drive not already enabling or enabled starts its enable-to-Run window; a Disable to an enabling or enabled
    /// drive starts its post-Disable window. Any other send, a Disable sent again or one to a drive in `Off` included,
    /// leaves the phase as it is, so Disables sent every tick can't hold misses off.
    pub(crate) const fn after_send(self, kind: Option<EchoKind>, sent_ns: u64) -> Self {
        match kind {
            Some(EchoKind::Enable) => match self {
                Self::Off | Self::Disabled { .. } => Self::Enabling { since_ns: sent_ns },
                Self::Enabling { .. } | Self::Running | Self::LeftRun => self,
            },
            Some(EchoKind::Disable) => match self {
                Self::Enabling { .. } | Self::Running | Self::LeftRun => {
                    Self::Disabled { since_ns: sent_ns }
                }
                Self::Off | Self::Disabled { .. } => self,
            },
            Some(
                EchoKind::Mit
                | EchoKind::SetZero
                | EchoKind::SetId { .. }
                | EchoKind::ParamRead(_)
                | EchoKind::ParamWrite { .. }
                | EchoKind::Reporting(_)
                | EchoKind::GetId
                | EchoKind::VersionQuery
                | EchoKind::FaultClear,
            )
            | None => self,
        }
    }
}

/// How a batch for this tick was taken.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Taken {
    /// Unexpired: all of it goes, but for what a held tick holds back.
    Fresh,
    /// Past its expiry: counted stale, and only its Disables and reporting off go.
    Expired,
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
    /// The last drain read past its limit or left frames queued: what it said can't be known in time.
    backlog: bool,
    /// Ticks that went by without running since the last `begin` ([`Self::skipped`]).
    skipped_since: u64,
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
                fresh_status: None,
                outstanding: None,
                answered: false,
                fault_seen: false,
                misses: 0,
                phase: Phase::Off,
                last_sent_ns: None,
                last_echo: None,
                stop: DriveStop::None,
            });
        }
        Ok(Self {
            timing,
            drives: table,
            limbs,
            pending_stop: None,
            backlog: false,
            skipped_since: 0,
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

    /// Whether a bus error has latched (bus-off, or the socket failed): there is nothing to send on.
    #[must_use]
    pub(crate) fn bus_lost(&self) -> bool {
        self.bus_error.is_some()
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
        l.pending.get_or_insert(StopReason::LimbRequested);
        Ok(())
    }

    /// How this tick's drain ended: call it after the drain (its frames already fed to [`Self::on_frame`]), before
    /// [`Self::begin`]. A backlog stops every active limb at this tick's start and holds the tick for every idle one,
    /// which clears the freshness this drain stamped (both in [`Self::begin`]). Reads stay unordered from a drain that
    /// left frames queued until a drain empties the socket.
    ///
    /// The frames of the drain itself are ordered unless an earlier drain left the socket unemptied: the socket is a
    /// queue, and the last drain emptied it before the last tick's sends, so whatever this drain reads came after them.
    /// Only what a drain leaves queued may predate the next sends, which is what `Unemptied` marks.
    ///
    /// That order says when a frame was read, not when the drive sent it, and the `Off` rule rests on it: a Reset read
    /// in order after a Disable puts the drive in `Off`, where a later Disable leaves it, and nothing sent to it counts
    /// as missed until it is enabled again. A drive wrongly `Off` (a Reset it sent before a Disable that was lost, read
    /// after that Disable; or a drive another sender runs) is then never counted silent until its next Enable. Motion
    /// stays covered: an MIT frame to a drive whose fresh status is older than the feedback limit stops its limb, and
    /// the drive's own timeout applies. Whether a real adapter can deliver a Reset that late is checked on it (PLAN
    /// step 8).
    pub fn drained(&mut self, drain: Drain) {
        match drain {
            Drain::Emptied => self.unordered = false,
            Drain::Backlog => {
                self.backlog = true;
                self.unordered = false;
            }
            Drain::Unemptied => {
                self.backlog = true;
                self.unordered = true;
            }
        }
    }

    /// The socket failed with `error`: every limb latches stopped, whatever the error, since a socket that can't send
    /// can't stop the drives either (fail closed, safety.md section 3). Every socket read or write failure other than a
    /// full queue comes here (PLAN.md item 6 Bus-off row); a failed write is also reported to [`Self::sent`], which
    /// only counts it. There is no bus to send a stop on; the drives time out on their own (`canTimeout`). Error frames
    /// come through [`Self::on_frame`] instead, where only bus-off latches.
    pub fn lost_bus(&mut self, error: BusError) {
        self.latch(error);
    }

    /// The socket's overflow counter, the last value the shell saw (`SO_RXQ_OVFL` comes only on frames queued after a
    /// drop, so a frame without it is no news).
    pub fn note_kernel_drops(&mut self, count: u32) {
        self.counters.kernel_drops = count;
    }

    /// `count` ticks went by without running (the thread stalled past them): each a missed deadline (PLAN.md item 3:
    /// missed deadlines are counted, never skipped silently). The next `begin` treats it as a late wake: every active
    /// limb stops, and the tick is held for every idle one (both in [`Self::begin`]).
    pub fn skipped(&mut self, count: u64) {
        if count > 0 {
            self.counters.missed_deadlines += count;
            self.skipped_since += count;
        }
    }

    /// Whether every limb is idle: nothing was ever enabled, or every limb was re-armed.
    #[must_use]
    pub(crate) fn all_idle(&self) -> bool {
        self.limbs
            .iter()
            .flatten()
            .all(|l| l.state == LimbState::Idle)
    }

    /// Whether the bus is healthy now: no latched bus error and not error-passive. The snapshot's `healthy` is this at
    /// `end`.
    #[must_use]
    pub(crate) fn healthy(&self) -> bool {
        self.bus_error.is_none() && !self.error_passive
    }

    /// Control's ring couldn't take `snap`, this tick's snapshot (it was full): counted in `snap`, which the caller
    /// keeps (it may be the last snapshot the bus hands back), and in every later one.
    pub fn snapshot_dropped(&mut self, snap: &mut Snapshot) {
        self.counters.snapshots_dropped += 1;
        snap.counters.snapshots_dropped = self.counters.snapshots_dropped;
    }

    /// Start tick `tick`, scheduled at `scheduled_ns`, woken at `now_ns`, with the newest batch from control. Call after
    /// draining the socket and [`Self::drained`]. Returns the frames to send, in order, stop frames first; report each
    /// with [`Self::sent`]. Each send says whether it expires ([`Send::expires`]): a command goes out only inside the
    /// send window, while a Disable or active reporting off goes out late too, whoever planned it.
    ///
    /// A stop asked for before the tick (the whole bus's or one limb's) is taken first, so it keeps its reason. A backlog
    /// in the drain, a wake past the send window (a missed deadline, counted whatever the limbs are doing) or ticks a
    /// stall slept through ([`Self::skipped`]) stop every active limb. None of them stops an idle limb (nothing enabled
    /// since start or its clear): the tick is **held** for it instead, since an untrusted tick holds an idle limb and
    /// doesn't stop it (PLAN.md item 3). Then, before anything is planned, a drive of an idle or active limb that the
    /// drain or an earlier read showed faulted, out of Run after running, or silent too long stops its limb, so no
    /// command (Enable included) reaches it this tick. On a held tick, in this order:
    ///
    /// 1. The batch is checked as on any tick, against the freshness as the drain left it: a bad batch stops every
    ///    limb, and motion on feedback past the limit stops its limb. Motion on feedback the drain stamped passes the
    ///    check.
    /// 2. Only the batch's Disables and reporting off are planned, which are right late or not; the rest, that motion
    ///    included, is held back unsent (`held_batches`), so nothing is enabled or moved on a tick whose reads can't
    ///    be trusted.
    /// 3. The freshness of every drive in a limb still idle is cleared once, here: the drain read late or past a
    ///    backlog, so the real age of what it stamped can't be bounded. A status read after this tick's sends (a
    ///    Disable it sends opens a reply) counts as fresh again, since the drain emptied the socket before them; after
    ///    a drain that left frames queued ([`Drain::Unemptied`]) nothing counts until one empties it.
    ///
    /// So motion on a later tick to a drive with no fresh status read since is refused as expired feedback, which
    /// stops its limb (PLAN.md item 6 Silence row).
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
        // A stop asked for before this tick began came first, so it keeps its reason over a backlog or a late wake.
        if let Some(reason) = self.pending_stop.take() {
            self.stop_bus(reason, now_ns);
        }
        // Whether a batch is still checked this tick is decided before any one limb stops: a batch for a bus whose
        // only limb stops now is still checked whole, and its frames for that limb are refused one by one.
        let takes_batches = self.any_running();
        self.take_pending_limb_stops(now_ns);
        let backlog = std::mem::take(&mut self.backlog);
        let stalled = std::mem::take(&mut self.skipped_since) > 0;
        let woke_late = now_ns > scheduled_ns.saturating_add(self.timing.send_window_ns);
        if woke_late {
            self.counters.missed_deadlines += 1;
        }
        if backlog {
            self.stop_bus(StopReason::Backlog, now_ns);
        } else if woke_late || stalled {
            self.stop_bus(StopReason::LateWake, now_ns);
        }
        // On a tick whose reads can't be trusted or that woke too late, only the batch's Disables and reporting off go.
        let hold = backlog || woke_late || stalled;
        self.veto(now_ns);
        let accepted = if takes_batches {
            self.check_batch(tick, now_ns, batch)
        } else {
            if batch.is_some() {
                self.counters.refused_batches += 1;
            }
            None
        };
        self.plan_stops(now_ns);
        match accepted {
            Some((batch, Taken::Fresh)) => {
                if self.push_commands(&batch, hold) {
                    self.counters.held_batches += 1;
                }
            }
            // Counted stale already; its Disables and reporting off still go, the rest is dropped.
            Some((batch, Taken::Expired)) => {
                self.push_commands(&batch, true);
            }
            None => {}
        }
        if hold {
            self.forget_fresh();
        }
        self.sends
    }

    /// Step 3 of a held tick ([`Self::begin`]): clear the freshness of every drive in a limb that takes commands, which
    /// by then means one still idle, the active ones having stopped. Stopping and stopped limbs take no motion, and a
    /// re-arm clears theirs.
    fn forget_fresh(&mut self) {
        let limbs = self.limbs;
        for d in self.drives.iter_mut().flatten() {
            let held = limbs
                .get(d.limb)
                .copied()
                .flatten()
                .is_some_and(|l| l.state.takes_commands());
            if held {
                d.fresh_ns = None;
                d.fresh_status = None;
            }
        }
    }

    /// Whether any limb is idle or active, so a batch could carry something.
    fn any_running(&self) -> bool {
        self.limbs
            .iter()
            .flatten()
            .any(|l| l.state.takes_commands())
    }

    /// The batch for this tick if it is sound, and whether it is fresh. A batch for another tick, or past its expiry,
    /// counts the tick stale and toward control's silence; one for another tick is not used at all, while an expired
    /// one for this tick still yields its Disables and reporting off, which are right late or not (can.md section 2).
    /// A frame aimed wrong, in a slot with no drive, or of a kind a batch may not carry is a bug upstream and stops the
    /// whole bus; motion on expired feedback in a fresh batch stops that drive's limb.
    fn check_batch(
        &mut self,
        tick: u64,
        now_ns: u64,
        batch: Option<&CommandBatch>,
    ) -> Option<(CommandBatch, Taken)> {
        let this_tick = batch.filter(|b| b.tick == tick);
        if this_tick.is_some_and(|b| b.expires_ns > now_ns) {
            self.silent = 0;
        } else {
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
        }
        let batch = this_tick?;
        let taken = if batch.expires_ns > now_ns {
            Taken::Fresh
        } else {
            Taken::Expired
        };
        // Check the whole batch before sending any of it.
        for (slot, frame) in batch.frames().iter().enumerate() {
            let Some(frame) = frame else { continue };
            let Some(drive) = self.drives.get(slot).copied().flatten() else {
                self.bad_batch(slot, now_ns);
                return None;
            };
            let Some((kind, target)) = echo_of(frame) else {
                self.bad_batch(slot, now_ns);
                return None;
            };
            if target != drive.device || !batch_may_carry(kind) {
                self.bad_batch(slot, now_ns);
                return None;
            }
        }
        for (slot, frame) in batch.frames().iter().enumerate() {
            let (Some(frame), Some(drive), Taken::Fresh) =
                (frame, self.drives.get(slot).copied().flatten(), taken)
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
        Some((*batch, taken))
    }

    /// A bad batch stops every limb. If this tick's stops already took the last idle or active one, there is nothing left
    /// to stop and no stop records it, so it is counted as refused.
    fn bad_batch(&mut self, slot: usize, now_ns: u64) {
        if !self.any_running() {
            self.counters.refused_batches += 1;
        }
        self.stop_all(StopReason::BadBatch { slot }, now_ns);
    }

    /// The batch's frames for limbs still idle or active; those for a stopping or stopped limb are dropped and counted.
    /// With `hold`, only its Disables and reporting off; returns whether anything else was held back.
    fn push_commands(&mut self, batch: &CommandBatch, hold: bool) -> bool {
        let mut held_back = false;
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
            if hold && !late_ok {
                held_back = true;
                continue;
            }
            self.sends.push(Send {
                slot,
                kind: SendKind::Command,
                frame: *frame,
                expires: !late_ok,
            });
        }
        held_back
    }

    /// What became of send `index` of this tick's list, written at `sent_ns`. A command's status window opens only if
    /// the socket took it. A refused send is only counted: [`SendOutcome::Failed`] never latches, so a socket write
    /// failure other than a full queue must also go to [`Self::lost_bus`].
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
        let quiet_ns = self.timing.stop_confirm_ns;
        let tick = self.tick;
        let Some(d) = self.drives.get_mut(send.slot).and_then(Option::as_mut) else {
            return;
        };
        d.last_sent_ns = Some(sent_ns);
        let counts_missed = match d.phase {
            Phase::Off => false,
            Phase::Disabled { since_ns } => sent_ns.saturating_sub(since_ns) >= quiet_ns,
            Phase::Enabling { since_ns } => sent_ns.saturating_sub(since_ns) >= ENABLE_TO_RUN_NS,
            Phase::Running | Phase::LeftRun => true,
        };
        let phase = d.phase.after_send(kind, sent_ns);
        if matches!(phase, Phase::Enabling { .. }) && !matches!(d.phase, Phase::Enabling { .. }) {
            // A fresh Enable starts the count afresh; until then it stays for the snapshot.
            d.misses = 0;
        }
        d.phase = phase;
        match (send.kind, &mut d.stop) {
            (SendKind::Disable, stop @ DriveStop::NeverSent) => *stop = DriveStop::Sent,
            (SendKind::ReportingOff, DriveStop::Confirmed { off, .. }) => *off = Off::Sent,
            (SendKind::Disable | SendKind::ReportingOff | SendKind::Command, _) => {}
        }
        if expects_status {
            d.outstanding = Some(Outstanding {
                tick,
                deadline_ns,
                stop_disable: send.kind == SendKind::Disable,
                counts_missed: counts_missed
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
                        fresh_status: d.fresh_status,
                        answered: d.answered,
                        fault_seen: d.fault_seen,
                        misses: d.misses,
                        last_echo: d.last_echo,
                        stop: d.stop.outcome(),
                        reporting_off_sent: matches!(
                            d.stop,
                            DriveStop::Confirmed { off: Off::Sent, .. }
                        ),
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
        | Err(
            DecodeError::IdTooWide(_)
            | DecodeError::BadLength { .. }
            | DecodeError::UnknownType { .. }
            | DecodeError::BadDeviceId { .. }
            | DecodeError::ReservedMode { .. }
            | DecodeError::UnknownParam { .. }
            | DecodeError::BadParamValue { .. }
            | DecodeError::UnexpectedData { .. }
            | DecodeError::OtherHost { .. }
            | DecodeError::ForeignType { .. }
            | DecodeError::ForeignWrite { .. },
        ) => None,
    }
}
