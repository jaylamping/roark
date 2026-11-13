#![doc = include_str!("../README.md")]

pub mod stop;

#[cfg(target_os = "linux")]
mod bus;
#[cfg(target_os = "linux")]
mod lock;

#[cfg(target_os = "linux")]
pub use bus::{BusReport, DriveReport, disable};
#[cfg(target_os = "linux")]
pub use lock::{Claim, LockError, claim};

use robstride::DeviceId;
use skeleton::Skeleton;

/// The lock the runtime holds for as long as it runs, and `disable` takes before it sends: in the runtime's
/// `RuntimeDirectory` (conventions/deploy.md section 2). Both binaries take `--lock` to override it.
pub const LOCK_PATH: &str = "/run/robot/runtime.lock";

/// The drives `disable` stops on one bus: every skeleton joint wired to it, in skeleton order.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BusTargets {
    /// The interface.
    pub bus: String,
    /// Each drive's ID and joint name.
    pub drives: Vec<(DeviceId, String)>,
}

/// Every bus with a joint on it and that bus's drives, in skeleton order. Only the (bus, ID) pairs and the joint names
/// are read: nothing else in the skeleton changes what `disable` sends. A joint with no bus is offline and gets nothing.
#[must_use]
pub fn targets(skeleton: &Skeleton) -> Vec<BusTargets> {
    let mut out: Vec<BusTargets> = Vec::new();
    for bus in &skeleton.buses {
        let drives: Vec<(DeviceId, String)> = skeleton
            .limbs
            .iter()
            .flat_map(|limb| &limb.joints)
            .filter(|joint| joint.bus.as_ref() == Some(&bus.name))
            .map(|joint| (joint.id, joint.name.as_str().to_owned()))
            .collect();
        if !drives.is_empty() {
            out.push(BusTargets {
                bus: bus.name.as_str().to_owned(),
                drives,
            });
        }
    }
    out
}
