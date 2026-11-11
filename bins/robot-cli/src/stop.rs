//! One bus's independent stop as plain values: what to send when, and what each drive's replies prove. No I/O and no
//! clock; the caller passes the time since the stop began, so every timing below is tested without a bus.
//!
//! The sequence is PLAN item 2's Stop: a Disable (type 4, fault-clear byte unset) to every drive at once, sent again
//! each tick to every drive that hasn't been read in Reset, for at most 100 ms; then each drive's active reporting off
//! (type 24) once its post-Disable silence is over, because a drive drops every frame in that silence. A drive still
//! reporting after its reporting off gets it again, a bounded number of times.
//!
//! The timings are PLAN item 2's. The runtime's bus layer holds the same provisional values in `can::Timing`; this
//! crate can't depend on `can` (PLAN item 3: `disable` depends on nothing else), so each is cited here instead.

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
/// Reporting off is sent at most this many times to one drive.
pub const REPORTING_OFF_TRIES: u8 = 3;
/// The stop ends by this time whatever happens. The longest it can need: the last Disable at 100 ms and its silence,
/// one resend, then every reporting off try and its watch (100 + 50 + 4 + 3 × 50 ms), rounded up.
pub const END: Duration = Duration::from_millis(310);

/// An OS error code from the socket, kept as the number so outcomes stay plain values.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OsError(pub i32);

impl fmt::Display for OsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        std::io::Error::from_raw_os_error(self.0).fmt(f)
    }
}

impl From<&std::io::Error> for OsError {
    /// An error with no OS code (none of the socket calls make one) becomes `EIO`.
    fn from(e: &std::io::Error) -> Self {
        Self(e.raw_os_error().unwrap_or(5))
    }
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

/// What became of one drive.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Read in Reset after a Disable and not seen out of it since; reporting off sent and no report read after it.
    Stopped,
    /// Nothing read from it (off, unpowered or not wired) on a bus that reported no errors: Disables and reporting off
    /// were sent to it anyway.
    Silent,
    /// Nothing read from it, and the bus sent error frames: the silence may be the bus's, not the drive's.
    SilentOnFaultyBus,
    /// It answered, but wasn't in Reset when last read.
    NotReset,
    /// Still reporting after every reporting off try.
    StillReporting,
    /// The stop ended before the watch after its last reporting off did.
    WatchCut,
    /// A Disable or reporting off for it never left: the socket's queue stayed full.
    QueueFull,
    /// The bus failed (`BusStop::fault` says how): what was sent and read for it is in its record.
    BusFailed,
}

impl Outcome {
    /// True when nothing about this drive needs a person: it is stopped, or it never answered on a healthy bus.
    #[must_use]
    pub const fn ok(self) -> bool {
        matches!(self, Self::Stopped | Self::Silent)
    }
}

impl fmt::Display for Outcome {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Stopped => "stopped",
            Self::Silent => "silent (never answered)",
            Self::SilentOnFaultyBus => "FAILED: never answered, and the bus sent error frames",
            Self::NotReset => "FAILED: answered, not in Reset when last read",
            Self::StillReporting => "FAILED: still reporting after reporting off",
            Self::WatchCut => "FAILED: the stop ended before reporting off could be checked",
            Self::QueueFull => "FAILED: a frame never left, the socket's queue stayed full",
            Self::BusFailed => "FAILED: the bus failed",
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
        match (self.reporting_off, self.last_report) {
            (Some(off), Some(report)) => report > off + REPORT_GRACE,
            _ => false,
        }
    }

    /// Whether its reporting off has gone and the watch after it passed.
    fn settled(&self, now: Duration) -> bool {
        self.reporting_off
            .is_some_and(|off| now >= off + REPORT_WATCH)
            && (!self.still_reporting() || self.reporting_offs >= REPORTING_OFF_TRIES)
    }
}

/// One bus's stop.
#[derive(Clone, Debug)]
pub struct BusStop {
    drives: Vec<DriveStop>,
    /// The bus failed. Sending stops on any fault but a read fault.
    fault: Option<BusFault>,
    /// Error frames read.
    error_frames: u32,
}

impl BusStop {
    /// A stop of the drives `ids`, all on one bus.
    #[must_use]
    pub fn new(ids: impl IntoIterator<Item = DeviceId>) -> Self {
        Self {
            drives: ids.into_iter().map(DriveStop::new).collect(),
            fault: None,
            error_frames: 0,
        }
    }

