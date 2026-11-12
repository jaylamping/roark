//! The caps a joint is enabled at (PLAN item 1, Null is not a number; Commissioning caps): its own once it is
//! commissioned, otherwise each the lower of its model's commissioning cap (`robstride::ModelRanges::commissioning`)
//! and its own, if set. One rule, read by the loader's current budget and by preflight.

use robstride::{Amps, Model, NewtonMeters, RadPerSec};

use crate::types::Joint;

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

/// A value as read: `None` didn't parse (the loader reports it), `Some(None)` is a written `null`.
type Read<T> = Option<Option<T>>;

impl Caps {
    /// The caps a joint of `model` is enabled at. It is commissioned unless one of its `direction`, `zero_rad` and
    /// `hard_rad` (`facts`) or its own caps is a written null. Commissioned, it gets its own caps; otherwise each the
    /// lower of the model's commissioning cap and its own, if set. A value that didn't parse only reaches here from the loader's
    /// budget: it doesn't make the joint uncommissioned, and an unparsed own cap counts as the commissioning cap.
    pub(crate) fn enabled_at(
        model: Model,
        facts: [Read<()>; 3],
        (torque, current, speed): (Read<NewtonMeters>, Read<Amps>, Read<RadPerSec>),
    ) -> Self {
        let commissioning = model.ranges().commissioning();
        let commissioned =
            !facts.into_iter().any(null) && !null(torque) && !null(current) && !null(speed);
        Self {
            torque: pick(torque, commissioning.torque_max, commissioned),
            current: pick(current, commissioning.current_max, commissioned),
            speed: pick(speed, commissioning.speed_max, commissioned),
        }
    }
}

/// Whether `value` is a written null.
const fn null<T: Copy>(value: Read<T>) -> bool {
    matches!(value, Some(None))
}

/// `own` when commissioned or below `ceiling`; `ceiling` when it is null, didn't parse or is higher.
fn pick<T: PartialOrd + Copy>(own: Read<T>, ceiling: T, commissioned: bool) -> T {
    match own.flatten() {
        Some(own) if commissioned || own < ceiling => own,
        Some(_) | None => ceiling,
    }
}

impl Joint {
    /// The caps the joint is enabled at (PLAN item 1): its own once commissioned (every cap, `direction`, `zero_rad` and
    /// `hard_rad` set; the UID is not part of it), otherwise each the lower of its model's commissioning cap and its
    /// own, if set.
    #[must_use]
    pub fn caps(&self) -> Caps {
        let fact = |set: bool| Some(set.then_some(()));
        Caps::enabled_at(
            self.actuator,
            [
                fact(self.direction.is_some()),
                fact(self.zero_rad.is_some()),
                fact(self.hard_rad.is_some()),
            ],
            (
                Some(self.torque_cap_nm),
                Some(self.current_cap_a),
                Some(self.speed_cap_rad_s),
            ),
        )
    }
}
