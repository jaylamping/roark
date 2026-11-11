//! The loader's refusals, one row per rule in PLAN item 1 ("Loader refuses", "Null is not permission") and skeleton.md
//! section 5. Every row edits one small all-limb fixture, never the live skeleton (testing.md rule 3).

use std::f64::consts::TAU;

use skeleton::{COMMISSIONING_SHARE, LoadError, ProblemKind};

/// Five limbs, some wired and some offline. One joint is fully commissioned so the checks that need a zero and a
/// direction have something to check.
const FIXTURE: &str = "\
schema: 1
name: test_robot
power:
  source: bench_24v
  vbus_v: [22.0, 26.0]
  current_budget_a: 25.0
buses:
  bus0:
    bitrate_bps: 1000000
    sample_point: 0.75
    adapter_serial: null
  bus1:
    bitrate_bps: 1000000
    sample_point: 0.75
    adapter_serial: \"ABC123\"
limbs:
  left_arm:
    joints:
      - name: arm_joint_one
        actuator: rs03
        bus: bus0
        id: 11
        uid: \"0x0123456789abcdef\"
        direction: -1
        zero_rad: 3.0
        reference_pose: \"link hanging, resting on the pad\"
        hard_rad: [-0.5, 1.5]
        soft_rad: [-0.4, 1.4]
        torque_cap_nm: 10.0
        current_cap_a: 12.0
        speed_cap_rad_s: 1.0
      - name: arm_joint_two
        actuator: rs02
        bus: bus0
        id: 12
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: 10.0
        speed_cap_rad_s: null
  right_arm:
    joints:
      - name: other_arm_joint
        actuator: rs00
        bus: bus1
        id: 11
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: null
        speed_cap_rad_s: null
  waist:
    joints:
      - name: offline_joint
        actuator: rs03
        bus: null
        id: 11
        uid: null
        direction: null
        zero_rad: null
        reference_pose: null
        hard_rad: null
        soft_rad: null
        torque_cap_nm: null
        current_cap_a: 43.0
        speed_cap_rad_s: null
  left_leg:
    joints: []
  right_leg:
    joints: []
";

/// The fixture with `from` replaced by `to`. `from` must appear exactly once, so a row can't silently edit nothing.
fn edit(from: &str, to: &str) -> String {
    assert_eq!(
        FIXTURE.matches(from).count(),
        1,
        "fixture edit `{from}` must match once"
    );
    FIXTURE.replacen(from, to, 1)
}

fn problems(text: &str) -> Vec<(String, ProblemKind)> {
    match skeleton::parse(text) {
        Ok(_) => Vec::new(),
        Err(LoadError::Invalid(problems)) => {
            problems.into_iter().map(|p| (p.path, p.kind)).collect()
        }
        // `parse` never reads a file; a read error here is a bug, and a non-empty list fails every row.
        Err(e @ LoadError::Read { .. }) => {
            vec![(e.to_string(), ProblemKind::Expected("no read error"))]
        }
    }
}

fn outside(drive_rad: [f64; 2]) -> ProblemKind {
    ProblemKind::HardWindowOutsidePowerOnTurn {
        drive_rad,
        turn_rad: [0.0, TAU],
    }
}

fn at(path: &str, kind: ProblemKind) -> (String, ProblemKind) {
    (path.to_owned(), kind)
}

const J1: &str = "limbs.left_arm.arm_joint_one";

