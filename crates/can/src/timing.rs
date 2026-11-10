//! The tick's timing and the drive-side times it is checked against: what a period, a collect, a send window and the
//! silence counts may be, refused at startup when they break the tick's promises (safety.md section 4).

use robstride::CanTimeout;

/// The drives' own command timeout, the `canTimeout` the host writes ([`CanTimeout::RUNTIME`], PLAN.md item 6). The age
/// of the feedback motion is written on (units-and-frames.md section 5), the span of control silence that stops the
/// bus's limbs and the span of a drive's missed replies that stops its limb (safety.md section 4) must each stay under
/// it ([`Timing::check`]).
pub const DRIVE_TIMEOUT_NS: u64 = match CanTimeout::RUNTIME.nanos() {
    Some(ns) => ns,
    // Evaluated at compile time: a RUNTIME that turned the timeout off fails the build, it never runs.
    None => panic!("canTimeout RUNTIME must be a timeout, not off"),
};

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
    /// How late after its scheduled start a tick may still send a command. Waking later is a missed deadline: it stops
    /// every active limb and holds the tick for every idle one ([`BusTick::begin`](crate::BusTick::begin)). A quarter
    /// period by default: provisional, to be tuned on the real adapter (PLAN step 8).
    pub send_window_ns: u64,
    /// When the tick stops collecting replies, from its scheduled start (about 60 % of the period, PLAN.md item 3).
    pub collect_ns: u64,
    /// The oldest a drive's last fresh status may be when motion is sent to it (three periods: 12 ms at 250 Hz, PLAN.md
    /// item 6 Silence row).
    pub feedback_limit_ns: u64,
    /// How long a stop sends Disable to each of its drives not yet confirmed, from the stop's start (the reply to the
    /// last of them may still confirm in [`Self::stop_replies_ns`]; the stop ends by [`Self::stop_max_ns`]); and the
    /// post-Disable silence window, in which missed replies aren't counted (100 ms; PLAN.md item 2 Silence windows says
    /// which Disables open it).
    pub stop_confirm_ns: u64,
    /// How long a drive drops frames after a Disable; its reporting-off waits this long after its confirmation, and a
    /// drive that never confirms gets none (post-Disable silences up to 48.7 ms measured, PLAN.md item 2).
    pub disable_silence_ns: u64,
    /// Ticks without a fresh batch, while a limb is active, that stop every limb on the bus (PLAN.md item 3: two).
    pub silent_ticks: u32,
    /// Consecutive commands a drive may leave unanswered by the collect deadline before its limb stops (PLAN.md item 6
    /// Silence row: three).
    pub silence_misses: u32,
}

