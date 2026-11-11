//! Unit newtypes (units-and-frames.md section 1): SI, plus `Gain` in the drive's own units; and the drive's CAN device ID.
//!
//! Values are always finite: `new` refuses NaN and infinities, so nothing downstream has to ask.

macro_rules! si_unit {
    ($(#[$doc:meta])* $name:ident) => {
        $(#[$doc])*
        #[derive(Clone, Copy, Debug, PartialEq, PartialOrd)]
        pub struct $name(pub(crate) f64);

        impl $name {
            /// The value, or `None` if it isn't finite.
            #[must_use]
            pub fn new(value: f64) -> Option<Self> {
                value.is_finite().then_some(Self(value))
            }

            /// The value in this unit.
            #[must_use]
            pub const fn get(self) -> f64 {
                self.0
            }

        }
    };
}

si_unit!(
    /// An angle in radians.
    Radians
);
si_unit!(
    /// An angular velocity in rad/s.
    RadPerSec
);
si_unit!(
    /// An angular acceleration in rad/s².
    RadPerSecSq
);
si_unit!(
    /// A torque in N·m.
    NewtonMeters
);
si_unit!(
    /// A current in amperes. Drive phase current (Iq) unless a field says otherwise (PLAN item 1).
    Amps
);
si_unit!(
    /// A voltage in volts.
    Volts
);
si_unit!(
    /// A drive loop or filter gain, in the drive's own units, which the manual doesn't give.
    Gain
);
si_unit!(
    /// A temperature in degrees Celsius.
    Celsius
);
si_unit!(
    /// A position gain (MIT Kp) in N·m/rad.
    NmPerRad
);
si_unit!(
    /// A velocity gain (MIT Kd) in N·m·s/rad.
    NmSecPerRad
);

/// A drive's 64-bit MCU unique identifier, exactly as the type-0 reply carries it (manual §4.1.1). The manual gives no
/// byte order, so it is compared as raw bytes.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Uid(pub [u8; 8]);

/// A drive's CAN ID on its bus, 1 to 127.
///
/// The host-tool parameter table gives `CAN_ID` (0x200A) a range of 0 to 127 (RS03 manual §3.3.4). 0 is refused: it is
/// the type-0 broadcast target, not a drive. IDs above 127 include the host (0xFD) and the identity marker (0xFE).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct DeviceId(u8);

/// A device ID outside 1 to 127.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("device ID {0} is outside 1 to 127")]
pub struct InvalidDeviceId(pub u64);

impl DeviceId {
    /// Highest ID the drive accepts (RS03 manual §3.3.4, `CAN_ID` 0x200A).
    pub const MAX: u8 = 127;

    /// The ID, or an error if it is outside 1 to 127.
    ///
    /// # Errors
    /// [`InvalidDeviceId`] when `value` is 0 or above 127.
    pub fn new(value: u64) -> Result<Self, InvalidDeviceId> {
        match u8::try_from(value) {
            Ok(id @ 1..=Self::MAX) => Ok(Self(id)),
            Ok(_) | Err(_) => Err(InvalidDeviceId(value)),
        }
    }

    /// The ID as sent on the wire.
    #[must_use]
    pub const fn get(self) -> u8 {
        self.0
    }
}

impl core::fmt::Display for DeviceId {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}", self.0)
    }
}
