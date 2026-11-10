//! Control's batch on the tick: checked whole before any of it is sent, then planned around the stops' frames, each
//! frame decoded once (rust.md section 9: no added latency on the hot path).

use robstride::encode::Reporting;
use robstride::{
    DecodeError, DeviceId, EchoKind, Frame, Inbound, Param, ParamValue, RunMode, decode,
};

use crate::tick::{BusTick, limb_state};
use crate::types::{
    CommandBatch, LimbState, MAX_DRIVES, MAX_SENDS, Send, SendKind, SendList, StopReason,
};

/// How a batch for this tick was taken.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Taken {
    /// Unexpired: all of it goes, but for what a held tick holds back.
    Fresh,
    /// Past its expiry: counted stale, and only its Disables and reporting off go.
    Expired,
}

/// This tick's sends, and what each one is, set when it is planned so [`BusTick::sent`] needn't decode it.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Planned {
    pub(crate) sends: SendList,
    kinds: [Option<EchoKind>; MAX_SENDS],
}

impl Planned {
    pub(crate) const EMPTY: Self = Self {
        sends: SendList::EMPTY,
        kinds: [None; MAX_SENDS],
    };

    /// Plan `send`, a frame of `kind`, as the next send.
    pub(crate) fn push(&mut self, send: Send, kind: EchoKind) {
        if let Some(k) = self.kinds.get_mut(self.sends.len()) {
            *k = Some(kind);
        }
        self.sends.push(send);
    }

    pub(crate) fn get(&self, index: usize) -> Option<(Send, Option<EchoKind>)> {
        let send = self.sends.get(index)?;
        Some((send, self.kinds.get(index).copied().flatten()))
    }
}

/// A batch for this tick that passed its checks: how it was taken, and each slot's frame kind, decoded once.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Accepted<'b> {
    batch: &'b CommandBatch,
    taken: Taken,
    kinds: [Option<EchoKind>; MAX_DRIVES],
}

/// Which of a batch's frames a pass over it plans: its Disables go ahead of the stops' reporting off, the rest after.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Part {
    Disables,
    Rest,
}

impl BusTick {
    /// Plan this tick's sends after the stops are settled: every Disable goes ahead of every reporting off, whoever
    /// planned it, so a queue that fills after the first frames never costs a Disable (PLAN.md item 2 Stop): the
    /// stops' Disables, the batch's, the stops' reporting off, then the rest of the batch. With `hold`, of the batch
    /// only its Disables and reporting off.
    pub(crate) fn plan_sends(&mut self, accepted: Option<Accepted<'_>>, hold: bool, now_ns: u64) {
        self.plan_stop_disables(now_ns);
        if let Some(accepted) = accepted {
            // An expired batch was counted stale already; its Disables and reporting off still go, the rest is dropped.
            let hold = hold || accepted.taken == Taken::Expired;
            self.push_commands(&accepted, hold, Part::Disables);
            self.plan_stop_reporting_off(now_ns);
            if self.push_commands(&accepted, hold, Part::Rest) && accepted.taken == Taken::Fresh {
                self.counters.held_batches += 1;
            }
        } else {
            self.plan_stop_reporting_off(now_ns);
        }
    }

