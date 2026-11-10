//! (rt) The bus thread's clocks on Linux, the one place the shell reads them: the loop's schedule on `CLOCK_MONOTONIC`
//! (absolute sleeps), the session's epoch for stamps, and the wall clock for the recording.

use std::io;
use std::time::{Duration, Instant, SystemTime};

use nix::sys::time::TimeSpec;
use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};
use telemetry::Epoch;

/// The bus's clocks: the loop's schedule on `CLOCK_MONOTONIC` (absolute sleeps) and the session's epoch for stamps.
pub(crate) struct Clock {
    start: Instant,
    start_ts: TimeSpec,
    epoch: Epoch,
}

impl Clock {
    /// The schedule from `start`, read against `CLOCK_MONOTONIC` (which `Instant` is on Linux) once, now.
    pub(crate) fn new(epoch: Epoch, start: Instant) -> io::Result<Self> {
        // Two reads of one clock: the sleep base first, so the gap between them makes every wake measure early, never
        // late.
        let now_ts = clock_gettime(ClockId::CLOCK_MONOTONIC).map_err(io::Error::from)?;
        let now = mono_now();
        let start_ts = if start >= now {
            now_ts + TimeSpec::from_duration(start.duration_since(now))
        } else {
            now_ts - TimeSpec::from_duration(now.duration_since(start))
        };
        Ok(Self {
            start,
            start_ts,
            epoch,
        })
    }

    /// Sleep until `at` on the monotonic clock, absolute, so a slow tick never shifts the next.
    pub(crate) fn sleep_until(&self, at: Instant) -> io::Result<()> {
        let offset = at.saturating_duration_since(self.start);
        let target = self.start_ts + TimeSpec::from_duration(offset);
        loop {
            match clock_nanosleep(
                ClockId::CLOCK_MONOTONIC,
                ClockNanosleepFlags::TIMER_ABSTIME,
                &target,
            ) {
                Err(nix::errno::Errno::EINTR) => {}
                Ok(_) => return Ok(()),
                Err(e) => return Err(e.into()),
            }
        }
    }

    /// The tick whose period `now` falls in: its start has passed, the next one's hasn't.
    pub(crate) fn tick_at(&self, now: Instant, period_ns: u64) -> u64 {
        let elapsed = now.saturating_duration_since(self.start).as_nanos();
        u64::try_from(elapsed / u128::from(period_ns)).unwrap_or(u64::MAX)
    }

    /// The first tick whose start hasn't passed: 0 when the thread starts before the schedule does.
    pub(crate) fn first_due(&self, period_ns: u64) -> u64 {
        let behind = mono_now().saturating_duration_since(self.start).as_nanos();
        u64::try_from(behind.div_ceil(u128::from(period_ns))).unwrap_or(u64::MAX)
    }

    /// Tick `n`'s scheduled start.
    pub(crate) fn at(&self, n: u64, period_ns: u64) -> Instant {
        self.start + Duration::from_nanos(n.saturating_mul(period_ns))
    }

    pub(crate) fn ns(&self, at: Instant) -> u64 {
        self.epoch.ns(at)
    }
}

/// The monotonic clock, read only here and in [`wall_ns`]: the tick itself is handed time (clippy.toml).
#[expect(
    clippy::disallowed_methods,
    reason = "the shell is where the bus reads its clock"
)]
pub(crate) fn mono_now() -> Instant {
    Instant::now()
}

/// The wall clock, for the recording's `wall_ns` only.
#[expect(
    clippy::disallowed_methods,
    reason = "the recording stamps each tick with wall time (logging.md)"
)]
pub(crate) fn wall_ns() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX))
}

/// Sleep for `span`, relative: only when the monotonic clock itself failed, so the stop still has ticks to run in.
#[expect(
    clippy::disallowed_methods,
    reason = "the fallback when the absolute sleep can't read the clock"
)]
pub(crate) fn sleep_relative(span: Duration) {
    std::thread::sleep(span);
}
