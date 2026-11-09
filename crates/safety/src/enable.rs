//! The enable sequence for one drive (PLAN item 2, "Enable one drive"): preflight passed → active reporting off → its
//! echo plus one tick → Enable → a fresh Run status within 50 ms → `run_mode` = MIT, its echo and a fresh Run status
//! answering it. Every frame goes in control's batch; no MIT frame is sent before Run is seen, and only
//! [`Next::Enabled`] lets control command the drive. Each wait takes only a reply read inside its 50 ms window, however
//! late the sequence is stepped. An echo proves only that the frame reached the controller, so the `run_mode` write
//! counts once a fresh status read after it still shows Run: the drive took a frame and stayed enabled.
//!
//! The runtime cancels the sequence on any event that voids its preflight (see [`PreflightPassed`]); the sequence
//! itself checks only that it is stepped with its drive's view and that the drive reports no fault. It sends no slow request to a drive while it is enabling: the bus keeps only each drive's last echo, so a
//! slow frame's echo would hide the sequence's own and the sequence would give up.
//!
//! Set Zero has no command in this stack yet. When it gets one, this sequence gains the "no Set Zero to this drive in
//! the last 800 ms" step before Enable.

use can::DriveView;
use robstride::{
    DeviceId, Drive, EchoKind, Frame, Mode, Param, ParamValue, Reporting, RunMode, StatusFaults,
    Write, encode,
};

use crate::preflight::PreflightPassed;
use crate::rule::RuleId;

/// How long each step has for its reply after its frame is planned: Run after the Enable (PLAN item 2, "refuse after
/// 50 ms"; 1.4 to 10.3 ms measured), and the echo of the reporting off and of the `run_mode` write.
pub const RUN_WITHIN_NS: u64 = 50_000_000;

