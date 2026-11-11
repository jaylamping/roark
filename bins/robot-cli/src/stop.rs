//! One bus's independent stop as plain values: what to send when, and what each drive's replies prove. No I/O and no
//! clock; the caller passes the time since the stop began, so every timing below is tested without a bus.
//!
//! The sequence is PLAN item 2's Stop: a Disable (type 4, fault-clear byte unset) to every drive at once, sent again
//! each tick to every drive that hasn't been read in Reset, for at most 100 ms; then each drive's active reporting off
//! (type 24) once its post-Disable silence is over, because a drive drops every frame in that silence. A drive still
//! reporting after its reporting off gets it again, a bounded number of times.

use robstride::{DeviceId, Frame, Inbound, Mode, Reporting, encode};

/// Disables are sent again this often to a drive not yet read in Reset: one tick at the runtime's 250 Hz (PLAN item 3).
pub const RESEND_NS: u64 = 4_000_000;
/// Disables go out for this long after the first (PLAN item 2, Stop: "Disables for 100 ms").
pub const DISABLE_WINDOW_NS: u64 = 100_000_000;
/// A drive drops every frame for up to this long after it takes a Disable (PLAN item 2, Silence windows: up to 48.7 ms
/// measured; `sim-drive` draws up to 50 ms). Its reporting off waits this long after its Reset is read, plus one
/// resend, in case a Disable sent again before the read restarted the silence.
pub const SILENCE_NS: u64 = 50_000_000;
/// A report read more than this long after reporting off was sent means it didn't take: a drive reports every 10 ms
/// while reporting is on (§4.1.11), so a report already on its way when reporting off went is read inside it.
pub const REPORT_GRACE_NS: u64 = 15_000_000;
/// How long the bus is watched for reports after each reporting off: five report intervals.
pub const REPORT_WATCH_NS: u64 = 50_000_000;
/// Reporting off is sent at most this many times to one drive.
pub const REPORTING_OFF_TRIES: u8 = 3;
/// The stop ends by this time whatever happens. The longest it can need: the last Disable at 100 ms and its silence,
/// one resend, then every reporting off try and its watch (100 + 50 + 4 + 3 × 50 ms), rounded up.
pub const END_NS: u64 = 310_000_000;

/// Why a frame couldn't be handed to the socket.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SendError {
    /// The socket's queue is full (`ENOBUFS`, `EAGAIN`): tried again at the next wake while the frame is still due.
    Full,
    /// Anything else (the interface is down or gone): the bus is failed and the stop ends on it.
    Failed(String),
}

/// What became of one drive.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Read in Reset after a Disable; reporting off sent and no report read after it.
    Stopped,
    /// Nothing read from it (off, unpowered or not wired): Disables and reporting off were sent to it anyway.
    Silent,
    /// It answered, but never in Reset.
    NotReset,
    /// Still reporting after every reporting off try.
    StillReporting,
    /// A frame for it never left: the queue stayed full, or the bus failed or wasn't read.
    NotSent(String),
}

impl Outcome {
    /// True when nothing about this drive needs a person: it is stopped, or it never answered.
    #[must_use]
    pub const fn ok(&self) -> bool {
        matches!(self, Self::Stopped | Self::Silent)
    }
}

/// One drive's stop and what was read from it. Times are nanoseconds since the stop began.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DriveStop {
    /// The drive.
    pub id: DeviceId,
    /// Disables handed to the socket.
    pub disables: u32,
    /// The first Disable handed to the socket.
    pub first_disable_ns: Option<u64>,
    /// When it was first read in Reset after a Disable had gone.
    pub reset_ns: Option<u64>,
    /// It sent anything after the first Disable went.
    pub answered: bool,
    /// Reporting off handed to the socket.
    pub reporting_offs: u8,
    /// The last reporting off handed to the socket.
    pub reporting_off_ns: Option<u64>,
    /// The last report (type 24) read from it.
    pub last_report_ns: Option<u64>,
    next_disable_ns: u64,
}

