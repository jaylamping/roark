//! (rt) The hold: every enabled joint gets a command each tick from the tick its own drive is in Run, until its limb
//! stops on any bus. And `host.mode`'s limb-mate clause over each held limb, on every bus it is on.

use can::{LimbState, LimbView, Snapshot, StopReason};
use robstride::{MitCommand, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians, encode};
use safety::{Cause, HoldVerdict, Mate, RuleId, limb_mates};
use skeleton::LimbName;

use super::{Buses, Counts, Enabler, Phase, place};
use crate::latch::StopLatch;
use crate::request::Scope;
use crate::roster::{Roster, RosterJoint};

impl Enabler {
    /// Hold every enabled joint, deciding limb by limb. A held limb stopped on any bus has its holds end and a stop of
    /// the whole limb asked, since the bus that stopped it reaches only its own part; one that `host.mode`'s limb-mate
    /// clause refuses is stopped the same way, counted once. A joint whose own part is no longer Active (stopped and
    /// cleared since) just stops being held. The joints of the enable running were checked by `step_run` this pass,
    /// which failed the enable on either verdict; they are held as they are.
    pub(super) fn hold(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        counts: &mut Counts,
    ) {
        let running = self.run.map(|(_, joints)| joints).unwrap_or_default();
        for limb in LimbName::ALL {
            let held = |phases: &[Phase], j: usize| {
                !running.contains(j)
                    && matches!(phases.get(j), Some(Phase::Enabled(_)))
                    && roster.joint(j).is_some_and(|e| e.limb == limb)
            };
            if !(0..self.phases.len()).any(|j| held(&self.phases, j)) {
                continue;
            }
            let verdict = self.verdict(roster, buses.snapshots, limb);
            for joint in 0..self.phases.len() {
                if !held(&self.phases, joint) {
                    continue;
                }
                let Some(entry) = roster.joint(joint) else {
                    continue;
                };
                match verdict {
                    LimbVerdict::Hold
                        if limb_on(buses.snapshots, entry)
                            .is_some_and(|l| l.state == LimbState::Active) =>
                    {
                        self.send_hold(joint, entry, buses, stops);
                    }
                    LimbVerdict::Hold | LimbVerdict::Halted | LimbVerdict::Mate(_) => {
                        self.drop_hold(joint, counts);
                    }
                }
            }
            match verdict {
                LimbVerdict::Hold => {}
                LimbVerdict::Halted => ask_halt(roster, buses.snapshots, limb, stops),
                LimbVerdict::Mate(rule) => {
                    counts.mode_stops += 1;
                    stops.ask(Scope::Limb(limb), Cause::Rule(rule));
                }
            }
        }
        for joint in running.iter() {
            if let Some(entry) = roster.joint(joint) {
                self.send_hold(joint, entry, buses, stops);
            }
        }
    }

    /// `joint`'s slack command into the next batch, if it is enabled.
    fn send_hold(
        &self,
        joint: usize,
        entry: &RosterJoint,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
    ) {
        let Some(Phase::Enabled(drive)) = self.phases.get(joint) else {
            return;
        };
        match encode::mit(*drive, &slack()) {
            Ok(frame) => place(buses, stops, entry, frame),
            // A model without MIT scales never passes preflight, so this is a runtime bug; stop rather than hold blind.
            Err(_) => stops.ask(Scope::Limb(entry.limb), Cause::Rule(RuleId::HostHang)),
        }
    }

    /// Whether `limb` may go on being held: stopped on no bus, and every drive of it this host didn't enable seen in
    /// Reset (`host.mode`'s limb-mate clause).
    pub(super) fn verdict(
        &self,
        roster: &Roster,
        snapshots: &[Option<Snapshot>],
        limb: LimbName,
    ) -> LimbVerdict {
        if halted(roster, snapshots, limb).is_some() {
            return LimbVerdict::Halted;
        }
        match limb_mates(self.mates(roster, snapshots, limb)) {
            HoldVerdict::Hold => LimbVerdict::Hold,
            HoldVerdict::Stop(rule) => LimbVerdict::Mate(rule),
        }
    }

