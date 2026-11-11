//! The caps a joint is enabled at (PLAN item 1, Null is not a number; Commissioning caps): its own once it is
//! commissioned, otherwise its model's commissioning caps, low enough that a wrong sign, a wrong zero or a bad target
//! can't hurt the drive or a printed part. One rule, read by the loader's current budget and by preflight.

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
    /// `model`'s commissioning caps. Each is a finite range times a finite share, so finite; were one not, it would be
    /// zero, which the budget counts as the drive would then run: at nothing.
    #[must_use]
    pub fn commissioning(model: Model) -> Self {
        let ranges = model.ranges();
        Self {
            torque: NewtonMeters::new(ranges.torque_max.get() * SHARE)
                .unwrap_or(NewtonMeters::ZERO),
            current: Amps::new(ranges.current_max.get() * SHARE).unwrap_or(Amps::ZERO),
            speed: RadPerSec::new(SPEED_RAD_S.min(ranges.speed_max.get()))
                .unwrap_or(RadPerSec::ZERO),
        }
    }
}

impl Joint {
    /// Whether the joint is commissioned: every cap, `direction`, `zero_rad` and `hard_rad` set.
    #[must_use]
    pub const fn commissioned(&self) -> bool {
        self.direction.is_some()
            && self.zero_rad.is_some()
            && self.hard_rad.is_some()
            && self.torque_cap_nm.is_some()
            && self.current_cap_a.is_some()
            && self.speed_cap_rad_s.is_some()
    }

    /// The caps the joint is enabled at: its own once commissioned; otherwise each the lower of its model's
    /// commissioning cap and its own, if set (PLAN item 1).
    #[must_use]
    pub fn caps(&self) -> Caps {
        let floor = Caps::commissioning(self.actuator);
        match (self.torque_cap_nm, self.current_cap_a, self.speed_cap_rad_s) {
            (Some(torque), Some(current), Some(speed)) if self.commissioned() => Caps {
                torque,
                current,
                speed,
            },
            (torque, current, speed) => Caps {
                torque: lower(torque, floor.torque),
                current: lower(current, floor.current),
                speed: lower(speed, floor.speed),
            },
        }
    }
}

/// `own`, if set and below `floor`; else `floor`.
fn lower<T: PartialOrd + Copy>(own: Option<T>, floor: T) -> T {
    match own {
        Some(own) if own < floor => own,
        Some(_) | None => floor,
    }
}
