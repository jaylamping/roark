//! The enable sequence for one drive (PLAN item 2, "Enable one drive"): preflight passed → active reporting off → its
//! echo plus one tick → Enable → a fresh Run status within 50 ms → `run_mode` = MIT, its echo and a fresh Run status
//! answering it. Every frame goes in control's batch; no MIT frame is sent before Run is seen, and only
//! [`Next::Enabled`] lets control command the drive. Each wait takes only a reply read inside its 50 ms window, however
//! late the sequence is stepped. An echo proves only that the frame reached the controller, so the `run_mode` write
//! counts once a fresh status read after it still shows Run: the drive took a frame and stayed enabled.
//!
//! The runtime cancels the sequence on any event that voids its preflight (see [`PreflightPassed`]); the sequence
//! itself checks, at every step, that it is stepped with its own drive on its own bus ([`Seen`]), that the drive
//! reports no fault, that until the Enable is planned it shows no mode but Reset since its preflight began, and that its
//! limb hasn't stopped or been cleared since preflight: each of those ends it.
//!
//! It sends every frame in control's batch, never as a slow request. A slow request to the drive meanwhile can't
//! disturb it: the bus keeps as `last_echo` only the kinds of frame a batch carries, so a slow frame's echo never hides
//! the sequence's own, and once the Enable has made the limb active the bus refuses slow writes to it
//! (`can::SlowRefusal::LimbNotIdle`), whose status answer could pass for the Enable's or the `run_mode` write's.
//!
//! Set Zero has no command in this stack yet. When it gets one, this sequence gains the "no Set Zero to this drive in
//! the last 800 ms" step before Enable.

use can::{DriveView, StopReason};
use robstride::{
    Drive, EchoKind, Frame, Mode, Param, ParamValue, Reporting, RunMode, StatusFaults, Write,
    encode,
};

use crate::preflight::{PreflightPassed, left_reset};
use crate::refusal::stopped_by;
use crate::rule::RuleId;
use crate::seen::{DriveAddress, Seen};

/// How long each step has for its reply after its frame is planned: the echo of each frame (reporting off, Enable, the
/// `run_mode` write), with the tick after the reporting off's echo inside the reporting off's window; Run after the
/// Enable (PLAN item 2, "refuse after 50 ms"; 1.4 to 10.3 ms measured); and the fresh Run answering the `run_mode`
/// write. The bus layer's enable-to-Run window ([`can::ENABLE_TO_RUN_NS`]) is as long but starts when the socket took
/// the Enable, which is no earlier than this sequence planned it: the sequence never waits for Run longer than the bus
/// does. It can give up as much as the planning-to-send delay before the bus would count the drive silent, which fails
/// closed: the limb is stopped either way.
pub const RUN_WITHIN_NS: u64 = can::ENABLE_TO_RUN_NS;

/// Why a drive's enable sequence gave up. Once an Enable may have gone out, the limb is stopped ([`Next::Stop`]), not
/// just refused ([`Next::Refused`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EnableFailure {
    /// The reporting-off frame wasn't read back from the socket in time.
    NoEcho,
    /// The reporting-off frame was read back, but no later tick came to plan the Enable within [`RUN_WITHIN_NS`] of the
    /// reporting off: the bus or control stalled, and the proof is that much older.
    Stalled,
    /// Neither the Enable's echo nor a fresh Run status was read within [`RUN_WITHIN_NS`] of the Enable being planned:
    /// it wasn't seen to go out (a held tick or a full queue drops it), but it may have, so the limb is stopped.
    NoEnableEcho,
    /// The `run_mode` = MIT write wasn't read back from the socket in time: the drive may not be in MIT mode.
    NoModeEcho,
    /// No fresh Run status within [`RUN_WITHIN_NS`] of the Enable, though its echo was read in that window; the last
    /// mode seen since, if any.
    NoRun {
        /// The last mode the drive reported.
        last: Option<Mode>,
    },
    /// The drive left Run after the Enable's answer: its latest status shows another mode, or the `run_mode` = MIT
    /// write was echoed but no fresh Run status answered it within [`RUN_WITHIN_NS`]; the last mode seen since, if any.
    LeftRun {
        /// The last mode the drive reported.
        last: Option<Mode>,
    },
    /// The sequence was handed another drive's view, by ID or by bus, or its own from another slot than its frames go
    /// to: a runtime bug.
    WrongView {
        /// The view's drive.
        view: DriveAddress,
        /// The view's slot in its snapshot.
        view_slot: usize,
        /// The drive the sequence is for.
        drive: DriveAddress,
        /// The slot its frames go to.
        slot: usize,
    },
    /// The drive's limb is stopping or stopped, or was cleared, since its preflight: the proof no longer holds, and the
    /// bus sends the limb none of the sequence's frames.
    LimbStopped {
        /// Why the limb stopped, if the snapshot still says.
        stop: Option<StopReason>,
        /// Whether the Enable had been planned: the limb was to be running, not idle.
        enable_planned: bool,
    },
    /// Before its Enable was planned, the drive showed a mode other than Reset (a status or a version reply read since
    /// its preflight began): something else put it there, and the Enable's answer would prove nothing.
    NotReset {
        /// The mode it showed.
        mode: Mode,
    },
    /// A status since the sequence began carried fault bits, or a fault was seen since the limb's last clear (then the
    /// bits are those of the latest status, possibly none).
    Faults {
        /// The bits.
        bits: StatusFaults,
    },
}

