//! The four RobStride models the robot uses and what each one accepts.
//!
//! Actuator differences are data, not types (rust.md section 11): one enum, one table.

use core::f64::consts::TAU;

use crate::units::{Amps, NewtonMeters, RadPerSec, Radians};

/// A RobStride actuator model. The skeleton names the model; everything model-specific lives here.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Model {
    /// RS00.
    Rs00,
    /// RS02.
    Rs02,
    /// RS03.
    Rs03,
    /// RS04.
    Rs04,
}

/// A model name that isn't one of `rs00`, `rs02`, `rs03`, `rs04`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("unknown actuator model")]
pub struct UnknownModel;

/// The highest value each host-set limit may take on this model.
///
/// Each is the lower of the parameter table's range for that register (manual §4.1.13) and the MIT-mode range for the same
/// quantity (§4.1.2), so a cap is always one the drive accepts and one MIT mode can express.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ModelRanges {
    /// `limit_torque` 0x700B upper bound.
    pub torque_max: NewtonMeters,
    /// `limit_cur` 0x7018 upper bound.
    pub current_max: Amps,
    /// `limit_spd` 0x7017 upper bound.
    pub speed_max: RadPerSec,
}

impl Model {
    /// Parses the skeleton's lower-case model name.
    ///
    /// # Errors
    /// [`UnknownModel`] for any other name.
    pub fn from_name(name: &str) -> Result<Self, UnknownModel> {
        match name {
            "rs00" => Ok(Self::Rs00),
            "rs02" => Ok(Self::Rs02),
            "rs03" => Ok(Self::Rs03),
            "rs04" => Ok(Self::Rs04),
            _ => Err(UnknownModel),
        }
    }

    /// The skeleton's name for this model.
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::Rs00 => "rs00",
            Self::Rs02 => "rs02",
            Self::Rs03 => "rs03",
            Self::Rs04 => "rs04",
        }
    }

    /// Upper bounds for the host-set torque, current and speed limits.
    #[must_use]
    #[expect(
        clippy::match_same_arms,
        reason = "one row per model, each citing its own manual; RS00 and RS02 agree today"
    )]
    pub fn ranges(self) -> ModelRanges {
        // (limit_torque N·m, limit_cur A, limit_spd rad/s)
        let (torque, current, speed) = match self {
            // RS00 manual 260713: §4.1.13 limit_torque 0-14, limit_cur 0-16, limit_spd 0-33; §4.1.2 MIT T ±14, V ±33.
            Self::Rs00 => (14.0, 16.0, 33.0),
            // RS02 manual 260713: §4.1.13 limit_torque 0-14, limit_cur 0-16, limit_spd 0-33. These match RS00's table and
            // undercut RS02's own §4.1.2 (T ±17, V ±44) and §1.3 (23 Apk), so the table may be a copy. Until a bench
            // read-back shows the drive accepts more, the lower table value is the bound (fail closed).
            Self::Rs02 => (14.0, 16.0, 33.0),
            // RS03 manual 261013: §4.1.13 limit_torque 0-60, limit_cur 0-43, limit_spd 0-20; §4.1.2 MIT T ±60, V ±20.
            Self::Rs03 => (60.0, 43.0, 20.0),
            // RS04 manual 260713: §4.1.13 limit_torque 0-120, limit_cur 0-90, limit_spd 0-20; §4.1.2 MIT V ±15, so speed
            // is bounded at 15.
            Self::Rs04 => (120.0, 90.0, 15.0),
        };
        ModelRanges {
            torque_max: NewtonMeters(torque),
            current_max: Amps(current),
            speed_max: RadPerSec(speed),
        }
    }

    /// Where the drive's reported output position folds over after power-on: the lower end of the one-turn window, and
    /// the window's length.
    ///
    /// With `zero_sta` 0x7029 at its default 0 the drive comes up reporting 0 to 2π (manual §4.2.2, same in all four
    /// manuals). The host never writes 0x7029 (PLAN item 2), so the default holds unless a vendor tool changed it.
    #[must_use]
    pub const fn power_on_window(self) -> (Radians, Radians) {
        match self {
            Self::Rs00 | Self::Rs02 | Self::Rs03 | Self::Rs04 => (Radians(0.0), Radians(TAU)),
        }
    }
}

impl core::fmt::Display for Model {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(self.name())
    }
}

#[cfg(test)]
mod tests {
    use super::Model;

    /// Guards: number - per-model cap bounds the skeleton loader enforces, RobStride manuals §4.1.13 and §4.1.2.
    #[test]
    fn cap_bounds_match_the_manuals() {
        let cases = [
            // (model, limit_torque N·m, limit_cur A, limit_spd rad/s)
            (Model::Rs00, 14.0, 16.0, 33.0),
            (Model::Rs02, 14.0, 16.0, 33.0),
            (Model::Rs03, 60.0, 43.0, 20.0),
            (Model::Rs04, 120.0, 90.0, 15.0),
        ];
        for (model, torque, current, speed) in cases {
            let r = model.ranges();
            let got = (r.torque_max.get(), r.current_max.get(), r.speed_max.get());
            assert!(got == (torque, current, speed), "{model}: {got:?}");
        }
    }
}
