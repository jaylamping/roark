//! A scan's probes and the set-ID: the slow requests named by ID rather than slot. How their window closes, what
//! answers them and when they may go; the rest of their path is every slow request's (`slow`). The rules are in
//! crates/can/README.md, Slow requests.

use robstride::{DeviceId, Uid};

use crate::slow::{SlowEntry, SlowKind, SlowOutcome, SlowRefusal, SlowState};
use crate::tick::BusTick;
use crate::types::LimbState;

impl SlowKind {
    /// The ID whose type-0 replies answer this request: a probe's ID, or a set-ID's new one. `None` for a request
    /// named by slot.
    #[must_use]
    pub const fn answer_id(self) -> Option<DeviceId> {
        match self {
            Self::Probe(id) | Self::SetId { new: id, .. } => Some(id),
            Self::Read(_) | Self::Write(_) | Self::GetId => None,
        }
    }
}

impl BusTick {
    /// What `entry`, in flight, ends as once its reply window is over. A probe or set-ID ends [`SlowOutcome::Unsure`]
    /// if its window was disturbed (an error frame or a kernel drop in it), the last drain left frames unread, or the
    /// bus has failed (a failed drain never reports how it went): an answer may be among what wasn't read. Otherwise it
    /// ends `Found` with what it heard, or timed out. Any other request is timed out.
    pub(crate) fn window_closed(&self, entry: &SlowEntry) -> SlowOutcome {
        let by_id = entry.request.kind.answer_id().is_some();
        if by_id && (entry.disturbed || self.unordered || self.bus_error.is_some()) {
            return SlowOutcome::Unsure;
        }
        match entry.state {
            SlowState::Heard { uid, other } => SlowOutcome::Found { uid, other },
            SlowState::Queued | SlowState::Sending | SlowState::Waiting | SlowState::Done(_) => {
                SlowOutcome::TimedOut
            }
        }
    }

    /// An error frame was read, or the kernel dropped frames: a probe or set-ID in flight can no longer say it heard
    /// every answer.
    pub(crate) fn slow_disturbed(&mut self) {
        for e in self.slow.iter_mut().flatten() {
            if e.state.in_flight() && e.request.kind.answer_id().is_some() {
                e.disturbed = true;
            }
        }
    }

    /// A type-0 reply from `device`: whether it answers the probe or set-ID in flight, a probe of `device` or a set-ID
    /// to `device`. It is held, with any other UID heard on that ID, until the next tick's start.
    pub(crate) fn slow_found_reply(&mut self, device: DeviceId, uid: Uid) -> bool {
        let Some(entry) = self.slow.iter_mut().flatten().find(|e| {
            matches!(e.state, SlowState::Waiting | SlowState::Heard { .. })
                && e.request.kind.answer_id() == Some(device)
        }) else {
            return false;
        };
        entry.state = match entry.state {
            SlowState::Waiting => SlowState::Heard { uid, other: None },
            SlowState::Heard {
                uid: first,
                other: None,
            } if first != uid => SlowState::Heard {
                uid: first,
                other: Some(uid),
            },
            state @ (SlowState::Heard { .. }
            | SlowState::Queued
            | SlowState::Sending
            | SlowState::Done(_)) => state,
        };
        true
    }

    /// Why a probe or set-ID may not go now: the bus has failed, a limb on it isn't idle (or a stop of it is asked or
    /// due), or control is silent. Its frame may reach any drive on the bus, so every limb must be idle, not only one.
    pub(crate) fn bus_request_refusal(&self) -> Result<(), SlowRefusal> {
        if self.bus_error.is_some() {
            return Err(SlowRefusal::BusFailed);
        }
        for (i, limb) in self.limbs.iter().enumerate() {
            if let Some(limb) = limb
                && (limb.state != LimbState::Idle || self.limb_halting(i, limb.state))
            {
                return Err(SlowRefusal::BusNotIdle);
            }
        }
        if self.silent >= self.timing.silent_ticks {
            return Err(SlowRefusal::ControlSilent);
        }
        Ok(())
    }
}
