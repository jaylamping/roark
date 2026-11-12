//! (rt) The stop latch: the operator's stops and control's own, each scope's causes in one atomic word, taken by
//! control once a pass. Pure, so it is tested on any OS; the control thread (Linux) and the runtime's `stop` are its
//! users.

use std::sync::atomic::{AtomicU32, Ordering};

use safety::{Cause, RuleId};
use skeleton::LimbName;

use crate::request::Scope;

/// The causes a scope's stop was asked for, one bit each: the operator, shutdown, a stop carried from another bus, then
/// each rule by [`RuleId::index`]. Never 0 for a stop asked.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Causes(u32);

/// The bit of the first rule; the bits below are the causes that aren't rules.
const FIRST_RULE: usize = 3;
const _: () = assert!(
    FIRST_RULE + RuleId::ALL.len() <= 32,
    "a cause per bit of a u32"
);

impl Causes {
    /// The bit for `cause`.
    const fn bit(cause: Cause) -> u32 {
        let n = match cause {
            Cause::Operator => 0,
            Cause::Shutdown => 1,
            Cause::Follows => 2,
            Cause::Rule(rule) => FIRST_RULE + rule.index(),
        };
        1 << n
    }

    /// Whether no cause is set: no stop asked.
    pub(crate) const fn is_empty(self) -> bool {
        self.0 == 0
    }

    /// Each cause set, the ones that aren't rules first, then the rules in [`RuleId::ALL`] order.
    pub(crate) fn iter(self) -> impl Iterator<Item = Cause> {
        Self::ALL
            .into_iter()
            .filter(move |c| self.0 & Self::bit(*c) != 0)
    }

    /// Whether a bit is set that no cause decodes to: a cause missing from [`Self::ALL`], which the compile-time check
    /// above rules out, but which the event log would then say rather than drop.
    pub(crate) fn unknown(self) -> bool {
        self.iter().fold(self.0, |left, c| left & !Self::bit(c)) != 0
    }

    /// Every cause, in decoding order.
    #[expect(
        clippy::indexing_slicing,
        reason = "checked at compile time: an index out of range fails the build"
    )]
    const ALL: [Cause; FIRST_RULE + RuleId::ALL.len()] = {
        let mut all = [Cause::Operator; FIRST_RULE + RuleId::ALL.len()];
        all[1] = Cause::Shutdown;
        all[2] = Cause::Follows;
        let mut i = 0;
        while i < RuleId::ALL.len() {
            all[FIRST_RULE + i] = Cause::Rule(RuleId::ALL[i]);
            i += 1;
        }
        all
    };
}

/// The operator's stops and control's own, latched until control takes them once a pass: per scope, every cause it was
/// asked for. A scope's causes are its latch (any set is a stop), so asking is one atomic OR and taking one swap: a stop
/// is never taken without its cause, nor a cause without its stop. Asking never fails, waits or allocates, and a stop
/// asked again before control takes it is the same stop, so a burst of stops can't fill anything (PLAN item 3a: stop is
/// always accepted and jumps the queue: control takes stops before any clear).
#[derive(Debug, Default)]
pub(crate) struct StopLatch {
    /// The five limbs in [`LimbName::ALL`] order, then the robot.
    scopes: [AtomicU32; SCOPES],
}

/// The robot's slot, after the limbs'.
const ROBOT: usize = LimbName::ALL.len();
/// The latch's scopes: every limb and the robot.
const SCOPES: usize = ROBOT + 1;
#[expect(
    clippy::indexing_slicing,
    reason = "checked at compile time: an index out of range fails the build"
)]
const _: () = {
    let mut i = 0;
    while i < LimbName::ALL.len() {
        assert!(
            slot(Scope::Limb(LimbName::ALL[i])) == i,
            "each limb's slot is its place in LimbName::ALL"
        );
        i += 1;
    }
};

/// A scope's slot in the latch.
const fn slot(scope: Scope) -> usize {
    match scope {
        Scope::Robot => ROBOT,
        Scope::Limb(LimbName::LeftArm) => 0,
        Scope::Limb(LimbName::RightArm) => 1,
        Scope::Limb(LimbName::Waist) => 2,
        Scope::Limb(LimbName::LeftLeg) => 3,
        Scope::Limb(LimbName::RightLeg) => 4,
    }
}

impl StopLatch {
    /// Ask for a stop of `scope`, for `cause`.
    pub(crate) fn ask(&self, scope: Scope, cause: Cause) {
        // Every slot is in range (checked above); were one not, the robot's stop covers it.
        if let Some(causes) = self.scopes.get(slot(scope)).or(self.scopes.last()) {
            causes.fetch_or(Causes::bit(cause), Ordering::AcqRel);
        }
    }

    /// Every stop asked since the last take, with its causes, clearing the latch.
    pub(crate) fn take(&self) -> Stops {
        let mut stops = Stops::default();
        for (causes, taken) in self.scopes.iter().zip(&mut stops.causes) {
            *taken = Causes(causes.swap(0, Ordering::AcqRel));
        }
        stops
    }
}

/// The stops taken from a [`StopLatch`] at once.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Stops {
    causes: [Causes; SCOPES],
}

impl Stops {
    /// Whether no stop was taken.
    pub(crate) fn is_empty(&self) -> bool {
        self.causes.iter().all(|c| c.is_empty())
    }

    /// The scopes to stop: the robot alone when it was asked, since it covers every limb; otherwise each limb asked, in
    /// [`LimbName::ALL`] order.
    pub(crate) fn scopes(self) -> impl Iterator<Item = Scope> {
        let robot = !self.of(Scope::Robot).is_empty();
        robot.then_some(Scope::Robot).into_iter().chain(
            LimbName::ALL
                .into_iter()
                .map(Scope::Limb)
                .filter(move |s| !robot && !self.of(*s).is_empty()),
        )
    }