impl DriveStop {
    fn new(id: DeviceId) -> Self {
        Self {
            id,
            disables: 0,
            first_disable_ns: None,
            reset_ns: None,
            answered: false,
            reporting_offs: 0,
            reporting_off_ns: None,
            last_report_ns: None,
            next_disable_ns: 0,
        }
    }

    /// When its reporting off is first due: its silence over after the Reset read, or after the last Disable.
    const fn reporting_off_due_ns(&self) -> u64 {
        match self.reset_ns {
            Some(reset) => reset + SILENCE_NS + RESEND_NS,
            None => DISABLE_WINDOW_NS + SILENCE_NS,
        }
    }

    /// Whether a report read after its reporting off shows reporting still on.
    fn still_reporting(&self) -> bool {
        match (self.reporting_off_ns, self.last_report_ns) {
            (Some(off), Some(report)) => report > off + REPORT_GRACE_NS,
            _ => false,
        }
    }

    /// Whether its reporting off has gone and the watch after it passed.
    fn settled(&self, now_ns: u64) -> bool {
        self.reporting_off_ns
            .is_some_and(|off| now_ns >= off + REPORT_WATCH_NS)
            && (!self.still_reporting() || self.reporting_offs >= REPORTING_OFF_TRIES)
    }
}

/// One bus's stop.
#[derive(Clone, Debug)]
pub struct BusStop {
    drives: Vec<DriveStop>,
    /// The bus failed: nothing more is sent, every drive not stopped is `NotSent`.
    failed: Option<String>,
    /// Reads failed: nothing more is read, sends go on, nothing more is confirmed.
    deaf: Option<String>,
}

impl BusStop {
    /// A stop of the drives `ids`, all on one bus.
    #[must_use]
    pub fn new(ids: impl IntoIterator<Item = DeviceId>) -> Self {
        Self {
            drives: ids.into_iter().map(DriveStop::new).collect(),
            failed: None,
            deaf: None,
        }
    }

    /// A frame read at `now_ns`. Only statuses and reports from this stop's drives count, and only once a Disable has
    /// gone to that drive.
    pub fn heard(&mut self, now_ns: u64, inbound: &Inbound) {
        let (header, report) = match inbound {
            Inbound::Status(s) => (s.header, false),
            Inbound::Report(s) => (s.header, true),
            _ => return,
        };
        let Some(drive) = self.drives.iter_mut().find(|d| d.id == header.device) else {
            return;
        };
        if drive.disables == 0 {
            return;
        }
        drive.answered = true;
        if report {
            drive.last_report_ns = Some(now_ns);
        }
        if header.mode == Mode::Reset && drive.reset_ns.is_none() {
            drive.reset_ns = Some(now_ns);
        }
    }

    /// Reads failed: nothing more can be confirmed, but the frames still go.
    pub fn deafen(&mut self, error: String) {
        self.deaf.get_or_insert(error);
    }

    /// The bus failed before anything could be sent (it couldn't be opened).
    pub fn fail(&mut self, error: String) {
        self.failed.get_or_insert(error);
    }

