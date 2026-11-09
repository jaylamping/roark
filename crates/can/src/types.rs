//! What crosses the bus thread's seams: command batches in, snapshots out (slow requests and results are in `slow`), all
//! fixed-size and `Copy` so the rings never
//! allocate (rust.md section 6).

use robstride::{DeviceId, EchoKind, Frame, Status};

use crate::error_frame::BusError;

/// The most drives one bus holds. The skeleton puts at most seven on a bus; a bus with more is refused at startup.
pub const MAX_DRIVES: usize = 8;
/// The most frames one tick sends: a command per drive, or a Disable and a reporting-off per drive while stopping.
pub const MAX_SENDS: usize = 2 * MAX_DRIVES;

/// The drives' own command timeout: three periods of feedback must fit inside it (PLAN.md item 3 Timing).
pub const DRIVE_TIMEOUT_NS: u64 = 50_000_000;

/// The tick's timing, in nanoseconds on the monotonic clock (`u64`, not `Duration`: the bus tick's exception,
/// units-and-frames.md section 5). [`BusTick::new`](crate::BusTick::new) refuses timing that
/// [`Timing::check`] doesn't pass.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Timing {
    /// One tick.
    pub period_ns: u64,
    /// How late after its scheduled start a tick may still send a command. Waking later is a missed deadline and a
    /// stop. A quarter period by default: provisional, to be tuned on the real adapter (PLAN step 8).
    pub send_window_ns: u64,
    /// When the tick stops collecting replies, from its scheduled start (about 60 % of the period, PLAN.md item 3).
    pub collect_ns: u64,
    /// The oldest a drive's last fresh status may be when motion is sent to it (three periods: 12 ms at 250 Hz, PLAN.md
    /// item 6 Silence row).
    pub feedback_limit_ns: u64,
    /// How long a stop waits for each drive's Disable to be confirmed and its reporting-off sent before it records the
    /// rest as unconfirmed, and how long after any Disable a drive's missed replies aren't counted (100 ms, PLAN.md
    /// item 2 Silence windows).
    pub stop_confirm_ns: u64,
    /// How long a drive drops frames after a Disable; its reporting-off waits this long after its confirmation, and a
    /// drive that never confirms gets none (post-Disable silences up to 48.7 ms measured, PLAN.md item 2).
    pub disable_silence_ns: u64,
    /// Ticks without a fresh batch that stop an active bus (PLAN.md item 3: two). Counted with every limb idle too:
    /// past it, slow requests are refused.
    pub silent_ticks: u32,
    /// Consecutive commands a drive may leave unanswered by the collect deadline before its limb stops (PLAN.md item 6
    /// Silence row: three).
    pub silence_misses: u32,
    /// How long a slow request's reply may take: one goes only if it is sent this long before the next tick starts, so
    /// the next drain reads its reply. A quarter period by default: provisional, to be measured on the real adapter
    /// (PLAN step 8).
    pub slow_reply_ns: u64,
}

impl Timing {
    /// The defaults at `hz` ticks a second (250 by default, PLAN.md item 3), the period rounded up to a whole
    /// nanosecond so the rate is never above `hz`. A rate [`Self::check`] refuses (0, or below 61 Hz, where three
    /// periods reach the drives' timeout) gives timing it refuses.
    #[must_use]
    pub const fn at_hz(hz: u64) -> Self {
        let period_ns = match hz {
            0 => 0,
            hz => 1_000_000_000_u64.div_ceil(hz),
        };
        Self {
            period_ns,
            send_window_ns: period_ns / 4,
            collect_ns: period_ns * 6 / 10,
            feedback_limit_ns: 3 * period_ns,
            stop_confirm_ns: 100_000_000,
            disable_silence_ns: 50_000_000,
            silent_ticks: 2,
            silence_misses: 3,
            slow_reply_ns: period_ns / 4,
        }
    }

