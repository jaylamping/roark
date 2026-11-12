//! The interface check at a bus's start (can.md section 2, Socket setup): a real interface runs only if its driver, bit
//! timing, state and modes match the skeleton; a `vcan` interface is the simulator and is taken as it is.
//!
//! The runtime doesn't set the interface up: `deploy/` link setup does (bitrate, sample point, TX queue, restart). This
//! module only reads what the kernel reports, through `ip -details -json link show` and the device's driver link in
//! sysfs, and refuses a bus that doesn't match before the first frame. Every mismatch is reported at once.

use std::fmt;

use serde_json::Value;

/// What the skeleton says a bus's interface must be.
#[derive(Clone, Debug, PartialEq)]
pub struct InterfaceSpec {
    /// Bit rate, bit/s.
    pub bitrate_bps: u32,
    /// Sample point, as a fraction of the bit.
    pub sample_point: f64,
    /// The Linux driver, as `/sys/class/net/<bus>/device/driver` names it.
    pub driver: String,
}

/// The interface a bus opened on, for the runtime's startup log.
#[derive(Clone, Debug, PartialEq)]
pub enum Interface {
    /// A `vcan` interface: the simulator's bus, with no driver or bit timing to check.
    Sim,
    /// A CAN controller that matched the skeleton.
    Real(RealInterface),
}

/// What the kernel reported for a real interface that passed the check.
#[derive(Clone, Debug, PartialEq)]
pub struct RealInterface {
    /// The driver.
    pub driver: String,
    /// Bit rate, bit/s.
    pub bitrate_bps: u32,
    /// Sample point as `ip` prints it (three decimals).
    pub sample_point: String,
    /// The controller state (`ERROR-ACTIVE`, `ERROR-WARNING` or `ERROR-PASSIVE`).
    pub state: String,
    /// The controller modes switched on (`ip`'s `ctrlmode`), none of them one the check refuses.
    pub modes: Vec<String>,
    /// The kernel's automatic bus-off restart, ms; 0 is off. Not checked: the bus layer latches a bus-off whatever the
    /// controller does next (can.md section 2, Errors and bus-off).
    pub restart_ms: Option<u64>,
    /// The controller's clock, Hz.
    pub clock_hz: Option<u64>,
    /// The interface's TX queue length, frames.
    pub txqueuelen: Option<u64>,
}

impl RealInterface {
    /// Whether the controller was error-passive when checked: the bus then starts unhealthy
    /// (`BusTick::start_error_passive`) until an error frame says it recovered.
    #[must_use]
    pub(crate) fn starts_error_passive(&self) -> bool {
        self.state == ERROR_PASSIVE
    }
}

impl fmt::Display for Interface {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Sim => f.write_str("vcan (sim)"),
            Self::Real(r) => {
                write!(
                    f,
                    "{}, {} bit/s, sample point {}, {}",
                    r.driver, r.bitrate_bps, r.sample_point, r.state
                )?;
                if !r.modes.is_empty() {
                    write!(f, ", modes {}", r.modes.join(" "))?;
                }
                if let Some(ms) = r.restart_ms {
                    write!(f, ", restart-ms {ms}")?;
                }
                if let Some(hz) = r.clock_hz {
                    write!(f, ", clock {hz} Hz")?;
                }
                if let Some(q) = r.txqueuelen {
                    write!(f, ", txqueuelen {q}")?;
                }
                Ok(())
            }
        }
    }
}

