#![doc = include_str!("../README.md")]

#[cfg_attr(
    not(target_os = "linux"),
    expect(
        dead_code,
        reason = "only the Linux main writes files; the tests still run everywhere"
    )
)]
mod files;

#[cfg(target_os = "linux")]
fn main() -> std::process::ExitCode {
    linux::main()
}

#[cfg(not(target_os = "linux"))]
fn main() -> std::process::ExitCode {
    // SocketCAN and candump are Linux only (CLAUDE.md: Linux work goes to the dev box).
    std::process::ExitCode::from(2)
}

#[cfg(target_os = "linux")]
mod linux {
    use std::io::{BufRead as _, BufReader, Write as _};
    use std::path::PathBuf;
    use std::process::{Child, Command, ExitCode, Stdio};
    use std::sync::mpsc::{Receiver, RecvTimeoutError, sync_channel};
    use std::time::{Duration, Instant, SystemTime};

    use nix::sys::signal::{SigSet, Signal, kill};
    use nix::unistd::Pid;

    use crate::files::{Closed, Rotator, prune};

    const USAGE: &str = "usage: candump-rotate --bus <if> --dir <dir> --cut-secs <n> --keep-days <n> -- <command> [<arg>...]";
    /// How often what has been written is pushed to the file as a complete zstd block: a crash loses at most this much.
    const FLUSH_EVERY: Duration = Duration::from_secs(1);
    /// Lines read from the command but not yet written. About 4 MB of `candump -L` text, several seconds of a busy bus:
    /// enough to ride out a slow disk. When it is full the reader waits, the pipe fills, candump waits, and the kernel
    /// counts what it drops, which candump writes to the log (`-d`).
    const QUEUE_LINES: usize = 65_536;

    fn say(line: &str) {
        let _ = writeln!(std::io::stderr(), "candump-rotate: {line}");
    }

    struct Args {
        bus: String,
        dir: PathBuf,
        cut: Duration,
        keep: Duration,
        command: Vec<String>,
    }

    fn args() -> Result<Args, String> {
        let mut it = std::env::args().skip(1);
        let (mut bus, mut dir, mut cut, mut keep) = (None, None, None, None);
        while let Some(flag) = it.next() {
            if flag == "--" {
                break;
            }
            let value = it.next().ok_or(format!("{flag} needs a value"))?;
            let number = |v: &str| {
                v.parse::<u64>()
                    .ok()
                    .filter(|n| *n > 0)
                    .ok_or(format!("{flag} must be a whole number above 0"))
            };
            match flag.as_str() {
                "--bus" => bus = Some(value),
                "--dir" => dir = Some(PathBuf::from(value)),
                "--cut-secs" => cut = Some(Duration::from_secs(number(&value)?)),
                "--keep-days" => {
                    let secs = number(&value)?
                        .checked_mul(86_400)
                        .ok_or(format!("{flag} is too large"))?;
                    keep = Some(Duration::from_secs(secs));
                }
                other => return Err(format!("unknown argument {other}; {USAGE}")),
            }
        }
        let command: Vec<String> = it.collect();
        let need = |what: &str| format!("{what} is required; {USAGE}");
        let bus = bus.ok_or_else(|| need("--bus"))?;
        // The bus names a file; a name that could leave the directory is refused.
        if bus.is_empty() || bus.contains('/') || bus.starts_with('.') {
            return Err(format!("--bus {bus:?} is not an interface name"));
        }
        if command.is_empty() {
            return Err(need("a command after --"));
        }
        Ok(Args {
            bus,
            dir: dir.ok_or_else(|| need("--dir"))?,
            cut: cut.ok_or_else(|| need("--cut-secs"))?,
            keep: keep.ok_or_else(|| need("--keep-days"))?,
            command,
        })
    }

    fn report_prune(args: &Args, open: Option<&std::path::Path>) {
        let (deleted, error) = prune(&args.dir, &args.bus, args.keep, SystemTime::now(), open);
        for path in deleted {
            say(&format!("{}: pruned {}", args.bus, path.display()));
        }
        if let Some(e) = error {
            say(&format!(
                "{}: pruning {}: {e}",
                args.bus,
                args.dir.display()
            ));
        }
    }

    /// Report a closed file, then prune, sparing the file now open.
    fn report_closed(args: &Args, closed: Option<Closed>, open: Option<&std::path::Path>) {
        if let Some(c) = closed {
            say(&format!(
                "{}: closed {}, {} lines",
                args.bus,
                c.path.display(),
                c.lines
            ));
            report_prune(args, open);
        }
    }

