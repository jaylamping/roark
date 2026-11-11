#![doc = include_str!("../README.md")]

#[cfg(target_os = "linux")]
mod frames;
#[cfg(target_os = "linux")]
mod host;
#[cfg(target_os = "linux")]
mod link;
#[cfg(target_os = "linux")]
mod respond;
#[cfg(target_os = "linux")]
mod stats;

#[cfg(target_os = "linux")]
fn main() -> Result<(), String> {
    use std::io::Write;
    use std::path::PathBuf;

    const USAGE: &str = "usage: can-bench host --bus <if> [--hz 250] [--slots 6] [--seconds 3600] \
                         [--deadline-pct 60, 1 to 89] --out <dir> | can-bench respond --bus <if> [--slots 6]";

    let mut it = std::env::args().skip(1);
    let mode = it.next().ok_or(USAGE)?;
    let mut args = host::HostArgs {
        bus: String::new(),
        hz: 250,
        slots: 6,
        seconds: 3600,
        deadline_pct: 60,
        out: PathBuf::new(),
    };
    while let Some(flag) = it.next() {
        let value = it.next().ok_or(format!("{flag} needs a value"))?;
        let bad = |e: std::num::ParseIntError| format!("{flag}: {e}");
        match flag.as_str() {
            "--bus" => args.bus = value,
            "--hz" => args.hz = value.parse().map_err(bad)?,
            "--slots" => args.slots = value.parse().map_err(bad)?,
            "--seconds" => args.seconds = value.parse().map_err(bad)?,
            "--deadline-pct" => args.deadline_pct = value.parse().map_err(bad)?,
            "--out" => args.out = PathBuf::from(value),
            other => return Err(format!("unknown argument {other}; {USAGE}")),
        }
    }
    if args.bus.is_empty() {
        return Err(format!("--bus is required; {USAGE}"));
    }
    match mode.as_str() {
        "host" => {
            if args.out.as_os_str().is_empty() {
                return Err(format!("--out is required; {USAGE}"));
            }
            let (summary, pass) = host::run(&args)?;
            std::io::stdout()
                .write_all(summary.as_bytes())
                .map_err(|e| e.to_string())?;
            // A run below the pass mark exits non-zero, so a script can tell; the reasons are the summary's last line.
            if pass {
                Ok(())
            } else {
                Err("below the pass mark".to_owned())
            }
        }
        "respond" => respond::run(&args.bus, args.slots),
        other => Err(format!("unknown mode {other}; {USAGE}")),
    }
}

#[cfg(not(target_os = "linux"))]
fn main() -> Result<(), String> {
    Err("can-bench runs only on Linux, where SocketCAN exists; see docs/dev-box.md".to_owned())
}
