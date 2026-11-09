//! The enable sequence for one drive (PLAN item 2, "Enable one drive"): preflight passed → active reporting off → its
//! echo plus one tick → Enable → a Run status within 50 ms → `run_mode` = MIT. Every frame goes in control's batch; no
//! MIT frame is sent before Run is seen, and only [`Next::Enabled`] lets control command the drive.
//!
//! The runtime sends no slow request to a drive while it is enabling: the bus keeps only each drive's last echo, so a
//! slow frame's echo would hide the reporting off's and the sequence would give up.
//!
//! Set Zero has no command in this stack yet. When it gets one, this sequence gains the "no Set Zero to this drive in
//! the last 800 ms" step before Enable.

use can::DriveView;
use robstride::{Drive, EchoKind, Frame, Mode, Reporting, StatusFaults, Write, encode};

use crate::preflight::PreflightPassed;
use crate::rule::RuleId;

/// How long the drive has to reach Run after its Enable is planned, and to echo its reporting off: PLAN item 2 ("refuse
/// after 50 ms"; 1.4 to 10.3 ms measured).
pub const RUN_WITHIN_NS: u64 = 50_000_000;

/// Why a drive's enable sequence gave up. Once an Enable may have gone out, the limb is stopped, not just refused.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EnableFailure {
    /// The reporting-off frame was never read back from the socket.
    NoEcho,
    /// No Run status within [`RUN_WITHIN_NS`] of the Enable; the last mode seen, if any.
    NoRun {
        /// The last mode the drive reported.
        last: Option<Mode>,
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
            Self::NoEcho => RuleId::HostBus,
            Self::NoRun { .. } => RuleId::HostMode,
            Self::Faults { .. } => RuleId::HostFault,
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
    AwaitEcho { since_ns: u64 },
    Settle { echo_tick: u64 },
    AwaitRun { since_ns: u64 },
    Enabled,
    Failed(EnableFailure),
}

/// One drive's enable sequence, stepped by the control thread once per tick as it builds that tick's batch.
#[derive(Debug, PartialEq, Eq)]
pub struct Enabling {
    drive: Drive,
    stage: Stage,
    started_ns: u64,
    enable_was_planned: bool,
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
            enable_was_planned: false,
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
            Stage::AwaitRun { .. } | Stage::Enabled => true,
            Stage::Failed(_) => self.enable_was_planned,
        }
    }

    /// The step for tick `tick`'s batch, planned at `now_ns` from the drive's latest view.
    pub fn step(&mut self, view: &DriveView, tick: u64, now_ns: u64) -> Next {
        self.enable_was_planned = self.enable_planned();
        if let Some(bits) = self.faults(view) {
            self.stage = Stage::Failed(EnableFailure::Faults { bits });
        }
        let (stage, next) = match self.stage {
            Stage::ReportingOff => (
                Stage::AwaitEcho { since_ns: now_ns },
                Next::Send(encode::active_reporting(self.drive.id(), Reporting::Off)),
            ),
            Stage::AwaitEcho { since_ns } => {
                let echoed = view.last_echo.is_some_and(|e| {
                    e.kind == EchoKind::Reporting(Reporting::Off) && e.read_ns >= since_ns
                });
                if echoed {
                    (Stage::Settle { echo_tick: tick }, Next::Wait)
                } else if now_ns.saturating_sub(since_ns) > RUN_WITHIN_NS {
                    Self::fail(EnableFailure::NoEcho)
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
                let seen = view.observed.filter(|o| o.read_ns >= since_ns);
                if seen.is_some_and(|o| o.status.header.mode == Mode::Run) {
                    (
                        Stage::Enabled,
                        Next::Send(encode::param_write(&Write::mit_mode(self.drive))),
                    )
                } else if now_ns.saturating_sub(since_ns) > RUN_WITHIN_NS {
                    Self::fail(EnableFailure::NoRun {
                        last: seen.map(|o| o.status.header.mode),
                    })
                } else {
                    (self.stage, Next::Wait)
                }
            }
            Stage::Enabled => (self.stage, Next::Enabled),
            Stage::Failed(failure) => (self.stage, Next::Failed(failure)),
        };
        self.stage = stage;
        next
    }

    const fn fail(failure: EnableFailure) -> (Stage, Next) {
        (Stage::Failed(failure), Next::Failed(failure))
    }

    fn faults(&self, view: &DriveView) -> Option<StatusFaults> {
        if let Stage::Failed(_) = self.stage {
            return None;
        }
        let bits = view
            .observed
            .filter(|o| o.read_ns >= self.started_ns)
            .map_or(StatusFaults::default(), |o| o.status.header.faults);
        (!bits.is_empty() || view.fault_seen).then_some(bits)
    }
}
