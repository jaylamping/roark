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
/// A bus with more drives than a bus thread holds.
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
    Ok(plans)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Guards: safety - the skeleton in `config/` maps onto bus threads as the bus layer expects: one per wired bus,
    /// slots limb by limb in file order, and each bus's limb indices naming the skeleton limb they stand for, so a stop
    /// or clear aimed at a limb reaches its slots and no other (PLAN item 6: a stop names its scope).
    #[test]
    fn the_skeleton_maps_onto_bus_threads_limb_by_limb() {
        let skeleton = skeleton::load(std::path::Path::new("../../config/skeleton.yaml")).unwrap();
        let plans = plan(&skeleton).unwrap();
        for p in &plans {
            let bus = skeleton
                .buses
                .iter()
                .find(|b| b.name.as_str() == p.name)
                .unwrap();
            assert_eq!(p.bitrate_bps, bus.bitrate_bps);
            assert_eq!(p.drives.len(), p.joints.len());
            // Each slot's limb index names the skeleton limb that joint belongs to, and its ID is the joint's.
            for (drive, joint) in p.drives.iter().zip(&p.joints) {
                let limb = skeleton
                    .limbs
                    .iter()
                    .find(|l| l.joints.iter().any(|j| &j.name == joint))
                    .unwrap();
                let entry = limb.joints.iter().find(|j| &j.name == joint).unwrap();
                assert_eq!(p.limbs[drive.limb], limb.name, "{joint:?}");
                assert_eq!(drive.device, entry.id);
                assert_eq!(
                    entry.bus.as_ref().map(skeleton::BusName::as_str),
                    Some(p.name.as_str())
                );
            }
            // Slots run limb by limb: once a limb's slots end, it never comes back.
            let mut seen = Vec::new();
            for d in &p.drives {
                if seen.last() != Some(&d.limb) {
                    assert!(!seen.contains(&d.limb), "{p:?}");
                    seen.push(d.limb);
                }
            }
        }
        // Every wired joint has exactly one slot; an unwired one has none.
        let wired = skeleton
            .limbs
            .iter()
            .flat_map(|l| &l.joints)
            .filter(|j| j.bus.is_some())
            .count();
        assert_eq!(plans.iter().map(|p| p.drives.len()).sum::<usize>(), wired);
        assert!(plans.iter().all(|p| !p.drives.is_empty()));
    }
}