impl EnableFailure {
    /// The rule it falls under.
    #[must_use]
    pub const fn rule(self) -> RuleId {
        match self {
            Self::NoEcho | Self::Stalled | Self::NoEnableEcho | Self::NoModeEcho => RuleId::HostBus,
            Self::WrongView { .. } | Self::LimbStopped { .. } | Self::NotReset { .. } => {
                RuleId::HostPreflight
            }
            Self::NoRun { .. } | Self::LeftRun { .. } => RuleId::HostMode,
            Self::Faults { .. } => RuleId::HostFault,
        }
    }

    /// The operator's line: the rule, the joint, what was seen and what was expected.
    #[must_use]
    pub fn message(self, joint: &str) -> String {
        let what = match self {
            Self::NoEcho => {
                "reporting off wasn't read back within 50 ms, expected its echo".to_owned()
            }
            Self::Stalled => {
                "had its reporting off read back, but no tick came within 50 ms of it to plan the Enable, expected the \
                 next tick"
                    .to_owned()
            }
            Self::NoEnableEcho => {
                "had its Enable not read back within 50 ms, so it may not have gone out, expected its echo"
                    .to_owned()
            }
            Self::NoModeEcho => {
                "the run_mode = MIT write wasn't read back within 50 ms, expected its echo"
                    .to_owned()
            }
            Self::NoRun {
                last: Some(Mode::Run),
            } => "reported Run, but no status read in the 50 ms after its Enable answered it in Run".to_owned(),
            Self::NoRun { last: Some(mode) } => {
                format!("reported {mode:?} 50 ms after its Enable, expected Run")
            }
            Self::NoRun { last: None } => {
                "sent no status within 50 ms of its Enable, expected Run".to_owned()
            }
            Self::LeftRun {
                last: Some(Mode::Run),
            } => "reported Run, but no status read in the 50 ms after the run_mode = MIT write answered it in Run"
                .to_owned(),
            Self::LeftRun { last: Some(mode) } => format!(
                "reported {mode:?} after the Enable's Run, expected Run through the run_mode = MIT write within 50 ms"
            ),
            Self::LeftRun { last: None } => {
                "sent no status within 50 ms of the run_mode = MIT write, expected Run".to_owned()
            }
            Self::WrongView {
                view,
                view_slot,
                drive,
                slot,
            } => format!("was stepped with {view}'s view in slot {view_slot}, expected {drive}'s in slot {slot}"),
            Self::LimbStopped {
                stop,
                enable_planned,
            } => format!(
                "found its limb stopped or cleared since its preflight{}, expected it {}",
                stopped_by(stop),
                if enable_planned {
                    "running"
                } else {
                    "idle throughout"
                }
            ),
            Self::NotReset { mode } => {
                format!("reported {mode:?} since its preflight began, before its Enable, expected Reset")
            }
            Self::Faults { bits } if bits.is_empty() => {
                "had a fault since the last clear, expected none".to_owned()
            }
            Self::Faults { bits } => {
                format!("reports faults {bits:?} while enabling, expected none")
            }
        };
        format!("enable failed ({}): {joint} {what}", self.rule())
    }

