//! One bus's independent stop as plain values: what to send when, and what each drive's replies prove. No I/O and no
//! clock; the caller passes the time since the stop began, so every timing below is tested without a bus.
//!
//! The sequence is PLAN item 2's Stop: a Disable (type 4, fault-clear byte unset) to every drive at once, sent again
//! each tick to every drive that hasn't been read in Reset, for at most 100 ms; then each drive's active reporting off
//! (type 24) once its post-Disable silence is over, because a drive drops every frame in that silence. A drive still
//! reporting after its reporting off gets it again, a bounded number of times.
//!
//! The timings are PLAN item 2's. The runtime's bus layer holds the resend tick and the silence as provisional values in
//! `can::Timing`; this crate can't depend on `can` (PLAN item 3: `disable` depends on nothing else), so each is cited
//! here instead. The report grace and watch and `END` are this stop's own.

#![cfg_attr(
    not(target_os = "linux"),
    expect(
        dead_code,
        reason = "only the Linux bus thread drives the stop from a socket; the stop and its tests build everywhere"
    )
)]

use std::fmt;
use std::time::Duration;

use robstride::{DeviceId, Frame, Inbound, Mode, Reporting, encode};

/// Disables are sent again this often to a drive not yet read in Reset: one tick at the runtime's 250 Hz (PLAN item 3).
pub const RESEND: Duration = Duration::from_millis(4);
/// Disables go out for this long after the first (PLAN item 2, Stop: "Disables for 100 ms").
pub const DISABLE_WINDOW: Duration = Duration::from_millis(100);
/// A drive drops every frame for up to this long after it takes a Disable (PLAN item 2, Silence windows: silences up
/// to 48.7 ms measured; `can::Timing::disable_silence_ns` and `sim-drive` use 50 ms). Its reporting off waits this long
/// after its Reset is read, plus one resend, in case a Disable sent again before the read restarted the silence.
pub const SILENCE: Duration = Duration::from_millis(50);
/// A report read more than this long after reporting off was sent means it didn't take: a drive reports every 10 ms
/// while reporting is on (§4.1.11), so a report already on its way when reporting off went is read inside it.
pub const REPORT_GRACE: Duration = Duration::from_millis(15);
/// How long the bus is watched for reports after each reporting off: five report intervals.
pub const REPORT_WATCH: Duration = Duration::from_millis(50);
/// Reporting off is sent at most this many times to one drive in one schedule. A drive seen out of Reset after its
/// reporting off starts a new schedule, so it can get more in all, until `END`.
pub const REPORTING_OFF_TRIES: u8 = 3;
/// The stop ends by this time whatever happens: the longest an undisturbed stop needs, the last Disable at 100 ms and
/// its silence, one resend, then every reporting off try and its watch (100 + 50 + 4 + 3 × 50 ms), rounded up. A drive
/// that leaves Reset late may need longer; it is cut here and needs a person.
pub const END: Duration = Duration::from_millis(310);

/// An OS error code from the socket, kept as the number so outcomes stay plain values.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OsError(pub i32);

impl fmt::Display for OsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        std::io::Error::from_raw_os_error(self.0).fmt(f)
    }
}

impl OsError {
    /// `EIO` (5, asm-generic/errno-base.h), for a failure that comes with no code of its own. A literal, as this module
    /// builds on every OS and nix is a Linux-only dependency.
    pub const EIO: Self = Self(5);
}

impl From<&std::io::Error> for OsError {
    /// An error with no OS code (none of the socket calls make one) becomes `EIO`.
    fn from(e: &std::io::Error) -> Self {
        e.raw_os_error().map_or(Self::EIO, Self)
    }
}

/// The bus-off class bit of an error frame's ID (`CAN_ERR_BUSOFF`, linux/can/error.h).
const CAN_ERR_BUSOFF: u32 = 0x40;
/// The controller class bit (`CAN_ERR_CRTL`): its byte is `data[1]`.
const CAN_ERR_CRTL: u32 = 0x04;
/// The controller's receive buffer overflowed (`CAN_ERR_CRTL_RX_OVERFLOW`, in `data[1]`): frames were lost.
const CAN_ERR_CRTL_RX_OVERFLOW: u8 = 0x01;

/// Whether the drain that just ran emptied the socket's queue.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Drain {
    /// Nothing more was queued.
    Emptied,
    /// It stopped at its bound with frames still queued.
    Capped,
}

