//! The `robot-cli` binary. For now one command:
//!
//! `robot-cli disable [--skeleton <file>] [--lock <file>] [--json]`: Disable, then active reporting off, to every
//! drive the skeleton wires to a bus, each bus on its own socket and thread. Refuses while the runtime holds its lock,
//! or when it can't tell whether it does. Prints one line per drive to stdout, or one JSON document with `--json`.
//! Exit 0 when every drive is stopped or silent; 1 when any drive needs a person; 2
//! when it refused or couldn't start.

#[cfg(target_os = "linux")]
fn main() -> std::process::ExitCode {
    linux::main()
}

#[cfg(not(target_os = "linux"))]
fn main() -> std::process::ExitCode {
    // SocketCAN is Linux only (CLAUDE.md: Linux work goes to the dev box).
    std::process::ExitCode::from(2)
}

#[cfg(target_os = "linux")]
mod linux {
    use std::io::Write as _;
    use std::path::PathBuf;
    use std::process::ExitCode;
    use std::time::Duration;

    use robot_cli::stop::BusFault;
    use robot_cli::{BusReport, LOCK_PATH, LockError, claim, disable, targets};
    use serde_json::{Value, json};

    const USAGE: &str = "usage: robot-cli disable [--skeleton <file>] [--lock <file>] [--json]";
    const REFUSED: u8 = 2;
    const REVISION: &str = env!("ROARK_GIT_REVISION");

    fn say(line: &str) {
        let _ = writeln!(std::io::stderr(), "robot-cli: {line}");
    }

    fn out(line: &str) {
        let _ = writeln!(std::io::stdout(), "{line}");
    }

    struct Args {
        skeleton: PathBuf,
        lock: PathBuf,
        json: bool,
    }

    fn args() -> Result<Args, String> {
        let mut it = std::env::args().skip(1);
        match it.next().as_deref() {
            Some("disable") => {}
            Some(other) => return Err(format!("unknown command {other}; {USAGE}")),
            None => return Err(USAGE.to_owned()),
        }
        let mut args = Args {
            skeleton: PathBuf::from("config/skeleton.yaml"),
            lock: PathBuf::from(LOCK_PATH),
            json: false,
        };
        while let Some(flag) = it.next() {
            let mut value = || it.next().ok_or(format!("{flag} needs a value"));
            match flag.as_str() {
                "--skeleton" => args.skeleton = PathBuf::from(value()?),
                "--lock" => args.lock = PathBuf::from(value()?),
                "--json" => args.json = true,
                other => return Err(format!("unknown argument {other}; {USAGE}")),
            }
        }
        Ok(args)
    }

    fn ms(at: Option<Duration>) -> String {
        at.map_or_else(
            || "-".to_owned(),
            |d| format!("{:.1} ms", d.as_secs_f64() * 1e3),
        )
    }

    fn ms_json(at: Option<Duration>) -> Value {
        at.map_or(Value::Null, |d| json!(d.as_secs_f64() * 1e3))
    }

    fn print(report: &BusReport) {
        if let Some(fault) = &report.fault {
            out(&format!("{}: FAILED: {fault}", report.bus));
        }
        if report.error_frames > 0 {
            let off = if report.bus_off {
                ", bus-off among them"
            } else {
                ""
            };
            out(&format!(
                "{}: {} error frames{off}",
                report.bus, report.error_frames
            ));
        }
        if let (Some(e), Some(fault)) = (report.read_fault, report.fault)
            && !matches!(fault, BusFault::Read(_))
        {
            out(&format!("{}: reads had failed first: {e}", report.bus));
        }
        if let Some(e) = report.errors_unseen {
            out(&format!(
                "{}: error frames can't be read ({e}), so a bus-off wouldn't be seen",
                report.bus
            ));
        }
        for d in &report.drives {
            let r = &d.record;
            out(&format!(
                "{} {} {}: {}; {} Disables, Reset read at {}, {} reporting off, last at {}",
                report.bus,
                r.id.get(),
                d.joint,
                d.outcome,
                r.disables,
                ms(r.reset),
                r.reporting_offs,
                ms(r.reporting_off),
            ));
        }
    }

    fn to_json(report: &BusReport) -> Value {
        json!({
            "bus": report.bus,
            "fault": report.fault.map(|f| json!({"kind": f.name(), "detail": f.to_string()})),
            "error_frames": report.error_frames,
            "bus_off": report.bus_off,
            "errors_unseen": report.errors_unseen.map(|e| e.to_string()),
            "read_fault": report.read_fault.map(|e| e.to_string()),
            "drives": report.drives.iter().map(|d| json!({
                "id": d.record.id.get(),
                "joint": d.joint,
                "outcome": d.outcome.name(),
                "ok": d.outcome.ok(),
                "disables": d.record.disables,
                "reset_ms": ms_json(d.record.reset),
                "reporting_offs": d.record.reporting_offs,
                "reporting_off_ms": ms_json(d.record.reporting_off),
            })).collect::<Vec<_>>(),
        })
    }

    pub(super) fn main() -> ExitCode {
        let args = match args() {
            Ok(a) => a,
            Err(e) => {
                say(&e);
                return ExitCode::from(REFUSED);
            }
        };
        say(&format!("build {REVISION}"));
        // Held until the process ends, so a runtime using this path can't start while the Disables go out (unless the
        // file is missing, below).
        let _claim = match claim(&args.lock) {
            Ok(c) => Some(c),
            Err(e @ LockError::Held(_)) => {
                say(&format!(
                    "{e}; refusing (stop the runtime with systemctl, which runs this after it exits)"
                ));
                return ExitCode::from(REFUSED);
            }
            Err(e @ LockError::Unknown { .. }) => {
                say(&format!(
                    "{e}; can't tell whether a runtime holds it, refusing"
                ));
                return ExitCode::from(REFUSED);
            }
            // No runtime using this path is running, so nothing else is on the bus now. One started during the stop
            // would make the file and take its lock unopposed. Under systemd the file exists through ExecStopPost and
            // the gap before an automatic restart (RuntimeDirectoryPreserve=restart), so only a start by hand can.
            Err(e @ LockError::Missing(_)) => {
                say(&format!("{e}; going on"));
                None
            }
        };
        let skeleton = match skeleton::load(&args.skeleton) {
            Ok(s) => s,
            Err(e) => {
                say(&format!(
                    "{}: {e}; nothing sent (the drives still go limp 50 ms after their last command)",
                    args.skeleton.display()
                ));
                return ExitCode::from(REFUSED);
            }
        };
        let targets = targets(&skeleton);
        if targets.is_empty() {
            say("no joint is wired to a bus; nothing to send");
        }
        let reports = disable(&targets);
        let failed = reports
            .iter()
            .flat_map(|r| &r.drives)
            .filter(|d| !d.outcome.ok())
            .count();
        let total: usize = reports.iter().map(|r| r.drives.len()).sum();
        if args.json {
            let doc = json!({
                "build": REVISION,
                "buses": reports.iter().map(to_json).collect::<Vec<_>>(),
                "need_a_person": failed,
                "drive_count": total,
            });
            out(&doc.to_string());
        } else {
            for r in &reports {
                print(r);
            }
            out(&format!(
                "disable: {failed} of {total} drives need a person"
            ));
        }
        if reports.iter().all(BusReport::ok) {
            ExitCode::SUCCESS
        } else {
            ExitCode::FAILURE
        }
    }
}