/// A row: what it checks, the edited file, and every problem expected, as (path, kind).
type Row = (&'static str, String, Vec<(String, ProblemKind)>);

/// Guards: safety - skeleton loader refusals, PLAN item 1 "Loader refuses" and "Null is not permission", skeleton.md section 5.
#[test]
#[expect(clippy::too_many_lines, reason = "one table, one row per loader rule")]
fn loader_refuses_each_broken_rule_and_accepts_unknowns_as_null() {
    let rows: Vec<Row> = vec![
        (
            "fixture: nulls, an offline joint and a repeated ID on another bus all load",
            FIXTURE.to_owned(),
            vec![],
        ),
        (
            "duplicate joint name",
            edit("name: other_arm_joint", "name: arm_joint_one"),
            vec![at(
                "limbs.right_arm.arm_joint_one",
                ProblemKind::DuplicateJoint("arm_joint_one".to_owned()),
            )],
        ),
        (
            "duplicate bus and ID",
            edit("id: 12", "id: 11"),
            vec![at(
                "limbs.left_arm.arm_joint_two.id",
                ProblemKind::DuplicateAddress {
                    other: "arm_joint_one".to_owned(),
                },
            )],
        ),
        (
            "unknown actuator model",
            edit("actuator: rs02", "actuator: rs05"),
            vec![at(
                "limbs.left_arm.arm_joint_two.actuator",
                ProblemKind::UnknownActuator("rs05".to_owned()),
            )],
        ),
        (
            "non-finite number",
            edit("zero_rad: 3.0", "zero_rad: .nan"),
            vec![at(&format!("{J1}.zero_rad"), ProblemKind::NonFinite)],
        ),
        (
            "reversed bounds",
            edit("hard_rad: [-0.5, 1.5]", "hard_rad: [1.5, -0.5]"),
            vec![at(&format!("{J1}.hard_rad"), ProblemKind::ReversedRange)],
        ),
        (
            "soft limits outside hard limits",
            edit("soft_rad: [-0.4, 1.4]", "soft_rad: [-0.6, 1.4]"),
            vec![at(&format!("{J1}.soft_rad"), ProblemKind::SoftOutsideHard)],
        ),
        (
            "cap above the model's range",
            edit("torque_cap_nm: 10.0", "torque_cap_nm: 61.0"),
            vec![at(
                &format!("{J1}.torque_cap_nm"),
                ProblemKind::CapAboveModel { max: 60.0 },
            )],
        ),
        (
            // Drive position = 3.0 - q: the window [-0.5, 1.5] is drive 1.5 to 3.5, inside the power-on turn 0 to 2π.
            // A zero of 1.0 puts it at -0.5 to 1.5, across the fold at 0.
            "hard window crosses the drive's power-on fold",
            edit("zero_rad: 3.0", "zero_rad: 1.0"),
            vec![at(&format!("{J1}.hard_rad"), outside([-0.5, 1.5]))],
        ),
        (
            // A zero of 9.0 puts it at 7.5 to 9.5: no fold inside, but a whole turn above what the drive reports.
            "hard window sits in another turn",
            edit("zero_rad: 3.0", "zero_rad: 9.0"),
            vec![at(&format!("{J1}.hard_rad"), outside([7.5, 9.5]))],
        ),
        (
            "hard window a full turn wide is refused even with no zero",
            edit(
                "hard_rad: null\n        soft_rad: null\n        torque_cap_nm: null\n        current_cap_a: 10.0",
                "hard_rad: [-3.2, 3.2]\n        soft_rad: null\n        torque_cap_nm: null\n        current_cap_a: 10.0",
            ),
            vec![at(
                "limbs.left_arm.arm_joint_two.hard_rad",
                ProblemKind::HardWindowTooWide { max_rad: TAU },
            )],
        ),
        (
            "a problem elsewhere doesn't hide a cross-joint one",
            edit("source: bench_24v", "source: bench_48v")
                .replace("name: other_arm_joint", "name: arm_joint_one"),
            vec![
                at("power.source", ProblemKind::Expected("bench_24v")),
                at(
                    "limbs.right_arm.arm_joint_one",
                    ProblemKind::DuplicateJoint("arm_joint_one".to_owned()),
                ),
            ],
        ),
        (
            "a broken joint doesn't hide a cross-joint problem between its siblings",
            edit("zero_rad: 3.0", "zero_rad: .nan")
                .replace("name: other_arm_joint", "name: arm_joint_two"),
            vec![
                at(&format!("{J1}.zero_rad"), ProblemKind::NonFinite),
                at(
                    "limbs.right_arm.arm_joint_two",
                    ProblemKind::DuplicateJoint("arm_joint_two".to_owned()),
                ),
            ],
        ),
        (
            "a bad power field doesn't hide the current budget",
            edit("source: bench_24v", "source: bench_48v")
                .replace("current_cap_a: 10.0", "current_cap_a: 14.0"),
            vec![
                at("power.source", ProblemKind::Expected("bench_24v")),
                at(
                    "power.current_budget_a",
                    ProblemKind::CurrentBudget {
                        sum_a: 12.0 + 14.0 + 16.0 * COMMISSIONING_SHARE,
                        budget_a: 25.0,
                    },
                ),
            ],
        ),
        (
            "a bad field doesn't hide the same joint's other checks",
            edit("hard_rad: [-0.5, 1.5]", "hard_rad: [1.5, -0.5]")
                .replace("torque_cap_nm: 10.0", "torque_cap_nm: 61.0"),
            vec![
                at(&format!("{J1}.hard_rad"), ProblemKind::ReversedRange),
                at(
                    &format!("{J1}.torque_cap_nm"),
                    ProblemKind::CapAboveModel { max: 60.0 },
                ),
            ],
        ),
        (
            "a bad field doesn't hide the same joint's duplicate address",
            edit("id: 12", "id: 11").replace("current_cap_a: 10.0", "current_cap_a: -1.0"),
            vec![
                at(
                    "limbs.left_arm.arm_joint_two.id",
                    ProblemKind::DuplicateAddress {
                        other: "arm_joint_one".to_owned(),
                    },
                ),
                at(
                    "limbs.left_arm.arm_joint_two.current_cap_a",
                    ProblemKind::OutOfRange("above 0"),
                ),
            ],
        ),
        (
            "a schema that isn't a number doesn't stop the rest of the file being checked",
            edit("schema: 1", "schema: one")
                .replace("name: test_robot", "name: test_robot\nextra_key: 1"),
            vec![
                at(
                    "schema",
                    ProblemKind::Expected("a whole number without leading zeros"),
                ),
                at("", ProblemKind::UnknownKey("extra_key".to_owned())),
            ],
        ),
        (
            // YAML 1.1 tools read `012` as octal 10, so a cap with a leading zero means different things to different
            // readers.
            "a number with a leading zero",
            edit("current_cap_a: 12.0", "current_cap_a: 012"),
            vec![at(
                &format!("{J1}.current_cap_a"),
                ProblemKind::Expected("a number without leading zeros"),
            )],
        ),
        (
            "a blank is not a value",
            edit(
                "reference_pose: \"link hanging, resting on the pad\"",
                "reference_pose: \"\"",
            ),
            vec![at(
                &format!("{J1}.reference_pose"),
                ProblemKind::Expected("text (write `null` if it isn't known yet)"),
            )],
        ),
        (
            "an ID with a leading zero",
            edit("id: 12", "id: 012"),
            vec![at(
                "limbs.left_arm.arm_joint_two.id",
                ProblemKind::Expected("a whole number without leading zeros"),
            )],
        ),
        (
            "a quoted direction",
            edit("direction: -1", "direction: \"-1\""),
            vec![at(
                &format!("{J1}.direction"),
                ProblemKind::Expected("1 or -1, unquoted"),
            )],
        ),
        (
            "a UID with sign characters",
            edit("uid: \"0x0123456789abcdef\"", "uid: \"+1+2+3+4+5+6+7+8\""),
            vec![at(
                &format!("{J1}.uid"),
                ProblemKind::Expected("16 hex digits"),
            )],
        ),
        (
            "current caps on joints with a bus sum above the budget",
            // 12 A + 14 A on wired joints, and the RS00's null cap at its commissioning current (5 % of 16 A); the offline
            // joint's 43 A doesn't count, it can't be enabled.
            edit("current_cap_a: 10.0", "current_cap_a: 14.0"),
            vec![at(
                "power.current_budget_a",
                ProblemKind::CurrentBudget {
                    sum_a: 12.0 + 14.0 + 16.0 * COMMISSIONING_SHARE,
                    budget_a: 25.0,
                },
            )],
        ),
        (
            "misspelt field is unknown, and the real one is missing: both reported at once",
            edit(
                "torque_cap_nm: null\n        current_cap_a: 10.0",
                "torque_cap_mn: null\n        current_cap_a: 10.0",
            ),
            vec![
                at(
                    "limbs.left_arm.arm_joint_two",
                    ProblemKind::Missing("torque_cap_nm".to_owned()),
                ),
                at(
                    "limbs.left_arm.arm_joint_two",
                    ProblemKind::UnknownKey("torque_cap_mn".to_owned()),
                ),
            ],
        ),
        (
            "joint names a bus that isn't listed",
            edit("bus: bus1", "bus: bus2"),
            vec![at(
                "limbs.right_arm.other_arm_joint.bus",
                ProblemKind::UnknownBus("bus2".to_owned()),
            )],
        ),
        (
            "a limb is missing",
            edit("  right_leg:\n    joints: []\n", ""),
            vec![at("limbs", ProblemKind::MissingLimb("right_leg"))],
        ),
        (
            "device ID outside 1 to 127",
            edit("id: 12", "id: 128"),
            vec![at(
                "limbs.left_arm.arm_joint_two.id",
                ProblemKind::OutOfRange("1 to 127"),
            )],
        ),
        (
            "anchors and aliases",
            edit("vbus_v: [22.0, 26.0]", "vbus_v: &window [22.0, 26.0]"),
            vec![at("", ProblemKind::NotPlainYaml("anchor".to_owned()))],
        ),
        (
            "unknown schema version",
            edit("schema: 1", "schema: 2"),
            vec![at("schema", ProblemKind::UnknownSchema(2))],
        ),
    ];

    for (what, text, expected) in rows {
        assert_eq!(problems(&text), expected, "{what}");
    }

    // Problems point at the field's own line, not the joint's.
    let found = match skeleton::parse(&edit("zero_rad: 3.0", "zero_rad: 1.0")) {
        Err(LoadError::Invalid(found)) => found,
        Ok(_) | Err(LoadError::Read { .. }) => Vec::new(),
    };
    let hard_line = FIXTURE
        .lines()
        .position(|l| l.contains("hard_rad: [-0.5, 1.5]"))
        .map(|i| i + 1);
    assert_eq!(
        found.first().map(|p| p.line),
        hard_line,
        "line of the hard_rad problem"
    );
}