    /// Whether this timing keeps the tick's promises: a send window inside the collect window inside the period, at
    /// least a period of feedback but less than the drives' timeout, a stop window that fits the post-Disable silence and a
    /// tick to send reporting off after it, at least one silent tick and one miss, and a slow reply window that fits
    /// between the collect deadline and the next tick.
    ///
    /// # Errors
    /// The first rule it breaks.
    pub const fn check(&self) -> Result<(), TimingError> {
        let (period_ns, send_window_ns, collect_ns) =
            (self.period_ns, self.send_window_ns, self.collect_ns);
        if period_ns == 0 {
            Err(TimingError::NoPeriod)
        } else if send_window_ns == 0 || send_window_ns > collect_ns {
            Err(TimingError::SendWindow {
                send_window_ns,
                collect_ns,
            })
        } else if collect_ns >= period_ns {
            Err(TimingError::Collect {
                collect_ns,
                period_ns,
            })
        } else if self.feedback_limit_ns < period_ns || self.feedback_limit_ns >= DRIVE_TIMEOUT_NS {
            Err(TimingError::FeedbackLimit {
                feedback_limit_ns: self.feedback_limit_ns,
                period_ns,
            })
        } else if self.stop_confirm_ns < self.disable_silence_ns.saturating_add(period_ns) {
            Err(TimingError::StopWindow {
                stop_confirm_ns: self.stop_confirm_ns,
                disable_silence_ns: self.disable_silence_ns,
                period_ns,
            })
        } else if self.silent_ticks == 0 {
            Err(TimingError::NoSilentTicks)
        } else if self.silence_misses == 0 {
            Err(TimingError::NoSilenceMisses)
        } else if self.slow_reply_ns == 0
            || collect_ns.saturating_add(self.slow_reply_ns) > period_ns
        {
            Err(TimingError::SlowReply {
                slow_reply_ns: self.slow_reply_ns,
                collect_ns,
                period_ns,
            })
        } else {
            Ok(())
        }
    }
}

/// The rule a [`Timing`] breaks, with the values that break it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum TimingError {
    /// The period is zero (a rate of 0 Hz).
    #[error("the period is zero")]
    NoPeriod,
    /// The send window is zero or ends after the collect deadline.
    #[error(
        "send window {send_window_ns} ns must be non-zero and end by the collect deadline, {collect_ns} ns"
    )]
    SendWindow {
        /// The send window.
        send_window_ns: u64,
        /// The collect deadline.
        collect_ns: u64,
    },
    /// The collect deadline isn't inside the period.
    #[error("collect deadline {collect_ns} ns must fall inside the period, {period_ns} ns")]
    Collect {
        /// The collect deadline.
        collect_ns: u64,
        /// The period.
        period_ns: u64,
    },
    /// The feedback limit is under a period, or reaches the drives' timeout.
    #[error(
        "feedback limit {feedback_limit_ns} ns must be at least the period, {period_ns} ns, and under the drives' \
         {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    FeedbackLimit {
        /// The feedback limit.
        feedback_limit_ns: u64,
        /// The period.
        period_ns: u64,
    },
    /// The stop window can't fit the post-Disable silence and a tick to send reporting off after it.
    #[error(
        "stop window {stop_confirm_ns} ns must outlast the post-Disable silence, {disable_silence_ns} ns, by a period, \
         {period_ns} ns"
    )]
    StopWindow {
        /// The stop window.
        stop_confirm_ns: u64,
        /// The post-Disable silence.
        disable_silence_ns: u64,
        /// The period.
        period_ns: u64,
    },
    /// `silent_ticks` is zero.
    #[error("silent_ticks must be at least 1")]
    NoSilentTicks,
    /// `silence_misses` is zero.
    #[error("silence_misses must be at least 1")]
    NoSilenceMisses,
    /// The slow reply window is zero or doesn't fit between the collect deadline and the next tick, so no slow request
    /// could go.
    #[error(
        "slow_reply_ns {slow_reply_ns} must be above zero and fit between collect_ns {collect_ns} and the period {period_ns}"
    )]
    SlowReply {
        /// The slow reply window.
        slow_reply_ns: u64,
        /// The collect deadline.
        collect_ns: u64,
        /// The period.
        period_ns: u64,
    },
}

