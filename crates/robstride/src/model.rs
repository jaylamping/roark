//! The four RobStride models the robot uses and what each one accepts.
//!
//! Actuator differences are data, not types (rust.md section 11): one enum, one table.

use core::f64::consts::TAU;

use crate::units::{Amps, DeviceId, NewtonMeters, RadPerSec, Radians};

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

/// One drive on the bus: its ID paired with its model once, from the skeleton. Every frame whose bytes depend on the
/// model (an MIT command, a cap) is built through it, so a frame scaled or capped for one model can't be sent to a drive
/// of another.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Drive {
    id: DeviceId,
    model: Model,
}

impl Drive {
    /// Drive `id`, a `model`.
    #[must_use]
    pub const fn new(id: DeviceId, model: Model) -> Self {
        Self { id, model }
    }

    /// Its CAN ID.
    #[must_use]
    pub const fn id(self) -> DeviceId {
        self.id
    }

    /// Its model.
    #[must_use]
    pub const fn model(self) -> Model {
        self.model
    }
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

impl ModelRanges {
    /// The share of the `limit_torque` and `limit_cur` ranges a joint not yet commissioned is enabled at ([PLAN, Open
    /// with Joey](https://github.com/jaylamping/roark/blob/main/PLAN.md#open-with-joey) 11: a starting point, to be set
    /// from logged runs).
    const COMMISSIONING_SHARE: f64 = 0.05;
    /// The `limit_spd` a joint not yet commissioned is enabled at, rad/s, or the range's top if lower (Open with Joey
    /// 11).
    const COMMISSIONING_SPEED_RAD_S: f64 = 0.5;

    /// The caps a joint of this model is enabled at until it is commissioned (PLAN item 1), each inside its range: the
    /// highest each may be until then.
    #[must_use]
    pub const fn commissioning(self) -> Self {
        let speed = self.speed_max.0;
        Self {
            torque_max: NewtonMeters(self.torque_max.0 * Self::COMMISSIONING_SHARE),
            current_max: Amps(self.current_max.0 * Self::COMMISSIONING_SHARE),
            speed_max: RadPerSec(if speed < Self::COMMISSIONING_SPEED_RAD_S {
                speed
            } else {
                Self::COMMISSIONING_SPEED_RAD_S
            }),
        }
    }
}

impl Model {
    /// Every model, in table order.
    pub(crate) const ALL: [Self; 4] = [Self::Rs00, Self::Rs02, Self::Rs03, Self::Rs04];

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

    /// The MIT-mode field ranges (§4.1.2) the codec encodes commands and decodes feedback with.
    ///
    /// Position is ±12.57 rad, the §4.4 sample's `P_MIN`/`P_MAX`; the frame tables round it to ±4π. RS03 velocity is
    /// ±20 rad/s in every RS03 manual revision, and bench capture cd-20261003T145133Z (`right_shoulder_pitch`, firmware
    /// 0.3.1.42) fits a full scale of 20.05 rad/s; the Seeed SDK's ±50 was wrong and decoded velocity 2.5× high.
    ///
    /// # Errors
    /// [`UnvouchedModel`] for RS00: every RS00 manual gives ±33 rad/s and ±14 N·m, the legacy code used ±50 and ±17, and
    /// no RS00 motion has been captured to settle it (PLAN item 2, "Open fact: RS00 MIT scales").
    pub const fn mit_scales(self) -> Result<MitScales, UnvouchedModel> {
        // (velocity rad/s, Kp N·m/rad, Kd N·m·s/rad, torque N·m)
        let (velocity, kp, kd, torque) = match self {
            Self::Rs00 => return Err(UnvouchedModel(self)),
            // RS02 manual 260713 §4.1.2 and §4.4.
            Self::Rs02 => (44.0, 500.0, 5.0, 17.0),
            // RS03 manual 261013 §4.1.2 and §4.4.
            Self::Rs03 => (20.0, 5000.0, 100.0, 60.0),
            // RS04 manual 260713 §4.1.2 and §4.4.
            Self::Rs04 => (15.0, 5000.0, 100.0, 120.0),
        };
        Ok(MitScales {
            position: MitRange::symmetric(MIT_POSITION_MAX_RAD),
            velocity: MitRange::symmetric(velocity),
            kp: MitRange::up_to(kp),
            kd: MitRange::up_to(kd),
            torque: MitRange::symmetric(torque),
        })
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

/// MIT position range, every model (§4.4 sample, `P_MAX 12.57f`).
const MIT_POSITION_MAX_RAD: f64 = 12.57;

/// Full scale of a 16-bit MIT field: codes 0 to 65535 span the range (§4.1.2).
const MIT_CODE_MAX: f64 = 65535.0;

/// A model whose MIT scales the codec can't vouch for, so it encodes no command and decodes no feedback for it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("{0} MIT scales are not settled; nothing is encoded or decoded for it")]
pub struct UnvouchedModel(pub Model);

/// One model's MIT field ranges. Each field maps codes 0 to 65535 linearly onto `min` to `max`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MitScales {
    /// Target and feedback position, rad.
    pub position: MitRange,
    /// Target and feedback velocity, rad/s.
    pub velocity: MitRange,
    /// Position gain, N·m/rad.
    pub kp: MitRange,
    /// Velocity gain, N·m·s/rad.
    pub kd: MitRange,
    /// Feed-forward and feedback torque, N·m.
    pub torque: MitRange,
}

/// A 16-bit MIT field's range: code 0 is `min`, code 65535 is `max` (§4.1.2). Only [`Model::mit_scales`] builds one, so
/// `min` and `max` are always finite with `min < max`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MitRange {
    min: f64,
    max: f64,
}

impl MitRange {
    const fn symmetric(max: f64) -> Self {
        Self { min: -max, max }
    }

    const fn up_to(max: f64) -> Self {
        Self { min: 0.0, max }
    }

    /// The value code 0 stands for.
    #[must_use]
    pub const fn min(self) -> f64 {
        self.min
    }

    /// The value code 65535 stands for.
    #[must_use]
    pub const fn max(self) -> f64 {
        self.max
    }

    /// The value a code stands for, as the drive reads it.
    #[must_use]
    pub fn value(self, code: u16) -> f64 {
        self.min + f64::from(code) * (self.max - self.min) / MIT_CODE_MAX
    }

    /// The code nearest `value`, or `None` if `value` is outside the range or not finite. Never clamps.
    ///
    /// The §4.4 sample truncates instead of rounding; truncation sends up to one code low and doesn't round-trip, since
    /// floating-point error puts thousands of exact codes a hair below themselves.
    #[must_use]
    pub fn code(self, value: f64) -> Option<u16> {
        if !value.is_finite() || !(self.min..=self.max).contains(&value) {
            return None;
        }
        // In [0.5, 65535.5] here, so the cast floors a non-negative value and the result fits in 16 bits.
        let scaled = (value - self.min) * MIT_CODE_MAX / (self.max - self.min) + 0.5;
        #[expect(
            clippy::as_conversions,
            clippy::cast_possible_truncation,
            clippy::cast_sign_loss,
            reason = "range checked above: scaled is in [0.5, 65535.5], so this is round-to-nearest into 0..=65535"
        )]
        let code = scaled as u32;
        u16::try_from(code).ok()
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
