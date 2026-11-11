//! What crosses the bus thread's seams: command batches in, snapshots out (slow requests and results are in `slow`), all
//! fixed-size and `Copy` so the rings never allocate (rust.md section 6).

use robstride::{DeviceId, EchoKind, Frame, Mode, Status};

use crate::error_frame::BusError;
use crate::timing::TimingError;

/// The most drives one bus holds. The skeleton puts at most seven on a bus; a bus with more is refused at startup.
pub const MAX_DRIVES: usize = 8;
/// Room for the frames one tick sends. A tick sends at most one frame per drive (a command, or while stopping a Disable
/// or a reporting off, never both); twice that is headroom, and a tick that plans past it is a bug in this crate.
pub const MAX_SENDS: usize = 2 * MAX_DRIVES;

/// One tick's commands from control: at most one encoded frame per drive slot (the drive's place in the bus's table).
/// Frames come only from `robstride::encode`, which builds only allowlisted frames. A batch may carry only motion,
/// Enable, Disable, active reporting off and the `run_mode` = MIT write; the tick refuses anything else as a bad batch,
/// since Set Zero, set-ID and other parameter traffic need sequencing a per-tick batch can't give (PLAN.md item 2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CommandBatch {
    /// The tick it is for. A batch for any other tick is stale and never sent.
    pub tick: u64,
    /// After this monotonic time it is expired: its commands are never sent, while its Disables and active reporting
    /// off still go if it is for this tick, since late they are still the right frames (can.md section 2).
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

    /// Put `frame` in `slot`; false if the slot is out of range (the frame is then not in the batch).
    #[must_use]
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
    /// It emptied the socket but read more frames than the shell may before a send: what it said can't be known in time,
    /// so every active limb stops and the tick is held for every idle one ([`BusTick::begin`](crate::BusTick::begin)).
    Backlog,
    /// It gave up with frames still queued: as for `Backlog`, and until a drain empties the socket its statuses may
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
    /// Not taken for any other reason: a socket write error, a frame the shell couldn't build, or a send not tried
    /// because the bus was already lost (nothing to send on). It records only that the frame wasn't taken and never
    /// latches: a socket write error other than a full queue must also go to
    /// [`BusTick::lost_bus`](crate::BusTick::lost_bus), which does.
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

    /// Add a send. Planning past [`MAX_SENDS`] is this crate's bug, so it ends the process rather than drop a frame
    /// that may be a Disable (rust.md section 4).
    pub(crate) fn push(&mut self, send: Send) {
        let slot = self.sends.get_mut(self.len);
        assert!(slot.is_some(), "a tick planned more than {MAX_SENDS} sends");
        if let Some(slot) = slot {
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

/// Where one limb on a bus is. Each limb runs and stops on its own; a stop of the whole bus stops every limb not
/// already stopping or stopped, and a late wake or a backlog every active one ([`StopReason`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimbState {
    /// Nothing enabled or commanded since start or the last re-arm; no batches needed, though slow requests are refused
    /// while control is silent.
    Idle,
    /// An Enable or MIT frame to one of its drives was sent, so the bus needs a fresh batch every tick.
    Active,
    /// A stop is in progress: Disables, then reporting off, its frames in batches refused; over by
    /// `Timing::stop_max_ns` after `since_ns` at the latest.
    Stopping {
        /// When the stop began, monotonic.
        since_ns: u64,
    },
    /// Stopped, latched: only an operator's clear re-arms it ([`BusTick::rearm`](crate::BusTick::rearm)).
    Stopped,
}

impl LimbState {
    /// Whether the limb takes control's commands: idle or active. Every check that gates a command on the limb asks
    /// this, so a new state has to say here whether it does.
    #[must_use]
    pub const fn takes_commands(self) -> bool {
        match self {
            Self::Idle | Self::Active => true,
            Self::Stopping { .. } | Self::Stopped => false,
        }
    }
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

/// The last of this host's frames to a drive of a kind a batch carries, read back from the socket.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EchoSeen {
    /// What it was.
    pub kind: EchoKind,
    /// When it was read, monotonic.
    pub read_ns: u64,
}

/// Why a limb stopped. `ExpiredFeedback`, `DriveFault`, `DriveMode`, `DriveSilent` and `LimbRequested`
/// (`BusTick::stop_limb`) stop only that limb; `LateWake` and `Backlog` stop every active limb; the rest, `Requested`
/// (`BusTick::request_stop`), `BadBatch` and `BadOrder` included, stop every limb on the bus.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopReason {
    /// No fresh batch for `Timing::silent_ticks` ticks while a limb was active (PLAN.md item 3).
    ControlSilent,
    /// The thread woke after its send window, or a stall skipped ticks, whatever its feedback's age (PLAN.md item 3).
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
    /// States). A drive this host never enabled doesn't stop its limb here: its excursions out of Reset are latched in
    /// [`DriveView::out_of_reset`], and preflight and the enable sequence refuse it.
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
    /// Control ordered a stop of a limb this bus doesn't have (`Order::StopLimb`): a bug upstream, and the bus can't
    /// tell which limb was meant.
    BadOrder {
        /// The limb index the order named.
        limb: usize,
    },
    /// More frames were queued before the send than the tick may read.
    Backlog,
    /// Asked for by the runtime or a test, for the whole bus.
    Requested,
    /// Asked for by the runtime or a test, for this limb alone.
    LimbRequested,
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
    /// Disable was sent; no Reset-mode status read after it was counted: none came, one was read after the stop's reply
    /// allowance (`Timing::stop_replies_ns`), or one may predate it (after a drain that left frames queued). Also a
    /// drive that was confirmed and then showed another mode: that withdraws the confirmation. A drive never confirmed
    /// gets no reporting off; one whose confirmation was withdrawn may have had it already. Either way re-arming waits
    /// for it to go quiet past its timeout.
    Sent,
    /// A Reset-mode status was read after a sent Disable, inside the stop's reply allowance, and no status, report or
    /// version reply in another mode since.
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

/// A drive's mode as a frame's status header showed it, with the monotonic time the bus thread read that frame.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ModeSeen {
    /// The mode.
    pub mode: Mode,
    /// When the frame was read.
    pub read_ns: u64,
}

