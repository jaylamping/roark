//! Stopping limbs: what starts a stop, what each stopping limb sends, when it is over, the bus error that stops every
//! limb at once, and the operator's re-arm.
//!
//! A stop sends Disable to every drive of the limb not yet confirmed, re-sent each tick, and active reporting off to
//! each confirmed drive once the post-Disable silence after its confirmation is over (a drive drops every frame in it,
//! PLAN.md item 2 Silence windows), until the socket takes it. A drive that never confirms is sent a Disable every
//! tick of the confirm window, so it never leaves its silence and gets no reporting off. The limb is stopped once every
//! drive has confirmed and taken its reporting off, or once the confirm window has passed and no confirmed drive still
//! waits for its reporting off ([`BusTick::stop_over`]).

use robstride::encode::{self, Reporting};

use crate::error_frame::BusError;
use crate::tick::{BusTick, DriveState, Phase};
use crate::timing::DRIVE_TIMEOUT_NS;
use crate::types::{LimbState, MAX_DRIVES, RearmRefused, Send, SendKind, StopOutcome, StopReason};

impl BusTick {
    /// Stop every limb not already stopping or stopped, for a reason that is the whole bus's.
    pub(crate) fn stop_all(&mut self, reason: StopReason, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            self.stop_limb_now(limb, reason, now_ns);
        }
    }

    /// A stop of the whole bus taken at a tick's start. A late wake or a backlog stops every active limb: an idle limb
    /// has nothing enabled to stop (its batch frames that tick go out late as expired, or not at all). Any other
    /// reason stops every limb.
    pub(crate) fn stop_bus(&mut self, reason: StopReason, now_ns: u64) {
        match reason {
            StopReason::LateWake | StopReason::Backlog => {
                for limb in 0..self.limbs.len() {
                    let active = self
                        .limbs
                        .get(limb)
                        .copied()
                        .flatten()
                        .is_some_and(|l| l.state == LimbState::Active);
                    if active {
                        self.stop_limb_now(limb, reason, now_ns);
                    }
                }
            }
            StopReason::Requested
            | StopReason::LimbRequested
            | StopReason::ControlSilent
            | StopReason::BadBatch { .. }
            | StopReason::ExpiredFeedback { .. }
            | StopReason::DriveFault { .. }
            | StopReason::DriveMode { .. }
            | StopReason::DriveSilent { .. }
            | StopReason::Bus(_) => self.stop_all(reason, now_ns),
        }
    }

    /// Start stopping limb `limb` now, unless it is already stopping or stopped (the first reason stays).
    pub(crate) fn stop_limb_now(&mut self, limb: usize, reason: StopReason, now_ns: u64) {
        let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut) else {
            return;
        };
        if !l.state.takes_commands() {
            return;
        }
        l.stop = Some(reason);
        l.state = LimbState::Stopping { since_ns: now_ns };
        l.pending = None;
        for d in self.drives.iter_mut().flatten().filter(|d| d.limb == limb) {
            d.stop = StopOutcome::NeverSent;
            d.confirmed_ns = None;
            d.reporting_off_sent = false;
        }
    }

    pub(crate) fn take_pending_limb_stops(&mut self, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            let pending = self
                .limbs
                .get_mut(limb)
                .and_then(Option::as_mut)
                .and_then(|l| l.pending.take());
            if let Some(reason) = pending {
                self.stop_limb_now(limb, reason, now_ns);
            }
        }
    }

    /// The check before every send, on what the drain just read: a drive of an idle or active limb that shows a fault,
    /// has left Run after running, or has missed too many replies in a row stops its limb before any command goes to
    /// it. An idle limb is checked too, so a faulted drive never gets its Enable.
    pub(crate) fn veto(&mut self, now_ns: u64) {
        for slot in 0..self.drives.len() {
            let Some(d) = self.drives.get(slot).copied().flatten() else {
                continue;
            };
            let takes_commands = self
                .limbs
                .get(d.limb)
                .copied()
                .flatten()
                .is_some_and(|l| l.state.takes_commands());
            if !takes_commands {
                continue;
            }
            if let Some(reason) = self.stop_due(slot, &d) {
                self.stop_limb_now(d.limb, reason, now_ns);
            }
        }
    }

    /// Why the drive in `slot` must stop its limb, if it must: a fault, a drop out of Run, or too many misses. The veto
    /// acts on it before the tick's sends, and a slow request is refused for it (slow traffic is a send too).
    pub(crate) fn stop_due(&self, slot: usize, d: &DriveState) -> Option<StopReason> {
        if d.fault_seen {
            Some(StopReason::DriveFault { slot })
        } else if d.phase == Phase::LeftRun {
            Some(StopReason::DriveMode { slot })
        } else if d.misses >= self.timing.silence_misses {
            Some(StopReason::DriveSilent { slot })
        } else {
            None
        }
    }

    /// The first stop any drive of limb `limb` is due for, so a slow request is refused for the whole limb the veto will
    /// stop, not only for the drive that shows it.
    pub(crate) fn limb_stop_due(&self, limb: usize) -> Option<StopReason> {
        self.drives
            .iter()
            .enumerate()
            .filter_map(|(slot, d)| d.as_ref().map(|d| (slot, d)))
            .filter(|(_, d)| d.limb == limb)
            .find_map(|(slot, d)| self.stop_due(slot, d))
    }

    /// The stop frames of every stopping limb, every Disable ahead of every reporting off (PLAN.md item 2 Stop:
    /// Disable to every affected drive, then reporting off), so a full queue never costs a Disable for a reporting off.
    /// Disables go to each drive not yet confirmed, inside the confirm window; reporting off to each confirmed drive
    /// once its silence is over. A limb whose stop is over ([`Self::stop_over`]) is stopped and sends nothing.
    pub(crate) fn plan_stops(&mut self, now_ns: u64) {
        let mut confirming = [false; MAX_DRIVES];
        let mut stopping = [false; MAX_DRIVES];
        for limb in 0..self.limbs.len() {
            let Some(LimbState::Stopping { since_ns }) =
                self.limbs.get(limb).copied().flatten().map(|l| l.state)
            else {
                continue;
            };
            if self.stop_over(limb, since_ns, now_ns) {
                if let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut) {
                    l.state = LimbState::Stopped;
                }
                continue;
            }
            if let (Some(c), Some(st)) = (confirming.get_mut(limb), stopping.get_mut(limb)) {
                *c = now_ns.saturating_sub(since_ns) < self.timing.stop_confirm_ns;
                *st = true;
            }
        }
        let flag =
            |table: &[bool; MAX_DRIVES], limb: usize| table.get(limb).copied().unwrap_or(false);
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && flag(&confirming, d.limb)
                && d.stop != StopOutcome::Confirmed
            {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::Disable,
                    frame: encode::disable(d.device),
                    expires: false,
                });
            }
        }
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && flag(&stopping, d.limb)
                && !d.reporting_off_sent
                && d.confirmed_ns
                    .is_some_and(|at| now_ns >= at.saturating_add(self.timing.disable_silence_ns))
            {
                self.sends.push(Send {
                    slot,
                    kind: SendKind::ReportingOff,
                    frame: encode::active_reporting(d.device, Reporting::Off),
                    expires: false,
                });
            }
        }
    }

    /// Whether limb `limb`'s stop, begun at `since_ns`, is over at `now_ns`. Disables go out for the confirm window; a
    /// drive confirmed in it (or by a Reset read just after it) still gets its reporting off once its silence is over,
    /// so the stop runs on past the window while one waits, at most until the window, the silence and a period have
    /// passed: a drive confirmed at the window's end is then a tick past its silence. The one place this is decided,
    /// for planning at `begin` and settling at `end`.
    pub(crate) fn stop_over(&self, limb: usize, since_ns: u64, now_ns: u64) -> bool {
        let elapsed = now_ns.saturating_sub(since_ns);
        if elapsed < self.timing.stop_confirm_ns {
            return false;
        }
        let waiting = self
            .drives
            .iter()
            .flatten()
            .filter(|d| d.limb == limb)
            .any(|d| d.confirmed_ns.is_some() && !d.reporting_off_sent);
        let cap = self
            .timing
            .stop_confirm_ns
            .saturating_add(self.timing.disable_silence_ns)
            .saturating_add(self.timing.period_ns);
        !waiting || elapsed >= cap
    }

    /// At the tick's end: a stopping limb whose drives have all confirmed and taken reporting off, or whose stop is
    /// over, is stopped.
    pub(crate) fn settle_stops(&mut self, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            let Some(LimbState::Stopping { since_ns }) =
                self.limbs.get(limb).copied().flatten().map(|l| l.state)
            else {
                continue;
            };
            let all_done = self
                .drives
                .iter()
                .flatten()
                .filter(|d| d.limb == limb)
                .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent);
            if (all_done || self.stop_over(limb, since_ns, now_ns))
                && let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut)
            {
                l.state = LimbState::Stopped;
            }
        }
    }

    /// A bus error that leaves nothing to send on: every limb stopped now, whatever it was doing. The first such error
    /// is kept in every later snapshot.
    pub(crate) fn latch(&mut self, error: BusError) {
        self.bus_error.get_or_insert(error);
        for limb in 0..self.limbs.len() {
            let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut) else {
                continue;
            };
            if l.state.takes_commands() {
                l.stop = Some(StopReason::Bus(error));
                for d in self.drives.iter_mut().flatten().filter(|d| d.limb == limb) {
                    d.stop = StopOutcome::NeverSent;
                }
            }
            l.state = LimbState::Stopped;
            l.pending = None;
        }
    }

    /// The operator cleared limb `limb` (PLAN.md item 6: a latched stop clears only by an operator `clear`): idle again,
    /// with its stop outcomes, fault history and miss counts started afresh, and a new generation. Each drive must
    /// first be confirmed in Reset by the stop, or have been sent nothing by this host for longer than the drive timeout
    /// since the last write the socket took (plus a period of margin for the adapter's queue), so it has dropped to
    /// Reset on its own. Every drive in it needs a
    /// fresh preflight before it is enabled again; that is the safety layer's.
    ///
    /// # Errors
    /// [`RearmRefused`] when the limb isn't on this bus, isn't stopped, the bus has failed, or a drive isn't known to
    /// be disabled yet.
    pub fn rearm(&mut self, limb: usize, now_ns: u64) -> Result<(), RearmRefused> {
        let Some(l) = self.limbs.get(limb).copied().flatten() else {
            return Err(RearmRefused::NoSuchLimb(limb));
        };
        if let Some(error) = self.bus_error {
            return Err(RearmRefused::BusFailed(error));
        }
        if l.state != LimbState::Stopped {
            return Err(RearmRefused::NotStopped(limb));
        }
        let quiet_ns = DRIVE_TIMEOUT_NS.saturating_add(self.timing.period_ns);
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && d.limb == limb
                && d.stop != StopOutcome::Confirmed
                && d.last_sent_ns
                    .is_some_and(|at| now_ns.saturating_sub(at) < quiet_ns)
            {
                return Err(RearmRefused::DriveNotQuiet { slot });
            }
        }
        if let Some(l) = self.limbs.get_mut(limb).and_then(Option::as_mut) {
            l.state = LimbState::Idle;
            l.stop = None;
            l.pending = None;
            l.generation = l.generation.saturating_add(1);
        }
        for d in self.drives.iter_mut().flatten().filter(|d| d.limb == limb) {
            d.stop = StopOutcome::None;
            d.confirmed_ns = None;
            d.reporting_off_sent = false;
            d.fault_seen = false;
            d.misses = 0;
            d.phase = Phase::Off;
            d.outstanding = None;
            d.fresh_ns = None;
        }
        Ok(())
    }
}
