//! The sim's random numbers: every delay a drive draws comes from its seed.

use std::time::Duration;

/// `SplitMix64`: small, seeded, and the same on every machine, so a sim run replays exactly.
#[derive(Debug)]
pub(crate) struct Rng(pub(crate) u64);

impl Rng {
    pub(crate) fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// A span between `lo` and `hi` microseconds, inclusive.
    pub(crate) fn between(&mut self, (lo, hi): (u64, u64)) -> Duration {
        Duration::from_micros(lo + self.next() % (hi - lo + 1))
    }
}
