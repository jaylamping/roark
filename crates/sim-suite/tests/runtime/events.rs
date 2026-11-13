//! What the runtime's two vcan runs leave on `/event`, checked against what each run did.

use telemetry::EventKind;
use telemetry::wire::Event;

use crate::common::{self, Brief};

/// The stop-and-clear run: every stop and clear is an event, and nothing was enabled.
pub(crate) fn of_the_stop_and_clear_run(events: &[Event]) {
    // Every stop and clear is an event: the operator's two stops, the run's end as the robot's stop, the refused
    // clear and the clear on each bus; nothing was enabled.
    let brief = Brief::default();
    let operator = Brief {
        reason: Some("operator"),
        ..brief
    };
    let shutdown = Brief {
        reason: Some("shutdown"),
        ..brief
    };
    assert_eq!(
        common::of_kind(events, EventKind::RobotStopped),
        [operator, shutdown]
    );
    assert_eq!(
        common::of_kind(events, EventKind::LimbStopped),
        [Brief {
            limb: Some("right_arm"),
            ..operator
        }]
    );
    let left_leg = Brief {
        limb: Some("left_leg"),
        tag: Some(1),
        ..brief
    };
    assert_eq!(
        common::of_kind(events, EventKind::ClearRefused),
        [Brief {
            reason: Some("offline"),
            ..left_leg
        }]
    );
    let cleared = |bus| Brief {
        limb: Some("right_arm"),
        bus: Some(bus),
        tag: Some(2),
        ..brief
    };
    let mut got = common::of_kind(events, EventKind::LimbCleared);
    got.sort_by_key(|e| e.bus);
    assert_eq!(got, [cleared("can0"), cleared("can1")]);
    assert_eq!(common::of_kind(events, EventKind::EnableStarted), []);
}

/// The enable run.
pub(crate) fn of_the_enable_run(events: &[Event]) {
    // The event log names each refusal's joint, limb and rule, each enable started and held, and the cause of each
    // stop: the late Run (tag 7) and the mate put in Run (after tag 9) under host.mode, the bus's fault under
    // host.fault, the operator's two, and the hold carrying the operator's bus stops to the limb (following them).
    let brief = Brief::default();
    let refused = |tag, joint, limb, rule, reason| Brief {
        joint: Some(joint),
        limb: Some(limb),
        rule,
        reason: Some(reason),
        tag: Some(tag),
        ..brief
    };
    assert_eq!(
        common::of_kind(events, EventKind::EnableRefused),
        [
            refused(
                1,
                "leg_a_one",
                "left_leg",
                Some("host.preflight"),
                "preflight"
            ),
            refused(3, "arm_a_one", "left_arm", None, "already_enabled"),
            refused(7, "arm_a_two", "left_arm", Some("host.mode"), "sequence"),
        ],
        "{events:?}"
    );
    let joints_and_tags = |kind| {
        common::of_kind(events, kind)
            .iter()
            .map(|e| (e.joint.unwrap_or_default(), e.tag.unwrap_or_default()))
            .collect::<Vec<_>>()
    };
    // One event per joint of each enable that started, in roster order.
    assert_eq!(
        joints_and_tags(EventKind::EnableStarted),
        [
            ("arm_a_one", 2),
            ("arm_a_two", 2),
            ("arm_a_one", 5),
            ("arm_a_two", 5),
            ("arm_a_two", 7),
            ("arm_a_one", 9),
            ("arm_a_one", 11),
            ("waist_one", 12),
        ],
        "{events:?}"
    );
    let tags = |kind| {
        common::of_kind(events, kind)
            .iter()
            .map(|e| e.tag.unwrap_or_default())
            .collect::<Vec<_>>()
    };
    assert_eq!(
        tags(EventKind::EnableSucceeded),
        [2, 5, 9, 11, 12],
        "{events:?}"
    );
    // The left arm is on one bus: one answer per clear.
    assert_eq!(tags(EventKind::LimbCleared), [4, 6, 8, 10], "{events:?}");
    let stops = common::of_kind(events, EventKind::LimbStopped);
    assert!(
        stops.iter().all(|e| e.limb == Some("left_arm")),
        "{events:?}"
    );
    let rules: Vec<_> = stops.iter().filter_map(|e| e.rule).collect();
    assert_eq!(
        rules,
        ["host.mode", "host.mode", "host.fault"],
        "{events:?}"
    );
    let reasons = |reason| stops.iter().filter(|e| e.reason == Some(reason)).count();
    assert_eq!(reasons("operator"), 2, "{events:?}");
    assert_eq!(reasons("follows_bus_stop"), 2, "{events:?}");
    assert_eq!(stops.len(), 7, "{events:?}");
    assert_eq!(
        common::of_kind(events, EventKind::RobotStopped),
        [Brief {
            reason: Some("shutdown"),
            ..brief
        }]
    );
}