impl Timing {
    /// The defaults at `hz` ticks a second (250 by default, PLAN.md item 3), the period rounded up to a whole
    /// nanosecond so the rate is never above `hz`. A rate [`Self::check`] refuses (0, or one slow enough that three
    /// periods plus the write slack and the read lag reach the drives' timeout) gives timing it refuses.
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
        }
    }

    /// Whether this timing keeps the tick's promises, each rule once, in this order:
    ///
    /// - a period ([`TimingError::NoPeriod`]), a send window inside the collect window ([`TimingError::SendWindow`]),
    ///   and the collect deadline inside the period ([`TimingError::Collect`]);
    /// - at least a period of feedback ([`TimingError::FeedbackLimit`]), with the feedback limit plus the write slack
    ///   plus the read lag (the oldest a status motion is written on can really be, units-and-frames.md section 5)
    ///   under the drives' timeout ([`TimingError::FeedbackAge`]);
    /// - a stop window that fits the post-Disable silence and a tick to send reporting off after it
    ///   ([`TimingError::StopWindow`]);
    /// - at least one silent tick ([`TimingError::NoSilentTicks`]), with the silent ticks plus the write slack (from
    ///   the last command to the stop's Disable) under the drives' timeout ([`TimingError::SilentTicks`]), so a silent
    ///   control is stopped before the drives give up on it;
    /// - at least one missed reply ([`TimingError::NoSilenceMisses`]), with the misses plus the tick that stops on them
    ///   plus the write slack (from the first unanswered command to the stop's Disable) under the drives' timeout
    ///   ([`TimingError::SilenceMisses`]), so a silent drive's limb is stopped before the drives give up.
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
        } else if self.feedback_limit_ns < period_ns {
            Err(TimingError::FeedbackLimit {
                feedback_limit_ns: self.feedback_limit_ns,
                period_ns,
            })
        } else if self
            .feedback_limit_ns
            .saturating_add(self.write_slack_ns())
            .saturating_add(self.read_lag_ns())
            >= DRIVE_TIMEOUT_NS
        {
            Err(TimingError::FeedbackAge {
                feedback_limit_ns: self.feedback_limit_ns,
                write_slack_ns: self.write_slack_ns(),
                read_lag_ns: self.read_lag_ns(),
            })
        } else if self.stop_confirm_ns < self.disable_silence_ns.saturating_add(period_ns) {
            Err(TimingError::StopWindow {
                stop_confirm_ns: self.stop_confirm_ns,
                disable_silence_ns: self.disable_silence_ns,
                period_ns,
            })
        } else if self.silent_ticks == 0 {
            Err(TimingError::NoSilentTicks)
        } else if self.spans_timeout(self.silent_ticks) {
            Err(TimingError::SilentTicks {
                silent_ticks: self.silent_ticks,
                period_ns,
                write_slack_ns: self.write_slack_ns(),
            })
        } else if self.silence_misses == 0 {
            Err(TimingError::NoSilenceMisses)
        // Misses are counted at a tick's end and stop the limb at the next tick's start: one period more than the count.
        } else if self.spans_timeout(self.silence_misses.saturating_add(1)) {
            Err(TimingError::SilenceMisses {
                silence_misses: self.silence_misses,
                period_ns,
                write_slack_ns: self.write_slack_ns(),
            })
        } else {
            Ok(())
        }
    }

    /// How long after a stop's start a Reset still confirms a drive, the reply allowance: the confirm window, a period
    /// and the send window. The stop's start is its tick's wake and the last Disable goes on the last tick that wakes
    /// inside the window, so that tick is scheduled before the window closes and the next one before a period after
    /// that; that tick may wake up to a send window late and still be on time, and its drain, before the wake ends,
    /// reads the reply to the last Disable at the latest. A Reset read later confirms nothing, so its drive gets no
    /// reporting off. A tick that wakes past its send window is a missed deadline, outside this promise. Provisional:
    /// Disable-to-Reset latency is measured on the real adapter (PLAN step 8).
    #[must_use]
    pub const fn stop_replies_ns(&self) -> u64 {
        self.stop_confirm_ns
            .saturating_add(self.period_ns)
            .saturating_add(self.send_window_ns)
    }

    /// The latest a stop ends, from its start: the reply allowance ([`Self::stop_replies_ns`]), the post-Disable
    /// silence, two periods and the send window. A drive confirmed just before the allowance closes has its reporting
    /// off due just before the allowance plus the silence. The first tick scheduled at or after that is due within a
    /// period and offers it, however it wakes; the next is scheduled a period later and, waking up to a send window
    /// late, still before this bound. So on ticks that wake inside their send windows the last drive that can confirm
    /// is offered its reporting off at least twice. A stop ends sooner once every drive has confirmed and its
    /// reporting off was taken, or once the allowance has closed and no confirmed drive's reporting off is still
    /// unsent; the bus tick decides it at each tick's start and end.
    #[must_use]
    pub const fn stop_max_ns(&self) -> u64 {
        self.stop_replies_ns()
            .saturating_add(self.disable_silence_ns)
            .saturating_add(self.period_ns.saturating_mul(2))
            .saturating_add(self.send_window_ns)
    }

    /// The most a tick may wake after its scheduled start and still send: the send window, since a wake exactly at its
    /// close isn't late. Motion passes its staleness check at the wake and, as a command that expires, is written by
    /// the window's close or not at all. A stop's Disable is planned on a wake up to this much after the tick that
    /// found control silent, or a drive's misses, was due, but never expires ([`Send::expires`](crate::Send::expires)):
    /// it is written after that wake by the shell's wake-to-write time, which this bound leaves out and PLAN step 8
    /// measures.
    const fn write_slack_ns(&self) -> u64 {
        self.send_window_ns
    }

    /// The most a status motion is sent on was read after its arrival: from the collect deadline to the close of the
    /// next tick's send window (units-and-frames.md section 5).
    const fn read_lag_ns(&self) -> u64 {
        self.period_ns
            .saturating_sub(self.collect_ns)
            .saturating_add(self.send_window_ns)
    }

    /// Whether `periods` periods plus the write slack reach the drives' timeout: a silence count that long would stop
    /// only after the drives had given up on their own, or never (safety.md section 4: no config value turns a
    /// protection off).
    const fn spans_timeout(&self, periods: u32) -> bool {
        widen(periods)
            .saturating_mul(self.period_ns)
            .saturating_add(self.write_slack_ns())
            >= DRIVE_TIMEOUT_NS
    }
}

