//! Frames read from the socket, before the send (the drain) or after it (the collect): what each one says about the bus
//! and its drives.

use robstride::{DecodeError, DeviceId, Inbound, Mode, Status, decode};
use telemetry::{Direction, FrameRecord};

use crate::batch::batch_may_carry;
use crate::error_frame::{BusError, classify, controller_passive};
use crate::tick::{BusTick, DriveState, DriveStop, Off, Reply, limb_state};
use crate::types::{EchoSeen, LimbState, MAX_DRIVES, Observed};

impl BusTick {
    /// One frame read at `read_ns`, before the send (draining) or after it.
    pub fn on_frame(&mut self, read_ns: u64, frame: &FrameRecord) {
        if frame.error {
            self.counters.error_frames += 1;
            // Of what an error frame can say, only bus-off stops the bus for good: the adapter may restart the bus by
            // itself (PLAN.md item 3, item 6 Bus-off row). The interface errors come from the socket, through
            // `lost_bus`; the controller's state is read below.
            let error = classify(frame.id, &frame.data);
            match error {
                BusError::BusOff => self.latch(error),
                BusError::ErrorPassive
                | BusError::ErrorWarning
                | BusError::ErrorActive
                | BusError::RxOverflow
                | BusError::TxTimeout
                | BusError::InterfaceDown
                | BusError::InterfaceGone
                | BusError::Socket(_)
                | BusError::Other(_) => {}
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
                    // Only the tick's own kinds of frame: a slow request's echo never hides the enable sequence's.
                    if batch_may_carry(echo.kind)
                        && let Some(d) = drive_of(&mut self.drives, echo.target)
                    {
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
            Ok(Inbound::Fault { device, faults, .. }) => match drive_of(&mut self.drives, device) {
                // Warnings alone aren't a fault (the codec: non-zero fault bytes mean faulted).
                Some(d) => d.fault_seen |= faults != [0; 4],
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Version { header, .. }) => {
                match drive_of(&mut self.drives, header.device) {
                    // A version reply carries the status header too: its faults and its mode count like a status's.
                    Some(d) => {
                        d.fault_seen |= !header.faults.is_empty();
                        let active = limb_state(&self.limbs, d.limb) == Some(LimbState::Active);
                        d.note_mode(header.mode, read_ns, active, self.unordered);
                    }
                    None => self.counters.unexpected += 1,
                }
            }
            Ok(Inbound::Param {
                device,
                param,
                outcome,
            }) => match self.slot_index(device) {
                Some(slot) => {
                    if !self.slow_read_reply(slot, param, outcome) {
                        self.counters.unsolicited += 1;
                    }
                }
                None => self.counters.unexpected += 1,
            },
            Ok(Inbound::Identity { device, uid }) => match self.slot_index(device) {
                Some(slot) => {
                    if !self.slow_identity_reply(slot, uid) {
                        self.counters.unsolicited += 1;
                    }
                }
                None => self.counters.unexpected += 1,
            },
        }
    }

    fn on_status(&mut self, read_ns: u64, status: Status, answer: bool) {
        let tick = self.tick;
        let unordered = self.unordered;
        let Some(slot) = self.slot_index(status.header.device) else {
            self.counters.unexpected += 1;
            return;
        };
        // A status while a write is in flight to the drive answers the write, not a command. Its faults and mode are
        // taken below all the same.
        let answers_write = answer && self.slow_write_reply(slot);
        let Some(d) = self.drives.get_mut(slot).and_then(Option::as_mut) else {
            return;
        };
        d.observed = Some(Observed { status, read_ns });
        if !status.header.faults.is_empty() {
            d.fault_seen = true;
        }
        let limb = limb_state(&self.limbs, d.limb);
        let active = limb == Some(LimbState::Active);
        // A Reset confirms only while the limb is stopping and inside the stop's reply allowance.
        let replies_ns = self.timing.stop_replies_ns();
        let confirms = matches!(
            limb,
            Some(LimbState::Stopping { since_ns }) if read_ns < since_ns.saturating_add(replies_ns)
        );
        d.note_mode(status.header.mode, read_ns, active, unordered);
        if !answer || answers_write {
            return;
        }
        // A write's own status read after it timed out (at this tick's start) lands below, as the reply to this tick's
        // command (crates/can/README.md, Slow requests). It is a real status of the drive from just before this tick's
        // sends, so it can't confirm a stop that isn't so: the write went only to a drive of an idle limb with no stop
        // due, so nothing has been sent to the drive since; a Reset in it shows the drive disabled, and a limb that
        // starts stopping this tick sends it no Enable, so it is still disabled when the stop's Disable arrives. Only a
        // status that also outlived an Enable on a later tick could, which is the read order `BusTick::drained`
        // assumes for every status.
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
        // Any Reset after the stop's Disable confirms it, even behind an earlier status still in flight, while the reply
        // allowance is open. After it, or once the limb is stopped, it confirms nothing: the stop's end is bounded
        // (`Timing::stop_max_ns`), and a confirmation then would record a reporting off that never comes.
        if confirms && o.stop_disable && status.header.mode == Mode::Reset && !d.stop.confirmed() {
            d.stop = DriveStop::Confirmed {
                at_ns: read_ns,
                off: Off::Unsent,
            };
        }
    }

    fn slot_index(&self, device: DeviceId) -> Option<usize> {
        self.drives
            .iter()
            .position(|d| d.as_ref().is_some_and(|d| d.device == device))
    }
}

/// The drive `device` in the table: over the table rather than the tick, so the limb table can be read beside it.
fn drive_of(
    drives: &mut [Option<DriveState>; MAX_DRIVES],
    device: DeviceId,
) -> Option<&mut DriveState> {
    drives.iter_mut().flatten().find(|d| d.device == device)
}
