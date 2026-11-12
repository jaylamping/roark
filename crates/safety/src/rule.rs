//! The rule IDs (safety.md section 2): one per rule in PLAN item 6's table (the limits row holds two), the same string
//! in the table, the code, each test's `Guards:` line, every event the rule emits and the operator's fault display.

use can::StopReason;

/// A safety rule, by its PLAN item 6 row.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RuleId {
    /// `canTimeout` written 1000 and read back exactly that before every enable.
    DriveCanTimeout,
    /// The three caps written from the skeleton and read back as written.
    DriveCaps,
    /// The damper reads 0, protection on.
    DriveDamper,
    /// Preflight's own checks: VBUS inside the skeleton's window, no fault bits, the drive in Reset, and its model's MIT
    /// scales settled. The enable sequence reports under it
    /// too when its proof no longer holds; PLAN item 6's Preflight row says when.
    HostPreflight,
    /// The drive's UID matches the skeleton's, once commissioned.
    HostIdentity,
    /// VBUS inside the window while running.
    HostVbus,
    /// A drive that stops answering, or answers too late, stops its limb.
    HostSilence,
    /// Any fault bit stops the limb.
    HostFault,
    /// A drive that leaves Run by itself, or shows no fresh Run within 50 ms of its Enable or of its `run_mode` = MIT
    /// write, stops its limb.
    HostMode,
    /// Soft limits inside every hard stop.
    HostSoftLimit,
    /// The predicted total torque under the joint's cap.
    HostTotalTorque,
    /// No gravity feed-forward until the joint's sign is verified.
    HostSign,
    /// Pause at 60 °C, stop at 75 °C.
    HostTemperature,
    /// A hung, late or broken control side lets the drives time out.
    HostHang,
    /// Bus-off, an interface down or gone, a bus the thread can't keep up with, or an enable's frames not read back or
    /// its Enable not planned inside the reporting off's window.
    HostBus,
    /// Under-voltage or throttling on the Pi refuses enable.
    HostPiHealth,
    /// A session log that can't be written refuses the next enable.
    HostLogging,
}

impl RuleId {
    /// Every rule, in declaration order: `ALL[r.index()] == r`.
    pub const ALL: [Self; 17] = [
        Self::DriveCanTimeout,
        Self::DriveCaps,
        Self::DriveDamper,
        Self::HostPreflight,
        Self::HostIdentity,
        Self::HostVbus,
        Self::HostSilence,
        Self::HostFault,
        Self::HostMode,
        Self::HostSoftLimit,
        Self::HostTotalTorque,
        Self::HostSign,
        Self::HostTemperature,
        Self::HostHang,
        Self::HostBus,
        Self::HostPiHealth,
        Self::HostLogging,
    ];

    /// Its position in [`RuleId::ALL`], from a match the compiler holds complete, so a code built from it can't miss a
    /// rule.
    #[must_use]
    pub const fn index(self) -> usize {
        match self {
            Self::DriveCanTimeout => 0,
            Self::DriveCaps => 1,
            Self::DriveDamper => 2,
            Self::HostPreflight => 3,
            Self::HostIdentity => 4,
            Self::HostVbus => 5,
            Self::HostSilence => 6,
            Self::HostFault => 7,
            Self::HostMode => 8,
            Self::HostSoftLimit => 9,
            Self::HostTotalTorque => 10,
            Self::HostSign => 11,
            Self::HostTemperature => 12,
            Self::HostHang => 13,
            Self::HostBus => 14,
            Self::HostPiHealth => 15,
            Self::HostLogging => 16,
        }
    }

    /// The ID as written in PLAN item 6, the logs and the UI.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::DriveCanTimeout => "drive.can_timeout",
            Self::DriveCaps => "drive.caps",
            Self::DriveDamper => "drive.damper",
            Self::HostPreflight => "host.preflight",
            Self::HostIdentity => "host.identity",
            Self::HostVbus => "host.vbus",
            Self::HostSilence => "host.silence",
            Self::HostFault => "host.fault",
            Self::HostMode => "host.mode",
            Self::HostSoftLimit => "host.soft_limit",
            Self::HostTotalTorque => "host.total_torque",
            Self::HostSign => "host.sign",
            Self::HostTemperature => "host.temperature",
            Self::HostHang => "host.hang",
            Self::HostBus => "host.bus",
            Self::HostPiHealth => "host.pi_health",
            Self::HostLogging => "host.logging",
        }
    }

    /// The rule behind a stop the bus layer made on its own, or `None` for [`StopReason::Requested`] and
    /// [`StopReason::LimbRequested`], whose cause is whoever asked (the operator, or a rule the control thread checks).
    #[must_use]
    pub const fn of_stop(reason: StopReason) -> Option<Self> {
        match reason {
            StopReason::DriveFault { .. } => Some(Self::HostFault),
            StopReason::DriveMode { .. } => Some(Self::HostMode),
            StopReason::DriveSilent { .. } | StopReason::ExpiredFeedback { .. } => {
                Some(Self::HostSilence)
            }
            StopReason::ControlSilent
            | StopReason::LateWake
            | StopReason::BadBatch { .. }
            | StopReason::BadOrder { .. } => Some(Self::HostHang),
            StopReason::Backlog | StopReason::Bus(_) => Some(Self::HostBus),
            StopReason::Requested | StopReason::LimbRequested => None,
        }
    }
}

// `ALL` holds every rule at its index, so a code built from `index` decodes through `ALL`.
#[expect(
    clippy::indexing_slicing,
    reason = "checked at compile time: an index out of range fails the build"
)]
const _: () = {
    let mut i = 0;
    while i < RuleId::ALL.len() {
        assert!(RuleId::ALL[i].index() == i, "RuleId::ALL is in index order");
        i += 1;
    }
};

impl core::fmt::Display for RuleId {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Why a limb stopped: a rule, someone asking, or a stop already made on another of its buses.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cause {
    /// A rule's verdict.
    Rule(RuleId),
    /// An operator's or client's `stop`.
    Operator,
    /// The runtime is exiting.
    Shutdown,
    /// The limb was already stopped on one of its buses, for a cause recorded when that stop was asked: this carries it
    /// to the limb's other buses.
    Follows,
}
