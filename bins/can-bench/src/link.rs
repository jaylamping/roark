//! Opening the interface under test, the check that nothing else is on the bus, and the kernel's link counters.

use std::fs::{File, OpenOptions};
use std::io;
use std::os::fd::AsFd;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use nix::errno::Errno;
use nix::fcntl::{Flock, FlockArg};
use nix::poll::{PollFd, PollFlags, ppoll};
use nix::sys::time::TimeSpec;
use socketcan::{CanFrame, CanSocket, Frame, Socket, SocketOptions};

use crate::frames;

/// The runtime's lock (`bins/runtime`): held for as long as a runtime runs.
const RUNTIME_LOCK: &str = "/run/robot/runtime.lock";
/// The runtime's systemd unit (`deploy/systemd`).
const RUNTIME_UNIT: &str = "runtime.service";

/// How long the bench listens before its first frame.
const LISTEN: Duration = Duration::from_secs(1);

/// `ENOBUFS`: the interface's queue is full.
const ENOBUFS: i32 = 105;

/// Whether a write failed only because a queue was full: `ENOBUFS` from the interface's queue or `EAGAIN` from the
/// socket's. The frame is dropped and counted, never retried (can.md section 2, "No busy retry").
pub(crate) fn queue_full(e: &io::Error) -> bool {
    e.raw_os_error() == Some(ENOBUFS) || e.kind() == io::ErrorKind::WouldBlock
}

/// Which end of the bench a process is, for the quiet check.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Role {
    Host,
    Responder,
}

/// How long `systemctl` may take to answer.
const SYSTEMCTL_DEADLINE: Duration = Duration::from_secs(5);

/// Keep the runtime off the bus for the whole run. First the unit: refuse unless it is masked or not installed, so
/// nothing can start a runtime during the run (a lock alone can't promise that: systemd deletes `/run/robot` on every
/// stop, so a restarted runtime locks a fresh file). Then, if the runtime's lock exists, take it shared and refuse if a
/// runtime holds it, which catches one still running from before the mask. Shared, so both bench ends may run on one
/// machine. The lock file is the runtime's and never made here: one made by root under `sudo` could keep the
/// `User=robot` runtime from opening it.
pub(crate) fn exclude_runtime() -> Result<Option<Flock<File>>, String> {
    unit_cannot_start()?;
    match OpenOptions::new().read(true).write(true).open(RUNTIME_LOCK) {
        Ok(file) => match Flock::lock(file, FlockArg::LockSharedNonblock) {
            Ok(lock) => Ok(Some(lock)),
            Err((_, Errno::EWOULDBLOCK)) => Err(format!(
                "{RUNTIME_LOCK} is held: a runtime is running; stop it before can-bench"
            )),
            Err((_, e)) => Err(format!("{RUNTIME_LOCK}: {e}")),
        },
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(format!("{RUNTIME_LOCK}: {e}")),
    }
}

/// `Ok` only when systemd positively can't start the runtime: no systemd on this machine, or `systemctl is-enabled`
/// says the unit is masked or not installed. Any other answer, a failed query or no answer in time refuses.
fn unit_cannot_start() -> Result<(), String> {
    if !std::path::Path::new("/run/systemd/system").exists() {
        return Ok(());
    }
    let refuse = |why: String| {
        Err(format!(
            "{RUNTIME_UNIT}: {why}; something could start it during the run. \
             Run `sudo systemctl mask --runtime --now {RUNTIME_UNIT}` first (undone at the next boot)"
        ))
    };
    let mut child = match Command::new("systemctl")
        .args(["is-enabled", RUNTIME_UNIT])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(e) => return refuse(format!("systemctl failed to start ({e})")),
    };
    let give_up = Instant::now() + SYSTEMCTL_DEADLINE;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if Instant::now() < give_up => std::thread::sleep(Duration::from_millis(20)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return refuse("systemctl gave no answer in time".to_owned());
            }
            Err(e) => return refuse(format!("systemctl: {e}")),
        }
    }
    let out = child
        .wait_with_output()
        .map_err(|e| format!("systemctl: {e}"))?;
    let state = String::from_utf8_lossy(&out.stdout).trim().to_owned();
    let err = String::from_utf8_lossy(&out.stderr);
    // Older systemd prints nothing for a unit that isn't installed and says so on stderr.
    if state == "not-found"
        || state.starts_with("masked")
        || (state.is_empty() && err.contains("No such file"))
    {
        Ok(())
    } else if state.is_empty() {
        refuse(format!("systemctl gave no state ({})", err.trim()))
    } else {
        refuse(format!("is {state}"))
    }
}

/// Open `bus` with error frames on and reads that don't block.
pub(crate) fn open(bus: &str) -> io::Result<CanSocket> {
    let socket = CanSocket::open(bus)?;
    socket.set_error_filter_accept_all()?;
    socket.set_nonblocking(true)?;
    Ok(socket)
}

/// Listen for one second and refuse if anything else is on the bus: a drive reporting, the runtime, the legacy stack, an
/// error frame (a bus already in trouble) or a remote frame. A host refuses every frame, since anything it hears before
/// its first request is another host or its responder; a responder accepts only this bench's requests, from a host
/// already running. The bench runs with no drive on the bus (`README.md`); a drive that is powered but silent doesn't
/// announce itself, which is why the procedure says to unplug them.
pub(crate) fn check_quiet(socket: &CanSocket, bus: &str, role: Role) -> Result<(), String> {
    let end = Instant::now() + LISTEN;
    loop {
        let now = Instant::now();
        let Some(left) = end.checked_duration_since(now).filter(|d| !d.is_zero()) else {
            return Ok(());
        };
        wait(socket, left).map_err(|e| format!("{bus}: {e}"))?;
        while let Some(frame) = read(socket).map_err(|e| format!("{bus}: {e}"))? {
            let allowed = matches!(&frame, CanFrame::Data(d)
                if role == Role::Responder && frames::request_slot(d.raw_id()).is_some());
            if !allowed {
                return Err(format!(
                    "{bus}: frame {:08X} heard before starting; can-bench runs only on a quiet bus with no drive, no \
                     other host and no error",
                    frame.raw_id()
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