/// One tick's commands from control: at most one encoded frame per drive slot (the drive's place in the bus's table).
/// Frames come only from `robstride::encode`, which builds only allowlisted frames. A batch may carry only motion,
/// Enable, Disable, active reporting off and the `run_mode` = MIT write; the tick refuses anything else as a bad batch,
/// since Set Zero, set-ID and other parameter traffic need sequencing a per-tick batch can't give (PLAN.md item 2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CommandBatch {
    /// The tick it is for. A batch for any other tick is stale and never sent.
    pub tick: u64,
    /// After this monotonic time it is expired and never sent.
    pub expires_ns: u64,
    frames: [Option<Frame>; MAX_DRIVES],
}

impl CommandBatch {
    /// An empty batch: a fresh batch with no frames still tells the bus that control is alive.
    #[must_use]
    pub const fn new(tick: u64, expires_ns: u64) -> Self {
        Self {
            tick,
            expires_ns,
            frames: [None; MAX_DRIVES],
        }
    }

    /// Put `frame` in `slot`; false if the slot is out of range.
    pub fn set(&mut self, slot: usize, frame: Frame) -> bool {
        self.frames
            .get_mut(slot)
            .map(|f| *f = Some(frame))
            .is_some()
    }

    pub(crate) fn frames(&self) -> &[Option<Frame>; MAX_DRIVES] {
        &self.frames
    }
}

/// How the shell's drain before a send ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Drain {
    /// It emptied the socket: what is read from here on came after the backlog.
    Emptied,
    /// It emptied the socket but read more frames than the shell may before a send: the bus stops, since what it said
    /// can't be known in time.
    Backlog,
    /// It gave up with frames still queued: the bus stops, and until a drain empties the socket its statuses may
    /// predate the sends. They still show each drive's mode and faults, but answer nothing and confirm nothing.
    Unemptied,
}

/// What a planned send is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SendKind {
    /// A frame from control's batch.
    Command,
    /// Disable (type 4) from a stop.
    Disable,
    /// Active reporting off (type 24) from a stop.
    ReportingOff,
}

/// One frame the tick will send.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Send {
    /// The drive slot it is for.
    pub slot: usize,
    /// What it is.
    pub kind: SendKind,
    /// The frame.
    pub frame: Frame,
    /// Whether it is dropped once the tick's send window has passed. Commands are; a Disable or active reporting off
    /// never is, whoever planned it, since late it is still the right frame (can.md section 2).
    pub expires: bool,
}

/// What became of a send.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SendOutcome {
    /// The socket took it. On real CAN that is submission to the kernel, not transmission: the kernel and adapter queues
    /// don't expire frames (can.md section 2).
    Sent,
    /// `ENOBUFS` or `EAGAIN`: dropped and counted, never retried.
    QueueFull,
    /// A send whose window had passed before the write: dropped and counted. Only sends that [`Send::expires`] are.
    Expired,
    /// Any other write error.
    Failed,
}

/// The frames one tick sends, in order.
#[derive(Clone, Copy, Debug)]
pub struct SendList {
    sends: [Option<Send>; MAX_SENDS],
    len: usize,
}

impl SendList {
    pub(crate) const EMPTY: Self = Self {
        sends: [None; MAX_SENDS],
        len: 0,
    };

    pub(crate) fn push(&mut self, send: Send) {
        if let Some(slot) = self.sends.get_mut(self.len) {
            *slot = Some(send);
            self.len += 1;
        }
    }

    pub(crate) fn get(&self, index: usize) -> Option<Send> {
        self.sends.get(index).copied().flatten()
    }

