//! The checked skeleton. Every value here has passed the loader; nothing downstream re-checks it (rust.md section 3).
//!
//! `None` means the value isn't known yet. It loads fine and refuses enable ("Null is not permission", PLAN item 1).

use core::fmt;

use robstride::{Amps, DeviceId, Model, NewtonMeters, RadPerSec, Radians, Volts};

/// The whole robot, as described by `config/skeleton.yaml`.
#[derive(Clone, Debug, PartialEq)]
pub struct Skeleton {
    /// The robot's name. The only place it appears.
    pub name: String,
    /// The supply the robot runs from.
    pub power: Power,
    /// Every CAN bus, in file order.
    pub buses: Vec<Bus>,
    /// The five limbs, in file order.
    pub limbs: Vec<Limb>,
}

/// The supply and its limits.
#[derive(Clone, Debug, PartialEq)]
pub struct Power {
    /// Which supply this file describes.
    pub source: PowerSource,
    /// Drive bus voltage window for preflight and the running check (PLAN item 6).
    pub vbus_v: Window<Volts>,
    /// Upper bound on the summed current caps of every joint that can be enabled together.
    pub current_budget_a: Amps,
}

/// The supply the robot runs from. The battery joins at milestone 4 (PLAN item 10).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PowerSource {
    /// The 24 V bench supply.
    Bench24V,
}

/// One CAN bus.
#[derive(Clone, Debug, PartialEq)]
pub struct Bus {
    /// Interface name, also used for `vcan` in sim (PLAN item 4).
    pub name: BusName,
    /// Bit rate, bit/s.
    pub bitrate: u32,
    /// Sample point as a fraction of the bit, between 0 and 1.
    pub sample_point: f64,
    /// USB serial of the adapter, for its link file (PLAN item 3). `None` until the adapter exists.
    pub adapter_serial: Option<String>,
}

/// One limb and its joints, shoulder to hand or hip to foot.
#[derive(Clone, Debug, PartialEq)]
pub struct Limb {
    /// Which limb.
    pub name: LimbName,
    /// Its joints, in file order.
    pub joints: Vec<Joint>,
}

/// The robot's five limbs (tenet 1). Adding one is a skeleton change agreed with the hardware side.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LimbName {
    /// The robot's left arm.
    LeftArm,
    /// The robot's right arm.
    RightArm,
    /// The waist.
    Waist,
    /// The robot's left leg.
    LeftLeg,
    /// The robot's right leg.
    RightLeg,
}

impl LimbName {
    /// Every limb, in the order the file lists them (skeleton.md section 4).
    pub const ALL: [Self; 5] = [
        Self::LeftArm,
        Self::RightArm,
        Self::Waist,
        Self::LeftLeg,
        Self::RightLeg,
    ];

    /// The name used in the file, logs and the `api`.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::LeftArm => "left_arm",
            Self::RightArm => "right_arm",
            Self::Waist => "waist",
            Self::LeftLeg => "left_leg",
            Self::RightLeg => "right_leg",
        }
    }
}

impl fmt::Display for LimbName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// One joint and its drive.
#[derive(Clone, Debug, PartialEq)]
pub struct Joint {
    /// Unique across the robot, `snake_case`, side first.
    pub name: JointName,
    /// The drive's model.
    pub actuator: Model,
    /// `None` while the limb isn't wired: the joint is offline.
    pub bus: Option<BusName>,
    /// The drive's CAN ID, unique on its bus.
    pub id: DeviceId,
    /// MCU UID from the type-0 reply, filled at commissioning.
    pub uid: Option<Uid>,
    /// Joint sign relative to the drive, set by the sign check.
    pub direction: Option<Direction>,
    /// Drive position at joint zero: `q_joint = direction × (q_motor − zero_rad)`.
    pub zero_rad: Option<Radians>,
    /// How the link is placed for referencing.
    pub reference_pose: Option<String>,
    /// Hard limits in joint space, inside the physical stops.
    pub hard_rad: Option<Window<Radians>>,
    /// Tighter soft limits than the default inset, inside `hard_rad`.
    pub soft_rad: Option<Window<Radians>>,
    /// Torque cap, N·m: the weakest part's number, not the drive's rating.
    pub torque_cap_nm: Option<NewtonMeters>,
    /// Phase current cap, A.
    pub current_cap_a: Option<Amps>,
    /// Speed cap, rad/s.
    pub speed_cap_rad_s: Option<RadPerSec>,
}

/// A `[lower, upper]` range with `lower < upper`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Window<T> {
    /// Lower end.
    pub lower: T,
    /// Upper end.
    pub upper: T,
}

/// A joint's sign relative to its drive.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Direction {
    /// Joint and drive turn the same way (`+1`).
    Same,
    /// Joint turns opposite to the drive (`-1`).
    Reversed,
}

impl Direction {
    /// `+1.0` or `-1.0`, for the drive-to-joint conversion.
    #[must_use]
    pub const fn sign(self) -> f64 {
        match self {
            Self::Same => 1.0,
            Self::Reversed => -1.0,
        }
    }
}

/// The drive's 64-bit MCU unique identifier (type-0 reply, manual §4.1.1).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Uid(pub [u8; 8]);

/// A joint name from the skeleton: lower-case letters, digits and `_`, starting with a letter.
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct JointName(pub(crate) String);

/// A bus (interface) name: lower-case letters and digits, at most 15 bytes (the kernel's interface name limit).
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct BusName(pub(crate) String);

impl JointName {
    /// The name as written in the skeleton.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl BusName {
    /// The interface name.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for JointName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl fmt::Display for BusName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
