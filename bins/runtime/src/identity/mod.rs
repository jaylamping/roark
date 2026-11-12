//! (rt) The operator's scan of a bus and set-ID of one drive, as the control thread runs them over that bus's slow
//! requests (PLAN item 3, Scan and identity; item 2, transmit allowlist; item 3a `scan(bus)`, `set_id(bus, old, new)`).
//! Pure over the rings: unit tested over hand-built results, and run end to end by the sim suite on `vcan`.
//!
//! One runs at a time, and never beside an enable: control refuses an enable while one runs, and one while an enable
//! runs. A scan probes every ID from 1 to 127 (type 0), one a tick. A set-ID sends its type 7 only once probes have
//! just shown exactly one drive answering at the old ID and none at the new; then it probes the new ID and the old, and
//! is done only when the same UID answers at the new ID alone. It never sends the type 7 twice. The bus refuses every
//! probe and set-ID unless every limb on it is idle (`can::SlowRefusal::BusNotIdle`), so neither can feed a running or
//! stopped drive.

mod reply;
#[cfg(test)]
mod tests;

use can::{MAX_DRIVES, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult};
use robstride::{DeviceId, Uid};

use crate::enable::SlowEnds;

pub use reply::{
    Answer, IdentityAsk, IdentityDone, IdentityRefused, IdentityReply, IdentityRequest, ScanTable,
};

/// The slot a probe or set-ID is asked under. The bus doesn't read it for them and hands it back in the result; no
/// drive has it, so no preflight ever takes the result for its own, and the job takes no preflight's.
const SLOT: usize = MAX_DRIVES;

/// How many times one probe is asked when its window can't be trusted (`Unsure`), control was silent, or it wasn't
/// sent, before that ID's answer is `Unsure`.
const TRIES: u8 = 3;

/// Where a set-ID is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Stage {
    /// Probing the old ID: exactly one drive must answer.
    Old,
    /// Probing the new ID: nothing may answer. `uid` answered at the old.
    New { uid: Uid },
    /// The type 7, asked once.
    Send { uid: Uid },
    /// Probing the new ID after the type 7.
    AfterNew { uid: Uid },
    /// Probing the old ID after the type 7; `at_new` is what answered at the new.
    AfterOld { uid: Uid, at_new: Answer },
}

impl Stage {
    /// Whether the type 7 may have gone.
    const fn sent(self) -> bool {
        matches!(self, Self::AfterNew { .. } | Self::AfterOld { .. })
    }
}

/// What the job running does.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Work {
    /// Probing `next`, then every ID after it, into [`Identity`]'s table.
    Scan { next: DeviceId },
    SetId {
        old: DeviceId,
        new: DeviceId,
        stage: Stage,
    },
}

/// How a job ended, its scan's table left in [`Identity`].
#[derive(Clone, Copy, Debug)]
enum End {
    Scanned,
    Moved { uid: Uid },
    Refused(IdentityRefused),
}

/// The scan or set-ID running.
#[derive(Clone, Copy, Debug)]
struct Job {
    tag: u64,
    bus: usize,
    work: Work,
    /// The request in flight, by its slow tag.
    asked: Option<u32>,
    /// Times the current probe has been asked.
    tries: u8,
}

/// The control thread's scans and set-IDs.
#[derive(Debug, Default)]
pub(crate) struct Identity {
    job: Option<Job>,
    /// The scan running's table, made once and cleared as each scan starts.
    table: ScanTable,
    /// The next slow tag.
    next_tag: u32,
}

impl Identity {
    /// Whether a scan or set-ID is running.
    pub(crate) const fn running(&self) -> bool {
        self.job.is_some()
    }

    /// The bus whose slow results the job running takes.
    pub(crate) fn bus(&self) -> Option<usize> {
        self.job.map(|j| j.bus)
    }

