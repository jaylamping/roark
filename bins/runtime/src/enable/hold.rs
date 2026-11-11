//! (rt) The hold: every enabled joint gets a command each tick from the tick its own drive is in Run, until its limb
//! stops on any bus. And `host.mode`'s limb-mate clause over each held limb, on every bus it is on.

use can::{LimbState, LimbView, Snapshot, StopReason};
use robstride::{MitCommand, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians, encode};
use safety::{HoldVerdict, Mate, limb_mates};
use skeleton::LimbName;

use super::{Buses, Counts, Enabler, Phase, place};
use crate::dispatch::StopLatch;
use crate::request::Scope;
use crate::roster::{Roster, RosterJoint};

impl Enabler {
    /// Hold every enabled joint whose limb is still Active on its bus and stopped on none; drop the rest, asking a stop
    /// of the whole limb when a part of it stopped on another bus (that bus's stop reaches only its own part). A held
    /// limb whose other drives `host.mode`'s limb-mate clause refuses is stopped, and its holds end at once. A joint of
    /// the enable running is held the same way; if its limb stopped, `step_run` has already failed the enable.
    pub(super) fn hold(
        &mut self,
        roster: &Roster,
        buses: &mut Buses<'_>,
        stops: &StopLatch,
        counts: &mut Counts,
    ) {
        for joint in 0..self.phases.len() {
            let Some(Phase::Enabled(drive)) = self.phases.get(joint) else {
                continue;
            };
            let drive = *drive;
            let Some(entry) = roster.joint(joint) else {
                continue;
            };
            let halted = halted(roster, buses.snapshots, entry.limb).is_some();
            let active =
                limb_on(buses.snapshots, entry).is_some_and(|l| l.state == LimbState::Active);
            if halted || !active {
                // Stopped elsewhere while Active here: this part must stop too. Stopped here, its bus has it.
                if halted && active {
                    stops.ask(Scope::Limb(entry.limb));
                }
                self.drop_hold(joint, counts);
                continue;
            }
            if let HoldVerdict::Stop(_) =
                limb_mates(self.mates(roster, buses.snapshots, entry.limb))
            {
                counts.mode_stops += 1;
                stops.ask(Scope::Limb(entry.limb));
                // Every hold of the limb ends now, so the stop is counted once.
                for mate in 0..self.phases.len() {
                    if roster.joint(mate).is_some_and(|m| m.limb == entry.limb) {
                        self.drop_hold(mate, counts);
                    }
                }
                continue;
            }
            match encode::mit(drive, &slack()) {
                Ok(frame) => place(buses, stops, entry, frame),
                // A model without MIT scales never passes preflight; stop rather than hold blind.
                Err(_) => stops.ask(Scope::Limb(entry.limb)),
            }
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

/// `entry`'s limb as its own bus's newest snapshot shows it.
pub(super) fn limb_on<'a>(
    snapshots: &'a [Option<Snapshot>],
    entry: &RosterJoint,
) -> Option<&'a LimbView> {
    let (bus, slot) = entry.slot()?;
    let snapshot = snapshots.get(bus)?.as_ref()?;
    snapshot.limb(snapshot.drive(slot)?.limb)
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
