//! The drive and limb states (PLAN item 6, States). Each transition is a pure function of the state and one event;
//! the runtime logs every transition with its cause. An event a state doesn't take returns `None`: nothing changes, and
//! the runtime refuses what asked for it.

use crate::rule::Cause;

/// Where one drive is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DriveState {
    /// No reply since start, since its limb was cleared of a fault, since a bus loss, or silence while disabled.
    Offline,
    /// Answers; no preflight in hand. Its identity is preflight's to check, not this state's.
    Seen,
    /// Preflight passed and not yet used.
    Checked,
    /// Run seen after this host's Enable.
    Enabled,
    /// A fault was seen: latched until its limb is cleared.
    Faulted,
}

/// What happened to a drive.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DriveEvent {
    /// It answered a request: a slow request or a command.
    Answered,
    /// Its preflight passed.
    PreflightPassed,
    /// Its preflight was refused.
    PreflightRefused,
    /// Run seen after its Enable.
    RunSeen,
    /// Disabled by this host (a stop, or the enable sequence giving up).
    Disabled,
    /// Left Run by itself, or answered in Reset while enabled (a reboot looks the same).
    LeftRun,
    /// Missed replies past the silence rule.
    Silent,
    /// A fault bit or fault report.
    Fault,
    /// Its bus failed.
    BusLost,
    /// The operator cleared its limb.
    Cleared,
}

impl DriveState {
    /// The state after `event`, or `None` if this state doesn't take it.
    #[must_use]
    pub const fn on(self, event: DriveEvent) -> Option<Self> {
        use DriveEvent as E;
        use DriveState::{Checked, Enabled, Faulted, Offline, Seen};
        match event {
            // A fault latches from anywhere, and only a clear lets go of it. A cleared drive hasn't answered since: it
            // is seen again at its next answer.
            E::Fault => Some(Faulted),
            E::Cleared => match self {
                Faulted => Some(Offline),
                Offline | Seen | Checked | Enabled => None,
            },
            E::BusLost => match self {
                Offline | Seen | Checked | Enabled => Some(Offline),
                Faulted => None,
            },
            // An answer shows the drive is there; it proves nothing new to a checked or enabled one.
            E::Answered => match self {
                Offline | Seen => Some(Seen),
                Checked | Enabled => Some(self),
                Faulted => None,
            },
            // Preflight runs again before every enable, so a checked drive takes a new verdict too.
            E::PreflightPassed => match self {
                Seen | Checked => Some(Checked),
                Offline | Enabled | Faulted => None,
            },
            E::PreflightRefused => match self {
                Seen | Checked => Some(Seen),
                Offline | Enabled | Faulted => None,
            },
            // Only a checked drive enables: preflight can't be skipped.
            E::RunSeen => match self {
                Checked => Some(Enabled),
                Offline | Seen | Enabled | Faulted => None,
            },
            // Disabled, or dropped out of Run: the preflight is spent or void either way.
            E::Disabled | E::LeftRun => match self {
                Checked | Enabled => Some(Seen),
                Offline | Seen | Faulted => None,
            },
            // PLAN item 6: silence drops an enabled drive to seen; a silent disabled drive is offline.
            E::Silent => match self {
                Enabled => Some(Seen),
                Seen | Checked => Some(Offline),
                Offline | Faulted => None,
            },
        }
    }
}

/// Where one limb is. PLAN item 6: idle → enabling → enabled → stopping → faulted.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimbState {
    /// Nothing enabled.
    Idle,
    /// Preflight and the enable sequence are running on its named joints.
    Enabling,
    /// Its named joints are in Run under control.
    Enabled,
    /// A stop is in progress.
    Stopping(Cause),
    /// Stopped and latched until the operator clears it.
    Faulted(Cause),
}

/// What happened to a limb.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimbEvent {
    /// An enable of some of its joints began.
    Enable,
    /// Every named joint reached Run.
    Enabled,
    /// The enable was refused, and none of its sequences had planned an Enable
    /// ([`Enabling::enable_planned`](crate::Enabling::enable_planned)): nothing was enabled, so nothing to stop. One
    /// sequence's refusal while another of the same enable has planned its Enable is a [`Self::Stop`], not this.
    Refused,
    /// A stop, and why. The first cause is kept.
    Stop(Cause),
    /// Every bus it is on says its stop is done.
    Settled,
    /// The operator cleared it, and every bus re-armed it.
    Cleared,
}

impl LimbState {
    /// The state after `event`, or `None` if this state doesn't take it.
    #[must_use]
    pub const fn on(self, event: LimbEvent) -> Option<Self> {
        use LimbEvent as E;
        use LimbState::{Enabled, Enabling, Faulted, Idle, Stopping};
        match event {
            E::Enable => match self {
                Idle => Some(Enabling),
                Enabling | Enabled | Stopping(_) | Faulted(_) => None,
            },
            E::Enabled => match self {
                Enabling => Some(Enabled),
                Idle | Enabled | Stopping(_) | Faulted(_) => None,
            },
            E::Refused => match self {
                Enabling => Some(Idle),
                Idle | Enabled | Stopping(_) | Faulted(_) => None,
            },
            // A drive of an idle limb faulting stops it too: the bus layer vetoes idle limbs as well. The first cause
            // is kept.
            E::Stop(cause) => match self {
                Idle | Enabling | Enabled => Some(Stopping(cause)),
                Stopping(_) | Faulted(_) => None,
            },
            E::Settled => match self {
                Stopping(cause) => Some(Faulted(cause)),
                Idle | Enabling | Enabled | Faulted(_) => None,
            },
            E::Cleared => match self {
                Faulted(_) => Some(Idle),
                Idle | Enabling | Enabled | Stopping(_) => None,
            },
        }
    }
}