    /// Every scope asked, the robot first, with every cause it was asked for: a limb's causes are kept even when the
    /// robot's stop covers it.
    pub(crate) fn asked(self) -> impl Iterator<Item = (Scope, Causes)> {
        std::iter::once(Scope::Robot)
            .chain(LimbName::ALL.into_iter().map(Scope::Limb))
            .map(move |s| (s, self.of(s)))
            .filter(|(_, c)| !c.is_empty())
    }

    /// `scope`'s causes.
    fn of(self, scope: Scope) -> Causes {
        self.causes.get(slot(scope)).copied().unwrap_or_default()
    }
}

/// Every scope a take holds, with its causes: for the tests here and of what uses the latch.
#[cfg(test)]
pub(crate) fn asked(stops: Stops) -> Vec<(Scope, Vec<Cause>)> {
    stops
        .asked()
        .map(|(scope, causes)| (scope, causes.iter().collect()))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Guards: safety - every stop asked before control takes the latch is taken, each scope once however often it was
    /// asked, with every cause it was asked for (a limb's kept under a robot stop that covers it), and a robot stop is
    /// routed alone since it covers every limb; nothing is left for the next take (PLAN item 3a: stop is always
    /// accepted; safety.md section 8: every stop is an event naming its rule).
    #[test]
    fn the_stop_latch_keeps_every_stop_and_every_cause_until_taken() {
        let latch = StopLatch::default();
        assert!(latch.take().is_empty());
        latch.ask(Scope::Limb(LimbName::Waist), Cause::Rule(RuleId::HostMode));
        latch.ask(Scope::Limb(LimbName::RightLeg), Cause::Follows);
        latch.ask(Scope::Limb(LimbName::Waist), Cause::Operator);
        latch.ask(Scope::Limb(LimbName::LeftArm), Cause::Operator);
        latch.ask(Scope::Limb(LimbName::LeftArm), Cause::Operator);
        let stops = latch.take();
        assert_eq!(
            stops.scopes().collect::<Vec<_>>(),
            [
                Scope::Limb(LimbName::LeftArm),
                Scope::Limb(LimbName::Waist),
                Scope::Limb(LimbName::RightLeg)
            ]
        );
        assert_eq!(
            asked(stops),
            [
                (Scope::Limb(LimbName::LeftArm), vec![Cause::Operator]),
                (
                    Scope::Limb(LimbName::Waist),
                    vec![Cause::Operator, Cause::Rule(RuleId::HostMode)]
                ),
                (Scope::Limb(LimbName::RightLeg), vec![Cause::Follows])
            ]
        );
        assert!(latch.take().is_empty());
        latch.ask(
            Scope::Limb(LimbName::RightArm),
            Cause::Rule(RuleId::HostMode),
        );
        latch.ask(Scope::Robot, Cause::Shutdown);
        let stops = latch.take();
        assert_eq!(stops.scopes().collect::<Vec<_>>(), [Scope::Robot]);
        assert_eq!(
            asked(stops),
            [
                (Scope::Robot, vec![Cause::Shutdown]),
                (
                    Scope::Limb(LimbName::RightArm),
                    vec![Cause::Rule(RuleId::HostMode)]
                )
            ]
        );
        assert!(latch.take().is_empty());
        // Every rule is kept as itself: ALL holds each at its index, and each round-trips the latch.
        for (i, rule) in RuleId::ALL.into_iter().enumerate() {
            assert_eq!(rule.index(), i, "{rule}");
        }
        for (limb, rule) in LimbName::ALL.into_iter().cycle().zip(RuleId::ALL) {
            latch.ask(Scope::Limb(limb), Cause::Rule(rule));
            assert_eq!(
                asked(latch.take()),
                [(Scope::Limb(limb), vec![Cause::Rule(rule)])]
            );
        }
    }

    /// Guards: safety - stops asked from other threads while control takes the latch are each taken, by the next take
    /// at the latest, under the cause they were asked for and never another's (safety.md section 8).
    #[test]
    fn stops_asked_during_a_take_keep_their_own_cause() {
        let latch = std::sync::Arc::new(StopLatch::default());
        let askers: Vec<_> = [
            (LimbName::LeftArm, Cause::Operator),
            (LimbName::Waist, Cause::Rule(RuleId::HostMode)),
        ]
        .into_iter()
        .map(|(limb, cause)| {
            let latch = std::sync::Arc::clone(&latch);
            std::thread::spawn(move || {
                for _ in 0..10_000 {
                    latch.ask(Scope::Limb(limb), cause);
                }
            })
        })
        .collect();
        let mut seen = Vec::new();
        while !askers.iter().all(std::thread::JoinHandle::is_finished) {
            seen.extend(asked(latch.take()));
        }
        for asker in askers {
            asker.join().unwrap();
        }
        seen.extend(asked(latch.take()));
        assert!(seen.contains(&(Scope::Limb(LimbName::LeftArm), vec![Cause::Operator])));
        assert!(seen.contains(&(
            Scope::Limb(LimbName::Waist),
            vec![Cause::Rule(RuleId::HostMode)]
        )));
        assert!(seen.iter().all(|s| matches!(
            s,
            (Scope::Limb(LimbName::LeftArm), c) if *c == [Cause::Operator]
        ) || matches!(
            s,
            (Scope::Limb(LimbName::Waist), c) if *c == [Cause::Rule(RuleId::HostMode)]
        )));
        assert!(latch.take().is_empty());
    }
}
