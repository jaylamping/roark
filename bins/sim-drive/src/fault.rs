//! Injected faults (PLAN item 4 Fault injection): what a test can make one simulated drive do wrong, when, and the record
//! of each injection. A fault applies to the drive from the moment it is injected; a scheduled one fires on its
//! trigger. Every injection is recorded once, so a replay shows what was injected (logging.md section 3).
//!
//! Two faults need no injection, because they are how the drives are set up: two drives built with one ID on a bus
//! (a duplicate ID), and a drive built with another UID than the skeleton's (a wrong UID). Bus-level faults (bus-off,
//! the interface going away) belong to the bus, not a drive.

use std::time::{Duration, Instant};

use robstride::{Celsius, DeviceId, Mode, Param, ParamValue, StatusFaults};

/// Faults one drive holds scheduled at once.
pub const FAULT_PLAN: usize = 8;
/// Injections a drive keeps until taken; past this the oldest stays and the newest is counted lost.
pub(crate) const INJECTED_LOG: usize = 16;
/// Registers one drive can be told to ignore writes to.
pub(crate) const IGNORED_WRITES: usize = 4;

/// Something a simulated drive does wrong.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Fault {
    /// Answers nothing from now on; it still acts on what it receives (until a reboot).
    Silent,
    /// Every frame it sends from now on goes out this much later.
    Late(Duration),
    /// The next this many frames it sends are lost.
    Drop(u32),
    /// The next this many frames it sends go out twice.
    Duplicate(u32),
    /// Every status and report from now on carries these fault bits. The mode stays as it is: no capture says a drive
    /// changes mode on a fault, so the sim doesn't.
    FaultBits(StatusFaults),
    /// The drive is in this mode now, by itself (a drop to Reset while running, say): its plant and `canTimeout`
    /// follow.
    Mode(Mode),
    /// The register reads this value from now on (VBUS out of its window, the damper off).
    Param(Param, ParamValue),
    /// Every status and report from now on gives this temperature.
    Temperature(Celsius),
    /// Power off and on now ([`crate::SimDrive::power_cycle`]): every injected fault is cleared with the rest of
    /// the drive's state; the plan and the record stay.
    Reboot,
    /// Writes to this register are answered but not kept, so a read-back shows the old value.
    IgnoreWrites(Param),
    /// The next this many Disables are lost: no reply, no change.
    IgnoreDisables(u32),
}

/// When a scheduled fault fires.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Trigger {
    /// As the drive takes its nth MIT command after the fault is scheduled, before answering it, so that command's
    /// reply already shows the fault. Counted from 1.
    OnMit(u32),
    /// At this time, or the first moment the drive is stepped after it.
    At(Instant),
}

/// One injection, as recorded.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Injected {
    /// When it took effect.
    pub at: Instant,
    /// The drive it was injected into, by its ID then.
    pub device: DeviceId,
    /// The fault.
    pub fault: Fault,
}

/// The plan is full: nothing more can be scheduled until a fault fires.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
#[error("the fault plan holds {FAULT_PLAN} faults already")]
pub struct PlanFull;

/// The faults in effect on a drive now.
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Active {
    pub(crate) silent: bool,
    pub(crate) late: Duration,
    pub(crate) drop: u32,
    pub(crate) duplicate: u32,
    pub(crate) faults: StatusFaults,
    pub(crate) temperature: Option<Celsius>,
    pub(crate) ignored_writes: [Option<Param>; IGNORED_WRITES],
    pub(crate) ignored_disables: u32,
}

impl Active {
    pub(crate) fn ignores_write(&self, param: Param) -> bool {
        self.ignored_writes.contains(&Some(param))
    }
}

/// The scheduled faults and the record of what fired, kept across a reboot.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Plan {
    /// Each with its MIT count when scheduled, for `OnMit`.
    pub(crate) faults: [Option<(Trigger, u32, Fault)>; FAULT_PLAN],
    pub(crate) mits: u32,
    pub(crate) log: [Option<Injected>; INJECTED_LOG],
    pub(crate) lost: u64,
}

impl Plan {
    pub(crate) const EMPTY: Self = Self {
        faults: [None; FAULT_PLAN],
        mits: 0,
        log: [None; INJECTED_LOG],
        lost: 0,
    };

    pub(crate) fn schedule(&mut self, trigger: Trigger, fault: Fault) -> Result<(), PlanFull> {
        let free = self
            .faults
            .iter_mut()
            .find(|f| f.is_none())
            .ok_or(PlanFull)?;
        *free = Some((trigger, self.mits, fault));
        Ok(())
    }

    /// The next fault due: by `now` for `At`, or on the current MIT count for `OnMit`. Taken out of the plan.
    pub(crate) fn due(&mut self, now: Instant) -> Option<(Instant, Fault)> {
        let mits = self.mits;
        let slot = self.faults.iter_mut().find(|f| match f {
            Some((Trigger::At(at), _, _)) => *at <= now,
            Some((Trigger::OnMit(n), from, _)) => mits.saturating_sub(*from) >= *n,
            None => false,
        })?;
        let (trigger, _, fault) = slot.take()?;
        let at = match trigger {
            Trigger::At(at) => at,
            Trigger::OnMit(_) => now,
        };
        Some((at, fault))
    }

    /// The earliest `At` still scheduled.
    pub(crate) fn next_at(&self) -> Option<Instant> {
        self.faults
            .iter()
            .flatten()
            .filter_map(|(trigger, _, _)| match trigger {
                Trigger::At(at) => Some(*at),
                Trigger::OnMit(_) => None,
            })
            .min()
    }

    pub(crate) fn record(&mut self, injected: Injected) {
        match self.log.iter_mut().find(|e| e.is_none()) {
            Some(slot) => *slot = Some(injected),
            None => self.lost += 1,
        }
    }

    pub(crate) fn take(&mut self) -> Option<Injected> {
        let slot = self
            .log
            .iter_mut()
            .filter(|e| e.is_some())
            .min_by_key(|e| e.map(|i| i.at))?;
        slot.take()
    }
}
