//! What an enable asks and how it is answered.

use safety::{EnableFailure, Refusal};
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
    /// A named joint's preflight refused it, or its skeleton entry did before anything was sent, or its limb stopped on
    /// some bus before any Enable was planned. Nothing was enabled.
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