/// Why a drive's enable sequence gave up. Once an Enable may have gone out, the limb is stopped, not just refused.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EnableFailure {
    /// The reporting-off frame wasn't read back from the socket in time.
    NoEcho,
    /// The `run_mode` = MIT write wasn't read back from the socket in time: the drive may not be in MIT mode.
    NoModeEcho,
    /// No fresh Run status within [`RUN_WITHIN_NS`] of the Enable; the last mode seen since, if any.
    NoRun {
        /// The last mode the drive reported.
        last: Option<Mode>,
    },
    /// The `run_mode` = MIT write was echoed but no fresh Run status answered it within [`RUN_WITHIN_NS`]; the last mode
    /// seen since, if any.
    LeftRun {
        /// The last mode the drive reported.
        last: Option<Mode>,
    },
    /// The sequence was handed another drive's view: a runtime bug.
    WrongView {
        /// The view's drive.
        view: DeviceId,
        /// The drive the sequence is for.
        drive: DeviceId,
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
            Self::NoEcho | Self::NoModeEcho => RuleId::HostBus,
            Self::WrongView { .. } => RuleId::HostPreflight,
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
                "reported {mode:?} after the run_mode = MIT write, expected Run within 50 ms"
            ),
            Self::LeftRun { last: None } => {
                "sent no status within 50 ms of the run_mode = MIT write, expected Run".to_owned()
            }
            Self::WrongView { view, drive } => format!(
                "was stepped with drive {}'s view, expected drive {}'s",
                view.get(),
                drive.get()
            ),
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
            Self::NoModeEcho => {
                "Frames aren't reaching the adapter: check the bus and the runtime's log, clear the limb, then run preflight and enable again"
            }
            Self::WrongView { .. } => "A runtime bug: stop and report it with the log",
            Self::NoRun { .. } | Self::LeftRun { .. } => {
                "Check the drive's power and fault state, clear the limb, then run preflight and enable again"
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
    /// It gave up.
    Failed(EnableFailure),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Stage {
    ReportingOff,
    AwaitEcho {
        since_ns: u64,
    },
    Settle {
        echo_tick: u64,
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
            stage: Stage::ReportingOff,
            started_ns: now_ns,
        }
    }

    /// The drive.
    #[must_use]
    pub const fn drive(&self) -> Drive {
        self.drive
    }

    /// Whether the Enable has been planned, so a failure from here on must stop the limb rather than just refuse.
    #[must_use]
    pub const fn enable_planned(&self) -> bool {
        match self.stage {
            Stage::ReportingOff | Stage::AwaitEcho { .. } | Stage::Settle { .. } => false,
            Stage::AwaitRun { .. } | Stage::AwaitModeEcho { .. } | Stage::Enabled => true,
            Stage::Failed { enable_planned, .. } => enable_planned,
        }
    }

    /// The step for tick `tick`'s batch, planned at `now_ns` (the runtime's monotonic epoch, as the view's times) from the
    /// drive's latest view.
    pub fn step(&mut self, view: &DriveView, tick: u64, now_ns: u64) -> Next {
        if view.device != self.drive.id() && !matches!(self.stage, Stage::Failed { .. }) {
            self.stage = self
                .failed(EnableFailure::WrongView {
                    view: view.device,
                    drive: self.drive.id(),
                })
                .0;
        } else if let Some(bits) = self.faults(view) {
            self.stage = self.failed(EnableFailure::Faults { bits }).0;
        }
        let (stage, next) = match self.stage {
            Stage::ReportingOff => (
                Stage::AwaitEcho { since_ns: now_ns },
                Next::Send(encode::active_reporting(self.drive.id(), Reporting::Off)),
            ),
            Stage::AwaitEcho { since_ns } => {
                if echoed(view, EchoKind::Reporting(Reporting::Off), since_ns) {
                    (Stage::Settle { echo_tick: tick }, Next::Wait)
                } else if late(since_ns, now_ns) {
                    self.failed(EnableFailure::NoEcho)
                } else {
                    (self.stage, Next::Wait)
                }
            }
            // One tick after the echo.
            Stage::Settle { echo_tick } if tick > echo_tick => (
                Stage::AwaitRun { since_ns: now_ns },
                Next::Send(encode::enable(self.drive.id())),
            ),
            Stage::Settle { .. } => (self.stage, Next::Wait),
            Stage::AwaitRun { since_ns } => {
                if let Some(answer) = fresh_since(view, since_ns).filter(|a| a.mode == Mode::Run) {
                    (
                        Stage::AwaitModeEcho {
                            since_ns: now_ns,
                            run_read_ns: answer.read_ns,
                        },
                        Next::Send(encode::param_write(&Write::mit_mode(self.drive))),
                    )
                } else if late(since_ns, now_ns) {
                    self.failed(EnableFailure::NoRun {
                        last: mode_since(view, since_ns),
                    })
                } else {
                    (self.stage, Next::Wait)
                }
            }
            Stage::AwaitModeEcho {
                since_ns,
                run_read_ns,
            } => {
                let mit = EchoKind::ParamWrite {
                    param: Param::RunMode,
                    value: ParamValue::RunMode(RunMode::Mit),
                };
                // Strictly after the Enable's answer, so that one status never answers both frames. Any status after it
                // in another mode is the drive leaving Run, fresh or not.
                let left = view
                    .observed
                    .filter(|o| o.read_ns > run_read_ns && o.status.header.mode != Mode::Run)
                    .map(|o| o.status.header.mode);
                let answer = left.or_else(|| {
                    fresh_since(view, since_ns)
                        .filter(|a| a.read_ns > run_read_ns)
                        .map(|a| a.mode)
                });
                match (answer, echoed(view, mit, since_ns), late(since_ns, now_ns)) {
                    (Some(Mode::Run), true, _) => (Stage::Enabled, Next::Enabled),
                    (Some(mode @ (Mode::Reset | Mode::Calibration)), _, _) => {
                        self.failed(EnableFailure::LeftRun { last: Some(mode) })
                    }
                    (Some(Mode::Run) | None, _, false) => (self.stage, Next::Wait),
                    (None, true, true) => self.failed(EnableFailure::LeftRun {
                        last: mode_since(view, since_ns),
                    }),
                    (Some(Mode::Run) | None, false, true) => self.failed(EnableFailure::NoModeEcho),
                }
            }
            Stage::Enabled => (self.stage, Next::Enabled),
            Stage::Failed { failure, .. } => (self.stage, Next::Failed(failure)),
        };
        self.stage = stage;
        next
    }

    /// The sequence gives up with `failure`, remembering whether the Enable had been planned.
    const fn failed(&self, failure: EnableFailure) -> (Stage, Next) {
        (
            Stage::Failed {
                failure,
                enable_planned: self.enable_planned(),
            },
            Next::Failed(failure),
        )
    }

    fn faults(&self, view: &DriveView) -> Option<StatusFaults> {
        if let Stage::Failed { .. } = self.stage {
            return None;
        }
        let bits = view
            .observed
            .filter(|o| o.read_ns >= self.started_ns)
            .map_or(StatusFaults::default(), |o| o.status.header.faults);
        (!bits.is_empty() || view.fault_seen).then_some(bits)
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
/// duplicate, a report) leaves it standing; one that contradicts it takes it back, and the step waits.
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
