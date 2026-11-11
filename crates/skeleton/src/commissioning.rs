//! The caps a joint is enabled at (PLAN item 1, Null is not a number; Commissioning caps): its own once it is
//! commissioned, otherwise each the lower of its model's commissioning cap and its own, if set. The commissioning caps
//! are low enough that a wrong sign, a wrong zero or a bad target can't hurt the drive or a printed part. One rule, read
//! by the loader's current budget and by preflight.

use robstride::{Amps, Model, NewtonMeters, RadPerSec};

use crate::types::Joint;

/// The share of the model's `limit_torque` and `limit_cur` ranges an uncommissioned joint gets ([Open with Joey
/// 11](https://github.com/jaylamping/roark/blob/main/PLAN.md#open-with-joey): a starting point, to be set from logged
/// runs).
const SHARE: f64 = 0.05;

/// The speed an uncommissioned joint gets, in rad/s, or its model's highest if lower (Open with Joey 11).
const SPEED_RAD_S: f64 = 0.5;

/// A joint's three caps, as written to its drive's `limit_torque`, `limit_cur` and `limit_spd`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Caps {
    /// `limit_torque`.
    pub torque: NewtonMeters,
    /// `limit_cur`.
    pub current: Amps,
    /// `limit_spd`.
    pub speed: RadPerSec,
}

impl Caps {
    /// The caps a joint of `model` with these caps of its own is enabled at: its own when all three are set and
    /// `facts_set` (its `direction`, `zero_rad` and `hard_rad` are), otherwise each the lower of the model's
    /// commissioning cap and its own, if set.
    pub(crate) fn enabled_at(
        model: Model,
        own: (Option<NewtonMeters>, Option<Amps>, Option<RadPerSec>),
        facts_set: bool,
    ) -> Self {
        match (facts_set, own) {
            (true, (Some(torque), Some(current), Some(speed))) => Self {
                torque,
                current,
                speed,
            },
            (_, (torque, current, speed)) => {
                let ranges = model.ranges();
                Self {
                    torque: lower(torque, ranges.torque_max.times(SHARE)),
                    current: lower(current, ranges.current_max.times(SHARE)),
                    speed: lower(speed, ranges.speed_max.at_most(SPEED_RAD_S)),
                }
            }
        }
    }
}

impl Joint {
    /// The caps the joint is enabled at (PLAN item 1): its own once commissioned (every cap, `direction`, `zero_rad` and
    /// `hard_rad` set; the UID is not part of it), otherwise each the lower of its model's commissioning cap and its
    /// own, if set.
    #[must_use]
    pub fn caps(&self) -> Caps {
        Caps::enabled_at(
            self.actuator,
            (self.torque_cap_nm, self.current_cap_a, self.speed_cap_rad_s),
            self.direction.is_some() && self.zero_rad.is_some() && self.hard_rad.is_some(),
        )
    }
}

/// `own`, if set and below `ceiling`; else `ceiling`.
fn lower<T: PartialOrd + Copy>(own: Option<T>, ceiling: T) -> T {
    match own {
        Some(own) if own < ceiling => own,
        Some(_) | None => ceiling,
    }
}
