//! (rt) The control thread's clocks on Linux, the one place it reads them: the shared schedule on `CLOCK_MONOTONIC`
//! (absolute sleeps, as the bus threads keep it), the session's epoch for batch deadlines, and the wall clock for the
//! session's start. It repeats the few lines of `can`'s private clock rather than widen `can`'s API for them.

use std::io;
use std::time::{Duration, Instant, SystemTime};

use nix::sys::time::TimeSpec;
use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};

/// The schedule every thread shares: tick `n` starts at `start + n × period`.
pub(crate) struct Schedule {
    start: Instant,
    start_ts: TimeSpec,
    period_ns: u64,
}

impl Schedule {
    /// The schedule from `start`, read against `CLOCK_MONOTONIC` (which `Instant` is on Linux) once, now.
    pub(crate) fn new(start: Instant, period_ns: u64) -> io::Result<Self> {
        // The sleep base first, so the gap between the two reads makes every wake early, never late.
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
            period_ns,
        })
    }

    /// Tick `n`'s start plus `offset_ns`.
    pub(crate) fn at(&self, n: u64, offset_ns: u64) -> Instant {
        self.start
            + Duration::from_nanos(n.saturating_mul(self.period_ns).saturating_add(offset_ns))
    }

    /// The first tick whose start plus `offset_ns` hasn't passed.
    pub(crate) fn next(&self, offset_ns: u64) -> u64 {
        let behind = mono_now()
            .saturating_duration_since(self.start + Duration::from_nanos(offset_ns))
            .as_nanos();
        u64::try_from(behind.div_ceil(u128::from(self.period_ns))).unwrap_or(u64::MAX)
    }

    /// The last tick whose start plus `offset_ns` has passed: the pass in progress, after a wake that may have come
    /// whole ticks late.
    pub(crate) fn current(&self, offset_ns: u64) -> u64 {
        let elapsed = mono_now()
            .saturating_duration_since(self.start + Duration::from_nanos(offset_ns))
            .as_nanos();
        u64::try_from(elapsed / u128::from(self.period_ns)).unwrap_or(u64::MAX)
    }

    /// Sleep until `at`, absolute, so a slow pass never shifts the next.
    pub(crate) fn sleep_until(&self, at: Instant) -> io::Result<()> {
        let target =
            self.start_ts + TimeSpec::from_duration(at.saturating_duration_since(self.start));
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
}

/// Whether `at` has passed.
pub(crate) fn passed(at: Instant) -> bool {
    mono_now() >= at
}

/// The monotonic clock, read only here and in [`wall_ns`].
#[expect(
    clippy::disallowed_methods,
    reason = "the control thread's schedule is where it reads its clock"
)]
pub(crate) fn mono_now() -> Instant {
    Instant::now()
}

/// The wall clock, for the session's start and end only.
#[expect(
    clippy::disallowed_methods,
    reason = "the recording stamps the session with wall time (logging.md)"
)]
pub(crate) fn wall_ns() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX))
}

/// Sleep one period, relative: only once the absolute clock has failed, to keep the thread from spinning while it ends.
#[expect(
    clippy::disallowed_methods,
    reason = "the absolute sleep failed; this only paces the way out"
)]
pub(crate) fn sleep_period(period_ns: u64) {
    std::thread::sleep(Duration::from_nanos(period_ns));
}
