//! Opening the interface under test, the check that nothing else is on the bus, and the kernel's link counters.

use std::fs::{File, OpenOptions};
use std::io;
use std::os::fd::AsFd;
use std::process::Command;
use std::time::{Duration, Instant};

use nix::errno::Errno;
use nix::fcntl::{Flock, FlockArg};
use nix::poll::{PollFd, PollFlags, ppoll};
use nix::sys::time::TimeSpec;
use socketcan::{CanFrame, CanSocket, Frame, Socket, SocketOptions};

use crate::frames;

/// The runtime's lock (`bins/runtime`): held for as long as a runtime runs.
const RUNTIME_LOCK: &str = "/run/robot/runtime.lock";

/// How long the bench listens before its first frame.
const LISTEN: Duration = Duration::from_secs(1);

/// `ENOBUFS`: the interface's queue is full. Counted, never retried (can.md section 2).
pub(crate) const ENOBUFS: i32 = 105;

/// Take the runtime's lock, shared, for the whole run, so the bench never runs alongside a runtime and a runtime can't
/// start under it. Shared, because the runtime takes it exclusive while both bench ends may run on one machine. `None` when this machine has never run one (no `/run/robot`); the lock is the runtime's, never made here.
pub(crate) fn claim_runtime_lock() -> Result<Option<Flock<File>>, String> {
    let file = match OpenOptions::new().read(true).write(true).open(RUNTIME_LOCK) {
        Ok(file) => file,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("{RUNTIME_LOCK}: {e}")),
    };
    match Flock::lock(file, FlockArg::LockSharedNonblock) {
        Ok(lock) => Ok(Some(lock)),
        Err((_, Errno::EWOULDBLOCK)) => Err(format!(
            "{RUNTIME_LOCK} is held: a runtime is running; stop it before can-bench"
        )),
        Err((_, e)) => Err(format!("{RUNTIME_LOCK}: {e}")),
    }
}

/// Open `bus` with error frames on and reads that don't block.
pub(crate) fn open(bus: &str) -> io::Result<CanSocket> {
    let socket = CanSocket::open(bus)?;
    socket.set_error_filter_accept_all()?;
    socket.set_nonblocking(true)?;
    Ok(socket)
}

/// Listen for one second and refuse if any frame that isn't this bench's own shows up: a drive reporting, the runtime,
/// the legacy stack. The bench runs with no drive on the bus (`README.md`); this catches the cases that announce
/// themselves. A drive that is powered but silent doesn't, which is why the procedure says to unplug them.
pub(crate) fn check_quiet(socket: &CanSocket, bus: &str) -> Result<(), String> {
    let end = Instant::now() + LISTEN;
    loop {
        let now = Instant::now();
        let Some(left) = end.checked_duration_since(now).filter(|d| !d.is_zero()) else {
            return Ok(());
        };
        wait(socket, left).map_err(|e| format!("{bus}: {e}"))?;
        while let Some(frame) = read(socket).map_err(|e| format!("{bus}: {e}"))? {
            if let CanFrame::Data(data) = frame
                && !frames::is_bench(data.raw_id())
            {
                return Err(format!(
                    "{bus}: frame {:08X} from something else on the bus; can-bench runs only with no drive and no \
                     other host on the bus",
                    data.raw_id()
                ));
            }
        }
    }
}

/// Wait up to `timeout` for a frame. True if one is ready.
pub(crate) fn wait(socket: &CanSocket, timeout: Duration) -> io::Result<bool> {
    let mut fds = [PollFd::new(socket.as_fd(), PollFlags::POLLIN)];
    match ppoll(&mut fds, Some(TimeSpec::from_duration(timeout)), None) {
        Ok(n) => Ok(n > 0),
        // A signal: no frame yet; the caller waits again until its deadline.
        Err(Errno::EINTR) => Ok(false),
        Err(e) => Err(e.into()),
    }
}

/// Read one frame without blocking. `None` when nothing is queued.
pub(crate) fn read(socket: &CanSocket) -> io::Result<Option<CanFrame>> {
    match socket.read_frame() {
        Ok(frame) => Ok(Some(frame)),
        Err(e) if e.kind() == io::ErrorKind::WouldBlock => Ok(None),
        Err(e) => Err(e),
    }
}

/// The kernel's counters for `bus`, from `ip -details -statistics -json link show`, as the JSON `ip` printed.
pub(crate) fn counters(bus: &str) -> Result<serde_json::Value, String> {
    let out = Command::new("ip")
        .args([
            "-details",
            "-statistics",
            "-json",
            "link",
            "show",
            "dev",
            bus,
        ])
        .output()
        .map_err(|e| format!("can't run ip: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "ip link show {bus}: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    serde_json::from_slice(&out.stdout).map_err(|e| format!("ip's JSON for {bus}: {e}"))
}

/// The driver behind `bus` (`gs_usb`, `slcan`, `mcp251x`, `mcp251xfd`, `peak_usb`, `vcan`), from sysfs.
pub(crate) fn driver(bus: &str) -> String {
    if let Ok(kind) = std::fs::read_link(format!("/sys/class/net/{bus}/device/driver")) {
        return kind
            .file_name()
            .map_or_else(String::new, |n| n.to_string_lossy().into_owned());
    }
    // `vcan` and `slcan` have no device behind them; the link kind names them.
    counters(bus)
        .ok()
        .and_then(|v| {
            v.get(0)?
                .get("linkinfo")?
                .get("info_kind")?
                .as_str()
                .map(str::to_owned)
        })
        .unwrap_or_else(|| "unknown".to_owned())
}