    /// Hand every frame due at `now_ns` to `send`, Disables to every drive before any reporting off. A full queue
    /// leaves the frame due for the next wake; any other failure fails the bus and nothing more is sent.
    pub fn step(&mut self, now_ns: u64, send: &mut dyn FnMut(Frame) -> Result<(), SendError>) {
        if self.failed.is_some() {
            return;
        }
        let fail = |error: SendError, failed: &mut Option<String>| match error {
            SendError::Full => false,
            SendError::Failed(e) => {
                failed.get_or_insert(e);
                true
            }
        };
        for drive in &mut self.drives {
            if drive.reset_ns.is_none()
                && now_ns < DISABLE_WINDOW_NS
                && now_ns >= drive.next_disable_ns
            {
                match send(encode::disable(drive.id)) {
                    Ok(()) => {
                        drive.disables += 1;
                        drive.first_disable_ns.get_or_insert(now_ns);
                        drive.next_disable_ns = now_ns + RESEND_NS;
                    }
                    Err(e) => {
                        if fail(e, &mut self.failed) {
                            return;
                        }
                    }
                }
            }
        }
        for drive in &mut self.drives {
            let due = match drive.reporting_off_ns {
                None => now_ns >= drive.reporting_off_due_ns(),
                Some(_) => drive.still_reporting() && drive.reporting_offs < REPORTING_OFF_TRIES,
            };
            if !due {
                continue;
            }
            match send(encode::active_reporting(drive.id, Reporting::Off)) {
                Ok(()) => {
                    drive.reporting_offs += 1;
                    drive.reporting_off_ns = Some(now_ns);
                }
                Err(e) => {
                    if fail(e, &mut self.failed) {
                        return;
                    }
                }
            }
        }
    }

    /// The next time something falls due, if the stop isn't over by `now_ns`. The caller wakes then or on a frame.
    #[must_use]
    pub fn next_ns(&self, now_ns: u64) -> Option<u64> {
        if self.done(now_ns) {
            return None;
        }
        let at = self
            .drives
            .iter()
            .filter_map(|d| {
                let disable = (d.reset_ns.is_none() && d.next_disable_ns < DISABLE_WINDOW_NS)
                    .then_some(d.next_disable_ns);
                let off = match d.reporting_off_ns {
                    None => Some(d.reporting_off_due_ns()),
                    Some(off) => Some(off + REPORT_WATCH_NS),
                };
                [disable, off].into_iter().flatten().min()
            })
            .min()
            .unwrap_or(END_NS);
        Some(at.clamp(now_ns, END_NS))
    }

    /// True once every drive is settled, the bus failed, or `END_NS` has passed.
    #[must_use]
    pub fn done(&self, now_ns: u64) -> bool {
        self.failed.is_some() || now_ns >= END_NS || self.drives.iter().all(|d| d.settled(now_ns))
    }

    /// Each drive's record and outcome, in the order given.
    #[must_use]
    pub fn outcomes(&self) -> Vec<(DriveStop, Outcome)> {
        self.drives
            .iter()
            .map(|d| (d.clone(), self.outcome(d)))
            .collect()
    }

    /// Why the bus failed, if it did.
    #[must_use]
    pub fn failure(&self) -> Option<&str> {
        self.failed.as_deref()
    }

    fn outcome(&self, d: &DriveStop) -> Outcome {
        let unsent = |what: &str| match &self.failed {
            Some(e) => Outcome::NotSent(format!("{what}: bus failed: {e}")),
            None => Outcome::NotSent(format!("{what}: the socket's queue stayed full")),
        };
        if d.disables == 0 {
            return unsent("no Disable sent");
        }
        if d.reporting_offs == 0 {
            return unsent("no reporting off sent");
        }
        if d.still_reporting() {
            return Outcome::StillReporting;
        }
        match (d.reset_ns, d.answered, &self.deaf) {
            (Some(_), _, _) => Outcome::Stopped,
            (None, true, _) => Outcome::NotReset,
            (None, false, Some(e)) => {
                Outcome::NotSent(format!("frames sent, but reads failed: {e}"))
            }
            (None, false, None) => Outcome::Silent,
        }
    }
}

#[cfg(test)]
mod tests {
    use robstride::{DeviceId, Frame, Inbound, decode, drive};

    use super::{
        BusStop, DISABLE_WINDOW_NS, END_NS, Outcome, REPORT_GRACE_NS, REPORTING_OFF_TRIES,
        RESEND_NS, SILENCE_NS, SendError,
    };

    const MS: u64 = 1_000_000;