/// What the bus thread does next.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Wait {
    /// The stop is over: report.
    Done,
    /// Frames are still queued: read them before any wait.
    DrainAgain,
    /// Wait for a frame, or until this time.
    Until(Duration),
}

/// Why a frame couldn't be handed to the socket.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SendError {
    /// The socket's queue is full (`ENOBUFS`, `EAGAIN`): tried again at the next wake while the frame is still due.
    Full,
    /// Anything else (the interface is down or gone): the bus is failed and the stop ends on it.
    Failed(OsError),
}

/// What went wrong with a whole bus.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum BusFault {
    /// The interface couldn't be opened: nothing was sent.
    #[error("can't open the interface: {0}")]
    Open(OsError),
    /// The bus's thread couldn't be started: nothing was sent.
    #[error("can't start the bus's thread: {0}")]
    Spawn(OsError),
    /// A write failed with something other than a full queue: nothing more was sent.
    #[error("a write failed: {0}")]
    Write(OsError),
    /// Reads failed: frames went on, but nothing after it was read, so nothing on this bus is confirmed.
    #[error("reads failed: {0}")]
    Read(OsError),
}

impl BusFault {
    /// A stable name for machine-read output (`--json`).
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::Open(_) => "open",
            Self::Spawn(_) => "spawn",
            Self::Write(_) => "write",
            Self::Read(_) => "read",
        }
    }
}

/// What became of one drive.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Read in Reset after a Disable and not seen out of it since; reporting off sent and no report read more than
    /// `REPORT_GRACE` after it.
    Stopped,
    /// Nothing read from it (off, unpowered or not wired), with no bus-off read on the bus after its socket opened and
    /// its error frames readable: Disables and reporting off were sent to it anyway. Lesser error frames (warning, passive, ACK) don't
    /// change this; a bus with no powered drive sends them.
    Silent,
    /// Nothing read from it, and the socket couldn't be asked for error frames, so a bus-off wouldn't have been seen:
    /// the silence may be the bus's, not the drive's.
    SilentErrorsUnseen,
    /// It answered, but was never read in Reset, or was read out of it since (an answer with no mode, such as a fault
    /// or parameter reply, counts as an answer only).
    NotReset,
    /// Still reporting after every reporting off try.
    StillReporting,
    /// The stop ended before its reporting off was due, or before the watch after it did.
    WatchCut,
    /// Frames from the bus went unread, still queued when the stop ended or dropped by the controller (RX overflow):
    /// one of them may have withdrawn its Reset, or been its answer.
    Unread,
    /// A Disable or reporting off for it was due and never left: the socket's queue stayed full.
    QueueFull,
    /// The bus failed (`BusStop::fault` says how) or went bus-off: what was sent and read for it is in its record.
    BusFailed,
}

impl Outcome {
    /// True when nothing about this drive needs a person: it is stopped, or it never answered, with no bus-off read on
    /// its bus and its errors readable.
    #[must_use]
    pub const fn ok(self) -> bool {
        matches!(self, Self::Stopped | Self::Silent)
    }
}

impl Outcome {
    /// A stable name for machine-read output (`--json`).
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::Stopped => "stopped",
            Self::Silent => "silent",
            Self::SilentErrorsUnseen => "silent_errors_unseen",
            Self::NotReset => "not_reset",
            Self::StillReporting => "still_reporting",
            Self::WatchCut => "watch_cut",
            Self::Unread => "unread",
            Self::QueueFull => "queue_full",
            Self::BusFailed => "bus_failed",
        }
    }
}

impl fmt::Display for Outcome {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Stopped => "stopped",
            Self::Silent => "silent (never answered)",
            Self::SilentErrorsUnseen => {
                "FAILED: never answered, and the bus's error frames couldn't be read"
            }
            Self::NotReset => "FAILED: answered, but never read in Reset or read out of it since",
            Self::StillReporting => "FAILED: still reporting after reporting off",
            Self::WatchCut => "FAILED: the stop ended before reporting off could be checked",
            Self::Unread => {
                "FAILED: frames from the bus went unread (still queued at the end, or lost to an RX overflow)"
            }
            Self::QueueFull => "FAILED: a frame never left, the socket's queue stayed full",
            Self::BusFailed => "FAILED: the bus failed or went bus-off",
        })
    }
}

