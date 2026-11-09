//! Frames read from the socket, before the send (the drain) or after it (the collect): what each one says about the bus
//! and its drives.

use robstride::{DecodeError, DeviceId, Inbound, Mode, Status, decode};
use telemetry::{Direction, FrameRecord};

use crate::error_frame::{classify, controller_passive};
use crate::tick::{BusTick, DriveState, Reply};
use crate::types::{EchoSeen, LimbState, Observed, StopOutcome};

impl BusTick {
    /// One frame read at `read_ns`, before the send (draining) or after it.
    pub fn on_frame(&mut self, read_ns: u64, frame: &FrameRecord) {
        if frame.error {
            self.counters.error_frames += 1;
            let error = classify(frame.id, &frame.data);
            if error.latches() {
                self.latch(error);
            }
            // The controller's state, read on its own: a frame can carry it beside a more severe flag (passive back
            // to warning together with an overflow), and warning after passive is a recovery.
            if let Some(passive) = controller_passive(frame.id, frame.data) {
                self.error_passive = passive;
            }
            return;
        }
        if !frame.extended || frame.remote {
            self.counters.undecodable += 1;
            return;
        }
        match decode(frame.id, frame.payload()) {
            // The codec names frames only another sender could have put on the bus.
            Err(
                DecodeError::OtherHost { .. }
                | DecodeError::ForeignType { .. }
                | DecodeError::ForeignWrite { .. },
            ) => self.counters.foreign_host += 1,
            Err(
                DecodeError::IdTooWide(_)
                | DecodeError::BadLength { .. }
                | DecodeError::UnknownType { .. }
                | DecodeError::BadDeviceId { .. }
                | DecodeError::ReservedMode { .. }
                | DecodeError::UnknownParam { .. }
                | DecodeError::BadParamValue { .. }
                | DecodeError::UnexpectedData { .. },
            ) => self.counters.undecodable += 1,
            Ok(Inbound::Echo(echo)) => {
                if frame.direction == Direction::TxEcho {
                    self.counters.echoes += 1;
                    if let Some(d) = self.slot_of(echo.target) {
                        d.last_echo = Some(EchoSeen {
                            kind: echo.kind,
                            read_ns,
                        });
                    }
                } else {
                    self.counters.foreign_host += 1;
                }
            }
            Ok(Inbound::Status(status)) => self.on_status(read_ns, status, true),
            Ok(Inbound::Report(status)) => self.on_status(read_ns, status, false),
            Ok(Inbound::Fault { device, faults, .. }) => match self.slot_of(device) {
                // Warnings alone aren't a fault (the codec: non-zero fault bytes mean faulted).
                Some(d) => d.fault_seen |= faults != [0; 4],
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Version { header, .. }) => {
                let unordered = self.unordered;
                let limbs = self.limbs;
                match self.slot_of(header.device) {
                    // A version reply carries the status header too: its faults and its mode count like a status's.
                    Some(d) => {
                        d.fault_seen |= !header.faults.is_empty();
                        let active = limbs.get(d.limb).copied().flatten().map(|l| l.state)
                            == Some(LimbState::Active);
                        d.note_mode(header.mode, active, unordered);
                    }
                    None => self.counters.unexpected += 1,
                }
            }
            Ok(Inbound::Identity { device, .. } | Inbound::Param { device, .. }) => {
                if self.slot_of(device).is_none() {
                    self.counters.unexpected += 1;
                }
            }
        }
    }

    fn on_status(&mut self, read_ns: u64, status: Status, answer: bool) {
        let device = status.header.device;
        let tick = self.tick;
        let unordered = self.unordered;
        let limbs = self.limbs;
        let Some(d) = self
            .drives
            .iter_mut()
            .flatten()
            .find(|d| d.device == device)
        else {
            self.counters.unexpected += 1;
            return;
        };
        d.observed = Some(Observed { status, read_ns });
        // A later status in another mode takes the fresh one back: it can't be accepted again by a Run that follows.
        if d.fresh_status
            .is_some_and(|f| f.status.header.mode != status.header.mode)
        {
            d.fresh_status = None;
        }
        if !status.header.faults.is_empty() {
            d.fault_seen = true;
        }
        let limb = limbs.get(d.limb).copied().flatten().map(|l| l.state);
        let active = limb == Some(LimbState::Active);
        let stopping = matches!(limb, Some(LimbState::Stopping { .. }));
        d.note_mode(status.header.mode, active, unordered);
        if !answer {
            return;
        }
        let Some(o) = d.outstanding.as_mut().filter(|_| !unordered) else {
            self.counters.unsolicited += 1;
            return;
        };
        if o.reply == Reply::Waiting {
            d.fresh_ns = Some(read_ns);
            d.fresh_status = Some(Observed { status, read_ns });
            if read_ns <= o.deadline_ns {
                o.reply = Reply::OnTime;
                d.answered = o.tick == tick;
                d.misses = 0;
            } else {
                o.reply = Reply::Late;
                self.counters.late += 1;
            }
        } else if o.tick == tick {
            self.counters.duplicate += 1;
        } else {
            self.counters.unsolicited += 1;
        }
        // Any Reset after the stop's Disable confirms it, even behind an earlier status still in flight. Once the limb
        // is stopped nothing more is sent, so a confirmation then would record a reporting off that never comes.
        if stopping
            && o.stop_disable
            && status.header.mode == Mode::Reset
            && d.stop != StopOutcome::Confirmed
        {
            d.stop = StopOutcome::Confirmed;
            d.confirmed_ns = Some(read_ns);
        }
    }

    fn slot_of(&mut self, device: DeviceId) -> Option<&mut DriveState> {
        self.drives
            .iter_mut()
            .flatten()
            .find(|d| d.device == device)
    }
}
