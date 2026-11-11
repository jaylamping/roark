//! The host side: the bus loop's shape on the interface under test. Each tick it sends one request per slot, reads
//! replies until the tick is nearly over, and records when each one was read. It does what the runtime's bus thread
//! does to the socket (can.md section 2) and nothing it doesn't, so the numbers are the ones the runtime would see.

use std::fmt::Write as _;
use std::fs::{self, File};
use std::io::{BufWriter, Write as _};
use std::path::PathBuf;
use std::time::Duration;

use nix::errno::Errno;
use nix::sys::time::TimeSpec;
use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Frame, Socket};

use crate::frames;
use crate::link::{self, ENOBUFS};
use crate::stats::{Spread, micros};

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

/// The pass mark, from PLAN "Open with Joey" item 9 (the defaults until Joey changes them): 99.9 % of wakes under
/// 0.5 ms late, and 99.9 % of replies read by the collect deadline. Missing replies and kernel receive drops also fail.
const WAKE_LATE_BUDGET_NS: u64 = 500_000;
/// The share of replies that must be read by the collect deadline, in tenths of a percent.
const IN_TIME_PER_MILLE: u64 = 999;

/// Reading stops this far into the period, so the next tick's sends aren't delayed by this one's reads.
const READ_END_PCT: u64 = 90;
/// The first tick starts this long after the bench is ready.
const LEAD: Duration = Duration::from_millis(100);
/// `CAN_ERR_BUSOFF` in an error frame's ID (`linux/can/error.h`).
const ERR_BUSOFF: u32 = 0x0040;