/// One way a real interface differs from what the skeleton says.
#[derive(Clone, Debug, PartialEq, thiserror::Error)]
pub enum Mismatch {
    /// Not a CAN interface at all (`lo`, an Ethernet device), or a kind this layer doesn't know.
    #[error("it is not a CAN interface (kind {})", kind.as_deref().unwrap_or("none"))]
    NotCan {
        /// `ip`'s `info_kind`, if any.
        kind: Option<String>,
    },
    /// The interface is administratively down.
    #[error("it is down (bring it up with its link setup)")]
    Down,
    /// Another driver than the skeleton's: another adapter took the bus's name.
    #[error("driver {} is not the skeleton's {expected}", found.as_deref().unwrap_or("(none found)"))]
    Driver {
        /// The skeleton's.
        expected: String,
        /// The interface's, if it has one.
        found: Option<String>,
    },
    /// Another bit rate than the skeleton's, or none set.
    #[error("bitrate {} bit/s is not the skeleton's {expected}", found.map_or_else(|| "(unset)".to_owned(), |b| b.to_string()))]
    Bitrate {
        /// The skeleton's.
        expected: u32,
        /// The interface's, if set.
        found: Option<u64>,
    },
    /// Another sample point than the skeleton's, or none set.
    #[error("sample point {} is not the skeleton's {expected:.3}", found.as_deref().unwrap_or("(unset)"))]
    SamplePoint {
        /// The skeleton's.
        expected: f64,
        /// The interface's, as `ip` prints it.
        found: Option<String>,
    },
    /// The controller is bus-off, stopped or asleep: it can't carry the bus's traffic as it stands.
    #[error("controller state {found} (restart the link: ip link set <bus> down, then up)")]
    State {
        /// The state `ip` reports.
        found: String,
    },
    /// A controller mode that hides a missing bus: frames would look sent though nothing reached the wire or was
    /// acknowledged.
    #[error("controller mode {mode} is on")]
    Mode {
        /// The mode, as `ip` names it.
        mode: String,
    },
}

/// Why an interface was refused.
#[derive(Clone, Debug, PartialEq, thiserror::Error)]
pub enum Refusal {
    /// The kernel's report couldn't be read, so nothing is opened.
    #[error("can't read the interface: {0}")]
    Unreadable(String),
    /// It is a real interface that doesn't match the skeleton.
    #[error("{}", join(.0))]
    Mismatch(Vec<Mismatch>),
}

fn join(mismatches: &[Mismatch]) -> String {
    mismatches
        .iter()
        .map(ToString::to_string)
        .collect::<Vec<_>>()
        .join("; ")
}

/// States a controller may start a bus in. Error-warning and error-passive still send and acknowledge; a controller
/// whose frames went unacknowledged while the drives were unpowered (an E-stop, `robot-cli disable` on a dead bus) sits
/// in error-passive until frames are acknowledged again, so refusing it would refuse every restart until someone resets
/// the link. The bus layer doesn't stop for error-passive mid-run either. Bus-off, stopped and asleep carry nothing.
const RUNNABLE_STATES: [&str; 3] = ["ERROR-ACTIVE", "ERROR-WARNING", ERROR_PASSIVE];

/// The state `ip` names error-passive: the bus starts unhealthy in it (`BusTick::start_error_passive`).
const ERROR_PASSIVE: &str = "ERROR-PASSIVE";

/// Controller modes that make frames look sent when nothing reached the wire or was acknowledged: loopback (frames
/// never leave the controller), listen-only (it never sends or acknowledges) and presume-ack (a missing receiver
/// raises no error).
const REFUSED_MODES: [&str; 3] = ["LOOPBACK", "LISTEN-ONLY", "PRESUME-ACK"];

/// Sample points `ip` prints to three decimals from the kernel's per-mille value; half a per-mille tells them apart.
const SAMPLE_POINT_TOLERANCE: f64 = 0.0005;

