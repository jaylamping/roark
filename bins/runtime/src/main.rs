//! The `runtime` binary: `runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>]`. Runs until SIGINT or SIGTERM,
//! then stops every limb, waits for the buses to confirm, and closes the session.

#[cfg(target_os = "linux")]
fn main() -> std::process::ExitCode {
    linux::main()
}

#[cfg(not(target_os = "linux"))]
fn main() -> std::process::ExitCode {
    // SocketCAN is Linux only (CLAUDE.md: Linux work goes to the dev box).
    std::process::ExitCode::FAILURE
}

#[cfg(target_os = "linux")]
mod linux {
    use std::io::Write as _;
    use std::path::PathBuf;
    use std::process::ExitCode;

    use can::LimbState;
    use nix::sys::signal::{SigSet, Signal};
    use runtime::{Runtime, RuntimeConfig};

    /// Write one line to stderr, which journald keeps; the logger thread comes with `api` (logging.md).
    fn say(line: &str) {
        let _ = writeln!(std::io::stderr(), "runtime: {line}");
    }

    fn args() -> Result<RuntimeConfig, String> {
        let mut config = RuntimeConfig {
            skeleton: PathBuf::from("config/skeleton.yaml"),
            sessions: PathBuf::from("/var/lib/robot/sessions"),
            hz: 250,
            operator: std::env::var("USER").unwrap_or_else(|_| "unknown".to_owned()),
            git_revision: option_env!("ROARK_GIT_REVISION")
                .unwrap_or("unknown")
                .to_owned(),
        };
        let mut it = std::env::args().skip(1);
        while let Some(flag) = it.next() {
            let mut value = || it.next().ok_or(format!("{flag} needs a value"));
            match flag.as_str() {
                "--skeleton" => config.skeleton = PathBuf::from(value()?),
                "--sessions" => config.sessions = PathBuf::from(value()?),
                "--hz" => config.hz = value()?.parse().map_err(|e| format!("--hz: {e}"))?,
                other => {
                    return Err(format!(
                        "unknown argument {other}; usage: runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>]"
                    ));
                }
            }
        }
        Ok(config)
    }

    pub(super) fn main() -> ExitCode {
        // Panics abort the process (Cargo.toml, rust.md section 4); the hook makes sure the reason reaches the journal
        // first. The drives go limp 50 ms after the last command (`drive.can_timeout`).
        let default = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            say(&format!("panic: {info}"));
            default(info);
        }));
        let config = match args() {
            Ok(c) => c,
            Err(e) => {
                say(&e);
                return ExitCode::FAILURE;
            }
        };
        // Blocked before any thread starts, so every thread inherits the mask and only the wait below takes them.
        let mut signals = SigSet::empty();
        signals.add(Signal::SIGINT);
        signals.add(Signal::SIGTERM);
        if let Err(e) = signals.thread_block() {
            say(&format!("can't block signals: {e}"));
            return ExitCode::FAILURE;
        }
        let runtime = match Runtime::start(&config) {
            Ok(r) => r,
            Err(e) => {
                say(&e.to_string());
                return ExitCode::FAILURE;
            }
        };
        say(&format!(
            "running {} bus(es) at {} Hz; session {}; nothing enabled",
            runtime.plans().len(),
            config.hz,
            runtime.session().display()
        ));
        match signals.wait() {
            Ok(signal) => say(&format!("{signal}: stopping")),
            Err(e) => say(&format!("signal wait failed ({e}): stopping")),
        }
        match runtime.stop() {
            Ok(exit) => {
                let mut clean = exit.control.error.is_none();
                for bus in &exit.buses {
                    if let Some(e) = &bus.error {
                        say(&format!("{}: {e}", bus.name));
                        clean = false;
                    }
                    // A limb never enabled is idle at the end; every other is stopped.
                    let at_rest = bus.last.is_some_and(|s| {
                        s.limbs()
                            .all(|(_, l)| matches!(l.state, LimbState::Idle | LimbState::Stopped))
                    });
                    if !at_rest {
                        say(&format!("{}: ended with a limb not stopped", bus.name));
                        clean = false;
                    }
                }
                if clean {
                    ExitCode::SUCCESS
                } else {
                    ExitCode::FAILURE
                }
            }
            Err(e) => {
                say(&e.to_string());
                ExitCode::FAILURE
            }
        }
    }
}