    /// The sends, in the order they must go out.
    pub fn iter(&self) -> impl Iterator<Item = Send> + '_ {
        self.sends.iter().take(self.len).flatten().copied()
    }

    /// How many.
    #[must_use]
    pub fn len(&self) -> usize {
        self.len
    }

    /// Whether the tick sends nothing.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

/// One drive on a bus and the limb it belongs to: the limb's index among the skeleton's limbs on this bus, from 0.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BusDrive {
    /// The drive.
    pub device: DeviceId,
    /// Its limb on this bus, below [`MAX_DRIVES`].
    pub limb: usize,
}

/// Where one limb on a bus is. Each limb runs and stops on its own; a stop of the whole bus stops every limb.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimbState {
    /// Nothing enabled or commanded since start or the last re-arm; no batches needed, though slow requests are refused
    /// while control is silent.
    Idle,
    /// An Enable or MIT frame to one of its drives was sent, so the bus needs a fresh batch every tick.
    Active,
    /// A stop is in progress: Disable to every unconfirmed drive each tick, its frames in batches refused.
    Stopping {
        /// When the stop began, monotonic.
        since_ns: u64,
    },
    /// Stopped, latched: only an operator's clear re-arms it ([`BusTick::rearm`](crate::BusTick::rearm)).
    Stopped,
}

/// One limb in a snapshot.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LimbView {
    /// Where it is.
    pub state: LimbState,
    /// Why it stopped, if it has since its last re-arm.
    pub stop: Option<StopReason>,
    /// How many times it has been re-armed: fault history and stop outcomes count from the last one.
    pub generation: u32,
}

/// The last of this host's frames to a drive read back from the socket.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EchoSeen {
    /// What it was.
    pub kind: EchoKind,
    /// When it was read, monotonic.
    pub read_ns: u64,
}

/// Why a limb stopped. `ExpiredFeedback`, `DriveFault`, `DriveMode` and `DriveSilent` stop only that drive's limb;
/// `Requested` stops the scope it was asked for (`BusTick::stop_limb` one limb, `BusTick::request_stop` the bus); the
/// rest, `BadBatch` included, stop every limb on the bus.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopReason {
    /// No fresh batch for `Timing::silent_ticks` ticks while a limb was active (PLAN.md item 3).
    ControlSilent,
    /// The thread woke after its send window (PLAN.md item 3).
    LateWake,
    /// A batch carried motion for a drive whose last fresh status was too old.
    ExpiredFeedback {
        /// That drive's slot.
        slot: usize,
    },
    /// A drive of an idle or active limb reported a fault, read before the send (PLAN.md item 6 Faults row).
    DriveFault {
        /// That drive's slot.
        slot: usize,
    },
    /// A drive seen in Run after its Enable later reported another mode with no Disable from this host (PLAN.md item 6
    /// States). A drive this host never enabled isn't watched here: preflight refuses one found already in Run.
    DriveMode {
        /// That drive's slot.
        slot: usize,
    },
    /// A drive left `Timing::silence_misses` commands in a row unanswered (PLAN.md item 6 Silence row).
    DriveSilent {
        /// That drive's slot.
        slot: usize,
    },
    /// A batch's frame didn't target its slot's drive, sat in a slot with no drive, or was a kind a batch may not carry
    /// ([`CommandBatch`]): a bug upstream.
    BadBatch {
        /// The slot.
        slot: usize,
    },
    /// More frames were queued before the send than the tick may read.
    Backlog,
    /// Asked for by the runtime or a test, for one limb or the whole bus.
    Requested,
    /// The bus itself failed.
    Bus(BusError),
}

