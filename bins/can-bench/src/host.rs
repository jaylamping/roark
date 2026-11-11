//! The host side: the bus loop's shape on the interface under test. Each tick it sends one request per slot, reads
//! replies until the tick is nearly over, and records when each one was read. Its numbers bound the interface, not the
//! runtime: it follows the bus thread's schedule (can.md section 2: absolute wake, drain, one send per slot, a full queue
//! counted and never retried, a stall skipped rather than caught up) but reads until 90 % of the period instead of the
//! collect deadline, sends no slow requests, and sets none of the bus thread's socket options beyond error frames.

use std::fmt::Write as _;
use std::fs::{self, File};
use std::io::{self, BufWriter, Write as _};
use std::path::{Path, PathBuf};
use std::time::Duration;

use nix::errno::Errno;
use nix::sys::time::TimeSpec;
use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Frame, Socket};

use crate::frames;
use crate::link::{self, Role};
use crate::report::{self, Counts, Results};

/// A run's settings.
pub(crate) struct HostArgs {
    pub(crate) bus: String,
    pub(crate) hz: u32,
    pub(crate) slots: usize,
    pub(crate) seconds: u32,
    /// The collect deadline as a share of the period, in percent (PLAN item 3: about 60).
    pub(crate) deadline_pct: u32,
    pub(crate) out: PathBuf,
}

/// Reading stops this far into the period, so the next tick's sends aren't delayed by this one's reads.
pub(crate) const READ_END_PCT: u64 = 90;
/// The first tick starts this long after the bench is ready.
const LEAD: Duration = Duration::from_millis(100);
/// The most frames one drain at a tick's start reads; more means a backlog, counted as foreign or late anyway.
const DRAIN_MAX: usize = 256;
/// `CAN_ERR_BUSOFF` in an error frame's ID (`linux/can/error.h`).
const ERR_BUSOFF: u32 = 0x0040;
/// `ticks.csv` is written through a buffer this big, so the measured thread seldom waits on the disk.
const CSV_BUFFER: usize = 4 << 20;

/// A run's times, from its settings.
#[derive(Clone, Copy)]
pub(crate) struct Times {
    pub(crate) period: u64,
    pub(crate) deadline: u64,
    /// A wake later than this into its tick would stop the bus in the runtime (`can::Timing`: a quarter of the
    /// period).
    pub(crate) send_window: u64,
    read_end: u64,
    ticks: u64,
}

fn now_ns() -> Result<u64, String> {
    let t = clock_gettime(ClockId::CLOCK_MONOTONIC).map_err(|e| format!("clock: {e}"))?;
    let sec = u64::try_from(t.tv_sec()).map_err(|e| format!("clock: {e}"))?;
    let nsec = u64::try_from(t.tv_nsec()).map_err(|e| format!("clock: {e}"))?;
    Ok(sec * 1_000_000_000 + nsec)
}

fn sleep_until(ns: u64) -> Result<(), String> {
    let at = TimeSpec::from_duration(Duration::from_nanos(ns));
    loop {
        match clock_nanosleep(
            ClockId::CLOCK_MONOTONIC,
            ClockNanosleepFlags::TIMER_ABSTIME,
            &at,
        ) {
            Ok(_) => return Ok(()),
            Err(Errno::EINTR) => {}
            Err(e) => return Err(format!("clock_nanosleep: {e}")),
        }
    }
}

/// Refuse settings the bench can't run, and an output folder that already holds a run.
fn check(args: &HostArgs) -> Result<Times, String> {
    if args.slots == 0 || args.slots > frames::MAX_SLOTS {
        return Err(format!("--slots must be 1 to {}", frames::MAX_SLOTS));
    }
    if args.seconds == 0 {
        return Err("--seconds must be 1 or more".to_owned());
    }
    if args.hz == 0 || args.hz > 2000 {
        return Err("--hz must be 1 to 2000".to_owned());
    }
    if args.deadline_pct == 0 || u64::from(args.deadline_pct) >= READ_END_PCT {
        return Err(format!("--deadline-pct must be 1 to {}", READ_END_PCT - 1));
    }
    for file in ["ticks.csv", "summary.txt"] {
        if args.out.join(file).exists() {
            return Err(format!(
                "{} already holds a run; give a new --out",
                args.out.display()
            ));
        }
    }
    let period = 1_000_000_000 / u64::from(args.hz);
    Ok(Times {
        period,
        deadline: period * u64::from(args.deadline_pct) / 100,
        send_window: period / 4,
        read_end: period * READ_END_PCT / 100,
        ticks: u64::from(args.seconds) * u64::from(args.hz),
    })
}