/// One drive's stop and what was read from it. Times are since the stop began.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DriveStop {
    /// The drive.
    pub id: DeviceId,
    /// Disables handed to the socket.
    pub disables: u32,
    /// When it was read in Reset after a Disable had gone, unless it was read out of Reset since.
    pub reset: Option<Duration>,
    /// It sent anything after the first Disable went.
    pub answered: bool,
    /// Reporting off handed to the socket.
    pub reporting_offs: u8,
    /// The last reporting off handed to the socket.
    pub reporting_off: Option<Duration>,
    /// The last report (type 24) read from it.
    pub last_report: Option<Duration>,
    next_disable: Duration,
    /// The last reporting off of the current schedule: a Reset withdrawn after a reporting off starts a new one.
    off: Option<Duration>,
    /// Reporting offs sent in the current schedule.
    tries: u8,
}

impl DriveStop {
    const fn new(id: DeviceId) -> Self {
        Self {
            id,
            disables: 0,
            reset: None,
            answered: false,
            reporting_offs: 0,
            reporting_off: None,
            last_report: None,
            next_disable: Duration::ZERO,
            off: None,
            tries: 0,
        }
    }

    /// When its reporting off is first due: its silence over after the Reset read, or after the last Disable.
    fn reporting_off_due(&self) -> Duration {
        match self.reset {
            Some(reset) => reset + SILENCE + RESEND,
            None => DISABLE_WINDOW + SILENCE,
        }
    }

    /// Whether a report read after its reporting off shows reporting still on.
    fn still_reporting(&self) -> bool {
        match (self.off, self.last_report) {
            (Some(off), Some(report)) => report > off + REPORT_GRACE,
            _ => false,
        }
    }

    /// Whether its reporting off has gone and the watch after it passed.
    fn settled(&self, now: Duration) -> bool {
        self.off.is_some_and(|off| now >= off + REPORT_WATCH)
            && (!self.still_reporting() || self.tries >= REPORTING_OFF_TRIES)
    }
}

/// One bus's stop.
#[derive(Clone, Debug)]
pub struct BusStop {
    drives: Vec<DriveStop>,
    /// Nothing more is sent: the bus couldn't be opened, its thread started, or a write failed.
    send_fault: Option<BusFault>,
    /// Nothing more is read; frames still go.
    read_fault: Option<OsError>,
    /// Error frames read, of any class.
    error_frames: u32,
    /// A bus-off error frame was read (`CAN_ERR_BUSOFF`): the class the runtime latches on (can.md, Errors and
    /// bus-off). Every drive on the bus then needs a person, as a late report or Run could have been lost.
    bus_off: bool,
    /// The socket couldn't be asked for error frames, so a bus-off wouldn't be seen. Only silent drives need a person
    /// then: a drive read in Reset was read whatever the bus's state, while a bus-off that was read means frames were
    /// lost, which no one confirmation rules out.
    errors_unseen: Option<OsError>,
    /// The last drain stopped at its bound with frames still queued.
    backlog: bool,
    /// The controller reported an RX overflow: frames from the bus were dropped before they could be read.
    frames_lost: bool,
}

impl BusStop {
    /// A stop of the drives `ids`, all on one bus.
    #[must_use]
    pub fn new(ids: impl IntoIterator<Item = DeviceId>) -> Self {
        Self {
            drives: ids.into_iter().map(DriveStop::new).collect(),
            send_fault: None,
            read_fault: None,
            error_frames: 0,
            bus_off: false,
            errors_unseen: None,
            backlog: false,
            frames_lost: false,
        }
    }