/// One drive in a snapshot.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DriveView {
    /// The drive.
    pub device: DeviceId,
    /// Its limb on this bus.
    pub limb: usize,
    /// The last status or report read from it, answer or not: its mode and fault bits are never filtered out. A version
    /// reply isn't kept here (it carries no feedback): its faults go to `fault_seen` and its mode to `mode`, so a version
    /// reply read since can have shown another mode than this one.
    pub observed: Option<Observed>,
    /// The mode the last frame with a status header showed, and when it was read: a status, a report or a version reply,
    /// the frames that carry one (an identity, parameter or fault reply carries none). The drive's latest word on its
    /// mode, answer or not; the stop logic reads the same headers.
    pub mode: Option<ModeSeen>,
    /// The last mode other than Reset a status header showed while this host hadn't enabled the drive (never enabled
    /// since start or its limb's last re-arm, or seen in Reset after this host's Disable) or had disabled it, and when
    /// it was read. Kept until the limb's next re-arm, so a drive that went to Run and back to Reset between two
    /// snapshots, or across snapshots control never read, still shows it; this host's own Enable and the Run that
    /// answers it never set it. Preflight and the enable sequence read it to refuse a drive something else took out
    /// of Reset since preflight began.
    pub out_of_reset: Option<ModeSeen>,
    /// When its last fresh status was read: the first status after a command the socket took. Freshness, not
    /// acknowledgement: the protocol has no sequence numbers, so which command a status answers can't be proven. Read
    /// time, not arrival: for every status motion is sent on, it trails the kernel's receipt by at most period -
    /// collect + send window (units-and-frames.md section 5). A held tick clears it, with `fresh_status`, for the
    /// drives of a limb still idle, after its batch checks ([`BusTick::begin`](crate::BusTick::begin)).
    pub fresh_ns: Option<u64>,
    /// The status `fresh_ns` is the read time of, kept while later frames show the same mode (a duplicate, a report, an
    /// unsolicited or earlier-tick status replacing `observed`, or a version reply), and dropped when a later one, a
    /// version reply included, shows another mode, which supersedes it. Read the drive's latest mode from `mode` and
    /// faults from `fault_seen`, never from this; `fresh_ns` stays the age
    /// of the last fresh reply either way.
    pub fresh_status: Option<Observed>,
    /// Whether it answered this tick's command by the collect deadline.
    pub answered: bool,
    /// Any fault bit or fault report seen since start or its limb's last re-arm. Sticky until then.
    pub fault_seen: bool,
    /// Commands in a row it left unanswered by the collect deadline.
    pub misses: u32,
    /// The last of this host's frames to it of a kind a batch carries, read back from the socket: the evidence a frame
    /// reached the controller (never that it reached the drive). Slow requests' echoes aren't kept here.
    pub last_echo: Option<EchoSeen>,
    /// What the current or last stop achieved for it.
    pub stop: StopOutcome,
    /// Whether the current or last stop's active reporting off was taken by the socket, for a drive whose confirmation
    /// still stands. False for a drive the stop never confirmed, for one whose reporting off the socket refused until
    /// the stop ended, and for one whose confirmation was withdrawn (`stop` back to `Sent`), even if the socket took its
    /// reporting off before that.
    pub reporting_off_sent: bool,
}

