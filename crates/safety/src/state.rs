//! The drive and limb states (PLAN item 6, States). Each transition is a pure function of the state and one event;
//! the runtime logs every transition with its cause. An event a state doesn't take returns `None`: nothing changes, and
//! the runtime refuses what asked for it.

use crate::rule::Cause;

/// Where one drive is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DriveState {
    /// No reply since start, a bus loss, or silence while disabled.
    Offline,
    /// Answers (and its UID matches, once commissioned); no preflight in hand.
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
    /// It answered a request.
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
    #[expect(
        clippy::match_same_arms,
        reason = "one transition per arm, so each reads against PLAN item 6"
    )]
    pub const fn on(self, event: DriveEvent) -> Option<Self> {
        use DriveEvent as E;
        Some(match (self, event) {
            // A fault latches from anywhere and only a clear lets go of it.
            (_, E::Fault) => Self::Faulted,
            (Self::Faulted, E::Cleared) => Self::Seen,
            (Self::Faulted, _) => return None,
            (_, E::BusLost) => Self::Offline,
            (Self::Offline | Self::Seen, E::Answered) => Self::Seen,
            (Self::Checked, E::Answered) => Self::Checked,
            (Self::Seen, E::PreflightPassed) => Self::Checked,
            (Self::Seen | Self::Checked, E::PreflightRefused) => Self::Seen,
            (Self::Checked, E::RunSeen) => Self::Enabled,
            // Disabled, or dropped out of Run: the preflight is spent or void either way.
            (Self::Checked | Self::Enabled, E::Disabled | E::LeftRun) => Self::Seen,
            // PLAN item 6: silence drops an enabled drive to seen; a silent disabled drive is offline.
            (Self::Enabled, E::Silent) => Self::Seen,
            (Self::Seen | Self::Checked, E::Silent) => Self::Offline,
            (
                Self::Offline,
                E::PreflightPassed
                | E::PreflightRefused
                | E::RunSeen
                | E::Disabled
                | E::LeftRun
                | E::Silent
                | E::Cleared,
            )
            | (Self::Seen, E::RunSeen | E::Disabled | E::LeftRun | E::Cleared)
            | (Self::Checked, E::PreflightPassed | E::Cleared)
            | (
                Self::Enabled,
                E::Answered | E::PreflightPassed | E::PreflightRefused | E::RunSeen | E::Cleared,
            ) => return None,
        })
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
    /// The enable was refused before any Enable was planned: nothing to stop.
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
    #[expect(
        clippy::match_same_arms,
        reason = "one transition per arm, so each reads against PLAN item 6"
    )]
    pub const fn on(self, event: LimbEvent) -> Option<Self> {
        use LimbEvent as E;
        Some(match (self, event) {
            (Self::Idle, E::Enable) => Self::Enabling,
            (Self::Enabling, E::Enabled) => Self::Enabled,
            (Self::Enabling, E::Refused) => Self::Idle,
            // A drive of an idle limb faulting stops it too: the bus layer vetoes idle limbs as well.
            (Self::Idle | Self::Enabling | Self::Enabled, E::Stop(cause)) => Self::Stopping(cause),
            (Self::Stopping(cause), E::Settled) => Self::Faulted(cause),
            (Self::Faulted(_), E::Cleared) => Self::Idle,
            (Self::Idle, E::Enabled | E::Refused | E::Settled | E::Cleared)
            | (Self::Enabling, E::Enable | E::Settled | E::Cleared)
            | (Self::Enabled, E::Enable | E::Enabled | E::Refused | E::Settled | E::Cleared)
            | (Self::Stopping(_), E::Enable | E::Enabled | E::Refused | E::Stop(_) | E::Cleared)
            | (Self::Faulted(_), E::Enable | E::Enabled | E::Refused | E::Stop(_) | E::Settled) => {
                return None;
            }
        })
    }
}
