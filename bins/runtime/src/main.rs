//! The `runtime` binary: `runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>] [--lock <file>]`. Takes its lock
//! first and refuses to start if it is held, then runs until SIGINT or SIGTERM, or until the run ends on its own (a
//! clock error or a bus thread that ended), then stops every limb, waits for the buses to confirm, and closes the
//! session.

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
    use std::fs::{File, OpenOptions};
    use std::io::Write as _;
    use std::path::{Path, PathBuf};
    use std::process::ExitCode;
    use std::sync::Arc;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::time::Duration;

    use can::LimbState;
    use nix::errno::Errno;
    use nix::fcntl::{Flock, FlockArg};
    use nix::sys::signal::{SigSet, Signal, kill};
    use nix::unistd::getpid;
    use runtime::{Runtime, RuntimeConfig, RuntimeExit};

    /// Write one line to stderr, which journald keeps; the logger thread comes with `api` (logging.md).
    fn say(line: &str) {
        let _ = writeln!(std::io::stderr(), "runtime: {line}");
    }

    /// The lock this process holds for as long as it runs, in the `RuntimeDirectory` systemd makes
    /// (conventions/deploy.md section 2). `robot-cli disable` takes the same lock (its `LOCK_PATH`) and refuses while it
    /// is held, so the independent stop never sends while a runtime is alive; a second runtime is refused the same way,
    /// so two never write to one bus. The kernel drops the lock when this process dies, by `kill -9` too.
    const LOCK_PATH: &str = "/run/robot/runtime.lock";

    const USAGE: &str =
        "usage: runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>] [--lock <file>]";

    /// Take the lock at `path` without waiting. It is never released before the process ends: leaked, so no drop can
    /// let it go early.
    fn lock(path: &Path) -> Result<(), String> {
        let file: File = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)
            .map_err(|e| format!("can't open the lock {}: {e}", path.display()))?;
        match Flock::lock(file, FlockArg::LockExclusiveNonblock) {
            Ok(lock) => {
                Box::leak(Box::new(lock));
                Ok(())
            }
            Err((_, Errno::EWOULDBLOCK)) => Err(format!(
                "{} is held: another runtime, or robot-cli disable, is running",
                path.display()
            )),
            Err((_, e)) => Err(format!("can't take the lock {}: {e}", path.display())),
        }
    }

    fn args() -> Result<(RuntimeConfig, PathBuf), String> {
        let mut config = RuntimeConfig {
            skeleton: PathBuf::from("config/skeleton.yaml"),
            sessions: PathBuf::from("/var/lib/robot/sessions"),
            hz: 250,
            operator: std::env::var("USER").unwrap_or_else(|_| "unknown".to_owned()),
            git_revision: env!("ROARK_GIT_REVISION").to_owned(),
            // Nothing in the binary reads them until the `api` does.
            views: false,
        };
        let mut lock = PathBuf::from(LOCK_PATH);
        let mut it = std::env::args().skip(1);
        while let Some(flag) = it.next() {
            let mut value = || it.next().ok_or(format!("{flag} needs a value"));
            match flag.as_str() {
                "--lock" => lock = PathBuf::from(value()?),
                "--skeleton" => config.skeleton = PathBuf::from(value()?),
                "--sessions" => config.sessions = PathBuf::from(value()?),
                "--hz" => config.hz = value()?.parse().map_err(|e| format!("--hz: {e}"))?,
                other => return Err(format!("unknown argument {other}; {USAGE}")),
            }
        }
        Ok((config, lock))
    }

    /// What was checked at startup (logging.md section 4).
    fn startup(runtime: &Runtime, config: &RuntimeConfig) {
        let info = runtime.info();
        say(&format!(
            "build {}; skeleton {} sha256 {}; {} Hz; session {}",
            config.git_revision,
            info.skeleton.path,
            info.skeleton.sha256,
            config.hz,
            info.session.display()
        ));
        for ((p, socket), rcvbuf) in info
            .plans
            .iter()
            .zip(&info.sockets)
            .zip(&info.receive_buffer_bytes)
        {
            let joints: Vec<&str> = p.joints.iter().map(skeleton::JointName::as_str).collect();
            say(&format!(
                "{}: {} bit/s, {:?} timestamps, receive filters {}, error filter {:#010x}, receive buffer {rcvbuf} bytes, \
                 joints {}",
                p.name,
                socket.bitrate,
                socket.timestamps,
                if socket.receive_filters.is_empty() {
                    "none (every ID)".to_owned()
                } else {
                    format!("{:?}", socket.receive_filters)
                },
                socket.error_filter,
                joints.join(" ")
            ));
        }
        let offline: Vec<&str> = info
            .offline
            .iter()
            .map(skeleton::JointName::as_str)
            .collect();
        say(&format!(
            "offline: {}; nothing enabled",
            if offline.is_empty() {
                "none".to_owned()
            } else {
                offline.join(" ")
            }
        ));
    }

    /// Raise SIGUSR1 once the run has ended on its own, so the signal wait wakes for it too.
    fn watch(finished: Arc<AtomicBool>) -> std::io::Result<()> {
        std::thread::Builder::new()
            .name("watch".to_owned())
            .spawn(move || {
                while !finished.load(Ordering::Acquire) {
                    pause();
                }
                if let Err(e) = kill(getpid(), Signal::SIGUSR1) {
                    say(&format!(
                        "can't wake the main thread ({e}); stop it with SIGTERM"
                    ));
                }
            })
            .map(drop)
    }

    #[expect(
        clippy::disallowed_methods,
        reason = "the watcher is off the realtime path; a run that ends on its own is noticed within 50 ms"
    )]
    fn pause() {
        std::thread::sleep(Duration::from_millis(50));
    }

    /// Log how the run ended; true when it ended cleanly, every bus at rest.
    fn report(exit: &RuntimeExit) -> bool {
        let c = &exit.control;
        let mut clean = c.error.is_none() && c.bus_ended.is_none();
        if let Some(e) = &c.error {
            say(&format!("control lost its clock: {e}"));
        }
        if let Some(bus) = c.bus_ended.and_then(|b| exit.buses.get(b)) {
            say(&format!("{} ended before the run did", bus.name));
        }
        say(&format!(
            "control: {} stale, {} skipped ticks, {} late batches; dropped {} batches, {} replies, {} views; {} stops \
             deferred; {} clears and {} enables refused while ending; {} stray slow results; {} limbs stopped for \
             host.mode; {} holds ended by a stop",
            c.stale_ticks,
            c.skipped_ticks,
            c.late_batches,
            c.batches_dropped,
            c.replies_dropped,
            c.views_dropped,
            c.stops_deferred,
            c.clears_ending,
            c.enables_ending,
            c.stray_results,
            c.mode_stops,
            c.holds_ended
        ));
        for bus in &exit.buses {
            if let Some(e) = &bus.error {
                say(&format!("{}: {e}", bus.name));
                clean = false;
            }
            match bus.last {
                // Ended before its first tick (a stop asked during the start): nothing ran.
                None => say(&format!("{}: ended before its first tick", bus.name)),
                // A limb never enabled is idle at the end; every other is stopped.
                Some(s)
                    if s.limbs()
                        .all(|(_, l)| matches!(l.state, LimbState::Idle | LimbState::Stopped)) => {}
                Some(_) => {
                    say(&format!("{}: ended with a limb not stopped", bus.name));
                    clean = false;
                }
            }
        }
        clean
    }

    /// The panic hook: the message (which may span lines) to fd 2, formatted on the stack and written with one `write`, so it takes no lock (a
    /// thread that panicked holding stderr's lock can't hang it) and allocates nothing (rust.md section 4). A message
    /// longer than the buffer is cut.
    fn panic_line(info: &std::panic::PanicHookInfo<'_>) {
        let mut buf = [0u8; 1024];
        let mut cursor = std::io::Cursor::new(&mut buf[..]);
        let thread = std::thread::current();
        // Full is fine: the line is cut, and the write below takes what fitted.
        let _ = writeln!(
            cursor,
            "runtime: panic in thread {}: {info}",
            thread.name().unwrap_or("unnamed")
        );
        let end = usize::try_from(cursor.position()).unwrap_or(0);
        if let Some(line) = buf.get(..end) {
            // Nothing to do if stderr is gone: the abort follows either way.
            let _ = nix::unistd::write(std::io::stderr(), line);
        }
    }

    pub(super) fn main() -> ExitCode {
        // Panics abort the process (Cargo.toml, rust.md section 4); the hook makes sure the reason reaches the journal
        // first, once, naming the thread. The drives go limp 50 ms after the last command (`drive.can_timeout`).
        std::panic::set_hook(Box::new(panic_line));
        let (config, lock_path) = match args() {
            Ok(c) => c,
            Err(e) => {
                say(&e);
                return ExitCode::FAILURE;
            }
        };
        // Before any socket opens: a runtime that can't hold the lock never sends.
        if let Err(e) = lock(&lock_path) {
            say(&e);
            return ExitCode::FAILURE;
        }
        // Blocked before any thread starts, so every thread inherits the mask and only the wait below takes them.
        // SIGUSR1 is the watcher's (the run ended on its own); one from elsewhere is a request to end like the others.
        let mut signals = SigSet::empty();
        signals.add(Signal::SIGINT);
        signals.add(Signal::SIGTERM);
        signals.add(Signal::SIGUSR1);
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
        startup(&runtime, &config);
        // Without the watcher a run that ends on its own goes unnoticed until a signal: end now rather than run blind.
        let mut clean = true;
        let finished = runtime.finished();
        if let Err(e) = watch(Arc::clone(&finished)) {
            say(&format!("can't start the watcher ({e}): ending"));
            clean = false;
        } else {
            match signals.wait() {
                // The watcher's, unless someone else sent it: then it is a request to end like the others.
                Ok(Signal::SIGUSR1) if finished.load(Ordering::Acquire) => {
                    say("the run ended on its own: ending");
                    clean = false;
                }
                Ok(signal) => say(&format!("{signal}: ending")),
                Err(e) => {
                    say(&format!("signal wait failed ({e}): ending"));
                    clean = false;
                }
            }
        }
        match runtime.end() {
            Ok(exit) => {
                if report(&exit) && clean {
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