    /// What the operator does about it (safety.md section 5).
    #[must_use]
    pub const fn remedy(self) -> &'static str {
        match self {
            Self::NoEcho => {
                "Frames aren't reaching the adapter: check the bus and the runtime's log, then enable again"
            }
            Self::Stalled => {
                "The bus thread or the runtime stalled: check the runtime's log and the Pi's load, then run preflight and enable again"
            }
            Self::NoEnableEcho | Self::NoModeEcho => {
                "Frames aren't reaching the adapter: check the bus and the runtime's log, clear the limb, then run preflight and enable again"
            }
            Self::WrongView { .. } => "A runtime bug: stop and report it with the log",
            Self::LimbStopped { .. } => {
                "Find why the limb stopped in the log, clear the limb, then run preflight and enable again"
            }
            Self::NoRun { .. } | Self::LeftRun { .. } => {
                "Check the drive's power and fault state, clear the limb, then run preflight and enable again"
            }
            Self::NotReset { .. } => {
                "Find what put it in that mode; power-cycle the drive, clear the limb if it is stopped, then run preflight and enable again"
            }
            Self::Faults { .. } => {
                "Find the fault's cause, power-cycle the drive, clear the limb, then run preflight again"
            }
        }
    }
}

/// What the sequence wants this tick.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Next {
    /// Put this frame in the drive's slot in this tick's batch.
    Send(Frame),
    /// Nothing this tick.
    Wait,
    /// The drive is in Run and MIT mode: control may command it.
    Enabled,
    /// It gave up before its Enable was planned: no Enable went to this drive. That speaks for this drive only: if any
    /// other sequence of the same enable has planned its Enable ([`Enabling::enable_planned`]), control stops the limb;
    /// only if none has is the enable refused, with nothing to stop.
    Refused(EnableFailure),
    /// It gave up once the Enable was planned: stop the drive's limb, since the Enable may have gone out.
    Stop(EnableFailure),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Stage {
    ReportingOff,
    AwaitEcho {
        since_ns: u64,
    },
    Settle {
        echo_tick: u64,
        /// When the reporting off was planned: the Enable is planned inside its window or not at all.
        since_ns: u64,
    },
    AwaitRun {
        since_ns: u64,
    },
    AwaitModeEcho {
        since_ns: u64,
        /// When the Run status that answered the Enable was read: the write's answer must come after it.
        run_read_ns: u64,
    },
    Enabled,
    Failed {
        failure: EnableFailure,
        enable_planned: bool,
    },
}

/// One drive's enable sequence, stepped by the control thread once per tick as it builds that tick's batch.
#[derive(Debug, PartialEq, Eq)]
pub struct Enabling {
    drive: Drive,
    address: DriveAddress,
    /// The drive's slot on its bus, where its frames go in the batch.
    slot: usize,
    /// The limb's `generation` while preflight ran: a clear since voids the proof.
    generation: u32,
    /// When preflight began: a mode out of Reset read since, before the Enable, voids the proof. Preflight checked every
    /// status and version reply from then to its pass, so this misses nothing read between the snapshot the pass judged
    /// and the clock control read for it.
    preflight_began_ns: u64,
    stage: Stage,
    started_ns: u64,
}

