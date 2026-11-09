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
/// The longest [`Fault::Late`]: twice the drives' 50 ms timeout, past which a reply is as good as lost to the host. The
/// outbox holds that long of replies at the 250 Hz tick with reporting on.
pub const MAX_LATE: Duration = Duration::from_millis(100);
/// The highest temperature a type-2 status can carry, °C (§4.1.2: tenths of a degree in 16 bits).
pub const MAX_TEMPERATURE_C: f64 = 6553.5;
/// Injections a drive keeps until taken; past this the oldest stays and the newest is counted lost.
pub(crate) const INJECTED_LOG: usize = 16;

/// Something a simulated drive does wrong.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Fault {
    /// Answers nothing from now on; it still acts on what it receives (until a reboot).
    Silent,
    /// Every frame it sends from now on goes out this much later, up to [`MAX_LATE`]; frames already waiting to go are
    /// delayed too.
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
    /// The register reads this value from now on (VBUS out of its window, the damper off). The value must be of the
    /// register's type.
    Param(Param, ParamValue),
    /// Every status and report from now on gives this temperature, 0 to [`MAX_TEMPERATURE_C`].
    Temperature(Celsius),
    /// Power off and on now ([`crate::SimDrive::power_cycle`]): every injected fault is cleared with the rest of
    /// the drive's state; the plan and the record stay.
    Reboot,
    /// Writes to this register are answered but not kept, so a read-back shows the old value.
    IgnoreWrites(Param),
    /// The next this many Disables are lost: no reply, no change, and not counted as received by `canTimeout`.
    IgnoreDisables(u32),
}

/// When a scheduled fault fires.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Trigger {
    /// As the drive takes its nth MIT command after the fault is scheduled, before answering it, so that command's
    /// reply already shows the fault. Counted from 1: 0 is refused.
    OnMit(u32),
    /// At this time: the drive is brought up to it, the fault applied, then the drive goes on, however late it is
    /// stepped. Several due at once fire in time order.
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

/// Why a fault isn't injected or scheduled. Nothing is recorded then.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum FaultRefused {
    /// The plan is full: nothing more can be scheduled until a fault fires.
    #[error("the fault plan holds {FAULT_PLAN} faults already")]
    PlanFull,
    /// `OnMit(0)`: MIT commands are counted from 1.
    #[error("OnMit counts from 1")]
    OnMitZero,
    /// A `Late` past [`MAX_LATE`].
    #[error("Late is at most {MAX_LATE:?}")]
    TooLate,
    /// A `Temperature` a status can't carry.
    #[error("a status carries 0 to {MAX_TEMPERATURE_C} °C")]
    Temperature,
    /// A `Param` whose value isn't of the register's type.
    #[error("{0:?} doesn't take that value")]
    WrongType(Param),
}

impl Fault {
    /// Whether the drive can honour it, but for a `Param`'s type, which the drive checks: what `inject` and `schedule`
    /// check.
    pub(crate) fn check(self) -> Result<(), FaultRefused> {
        match self {
            Self::Late(by) if by > MAX_LATE => Err(FaultRefused::TooLate),
            Self::Temperature(c) if !(0.0..=MAX_TEMPERATURE_C).contains(&c.get()) => {
                Err(FaultRefused::Temperature)
            }
            Self::Silent
            | Self::Late(_)
            | Self::Drop(_)
            | Self::Duplicate(_)
            | Self::FaultBits(_)
            | Self::Mode(_)
            | Self::Param(..)
            | Self::Temperature(_)
            | Self::Reboot
            | Self::IgnoreWrites(_)
            | Self::IgnoreDisables(_) => Ok(()),
        }
    }
}

/// The faults in effect on a drive now.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Active {
    pub(crate) silent: bool,
    pub(crate) late: Duration,
    pub(crate) drop: u32,
    pub(crate) duplicate: u32,
    pub(crate) faults: StatusFaults,
    pub(crate) temperature: Option<Celsius>,
    /// One flag per register, in `Param::ALL` order: a set, so injecting one twice changes nothing.
    pub(crate) ignored_writes: [bool; Param::ALL.len()],
    pub(crate) ignored_disables: u32,
}

impl Default for Active {
    fn default() -> Self {
        Self {
            silent: false,
            late: Duration::ZERO,
            drop: 0,
            duplicate: 0,
            faults: StatusFaults::default(),
            temperature: None,
            ignored_writes: [false; Param::ALL.len()],
            ignored_disables: 0,
        }
    }
}

impl Active {
    pub(crate) fn ignores_write(&self, param: Param) -> bool {
        Param::ALL
            .iter()
            .position(|p| *p == param)
            .and_then(|i| self.ignored_writes.get(i))
            .copied()
            .unwrap_or(false)
    }

    pub(crate) fn ignore_writes(&mut self, param: Param) {
        if let Some(flag) = Param::ALL
            .iter()
            .position(|p| *p == param)
            .and_then(|i| self.ignored_writes.get_mut(i))
        {
            *flag = true;
        }
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

    pub(crate) fn schedule(&mut self, trigger: Trigger, fault: Fault) -> Result<(), FaultRefused> {
        fault.check()?;
        if trigger == Trigger::OnMit(0) {
            return Err(FaultRefused::OnMitZero);
        }
        let free = self
            .faults
            .iter_mut()
            .find(|f| f.is_none())
            .ok_or(FaultRefused::PlanFull)?;
        *free = Some((trigger, self.mits, fault));
        Ok(())
    }

    /// The next fault due by `now`, taken out of the plan: the earliest `At` at or before `now`, then any `OnMit`
    /// whose count is reached (it fires at `now`), each in the order scheduled when tied.
    pub(crate) fn due(&mut self, now: Instant) -> Option<(Instant, Fault)> {
        let mits = self.mits;
        let (i, at) = self
            .faults
            .iter()
            .enumerate()
            .filter_map(|(i, f)| match f {
                Some((Trigger::At(at), _, _)) => (*at <= now).then_some((i, *at)),
                Some((Trigger::OnMit(n), from, _)) => {
                    (mits.saturating_sub(*from) >= *n).then_some((i, now))
                }
                None => None,
            })
            .min_by_key(|(i, at)| (*at, *i))?;
        let (_, _, fault) = self.faults.get_mut(i)?.take()?;
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
