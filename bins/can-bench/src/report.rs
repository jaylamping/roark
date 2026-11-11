//! What a host run measured, and its summary: the spreads, the counts, the kernel's counter changes and the verdict.

use crate::host::{HostArgs, Times};
use crate::stats::{Spread, micros};

/// PLAN "Open with Joey" item 9 (the realtime budget, the defaults until Joey changes it): tick-start jitter of 0.5 ms
/// and 99.9 % of replies before the collect deadline. Kept here only because the verdict needs the numbers; PLAN holds
/// them, and a change there is made here in the same PR.
const WAKE_LATE_BUDGET_NS: u64 = 500_000;
/// Item 9's share of replies by the collect deadline, in tenths of a percent.
const IN_TIME_PER_MILLE: u64 = 999;

/// What a run counted, beyond the times.
#[derive(Default)]
pub(crate) struct Counts {
    /// Ticks never run: their reading time was over before the wake.
    pub(crate) skipped: u64,
    /// Wakes later than the send window: each would stop the bus in the runtime.
    pub(crate) past_send_window: u64,
    /// Replies for this tick that were never read before the next.
    pub(crate) missing: u64,
    /// Replies read in a later tick than their request.
    pub(crate) late: u64,
    /// A second reply for the same slot and tick.
    pub(crate) duplicate: u64,
    /// Requests the interface's queue was too full to take (`ENOBUFS` or `EAGAIN`).
    pub(crate) tx_full: u64,
    /// Error frames, of any kind.
    pub(crate) error_frames: u64,
    /// Error frames that say bus-off.
    pub(crate) bus_off: u64,
    /// Frames that aren't this bench's.
    pub(crate) foreign: u64,
}

/// The samples and counts a run collects, made with room for the whole run so the measured loop doesn't reallocate.
pub(crate) struct Results {
    pub(crate) counts: Counts,
    pub(crate) wake_late: Vec<u64>,
    pub(crate) reply_at: Vec<u64>,
    pub(crate) round_trip: Vec<u64>,
    pub(crate) last_reply: Vec<u64>,
}

impl Results {
    pub(crate) fn with_capacity(ticks: usize, slots: usize) -> Self {
        Self {
            counts: Counts::default(),
            wake_late: Vec::with_capacity(ticks),
            reply_at: Vec::with_capacity(ticks.saturating_mul(slots)),
            round_trip: Vec::with_capacity(ticks.saturating_mul(slots)),
            last_reply: Vec::with_capacity(ticks),
        }
    }
}

/// A finished (or ended) run, for its summary.
pub(crate) struct Run<'a> {
    pub(crate) args: &'a HostArgs,
    pub(crate) driver: &'a str,
    pub(crate) hw_stamps: bool,
    pub(crate) times: Times,
    pub(crate) results: Results,
    pub(crate) before: Option<&'a serde_json::Value>,
    pub(crate) after: Option<&'a serde_json::Value>,
    /// Why the run ended before its time, if it did.
    pub(crate) ended: Option<&'a str>,
}

