//! One bus of simulated drives on a `vcan` socket: host frames in, each drive's replies out when they fall due.

use std::io::ErrorKind;
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use robstride::drive::{self, DriveFrame};
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket};

use crate::{Injected, SimDrive};

/// The longest the loop blocks on a read, so it notices `stop` and frames falling due.
const MAX_WAIT: Duration = Duration::from_millis(5);
/// A read timeout of zero would block forever, so the shortest wait is this.
const MIN_WAIT: Duration = Duration::from_micros(100);
/// `ENOBUFS`: the interface's queue is full. The frame is dropped and counted, never retried (can.md section 2).
const ENOBUFS: i32 = 105;

/// Why a bus can't be served.
#[derive(Debug, thiserror::Error)]
pub enum ServeError {
    /// The interface isn't a `vcan`, or can't be checked.
    #[error(transparent)]
    NotVcan(#[from] NotVcan),
    /// The socket failed.
    #[error("{bus}: {source}")]
    Socket {
        /// The interface.
        bus: String,
        /// What failed.
        source: std::io::Error,
    },
}

/// An interface `sim-drive` refuses to touch.
#[derive(Debug, thiserror::Error)]
pub enum NotVcan {
    /// `ip` says the interface is some other kind: a bus named `can1` can be the robot's real one.
    #[error(
        "{bus} is not a vcan interface; sim-drive only runs on vcan (`ip -details link show dev {bus}`)"
    )]
    OtherKind {
        /// The interface.
        bus: String,
    },
    /// `ip` couldn't show the interface: it doesn't exist, or `ip` isn't installed.
    #[error("{bus}: can't check its link kind: {reason}")]
    Unchecked {
        /// The interface.
        bus: String,
        /// What `ip` said, or why it didn't run.
        reason: String,
    },
}

/// Refuse unless `bus` is a `vcan` interface. Checked before the first frame on every socket `sim-drive` opens, and by
/// every sim test, so neither can send to a real drive. Anything `ip` doesn't answer with link kind `vcan` is refused.
///
/// # Errors
/// [`NotVcan`].
pub fn ensure_vcan(bus: &str) -> Result<(), NotVcan> {
    let unchecked = |reason: String| NotVcan::Unchecked {
        bus: bus.to_owned(),
        reason,
    };
    if bus.is_empty() || bus.starts_with('-') {
        return Err(unchecked("not an interface name".to_owned()));
    }
    let out = Command::new("ip")
        .args(["-details", "-json", "link", "show", "dev", bus])
        .output()
        .map_err(|e| unchecked(format!("ip didn't run: {e}")))?;
    if !out.status.success() {
        return Err(unchecked(
            String::from_utf8_lossy(&out.stderr).trim().to_owned(),
        ));
    }
    // iproute2's JSON is compact: a vcan link carries exactly this pair. Any other shape is refused.
    if String::from_utf8_lossy(&out.stdout).contains(r#""info_kind":"vcan""#) {
        Ok(())
    } else {
        Err(NotVcan::OtherKind {
            bus: bus.to_owned(),
        })
    }
}

/// Serve `drives` on `bus` until `stop` is set: each host frame goes to the drive it targets, and each drive's frames go
/// out when they fall due. Frames that aren't host commands (other drives' replies, garbage) are ignored. Every fault
/// injected into a drive, scheduled before serving or fired on its trigger, is handed to `injected` as it takes
/// effect, for the recording's `/fault_injected` (logging.md section 3).
///
/// # Errors
/// [`ServeError`] if `bus` isn't `vcan` or its socket fails.
pub fn serve(
    bus: &str,
    drives: &mut [SimDrive],
    stop: &AtomicBool,
    injected: &mut dyn FnMut(Injected),
) -> Result<(), ServeError> {
    ensure_vcan(bus)?;
    let io = |source| ServeError::Socket {
        bus: bus.to_owned(),
        source,
    };
    let socket = CanSocket::open(bus).map_err(io)?;
    while !stop.load(Ordering::Relaxed) {
        let now = Instant::now();
        for sim in drives.iter_mut() {
            while let Some(frame) = sim.pop_due(now) {
                send(&socket, frame).map_err(io)?;
            }
            while let Some(fault) = sim.take_injected() {
                injected(fault);
            }
        }
        let next = drives.iter().filter_map(SimDrive::next_event).min();
        let wait = next.map_or(MAX_WAIT, |at| at.saturating_duration_since(now));
        socket
            .set_read_timeout(wait.clamp(MIN_WAIT, MAX_WAIT))
            .map_err(io)?;
        match socket.read_frame() {
            Ok(CanFrame::Data(frame)) => {
                let Id::Extended(id) = frame.id() else {
                    continue;
                };
                if let Ok(Some(host)) = drive::command(id.as_raw(), frame.data()) {
                    let now = Instant::now();
                    for sim in drives.iter_mut() {
                        sim.receive(now, host);
                    }
                }
            }
            Ok(CanFrame::Remote(_) | CanFrame::Error(_)) => {}
            Err(e) if matches!(e.kind(), ErrorKind::WouldBlock | ErrorKind::TimedOut) => {}
            Err(e) => return Err(io(e)),
        }
    }
    Ok(())
}

fn send(socket: &CanSocket, frame: DriveFrame) -> std::io::Result<()> {
    let id = ExtendedId::new(frame.id())
        .ok_or_else(|| std::io::Error::other("ID wider than 29 bits"))?;
    let data =
        CanDataFrame::new(id, &frame.data()).ok_or_else(|| std::io::Error::other("bad frame"))?;
    match socket.write_frame(&data) {
        Err(e) if e.raw_os_error() == Some(ENOBUFS) || e.kind() == ErrorKind::WouldBlock => Ok(()),
        other => other,
    }
}