    /// A frame read at `now`. Only frames from this stop's drives count, and only once a Disable has gone to that
    /// drive. Any frame from it means it answered; a status, report or version reply also gives its mode: Reset
    /// confirms it, and anything else withdraws a confirmation already made. A withdrawn drive's reporting off schedule
    /// starts over: inside the 100 ms window it gets Disables again and its reporting off waits out their silence; after
    /// it, no Disable goes, and its reporting off is due as for a drive never read in Reset (150 ms, so at once if that
    /// has passed).
    pub fn heard(&mut self, now: Duration, inbound: &Inbound) {
        let (device, mode, report) = match inbound {
            Inbound::Status(s) => (s.header.device, Some(s.header.mode), false),
            Inbound::Report(s) => (s.header.device, Some(s.header.mode), true),
            Inbound::Version { header, .. } => (header.device, Some(header.mode), false),
            Inbound::Identity { device, .. }
            | Inbound::Fault { device, .. }
            | Inbound::Param { device, .. } => (*device, None, false),
            Inbound::Echo(_) => return,
        };
        let Some(drive) = self.drives.iter_mut().find(|d| d.id == device) else {
            return;
        };
        if drive.disables == 0 {
            return;
        }
        drive.answered = true;
        if report {
            drive.last_report = Some(now);
        }
        match mode {
            Some(Mode::Reset) => {
                drive.reset.get_or_insert(now);
            }
            Some(Mode::Run | Mode::Calibration) if drive.reset.is_some() => {
                drive.reset = None;
                drive.off = None;
                drive.tries = 0;
            }
            Some(Mode::Run | Mode::Calibration) | None => {}
        }
    }

    /// An error frame was read; `class` is its ID's error class bits and `controller` its `data[1]` (linux/can/error.h).
    /// Bus-off fails the bus, and an RX overflow means frames were lost, so no drive on the bus is ok. Warning, passive
    /// and ACK errors count for nothing: they are what a bus with no powered drive on it sends.
    pub(crate) const fn heard_error_frame(&mut self, class: u32, controller: u8) {
        self.error_frames = self.error_frames.saturating_add(1);
        self.bus_off |= class & CAN_ERR_BUSOFF != 0;
        self.frames_lost |= class & CAN_ERR_CRTL != 0 && controller & CAN_ERR_CRTL_RX_OVERFLOW != 0;
    }

    /// The socket couldn't be asked for error frames: a bus-off wouldn't be seen, so a silent drive can't be told from
    /// one behind a dead bus.
    pub(crate) const fn cant_see_errors(&mut self, e: OsError) {
        self.errors_unseen = Some(e);
    }

    /// The drain that just ran emptied the queue, or stopped at its bound with frames still in it.
    pub(crate) fn drained(&mut self, drain: Drain) {
        self.backlog = drain == Drain::Capped;
    }

    /// The bus failed. A read fault ends the reads and lets frames go on; any other ends the sending. The first of each
    /// is kept.
    pub(crate) fn fail(&mut self, fault: BusFault) {
        if let BusFault::Read(e) = fault {
            self.read_fault.get_or_insert(e);
        } else {
            self.send_fault.get_or_insert(fault);
        }
    }

    /// Whether anything more may be sent: until a fault other than a read fault.
    const fn sending(&self) -> bool {
        self.send_fault.is_none()
    }

    /// Whether the socket is still read: until a read fault.
    #[must_use]
    pub(crate) const fn reading(&self) -> bool {
        self.read_fault.is_none()
    }

    /// What the bus thread does after the step at `now`: read queued frames first, while there are any and the stop
    /// isn't over, since one may withdraw a Reset; otherwise wait for the next due time, or report.
    #[must_use]
    pub(crate) fn wait(&self, now: Duration) -> Wait {
        match self.next(now) {
            _ if self.backlog && self.reading() && self.sending() && now < END => Wait::DrainAgain,
            Some(at) => Wait::Until(at),
            None => Wait::Done,
        }
    }

    /// Hand every frame due at `now` to `send`, Disables to every drive before any reporting off. A full queue leaves
    /// the frame due for the next wake; any other failure fails the bus and nothing more is sent.
    pub fn step(&mut self, now: Duration, send: &mut dyn FnMut(Frame) -> Result<(), SendError>) {
        if !self.sending() {
            return;
        }
        let failed = self.send_due(now, send);
        if let Some(e) = failed {
            self.fail(BusFault::Write(e));
        }
    }

