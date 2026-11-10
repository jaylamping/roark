//! Stopping limbs: what starts a stop, what each stopping limb sends, when it is over, the bus error that stops every
//! limb at once, and the operator's re-arm.
//!
//! A stop sends Disable to every drive of the limb not yet confirmed, re-sent each tick of the confirm window
//! ([`Timing::stop_confirm_ns`](crate::Timing::stop_confirm_ns)). A drive confirms with a Reset read after the stop's
//! Disable inside the reply allowance ([`Timing::stop_replies_ns`](crate::Timing::stop_replies_ns): the window, a
//! period and the send window, for the reply to its last Disable); a Reset read later confirms nothing, and any other
//! mode read after a confirmation withdraws it (`DriveState::note_mode`). Each confirmed drive is sent active reporting
//! off once the post-Disable silence after its confirmation is over (a drive drops every frame in it, PLAN.md item 2
//! Silence windows), every tick until the socket takes it. A drive that never confirms gets no reporting off. When the
//! stop ends is decided in one place, [`BusTick::stop_over`], bounded by
//! [`Timing::stop_max_ns`](crate::Timing::stop_max_ns).

use robstride::EchoKind;
use robstride::encode::{self, Reporting};

use crate::error_frame::BusError;
use crate::tick::{BusTick, DriveStop, Off, Phase, limb_state};
use crate::timing::DRIVE_TIMEOUT_NS;
use crate::types::{LimbState, RearmRefused, Send, SendKind, StopReason};

impl BusTick {
    /// Stop every limb not already stopping or stopped, for a reason that is the whole bus's.
    pub(crate) fn stop_all(&mut self, reason: StopReason, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            self.stop_limb_now(limb, reason, now_ns);
        }
    }

    /// Stop every active limb, for a late wake or a backlog: an idle limb has nothing enabled to stop (that tick only
    /// its batch's Disables and reporting off go, [`Self::begin`]).
    pub(crate) fn stop_active(&mut self, reason: StopReason, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            if limb_state(&self.limbs, limb) == Some(LimbState::Active) {
                self.stop_limb_now(limb, reason, now_ns);
            }
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
            d.stop = DriveStop::NeverSent;
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
            let takes_commands =
                limb_state(&self.limbs, d.limb).is_some_and(LimbState::takes_commands);
            if !takes_commands {
                continue;
            }
            let reason = if d.fault_seen {
                Some(StopReason::DriveFault { slot })
            } else if d.phase == Phase::LeftRun {
                Some(StopReason::DriveMode { slot })
            } else if d.misses >= self.timing.silence_misses {
                Some(StopReason::DriveSilent { slot })
            } else {
                None
            };
            if let Some(reason) = reason {
                self.stop_limb_now(d.limb, reason, now_ns);
            }
        }
    }

    /// Every stopping limb's Disables: to each drive not yet confirmed, inside the confirm window. Planned after
    /// [`Self::settle_stops`], so a limb whose stop is over is stopped and sends nothing, and ahead of every reporting
    /// off ([`Self::begin`] has the order).
    pub(crate) fn plan_stop_disables(&mut self, now_ns: u64) {
        let confirm_ns = self.timing.stop_confirm_ns;
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && let Some(LimbState::Stopping { since_ns }) = limb_state(&self.limbs, d.limb)
                && now_ns.saturating_sub(since_ns) < confirm_ns
                && !d.stop.confirmed()
            {
                let send = Send {
                    slot,
                    kind: SendKind::Disable,
                    frame: encode::disable(d.device),
                    expires: false,
                };
                self.planned.push(send, EchoKind::Disable);
            }
        }
    }

    /// Every stopping limb's reporting off: to each confirmed drive whose silence is over, every tick until the socket
    /// takes it.
    pub(crate) fn plan_stop_reporting_off(&mut self, now_ns: u64) {
        let silence = self.timing.disable_silence_ns;
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && let Some(LimbState::Stopping { .. }) = limb_state(&self.limbs, d.limb)
                && let DriveStop::Confirmed {
                    at_ns,
                    off: Off::Unsent,
                } = d.stop
                && now_ns >= at_ns.saturating_add(silence)
            {
                let send = Send {
                    slot,
                    kind: SendKind::ReportingOff,
                    frame: encode::active_reporting(d.device, Reporting::Off),
                    expires: false,
                };
                self.planned.push(send, EchoKind::Reporting(Reporting::Off));
            }
        }
    }

    /// Whether limb `limb`'s stop, begun at `since_ns`, is over at `now_ns`; the one place this is decided, for
    /// planning at `begin` and settling at `end`. It is over once every drive has confirmed and the socket took its
    /// reporting off. Otherwise never before the reply allowance closes ([`Timing::stop_replies_ns`], when a Reset can
    /// no longer confirm), and after it as soon as no confirmed drive's reporting off is still unsent, or at the
    /// latest at [`Timing::stop_max_ns`], with any reporting off never taken recorded unsent.
    ///
    /// [`Timing::stop_replies_ns`]: crate::Timing::stop_replies_ns
    /// [`Timing::stop_max_ns`]: crate::Timing::stop_max_ns
    pub(crate) fn stop_over(&self, limb: usize, since_ns: u64, now_ns: u64) -> bool {
        let mut drives = self.drives.iter().flatten().filter(|d| d.limb == limb);
        if drives
            .clone()
            .all(|d| matches!(d.stop, DriveStop::Confirmed { off: Off::Sent, .. }))
        {
            return true;
        }
        let elapsed = now_ns.saturating_sub(since_ns);
        if elapsed < self.timing.stop_replies_ns() {
            return false;
        }
        elapsed >= self.timing.stop_max_ns()
            || !drives.any(|d| {
                matches!(
                    d.stop,
                    DriveStop::Confirmed {
                        off: Off::Unsent,
                        ..
                    }
                )
            })
    }

    /// At the tick's start, before its stop frames are planned, and at its end: a stopping limb whose stop is over
    /// ([`Self::stop_over`]) is stopped.
    pub(crate) fn settle_stops(&mut self, now_ns: u64) {
        for limb in 0..self.limbs.len() {
            let Some(LimbState::Stopping { since_ns }) = limb_state(&self.limbs, limb) else {
                continue;
            };
            if self.stop_over(limb, since_ns, now_ns)
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
                    d.stop = DriveStop::NeverSent;
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
        let Some(state) = limb_state(&self.limbs, limb) else {
            return Err(RearmRefused::NoSuchLimb(limb));
        };
        if let Some(error) = self.bus_error {
            return Err(RearmRefused::BusFailed(error));
        }
        if state != LimbState::Stopped {
            return Err(RearmRefused::NotStopped(limb));
        }
        let quiet_ns = DRIVE_TIMEOUT_NS.saturating_add(self.timing.period_ns);
        for (slot, d) in self.drives.iter().enumerate() {
            if let Some(d) = d
                && d.limb == limb
                && !d.stop.confirmed()
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
            d.stop = DriveStop::None;
            d.fault_seen = false;
            d.misses = 0;
            d.phase = Phase::Off;
            d.outstanding = None;
            d.fresh_ns = None;
            d.fresh_status = None;
        }
        Ok(())
    }
}