#[expect(
    clippy::as_conversions,
    reason = "u32 to u64 widens losslessly, and u64::from isn't const"
)]
const fn widen(n: u32) -> u64 {
    n as u64
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
    /// The feedback limit is under a period.
    #[error("feedback limit {feedback_limit_ns} ns must be at least the period, {period_ns} ns")]
    FeedbackLimit {
        /// The feedback limit.
        feedback_limit_ns: u64,
        /// The period.
        period_ns: u64,
    },
    /// The feedback limit plus the write slack plus the read lag reaches the drives' timeout: motion could be written
    /// on a status older, in real age, than the drive's own patience.
    #[error(
        "feedback limit {feedback_limit_ns} ns plus write slack {write_slack_ns} ns plus read lag {read_lag_ns} ns \
         must be under the drives' {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    FeedbackAge {
        /// The feedback limit.
        feedback_limit_ns: u64,
        /// The send window: how long after the staleness check, at the wake, the frame may be written.
        write_slack_ns: u64,
        /// Period - collect + send window: how long after its arrival a status may be read.
        read_lag_ns: u64,
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
    /// `silent_ticks` is zero.
    #[error("silent_ticks must be at least 1")]
    NoSilentTicks,
    /// `silent_ticks` periods plus the write slack reach the drives' timeout: the bus would stop a silent control only
    /// after the drives had given up on their own, or never (safety.md section 4: no config value turns a protection
    /// off).
    #[error(
        "{silent_ticks} silent ticks of {period_ns} ns plus write slack {write_slack_ns} ns must span less than the \
         drives' {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    SilentTicks {
        /// The silent ticks.
        silent_ticks: u32,
        /// The period.
        period_ns: u64,
        /// The send window: how late in its tick the wake that plans the stop's Disable may come. The write follows
        /// it by the shell's wake-to-write time (PLAN step 8).
        write_slack_ns: u64,
    },
    /// `silence_misses` is zero.
    #[error("silence_misses must be at least 1")]
    NoSilenceMisses,
    /// `silence_misses` periods, plus the tick that stops the limb after the last miss, plus the write slack reach the
    /// drives' timeout: the limb would stop a silent drive only after the drives had given up on their own, or never.
    #[error(
        "{silence_misses} missed replies of {period_ns} ns, plus one period (the tick that stops the limb), plus write \
         slack {write_slack_ns} ns must span less than the drives' {DRIVE_TIMEOUT_NS} ns timeout"
    )]
    SilenceMisses {
        /// The count.
        silence_misses: u32,
        /// The period.
        period_ns: u64,
        /// The send window: how late in its tick the wake that plans the stop's Disable may come. The write follows
        /// it by the shell's wake-to-write time (PLAN step 8).
        write_slack_ns: u64,
    },
}