    /// The batch for this tick if it is sound, and whether it is fresh. A batch for another tick, or past its expiry,
    /// counts the tick stale and toward control's silence; one for another tick is not used at all, while an expired
    /// one for this tick still yields its Disables and reporting off, which are right late or not (can.md section 2).
    /// A frame aimed wrong, in a slot with no drive, or of a kind a batch may not carry is a bug upstream and stops the
    /// whole bus; motion on expired feedback in a fresh batch stops that drive's limb.
    pub(crate) fn check_batch<'b>(
        &mut self,
        tick: u64,
        now_ns: u64,
        batch: Option<&'b CommandBatch>,
    ) -> Option<Accepted<'b>> {
        let this_tick = batch.filter(|b| b.tick == tick);
        if this_tick.is_some_and(|b| b.expires_ns > now_ns) {
            self.silent = 0;
        } else {
            if batch.is_some() {
                self.counters.stale_ticks += 1;
            }
            // Counted with every limb idle too: silent control also cancels slow requests.
            self.silent = self.silent.saturating_add(1);
            let active = self
                .limbs
                .iter()
                .flatten()
                .any(|l| l.state == LimbState::Active);
            if active && self.silent >= self.timing.silent_ticks {
                self.stop_all(StopReason::ControlSilent, now_ns);
            }
        }
        let batch = this_tick?;
        let taken = if batch.expires_ns > now_ns {
            Taken::Fresh
        } else {
            Taken::Expired
        };
        // Check the whole batch before sending any of it, decoding each frame once.
        let mut kinds = [None; MAX_DRIVES];
        for (slot, (frame, kind)) in batch.frames().iter().zip(&mut kinds).enumerate() {
            let Some(frame) = frame else { continue };
            let device = self
                .drives
                .get(slot)
                .and_then(Option::as_ref)
                .map(|d| d.device);
            match (device, echo_of(frame)) {
                (Some(device), Some((k, target))) if target == device && batch_may_carry(k) => {
                    *kind = Some(k);
                }
                _ => {
                    self.bad_batch(slot, now_ns);
                    return None;
                }
            }
        }
        if taken == Taken::Fresh {
            for (slot, kind) in kinds.iter().enumerate() {
                let Some(d) = self.drives.get(slot).and_then(Option::as_ref) else {
                    continue;
                };
                let stale = d
                    .fresh_ns
                    .is_none_or(|at| now_ns.saturating_sub(at) > self.timing.feedback_limit_ns);
                if *kind == Some(EchoKind::Mit) && stale {
                    self.stop_limb_now(d.limb, StopReason::ExpiredFeedback { slot }, now_ns);
                }
            }
        }
        Some(Accepted {
            batch,
            taken,
            kinds,
        })
    }

    /// A bad batch stops every limb. If this tick's stops already took the last idle or active one, there is nothing left
    /// to stop and no stop records it, so it is counted as refused.
    fn bad_batch(&mut self, slot: usize, now_ns: u64) {
        if !self.any_running() {
            self.counters.refused_batches += 1;
        }
        self.stop_all(StopReason::BadBatch { slot }, now_ns);
    }

    /// The batch's frames in `part` for limbs still idle or active; those for a stopping or stopped limb are dropped,
    /// and counted in the pass over the rest. With `hold`, only its Disables and reporting off; returns whether
    /// anything else was held back.
    fn push_commands(&mut self, accepted: &Accepted<'_>, hold: bool, part: Part) -> bool {
        let mut held_back = false;
        let frames = accepted.batch.frames().iter().zip(accepted.kinds);
        for (slot, (frame, kind)) in frames.enumerate() {
            let (Some(frame), Some(kind), Some(limb)) = (
                frame,
                kind,
                self.drives
                    .get(slot)
                    .and_then(Option::as_ref)
                    .map(|d| d.limb),
            ) else {
                continue;
            };
            let running = limb_state(&self.limbs, limb).is_some_and(LimbState::takes_commands);
            if !running {
                if part == Part::Rest {
                    self.counters.refused_frames += 1;
                }
                continue;
            }
            if (kind == EchoKind::Disable) != (part == Part::Disables) {
                continue;
            }
            let late_ok = matches!(
                kind,
                EchoKind::Disable | EchoKind::Reporting(Reporting::Off)
            );
            if hold && !late_ok {
                held_back = true;
                continue;
            }
            self.planned.push(
                Send {
                    slot,
                    kind: SendKind::Command,
                    frame: *frame,
                    expires: !late_ok,
                },
                kind,
            );
        }
        held_back
    }
}

/// Whether control's batch may carry a frame of this kind: motion, Enable, Disable, and the enable sequence's active
/// reporting off and `run_mode` = MIT write (PLAN.md item 2 Enable one drive). Set Zero, set-ID, parameter reads and
/// other writes, reporting on and queries each need sequencing a per-tick batch can't give (PLAN.md item 2: Set Zero
/// only with the limb stopped, set-ID only with one drive answering); a set-ID would also leave the drive table on the
/// old ID.
pub(crate) fn batch_may_carry(kind: EchoKind) -> bool {
    matches!(
        kind,
        EchoKind::Mit
            | EchoKind::Enable
            | EchoKind::Disable
            | EchoKind::Reporting(Reporting::Off)
            | EchoKind::ParamWrite {
                param: Param::RunMode,
                value: ParamValue::RunMode(RunMode::Mit),
            }
    )
}

/// What a host frame is and whom it targets, read back through the codec (so the ID layout stays in `robstride`).
fn echo_of(frame: &Frame) -> Option<(EchoKind, DeviceId)> {
    match decode(frame.id(), &frame.data()) {
        Ok(Inbound::Echo(echo)) => Some((echo.kind, echo.target)),
        Ok(
            Inbound::Identity { .. }
            | Inbound::Status(_)
            | Inbound::Report(_)
            | Inbound::Fault { .. }
            | Inbound::Version { .. }
            | Inbound::Param { .. },
        )
        | Err(
            DecodeError::IdTooWide(_)
            | DecodeError::BadLength { .. }
            | DecodeError::UnknownType { .. }
            | DecodeError::BadDeviceId { .. }
            | DecodeError::ReservedMode { .. }
            | DecodeError::UnknownParam { .. }
            | DecodeError::BadParamValue { .. }
            | DecodeError::UnexpectedData { .. }
            | DecodeError::OtherHost { .. }
            | DecodeError::ForeignType { .. }
            | DecodeError::ForeignWrite { .. },
        ) => None,
    }
}