    /// A frame read at `now`. Only frames from this stop's drives count, and only once a Disable has gone to that
    /// drive. Any frame from it means it answered; a status, report or version reply also gives its mode: Reset
    /// confirms it, and anything else withdraws a confirmation already made.
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
            Some(Mode::Run | Mode::Calibration) => drive.reset = None,
            None => {}
        }
    }

    /// An error frame was read: a drive that never answers may be behind a faulty bus rather than off.
    pub const fn heard_error_frame(&mut self) {
        self.error_frames = self.error_frames.saturating_add(1);
    }

    /// The bus failed. The first fault is kept.
    pub fn fail(&mut self, fault: BusFault) {
        self.fault.get_or_insert(fault);
    }

    /// Whether anything more may be sent: not after a fault, but for a read fault, under which frames still go.
    fn sending(&self) -> bool {
        matches!(self.fault, None | Some(BusFault::Read(_)))
    }

    /// Hand every frame due at `now` to `send`, Disables to every drive before any reporting off. A full queue leaves
    /// the frame due for the next wake; any other failure fails the bus and nothing more is sent.
    pub fn step(&mut self, now: Duration, send: &mut dyn FnMut(Frame) -> Result<(), SendError>) {
        for i in 0..self.drives.len() {
            if !self.sending() {
                return;
            }
            let Some(drive) = self.drives.get_mut(i) else {
                return;
            };
            if drive.reset.is_some() || now >= DISABLE_WINDOW || now < drive.next_disable {
                continue;
            }
            match send(encode::disable(drive.id)) {
                Ok(()) => {
                    drive.disables += 1;
                    drive.next_disable = now + RESEND;
                }
                Err(SendError::Full) => {}
                Err(SendError::Failed(e)) => self.fail(BusFault::Write(e)),
            }
        }
        for i in 0..self.drives.len() {
            if !self.sending() {
                return;
            }
            let Some(drive) = self.drives.get_mut(i) else {
                return;
            };
            let due = match drive.reporting_off {
                None => now >= drive.reporting_off_due(),
                Some(_) => drive.still_reporting() && drive.reporting_offs < REPORTING_OFF_TRIES,
            };
            if !due {
                continue;
            }
            match send(encode::active_reporting(drive.id, Reporting::Off)) {
                Ok(()) => {
                    drive.reporting_offs += 1;
                    drive.reporting_off = Some(now);
                }
                Err(SendError::Full) => {}
                Err(SendError::Failed(e)) => self.fail(BusFault::Write(e)),
            }
        }
    }

    /// The next time after `now` that something falls due, if the stop isn't over. The caller wakes then or on a frame.
    #[must_use]
    pub fn next(&self, now: Duration) -> Option<Duration> {
        if self.done(now) {
            return None;
        }
        let at = self
            .drives
            .iter()
            .flat_map(|d| {
                let disable = (d.reset.is_none() && d.next_disable < DISABLE_WINDOW)
                    .then_some(d.next_disable);
                let off = match d.reporting_off {
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
    #[must_use]
    pub fn done(&self, now: Duration) -> bool {
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

    /// How the bus failed, if it did.
    #[must_use]
    pub const fn fault(&self) -> Option<BusFault> {
        self.fault
    }

    /// Error frames read.
    #[must_use]
    pub const fn error_frames(&self) -> u32 {
        self.error_frames
    }

    fn outcome(&self, d: &DriveStop, now: Duration) -> Outcome {
        if self.fault.is_some() {
            return Outcome::BusFailed;
        }
        if d.disables == 0 || d.reporting_offs == 0 {
            return Outcome::QueueFull;
        }
        if d.still_reporting() {
            return Outcome::StillReporting;
        }
        match (d.reset, d.answered) {
            (Some(_), _) if !d.settled(now) => Outcome::WatchCut,
            (Some(_), _) => Outcome::Stopped,
            (None, true) => Outcome::NotReset,
            (None, false) if self.error_frames > 0 => Outcome::SilentOnFaultyBus,
            (None, false) => Outcome::Silent,
        }
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use robstride::{DeviceId, Frame, Inbound, decode, drive};

    use super::{
        BusFault, BusStop, DISABLE_WINDOW, END, OsError, Outcome, REPORT_GRACE,
        REPORTING_OFF_TRIES, RESEND, SILENCE, SendError,
    };

    const MS: Duration = Duration::from_millis(1);

    /// Frames the stop sent, each with its time in milliseconds: `('D', n)` a Disable, `('R', n)` reporting off.
    type Sent = [(u64, (char, u8))];
    /// What `run` returns: every frame sent, and when the stop ended.
    type Run = (Vec<(u64, (char, u8))>, Duration);

    fn id(n: u8) -> DeviceId {
        DeviceId::new(u64::from(n)).unwrap()
    }

    fn ms(d: Duration) -> u64 {
        u64::try_from(d.as_millis()).unwrap()
    }

    /// A status (or report) from drive `n`: type 2 (or 24), mode in ID bits 23..22, the drive in bits 15..8.
    fn from(n: u8, run: bool, report: bool) -> Inbound {
        let kind: u32 = if report { 24 } else { 2 };
        let mode: u32 = if run { 2 } else { 0 };
        decode(
            (kind << 24) | (mode << 22) | (u32::from(n) << 8) | 0xFD,
            &[0x80, 0, 0x80, 0, 0x80, 0, 0, 0xFA],
        )
        .unwrap()
    }

    fn what(frame: Frame) -> (char, u8) {
        let host = drive::command(frame.id(), &frame.data()).unwrap().unwrap();
        let kind = match host.command {
            drive::Command::Disable => 'D',
            drive::Command::Reporting(robstride::Reporting::Off) => 'R',
            _ => '?',
        };
        assert_ne!(kind, '?', "the stop sent {:?}", host.command);
        (kind, host.target.get())
    }

    /// Run `stop` a millisecond at a time to its end, `answer` giving the drives' frames at each millisecond from the
    /// frames sent so far. Returns every frame sent and when the stop ended.
    fn run(
        stop: &mut BusStop,
        answer: &dyn Fn(u64, &Sent) -> Vec<Inbound>,
        send: &dyn Fn(u64, (char, u8)) -> Result<(), SendError>,
    ) -> Run {
        let mut log = Vec::new();
        let mut now = Duration::ZERO;
        while !stop.done(now) {
            for inbound in answer(ms(now), &log) {
                stop.heard(now, &inbound);
            }
            let mut out = Vec::new();
            stop.step(now, &mut |f| {
                let w = what(f);
                send(ms(now), w).map(|()| out.push((ms(now), w)))
            });
            log.extend(out);
            now += MS;
        }
        assert!(now <= END + MS, "the stop ran past its end: {now:?}");
        (log, now)
    }

    fn times(sent: &Sent, frame: (char, u8)) -> Vec<u64> {
        sent.iter()
            .filter(|(_, w)| *w == frame)
            .map(|(t, _)| *t)
            .collect()
    }

    fn outcomes(stop: &BusStop, end: Duration) -> Vec<Outcome> {
        stop.outcomes(end).into_iter().map(|(_, o)| o).collect()
    }

    /// Guards: safety - the independent stop's sequence (PLAN item 2, Stop): a Disable to every drive at once, sent
    /// again each tick to a drive not read in Reset for 100 ms; reporting off only after the post-Disable silence (54 ms
    /// after the Reset read, 150 ms for a drive never read in Reset); and the outcome is what was read: a drive read in
    /// Reset is stopped, one that never answered is silent, one that answered only in Run, or went back to Run after a
    /// Reset, needs a person.
    #[test]
    fn disables_go_to_every_drive_until_reset_then_reporting_off_after_the_silence() {
        // 11 answers each Disable 1 ms later in Reset; 12 never answers; 13 answers each Disable in Run; 14 answers in
        // Reset, then reports in Run at 30 ms (another controller enabled it).
        let answer = |now: u64, sent: &Sent| {
            let mut out = Vec::new();
            for (t, w) in sent {
                if *t + 1 == now {
                    match w {
                        ('D', 11 | 14) => out.push(from(w.1, false, false)),
                        ('D', 13) => out.push(from(13, true, false)),
                        _ => {}
                    }
                }
            }
            if now == 30 {
                out.push(from(14, true, true));
            }
            out
        };
        let mut stop = BusStop::new([id(11), id(12), id(13), id(14)]);
        let (sent, end) = run(&mut stop, &answer, &|_, _| Ok(()));

        // Every drive's first Disable goes in the first step, before any reporting off.
        let first: Vec<(char, u8)> = sent.iter().take(4).map(|(_, w)| *w).collect();
        assert_eq!(first, [('D', 11), ('D', 12), ('D', 13), ('D', 14)]);
        let every_tick: Vec<u64> = (0..ms(DISABLE_WINDOW)).step_by(4).collect();
        assert_eq!(times(&sent, ('D', 11)), [0]);
        assert_eq!(times(&sent, ('D', 12)), every_tick);
        assert_eq!(times(&sent, ('D', 13)), every_tick);
        // 14's Disables start again once it is seen in Run, and it is confirmed again a tick later.
        assert_eq!(times(&sent, ('D', 14)), [0, 30]);
        assert_eq!(times(&sent, ('R', 11)), [ms(MS + SILENCE + RESEND)]);
        assert_eq!(times(&sent, ('R', 12)), [ms(DISABLE_WINDOW + SILENCE)]);
        assert_eq!(times(&sent, ('R', 13)), [ms(DISABLE_WINDOW + SILENCE)]);
        assert_eq!(times(&sent, ('R', 14)), [ms(31 * MS + SILENCE + RESEND)]);
        assert_eq!(
            outcomes(&stop, end),
            [
                Outcome::Stopped,
                Outcome::Silent,
                Outcome::NotReset,
                Outcome::Stopped
            ]
        );
        assert!(stop.fault().is_none());
    }

    /// Guards: bug - drives left reporting by a faulted session flooded every later start, marengo
    /// `docs/safety.md` "Reporting Off at exit (2026-10-04)": a drive still reporting after its reporting off gets it
    /// again, at most `REPORTING_OFF_TRIES` times, and is reported as needing a person if it never stops; a report
    /// already on its way when reporting off went doesn't count.
    #[test]
    fn reporting_off_is_sent_again_while_reports_keep_coming() {
        // In Reset and reporting every 10 ms: 21 stops after its second reporting off, 22 never stops, and 23 stops
        // after its first but sends one last report just inside the grace.
        let answer = |now: u64, sent: &Sent| {
            let mut out = Vec::new();
            for (n, stops_after) in [(21, 2), (22, usize::MAX), (23, 1)] {
                let offs = times(sent, ('R', n));
                if now.is_multiple_of(10) && offs.len() < stops_after {
                    out.push(from(n, false, true));
                }
                if n == 23
                    && offs
                        .first()
                        .is_some_and(|off| now == off + ms(REPORT_GRACE) - 1)
                {
                    out.push(from(n, false, true));
                }
            }
            out
        };
        let mut stop = BusStop::new([id(21), id(22), id(23)]);
        let (sent, end) = run(&mut stop, &answer, &|_, _| Ok(()));
        assert_eq!(times(&sent, ('R', 21)).len(), 2);
        assert_eq!(
            times(&sent, ('R', 22)).len(),
            usize::from(REPORTING_OFF_TRIES)
        );
        assert_eq!(times(&sent, ('R', 23)).len(), 1);
        assert_eq!(
            outcomes(&stop, end),
            [Outcome::Stopped, Outcome::StillReporting, Outcome::Stopped]
        );
    }

    /// Guards: safety - a socket failure on one bus (PLAN item 6, `host.bus`): a full queue only delays a frame to the
    /// next wake; any other write error fails the bus at once and sends nothing more on it; a read failure lets the
    /// frames go on but confirms nothing; and a drive that never answers on a bus that sent error frames isn't taken
    /// for one that is off. Each of these needs a person.
    #[test]
    fn socket_failures_and_error_frames_need_a_person() {
        let echo = |now: u64, sent: &Sent| -> Vec<Inbound> {
            sent.iter()
                .filter(|(t, w)| *t + 1 == now && w.0 == 'D')
                .map(|(_, w)| from(w.1, false, false))
                .collect()
        };
        // The queue is full for the first 2 ms: every Disable goes at 2 ms, all at once.
        let mut full = BusStop::new([id(11), id(12)]);
        let (sent, end) = run(&mut full, &echo, &|now, _| {
            if now < 2 {
                Err(SendError::Full)
            } else {
                Ok(())
            }
        });
        assert_eq!(times(&sent, ('D', 11)), [2]);
        assert_eq!(times(&sent, ('D', 12)), [2]);
        assert_eq!(outcomes(&full, end), [Outcome::Stopped, Outcome::Stopped]);

        // The interface goes away on the second Disable of the first step: nothing more is sent, the stop is over.
        let mut gone = BusStop::new([id(11), id(12)]);
        let (sent, end) = run(&mut gone, &|_, _| Vec::new(), &|_, w| {
            if w == ('D', 12) {
                Err(SendError::Failed(OsError(19)))
            } else {
                Ok(())
            }
        });
        assert_eq!(sent, [(0, ('D', 11))]);
        assert_eq!(gone.fault(), Some(BusFault::Write(OsError(19))));
        assert_eq!(
            outcomes(&gone, end),
            [Outcome::BusFailed, Outcome::BusFailed]
        );

        // Reads fail after 11 is confirmed: every frame still goes, and nothing on the bus counts as confirmed.
        let mut deaf = BusStop::new([id(11), id(12)]);
        let mut now = Duration::ZERO;
        let mut sent = 0;
        while !deaf.done(now) {
            if now == MS {
                deaf.heard(now, &from(11, false, false));
                deaf.fail(BusFault::Read(OsError(5)));
            }
            deaf.step(now, &mut |_| {
                sent += 1;
                Ok(())
            });
            now += MS;
        }
        assert_eq!(sent, 1 + ms(DISABLE_WINDOW) / 4 + 2);
        assert_eq!(
            outcomes(&deaf, now),
            [Outcome::BusFailed, Outcome::BusFailed]
        );

        // Error frames on the bus: a silent drive isn't reported as off.
        let mut errors = BusStop::new([id(11)]);
        errors.heard_error_frame();
        let (_, end) = run(&mut errors, &|_, _| Vec::new(), &|_, _| Ok(()));
        assert_eq!(outcomes(&errors, end), [Outcome::SilentOnFaultyBus]);
    }
}