/// The run's summary, ending in the verdict against the pass mark, which is also returned.
pub(crate) fn summary(run: &Run<'_>) -> (String, bool) {
    let r = &run.results;
    let c = &r.counts;
    let wake_late = Spread::new(r.wake_late.clone());
    let reply_at = Spread::new(r.reply_at.clone());
    let round_trip = Spread::new(r.round_trip.clone());
    let last_reply = Spread::new(r.last_reply.clone());
    let expected = reply_at.len() as u64 + c.missing;
    let in_time = reply_at.within(run.times.deadline) as u64;
    #[expect(clippy::cast_precision_loss, reason = "display only")]
    let share = if expected == 0 {
        0.0
    } else {
        in_time as f64 * 100.0 / expected as f64
    };
    let mut lines = vec![
        format!("can-bench host, build {}", env!("ROARK_GIT_REVISION")),
        format!(
            "bus {} driver {}, hardware timestamps {}",
            run.args.bus,
            run.driver,
            if run.hw_stamps { "yes" } else { "no" }
        ),
        format!(
            "{} Hz, {} slots, {} s, collect deadline {}% = {:.0} us, send window {:.0} us",
            run.args.hz,
            run.args.slots,
            run.args.seconds,
            run.args.deadline_pct,
            micros(run.times.deadline),
            micros(run.times.send_window)
        ),
        String::new(),
        wake_late.line("wake late"),
        round_trip.line("round trip"),
        reply_at.line("reply after tick start"),
        last_reply.line("last reply of tick"),
        String::new(),
        format!("replies by the deadline: {in_time} of {expected} ({share:.4} %)"),
        format!(
            "missing {}  late {}  duplicate {}  tx queue full {}",
            c.missing, c.late, c.duplicate, c.tx_full
        ),
        format!(
            "wakes past the send window {}  ticks skipped {}",
            c.past_send_window, c.skipped
        ),
        format!(
            "error frames {}  bus-off {}  foreign frames {}",
            c.error_frames, c.bus_off, c.foreign
        ),
        String::new(),
    ];
    let (kernel, kernel_drops) = kernel_lines(run.before, run.after);
    lines.extend(kernel);
    let mut fails = verdict(&wake_late, c, share, in_time, expected, kernel_drops);
    if let Some(why) = run.ended {
        lines.push(format!("run ended early: {why}"));
        fails.insert(0, format!("run ended early ({why})"));
    }
    lines.push(String::new());
    let pass = fails.is_empty();
    lines.push(if pass {
        "PASS".to_owned()
    } else {
        format!("FAIL: {}", fails.join("; "))
    });
    let mut s = lines.join("\n");
    s.push('\n');
    (s, pass)
}

/// The kernel's link counters' change over the run, and the receive drops among them. `None` when `ip` couldn't be read
/// at either end.
fn kernel_lines(
    before: Option<&serde_json::Value>,
    after: Option<&serde_json::Value>,
) -> (Vec<String>, Option<u64>) {
    let (Some(before), Some(after)) = (before, after) else {
        return (
            vec!["kernel counters: not read (ip failed)".to_owned()],
            None,
        );
    };
    let mut lines = vec!["kernel counters, change over the run:".to_owned()];
    let mut drops = None;
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
                    drops = Some(drops.unwrap_or(0) + b.saturating_sub(a));
                }
                parts.push(format!("{key} {}", b.saturating_sub(a)));
            }
        }
        lines.push(format!("  {dir}: {}", parts.join("  ")));
    }
    let restarts = |v: &serde_json::Value| {
        v.get(0)?
            .get("linkinfo")?
            .get("info_xstats")?
            .get("restarts")?
            .as_u64()
    };
    if let (Some(a), Some(b)) = (restarts(before), restarts(after)) {
        lines.push(format!("  restarts {}", b.saturating_sub(a)));
    }
    (lines, drops)
}

/// What failed the pass mark; empty for a pass. The first two checks are PLAN item 9's. The rest are this bench's own
/// (docs/can-interface-comparison.md, "Pass mark"): each is a loss the runtime would act on.
fn verdict(
    wake_late: &Spread,
    c: &Counts,
    share: f64,
    in_time: u64,
    expected: u64,
    kernel_drops: Option<u64>,
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
    for (n, what) in [
        (c.missing, "replies missing"),
        (c.tx_full, "requests refused by a full queue"),
        (c.past_send_window, "wakes past the send window"),
        (c.skipped, "ticks skipped"),
    ] {
        if n > 0 {
            fails.push(format!("{n} {what}"));
        }
    }
    match kernel_drops {
        Some(0) => {}
        Some(n) => fails.push(format!("{n} frames dropped by the kernel")),
        None => fails.push("kernel receive drops unknown (ip counters unread)".to_owned()),
    }
    fails
}