    /// End `joint`'s hold, if it has one.
    fn drop_hold(&mut self, joint: usize, counts: &mut Counts) {
        if let Some(phase) = self.phases.get_mut(joint)
            && let Phase::Enabled(_) = phase
        {
            *phase = Phase::Off;
            counts.holds_ended += 1;
        }
    }

    /// Every wired drive of `limb`, on whichever bus, as `host.mode`'s limb-mate clause sees it. A drive on no bus is
    /// offline and can't be seen by any bus.
    fn mates<'a>(
        &'a self,
        roster: &'a Roster,
        snapshots: &'a [Option<Snapshot>],
        limb: LimbName,
    ) -> impl Iterator<Item = Mate<'a>> + 'a {
        (0..roster.len()).filter_map(move |j| {
            let entry = roster.joint(j).filter(|e| e.limb == limb)?;
            let (bus, slot) = entry.slot()?;
            Some(Mate {
                view: snapshots
                    .get(bus)
                    .and_then(Option::as_ref)
                    .and_then(|s| s.drive(slot)),
                enabled_here: matches!(
                    self.phases.get(j),
                    Some(Phase::Enabling(_) | Phase::Enabled(_))
                ),
            })
        })
    }
}

/// What a held limb gets this pass.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum LimbVerdict {
    /// Held on.
    Hold,
    /// Stopped on some bus: stopped on every bus.
    Halted,
    /// A drive of it this host didn't enable left Reset, or can't be seen: stopped under this rule (`host.mode`).
    Mate(RuleId),
}

/// `entry`'s limb as its own bus's newest snapshot shows it.
pub(super) fn limb_on<'a>(
    snapshots: &'a [Option<Snapshot>],
    entry: &RosterJoint,
) -> Option<&'a LimbView> {
    let (bus, slot) = entry.slot()?;
    let snapshot = snapshots.get(bus)?.as_ref()?;
    snapshot.limb(snapshot.drive(slot)?.limb)
}

/// A held `limb` stopped on some bus, stopped on every bus: under each rule its stopped parts' own stops name (a bus's
/// `host.fault` or `host.silence`, say), or, when none names one, as following a stop asked of the bus, whose cause was
/// recorded when it was asked (the operator's, or control's own).
fn ask_halt(roster: &Roster, snapshots: &[Option<Snapshot>], limb: LimbName, stops: &StopLatch) {
    let mut any_rule = false;
    let rules = (0..roster.len())
        .filter_map(|j| roster.joint(j))
        .filter(|e| e.limb == limb)
        .filter_map(|e| limb_on(snapshots, e))
        .filter(|l| !l.state.takes_commands())
        .filter_map(|l| l.stop.and_then(RuleId::of_stop));
    for rule in rules {
        stops.ask(Scope::Limb(limb), Cause::Rule(rule));
        any_rule = true;
    }
    if !any_rule {
        stops.ask(Scope::Limb(limb), Cause::Follows);
    }
}

/// Why `limb` is stopping or stopped on some bus, if it is on any: the newest snapshot of every bus it is on.
#[expect(
    clippy::option_option,
    reason = "outer: whether some part is stopped; inner: whether its snapshot still says why"
)]
pub(super) fn halted(
    roster: &Roster,
    snapshots: &[Option<Snapshot>],
    limb: LimbName,
) -> Option<Option<StopReason>> {
    (0..roster.len())
        .filter_map(|j| roster.joint(j))
        .filter(|e| e.limb == limb)
        .filter_map(|e| limb_on(snapshots, e))
        .find(|l| !l.state.takes_commands())
        .map(|l| l.stop)
}

/// The hold every enabled drive gets until real control modes and their gains exist: zero gains and zero torque, so the
/// drive is in Run and watched by the bus's rules (`host.fault`, `host.mode`, `host.silence`) but holds nothing. It
/// commands no motion, so the motion rules (soft limits, total torque) have nothing to check yet.
#[expect(
    clippy::unwrap_used,
    reason = "zero is in range for every unit type; checked by the test"
)]
pub(super) fn slack() -> MitCommand {
    MitCommand {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(0.0).unwrap(),
        kd: NmSecPerRad::new(0.0).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    }
}
