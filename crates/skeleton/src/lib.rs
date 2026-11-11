#![doc = include_str!("../README.md")]

mod check;
mod commissioning;
mod error;
mod joint;
mod read;
mod types;
mod yaml;

use std::io::Read;
use std::path::Path;

pub use commissioning::Caps;
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
    parse(&read(path)?)
}

/// Reads the skeleton file at `path` as text, unchecked, for a caller that must record exactly the bytes it then
/// [`parse`]s (the session's skeleton hash).
///
/// # Errors
/// [`LoadError::Read`] if the file can't be read, [`LoadError::Invalid`] if it is over 1 MiB.
pub fn read(path: &Path) -> Result<String, LoadError> {
    let read_error = |source| LoadError::Read {
        path: path.to_owned(),
        source,
    };
    // Read through `take`, not a size check first: a FIFO or /dev/zero reports size 0, and a file can grow after the check.
    let mut text = String::new();
    std::fs::File::open(path)
        .map_err(read_error)?
        .take(MAX_BYTES + 1)
        .read_to_string(&mut text)
        .map_err(read_error)?;
    if u64::try_from(text.len()).map_or(true, |n| n > MAX_BYTES) {
        return Err(LoadError::Invalid(vec![Problem::at_line(
            1,
            ProblemKind::OutOfRange("at most 1 MiB"),
        )]));
    }
    Ok(text)
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
    // A missing or unreadable schema is one more problem, and the rest is still checked against this schema's rules.
    let schema = r.required(&mut f, "schema", integer);
    if let Some(schema) = schema
        && schema != SCHEMA
    {
        // Nothing else in a file of another schema can be read with these rules.
        r.report(
            f.line_of("schema"),
            "schema",
            ProblemKind::UnknownSchema(schema),
        );
        return None;
    }
    let name = r.required(&mut f, "name", |n| text(n).map(str::to_owned));
    let power = f.take("power", r).and_then(|n| read_power(r, n));
    let buses = f.take("buses", r).and_then(|n| check::read_buses(r, n));
    let limbs_line = f.line_of("limbs");
    let limbs = f
        .take("limbs", r)
        .and_then(|n| check::read_limbs(r, n, limbs_line));
    f.finish(r);

    // Cross-joint checks run on whatever parsed, so every problem is reported at once.
    let budget = power.as_ref().and_then(|p| p.budget);
    if let Some(limbs) = &limbs {
        check::cross_joint(
            r,
            &limbs.sites,
            buses.as_ref().map(|b| b.names.as_slice()),
            budget,
        );
    }

    schema?;
    let buses = buses.filter(|b| b.complete)?.buses;
    Some(Skeleton {
        name: name?,
        power: power?.power?,
        buses,
        limbs: limbs?.limbs?,
    })
}

/// What `read_power` found: the block if all of it parsed, and the budget with its line if that field did, so the
/// budget check still runs when another power field is broken.
struct PowerBlock {
    power: Option<Power>,
    budget: Option<(f64, usize)>,
}

fn read_power(r: &mut Reader, node: &Node) -> Option<PowerBlock> {
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
    let budget_line = f.line_of("current_budget_a");
    let current_budget_a = r.required(&mut f, "current_budget_a", positive(Amps::new));
    f.finish(r);
    let power = (|| {
        Some(Power {
            source: source?,
            vbus_v: vbus_v?,
            current_budget_a: current_budget_a?,
        })
    })();
    let budget = current_budget_a.map(|a| (a.get(), budget_line));
    Some(PowerBlock { power, budget })
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