/// What a stop achieved for one drive (PLAN.md item 2 Stop).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum StopOutcome {
    /// No stop has happened.
    #[default]
    None,
    /// A stop happened but no Disable to this drive was taken by the socket (also every drive of a bus whose error
    /// left nothing to send on).
    NeverSent,
    /// Disable was sent; no Reset-mode status read after it was counted (a read that may predate it, after a drain that
    /// left frames queued, confirms nothing).
    Sent,
    /// A Reset-mode status was read after a sent Disable.
    Confirmed,
}

/// A status as read, with the monotonic time the bus thread read it.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Observed {
    /// The status (or report) frame.
    pub status: Status,
    /// When it was read.
    pub read_ns: u64,
}

/// One drive in a snapshot.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DriveView {
    /// The drive.
    pub device: DeviceId,
    /// Its limb on this bus.
    pub limb: usize,
    /// The last status or report read from it, answer or not: its mode and fault bits are never filtered out.
    pub observed: Option<Observed>,
    /// When its last fresh status was read: the first status after a command the socket took. Freshness, not
    /// acknowledgement: the protocol has no sequence numbers, so which command a status answers can't be proven. Read
    /// time, not arrival: it can trail the kernel's receipt by up to period - collect + send window
    /// (units-and-frames.md section 5).
    pub fresh_ns: Option<u64>,
    /// Whether it answered this tick's command by the collect deadline.
    pub answered: bool,
    /// Any fault bit or fault report seen since start or its limb's last re-arm. Sticky until then.
    pub fault_seen: bool,
    /// Commands in a row it left unanswered by the collect deadline.
    pub misses: u32,
    /// The last of this host's frames to it read back from the socket: the evidence a frame reached the controller
    /// (never that it reached the drive).
    pub last_echo: Option<EchoSeen>,
    /// What the current or last stop achieved for it.
    pub stop: StopOutcome,
    /// Whether the current or last stop's active reporting off was taken by the socket.
    pub reporting_off_sent: bool,
}

/// Per-bus counts since start.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Counters {
    /// Commands the socket took that got no status by the collect deadline. Not Enable or Disable: a drive may take
    /// 10 ms to reach Run, and goes silent after a Disable (PLAN.md item 2 Silence windows).
    pub unanswered: u64,
    /// Statuses for a command after its tick's collect deadline.
    pub late: u64,
    /// A second status for one command within its tick.
    pub duplicate: u64,
    /// Frames from this bus's drives that answer nothing: a status with no command outstanding, after the command was
    /// answered in an earlier tick, or read when it may predate the send; a parameter or identity reply with no slow
    /// request waiting for it.
    pub unsolicited: u64,
    /// Frames from a device this bus doesn't own.
    pub unexpected: u64,
    /// Host frames sent by someone other than this socket (PLAN.md item 3: only the realtime process transmits).
    pub foreign_host: u64,
    /// This socket's own frames read back.
    pub echoes: u64,
    /// Frames the codec can't read.
    pub undecodable: u64,
    /// Error frames.
    pub error_frames: u64,
    /// Sends the socket refused (`ENOBUFS`, `EAGAIN`, other errors).
    pub tx_dropped: u64,
    /// Sends dropped because their window had passed.
    pub tx_expired: u64,
    /// Ticks handed a stale or expired batch.
    pub stale_ticks: u64,
    /// Batches refused because every limb was stopping or stopped.
    pub refused_batches: u64,
    /// Frames of a fresh batch dropped because their limb was stopping or stopped.
    pub refused_frames: u64,
    /// Ticks the thread woke for after their send window.
    pub missed_deadlines: u64,
    /// The socket's overflow counter (`SO_RXQ_OVFL`), the last value seen.
    pub kernel_drops: u32,
    /// Snapshots control's ring was too full to take.
    pub snapshots_dropped: u64,
    /// Slow results control's ring was too full to take.
    pub slow_results_dropped: u64,
}