    /// `step`'s sending: the OS error that failed a write, if one did, after which nothing more is sent.
    fn send_due(
        &mut self,
        now: Duration,
        send: &mut dyn FnMut(Frame) -> Result<(), SendError>,
    ) -> Option<OsError> {
        for drive in &mut self.drives {
            if drive.reset.is_some() || now >= DISABLE_WINDOW || now < drive.next_disable {
                continue;
            }
            match send(encode::disable(drive.id)) {
                Ok(()) => {
                    drive.disables += 1;
                    drive.next_disable = now + RESEND;
                }
                Err(SendError::Full) => {}
                Err(SendError::Failed(e)) => return Some(e),
            }
        }
        for drive in &mut self.drives {
            let due = match drive.off {
                // Never before a Disable has left: PLAN item 2's order is Disable, then reporting off.
                None => drive.disables > 0 && now >= drive.reporting_off_due(),
                Some(_) => drive.still_reporting() && drive.tries < REPORTING_OFF_TRIES,
            };
            if !due {
                continue;
            }
            match send(encode::active_reporting(drive.id, Reporting::Off)) {
                Ok(()) => {
                    drive.reporting_offs = drive.reporting_offs.saturating_add(1);
                    drive.tries += 1;
                    drive.off = Some(now);
                    drive.reporting_off = Some(now);
                }
                Err(SendError::Full) => {}
                Err(SendError::Failed(e)) => return Some(e),
            }
        }
        None
    }

    /// The next time after `now` that something falls due, if the stop isn't over. The caller wakes then or on a frame.
    fn next(&self, now: Duration) -> Option<Duration> {
        if self.done(now) {
            return None;
        }
        let at = self
            .drives
            .iter()
            .flat_map(|d| {
                let disable = (d.reset.is_none() && d.next_disable < DISABLE_WINDOW)
                    .then_some(d.next_disable);
                let off = match d.off {
                    None => d.reporting_off_due(),
                    Some(off) => off + REPORT_WATCH,
                };
                [disable, Some(off)]
            })
            .flatten()
            .filter(|&t| t > now)
            .min()
            .unwrap_or(END);
        Some(at.min(END))
    }

    /// True once every drive is settled, sending has stopped on a fault, or `END` has passed.
    fn done(&self, now: Duration) -> bool {
        !self.sending() || now >= END || self.drives.iter().all(|d| d.settled(now))
    }

    /// Each drive's record and outcome at `now`, the time the stop ended, in the order given.
    #[must_use]
    pub fn outcomes(&self, now: Duration) -> Vec<(DriveStop, Outcome)> {
        self.drives
            .iter()
            .map(|d| (d.clone(), self.outcome(d, now)))
            .collect()
    }

    /// How the bus failed, if it did: the fault that ended the sending, else the one that ended the reads.
    #[must_use]
    pub(crate) fn fault(&self) -> Option<BusFault> {
        self.send_fault.or(self.read_fault.map(BusFault::Read))
    }

    /// The fault that ended the reads, if any, also when a later one ended the sending.
    #[must_use]
    pub(crate) const fn read_fault(&self) -> Option<OsError> {
        self.read_fault
    }

    /// Error frames read, of any class.
    #[must_use]
    pub(crate) const fn error_frames(&self) -> u32 {
        self.error_frames
    }

    /// Whether an RX overflow error frame was read: frames were lost.
    #[must_use]
    pub(crate) const fn frames_lost(&self) -> bool {
        self.frames_lost
    }

    /// Whether a bus-off error frame was read.
    #[must_use]
    pub(crate) const fn bus_off(&self) -> bool {
        self.bus_off
    }

    /// Why the socket couldn't be asked for error frames, if it couldn't.
    #[must_use]
    pub(crate) const fn errors_unseen(&self) -> Option<OsError> {
        self.errors_unseen
    }

    fn outcome(&self, d: &DriveStop, now: Duration) -> Outcome {
        if self.fault().is_some() || self.bus_off {
            return Outcome::BusFailed;
        }
        if d.disables == 0 || (d.off.is_none() && now >= d.reporting_off_due()) {
            return Outcome::QueueFull;
        }
        if d.still_reporting() {
            return Outcome::StillReporting;
        }
        let outcome = match (d.reset, d.answered) {
            (Some(_), _) if !d.settled(now) => Outcome::WatchCut,
            (Some(_), _) => Outcome::Stopped,
            (None, true) => Outcome::NotReset,
            (None, false) if self.errors_unseen.is_some() => Outcome::SilentErrorsUnseen,
            (None, false) if !d.settled(now) => Outcome::WatchCut,
            (None, false) => Outcome::Silent,
        };
        if (self.backlog || self.frames_lost) && outcome.ok() {
            Outcome::Unread
        } else {
            outcome
        }
    }
}

#[cfg(test)]
mod tests;
