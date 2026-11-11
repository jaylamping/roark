//! Which bus threads the skeleton asks for: each bus's drives in slot order, and which skeleton limb each of the bus's
//! limb indices is. Pure, so it is tested on any OS.

use can::{BusDrive, MAX_DRIVES};
use skeleton::{JointName, LimbName, Skeleton};

/// One bus thread's share of the skeleton.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BusPlan {
    /// The interface, as the skeleton names it.
    pub name: String,
    /// Its bitrate, bit/s, for the recording's bus info.
    pub bitrate_bps: u32,
    /// Its drives in slot order: limb by limb in skeleton order, each limb's joints in file order.
    pub drives: Vec<BusDrive>,
    /// The joint in each slot.
    pub joints: Vec<JointName>,
    /// The skeleton limb behind each of this bus's limb indices (`BusDrive::limb`), in order of first appearance.
    pub limbs: Vec<LimbName>,
}

impl BusPlan {
    /// This bus's index for `limb`, if any of its joints are here.
    #[must_use]
    pub fn limb_index(&self, limb: LimbName) -> Option<usize> {
        self.limbs.iter().position(|l| *l == limb)
    }
}

/// Why the skeleton's buses can't be run.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum PlanError {
    /// No bus has a joint on it: nothing to run.
    #[error("no bus has a joint on it")]
    NoBus,
    /// More drives on one bus than a bus thread holds.
    #[error("{bus} has {drives} drives; a bus thread holds at most {MAX_DRIVES}")]
    TooManyDrives {
        /// The bus.
        bus: String,
        /// How many the skeleton puts there.
        drives: usize,
    },
}

/// The bus threads for `skeleton`: one per bus with at least one joint on it, in the skeleton's bus order. A bus with no
/// joint gets no thread (nothing to command or watch); a joint with no bus (its limb not wired) is offline and on none.
///
/// # Errors
/// A bus with more drives than a bus thread holds, or no bus with a joint on it.
pub fn plan(skeleton: &Skeleton) -> Result<Vec<BusPlan>, PlanError> {
    let mut plans = Vec::new();
    for bus in &skeleton.buses {
        let mut plan = BusPlan {
            name: bus.name.as_str().to_owned(),
            bitrate_bps: bus.bitrate_bps,
            drives: Vec::new(),
            joints: Vec::new(),
            limbs: Vec::new(),
        };
        for limb in &skeleton.limbs {
            for joint in limb
                .joints
                .iter()
                .filter(|j| j.bus.as_ref() == Some(&bus.name))
            {
                let index = plan.limb_index(limb.name).unwrap_or_else(|| {
                    plan.limbs.push(limb.name);
                    plan.limbs.len() - 1
                });
                plan.drives.push(BusDrive {
                    device: joint.id,
                    limb: index,
                });
                plan.joints.push(joint.name.clone());
            }
        }
        if plan.drives.len() > MAX_DRIVES {
            return Err(PlanError::TooManyDrives {
                bus: plan.name,
                drives: plan.drives.len(),
            });
        }
        if !plan.drives.is_empty() {
            plans.push(plan);
        }
    }
    if plans.is_empty() {
        return Err(PlanError::NoBus);
    }
    Ok(plans)
}

/// The joints on no bus: their limbs aren't wired yet, so they are offline and nothing runs them (tenet 1).
#[must_use]
pub fn offline(skeleton: &Skeleton) -> Vec<JointName> {
    skeleton
        .limbs
        .iter()
        .flat_map(|l| &l.joints)
        .filter(|j| j.bus.is_none())
        .map(|j| j.name.clone())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The runtime's test robot (`tests/skeleton.yaml`).
    fn fixture() -> Skeleton {
        skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap()
    }

    /// Guards: safety - the skeleton maps onto bus threads as the bus layer expects: one per wired bus, slots limb by
    /// limb in file order, and each bus's limb indices naming the skeleton limb they stand for, so a stop or clear aimed
    /// at a limb reaches its slots and no other (PLAN item 6: a stop names its scope); a joint on no bus is offline.
    #[test]
    fn the_skeleton_maps_onto_bus_threads_limb_by_limb() {
        let skeleton = fixture();
        let plans = plan(&skeleton).unwrap();
        let ids = |p: &BusPlan| {
            p.drives
                .iter()
                .map(|d| (d.device.get(), d.limb))
                .collect::<Vec<_>>()
        };
        assert_eq!(
            plans.iter().map(|p| p.name.as_str()).collect::<Vec<_>>(),
            ["can0", "can1"]
        );
        // can0: the right arm's first two joints, then the waist.
        assert_eq!(plans[0].limbs, [LimbName::RightArm, LimbName::Waist]);
        assert_eq!(ids(&plans[0]), [(21, 0), (22, 0), (31, 1)]);
        // can1: the left arm, then the right arm's third joint, under can1's own index for it.
        assert_eq!(plans[1].limbs, [LimbName::LeftArm, LimbName::RightArm]);
        assert_eq!(ids(&plans[1]), [(11, 0), (12, 0), (23, 1)]);
        assert_eq!(plans[1].joints[2].as_str(), "arm_b_three");
        assert!(plans.iter().all(|p| p.bitrate_bps == 1_000_000));
        // The leg's joint is on no bus: offline, and in no plan.
        assert_eq!(
            offline(&skeleton)
                .iter()
                .map(JointName::as_str)
                .collect::<Vec<_>>(),
            ["leg_a_one"]
        );
        assert_eq!(plans[0].limb_index(LimbName::LeftLeg), None);
        assert_eq!(plans[1].limb_index(LimbName::LeftLeg), None);
    }

    /// Guards: safety - a skeleton with no joint on any bus is refused rather than run with no bus thread, where control
    /// would end at once and the runtime would sit with nothing to stop (architecture.md section 5: refuse to start).
    #[test]
    fn a_skeleton_with_no_wired_joint_is_refused() {
        let text = include_str!("../tests/skeleton.yaml")
            .replace("bus: can0", "bus: null")
            .replace("bus: can1", "bus: null");
        assert_eq!(
            plan(&skeleton::parse(&text).unwrap()),
            Err(PlanError::NoBus)
        );
    }
}
