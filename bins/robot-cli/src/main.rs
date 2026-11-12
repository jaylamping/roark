//! The `robot-cli` binary. For now one command:
//!
//! `robot-cli disable [--skeleton <file>] [--lock <file>]`: Disable, then active reporting off, to every drive the
//! skeleton wires to a bus, each bus on its own socket and thread. Refuses while the runtime holds its lock. Prints one
//! line per drive to stdout. Exit 0 when every drive was read in Reset or never answered; 1 when any drive needs a
//! person (a bus failed, a drive answered but never in Reset, or still reports); 2 when it refused or couldn't start.

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

    use robot_cli::stop::Outcome;
    use robot_cli::{BusReport, LOCK_PATH, LockError, claim, disable, targets};

    const USAGE: &str = "usage: robot-cli disable [--skeleton <file>] [--lock <file>]";
    const REFUSED: u8 = 2;

    fn say(line: &str) {
        let _ = writeln!(std::io::stderr(), "robot-cli: {line}");
    }

    fn out(line: &str) {
        let _ = writeln!(std::io::stdout(), "{line}");
    }

    struct Args {
        skeleton: PathBuf,
        lock: PathBuf,
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
        };
        while let Some(flag) = it.next() {
            let mut value = || it.next().ok_or(format!("{flag} needs a value"));
            match flag.as_str() {
                "--skeleton" => args.skeleton = PathBuf::from(value()?),
                "--lock" => args.lock = PathBuf::from(value()?),
                other => return Err(format!("unknown argument {other}; {USAGE}")),
            }
        }
        Ok(args)
    }

    fn ms(ns: Option<u64>) -> String {
        #[expect(
            clippy::cast_precision_loss,
            reason = "a display of times under a second"
        )]
        ns.map_or_else(|| "-".to_owned(), |ns| format!("{:.1} ms", ns as f64 / 1e6))
    }

    fn print(report: &BusReport) {
        if let Some(e) = &report.failure {
            out(&format!("{}: FAILED: {e}", report.bus));
        }
        for (name, d, outcome) in &report.drives {
            let what = match outcome {
                Outcome::Stopped => "stopped".to_owned(),
                Outcome::Silent => "silent (never answered)".to_owned(),
                Outcome::NotReset => "FAILED: answered, never in Reset".to_owned(),
                Outcome::StillReporting => "FAILED: still reporting after reporting off".to_owned(),
                Outcome::NotSent(why) => format!("FAILED: {why}"),
            };
            out(&format!(
                "{} {} {name}: {what}; {} Disables, Reset read at {}, {} reporting off, last at {}",
                report.bus,
                d.id.get(),
                d.disables,
                ms(d.reset_ns),
                d.reporting_offs,
                ms(d.reporting_off_ns),
            ));
        }
    }

    pub(super) fn main() -> ExitCode {
        let args = match args() {
            Ok(a) => a,
            Err(e) => {
                say(&e);
                return ExitCode::from(REFUSED);
            }
        };
        // Held until the process ends, so a runtime can't start while the Disables go out.
        let _claim = match claim(&args.lock) {
            Ok(c) => Some(c),
            Err(e @ LockError::Held(_)) => {
                say(&format!(
                    "{e}; refusing (stop the runtime with systemctl, which runs this after it exits)"
                ));
                return ExitCode::from(REFUSED);
            }
            // No runtime made the lock, or it can't be checked: a Disable is never the unsafe direction, so go on.
            Err(e) => {
                say(&format!("{e}; going on without the lock"));
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
            return ExitCode::SUCCESS;
        }
        let reports = disable(&targets);
        for r in &reports {
            print(r);
        }
        let failed = reports
            .iter()
            .flat_map(|r| &r.drives)
            .filter(|(_, _, o)| !o.ok())
            .count();
        let total: usize = reports.iter().map(|r| r.drives.len()).sum();
        out(&format!(
            "disable: {failed} of {total} drives need a person"
        ));
        if failed == 0 {
            ExitCode::SUCCESS
        } else {
            ExitCode::FAILURE
        }
    }
}