    /// Take `request`: refused at once if it names no bus, a bus that has ended, a set-ID from an ID to itself, or comes
    /// while an enable or another job runs; otherwise it starts, and is asked on the next [`Self::tick`].
    pub(crate) fn take(
        &mut self,
        request: IdentityRequest,
        ended: &[bool],
        enabling: bool,
    ) -> Result<(), IdentityRefused> {
        match ended.get(request.bus) {
            None => return Err(IdentityRefused::NoBus),
            Some(true) => return Err(IdentityRefused::BusEnded),
            Some(false) => {}
        }
        if enabling || self.job.is_some() {
            return Err(IdentityRefused::Busy);
        }
        let work = match request.ask {
            IdentityAsk::Scan => {
                self.table = ScanTable::default();
                Work::Scan {
                    next: DeviceId::FIRST,
                }
            }
            IdentityAsk::SetId { old, new } if old == new => {
                return Err(IdentityRefused::SameId);
            }
            IdentityAsk::SetId { old, new } => Work::SetId {
                old,
                new,
                stage: Stage::Old,
            },
        };
        self.job = Some(Job {
            tag: request.tag,
            bus: request.bus,
            work,
            asked: None,
            tries: 0,
        });
        Ok(())
    }

    /// One tick on: the results on the job's bus taken (any other there counted in `stray`), the next request asked,
    /// and the job's reply once it ends.
    pub(crate) fn tick(
        &mut self,
        slow: &mut [SlowEnds],
        ended: &[bool],
        stray: &mut u64,
    ) -> Option<IdentityReply> {
        let job = self.job.as_mut()?;
        let Some(ends) = slow.get_mut(job.bus) else {
            return self.abandon(IdentityRefused::NoBus);
        };
        for _ in 0..ends.results.buffer().capacity() {
            let Ok(result) = ends.results.pop() else {
                break;
            };
            if job.asked.is_some_and(|tag| is_answer(result, tag)) {
                job.asked = None;
                if let Some(end) = job.answered(result.outcome, &mut self.table) {
                    let (tag, bus) = (job.tag, job.bus);
                    self.job = None;
                    return Some(IdentityReply {
                        tag,
                        bus,
                        outcome: match end {
                            End::Scanned => Ok(IdentityDone::Scanned(self.table)),
                            End::Moved { uid } => Ok(IdentityDone::Moved { uid }),
                            End::Refused(why) => Err(why),
                        },
                    });
                }
            } else {
                *stray += 1;
            }
        }
        if ended.get(job.bus).is_none_or(|e| *e) {
            return self.abandon(IdentityRefused::BusEnded);
        }
        if job.asked.is_none() {
            let tag = self.next_tag;
            let request = SlowRequest {
                tag,
                slot: SLOT,
                kind: job.kind(),
            };
            // The ring holds a request per slot and the job asks one at a time, so it has room once the bus takes any
            // preflight's left in it; until then the job asks again next tick.
            if ends.requests.push(request).is_ok() {
                self.next_tag = tag.wrapping_add(1);
                job.asked = Some(tag);
            }
        }
        None
    }

    /// End the job running, if any, because of `why`: its reply. Past the type 7 the reply says it may have gone.
    pub(crate) fn abandon(&mut self, why: IdentityRefused) -> Option<IdentityReply> {
        let job = self.job.take()?;
        Some(IdentityReply {
            tag: job.tag,
            bus: job.bus,
            outcome: Err(job.unconfirmed().unwrap_or(why)),
        })
    }
}

/// Whether `result` answers the job's request `tag`.
const fn is_answer(result: SlowResult, tag: u32) -> bool {
    result.slot == SLOT && result.tag == tag
}

/// What a probe's outcome says answered at its ID; `None` when it should be asked again (its window couldn't be
/// trusted, control was silent, or it wasn't sent); `Err` when the bus refused it for another reason.
fn probe_answer(outcome: SlowOutcome) -> Result<Option<Answer>, SlowRefusal> {
    match outcome {
        SlowOutcome::Found { uid, other: None } => Ok(Some(Answer::One(uid))),
        SlowOutcome::Found {
            uid,
            other: Some(other),
        } => Ok(Some(Answer::Several { uid, other })),
        SlowOutcome::TimedOut => Ok(Some(Answer::Silent)),
        SlowOutcome::Unsure
        | SlowOutcome::NotSent(_)
        | SlowOutcome::Refused(SlowRefusal::ControlSilent) => Ok(None),
        SlowOutcome::Refused(why) => Err(why),
        // A probe is answered by none of these; if one came, what answered can't be told.
        SlowOutcome::Read(_) | SlowOutcome::Identity(_) | SlowOutcome::WriteAnswered => {
            Ok(Some(Answer::Unsure))
        }
    }
}

