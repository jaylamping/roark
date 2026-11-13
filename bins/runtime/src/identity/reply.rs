//! What a scan or set-ID asks and how it is answered.

use can::{SlowRefusal, Unsent};
use robstride::{DeviceId, Uid};

/// IDs a scan covers, as a table indexed by the ID itself: 0 (the broadcast target, never a drive) to 127.
const IDS: usize = 128;
const _: () = assert!(DeviceId::MAX == 127);

/// The operator's scan of a bus or set-ID of one drive on it, answered by one [`IdentityReply`] under `tag`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct IdentityRequest {
    /// The requester's tag, echoed in the reply.
    pub tag: u64,
    /// The bus, as its index in the runtime's plan.
    pub bus: usize,
    /// What it asks.
    pub ask: IdentityAsk,
}

/// What an [`IdentityRequest`] asks.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IdentityAsk {
    /// Probe every ID from 1 to 127 (type 0) and list what answered at each.
    Scan,
    /// Move the one drive at `old` to `new` (type 7), once probes show exactly one drive at `old` and none at `new`.
    SetId {
        /// The drive's ID now.
        old: DeviceId,
        /// The ID to give it.
        new: DeviceId,
    },
}

/// What answered a probe of one ID.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Answer {
    /// Nothing answered by the next tick's start: no drive at that ID.
    #[default]
    Silent,
    /// One UID answered. On a real bus two drives answering together are assumed to collide and so show as `Unsure`;
    /// the bench checks that (`can::SlowOutcome::Found`).
    One(Uid),
    /// Two drives with different UIDs answered: the ID is shared.
    Several {
        /// The first UID.
        uid: Uid,
        /// Another.
        other: Uid,
    },
    /// What answered can't be told: each time the probe was asked its window couldn't be trusted, it wasn't sent, or
    /// its result never came.
    Unsure,
}

/// A bus's scan: what answered at each ID from 1 to 127.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ScanTable {
    answers: [Answer; IDS],
}

impl Default for ScanTable {
    fn default() -> Self {
        Self {
            answers: [Answer::Silent; IDS],
        }
    }
}

impl ScanTable {
    /// What answered at `id`.
    #[must_use]
    pub fn at(&self, id: DeviceId) -> Answer {
        self.answers
            .get(usize::from(id.get()))
            .copied()
            .unwrap_or_default()
    }

    /// Every ID that wasn't silent, in order.
    pub fn heard(&self) -> impl Iterator<Item = (DeviceId, Answer)> + '_ {
        core::iter::successors(Some(DeviceId::FIRST), |id| id.next())
            .map(|id| (id, self.at(id)))
            .filter(|(_, a)| *a != Answer::Silent)
    }

    pub(super) fn set(&mut self, id: DeviceId, answer: Answer) {
        if let Some(a) = self.answers.get_mut(usize::from(id.get())) {
            *a = answer;
        }
    }
}

/// The answer to an [`IdentityRequest`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct IdentityReply {
    /// The request's tag.
    pub tag: u64,
    /// The request's bus.
    pub bus: usize,
    /// What the request asked.
    pub ask: IdentityAsk,
    /// What it found or did, or why not.
    pub outcome: Result<IdentityDone, IdentityRefused>,
}

/// What a scan or set-ID did.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[expect(
    clippy::large_enum_variant,
    reason = "a reply goes through a ring made at start; boxing the table would allocate on the loop"
)]
pub enum IdentityDone {
    /// The scan's table.
    Scanned(ScanTable),
    /// The drive with `uid` answers at the new ID, and nothing at the old.
    Moved {
        /// Its UID, the same before and after.
        uid: Uid,
    },
}

/// Why a scan or set-ID didn't finish. Only [`Self::Unconfirmed`] says a type 7 may have gone; every other means none
/// did (a scan's probes may have).
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum IdentityRefused {
    /// The plan has no such bus.
    #[error("no such bus")]
    NoBus,
    /// An enable, or another scan or set-ID, is running.
    #[error("an enable, scan or set-ID is running")]
    Busy,
    /// A set-ID from an ID to itself.
    #[error("the old and new IDs are the same")]
    SameId,
    /// The bus refused a probe or the type 7, with its reason: `BusNotIdle` while a limb on it isn't idle, `BusFailed`
    /// once it has failed, or any other [`SlowRefusal`] but `ControlSilent`, after which a probe is asked again.
    #[error("the bus refused it: {0}")]
    Bus(SlowRefusal),
    /// The type 7 wasn't sent: it expired queued or the socket didn't take it.
    #[error("the set-ID wasn't sent: {0:?}")]
    NotSent(Unsent),
    /// Not exactly one drive answered at the old ID: what did.
    #[error("not exactly one drive at the old ID: {0:?}")]
    NotOne(Answer),
    /// Something answered at the new ID, or that couldn't be told: what did.
    #[error("the new ID isn't free: {0:?}")]
    Taken(Answer),
    /// The type 7 may have gone, but the probes after it don't show the drive at the new ID alone and nothing at the
    /// old: what answered at each (`Unsure` where the bus ended, the run ended or the probe couldn't be asked). Probe
    /// both IDs, or scan, before anything else; the type 7 is never sent again.
    #[error("the set-ID may have gone but isn't confirmed: old {at_old:?}, new {at_new:?}")]
    Unconfirmed {
        /// What answered at the old ID after.
        at_old: Answer,
        /// What answered at the new ID after.
        at_new: Answer,
    },
    /// The bus thread has ended.
    #[error("the bus thread has ended")]
    BusEnded,
    /// The run is ending.
    #[error("the run is ending")]
    Ending,
}

impl IdentityRefused {
    /// The refusal's word in its event.
    pub(crate) const fn reason(self) -> &'static str {
        match self {
            Self::NoBus => "no_bus",
            Self::Busy => "busy",
            Self::SameId => "same_id",
            Self::Bus(_) => "bus_refused",
            Self::NotSent(_) => "not_sent",
            Self::NotOne(_) => "not_one_at_old_id",
            Self::Taken(_) => "new_id_taken",
            Self::Unconfirmed { .. } => "unconfirmed",
            Self::BusEnded => "bus_ended",
            Self::Ending => "ending",
        }
    }
}
