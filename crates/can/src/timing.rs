//! The tick's timing and the drive-side times it is checked against: what a period, a collect, a send window and the
//! silence counts may be, refused at startup when they break the tick's promises (safety.md section 4).

use robstride::CanTimeout;

/// The drives' own command timeout, the `canTimeout` the host writes ([`CanTimeout::RUNTIME`], in 50 µs steps): three
/// periods of feedback must fit inside it (PLAN.md item 3 Timing).
#[expect(
    clippy::as_conversions,
    reason = "u32 to u64 widens losslessly, and u64::from isn't const"
)]
pub const DRIVE_TIMEOUT_NS: u64 = CanTimeout::RUNTIME.ticks() as u64 * 50_000;

/// How long a drive may take from an Enable the socket took to its first Run status before its missed replies count
/// again (PLAN.md item 2 Enable one drive: measured 1.4 to 10.3 ms, refuse after 50 ms).
pub const ENABLE_TO_RUN_NS: u64 = 50_000_000;

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
    /// tick to send reporting off after it, silence counts of at least one that fire before the drives' timeout, and a
    /// slow reply window that fits between the collect deadline and the next tick.
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
        } else if self.silent_ticks == 0 || spans_timeout(self.silent_ticks, period_ns) {
            Err(TimingError::SilentTicks {
                silent_ticks: self.silent_ticks,
                period_ns,
            })
        } else if self.silence_misses == 0 || spans_timeout(self.silence_misses, period_ns) {
            Err(TimingError::SilenceMisses {
                silence_misses: self.silence_misses,
                period_ns,
            })
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
    /// `silent_ticks` is zero, or so many that the drives' timeout passes first (the count would never stop a bus).
    #[error(
        "silent_ticks {silent_ticks} must be at least 1, and that many periods of {period_ns} ns under the drives' \
         {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    SilentTicks {
        /// The count.
        silent_ticks: u32,
        /// The period.
        period_ns: u64,
    },
    /// `silence_misses` is zero, or so many that the drives' timeout passes first (the count would never stop a limb).
    #[error(
        "silence_misses {silence_misses} must be at least 1, and that many periods of {period_ns} ns under the \
         drives' {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    SilenceMisses {
        /// The count.
        silence_misses: u32,
        /// The period.
        period_ns: u64,
    },
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

/// Whether `count` periods reach the drives' timeout: a silence count that long turns its rule off (safety.md section 4:
/// no config value turns a protection off).
const fn spans_timeout(count: u32, period_ns: u64) -> bool {
    // `u64::from` isn't const; u32 widens losslessly.
    #[expect(clippy::as_conversions, reason = "u32 to u64 widens losslessly")]
    let count = count as u64;
    count.saturating_mul(period_ns) >= DRIVE_TIMEOUT_NS
}