    /// Read the command's output a line at a time into the queue until it ends.
    fn read_lines(child: &mut Child) -> Result<Receiver<Vec<u8>>, String> {
        let stdout = child.stdout.take().ok_or("the command has no stdout")?;
        let (tx, rx) = sync_channel(QUEUE_LINES);
        std::thread::Builder::new()
            .name("read".to_owned())
            .spawn(move || {
                let mut reader = BufReader::with_capacity(1 << 16, stdout);
                loop {
                    let mut line = Vec::with_capacity(96);
                    match reader.read_until(b'\n', &mut line) {
                        Ok(0) => break,
                        Ok(_) => {
                            if tx.send(line).is_err() {
                                break;
                            }
                        }
                        Err(e) => {
                            say(&format!("reading the command's output: {e}"));
                            break;
                        }
                    }
                }
            })
            .map_err(|e| format!("can't start the reader: {e}"))?;
        Ok(rx)
    }

    /// SIGTERM, SIGINT and SIGHUP are passed on to the command, and this process ends when the command's output does,
    /// with its last file closed cleanly. Under systemd the command gets the signal itself too; passing it on covers a
    /// signal sent to this process alone.
    fn forward_signals(child: &Child, signals: SigSet) -> Result<(), String> {
        let pid = i32::try_from(child.id())
            .map(Pid::from_raw)
            .map_err(|e| format!("command pid: {e}"))?;
        std::thread::Builder::new()
            .name("signals".to_owned())
            .spawn(move || {
                while let Ok(signal) = signals.wait() {
                    // The command may already have ended; then there is nothing to pass on.
                    let _ = kill(pid, signal);
                }
            })
            .map_err(|e| format!("can't start the signal thread: {e}"))?;
        Ok(())
    }

    /// Write every line to the rotating files until the command's output ends or a write fails.
    fn write_lines(args: &Args, rx: &Receiver<Vec<u8>>) -> Result<(), String> {
        let mut rotator = Rotator::new(args.dir.clone(), args.bus.clone(), args.cut);
        let failed =
            |e: std::io::Error| format!("{}: writing {}: {e}", args.bus, args.dir.display());
        let mut next_tick = Instant::now() + FLUSH_EVERY;
        loop {
            let wait = next_tick.saturating_duration_since(Instant::now());
            match rx.recv_timeout(wait) {
                Ok(line) => {
                    let closed = rotator
                        .line(&line, SystemTime::now(), Instant::now())
                        .map_err(failed)?;
                    report_closed(args, closed, rotator.current());
                }
                Err(RecvTimeoutError::Timeout) => {}
                Err(RecvTimeoutError::Disconnected) => break,
            }
            let now = Instant::now();
            if now >= next_tick {
                let closed = rotator.tick(now).map_err(failed)?;
                report_closed(args, closed, rotator.current());
                next_tick = now + FLUSH_EVERY;
            }
        }
        let closed = rotator.close().map_err(failed)?;
        report_closed(args, closed, rotator.current());
        Ok(())
    }

    pub(super) fn main() -> ExitCode {
        let args = match args() {
            Ok(args) => args,
            Err(e) => {
                say(&e);
                return ExitCode::from(2);
            }
        };
        say(&format!(
            "build {}; {} to {}, cut every {} s, kept {} days: {}",
            env!("ROARK_GIT_REVISION"),
            args.bus,
            args.dir.display(),
            args.cut.as_secs(),
            args.keep.as_secs() / 86_400,
            args.command.join(" ")
        ));
        if let Err(e) = std::fs::create_dir_all(&args.dir) {
            say(&format!("can't make {}: {e}", args.dir.display()));
            return ExitCode::from(2);
        }
        report_prune(&args, None);

        // The command starts before the signals are blocked, so it doesn't inherit the block; every thread started
        // after the block does, and only the signal thread takes them.
        let Some((program, rest)) = args.command.split_first() else {
            return ExitCode::from(2);
        };
        let mut child = match Command::new(program)
            .args(rest)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(e) => {
                say(&format!("can't start {program}: {e}"));
                return ExitCode::from(2);
            }
        };
        let mut signals = SigSet::empty();
        for s in [Signal::SIGTERM, Signal::SIGINT, Signal::SIGHUP] {
            signals.add(s);
        }
        let started = signals
            .thread_block()
            .map_err(|e| format!("can't block signals: {e}"))
            .and_then(|()| forward_signals(&child, signals))
            .and_then(|()| read_lines(&mut child));
        let written = started.and_then(|rx| write_lines(&args, &rx));
        if let Err(e) = &written {
            say(e);
            // Fails only if the command has already ended, which is what this is for.
            let _ = child.kill();
        }
        let status = child.wait();
        say(&format!("{}: {program} ended: {status:?}", args.bus));
        if written.is_ok() && status.is_ok_and(|s| s.success()) {
            ExitCode::SUCCESS
        } else {
            ExitCode::FAILURE
        }
    }
}
