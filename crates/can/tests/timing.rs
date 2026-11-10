//! The tick's timing checked at startup without a socket: every rule `Timing::check` enforces, one row per rule and its
//! boundary (safety.md section 4).

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use can::{BusTick, ConfigError, DRIVE_TIMEOUT_NS, Timing, TimingError};
use common::{id, one_limb};

/// Guards: safety - timing that breaks the tick's promises is refused at startup, never quietly replaced, one row per
/// rule and its boundary, the silence counts apart (`silence_counts_must_fire_before_the_drive_timeout`): a feedback
/// limit that with the write slack and the read lag reaches the drives' 50 ms timeout is refused (units-and-frames.md
/// section 5); a stop window must fit the post-Disable silence and a tick to send reporting off; a slow reply window
/// must be non-zero and end, from the collect deadline, before the next tick (the shell sends slow requests only after
/// the deadline, so a window that fills the slack lets nothing go); a slow request may wait queued at least a tick; and
/// the slowest rate the defaults allow is 86 Hz, since at 85 Hz three misses, the tick that stops on them and the write
/// slack reach the timeout (safety.md: invalid configuration is an error; PLAN.md item 3: parameter traffic only in the
/// slack).
#[test]
#[expect(
    clippy::too_many_lines,
    reason = "one table, one row per timing rule and its boundary"
)]
fn timing_that_breaks_the_tick_is_refused() {
    let base = Timing::at_hz(250);
    let fits = base.disable_silence_ns + base.period_ns;
    // At 250 Hz the write slack is the 1 ms send window, and the read lag period - collect + send window, 4 - 2.4 + 1 ms.
    let (slack, lag) = (1_000_000, 2_600_000);
    let rows = [
        ("no rate", Timing::at_hz(0), Some(TimingError::NoPeriod)),
        (
            "no send window",
            Timing {
                send_window_ns: 0,
                ..base
            },
            Some(TimingError::SendWindow {
                send_window_ns: 0,
                collect_ns: base.collect_ns,
            }),
        ),
        (
            "send window past collect",
            Timing {
                send_window_ns: base.collect_ns + 1,
                ..base
            },
            Some(TimingError::SendWindow {
                send_window_ns: base.collect_ns + 1,
                collect_ns: base.collect_ns,
            }),
        ),
        (
            "collect at the period",
            Timing {
                collect_ns: base.period_ns,
                ..base
            },
            Some(TimingError::Collect {
                collect_ns: base.period_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "feedback under a period",
            Timing {
                feedback_limit_ns: base.period_ns - 1,
                ..base
            },
            Some(TimingError::FeedbackLimit {
                feedback_limit_ns: base.period_ns - 1,
                period_ns: base.period_ns,
            }),
        ),
        (
            "feedback plus slack and lag reaches the timeout",
            Timing {
                feedback_limit_ns: DRIVE_TIMEOUT_NS - slack - lag,
                ..base
            },
            Some(TimingError::FeedbackAge {
                feedback_limit_ns: 46_400_000,
                write_slack_ns: slack,
                read_lag_ns: lag,
            }),
        ),
        (
            "feedback plus slack and lag just under the timeout",
            Timing {
                feedback_limit_ns: DRIVE_TIMEOUT_NS - slack - lag - 1,
                ..base
            },
            None,
        ),
        (
            "85 Hz",
            Timing::at_hz(85),
            Some(TimingError::SilenceMisses {
                silence_misses: 3,
                period_ns: 11_764_706,
                write_slack_ns: 2_941_176,
            }),
        ),
        ("86 Hz", Timing::at_hz(86), None),
        (
            "stop window too short",
            Timing {
                stop_confirm_ns: fits - 1,
                ..base
            },
            Some(TimingError::StopWindow {
                stop_confirm_ns: fits - 1,
                disable_silence_ns: base.disable_silence_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "stop window just fits",
            Timing {
                stop_confirm_ns: fits,
                ..base
            },
            None,
        ),
        (
            "no slow reply window",
            Timing {
                slow_reply_ns: 0,
                ..base
            },
            Some(TimingError::SlowReply {
                slow_reply_ns: 0,
                collect_ns: base.collect_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "slow reply window fills the slack",
            Timing {
                slow_reply_ns: base.period_ns - base.collect_ns,
                ..base
            },
            Some(TimingError::SlowReply {
                slow_reply_ns: base.period_ns - base.collect_ns,
                collect_ns: base.collect_ns,
                period_ns: base.period_ns,
            }),
        ),
        (
            "slow reply window just fits the slack",
            Timing {
                slow_reply_ns: base.period_ns - base.collect_ns - 1,
                ..base
            },
            None,
        ),
        (
            "no tick a slow request may wait queued",
            Timing {
                slow_queue_ticks: 0,
                ..base
            },
            Some(TimingError::NoSlowQueueTicks),
        ),
        ("250 Hz", base, None),
    ];
    for (name, timing, refused) in rows {
        assert_eq!(
            BusTick::new(&one_limb(&[id(101)]), timing).err(),
            refused.map(ConfigError::Timing),
            "{name}: {timing:?}"
        );
    }
}

/// Guards: safety - each silence count must be at least one and stop before the drives time out on their own: zero
/// would stop an active bus at its first tick or every limb at its first send, and a count whose span, plus the write
/// slack (the stop's Disable goes out up to a send window after the tick that stops), reaches the drives' timeout turns
/// its rule off. Silent ticks span their count of periods; missed replies one more, the tick that stops on them
/// (safety.md section 4: no config value turns a protection off; PLAN.md items 3 and 6).
#[test]
#[expect(
    clippy::too_many_lines,
    reason = "one table, one row per silence rule and its boundary"
)]
fn silence_counts_must_fire_before_the_drive_timeout() {
    let base = Timing::at_hz(250);
    // At 250 Hz the write slack is the 1 ms send window.
    let slack = 1_000_000;
    let rows = [
        (
            "no silent ticks",
            Timing {
                silent_ticks: 0,
                ..base
            },
            Some(TimingError::NoSilentTicks),
        ),
        (
            "silent ticks span the timeout: 13 of 4 ms plus 1 ms",
            Timing {
                silent_ticks: 13,
                ..base
            },
            Some(TimingError::SilentTicks {
                silent_ticks: 13,
                period_ns: base.period_ns,
                write_slack_ns: slack,
            }),
        ),
        (
            "a tick fewer fits",
            Timing {
                silent_ticks: 12,
                ..base
            },
            None,
        ),
        (
            "the send window alone tips 48 ms of silent ticks to exactly the timeout",
            Timing {
                silent_ticks: 12,
                send_window_ns: 2_000_000,
                ..base
            },
            Some(TimingError::SilentTicks {
                silent_ticks: 12,
                period_ns: base.period_ns,
                write_slack_ns: 2_000_000,
            }),
        ),
        (
            "a send window one ns shorter fits",
            Timing {
                silent_ticks: 12,
                send_window_ns: 1_999_999,
                ..base
            },
            None,
        ),
        (
            "silent ticks that never end",
            Timing {
                silent_ticks: u32::MAX,
                ..base
            },
            Some(TimingError::SilentTicks {
                silent_ticks: u32::MAX,
                period_ns: base.period_ns,
                write_slack_ns: slack,
            }),
        ),
        (
            "no silence misses",
            Timing {
                silence_misses: 0,
                ..base
            },
            Some(TimingError::NoSilenceMisses),
        ),
        (
            "misses span the timeout: 12 and the stopping tick, of 4 ms, plus 1 ms",
            Timing {
                silence_misses: 12,
                ..base
            },
            Some(TimingError::SilenceMisses {
                silence_misses: 12,
                period_ns: base.period_ns,
                write_slack_ns: slack,
            }),
        ),
        (
            "a miss fewer fits",
            Timing {
                silence_misses: 11,
                ..base
            },
            None,
        ),
        (
            "the send window alone tips 48 ms of misses to exactly the timeout",
            Timing {
                silence_misses: 11,
                send_window_ns: 2_000_000,
                ..base
            },
            Some(TimingError::SilenceMisses {
                silence_misses: 11,
                period_ns: base.period_ns,
                write_slack_ns: 2_000_000,
            }),
        ),
        (
            "a send window one ns shorter fits",
            Timing {
                silence_misses: 11,
                send_window_ns: 1_999_999,
                ..base
            },
            None,
        ),
        (
            "misses that never end",
            Timing {
                silence_misses: u32::MAX,
                ..base
            },
            Some(TimingError::SilenceMisses {
                silence_misses: u32::MAX,
                period_ns: base.period_ns,
                write_slack_ns: slack,
            }),
        ),
    ];
    for (name, timing, refused) in rows {
        assert_eq!(
            BusTick::new(&one_limb(&[id(101)]), timing).err(),
            refused.map(ConfigError::Timing),
            "{name}: {timing:?}"
        );
    }
}
