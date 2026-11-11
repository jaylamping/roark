//! The caps an uncommissioned joint runs at (PLAN item 1, Commissioning caps; Open with Joey 11): low enough that a
//! wrong sign, a wrong zero or a bad target can't hurt the drive or a printed part.

use robstride::{Amps, Model, NewtonMeters, RadPerSec};

/// The share of the model's `limit_torque` and `limit_cur` ranges an uncommissioned joint gets (Joey, 2026-11-11: a
/// starting point, to be set from logged runs once a full limb moves).
pub const COMMISSIONING_SHARE: f64 = 0.05;

/// The speed an uncommissioned joint gets, in rad/s, or its model's highest if lower.
pub const COMMISSIONING_SPEED_RAD_S: f64 = 0.5;

/// The three caps preflight writes to an uncommissioned joint's drive and reads back.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CommissioningCaps {
    /// `limit_torque`.
    pub torque: NewtonMeters,
    /// `limit_cur`.
    pub current: Amps,
    /// `limit_spd`.
    pub speed: RadPerSec,
}

impl CommissioningCaps {
    /// `model`'s commissioning caps. Each is a finite range scaled by a finite share, so always some; `None` would
    /// mean a model table gone wrong, which refuses rather than guesses.
    #[must_use]
    pub fn of(model: Model) -> Option<Self> {
        let ranges = model.ranges();
        Some(Self {
            torque: NewtonMeters::new(ranges.torque_max.get() * COMMISSIONING_SHARE)?,
            current: Amps::new(ranges.current_max.get() * COMMISSIONING_SHARE)?,
            speed: RadPerSec::new(COMMISSIONING_SPEED_RAD_S.min(ranges.speed_max.get()))?,
        })
    }
}
