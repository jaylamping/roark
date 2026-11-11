//! Percentiles of the measured times, for the summary.

use std::fmt::Write as _;

/// A sorted list of durations in nanoseconds.
pub(crate) struct Spread(Vec<u64>);

impl Spread {
    pub(crate) fn new(mut values: Vec<u64>) -> Self {
        values.sort_unstable();
        Self(values)
    }

    /// The value at or below which `per_10k` ten-thousandths of the values fall (nearest rank). `None` when empty.
    pub(crate) fn at(&self, per_10k: u64) -> Option<u64> {
        let n = u64::try_from(self.0.len()).ok()?;
        if n == 0 {
            return None;
        }
        let rank = (n * per_10k).div_ceil(10_000).max(1);
        self.0.get(usize::try_from(rank - 1).ok()?).copied()
    }

    /// How many values are at or below `limit`.
    pub(crate) fn within(&self, limit: u64) -> usize {
        self.0.partition_point(|&v| v <= limit)
    }

    pub(crate) fn len(&self) -> usize {
        self.0.len()
    }

    /// One summary line: count, median, 99 %, 99.9 %, 99.99 % and the worst, in microseconds.
    pub(crate) fn line(&self, name: &str) -> String {
        let us = |v: Option<u64>| v.map_or_else(|| "-".to_owned(), |v| format!("{:.0}", micros(v)));
        let mut s = String::new();
        let _ = write!(
            s,
            "{name:<22} n={:<9} p50={:>6} p99={:>6} p99.9={:>6} p99.99={:>6} max={:>6} us",
            self.len(),
            us(self.at(5000)),
            us(self.at(9900)),
            us(self.at(9990)),
            us(self.at(9999)),
            us(self.0.last().copied()),
        );
        s
    }
}

/// Nanoseconds as microseconds, for display only.
#[expect(
    clippy::cast_precision_loss,
    reason = "display only; bench times are far below 2^52 ns"
)]
pub(crate) fn micros(ns: u64) -> f64 {
    ns as f64 / 1000.0
}
