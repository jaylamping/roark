//! The drive and limb states (PLAN item 6, States), and the rule behind each of the bus layer's own stops.

use can::{BusError, StopReason};
use safety::{Cause, DriveEvent as D, DriveState, LimbEvent as L, LimbState, RuleId};

/// Guards: safety - PLAN item 6 States, drive: offline → seen → checked → enabled, a fault latches from anywhere until a
/// clear, silence, a drop out of Run or a reboot drops preflight (an enabled drive back to seen, a silent disabled one
/// to offline), and nothing enables a drive that isn't checked.
#[test]
fn drive_states_follow_plan_item_6() {
    use DriveState::{Checked, Enabled, Faulted, Offline, Seen};
    let rows = [
        (Offline, D::Answered, Some(Seen)),
        (Seen, D::PreflightPassed, Some(Checked)),
        (Seen, D::PreflightRefused, Some(Seen)),
        (Checked, D::PreflightRefused, Some(Seen)),
        (Checked, D::RunSeen, Some(Enabled)),
        (Checked, D::Answered, Some(Checked)),
        (Enabled, D::LeftRun, Some(Seen)),
        (Enabled, D::Silent, Some(Seen)),
        (Enabled, D::Disabled, Some(Seen)),
        (Checked, D::Disabled, Some(Seen)),
        (Seen, D::Silent, Some(Offline)),
        (Checked, D::Silent, Some(Offline)),
        (Enabled, D::BusLost, Some(Offline)),
        (Seen, D::BusLost, Some(Offline)),
        // Only a checked drive enables: preflight can't be skipped.
        (Offline, D::RunSeen, None),
        (Seen, D::RunSeen, None),
        (Offline, D::PreflightPassed, None),
        // A fault latches from every state; only a clear lets go, and then preflight is needed again.
        (Offline, D::Fault, Some(Faulted)),
        (Checked, D::Fault, Some(Faulted)),
        (Enabled, D::Fault, Some(Faulted)),
        (Faulted, D::Fault, Some(Faulted)),
        (Faulted, D::Answered, None),
        (Faulted, D::PreflightPassed, None),
        (Faulted, D::RunSeen, None),
        (Faulted, D::BusLost, None),
        (Faulted, D::Cleared, Some(Seen)),
        (Seen, D::Cleared, None),
        (Enabled, D::Cleared, None),
    ];
    for (from, event, to) in rows {
        assert_eq!(from.on(event), to, "{from:?} on {event:?}");
    }
}

/// Guards: safety - PLAN item 6 States, limb: idle → enabling → enabled → stopping → faulted; a stop from any running
/// state keeps its first cause and latches, only a clear of a faulted limb makes it idle, and a refused enable that sent
/// no Enable leaves it idle.
#[test]
fn limb_states_follow_plan_item_6() {
    use LimbState::{Enabled, Enabling, Faulted, Idle, Stopping};
    let op = Cause::Operator;
    let fault = Cause::Rule(RuleId::HostFault);
    let rows = [
        (Idle, L::Enable, Some(Enabling)),
        (Enabling, L::Enabled, Some(Enabled)),
        (Enabling, L::Refused, Some(Idle)),
        (Enabled, L::Stop(fault), Some(Stopping(fault))),
        (Enabling, L::Stop(op), Some(Stopping(op))),
        (Idle, L::Stop(fault), Some(Stopping(fault))),
        (Stopping(fault), L::Stop(op), None),
        (Stopping(fault), L::Settled, Some(Faulted(fault))),
        (Faulted(fault), L::Cleared, Some(Idle)),
        // Nothing else leaves a latched or stopping limb.
        (Faulted(fault), L::Enable, None),
        (Faulted(fault), L::Stop(op), None),
        (Stopping(fault), L::Cleared, None),
        (Stopping(fault), L::Enable, None),
        // Only an idle limb starts an enable; a running one isn't cleared.
        (Enabling, L::Enable, None),
        (Enabled, L::Enable, None),
        (Enabled, L::Refused, None),
        (Enabled, L::Cleared, None),
        (Idle, L::Cleared, None),
        (Idle, L::Enabled, None),
    ];
    for (from, event, to) in rows {
        assert_eq!(from.on(event), to, "{from:?} on {event:?}");
    }
}

/// Guards: safety - safety.md section 2: each stop the bus layer makes on its own is logged under its rule's ID
/// (`host.fault`, `host.mode`, `host.silence`, `host.hang`, `host.bus`), and a requested stop carries its asker's cause.
#[test]
fn every_bus_layer_stop_is_named_by_its_rule() {
    let rows = [
        (StopReason::DriveFault { slot: 0 }, Some("host.fault")),
        (StopReason::DriveMode { slot: 0 }, Some("host.mode")),
        (StopReason::DriveSilent { slot: 0 }, Some("host.silence")),
        (
            StopReason::ExpiredFeedback { slot: 0 },
            Some("host.silence"),
        ),
        (StopReason::ControlSilent, Some("host.hang")),
        (StopReason::LateWake, Some("host.hang")),
        (StopReason::BadBatch { slot: 0 }, Some("host.hang")),
        (StopReason::Backlog, Some("host.bus")),
        (StopReason::Bus(BusError::BusOff), Some("host.bus")),
        (StopReason::Requested, None),
    ];
    for (reason, id) in rows {
        assert_eq!(
            RuleId::of_stop(reason).map(RuleId::as_str),
            id,
            "{reason:?}"
        );
    }
}
