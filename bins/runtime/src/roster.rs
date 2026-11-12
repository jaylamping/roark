//! Every joint the skeleton has, in skeleton order, with where it is wired and what preflight checks it against: what an
//! enable names and the control thread runs. Pure, so it is tested on any OS.

use safety::{Refusal, Target};
use skeleton::{BusName, JointName, LimbName, Skeleton};

use crate::plan::BusPlan;

/// The most joints a [`JointSet`] holds.
pub const MAX_JOINTS: usize = 64;

/// One joint as the runtime runs it.
#[derive(Clone, Debug, PartialEq)]
pub struct RosterJoint {
    /// Its name.
    pub name: JointName,
    /// Its limb.
    pub limb: LimbName,
    /// Where it is wired; `None` when it is on no bus (offline).
    pub at: Option<Wire>,
    /// What preflight checks its drive against, or why nothing can be: no bus, a model without settled MIT scales, or a
    /// cap its model can't take. A null fact or cap is no refusal: it lowers the caps (`skeleton::Joint::caps`).
    pub target: Result<Target, Refusal>,
}

/// Where a joint is wired.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Wire {
    /// Its bus, as its index in the plan.
    pub bus: usize,
    /// Its slot on that bus.
    pub slot: usize,
    /// Its bus's name, for the views preflight and the enable sequence check against.
    pub name: BusName,
}

impl RosterJoint {
    /// Its bus, as its index in the plan, and its slot there; `None` when it is offline.
    #[must_use]
    pub fn slot(&self) -> Option<(usize, usize)> {
        self.at.as_ref().map(|w| (w.bus, w.slot))
    }
}

/// Every joint, in skeleton order (limb by limb, each limb's joints in file order).
#[derive(Clone, Debug, PartialEq)]
pub struct Roster {
    joints: Vec<RosterJoint>,
}

/// A set of the roster's joints, by their index in it. `Copy`, with no allocation, so it can go through a ring.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct JointSet(u64);

/// A joint name the skeleton doesn't have.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
#[error("no joint {0} in the skeleton")]
pub struct UnknownJoint(pub String);

/// Why the roster can't be built.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("the skeleton has {0} joints; the runtime holds at most {MAX_JOINTS}")]
pub struct TooManyJoints(pub usize);

impl Roster {
    /// The roster of `skeleton`, wired as `plans` put it.
    ///
    /// # Errors
    /// More joints than a [`JointSet`] holds.
    pub fn new(skeleton: &Skeleton, plans: &[BusPlan]) -> Result<Self, TooManyJoints> {
        let joints: Vec<RosterJoint> = skeleton
            .limbs
            .iter()
            .flat_map(|limb| limb.joints.iter().map(move |joint| (limb.name, joint)))
            .map(|(limb, joint)| {
                let at = joint.bus.as_ref().and_then(|name| {
                    plans.iter().enumerate().find_map(|(bus, p)| {
                        (name.as_str() == p.name.as_str())
                            .then(|| p.joints.iter().position(|j| *j == joint.name))
                            .flatten()
                            .map(|slot| Wire {
                                bus,
                                slot,
                                name: name.clone(),
                            })
                    })
                });
                RosterJoint {
                    name: joint.name.clone(),
                    limb,
                    at,
                    target: Target::new(joint, &skeleton.power),
                }
            })
            .collect();
        if joints.len() > MAX_JOINTS {
            return Err(TooManyJoints(joints.len()));
        }
        Ok(Self { joints })
    }

    /// The joint at `index`.
    #[must_use]
    pub fn joint(&self, index: usize) -> Option<&RosterJoint> {
        self.joints.get(index)
    }

    /// How many joints.
    #[must_use]
    pub fn len(&self) -> usize {
        self.joints.len()
    }

    /// Every joint's name, by index: the table control's events name joints by.
    #[must_use]
    pub fn names(&self) -> Vec<String> {
        self.joints
            .iter()
            .map(|j| j.name.as_str().to_owned())
            .collect()
    }

    /// Whether there are none.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.joints.is_empty()
    }

    /// The joints named.
    ///
    /// # Errors
    /// The first name the skeleton doesn't have.
    pub fn set<'a>(
        &self,
        names: impl IntoIterator<Item = &'a str>,
    ) -> Result<JointSet, UnknownJoint> {
        let mut set = JointSet::default();
        for name in names {
            let index = self
                .joints
                .iter()
                .position(|j| j.name.as_str() == name)
                .ok_or_else(|| UnknownJoint(name.to_owned()))?;
            set.insert(index);
        }
        Ok(set)
    }
}

impl JointSet {
    /// Whether it holds no joint.
    #[must_use]
    pub const fn is_empty(self) -> bool {
        self.0 == 0
    }

    /// Whether it holds the joint at `index`.
    #[must_use]
    pub const fn contains(self, index: usize) -> bool {
        index < MAX_JOINTS && self.0 & (1 << index) != 0
    }

    /// Add the joint at `index`; one past [`MAX_JOINTS`] is ignored (the roster never has one).
    pub const fn insert(&mut self, index: usize) {
        if index < MAX_JOINTS {
            self.0 |= 1 << index;
        }
    }

    /// The joints, by index, in order.
    pub fn iter(self) -> impl Iterator<Item = usize> {
        (0..MAX_JOINTS).filter(move |i| self.contains(*i))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Guards: safety - an enable names joints by the skeleton's names and reaches exactly those joints, each at its own
    /// bus and slot, with the checks preflight runs from the skeleton; a joint on no bus has no slot and refuses as
    /// unwired, and a name the skeleton doesn't have is refused rather than ignored (PLAN item 6: enable is per joint
    /// set; tenet 1).
    #[test]
    fn the_roster_finds_each_named_joint_where_it_is_wired() {
        let skeleton = skeleton::parse(include_str!("../tests/skeleton.yaml")).unwrap();
        let plans = crate::plan(&skeleton).unwrap();
        let roster = Roster::new(&skeleton, &plans).unwrap();
        let at = |name: &str| {
            let set = roster.set([name]).unwrap();
            let i = set.iter().next().unwrap();
            roster.joint(i).unwrap().slot()
        };
        // can1 holds the left arm (slots 0 and 1) and the right arm's third joint (slot 2); can0 the right arm's first
        // two and the waist.
        assert_eq!(at("arm_a_one"), Some((1, 0)));
        assert_eq!(at("arm_a_two"), Some((1, 1)));
        assert_eq!(at("arm_b_three"), Some((1, 2)));
        assert_eq!(at("arm_b_one"), Some((0, 0)));
        assert_eq!(at("waist_one"), Some((0, 2)));
        assert_eq!(at("leg_a_one"), None);
        let leg = roster.set(["leg_a_one"]).unwrap().iter().next().unwrap();
        assert_eq!(roster.joint(leg).unwrap().target, Err(Refusal::Unwired));
        let left = roster.set(["arm_a_one", "arm_a_two"]).unwrap();
        assert!(left.iter().all(|i| roster.joint(i).unwrap().target.is_ok()));
        assert_eq!(
            roster.set(["arm_a_one", "elbow"]),
            Err(UnknownJoint("elbow".to_owned()))
        );
    }
}
