//! systemd's notify protocol (`sd_notify(3)`), the three messages the runtime sends: `READY=1` once every thread is
//! running, `WATCHDOG=1` while the run makes progress, and `STOPPING=1` as it ends. Plain datagrams on the socket
//! systemd names in `NOTIFY_SOCKET`; no libsystemd.

use std::io;
use std::os::linux::net::SocketAddrExt as _;
use std::os::unix::net::{SocketAddr, UnixDatagram};
use std::time::Duration;

/// The socket systemd listens on for this service.
pub(crate) struct Notify {
    socket: UnixDatagram,
    to: SocketAddr,
}

impl Notify {
    /// The socket named by `NOTIFY_SOCKET`, or `None` when it isn't set: the runtime wasn't started by systemd with
    /// `Type=notify` (by hand, or by a test), and there is nobody to tell.
    ///
    /// # Errors
    /// The variable names an address this can't reach (empty, or not a path or an abstract name), or no socket could
    /// be made.
    pub(crate) fn from_env() -> Result<Option<Self>, String> {
        let Some(name) = std::env::var_os("NOTIFY_SOCKET") else {
            return Ok(None);
        };
        let bytes = name.as_encoded_bytes();
        let to = match bytes {
            // An abstract socket: `@` stands for the leading NUL.
            [b'@', rest @ ..] if !rest.is_empty() => SocketAddr::from_abstract_name(rest),
            [b'/', ..] => SocketAddr::from_pathname(&name),
            _ => {
                return Err(format!(
                    "NOTIFY_SOCKET {} is neither a path nor an abstract socket",
                    name.display()
                ));
            }
        }
        .map_err(|e| format!("NOTIFY_SOCKET {}: {e}", name.display()))?;
        let socket =
            UnixDatagram::unbound().map_err(|e| format!("can't make the notify socket: {e}"))?;
        // A send to a full socket fails at once rather than wait: the stop path and the watcher never block on
        // systemd (architecture.md section 2).
        socket
            .set_nonblocking(true)
            .map_err(|e| format!("can't make the notify socket non-blocking: {e}"))?;
        Ok(Some(Self { socket, to }))
    }

    /// Send one message, such as `READY=1`.
    ///
    /// # Errors
    /// The datagram didn't go: systemd is gone, or its socket is full (`WouldBlock`); never waits.
    pub(crate) fn send(&self, state: &str) -> io::Result<()> {
        self.socket
            .send_to_addr(state.as_bytes(), &self.to)
            .map(drop)
    }
}

/// The watchdog interval systemd asks of this process: `WATCHDOG_USEC`, unless `WATCHDOG_PID` names another process.
/// `Ok(None)` when there is no watchdog.
///
/// # Errors
/// `WATCHDOG_USEC` isn't a whole number of microseconds.
pub(crate) fn watchdog() -> Result<Option<Duration>, String> {
    let Ok(usec) = std::env::var("WATCHDOG_USEC") else {
        return Ok(None);
    };
    if std::env::var("WATCHDOG_PID").is_ok_and(|pid| pid != std::process::id().to_string()) {
        return Ok(None);
    }
    usec.parse()
        .map(|us| Some(Duration::from_micros(us)))
        .map_err(|e| format!("WATCHDOG_USEC {usec:?}: {e}"))
}