/// Run the host side, print the summary, and write `ticks.csv` and `summary.txt` under `args.out`. Returns whether the
/// run met the pass mark. Once the run has started, an error ends it but the summary is still printed and written,
/// saying why.
pub(crate) fn run(args: &HostArgs) -> Result<bool, String> {
    let times = check(args)?;
    let _runtime_lock = link::exclude_runtime()?;
    let bus = args.bus.as_str();
    let socket = link::open(bus).map_err(|e| format!("{bus}: {e}"))?;
    link::check_quiet(&socket, bus, Role::Host)?;
    fs::create_dir_all(&args.out).map_err(|e| format!("{}: {e}", args.out.display()))?;
    let before = link::counters(bus).ok();
    let driver = link::driver(bus);
    let hw_stamps = socket.has_hw_timestamps();
    let requests: Vec<ExtendedId> = (0..args.slots)
        .map(|s| frames::request_id(s).and_then(ExtendedId::new))
        .collect::<Option<_>>()
        .ok_or("request ID out of range")?;

    let mut state = State::new(&args.out, args.slots, times)?;
    let ended = state.ticks(&socket, bus, &requests).err();
    let ended = match (ended, state.csv.flush()) {
        (Some(e), _) => Some(e),
        (None, Err(e)) => Some(format!("ticks.csv: {e}")),
        (None, Ok(())) => None,
    };
    let after = link::counters(bus).ok();
    let (summary, pass) = report::summary(&report::Run {
        args,
        driver: &driver,
        hw_stamps,
        times,
        results: state.results,
        before: before.as_ref(),
        after: after.as_ref(),
        ended: ended.as_deref(),
    });
    // Printed first, so a summary.txt that can't be written loses no numbers.
    io::stdout()
        .write_all(summary.as_bytes())
        .map_err(|e| e.to_string())?;
    let path = args.out.join("summary.txt");
    fs::write(&path, &summary).map_err(|e| format!("{}: {e}", path.display()))?;
    Ok(pass)
}

/// Everything a run carries from tick to tick.
struct State {
    times: Times,
    results: Results,
    csv: BufWriter<File>,
    sent_at: Vec<Option<u64>>,
    read_at: Vec<Option<u64>>,
    sent_count: u32,
}

impl State {
    fn new(out: &Path, slots: usize, times: Times) -> Result<Self, String> {
        let ticks = usize::try_from(times.ticks).map_err(|e| e.to_string())?;
        Ok(Self {
            times,
            results: Results::with_capacity(ticks, slots),
            csv: open_csv(out, slots)?,
            sent_at: vec![None; slots],
            read_at: vec![None; slots],
            sent_count: 0,
        })
    }

    /// Every tick of the run, in order. A wake after a tick's period skips to the tick in progress, as the bus thread
    /// does (`can` clock): the ticks slept through are counted as skipped, never sent late or counted as missing
    /// replies. Unlike the bus thread, which runs the tick in progress late, the bench also skips it when its reading
    /// time is already over, since it could only count every reply missing.
    fn ticks(
        &mut self,
        socket: &CanSocket,
        bus: &str,
        requests: &[ExtendedId],
    ) -> Result<(), String> {
        let t = self.times;
        // Ticks fall on whole periods of the monotonic clock, so hosts on one machine at one rate tick together, as the
        // runtime's bus threads do on one schedule.
        let lead = now_ns()? + u64::try_from(LEAD.as_nanos()).map_err(|e| e.to_string())?;
        let origin = lead.div_ceil(t.period) * t.period;
        let mut k = 0;
        while k < t.ticks {
            let scheduled = origin + k * t.period;
            sleep_until(scheduled)?;
            let woke = now_ns()?;
            let late = woke.saturating_sub(scheduled);
            self.results.wake_late.push(late);
            // The tick in progress, and whether its reading time is already over. A stall past the run's end ends it.
            let current = ((woke - origin) / t.period).min(t.ticks);
            if current > k {
                self.results.counts.skipped += current - k;
                k = current;
                if k >= t.ticks {
                    break;
                }
            }
            let start = origin + k * t.period;
            if woke >= start + t.read_end {
                self.results.counts.skipped += 1;
                k += 1;
                continue;
            }
            self.tick(socket, bus, requests, k, start, late)?;
            k += 1;
        }
        Ok(())
    }

    /// One tick: drain what came late, send, collect, record.
    fn tick(
        &mut self,
        socket: &CanSocket,
        bus: &str,
        requests: &[ExtendedId],
        k: u64,
        start: u64,
        late: u64,
    ) -> Result<(), String> {
        let tick = u32::try_from(k).map_err(|e| e.to_string())?;
        for _ in 0..DRAIN_MAX {
            let Some(frame) = link::read(socket).map_err(|e| format!("{bus}: {e}"))? else {
                break;
            };
            classify(&frame, tick, &mut self.results.counts, None);
        }
        self.sent_at.fill(None);
        self.read_at.fill(None);
        self.send(socket, bus, requests, tick, start)?;
        self.collect(socket, bus, tick, start)?;

        let missing = self
            .read_at
            .iter()
            .zip(&self.sent_at)
            .filter(|(r, s)| r.is_none() && s.is_some())
            .count();
        self.results.counts.missing += u64::try_from(missing).map_err(|e| e.to_string())?;
        let last = self
            .read_at
            .iter()
            .flatten()
            .max()
            .map(|t| t.saturating_sub(start));
        if missing == 0
            && let Some(l) = last
        {
            self.results.last_reply.push(l);
        }
        let row = row(k, late, last, missing, &self.read_at, start);
        writeln!(self.csv, "{row}").map_err(|e| format!("ticks.csv: {e}"))
    }