/// What a run counted, beyond the times.
#[derive(Default)]
struct Counts {
    /// Ticks whose wake came after the tick had already ended.
    overruns: u64,
    /// Replies for this tick that were never read before the next.
    missing: u64,
    /// Replies read in a later tick than their request.
    late: u64,
    /// A second reply for the same slot and tick.
    duplicate: u64,
    /// Requests the interface's queue was too full to take (`ENOBUFS`).
    tx_full: u64,
    /// Error frames, of any kind.
    error_frames: u64,
    /// Error frames that say bus-off.
    bus_off: u64,
    /// Frames that aren't this bench's.
    foreign: u64,
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

/// Refuse settings the bench can't run.
fn check(args: &HostArgs) -> Result<(), String> {
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
    Ok(())
}

/// Run the host side and write `ticks.csv` and `summary.txt` under `args.out`. Returns the summary and whether the run
/// met the pass mark.
pub(crate) fn run(args: &HostArgs) -> Result<(String, bool), String> {
    check(args)?;
    let _runtime_lock = link::claim_runtime_lock()?;
    let bus = args.bus.as_str();
    let socket = link::open(bus).map_err(|e| format!("{bus}: {e}"))?;
    link::check_quiet(&socket, bus)?;
    fs::create_dir_all(&args.out).map_err(|e| format!("{}: {e}", args.out.display()))?;
    let before = link::counters(bus)?;
    let driver = link::driver(bus);
    let hw_stamps = socket.has_hw_timestamps();

    let requests: Vec<ExtendedId> = (0..args.slots)
        .map(|s| frames::request_id(s).and_then(ExtendedId::new))
        .collect::<Option<_>>()
        .ok_or("request ID out of range")?;
    let period = 1_000_000_000 / u64::from(args.hz);
    let deadline = period * u64::from(args.deadline_pct) / 100;
    let read_end = period * READ_END_PCT / 100;
    let ticks = u64::from(args.seconds) * u64::from(args.hz);

    let mut csv = open_csv(&args.out, args.slots)?;

    let mut counts = Counts::default();
    let mut wake_late = Vec::new();
    let mut reply_at = Vec::new();
    let mut round_trip = Vec::new();
    let mut last_reply = Vec::new();
    let mut sent_at = vec![None; args.slots];
    let mut read_at: Vec<Option<u64>> = vec![None; args.slots];
    let mut sent_count: u32 = 0;
    let origin = now_ns()? + u64::try_from(LEAD.as_nanos()).map_err(|e| e.to_string())?;

    for k in 0..ticks {
        let start = origin + k * period;
        sleep_until(start)?;
        let woke = now_ns()?;
        let late_ns = woke.saturating_sub(start);
        wake_late.push(late_ns);
        if late_ns >= period {
            counts.overruns += 1;
        }
        let tick = u32::try_from(k).map_err(|e| e.to_string())?;

        // Drain what came after last tick's reads: anything here is late.
        while let Some(frame) = link::read(&socket).map_err(|e| format!("{bus}: {e}"))? {
            classify(&frame, tick, &mut counts, None);
        }

        sent_at.fill(None);
        read_at.fill(None);
        send(
            &socket,
            bus,
            &requests,
            tick,
            &mut sent_count,
            &mut sent_at,
            &mut counts,
        )?;

        let times = Times {
            start,
            end: start + read_end,
        };
        collect(
            &socket,
            bus,
            tick,
            times,
            &sent_at,
            &mut read_at,
            &mut counts,
            &mut round_trip,
            &mut reply_at,
        )?;

        let missing = read_at
            .iter()
            .zip(&sent_at)
            .filter(|(r, s)| r.is_none() && s.is_some())
            .count();
        counts.missing += u64::try_from(missing).map_err(|e| e.to_string())?;
        let last = read_at
            .iter()
            .flatten()
            .max()
            .map(|t| t.saturating_sub(start));
        if missing == 0
            && let Some(l) = last
        {
            last_reply.push(l);
        }
        let row = row(k, late_ns, last, missing, &read_at, start);
        writeln!(csv, "{row}").map_err(|e| e.to_string())?;
    }
    csv.flush().map_err(|e| e.to_string())?;

    let after = link::counters(bus)?;
    let (summary, pass) = summary(
        args, &driver, hw_stamps, deadline, &counts, wake_late, reply_at, round_trip, last_reply,
        &before, &after,
    );
    let path = args.out.join("summary.txt");
    fs::write(&path, &summary).map_err(|e| format!("{}: {e}", path.display()))?;
    Ok((summary, pass))
}

/// Create `ticks.csv` under `out` and write its header: one row per tick, one reply column per slot.
fn open_csv(out: &std::path::Path, slots: usize) -> Result<BufWriter<File>, String> {
    let path = out.join("ticks.csv");
    let mut csv =
        BufWriter::new(File::create(&path).map_err(|e| format!("{}: {e}", path.display()))?);
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

/// Send one request per slot, once each; a full queue drops it and counts it, as the bus thread does.
fn send(
    socket: &CanSocket,
    bus: &str,
    requests: &[ExtendedId],
    tick: u32,
    sent_count: &mut u32,
    sent_at: &mut [Option<u64>],
    counts: &mut Counts,
) -> Result<(), String> {
    for (slot, id) in requests.iter().enumerate() {
        let frame =
            CanDataFrame::new(*id, &frames::payload(tick, *sent_count)).ok_or("frame build")?;
        match socket.write_frame(&CanFrame::Data(frame)) {
            Ok(()) => {
                if let Some(s) = sent_at.get_mut(slot) {
                    *s = Some(now_ns()?);
                }
                *sent_count = sent_count.wrapping_add(1);
            }
            Err(e) if e.raw_os_error() == Some(ENOBUFS) => counts.tx_full += 1,
            Err(e) => return Err(format!("{bus}: write: {e}")),
        }
    }
    Ok(())
}

/// The tick's start and the time reading stops, on the monotonic clock.
#[derive(Clone, Copy)]
struct Times {
    start: u64,
    end: u64,
}

/// Read replies until every sent request is answered or reading time is over, recording when each was read.
#[expect(
    clippy::too_many_arguments,
    reason = "the tick's state, passed rather than bundled for one call site"
)]
fn collect(
    socket: &CanSocket,
    bus: &str,
    tick: u32,
    times: Times,
    sent_at: &[Option<u64>],
    read_at: &mut [Option<u64>],
    counts: &mut Counts,
    round_trip: &mut Vec<u64>,
    reply_at: &mut Vec<u64>,
) -> Result<(), String> {
    loop {
        let now = now_ns()?;
        if now >= times.end
            || read_at
                .iter()
                .zip(sent_at)
                .all(|(r, s)| r.is_some() || s.is_none())
        {
            return Ok(());
        }
        link::wait(socket, Duration::from_nanos(times.end - now))
            .map_err(|e| format!("{bus}: {e}"))?;
        while let Some(frame) = link::read(socket).map_err(|e| format!("{bus}: {e}"))? {
            let t = now_ns()?;
            if let Some(slot) = classify(&frame, tick, counts, Some(read_at)) {
                if let Some(r) = read_at.get_mut(slot) {
                    *r = Some(t);
                }
                if let Some(Some(s)) = sent_at.get(slot) {
                    round_trip.push(t.saturating_sub(*s));
                }
                reply_at.push(t.saturating_sub(times.start));
            }
        }
    }
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

/// The run's summary: settings, what the interface is, the time spreads, the counts, the kernel's counter changes and
/// the verdict against the pass mark, which is also returned.
#[expect(
    clippy::too_many_arguments,
    reason = "one call site; the pieces are the run's results"
)]
fn summary(
    args: &HostArgs,
    driver: &str,
    hw_stamps: bool,
    deadline: u64,
    counts: &Counts,
    wake_late: Vec<u64>,
    reply_at: Vec<u64>,
    round_trip: Vec<u64>,
    last_reply: Vec<u64>,
    before: &serde_json::Value,
    after: &serde_json::Value,
) -> (String, bool) {
    let wake_late = Spread::new(wake_late);
    let reply_at = Spread::new(reply_at);
    let round_trip = Spread::new(round_trip);
    let last_reply = Spread::new(last_reply);
    let expected = reply_at.len() as u64 + counts.missing;
    let in_time = reply_at.within(deadline) as u64;
    #[expect(clippy::cast_precision_loss, reason = "display only")]
    let share = if expected == 0 {
        0.0
    } else {
        in_time as f64 * 100.0 / expected as f64
    };
    let mut s = String::new();
    let mut line = |l: String| {
        s.push_str(&l);
        s.push('\n');
    };
    line(format!(
        "can-bench host, build {}",
        env!("CARGO_PKG_VERSION")
    ));
    line(format!(
        "bus {} driver {driver}, hardware timestamps {}",
        args.bus,
        if hw_stamps { "yes" } else { "no" }
    ));
    line(format!(
        "{} Hz, {} slots, {} s, collect deadline {}% = {:.0} us",
        args.hz,
        args.slots,
        args.seconds,
        args.deadline_pct,
        micros(deadline)
    ));
    line(String::new());
    line(wake_late.line("wake late"));
    line(round_trip.line("round trip"));
    line(reply_at.line("reply after tick start"));
    line(last_reply.line("last reply of tick"));
    line(String::new());
    line(format!(
        "replies by the deadline: {in_time} of {expected} ({share:.4} %)"
    ));
    line(format!(
        "missing {}  late {}  duplicate {}  tx queue full {}  overruns {}",
        counts.missing, counts.late, counts.duplicate, counts.tx_full, counts.overruns
    ));
    line(format!(
        "error frames {}  bus-off {}  foreign frames {}",
        counts.error_frames, counts.bus_off, counts.foreign
    ));
    line(String::new());
    line("kernel counters, change over the run:".to_owned());
    let mut kernel_drops = 0;
    for (dir, keys) in [
        ("rx", &["packets", "errors", "dropped", "over_errors"][..]),
        ("tx", &["packets", "errors", "dropped"][..]),
    ] {
        let mut parts = Vec::new();
        for key in keys {
            let get =
                |v: &serde_json::Value| v.get(0)?.get("stats64")?.get(dir)?.get(*key)?.as_u64();
            if let (Some(a), Some(b)) = (get(before), get(after)) {
                if dir == "rx" && (*key == "dropped" || *key == "over_errors") {
                    kernel_drops += b.saturating_sub(a);
                }
                parts.push(format!("{key} {}", b.saturating_sub(a)));
            }
        }
        line(format!("  {dir}: {}", parts.join("  ")));
    }
    let restarts = |v: &serde_json::Value| {
        v.get(0)?
            .get("linkinfo")?
            .get("info_xstats")?
            .get("restarts")?
            .as_u64()
    };
    if let (Some(a), Some(b)) = (restarts(before), restarts(after)) {
        line(format!("  restarts {}", b.saturating_sub(a)));
    }
    let fails = verdict(
        &wake_late,
        share,
        in_time,
        expected,
        counts.missing,
        kernel_drops,
    );
    line(String::new());
    let pass = fails.is_empty();
    line(if pass {
        "PASS".to_owned()
    } else {
        format!("FAIL: {}", fails.join("; "))
    });
    (s, pass)
}

/// What failed the pass mark; empty for a pass.
fn verdict(
    wake_late: &Spread,
    share: f64,
    in_time: u64,
    expected: u64,
    missing: u64,
    kernel_drops: u64,
) -> Vec<String> {
    let mut fails = Vec::new();
    match wake_late.at(9990) {
        Some(w) if w < WAKE_LATE_BUDGET_NS => {}
        w => fails.push(format!(
            "wake late p99.9 {} us, budget {:.0} us",
            w.map_or_else(|| "-".to_owned(), |w| format!("{:.0}", micros(w))),
            micros(WAKE_LATE_BUDGET_NS)
        )),
    }
    if expected == 0 || in_time * 1000 < expected * IN_TIME_PER_MILLE {
        fails.push(format!(
            "{share:.4} % of replies by the deadline, need 99.9 %"
        ));
    }
    if missing > 0 {
        fails.push(format!("{missing} replies missing"));
    }
    if kernel_drops > 0 {
        fails.push(format!("{kernel_drops} frames dropped by the kernel"));
    }
    fails
}
