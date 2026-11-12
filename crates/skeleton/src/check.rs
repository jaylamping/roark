//! Buses, limbs, and the checks that look across joints: unique names, unique (bus, ID), known buses, all five limbs,
//! and the current budget (PLAN item 1, "Loader refuses").
//!
//! Cross-joint checks run over every joint that parsed, even when something elsewhere in the file didn't, so one typo
//! never hides a duplicate ID (skeleton.md section 5: every error at once).

use std::collections::{HashMap, HashSet};

use robstride::{Amps, DeviceId};

use crate::error::ProblemKind;
use crate::joint::{Site, bus_name, read_joint};
use crate::read::{Reader, integer, text};
use crate::types::{Bus, BusName, JointName, Limb, LimbName};
use crate::yaml::{Node, Value};

/// Classical CAN tops out at 1 Mbit/s (ISO 11898-1).
const MAX_BITRATE: u64 = 1_000_000;

/// What `read_buses` found: every bus that parsed, every bus name written (for the unknown-bus check), and whether all
/// of it parsed.
pub(crate) struct BusTable {
    pub(crate) buses: Vec<Bus>,
    pub(crate) names: Vec<String>,
    pub(crate) complete: bool,
}

/// What `read_limbs` found: every joint that parsed, the limbs if all of them did, and the `limbs:` line.
pub(crate) struct Limbs {
    pub(crate) sites: Vec<Site>,
    pub(crate) limbs: Option<Vec<Limb>>,
}

pub(crate) fn read_buses(r: &mut Reader, node: &Node) -> Option<BusTable> {
    let mut f = r.fields(node, "buses")?;
    let mut out = BusTable {
        buses: Vec::new(),
        names: Vec::new(),
        complete: true,
    };
    for entry in f.all() {
        out.names.push(entry.key.clone());
        let path = format!("buses.{}", entry.key);
        let key = Node {
            line: entry.key_line,
            value: Value::Scalar {
                text: entry.key.clone(),
                quoted: true,
            },
        };
        let name = bus_name(&key)
            .map_err(|kind| r.report(entry.key_line, path.clone(), kind))
            .ok();
        let Some(mut bf) = r.fields(&entry.value, &path) else {
            out.complete = false;
            continue;
        };
        let bitrate_bps = r.required(&mut bf, "bitrate_bps", |n| match integer(n)? {
            v @ 1..=MAX_BITRATE => {
                u32::try_from(v).map_err(|_| ProblemKind::OutOfRange("1 to 1000000"))
            }
            _ => Err(ProblemKind::OutOfRange("1 to 1000000")),
        });
        let sample_point = r.required(&mut bf, "sample_point", crate::sample_point);
        let adapter_serial = r.nullable(&mut bf, "adapter_serial", |n| text(n).map(str::to_owned));
        bf.finish(r);
        match (name, bitrate_bps, sample_point, adapter_serial) {
            (Some(name), Some(bitrate_bps), Some(sample_point), Some(adapter_serial)) => {
                out.buses.push(Bus {
                    name,
                    bitrate_bps,
                    sample_point,
                    adapter_serial,
                });
            }
            _ => out.complete = false,
        }
    }
    f.finish(r);
    Some(out)
}

pub(crate) fn read_limbs(r: &mut Reader, node: &Node, limbs_line: usize) -> Option<Limbs> {
    let mut f = r.fields(node, "limbs")?;
    let mut out = Limbs {
        sites: Vec::new(),
        limbs: Some(Vec::new()),
    };
    for entry in f.all() {
        let path = format!("limbs.{}", entry.key);
        let name = LimbName::ALL.into_iter().find(|l| l.as_str() == entry.key);
        if name.is_none() {
            r.report(
                entry.key_line,
                path.clone(),
                ProblemKind::UnknownLimb(entry.key.clone()),
            );
        }
        let joints = read_limb(r, &entry.value, &path);
        let complete = joints.as_ref().is_some_and(|sites| {
            sites
                .iter()
                .all(|s| s.as_ref().is_some_and(|s| s.joint.is_some()))
        });
        // Every joint entry goes to the cross-joint checks with whatever of it parsed, even when a sibling, or another
        // field of the same joint, didn't.
        let sites: Vec<Site> = joints.into_iter().flatten().flatten().collect();
        match (name, complete, &mut out.limbs) {
            (Some(name), true, Some(limbs)) => limbs.push(Limb {
                name,
                joints: sites.iter().filter_map(|s| s.joint.clone()).collect(),
            }),
            (_, _, limbs) => *limbs = None,
        }
        out.sites.extend(sites);
    }
    for limb in LimbName::ALL {
        if !f.has(limb.as_str()) {
            r.report(limbs_line, "limbs", ProblemKind::MissingLimb(limb.as_str()));
            out.limbs = None;
        }
    }
    f.finish(r);
    Some(out)
}

/// One limb's joints: `Some` with each joint's result if the limb is a mapping with a `joints` list.
fn read_limb(r: &mut Reader, node: &Node, path: &str) -> Option<Vec<Option<Site>>> {
    let mut lf = r.fields(node, path)?;
    let joints_node = lf.take("joints", r);
    lf.finish(r);
    let joints_node = joints_node?;
    let Value::Seq(items) = &joints_node.value else {
        r.report(
            joints_node.line,
            format!("{path}.joints"),
            ProblemKind::Expected("a list of joints"),
        );
        return None;
    };
    Some(
        items
            .iter()
            .enumerate()
            .map(|(i, n)| read_joint(r, n, path, i))
            .collect(),
    )
}

/// `bus_names` is `None` when `buses:` couldn't be read; `budget` is `None` when the power block couldn't.
pub(crate) fn cross_joint(
    r: &mut Reader,
    sites: &[Site],
    bus_names: Option<&[String]>,
    budget: Option<(f64, usize)>,
) {
    let mut names: HashSet<&str> = HashSet::new();
    let mut addresses: HashMap<(&BusName, DeviceId), &str> = HashMap::new();
    let mut current_sum_a = 0.0;

    for site in sites {
        // A joint whose name didn't parse is named by its path in other joints' problems.
        let name = site
            .name
            .as_ref()
            .map_or(site.path.as_str(), JointName::as_str);
        if site.name.is_some() && !names.insert(name) {
            r.report(
                site.line,
                site.path.clone(),
                ProblemKind::DuplicateJoint(name.to_owned()),
            );
        }
        let Some(Some(bus)) = &site.bus else {
            // No bus: the joint is offline and can't be enabled, so it takes no address and no share of the budget.
            // A bus that didn't parse is reported already.
            continue;
        };
        if bus_names.is_some_and(|names| !names.iter().any(|n| n == bus.as_str())) {
            r.report(
                site.bus_line,
                format!("{}.bus", site.path),
                ProblemKind::UnknownBus(bus.to_string()),
            );
        }
        if let Some(id) = site.id
            && let Some(other) = addresses.insert((bus, id), name)
        {
            r.report(
                site.id_line,
                format!("{}.id", site.path),
                ProblemKind::DuplicateAddress {
                    other: other.to_owned(),
                },
            );
        }
        // Every joint with a bus can be named in one enable (tenet 1), so each counts against the budget at the
        // current it is enabled at (`Joint::caps`, PLAN item 1), a joint with a field that didn't parse included.
        current_sum_a += site.current_a.map_or(0.0, Amps::get);
    }

    if let Some((budget_a, line)) = budget
        && current_sum_a > budget_a
    {
        r.report(
            line,
            "power.current_budget_a",
            ProblemKind::CurrentBudget {
                sum_a: current_sum_a,
                budget_a,
            },
        );
    }
}