    /// Send one request per slot, once each; a full queue drops it and counts it, as the bus thread does. A write
    /// started after the tick's send window (a late wake, or a stall after it) counts the tick once as past the
    /// window, where the bus thread would stop the bus.
    fn send(
        &mut self,
        socket: &CanSocket,
        bus: &str,
        requests: &[ExtendedId],
        tick: u32,
        start: u64,
    ) -> Result<(), String> {
        let send_by = start + self.times.send_window;
        let mut past_window = false;
        for (slot, id) in requests.iter().enumerate() {
            past_window |= now_ns()? > send_by;
            let frame = CanDataFrame::new(*id, &frames::payload(tick, self.sent_count))
                .ok_or("frame build")?;
            match socket.write_frame(&CanFrame::Data(frame)) {
                Ok(()) => {
                    if let Some(s) = self.sent_at.get_mut(slot) {
                        *s = Some(now_ns()?);
                    }
                    self.sent_count = self.sent_count.wrapping_add(1);
                }
                Err(e) if link::queue_full(&e) => self.results.counts.tx_full += 1,
                Err(e) => return Err(format!("{bus}: write: {e}")),
            }
        }
        if past_window {
            self.results.counts.past_send_window += 1;
        }
        Ok(())
    }

    /// Read replies until every sent request is answered or reading time is over, recording when each was read.
    fn collect(
        &mut self,
        socket: &CanSocket,
        bus: &str,
        tick: u32,
        start: u64,
    ) -> Result<(), String> {
        let end = start + self.times.read_end;
        loop {
            let now = now_ns()?;
            let answered = self
                .read_at
                .iter()
                .zip(&self.sent_at)
                .all(|(r, s)| r.is_some() || s.is_none());
            if now >= end || answered {
                return Ok(());
            }
            link::wait(socket, Duration::from_nanos(end - now))
                .map_err(|e| format!("{bus}: {e}"))?;
            while let Some(frame) = link::read(socket).map_err(|e| format!("{bus}: {e}"))? {
                let t = now_ns()?;
                if let Some(slot) =
                    classify(&frame, tick, &mut self.results.counts, Some(&self.read_at))
                {
                    if let Some(r) = self.read_at.get_mut(slot) {
                        *r = Some(t);
                    }
                    if let Some(Some(s)) = self.sent_at.get(slot) {
                        self.results.round_trip.push(t.saturating_sub(*s));
                    }
                    self.results.reply_at.push(t.saturating_sub(start));
                }
                if t >= end {
                    break;
                }
            }
        }
    }
}

/// Create `ticks.csv` under `out` and write its header: one row per tick run, one reply column per slot.
fn open_csv(out: &Path, slots: usize) -> Result<BufWriter<File>, String> {
    let path = out.join("ticks.csv");
    let file = File::create(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut csv = BufWriter::with_capacity(CSV_BUFFER, file);
    let mut header = String::from("tick,wake_late_ns,last_reply_ns,missing");
    for s in 0..slots {
        let _ = write!(header, ",reply_{s}_ns");
    }
    writeln!(csv, "{header}").map_err(|e| e.to_string())?;
    Ok(csv)
}

/// One tick's CSV row. Times are from the tick's scheduled start; a reply never read is an empty field.
fn row(
    k: u64,
    late_ns: u64,
    last: Option<u64>,
    missing: usize,
    read_at: &[Option<u64>],
    start: u64,
) -> String {
    let mut row = format!(
        "{k},{late_ns},{},{missing}",
        last.map_or_else(String::new, |l| l.to_string())
    );
    for r in read_at {
        row.push(',');
        if let Some(r) = r {
            let _ = write!(row, "{}", r.saturating_sub(start));
        }
    }
    row
}

/// Sort one frame into the counts. Returns its slot if it is a reply to this tick's request not yet read.
fn classify(
    frame: &CanFrame,
    tick: u32,
    counts: &mut Counts,
    read_at: Option<&[Option<u64>]>,
) -> Option<usize> {
    match frame {
        CanFrame::Error(e) => {
            counts.error_frames += 1;
            if e.raw_id() & ERR_BUSOFF != 0 {
                counts.bus_off += 1;
            }
            None
        }
        CanFrame::Remote(_) => {
            counts.foreign += 1;
            None
        }
        CanFrame::Data(d) => {
            let Some(slot) = frames::reply_slot(d.raw_id()) else {
                // Our own requests don't come back (no loopback to the sender); anything else is foreign.
                if frames::request_slot(d.raw_id()).is_none() {
                    counts.foreign += 1;
                }
                return None;
            };
            match (frames::payload_tick(d.data()), read_at) {
                (Some(t), Some(read)) if t == tick => {
                    if read.get(slot).copied().flatten().is_some() {
                        counts.duplicate += 1;
                        None
                    } else {
                        Some(slot)
                    }
                }
                _ => {
                    counts.late += 1;
                    None
                }
            }
        }
    }
}