/// Per-bus counts since start.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Counters {
    /// Commands the socket took that got no status by the collect deadline, counted only where a miss counts toward
    /// `Timing::silence_misses`: not an Enable or a Disable, and nothing inside PLAN.md item 2's Silence windows.
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
    /// Sends the socket refused (`ENOBUFS`, `EAGAIN`, other errors), and sends not tried once the bus was lost.
    pub tx_dropped: u64,
    /// Sends dropped because their window had passed.
    pub tx_expired: u64,
    /// Ticks handed a stale or expired batch (an expired one for the tick still sends its Disables and reporting off).
    pub stale_ticks: u64,
    /// Batches refused because every limb was stopping or stopped, a bad one included once no limb was left to stop.
    pub refused_batches: u64,
    /// Batches whose Disables and reporting off alone were sent, the rest held back, for a backlog or a late wake that
    /// tick.
    pub held_batches: u64,
    /// Frames of a batch for this tick, fresh or expired, dropped because their limb was stopping or stopped.
    pub refused_frames: u64,
    /// Ticks that woke past their send window, plus each tick a stalled thread never ran
    /// ([`BusTick::skipped`](crate::BusTick::skipped)).
    pub missed_deadlines: u64,
    /// The socket's overflow counter (`SO_RXQ_OVFL`), the last value seen.
    pub kernel_drops: u32,
    /// Snapshots control's ring was too full to take.
    pub snapshots_dropped: u64,
    /// Slow results control's ring was too full to take.
    pub slow_results_dropped: u64,
    /// Slow requests that expired unsent, queued for `Timing::slow_queue_ticks` ticks.
    pub slow_expired: u64,
    /// Answers to control's re-arm orders that its ring was too full to take.
    pub rearms_dropped: u64,
    /// Stop orders naming a limb this bus doesn't have (`StopReason::BadOrder`), each stopping the bus.
    pub bad_orders: u64,
}

/// The bus at the end of a tick, for control and the safety layer.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Snapshot {
    /// The tick.
    pub tick: u64,
    /// The first bus error that latched (bus-off from an error frame, or any socket failure passed to `lost_bus`), even
    /// if a limb was already stopping.
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
    /// The same drive listed twice: every status would go to its first slot.
    #[error("drive {0:?} is listed twice")]
    DuplicateDrive(DeviceId),
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
    /// Timing [`crate::Timing::check`] refuses.
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
    /// A stop of the limb or the bus was asked before this clear and not yet planned: the stop stands.
    #[error("a stop of limb {0} or its bus is still pending")]
    StopPending(usize),
    /// The bus thread ended before it took the order.
    #[error("the bus thread ended before the clear")]
    Ended,
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