/// Read `bus` as the kernel reports it and check it against `spec`.
///
/// # Errors
/// [`Refusal`]: the report couldn't be read, or the interface doesn't match.
#[cfg(target_os = "linux")]
pub(crate) fn check_bus(bus: &str, spec: &InterfaceSpec) -> Result<Interface, Refusal> {
    use std::path::Path;
    use std::process::Command;

    if bus.is_empty() || bus.starts_with('-') || bus.contains('/') {
        return Err(Refusal::Unreadable(format!(
            "{bus:?} is not an interface name"
        )));
    }
    let out = Command::new("ip")
        .args(["-details", "-json", "link", "show", "dev", bus])
        .output()
        .map_err(|e| Refusal::Unreadable(format!("can't run ip: {e}")))?;
    if !out.status.success() {
        return Err(Refusal::Unreadable(
            String::from_utf8_lossy(&out.stderr).trim().to_owned(),
        ));
    }
    // A virtual interface has no device, so no driver link; any other failure to read it is reported.
    let driver =
        match std::fs::read_link(Path::new("/sys/class/net").join(bus).join("device/driver")) {
            Ok(p) => p.file_name().map(|n| n.to_string_lossy().into_owned()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
            Err(e) => {
                return Err(Refusal::Unreadable(format!(
                    "can't read {bus}'s driver from sysfs: {e}"
                )));
            }
        };
    check(
        &String::from_utf8_lossy(&out.stdout),
        driver.as_deref(),
        spec,
    )
}

/// Check one interface: `ip_json` is `ip -details -json link show dev <bus>`'s output, `driver` the device's driver
/// (none for a virtual interface).
///
/// # Errors
/// [`Refusal`]: the report couldn't be read, or the interface doesn't match.
pub(crate) fn check(
    ip_json: &str,
    driver: Option<&str>,
    spec: &InterfaceSpec,
) -> Result<Interface, Refusal> {
    let links: Value = serde_json::from_str(ip_json)
        .map_err(|e| Refusal::Unreadable(format!("ip's report isn't JSON: {e}")))?;
    let Some([link]) = links.as_array().map(Vec::as_slice) else {
        return Err(Refusal::Unreadable(
            "ip didn't report exactly one interface".to_owned(),
        ));
    };
    let info = link.get("linkinfo");
    let kind = info
        .and_then(|i| i.get("info_kind"))
        .and_then(Value::as_str);
    match kind {
        Some("vcan") => return Ok(Interface::Sim),
        Some("can") => {}
        other => {
            return Err(Refusal::Mismatch(vec![Mismatch::NotCan {
                kind: other.map(str::to_owned),
            }]));
        }
    }
    let data = info.and_then(|i| i.get("info_data"));
    let timing = data.and_then(|d| d.get("bittiming"));
    let mut wrong = Vec::new();

    let up = link
        .get("flags")
        .and_then(Value::as_array)
        .is_some_and(|flags| flags.iter().any(|f| f.as_str() == Some("UP")));
    if !up {
        wrong.push(Mismatch::Down);
    }
    if driver != Some(spec.driver.as_str()) {
        wrong.push(Mismatch::Driver {
            expected: spec.driver.clone(),
            found: driver.map(str::to_owned),
        });
    }
    let bitrate = timing
        .and_then(|t| t.get("bitrate"))
        .and_then(Value::as_u64);
    if bitrate != Some(u64::from(spec.bitrate_bps)) {
        wrong.push(Mismatch::Bitrate {
            expected: spec.bitrate_bps,
            found: bitrate,
        });
    }
    let sample_point = sample_point(timing);
    let sample_matches = sample_point
        .as_deref()
        .and_then(|s| s.parse::<f64>().ok())
        .is_some_and(|sp| (sp - spec.sample_point).abs() < SAMPLE_POINT_TOLERANCE);
    if !sample_matches {
        wrong.push(Mismatch::SamplePoint {
            expected: spec.sample_point,
            found: sample_point.clone(),
        });
    }
    // A down interface reports STOPPED; `Down` already says so.
    let state = data
        .and_then(|d| d.get("state"))
        .and_then(Value::as_str)
        .unwrap_or("(none)");
    if up && !RUNNABLE_STATES.contains(&state) {
        wrong.push(Mismatch::State {
            found: state.to_owned(),
        });
    }
    let modes = modes(data)?;
    for mode in modes.iter().filter(|m| REFUSED_MODES.contains(&m.as_str())) {
        wrong.push(Mismatch::Mode { mode: mode.clone() });
    }

    if !wrong.is_empty() {
        return Err(Refusal::Mismatch(wrong));
    }
    // What the kernel reported; it matched the skeleton to get here.
    Ok(Interface::Real(RealInterface {
        driver: driver.unwrap_or_default().to_owned(),
        bitrate_bps: bitrate
            .and_then(|b| u32::try_from(b).ok())
            .unwrap_or_default(),
        sample_point: sample_point.unwrap_or_default(),
        state: state.to_owned(),
        modes,
        restart_ms: data
            .and_then(|d| d.get("restart_ms"))
            .and_then(Value::as_u64),
        clock_hz: data.and_then(|d| d.get("clock")).and_then(Value::as_u64),
        txqueuelen: link.get("txqlen").and_then(Value::as_u64),
    }))
}

/// The sample point as `ip` prints it: a string ("0.750"), or a number in case a version prints one.
fn sample_point(timing: Option<&Value>) -> Option<String> {
    timing.and_then(|t| t.get("sample_point")).and_then(|v| {
        v.as_str()
            .map(str::to_owned)
            .or_else(|| v.as_f64().map(|n| format!("{n:.3}")))
    })
}

/// The controller modes switched on. `ip` leaves `ctrlmode` out when no mode is on; one in any other shape than a list
/// of names can't be read.
fn modes(data: Option<&Value>) -> Result<Vec<String>, Refusal> {
    let Some(m) = data.and_then(|d| d.get("ctrlmode")) else {
        return Ok(Vec::new());
    };
    match m
        .as_array()
        .map(|a| a.iter().map(Value::as_str).collect::<Option<Vec<_>>>())
    {
        Some(Some(names)) => Ok(names.into_iter().map(str::to_owned).collect()),
        _ => Err(Refusal::Unreadable(format!(
            "ip's ctrlmode isn't a list of names: {m}"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> InterfaceSpec {
        InterfaceSpec {
            bitrate_bps: 1_000_000,
            sample_point: 0.75,
            driver: "mcp251xfd".to_owned(),
        }
    }

    /// An MCP2518FD channel set up as the skeleton says, in the shape iproute2's `ip -details -json link show` prints
    /// (`ip/iplink_can.c`, `can_print_opt`: the sample point is a string, `ctrlmode` is left out when no mode is on).
    /// `edit` changes it for one row.
    fn report(edit: impl FnOnce(&mut Value)) -> String {
        let mut link = serde_json::json!({
            "ifindex": 4,
            "ifname": "can1",
            "flags": ["NOARP", "UP", "LOWER_UP", "ECHO"],
            "mtu": 16,
            "operstate": "UP",
            "txqlen": 10,
            "link_type": "can",
            "linkinfo": {
                "info_kind": "can",
                "info_data": {
                    "ctrlmode": ["BERR-REPORTING"],
                    "state": "ERROR-ACTIVE",
                    "berr_counter": { "tx": 0, "rx": 0 },
                    "restart_ms": 0,
                    "bittiming": {
                        "bitrate": 1_000_000, "sample_point": "0.750", "tq": 25, "prop_seg": 14,
                        "phase_seg1": 15, "phase_seg2": 10, "sjw": 1, "brp": 1
                    },
                    "clock": 40_000_000
                }
            }
        });
        edit(&mut link);
        serde_json::json!([link]).to_string()
    }

    /// What the check reports for [`report`]'s interface in `state`: the kernel's values.
    fn passed(state: &str) -> RealInterface {
        RealInterface {
            driver: "mcp251xfd".to_owned(),
            bitrate_bps: 1_000_000,
            sample_point: "0.750".to_owned(),
            state: state.to_owned(),
            modes: vec!["BERR-REPORTING".to_owned()],
            restart_ms: Some(0),
            clock_hz: Some(40_000_000),
            txqueuelen: Some(10),
        }
    }

    fn set(path: &[&str], value: Value) -> impl FnOnce(&mut Value) {
        let path: Vec<String> = path.iter().map(|s| (*s).to_owned()).collect();
        move |v| {
            let mut at = v;
            for key in &path {
                at = &mut at[key.as_str()];
            }
            *at = value;
        }
    }

    /// Guards: number - the skeleton's driver, bitrate and sample point, checked against the real interface before
    /// the bus's first frame, and the controller states and modes that would hide a missing bus (can.md section 2,
    /// Socket setup).
    #[test]
    #[expect(clippy::too_many_lines, reason = "one table, one row per check")]
    fn a_real_interface_runs_only_as_the_skeleton_says() {
        use serde_json::json;
        /// A row: what it shows, `ip`'s report, the driver, and what the check reports on a pass or finds wrong.
        type Row = (
            &'static str,
            String,
            Option<&'static str>,
            Result<RealInterface, Vec<Mismatch>>,
        );
        let mcp = Some("mcp251xfd");
        let rows: Vec<Row> = vec![
            ("as set up", report(|_| {}), mcp, Ok(passed("ERROR-ACTIVE"))),
            (
                "error-warning still carries the bus",
                report(set(
                    &["linkinfo", "info_data", "state"],
                    json!("ERROR-WARNING"),
                )),
                mcp,
                Ok(passed("ERROR-WARNING")),
            ),
            (
                "the sample point as a number",
                report(set(
                    &["linkinfo", "info_data", "bittiming", "sample_point"],
                    json!(0.75),
                )),
                mcp,
                Ok(passed("ERROR-ACTIVE")),
            ),
            (
                "another adapter took the name",
                report(|_| {}),
                Some("mcp251x"),
                Err(vec![Mismatch::Driver {
                    expected: "mcp251xfd".to_owned(),
                    found: Some("mcp251x".to_owned()),
                }]),
            ),
            (
                "no driver",
                report(|_| {}),
                None,
                Err(vec![Mismatch::Driver {
                    expected: "mcp251xfd".to_owned(),
                    found: None,
                }]),
            ),
            (
                "500 kbit/s",
                report(set(
                    &["linkinfo", "info_data", "bittiming", "bitrate"],
                    json!(500_000),
                )),
                mcp,
                Err(vec![Mismatch::Bitrate {
                    expected: 1_000_000,
                    found: Some(500_000),
                }]),
            ),
            (
                "never configured: no bit timing",
                report(set(&["linkinfo", "info_data", "bittiming"], Value::Null)),
                mcp,
                Err(vec![
                    Mismatch::Bitrate {
                        expected: 1_000_000,
                        found: None,
                    },
                    Mismatch::SamplePoint {
                        expected: 0.75,
                        found: None,
                    },
                ]),
            ),
            (
                "the controller's nearest sample point",
                report(set(
                    &["linkinfo", "info_data", "bittiming", "sample_point"],
                    json!("0.875"),
                )),
                mcp,
                Err(vec![Mismatch::SamplePoint {
                    expected: 0.75,
                    found: Some("0.875".to_owned()),
                }]),
            ),
            (
                "down",
                report(|l| {
                    l["flags"] = json!(["NOARP", "ECHO"]);
                    l["linkinfo"]["info_data"]["state"] = json!("STOPPED");
                }),
                mcp,
                Err(vec![Mismatch::Down]),
            ),
            (
                "bus-off",
                report(set(&["linkinfo", "info_data", "state"], json!("BUS-OFF"))),
                mcp,
                Err(vec![Mismatch::State {
                    found: "BUS-OFF".to_owned(),
                }]),
            ),
            (
                "error-passive still carries the bus (frames unacknowledged while the drives were off)",
                report(set(
                    &["linkinfo", "info_data", "state"],
                    json!("ERROR-PASSIVE"),
                )),
                mcp,
                Ok(passed("ERROR-PASSIVE")),
            ),
            (
                "listen-only and presume-ack",
                report(set(
                    &["linkinfo", "info_data", "ctrlmode"],
                    json!(["LISTEN-ONLY", "BERR-REPORTING", "PRESUME-ACK"]),
                )),
                mcp,
                Err(vec![
                    Mismatch::Mode {
                        mode: "LISTEN-ONLY".to_owned(),
                    },
                    Mismatch::Mode {
                        mode: "PRESUME-ACK".to_owned(),
                    },
                ]),
            ),
            (
                "loopback",
                report(set(
                    &["linkinfo", "info_data", "ctrlmode"],
                    json!(["LOOPBACK"]),
                )),
                mcp,
                Err(vec![Mismatch::Mode {
                    mode: "LOOPBACK".to_owned(),
                }]),
            ),
            (
                "not CAN",
                report(set(&["linkinfo"], Value::Null)),
                None,
                Err(vec![Mismatch::NotCan { kind: None }]),
            ),
        ];
        for (name, json, driver, want) in rows {
            let got = match check(&json, driver, &spec()) {
                Ok(Interface::Real(real)) => Some(Ok(real)),
                Err(Refusal::Mismatch(found)) => Some(Err(found)),
                Ok(Interface::Sim) | Err(Refusal::Unreadable(_)) => None,
            };
            if let Some(Ok(real)) = &got {
                assert_eq!(
                    real.starts_error_passive(),
                    real.state == "ERROR-PASSIVE",
                    "{name}: starts unhealthy only error-passive"
                );
            }
            assert_eq!(got, Some(want), "{name}");
        }
        // Modes in a shape that can't be read can't be checked, so the interface isn't opened.
        assert_eq!(
            check(
                &report(set(
                    &["linkinfo", "info_data", "ctrlmode"],
                    json!("LOOPBACK")
                )),
                mcp,
                &spec()
            ),
            Err(Refusal::Unreadable(
                "ip's ctrlmode isn't a list of names: \"LOOPBACK\"".to_owned()
            ))
        );
        // The simulator's bus is taken as it is: no driver, no bit timing.
        let vcan = serde_json::json!([{ "ifname": "can1", "flags": ["NOARP", "UP", "LOWER_UP"],
            "linkinfo": { "info_kind": "vcan" } }]);
        assert_eq!(check(&vcan.to_string(), None, &spec()), Ok(Interface::Sim));
        // A report that can't be read opens nothing.
        assert!(matches!(
            check("", mcp, &spec()),
            Err(Refusal::Unreadable(_))
        ));
    }
}
