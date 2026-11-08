//! Loads and checks `config/skeleton.yaml`, the one file that says what the robot is (tenet 2).
//!
//! The file is parsed once, at startup, into checked types ([`Skeleton`]); nothing downstream sees raw YAML or re-checks
//! it. Every problem in the file is reported at once, each naming its line, limb, joint and field. The rules are PLAN
//! item 1, "Loader refuses", and skeleton.md sections 4 and 5.
//!
//! Must never: write the skeleton, read any other file about the hardware (CAD, URDF, legacy config), or give a safety
//! value a default. Unknown is `None`, and `None` refuses enable downstream.
//! Talks to: `robstride` for the actuator models and their ranges. Read by every binary that needs the robot's shape.

mod check;
mod error;
mod joint;
mod read;
mod types;
mod yaml;

use std::path::Path;

pub use error::{LoadError, Problem, ProblemKind};
pub use types::{
    Bus, BusName, Direction, Joint, JointName, Limb, LimbName, Power, PowerSource, Skeleton, Uid,
    Window,
};

use robstride::{Amps, Volts};

use crate::read::{Reader, integer, number, positive, range, text};
use crate::yaml::Node;

/// The schema version this loader reads. Bumped when an older file no longer loads (skeleton.md section 1).
const SCHEMA: u64 = 1;

/// Upper bound on the file's size. The real file is a few kB; this stops a wrong path (a log, a disk image) from being
/// read whole.
const MAX_BYTES: u64 = 1 << 20;

/// Reads and checks the skeleton at `path`.
///
/// # Errors
/// [`LoadError::Read`] if the file can't be read, [`LoadError::Invalid`] with every problem found otherwise.
pub fn load(path: &Path) -> Result<Skeleton, LoadError> {
    let read_error = |source| LoadError::Read {
        path: path.to_owned(),
        source,
    };
    let size = std::fs::metadata(path).map_err(read_error)?.len();
    if size > MAX_BYTES {
        return Err(LoadError::Invalid(vec![Problem::at_line(
            1,
            ProblemKind::OutOfRange("at most 1 MiB"),
        )]));
    }
    let text = std::fs::read_to_string(path).map_err(read_error)?;
    parse(&text)
}

/// Checks skeleton YAML given as text.
///
/// # Errors
/// [`LoadError::Invalid`] with every problem found.
pub fn parse(text: &str) -> Result<Skeleton, LoadError> {
    let root = yaml::parse(text).map_err(|p| LoadError::Invalid(vec![p]))?;
    let mut r = Reader::default();
    let skeleton = read_skeleton(&mut r, &root);
    match skeleton {
        Some(s) if r.problems.is_empty() => Ok(s),
        Some(_) | None => {
            if r.problems.is_empty() {
                // A `None` always comes with a reported problem; this keeps the error non-empty if that ever breaks.
                r.report(root.line, "", ProblemKind::Expected("a valid skeleton"));
            }
            r.problems.sort_by_key(|p| p.line);
            Err(LoadError::Invalid(r.problems))
        }
    }
}

fn read_skeleton(r: &mut Reader, root: &Node) -> Option<Skeleton> {
    let mut f = r.fields(root, "")?;
    let schema = r.required(&mut f, "schema", integer)?;
    if schema != SCHEMA {
        // Nothing else in a file of another schema can be read with these rules.
        r.report(root.line, "schema", ProblemKind::UnknownSchema(schema));
        return None;
    }
    let name = r.required(&mut f, "name", |n| match text(n)? {
        "" => Err(ProblemKind::Expected("a name")),
        t => Ok(t.to_owned()),
    });
    let power = f.take("power", r).and_then(|n| read_power(r, n));
    let buses = f.take("buses", r).and_then(|n| check::read_buses(r, n));
    let limbs = f.take("limbs", r).and_then(|n| check::read_limbs(r, n));
    f.finish(r);

    let (power, budget_line) = power?;
    let skeleton = Skeleton {
        name: name?,
        power,
        buses: buses?,
        limbs: Vec::new(),
    };
    let limbs = limbs?;
    check::cross_joint(r, &skeleton, &limbs, budget_line);
    Some(Skeleton {
        limbs: limbs.into_iter().map(|(limb, _)| limb).collect(),
        ..skeleton
    })
}

fn read_power(r: &mut Reader, node: &Node) -> Option<(Power, usize)> {
    let mut f = r.fields(node, "power")?;
    let source = r.required(&mut f, "source", |n| match text(n)? {
        "bench_24v" => Ok(PowerSource::Bench24V),
        _ => Err(ProblemKind::Expected("bench_24v")),
    });
    let vbus_v = r.required(&mut f, "vbus_v", |n| {
        let (lower, upper) = range(Volts::new)(n)?;
        if lower.get() > 0.0 {
            Ok(Window { lower, upper })
        } else {
            Err(ProblemKind::OutOfRange("above 0 V"))
        }
    });
    let budget_node = f.take("current_budget_a", r);
    let budget_line = budget_node.map_or(f.line, |n| n.line);
    let current_budget_a =
        budget_node.and_then(|n| r.parsed(n, f.path_of("current_budget_a"), positive(Amps::new)));
    f.finish(r);
    Some((
        Power {
            source: source?,
            vbus_v: vbus_v?,
            current_budget_a: current_budget_a?,
        },
        budget_line,
    ))
}

/// The sample point as a fraction strictly between 0 and 1.
pub(crate) fn sample_point(node: &Node) -> Result<f64, ProblemKind> {
    let value = number(node)?;
    if value > 0.0 && value < 1.0 {
        Ok(value)
    } else {
        Err(ProblemKind::OutOfRange("between 0 and 1"))
    }
}