impl Enabling {
    /// Begin with the drive's preflight proof, at `now_ns`.
    #[must_use]
    #[expect(
        clippy::needless_pass_by_value,
        reason = "the proof is used up: one preflight, one enable"
    )]
    pub const fn new(passed: PreflightPassed, now_ns: u64) -> Self {
        Self {
            drive: passed.drive(),
            address: passed.address(),
            slot: passed.slot(),
            generation: passed.generation(),
            preflight_began_ns: passed.started_ns(),
            stage: Stage::ReportingOff,
            started_ns: now_ns,
        }
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    /// Whether this drive's Enable has been planned, so it may have gone out: a failure from here on stops the limb
    /// ([`Next::Stop`]). Control asks it of every sequence of an enable when one gives up: a [`Next::Refused`] speaks
    /// for its own drive only, and the limb must be stopped, not returned to idle, if any of them has planned its
    /// Enable.
    #[must_use]
    pub const fn enable_planned(&self) -> bool {
        match self.stage {
            Stage::ReportingOff | Stage::AwaitEcho { .. } | Stage::Settle { .. } => false,
            Stage::AwaitRun { .. } | Stage::AwaitModeEcho { .. } | Stage::Enabled => true,
            Stage::Failed { enable_planned, .. } => enable_planned,
        }
    }

    /// The step for tick `tick`'s batch, planned at `now_ns` (the runtime's monotonic epoch, as the view's times) from
    /// what the drive's bus last showed of it. Another drive's view (by ID or by bus, or from another slot), a fault,
    /// or a limb stopping, stopped or cleared since preflight ends the sequence at any step but a failure; a mode out of
    /// Reset since preflight began ends it at any step before the Enable is planned, so no Enable goes to a drive
    /// something else enabled.
    pub fn step(&mut self, seen: Seen<'_>, tick: u64, now_ns: u64) -> Next {
        let view = seen.view;
        if let Some(failure) = self.voided(seen) {
            self.stage = self.failed(failure).0;
        }
        let (stage, next) = match self.stage {
            Stage::ReportingOff => (
                Stage::AwaitEcho { since_ns: now_ns },
                Next::Send(encode::active_reporting(self.drive.id(), Reporting::Off)),
            ),
            Stage::AwaitEcho { since_ns } => {
                if echoed(view, EchoKind::Reporting(Reporting::Off), since_ns) {
                    (
                        Stage::Settle {
                            echo_tick: tick,
                            since_ns,
                        },
                        Next::Wait,
                    )
                } else if late(since_ns, now_ns) {
                    self.failed(EnableFailure::NoEcho)
                } else {
                    (self.stage, Next::Wait)
                }
            }
            // One tick after the echo, inside the reporting off's window: a stall past it would plan the Enable on a
            // proof that much older.
            Stage::Settle { since_ns, .. } if late(since_ns, now_ns) => {
                self.failed(EnableFailure::Stalled)
            }
            Stage::Settle { echo_tick, .. } if tick > echo_tick => (
                Stage::AwaitRun { since_ns: now_ns },
                Next::Send(encode::enable(self.drive.id())),
            ),
            Stage::Settle { .. } => (self.stage, Next::Wait),
            Stage::AwaitRun { since_ns } => self.await_run(view, since_ns, now_ns),
            Stage::AwaitModeEcho {
                since_ns,
                run_read_ns,
            } => {
                let mit = EchoKind::ParamWrite {
                    param: Param::RunMode,
                    value: ParamValue::RunMode(RunMode::Mit),
                };
                // Strictly after the Enable's answer, so that one status never answers both frames. The drive's latest
                // status, if it is after that and in another mode, is the drive leaving Run, fresh or not. A Reset hidden
                // by a later Run in one snapshot is the bus layer's to catch: it latches the drop out of Run and stops
                // the limb, which ends this at the next step (`LimbStopped`).
                let left = view
                    .observed
                    .filter(|o| o.read_ns > run_read_ns && o.status.header.mode != Mode::Run)
                    .map(|o| o.status.header.mode);
                let answer = fresh_since(view, since_ns)
                    .filter(|a| a.read_ns > run_read_ns)
                    .map(|a| a.mode);
                if let Some(mode) = left {
                    self.failed(EnableFailure::LeftRun { last: Some(mode) })
                } else {
                    match (answer, echoed(view, mit, since_ns), late(since_ns, now_ns)) {
                        (Some(Mode::Run), true, _) => (Stage::Enabled, Next::Enabled),
                        // A fresh answer in another mode with no later status: not a view the bus builds (the answer
                        // is then the latest status, caught above), but it is the drive leaving Run all the same.
                        (Some(mode @ (Mode::Reset | Mode::Calibration)), _, _) => {
                            self.failed(EnableFailure::LeftRun { last: Some(mode) })
                        }
                        (Some(Mode::Run) | None, _, false) => (self.stage, Next::Wait),
                        (None, true, true) => self.failed(EnableFailure::LeftRun {
                            last: mode_since(view, since_ns),
                        }),
                        (Some(Mode::Run) | None, false, true) => {
                            self.failed(EnableFailure::NoModeEcho)
                        }
                    }
                }
            }
            Stage::Enabled => (self.stage, Next::Enabled),
            Stage::Failed {
                failure,
                enable_planned,
            } => (self.stage, verdict(failure, enable_planned)),
        };
        self.stage = stage;
        next
    }

    /// The step awaiting the Enable's answer, planned at `since_ns`. Run counts only inside the window from planning;
    /// once it has passed without Run, the Enable's echo only tells an Enable not seen to go out (dropped unsent on a
    /// held tick or a full queue, or not read back in time) from a drive that never answered it.
    fn await_run(&self, view: &DriveView, since_ns: u64, now_ns: u64) -> (Stage, Next) {
        if let Some(answer) = fresh_since(view, since_ns).filter(|a| a.mode == Mode::Run) {
            (
                Stage::AwaitModeEcho {
                    since_ns: now_ns,
                    run_read_ns: answer.read_ns,
                },
                Next::Send(encode::param_write(&Write::mit_mode(self.drive))),
            )
        } else if !late(since_ns, now_ns) {
            (self.stage, Next::Wait)
        } else if echoed(view, EchoKind::Enable, since_ns) {
            self.failed(EnableFailure::NoRun {
                last: mode_since(view, since_ns),
            })
        } else {
            self.failed(EnableFailure::NoEnableEcho)
        }
    }

    /// The sequence gives up with `failure`, remembering whether the Enable had been planned.
    const fn failed(&self, failure: EnableFailure) -> (Stage, Next) {
        let enable_planned = self.enable_planned();
        (
            Stage::Failed {
                failure,
                enable_planned,
            },
            verdict(failure, enable_planned),
        )
    }

    /// What ends the sequence whatever its step: another drive's view, a fault, until the Enable is planned the drive
    /// out of Reset since its preflight began, or the limb stopped or cleared since preflight; the drive's own word
    /// first, so a stop the bus made for it is named by its own rule. `None` once it has failed: the first failure
    /// stands.
    fn voided(&self, seen: Seen<'_>) -> Option<EnableFailure> {
        if let Stage::Failed { .. } = self.stage {
            return None;
        }
        if !self.address.is(seen.bus, seen.view.device) || seen.slot != self.slot {
            return Some(EnableFailure::WrongView {
                view: seen.address(),
                view_slot: seen.slot,
                drive: self.address,
                slot: self.slot,
            });
        }
        if let Some(bits) = self.faults(seen.view) {
            return Some(EnableFailure::Faults { bits });
        }
        // Once the Enable is planned a mode out of Reset is its answer, which the steps judge.
        if !self.enable_planned()
            && let Some(mode) = left_reset(seen.view, self.preflight_began_ns)
        {
            return Some(EnableFailure::NotReset { mode });
        }
        (!seen.limb.state.takes_commands() || seen.limb.generation != self.generation).then_some(
            EnableFailure::LimbStopped {
                stop: seen.limb.stop,
                enable_planned: self.enable_planned(),
            },
        )
    }

    fn faults(&self, view: &DriveView) -> Option<StatusFaults> {
        let bits = view
            .observed
            .filter(|o| o.read_ns >= self.started_ns)
            .map_or(StatusFaults::default(), |o| o.status.header.faults);
        (!bits.is_empty() || view.fault_seen).then_some(bits)
    }
}