    fn id(n: u8) -> DeviceId {
        DeviceId::new(u64::from(n)).unwrap()
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

    /// What a frame the stop sent is: `('D', n)` a Disable, `('R', n)` reporting off.
    fn what(frame: Frame) -> (char, u8) {
        let host = drive::command(frame.id(), &frame.data()).unwrap().unwrap();
        let n = host.target.get();
        let kind = match host.command {
            drive::Command::Disable => 'D',
            drive::Command::Reporting(robstride::Reporting::Off) => 'R',
            _ => '?',
        };
        assert_ne!(kind, '?', "the stop sent {:?}", host.command);
        (kind, n)
    }

    /// Frames the stop sent, each with its time.
    type Sent = [(u64, (char, u8))];

    /// Run `stop` a millisecond at a time to its end, `answer` giving each drive's frames at each millisecond after the
    /// frames sent so far; every frame sent is returned with its time.
    fn run(
        stop: &mut BusStop,
        answer: &dyn Fn(u64, &Sent) -> Vec<Inbound>,
        send: &dyn Fn(u64, (char, u8)) -> Result<(), SendError>,
    ) -> Vec<(u64, (char, u8))> {
        let mut log = Vec::new();
        let mut now = 0;
        while !stop.done(now) {
            for inbound in answer(now, &log) {
                stop.heard(now, &inbound);
            }
            let mut out = Vec::new();
            stop.step(now, &mut |f| {
                let w = what(f);
                send(now, w).map(|()| out.push((now, w)))
            });
            log.extend(out);
            now += MS;
        }
        assert!(now <= END_NS + MS, "the stop ran past its end: {now}");
        log
    }

    fn times(sent: &Sent, frame: (char, u8)) -> Vec<u64> {
        sent.iter()
            .filter(|(_, w)| *w == frame)
            .map(|(t, _)| t / MS)
            .collect()
    }

    /// Guards: safety - the independent stop's sequence (PLAN item 2, Stop): a Disable to every drive at once, sent
    /// again each tick to a drive not read in Reset for 100 ms; reporting off only after the post-Disable silence (54 ms
    /// after the Reset read, 150 ms for a drive never read in Reset); and the outcome is what was read: a drive read in
    /// Reset is stopped, one that never answered is silent, one that answered only in Run needs a person.
    #[test]
    fn disables_go_to_every_drive_until_reset_then_reporting_off_after_the_silence() {
        // 11 answers each Disable 1 ms later in Reset; 12 never answers; 13 answers each Disable in Run.
        let answer = |now: u64, sent: &Sent| {
            let mut out = Vec::new();
            for (t, w) in sent {
                if *t + MS == now {
                    match w {
                        ('D', 11) => out.push(from(11, false, false)),
                        ('D', 13) => out.push(from(13, true, false)),
                        _ => {}
                    }
                }
            }
            out
        };
        let mut stop = BusStop::new([id(11), id(12), id(13)]);
        let sent = run(&mut stop, &answer, &|_, _| Ok(()));

        // Every drive's first Disable goes in the first step, before any reporting off.
        let first: Vec<(char, u8)> = sent.iter().take(3).map(|(_, w)| *w).collect();
        assert_eq!(first, [('D', 11), ('D', 12), ('D', 13)]);
        let every_tick: Vec<u64> = (0..DISABLE_WINDOW_NS / MS).step_by(4).collect();
        assert_eq!(times(&sent, ('D', 11)), [0]);
        assert_eq!(times(&sent, ('D', 12)), every_tick);
        assert_eq!(times(&sent, ('D', 13)), every_tick);
        assert_eq!(
            times(&sent, ('R', 11)),
            [(MS + SILENCE_NS + RESEND_NS) / MS]
        );
        assert_eq!(
            times(&sent, ('R', 12)),
            [(DISABLE_WINDOW_NS + SILENCE_NS) / MS]
        );
        assert_eq!(
            times(&sent, ('R', 13)),
            [(DISABLE_WINDOW_NS + SILENCE_NS) / MS]
        );

        let outcomes: Vec<Outcome> = stop.outcomes().into_iter().map(|(_, o)| o).collect();
        assert_eq!(
            outcomes,
            [Outcome::Stopped, Outcome::Silent, Outcome::NotReset]
        );
        assert!(stop.failure().is_none());
    }

    /// Guards: bug - drives left reporting by a faulted session flooded every later start, marengo
    /// `docs/safety.md` "Reporting Off at exit (2026-10-04)": a drive still reporting after its reporting off gets it
    /// again, at most `REPORTING_OFF_TRIES` times, and is reported as needing a person if it never stops; a report
    /// already on its way when reporting off went doesn't count.
    #[test]
    fn reporting_off_is_sent_again_while_reports_keep_coming() {
        // 11 is in Reset and reports every 10 ms: 21 stops after its second reporting off, 22 never stops, and 23 sends
        // one last report just inside the grace after its first.
        let answer = |now: u64, sent: &Sent| {
            let mut out = Vec::new();
            for (n, stops_after) in [(21, 2), (22, usize::MAX), (23, 1)] {
                let offs = times(sent, ('R', n));
                if now.is_multiple_of(10 * MS) && offs.len() < stops_after {
                    out.push(from(n, false, true));
                }
                // 23's last report, sent just before its reporting off arrived, is read just inside the grace.
                if n == 23
                    && offs
                        .first()
                        .is_some_and(|off| now == off * MS + REPORT_GRACE_NS - MS)
                {
                    out.push(from(n, false, true));
                }
            }
            out
        };
        let mut stop = BusStop::new([id(21), id(22), id(23)]);
        let sent = run(&mut stop, &answer, &|_, _| Ok(()));
        assert_eq!(times(&sent, ('R', 21)).len(), 2);
        assert_eq!(
            times(&sent, ('R', 22)).len(),
            usize::from(REPORTING_OFF_TRIES)
        );
        assert_eq!(times(&sent, ('R', 23)).len(), 1);
        let outcomes: Vec<Outcome> = stop.outcomes().into_iter().map(|(_, o)| o).collect();
        assert_eq!(
            outcomes,
            [Outcome::Stopped, Outcome::StillReporting, Outcome::Stopped]
        );
    }

    /// Guards: safety - a socket failure on one bus (PLAN item 6, `host.bus`): a full queue only delays a frame to the
    /// next wake, while any other write error fails the bus at once, sends nothing more on it and reports every drive
    /// not confirmed as needing a person.
    #[test]
    fn a_full_queue_delays_a_frame_and_a_failed_write_ends_the_bus() {
        // The queue is full for the first 2 ms: every Disable goes at 2 ms, all at once.
        let mut full = BusStop::new([id(11), id(12)]);
        let sent = run(
            &mut full,
            &|now, sent| {
                sent.iter()
                    .filter(|(t, w)| *t + MS == now && w.0 == 'D')
                    .map(|(_, w)| from(w.1, false, false))
                    .collect()
            },
            &|now, _| {
                if now < 2 * MS {
                    Err(SendError::Full)
                } else {
                    Ok(())
                }
            },
        );
        assert_eq!(times(&sent, ('D', 11)), [2]);
        assert_eq!(times(&sent, ('D', 12)), [2]);
        let outcomes: Vec<Outcome> = full.outcomes().into_iter().map(|(_, o)| o).collect();
        assert_eq!(outcomes, [Outcome::Stopped, Outcome::Stopped]);

        // The interface goes away on the second Disable of the first step: nothing more is sent, the stop is over.
        let mut gone = BusStop::new([id(11), id(12)]);
        let sent = run(&mut gone, &|_, _| Vec::new(), &|_, w| {
            if w == ('D', 12) {
                Err(SendError::Failed("ENODEV".to_owned()))
            } else {
                Ok(())
            }
        });
        assert_eq!(sent, [(0, ('D', 11))]);
        assert_eq!(gone.failure(), Some("ENODEV"));
        assert!(
            gone.outcomes()
                .iter()
                .all(|(_, o)| matches!(o, Outcome::NotSent(_)))
        );
    }
}
