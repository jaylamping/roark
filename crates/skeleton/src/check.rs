//! Buses, limbs, and the checks that look across joints: unique names, unique (bus, ID), known buses, all five limbs,
//! and the current budget (PLAN item 1, "Loader refuses").

use std::collections::{HashMap, HashSet};

use robstride::DeviceId;

use crate::error::ProblemKind;
use crate::joint::{Site, bus_name, read_joint};
use crate::read::{Reader, integer, text};
use crate::types::{Bus, BusName, Limb, LimbName, Skeleton};
use crate::yaml::{Node, Value};

/// Classical CAN tops out at 1 Mbit/s (ISO 11898-1).
const MAX_BITRATE: u64 = 1_000_000;

pub(crate) fn read_buses(r: &mut Reader, node: &Node) -> Option<Vec<Bus>> {
    let mut f = r.fields(node, "buses")?;
    let mut buses = Vec::new();
    let mut ok = true;
    for entry in f.all() {
        let path = format!("buses.{}", entry.key);
        let name = bus_name(&Node {
            line: entry.key_line,
            value: Value::Scalar {
                text: entry.key.clone(),
                quoted: true,
            },
        })
        .map_err(|kind| r.report(entry.key_line, path.clone(), kind))
        .ok();
        let Some(mut bf) = r.fields(&entry.value, &path) else {
            ok = false;
            continue;
        };
        let bitrate = r.required(&mut bf, "bitrate", |n| match integer(n)? {
            v @ 1..=MAX_BITRATE => {
                u32::try_from(v).map_err(|_| ProblemKind::OutOfRange("1 to 1000000"))
            }
            _ => Err(ProblemKind::OutOfRange("1 to 1000000")),
        });
        let sample_point = r.required(&mut bf, "sample_point", crate::sample_point);
        let adapter_serial = r.nullable(&mut bf, "adapter_serial", |n| text(n).map(str::to_owned));
        bf.finish(r);
        match (name, bitrate, sample_point, adapter_serial) {
            (Some(name), Some(bitrate), Some(sample_point), Some(adapter_serial)) => {
                buses.push(Bus {
                    name,
                    bitrate,
                    sample_point,
                    adapter_serial,
                });
            }
            _ => ok = false,
        }
    }
    f.finish(r);
    ok.then_some(buses)
}

/// Every limb with its joints' sites, or `None` if any limb or joint couldn't be read.
pub(crate) fn read_limbs(r: &mut Reader, node: &Node) -> Option<Vec<(Limb, Vec<Site>)>> {
    let mut f = r.fields(node, "limbs")?;
    let mut limbs = Vec::new();
    let mut ok = true;
    for entry in f.all() {
        let path = format!("limbs.{}", entry.key);
        let Some(name) = LimbName::ALL.into_iter().find(|l| l.as_str() == entry.key) else {
            r.report(
                entry.key_line,
                path,
                ProblemKind::UnknownLimb(entry.key.clone()),
            );
            ok = false;
            continue;
        };
        let Some(mut lf) = r.fields(&entry.value, &path) else {
            ok = false;
            continue;
        };
        let joints_node = lf.take("joints", r);
        lf.finish(r);
        let Some(joints_node) = joints_node else {
            ok = false;
            continue;
        };
        let Value::Seq(items) = &joints_node.value else {
            r.report(
                joints_node.line,
                format!("{path}.joints"),
                ProblemKind::Expected("a list of joints"),
            );
            ok = false;
            continue;
        };
        let sites: Vec<Option<Site>> = items
            .iter()
            .enumerate()
            .map(|(i, n)| read_joint(r, n, &path, i))
            .collect();
        let sites: Option<Vec<Site>> = sites.into_iter().collect();
        let Some(sites) = sites else {
            ok = false;
            continue;
        };
        let joints = sites.iter().map(|s| s.joint.clone()).collect();
        limbs.push((Limb { name, joints }, sites));
    }
    for limb in LimbName::ALL {
        if !f.has(limb.as_str()) {
            r.report(f.line, "limbs", ProblemKind::MissingLimb(limb.as_str()));
            ok = false;
        }
    }
    f.finish(r);
    ok.then_some(limbs)
}

pub(crate) fn cross_joint(
    r: &mut Reader,
    s: &Skeleton,
    limbs: &[(Limb, Vec<Site>)],
    budget_line: usize,
) {
    let sites = || limbs.iter().flat_map(|(_, sites)| sites);
    let mut names: HashSet<&str> = HashSet::new();
    let mut addresses: HashMap<(&BusName, DeviceId), &str> = HashMap::new();
    let mut current_sum_a = 0.0;

    for site in sites() {
        let j = &site.joint;
        if !names.insert(j.name.as_str()) {
            r.report(
                site.line,
                site.path.clone(),
                ProblemKind::DuplicateJoint(j.name.to_string()),
            );
        }
        let Some(bus) = &j.bus else {
            // No bus: the joint is offline and can't be enabled, so it takes no address and no share of the budget.
            continue;
        };
        if !s.buses.iter().any(|b| &b.name == bus) {
            r.report(
                site.line,
                format!("{}.bus", site.path),
                ProblemKind::UnknownBus(bus.to_string()),
            );
        }
        if let Some(other) = addresses.insert((bus, j.id), j.name.as_str()) {
            r.report(
                site.line,
                format!("{}.id", site.path),
                ProblemKind::DuplicateAddress {
                    other: other.to_owned(),
                },
            );
        }
        // Every joint with a bus can be named in one enable (tenet 1), so all of them count against the budget.
        current_sum_a += j.current_cap_a.map_or(0.0, robstride::Amps::get);
    }

    let budget_a = s.power.current_budget_a.get();
    if current_sum_a > budget_a {
        r.report(
            budget_line,
            "power.current_budget_a",
            ProblemKind::CurrentBudget {
                sum_a: current_sum_a,
                budget_a,
            },
        );
    }
}
