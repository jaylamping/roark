//! What an enable asks and how it is answered.

use safety::{EnableFailure, Refusal, RuleId};
use skeleton::LimbName;

use crate::roster::JointSet;
#[cfg(doc)]
use crate::roster::Roster;

/// The operator's enable of a set of joints, answered by one [`EnableReply`] under `tag`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Enable {
    /// The requester's tag, echoed in the reply.
    pub tag: u64,
    /// The joints, from [`Runtime::joints`](crate::Runtime::joints) or [`Roster::set`].
    pub joints: JointSet,
}

/// The answer to an [`Enable`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EnableReply {
    /// The enable's tag.
    pub tag: u64,
    /// Enabled and held, or why not.
    pub outcome: Result<(), EnableRefused>,
}

/// Why an enable didn't happen. A joint is named by its index in the roster. Where `stopped` is false, no Enable was
/// planned, so nothing was enabled; preflight's reads and writes, and a sequence's active-reporting off, may have gone.
#[derive(Clone, Copy, Debug, PartialEq, thiserror::Error)]
pub enum EnableRefused {
    /// It named no joint.
    #[error("no joint named")]
    Empty,
    /// It named an index the roster doesn't have.
    #[error("no joint {joint} in the roster")]
    UnknownJoint {
        /// The index.
        joint: usize,
    },
    /// Another enable is still running.
    #[error("another enable is running")]
    Busy,
    /// The session's recording has failed: no new enable while the log can't be written (PLAN item 6 `host.logging`).
    #[error("the recording has failed")]
    Logging,
    /// A named joint is already enabled.
    #[error("joint {joint} is already enabled")]
    AlreadyEnabled {
        /// The joint.
        joint: usize,
    },
    /// A named joint's preflight refused it, or its skeleton entry did before anything was sent, or its limb is held on
    /// some bus (`LimbActive`, before any preflight), or its limb stopped on some bus before any Enable was planned.
    /// Nothing was enabled.
    #[error("joint {joint}: {refusal:?}")]
    Preflight {
        /// The joint.
        joint: usize,
        /// Why.
        refusal: Refusal,
    },
    /// A named joint's enable sequence failed, or its limb stopped on some bus once its Enable was planned.
    #[error("joint {joint}: {failure:?} (limbs stopped: {stopped})")]
    Sequence {
        /// The joint.
        joint: usize,
        /// Why.
        failure: EnableFailure,
        /// Whether an Enable of this enable may have gone out, so every limb it named was stopped.
        stopped: bool,
    },
    /// A named joint's bus thread has ended.
    #[error("joint {joint}'s bus thread has ended (limbs stopped: {stopped})")]
    BusEnded {
        /// The joint.
        joint: usize,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// A named joint's drive wasn't in its bus's snapshot within `safety::ANSWER_WITHIN_NS` of the enable: its bus
    /// had published none, or none showing it.
    #[error("joint {joint}'s drive wasn't seen on its bus (limbs stopped: {stopped})")]
    Unseen {
        /// The joint.
        joint: usize,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// Another host sent on a bus a named joint is on while the enable ran: its writes may have changed what preflight
    /// proved (PLAN item 3: only the realtime process transmits).
    #[error("another host sent on bus {bus} during the enable (limbs stopped: {stopped})")]
    ForeignHost {
        /// The bus, as its index in the plan.
        bus: usize,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// A drive of a named limb that this host didn't enable left Reset, or couldn't be seen, once an Enable of the limb
    /// may have gone (`host.mode`'s limb-mate clause, PLAN item 6).
    #[error(
        "a drive of {limb:?} not enabled here left Reset or can't be seen (host.mode; limbs stopped: {stopped})"
    )]
    LimbMate {
        /// The limb.
        limb: LimbName,
        /// Whether every limb it named was stopped.
        stopped: bool,
    },
    /// The run is ending.
    #[error("the run is ending")]
    Ending,
}

impl EnableRefused {
    /// The safety rule it falls under; `None` for a request that was wrong or came at the wrong time, which no rule
    /// refused.
    #[must_use]
    pub const fn rule(&self) -> Option<RuleId> {
        match self {
            Self::Empty
            | Self::UnknownJoint { .. }
            | Self::Busy
            | Self::AlreadyEnabled { .. }
            | Self::Ending => None,
            Self::Logging => Some(RuleId::HostLogging),
            Self::Preflight { refusal, .. } => Some(refusal.rule()),
            Self::Sequence { failure, .. } => Some(failure.rule()),
            Self::BusEnded { .. } => Some(RuleId::HostBus),
            // Preflight's no-status clause (a drive the bus shows nothing of can't be proved), and another host's writes
            // that may have changed what preflight proved.
            Self::Unseen { .. } | Self::ForeignHost { .. } => Some(RuleId::HostPreflight),
            Self::LimbMate { .. } => Some(RuleId::HostMode),
        }
    }

    /// A word for it in the event log.
    #[must_use]
    pub const fn reason(&self) -> &'static str {
        match self {
            Self::Empty => "empty",
            Self::UnknownJoint { .. } => "unknown_joint",
            Self::Busy => "busy",
            Self::Logging => "logging",
            Self::AlreadyEnabled { .. } => "already_enabled",
            Self::Preflight { .. } => "preflight",
            Self::Sequence { .. } => "sequence",
            Self::BusEnded { .. } => "bus_ended",
            Self::Unseen { .. } => "unseen",
            Self::ForeignHost { .. } => "foreign_host",
            Self::LimbMate { .. } => "limb_mate",
            Self::Ending => "ending",
        }
    }

    /// The joint it names, if one.
    #[must_use]
    pub const fn joint(&self) -> Option<usize> {
        match self {
            Self::UnknownJoint { joint }
            | Self::AlreadyEnabled { joint }
            | Self::Preflight { joint, .. }
            | Self::Sequence { joint, .. }
            | Self::BusEnded { joint, .. }
            | Self::Unseen { joint, .. } => Some(*joint),
            Self::Empty
            | Self::Busy
            | Self::Logging
            | Self::ForeignHost { .. }
            | Self::LimbMate { .. }
            | Self::Ending => None,
        }
    }
}
