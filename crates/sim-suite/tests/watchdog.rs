//! The runtime under systemd's notify protocol, as `deploy/systemd/runtime.service` runs it (`Type=notify`,
//! `WatchdogSec`): the real binary on `vcan` with the runtime's test robot (`bins/runtime/tests/skeleton.yaml`) and a
//! socket standing in for systemd's. Which passes feed the watchdog is the control thread's unit test
//! (`a_bus_behind_holds_the_watchdog_back_only_while_it_has_a_run`); this is the binary saying it.
//!
//! The binary comes from the build `scripts/sim.sh` makes before it runs the suite.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::io::BufRead as _;
use std::os::unix::net::UnixDatagram;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

use common::{binary, scratch};
use nix::sys::signal::{Signal, kill};
use nix::unistd::Pid;
use sim_drive::ensure_vcan;

/// The unit's `WatchdogSec`: a gap between two `WATCHDOG=1` longer than this is a gap systemd would kill for.
const WATCHDOG: Duration = Duration::from_secs(1);
/// Far past what a start or an end of the test robot takes, short of the test's 60 s limit.
const LONG: Duration = Duration::from_secs(10);

/// The next message on `socket`, or `None` when none comes within `within`.
fn next(socket: &UnixDatagram, within: Duration) -> Option<String> {
    socket.set_read_timeout(Some(within)).ok()?;
    let mut buf = [0u8; 256];
    let n = socket.recv(&mut buf).ok()?;
    Some(String::from_utf8_lossy(buf.get(..n)?).into_owned())
}

/// Guards: safety - the watchdog the unit relies on (PLAN item 3 and "Repo, toolchain, CI and deploy":
/// `Type=notify`, `WatchdogSec`): the runtime says `READY=1` first, once its threads run, then feeds `WATCHDOG=1` more
/// often than the unit's `WatchdogSec` while control makes progress, and says `STOPPING=1` when SIGTERM ends it, then
/// exits cleanly.
#[test]
fn the_runtime_says_ready_feeds_the_watchdog_and_says_stopping() {
    let skeleton =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bins/runtime/tests/skeleton.yaml");
    for name in ["can0", "can1"] {
        ensure_vcan(name).unwrap();
    }
    let dir = scratch("watchdog");
    let path = dir.join("notify");
    let socket = UnixDatagram::bind(&path).unwrap();
    let mut runtime = Command::new(binary("runtime"))
        .arg("--skeleton")
        .arg(&skeleton)
        .arg("--sessions")
        .arg(dir.join("sessions"))
        .arg("--lock")
        .arg(dir.join("runtime.lock"))
        .env("NOTIFY_SOCKET", &path)
        .env("WATCHDOG_USEC", WATCHDOG.as_micros().to_string())
        .env_remove("WATCHDOG_PID")
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    // Read on its own thread, so a full pipe never stalls the runtime; kept for the failure messages.
    let stderr = runtime.stderr.take().unwrap();
    let log = std::thread::spawn(move || {
        std::io::BufReader::new(stderr)
            .lines()
            .map_while(Result::ok)
            .collect::<Vec<_>>()
    });

    let ready = next(&socket, LONG);
    let fed: Vec<Option<String>> = (0..10).map(|_| next(&socket, WATCHDOG)).collect();
    kill(
        Pid::from_raw(i32::try_from(runtime.id()).unwrap()),
        Signal::SIGTERM,
    )
    .unwrap();
    // Any feed already on its way comes first.
    let stopping = std::iter::from_fn(|| next(&socket, LONG)).find(|m| m != "WATCHDOG=1");
    let status = runtime.wait().unwrap();
    let log = log.join().unwrap();
    let _ = std::fs::remove_dir_all(&dir);

    assert_eq!(ready.as_deref(), Some("READY=1"), "{log:#?}");
    for m in &fed {
        assert_eq!(m.as_deref(), Some("WATCHDOG=1"), "{fed:?} {log:#?}");
    }
    assert_eq!(stopping.as_deref(), Some("STOPPING=1"), "{log:#?}");
    assert!(status.success(), "{status} {log:#?}");
}