/// What a failure asks of control: a refusal before the Enable was planned, a stop of the limb after.
const fn verdict(failure: EnableFailure, enable_planned: bool) -> Next {
    if enable_planned {
        Next::Stop(failure)
    } else {
        Next::Refused(failure)
    }
}

/// Whether a reply read at `read_ns` falls in the window of a step planned at `since_ns`.
const fn in_window(read_ns: u64, since_ns: u64) -> bool {
    read_ns >= since_ns && read_ns <= since_ns.saturating_add(RUN_WITHIN_NS)
}

/// Whether the window of a step planned at `since_ns` has passed by `now_ns`.
const fn late(since_ns: u64, now_ns: u64) -> bool {
    now_ns.saturating_sub(since_ns) > RUN_WITHIN_NS
}

/// A status that answered a frame: its mode and when it was read.
#[derive(Clone, Copy)]
struct Answer {
    mode: Mode,
    read_ns: u64,
}

/// The fresh status (the first after a command the socket took) read inside the window of a step planned at `since_ns`:
/// the drive's answer to that step's frame, as near as the protocol can tell. A later status that agrees with it (a
/// duplicate, a report) leaves it standing; one that contradicts it takes it back: awaiting the Enable's Run the step
/// waits, awaiting the write's answer a status in another mode ends the sequence by itself.
fn fresh_since(view: &DriveView, since_ns: u64) -> Option<Answer> {
    let fresh = view
        .fresh_status
        .filter(|o| in_window(o.read_ns, since_ns))?;
    let contradicted = view
        .observed
        .is_some_and(|o| o.status.header.mode != fresh.status.header.mode);
    (!contradicted).then_some(Answer {
        mode: fresh.status.header.mode,
        read_ns: fresh.read_ns,
    })
}

/// The last mode reported since a step planned at `since_ns`, fresh or not, in or after its window.
fn mode_since(view: &DriveView, since_ns: u64) -> Option<Mode> {
    view.observed
        .filter(|o| o.read_ns >= since_ns)
        .map(|o| o.status.header.mode)
}

/// Whether the drive's last echo is `kind`, read inside the window of a step planned at `since_ns`.
fn echoed(view: &DriveView, kind: EchoKind, since_ns: u64) -> bool {
    view.last_echo
        .is_some_and(|e| e.kind == kind && in_window(e.read_ns, since_ns))
}
