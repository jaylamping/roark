//! A drive's outbox: the frames it has yet to put on the bus, and the transport faults that shape them. Each frame is
//! settled as the drive's clock passes its due time, with the transport faults in effect then: a silent drive sends
//! nothing, a late one holds each frame once more by its lateness, and lost or doubled frames go by count. A settled
//! frame has gone: no fault injected later reaches it, and the host reads it whenever it next polls.

use std::time::{Duration, Instant};

use robstride::drive::DriveFrame;

/// Frames waiting for their due time or for the host to read them: [`crate::MAX_LATE`] of command replies at the 250 Hz
/// tick with reports on every 10 ms, and room to spare. A full outbox drops the frame and counts it.
pub(crate) const OUTBOX: usize = 64;

/// The transport faults in effect: [`crate::Fault::Silent`], `Late`, `Drop` and `Duplicate`.
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Transport {
    pub(crate) silent: bool,
    pub(crate) late: Duration,
    pub(crate) drop: u32,
    pub(crate) duplicate: u32,
}

/// A frame in the outbox.
#[derive(Clone, Copy, Debug)]
struct Queued {
    due: Instant,
    frame: DriveFrame,
    state: State,
}

#[derive(Clone, Copy, Debug)]
enum State {
    /// Not yet due; `delayed` once a `Late` has held it, so it is held only once.
    Waiting { delayed: bool },
    /// Gone out at `due`, waiting only for the host to read it.
    Sent,
}

/// The frames a drive has queued or sent and the host hasn't read, at most [`OUTBOX`].
#[derive(Clone, Copy, Debug)]
pub(crate) struct Outbox {
    slots: [Option<Queued>; OUTBOX],
    /// Transport faults in effect now.
    pub(crate) faults: Transport,
    dropped: u64,
}

impl Outbox {
    pub(crate) const EMPTY: Self = Self {
        slots: [None; OUTBOX],
        faults: Transport {
            silent: false,
            late: Duration::ZERO,
            drop: 0,
            duplicate: 0,
        },
        dropped: 0,
    };

    /// Frames dropped because the outbox was full or the frame couldn't be built, and reports skipped as a full outbox
    /// would drop them.
    pub(crate) const fn dropped(&self) -> u64 {
        self.dropped
    }

    /// Count `n` frames dropped.
    pub(crate) const fn count_dropped(&mut self, n: u64) {
        self.dropped = self.dropped.saturating_add(n);
    }

    pub(crate) fn is_full(&self) -> bool {
        self.slots.iter().all(Option::is_some)
    }

    /// Queue `frame` to go out at `due`; a frame that can't be built (`None`) or has no room is dropped and counted.
    pub(crate) fn send(&mut self, due: Instant, frame: Option<DriveFrame>) {
        if let Some(frame) = frame {
            self.put(Queued {
                due,
                frame,
                state: State::Waiting { delayed: false },
            });
        } else {
            self.count_dropped(1);
        }
    }

    fn put(&mut self, queued: Queued) {
        match self.slots.iter_mut().find(|s| s.is_none()) {
            Some(slot) => *slot = Some(queued),
            None => self.count_dropped(1),
        }
    }

    /// Settle every frame due before `until` (or at it, if `inclusive`), earliest first, with the transport faults in
    /// effect now: the caller settles up to each fault's time before it applies the fault.
    pub(crate) fn settle(&mut self, until: Instant, inclusive: bool) {
        // Each pass settles a frame, or holds it once by `Late` (it settles on a later pass): at most two a slot.
        for _ in 0..2 * OUTBOX {
            let Some(slot) = self
                .slots
                .iter_mut()
                .filter(|s| {
                    s.is_some_and(|q| {
                        matches!(q.state, State::Waiting { .. })
                            && (q.due < until || (inclusive && q.due == until))
                    })
                })
                .min_by_key(|s| s.map(|q| q.due))
            else {
                return;
            };
            let Some(queued) = slot.take() else {
                return;
            };
            let faults = &mut self.faults;
            if faults.silent {
                continue;
            }
            if matches!(queued.state, State::Waiting { delayed: false }) && !faults.late.is_zero() {
                *slot = Some(Queued {
                    due: queued.due + faults.late,
                    state: State::Waiting { delayed: true },
                    ..queued
                });
                continue;
            }
            if faults.drop > 0 {
                faults.drop -= 1;
                continue;
            }
            let sent = Queued {
                state: State::Sent,
                ..queued
            };
            *slot = Some(sent);
            // The second copy goes out with the first, and isn't doubled again.
            if faults.duplicate > 0 {
                faults.duplicate -= 1;
                self.put(sent);
            }
        }
    }

    /// The power goes at `at`: what is due by then goes out first, the rest is lost, and the transport faults clear.
    pub(crate) fn power_off(&mut self, at: Instant) {
        self.settle(at, true);
        for slot in &mut self.slots {
            if slot.is_some_and(|q| matches!(q.state, State::Waiting { .. })) {
                *slot = None;
            }
        }
        self.faults = Transport::default();
    }

    /// The earliest frame gone out by `now`, taken out of the outbox.
    pub(crate) fn pop(&mut self, now: Instant) -> Option<DriveFrame> {
        self.slots
            .iter_mut()
            .filter(|s| s.is_some_and(|q| matches!(q.state, State::Sent) && q.due <= now))
            .min_by_key(|s| s.map(|q| q.due))?
            .take()
            .map(|q| q.frame)
    }

    /// The earliest due time of any frame in the outbox.
    pub(crate) fn next_due(&self) -> Option<Instant> {
        self.slots.iter().flatten().map(|q| q.due).min()
    }
}
