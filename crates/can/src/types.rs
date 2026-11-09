//! What crosses the bus thread's seams: command batches in, snapshots out, all fixed-size and `Copy` so the rings never
//! allocate (rust.md section 6).

use robstride::{DeviceId, Frame, Status};

use crate::error_frame::BusError;

/// The most drives one bus holds. The skeleton puts at most seven on a bus; a bus with more is refused at startup.
pub const MAX_DRIVES: usize = 8;
/// The most frames one tick sends: a command per drive, or a Disable and a reporting-off per drive while stopping.
pub const MAX_SENDS: usize = 2 * MAX_DRIVES;

/// The drives' own command timeout: three periods of feedback must fit inside it (PLAN.md item 3 Timing).
pub const DRIVE_TIMEOUT_NS: u64 = 50_000_000;

/// The tick's timing, in nanoseconds on the monotonic clock. [`BusTick::new`](crate::BusTick::new) refuses timing that
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
    /// rest as unconfirmed (100 ms, PLAN.md item 2 Silence windows).
    pub stop_confirm_ns: u64,
    /// How long a drive drops frames after a Disable; its reporting-off waits this long after the confirmation (post-
    /// Disable silences up to 48.7 ms measured, PLAN.md item 2).
    pub disable_silence_ns: u64,
    /// Ticks without a fresh batch that stop an active bus (PLAN.md item 3: two).
    pub silent_ticks: u32,
}

impl Timing {
    /// The defaults at `hz` ticks a second (250 by default, PLAN.md item 3). A rate [`Self::check`] refuses (0, or
    /// below about 61 Hz, where three periods pass the drives' timeout) gives timing it refuses.
    #[must_use]
    pub const fn at_hz(hz: u64) -> Self {
        let period_ns = match 1_000_000_000_u64.checked_div(hz) {
            Some(p) => p,
            None => 0,
        };
        Self {
            period_ns,
            send_window_ns: period_ns / 4,
            collect_ns: period_ns * 6 / 10,
            feedback_limit_ns: 3 * period_ns,
            stop_confirm_ns: 100_000_000,
            disable_silence_ns: 50_000_000,
            silent_ticks: 2,
        }
    }

    /// Whether this timing keeps the tick's promises: a send window inside the collect window inside the period, at
    /// least a period of feedback but less than the drives' timeout, a stop window longer than the post-Disable silence.
    ///
    /// # Errors
    /// The first rule it breaks.
    pub const fn check(&self) -> Result<(), &'static str> {
        if self.period_ns == 0 {
            Err("the period is zero")
        } else if self.send_window_ns == 0 || self.send_window_ns > self.collect_ns {
            Err("the send window must be non-zero and end by the collect deadline")
        } else if self.collect_ns >= self.period_ns {
            Err("the collect deadline must fall inside the period")
        } else if self.feedback_limit_ns < self.period_ns
            || self.feedback_limit_ns >= DRIVE_TIMEOUT_NS
        {
            Err("the feedback limit must be at least a period and under the drives' 50 ms timeout")
        } else if self.stop_confirm_ns <= self.disable_silence_ns {
            Err("the stop window must outlast the post-Disable silence")
        } else if self.silent_ticks == 0 {
            Err("silent_ticks must be at least 1")
        } else {
            Ok(())
        }
    }
}

/// One tick's commands from control: at most one encoded frame per drive slot (the drive's place in the bus's table).
/// Frames come only from `robstride::encode`, so the transmit allowlist holds here too.
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
}

/// What became of a send.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SendOutcome {
    /// The socket took it. On real CAN that is submission to the kernel, not transmission: the kernel and adapter queues
    /// don't expire frames (can.md section 2).
    Sent,
    /// `ENOBUFS` or `EAGAIN`: dropped and counted, never retried.
    QueueFull,
    /// A command whose send window had passed before the write: dropped and counted. Stop frames never expire.
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

/// Where a bus is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BusState {
    /// Nothing enabled or commanded since start; no batches needed.
    Idle,
    /// It has sent an Enable or MIT frame, so it needs a fresh batch every tick.
    Active,
    /// A stop is in progress: Disable to every unconfirmed drive each tick, batches refused.
    Stopping {
        /// When the stop began, monotonic.
        since_ns: u64,
    },
    /// Stopped, latched: nothing in this crate leaves it. Clearing is the safety layer's, through preflight.
    Stopped,
}

/// Why a bus stopped.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopReason {
    /// No fresh batch for `Timing::silent_ticks` ticks while active (PLAN.md item 3).
    ControlSilent,
    /// The thread woke after its send window (PLAN.md item 3).
    LateWake,
    /// A batch carried motion for a drive whose last fresh status was too old.
    ExpiredFeedback {
        /// That drive's slot.
        slot: usize,
    },
    /// A batch's frame didn't target its slot's drive: a bug upstream.
    BadBatch {
        /// The slot.
        slot: usize,
    },
    /// More frames were queued before the send than the tick may read.
    Backlog,
    /// Asked for by the runtime or a test.
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
    /// Disable was sent; no Reset-mode status came after it.
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
    /// The last status or report read from it, answer or not: its mode and fault bits are never filtered out.
    pub observed: Option<Observed>,
    /// When its last fresh status was read: the first status after a command the socket took. Freshness, not
    /// acknowledgement: the protocol has no sequence numbers, so which command a status answers can't be proven.
    pub fresh_ns: Option<u64>,
    /// Whether it answered this tick's command by the collect deadline.
    pub answered: bool,
    /// Any fault bit or fault report seen since start. Sticky.
    pub fault_seen: bool,
    /// What the current or last stop achieved for it.
    pub stop: StopOutcome,
    /// Whether the current or last stop's active reporting off was taken by the socket.
    pub reporting_off_sent: bool,
}

/// Per-bus counts since start.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Counters {
    /// Commands the socket took that got no status by the collect deadline.
    pub unanswered: u64,
    /// Statuses for a command after its tick's collect deadline.
    pub late: u64,
    /// A second status for one command.
    pub duplicate: u64,
    /// Statuses from this bus's drives with no command outstanding.
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
    /// Batches refused while stopping or stopped.
    pub refused_batches: u64,
    /// Ticks the thread woke for after their send window.
    pub missed_deadlines: u64,
    /// The socket's overflow counter (`SO_RXQ_OVFL`), the last value seen.
    pub kernel_drops: u32,
    /// Snapshots control's ring was too full to take.
    pub snapshots_dropped: u64,
}

/// The bus at the end of a tick, for control and the safety layer.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Snapshot {
    /// The tick.
    pub tick: u64,
    /// The bus's state after it.
    pub state: BusState,
    /// Why it stopped, if it has.
    pub stop: Option<StopReason>,
    /// The first bus error that latched (bus-off, interface down or gone), even if the bus was already stopping.
    pub bus_error: Option<BusError>,
    /// No latched bus error and not error-passive: the recording's `valid` flag (logging.md section 8.2).
    pub healthy: bool,
    /// Counts since start.
    pub counters: Counters,
    drives: [Option<DriveView>; MAX_DRIVES],
}

impl Snapshot {
    pub(crate) fn new(
        tick: u64,
        state: BusState,
        stop: Option<StopReason>,
        bus_error: Option<BusError>,
        healthy: bool,
        counters: Counters,
    ) -> Self {
        Self {
            tick,
            state,
            stop,
            bus_error,
            healthy,
            counters,
            drives: [None; MAX_DRIVES],
        }
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
    /// Timing [`Timing::check`] refuses.
    #[error("bad timing: {0}")]
    Timing(&'static str),
}