/// The bus at the end of a tick, for control and the safety layer.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Snapshot {
    /// The tick.
    pub tick: u64,
    /// The first bus error that latched (bus-off, interface down or gone), even if the bus was already stopping.
    pub bus_error: Option<BusError>,
    /// No latched bus error and not error-passive: the recording's `valid` flag (logging.md section 8.2).
    pub healthy: bool,
    /// Counts since start.
    pub counters: Counters,
    limbs: [Option<LimbView>; MAX_DRIVES],
    drives: [Option<DriveView>; MAX_DRIVES],
}

impl Snapshot {
    pub(crate) fn new(
        tick: u64,
        bus_error: Option<BusError>,
        healthy: bool,
        counters: Counters,
        limbs: &[Option<LimbView>; MAX_DRIVES],
    ) -> Self {
        Self {
            tick,
            bus_error,
            healthy,
            counters,
            limbs: *limbs,
            drives: [None; MAX_DRIVES],
        }
    }

    /// Limb `limb` on this bus.
    #[must_use]
    pub fn limb(&self, limb: usize) -> Option<&LimbView> {
        self.limbs.get(limb).and_then(Option::as_ref)
    }

    /// Every limb on this bus, with its index.
    pub fn limbs(&self) -> impl Iterator<Item = (usize, &LimbView)> + '_ {
        self.limbs
            .iter()
            .enumerate()
            .filter_map(|(i, l)| l.as_ref().map(|l| (i, l)))
    }

    /// Whether every limb is idle or stopped: nothing on this bus is running or still stopping.
    #[must_use]
    pub fn settled(&self) -> bool {
        self.limbs()
            .all(|(_, l)| matches!(l.state, LimbState::Idle | LimbState::Stopped))
    }

    /// Whether every limb is stopped.
    #[must_use]
    pub fn stopped(&self) -> bool {
        self.limbs().all(|(_, l)| l.state == LimbState::Stopped)
    }

    pub(crate) fn set(&mut self, slot: usize, view: DriveView) {
        if let Some(d) = self.drives.get_mut(slot) {
            *d = Some(view);
        }
    }

    /// Slot `slot`'s drive.
    #[must_use]
    pub fn drive(&self, slot: usize) -> Option<&DriveView> {
        self.drives.get(slot).and_then(Option::as_ref)
    }

    /// Every drive, in slot order.
    pub fn drives(&self) -> impl Iterator<Item = &DriveView> + '_ {
        self.drives.iter().flatten()
    }
}

/// A bus the tick can't run.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ConfigError {
    /// More drives than [`MAX_DRIVES`].
    #[error("{0} drives on one bus; the bus table holds {MAX_DRIVES}")]
    TooManyDrives(usize),
    /// A drive's limb index is past the table.
    #[error(
        "the drive in slot {slot} is in limb {limb}; limbs on one bus are numbered below {MAX_DRIVES}"
    )]
    LimbOutOfRange {
        /// The drive's slot.
        slot: usize,
        /// The limb it named.
        limb: usize,
    },
    /// Timing [`Timing::check`] refuses.
    #[error("bad timing: {0}")]
    Timing(TimingError),
}

/// A limb index that isn't on this bus.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("limb {0} isn't on this bus")]
pub struct NoSuchLimb(pub usize);

/// Why a limb can't be re-armed yet.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum RearmRefused {
    /// No drive on this bus is in that limb.
    #[error("no limb {0} on this bus")]
    NoSuchLimb(usize),
    /// The bus itself failed; only a new bus thread and socket bring it back.
    #[error("the bus failed ({0:?}); it comes back only with a new bus thread")]
    BusFailed(BusError),
    /// The limb is running or still stopping: only a stopped limb is re-armed.
    #[error("limb {0} isn't stopped")]
    NotStopped(usize),
    /// A drive is neither confirmed in Reset nor silent long enough to have timed out.
    #[error(
        "the drive in slot {slot} isn't confirmed disabled and hasn't been quiet past its timeout"
    )]
    DriveNotQuiet {
        /// That drive's slot.
        slot: usize,
    },
}
