//! What can go wrong loading the skeleton. The loader collects every problem it finds and returns them all at once
//! (skeleton.md section 5), each naming where it is: line, limb, joint and field.

use core::fmt;
use std::path::PathBuf;

/// The skeleton couldn't be loaded. The runtime refuses to start on this (architecture.md section 5).
#[derive(Debug, thiserror::Error)]
pub enum LoadError {
    /// The file couldn't be read.
    #[error("can't read the skeleton at {}: {source}", path.display())]
    Read {
        /// The file the loader was given.
        path: PathBuf,
        /// What the OS said.
        source: std::io::Error,
    },
    /// The file was read but breaks one or more rules. Never empty.
    #[error("the skeleton has {} problem(s):{}", .0.len(), ProblemList(.0))]
    Invalid(Vec<Problem>),
}

/// One broken rule, and where.
#[derive(Clone, Debug, PartialEq)]
pub struct Problem {
    /// Line in the file, 1-based.
    pub line: usize,
    /// Where in the robot: `limbs.left_arm.left_elbow_pitch.torque_cap_nm`, or `buses.can1.bitrate`. Empty for the
    /// whole file.
    pub path: String,
    /// What is wrong.
    pub kind: ProblemKind,
}

/// The rule a [`Problem`] breaks.
#[derive(Clone, Debug, PartialEq)]
pub enum ProblemKind {
    /// The YAML itself doesn't parse.
    Yaml(String),
    /// Anchors, aliases, merge keys, tags, block scalars and multiple documents are refused (skeleton.md section 4).
    NotPlainYaml(String),
    /// The same key twice in one mapping.
    DuplicateKey(String),
    /// A key the schema doesn't have, such as a misspelt field.
    UnknownKey(String),
    /// A field that must be written out (as `null` if unknown) is missing. No safety field has a default.
    Missing(String),
    /// The value has the wrong shape, for example text where a number belongs.
    Expected(&'static str),
    /// `.nan`, `.inf` or a number too large for `f64`.
    NonFinite,
    /// A number outside the range the field allows.
    OutOfRange(&'static str),
    /// The file's `schema:` is not one this loader knows.
    UnknownSchema(u64),
    /// The actuator isn't a model the codec knows.
    UnknownActuator(String),
    /// A `[lower, upper]` range whose lower end isn't below its upper end.
    ReversedRange,
    /// `soft_rad` reaches outside `hard_rad`.
    SoftOutsideHard,
    /// A cap above what this actuator model accepts.
    CapAboveModel {
        /// The model's upper bound for this cap.
        max: f64,
    },
    /// The hard window is a full turn or wider, so no zero can fit it inside the drive's power-on turn.
    HardWindowTooWide {
        /// One turn, rad.
        max_rad: f64,
    },
    /// The hard window, seen from the drive (`zero_rad + direction × q`), leaves the one turn the drive reports after
    /// power-on, so a reading after power-up can't say which turn the joint is in.
    HardWindowOutsidePowerOnTurn {
        /// The hard window in drive position, rad.
        drive_rad: [f64; 2],
        /// The power-on turn, rad, end excluded.
        turn_rad: [f64; 2],
    },
    /// Two joints with one name.
    DuplicateJoint(String),
    /// Two joints with the same (bus, ID).
    DuplicateAddress {
        /// The other joint at this address.
        other: String,
    },
    /// A joint names a bus that isn't under `buses:`.
    UnknownBus(String),
    /// A limb that isn't one of the robot's five.
    UnknownLimb(String),
    /// A limb is missing: the robot has five, and an unbuilt one is listed with its drives offline (tenet 1).
    MissingLimb(&'static str),
    /// The currents joints that can be enabled together are enabled at (`Joint::caps`) sum above the power budget.
    CurrentBudget {
        /// Sum of those currents, A.
        sum_a: f64,
        /// `power.current_budget_a`.
        budget_a: f64,
    },
}

impl Problem {
    pub(crate) fn at_line(line: usize, kind: ProblemKind) -> Self {
        Self {
            line,
            path: String::new(),
            kind,
        }
    }
}

impl fmt::Display for Problem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let at = if self.path.is_empty() {
            "file"
        } else {
            &self.path
        };
        write!(f, "line {}: {at}: ", self.line)?;
        match &self.kind {
            ProblemKind::Yaml(why) => write!(f, "not valid YAML: {why}"),
            ProblemKind::NotPlainYaml(what) => {
                write!(f, "{what} not allowed; write every value out in full")
            }
            ProblemKind::DuplicateKey(key) => write!(f, "key `{key}` appears twice"),
            ProblemKind::UnknownKey(key) => write!(f, "unknown key `{key}`"),
            ProblemKind::Missing(key) => {
                write!(f, "missing `{key}` (write `null` if it isn't known yet)")
            }
            ProblemKind::Expected(what) => write!(f, "expected {what}"),
            ProblemKind::NonFinite => f.write_str("not a finite number"),
            ProblemKind::OutOfRange(range) => write!(f, "out of range, must be {range}"),
            ProblemKind::UnknownSchema(v) => {
                write!(
                    f,
                    "schema {v} is not one this loader knows (expected {})",
                    crate::SCHEMA
                )
            }
            ProblemKind::UnknownActuator(name) => {
                write!(f, "unknown actuator `{name}` (rs00, rs02, rs03 or rs04)")
            }
            ProblemKind::ReversedRange => f.write_str("lower end must be below upper end"),
            ProblemKind::SoftOutsideHard => f.write_str("soft_rad reaches outside hard_rad"),
            ProblemKind::CapAboveModel { max } => {
                write!(f, "above this actuator's maximum of {max}")
            }
            ProblemKind::HardWindowTooWide { max_rad } => {
                write!(
                    f,
                    "hard window is {max_rad:.3} rad or wider; it must fit inside one turn of the drive"
                )
            }
            ProblemKind::HardWindowOutsidePowerOnTurn {
                drive_rad: [lo, hi],
                turn_rad: [start, end],
            } => write!(
                f,
                "with this zero_rad and direction the hard window is drive position {lo:.3} to {hi:.3} rad, outside \
                 the {start:.3} to {end:.3} rad the drive reports after power-on"
            ),
            ProblemKind::DuplicateJoint(name) => write!(f, "joint `{name}` is listed twice"),
            ProblemKind::DuplicateAddress { other } => write!(f, "same bus and ID as `{other}`"),
            ProblemKind::UnknownBus(bus) => write!(f, "bus `{bus}` is not under `buses:`"),
            ProblemKind::UnknownLimb(name) => {
                write!(
                    f,
                    "unknown limb `{name}` (left_arm, right_arm, waist, left_leg or right_leg)"
                )
            }
            ProblemKind::MissingLimb(name) => {
                write!(f, "limb `{name}` is missing; list it with its joints")
            }
            ProblemKind::CurrentBudget { sum_a, budget_a } => {
                write!(
                    f,
                    "the currents joints with a bus are enabled at (their own caps once commissioned; until then their commissioning caps, or their own where lower) sum to {sum_a} A, above the {budget_a} A budget"
                )
            }
        }
    }
}

struct ProblemList<'a>(&'a [Problem]);

impl fmt::Display for ProblemList<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.iter().try_for_each(|p| write!(f, "\n  {p}"))
    }
}