impl Job {
    /// What to ask next.
    const fn kind(&self) -> SlowKind {
        match self.work {
            Work::Scan { next, .. } => SlowKind::Probe(next),
            Work::SetId { old, new, stage } => match stage {
                Stage::Old | Stage::AfterOld { .. } => SlowKind::Probe(old),
                Stage::New { .. } | Stage::AfterNew { .. } => SlowKind::Probe(new),
                Stage::Send { .. } => SlowKind::SetId { old, new },
            },
        }
    }

    /// A set-ID whose type 7 may have gone (asked and not yet answered, or answered): what is known of both IDs, the
    /// rest `Unsure`.
    const fn unconfirmed(&self) -> Option<IdentityRefused> {
        match self.work {
            Work::SetId { stage, .. }
                if stage.sent()
                    || (matches!(stage, Stage::Send { .. }) && self.asked.is_some()) =>
            {
                Some(IdentityRefused::Unconfirmed {
                    at_old: Answer::Unsure,
                    at_new: match stage {
                        Stage::AfterOld { at_new, .. } => at_new,
                        Stage::Old
                        | Stage::New { .. }
                        | Stage::Send { .. }
                        | Stage::AfterNew { .. } => Answer::Unsure,
                    },
                })
            }
            Work::SetId { .. } | Work::Scan { .. } => None,
        }
    }

    /// Take the outcome of the request in flight: the job's outcome if it ends here.
    fn answered(&mut self, outcome: SlowOutcome, table: &mut ScanTable) -> Option<End> {
        if let Work::SetId {
            stage: Stage::Send { uid },
            old,
            new,
        } = self.work
        {
            // Refused or not sent: no type 7 went, and none is asked again. Anything else: it may have, so probe both.
            return match outcome {
                SlowOutcome::Refused(why) => Some(End::Refused(IdentityRefused::Bus(why))),
                SlowOutcome::NotSent(why) => Some(End::Refused(IdentityRefused::NotSent(why))),
                SlowOutcome::Read(_)
                | SlowOutcome::Identity(_)
                | SlowOutcome::Found { .. }
                | SlowOutcome::Unsure
                | SlowOutcome::WriteAnswered
                | SlowOutcome::TimedOut => {
                    self.work = Work::SetId {
                        old,
                        new,
                        stage: Stage::AfterNew { uid },
                    };
                    None
                }
            };
        }
        let answer = match probe_answer(outcome) {
            Ok(Some(answer)) => answer,
            Ok(None) if self.tries.saturating_add(1) < TRIES => {
                self.tries = self.tries.saturating_add(1);
                return None;
            }
            Ok(None) => Answer::Unsure,
            Err(why) => {
                return Some(End::Refused(
                    self.unconfirmed().unwrap_or(IdentityRefused::Bus(why)),
                ));
            }
        };
        self.tries = 0;
        match &mut self.work {
            Work::Scan { next } => {
                table.set(*next, answer);
                match next.next() {
                    Some(id) => {
                        *next = id;
                        None
                    }
                    None => Some(End::Scanned),
                }
            }
            Work::SetId { stage, .. } => match (*stage, answer) {
                (Stage::Old, Answer::One(uid)) => {
                    *stage = Stage::New { uid };
                    None
                }
                (Stage::Old, other) => Some(End::Refused(IdentityRefused::NotOne(other))),
                (Stage::New { uid }, Answer::Silent) => {
                    *stage = Stage::Send { uid };
                    None
                }
                (Stage::New { .. }, other) => Some(End::Refused(IdentityRefused::Taken(other))),
                (Stage::AfterNew { uid }, at_new) => {
                    *stage = Stage::AfterOld { uid, at_new };
                    None
                }
                (Stage::AfterOld { uid, at_new }, at_old) => {
                    Some(if at_new == Answer::One(uid) && at_old == Answer::Silent {
                        End::Moved { uid }
                    } else {
                        End::Refused(IdentityRefused::Unconfirmed { at_old, at_new })
                    })
                }
                // Handled above: the type 7's own outcome isn't a probe's.
                (Stage::Send { .. }, _) => None,
            },
        }
    }
}
