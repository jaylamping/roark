//! A bus told to exit waits for control to see every limb stopped, but not for ever (crates/can/README.md, `exit`).

use crate::timing::Timing;

/// A snapshot as the ring met it.
#[derive(Clone, Copy)]
pub(crate) struct Pushed {
    /// Every limb in it is stopped (`Snapshot::stopped`).
    pub(crate) stopped: bool,
    /// The ring took it.
    pub(crate) taken: bool,
}

/// A bus told to exit waits for control's ring to take a snapshot with every limb stopped, but not for ever.
pub(crate) struct ExitWait {
    /// The all-stopped snapshots made after `exit` that the ring may leave untaken before the thread returns anyway:
    /// one stop window (`Timing::stop_confirm_ns`, 100 ms by default) in ticks of this bus, rounded up; `Timing::check`
    /// makes the window at least a period, so at least one. The shutdown already gives the drives that window to
    /// confirm their Disables; a control that is alive reads its ring well inside one more, and one that isn't must not
    /// hold the join (and the recorder's close). Provisional, like the stop window itself: tuned with the rest of the
    /// timing on the real adapter (PLAN step 8).
    limit: u64,
    /// Those made so far.
    untaken: u64,
    /// Whether the ring has taken an all-stopped snapshot, before `exit` or after, with no snapshot showing a limb
    /// running again (re-armed) since.
    took_stopped: bool,
}

impl ExitWait {
    pub(crate) fn new(timing: Timing) -> Self {
        Self {
            limit: timing.stop_confirm_ns.div_ceil(timing.period_ns),
            untaken: 0,
            took_stopped: false,
        }
    }

    /// A re-arm made a limb idle again: an all-stopped snapshot taken before it no longer says control has seen the
    /// limbs stopped.
    pub(crate) fn rearmed(&mut self) {
        self.took_stopped = false;
    }

    /// After each snapshot's push: whether a bus told to exit is done, because the ring has taken a snapshot with every
    /// limb stopped, control has dropped the ring (`abandoned`), or `limit` such snapshots have gone untaken.
    pub(crate) fn done(&mut self, pushed: Pushed, exiting: bool, abandoned: bool) -> bool {
        let Pushed { stopped, taken } = pushed;
        if !stopped {
            // A re-armed limb running again: only a snapshot taken after it stopped again counts.
            self.took_stopped = false;
            return false;
        }
        self.took_stopped |= taken;
        if !exiting {
            return false;
        }
        if self.took_stopped || abandoned {
            return true;
        }
        self.untaken += 1;
        self.untaken >= self.limit
    }
}

#[cfg(test)]
mod tests {
    use super::{ExitWait, Pushed, Timing};

    /// Guards: safety - a bus told to exit returns only once control has seen every limb stopped, never on a stopped
    /// snapshot it took before a re-arm let a limb run again (PLAN.md item 2 Exit; crates/can/README.md, `exit`).
    #[test]
    fn an_exit_waits_for_a_stopped_snapshot_taken_after_the_last_rearm() {
        let timing = Timing::at_hz(250);
        // Every limb stopped, and control took the snapshot: an exit now would be done.
        let mut wait = ExitWait::new(timing);
        assert!(!wait.done(
            Pushed {
                stopped: true,
                taken: true
            },
            false,
            false
        ));
        // Cleared, the limb runs again; told to exit, the bus stops it but control's ring takes nothing.
        wait.rearmed();
        assert!(!wait.done(
            Pushed {
                stopped: false,
                taken: true
            },
            false,
            false
        ));
        let limit = timing.stop_confirm_ns.div_ceil(timing.period_ns);
        for n in 1..limit {
            assert!(
                !wait.done(
                    Pushed {
                        stopped: true,
                        taken: false
                    },
                    true,
                    false
                ),
                "untaken {n}"
            );
        }
        assert!(
            wait.done(
                Pushed {
                    stopped: true,
                    taken: false
                },
                true,
                false
            ),
            "the wait's limit"
        );
        // A re-arm alone, with no snapshot showing a limb running after it, also forgets the earlier stopped one.
        let mut wait = ExitWait::new(timing);
        assert!(!wait.done(
            Pushed {
                stopped: true,
                taken: true
            },
            false,
            false
        ));
        wait.rearmed();
        assert!(!wait.done(
            Pushed {
                stopped: true,
                taken: false
            },
            true,
            false
        ));
        assert!(
            wait.done(
                Pushed {
                    stopped: true,
                    taken: true
                },
                true,
                false
            ),
            "control took the stopped snapshot"
        );
    }
}
